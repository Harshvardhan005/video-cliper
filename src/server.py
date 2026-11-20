"""
Autonomous Video Clipper Studio - High-Performance Web Server
Provides REST API, Server-Sent Events (SSE) progress streaming,
file range streaming, and unified web dashboard serving.
"""

import cgi
import json
import logging
import os
import shutil
import sys
import threading
import time
import urllib.parse
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import PipelineResult, VideoClipperPipeline

logger = logging.getLogger(__name__)

# In-memory job tracker
JOBS: Dict[str, Dict] = {}


class ClipperServerHandler(BaseHTTPRequestHandler):
    pipeline = VideoClipperPipeline()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_file("dashboard/index.html", "text/html")
        elif path.startswith("/api/progress/"):
            job_id = path.split("/")[-1]
            self._serve_sse_progress(job_id)
        elif path.startswith("/api/results/"):
            job_id = path.split("/")[-1]
            self._serve_results(job_id)
        elif path == "/api/file":
            file_path = query.get("path", [None])[0]
            self._serve_media_file(file_path)
        elif path.startswith("/api/download-all/"):
            job_id = path.split("/")[-1]
            self._serve_zip(job_id)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/process":
            self._handle_process()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _serve_file(self, file_path: str, content_type: str):
        if not os.path.exists(file_path):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        with open(file_path, "rb") as f:
            data = f.read()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_media_file(self, file_path: Optional[str]):
        if not file_path or not os.path.isfile(file_path):
            self.send_error(HTTPStatus.NOT_FOUND, "Media file not found")
            return

        file_size = os.path.getsize(file_path)
        content_type = "video/mp4" if file_path.endswith(".mp4") else "image/jpeg"

        # Support HTTP Range requests for video seeking
        range_header = self.headers.get("Range")
        if range_header:
            try:
                byte_range = range_header.strip().split("=")[-1]
                start_str, end_str = byte_range.split("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                length = end - start + 1

                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(file_path, "rb") as f:
                    f.seek(start)
                    self.wfile.write(f.read(length))
                return
            except Exception as e:
                logger.warning(f"Error handling range request: {e}")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        with open(file_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def _serve_sse_progress(self, job_id: str):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        last_progress = -1.0
        while True:
            job = JOBS.get(job_id)
            if not job:
                msg = json.dumps({"status": "waiting", "message": "Initializing...", "progress": 0.05})
                self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.5)
                continue

            current_progress = job.get("progress", 0.0)
            if current_progress != last_progress or job.get("status") in ("completed", "failed"):
                last_progress = current_progress
                payload = {
                    "status": job.get("status"),
                    "message": job.get("message", "Processing..."),
                    "progress": current_progress,
                    "error": job.get("error")
                }
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                self.wfile.flush()

            if job.get("status") in ("completed", "failed"):
                break

            time.sleep(0.4)

    def _serve_results(self, job_id: str):
        job = JOBS.get(job_id)
        if not job or "result" not in job:
            self.send_error(HTTPStatus.NOT_FOUND, "Job results not ready")
            return

        res_dict = job["result"].to_dict()
        data = json.dumps(res_dict).encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_zip(self, job_id: str):
        job = JOBS.get(job_id)
        if not job or "result" not in job:
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return

        zip_path = os.path.join("temp", f"{job_id}_export.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for clip in job["result"].clips:
                if os.path.exists(clip.clip_video_path):
                    zipf.write(clip.clip_video_path, f"clips/{os.path.basename(clip.clip_video_path)}")
                if os.path.exists(clip.thumbnail_path):
                    zipf.write(clip.thumbnail_path, f"thumbnails/{os.path.basename(clip.thumbnail_path)}")
                if os.path.exists(clip.ass_caption_path):
                    zipf.write(clip.ass_caption_path, f"captions/{os.path.basename(clip.ass_caption_path)}")
                if os.path.exists(clip.metadata_json_path):
                    zipf.write(clip.metadata_json_path, f"metadata/{os.path.basename(clip.metadata_json_path)}")

        self._serve_file(zip_path, "application/zip")

    def _handle_process(self):
        ctype, pdict = cgi.parse_header(self.headers.get("content-type"))
        job_id = f"job_{int(time.time())}"

        url = None
        local_file_path = None
        caption_preset = "hormozi"
        duration_preset = "medium"
        max_clips = 5
        layout_mode = "smart_auto"

        if ctype == "multipart/form-data":
            pdict["boundary"] = bytes(pdict["boundary"], "utf-8")
            pdict["CONTENT-LENGTH"] = int(self.headers.get("Content-Length", 0))
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})

            if "url" in form and form["url"].value:
                url = form["url"].value
            if "caption_preset" in form:
                caption_preset = form["caption_preset"].value
            if "duration_preset" in form:
                duration_preset = form["duration_preset"].value
            if "max_clips" in form:
                try:
                    max_clips = int(form["max_clips"].value)
                except Exception:
                    pass
            if "layout_mode" in form:
                layout_mode = form["layout_mode"].value

            if "file" in form and form["file"].filename:
                file_item = form["file"]
                os.makedirs("input", exist_ok=True)
                clean_name = os.path.basename(file_item.filename)
                save_path = os.path.join("input", f"{job_id}_{clean_name}")
                with open(save_path, "wb") as f:
                    f.write(file_item.file.read())
                local_file_path = save_path

        elif ctype == "application/json":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            url = body.get("url")
            caption_preset = body.get("caption_preset", "hormozi")
            duration_preset = body.get("duration_preset", "medium")
            max_clips = int(body.get("max_clips", 5))
            layout_mode = body.get("layout_mode", "smart_auto")

        input_target = local_file_path or url
        if not input_target:
            self.send_error(HTTPStatus.BAD_REQUEST, "No input video or URL provided")
            return

        JOBS[job_id] = {
            "status": "queued",
            "progress": 0.05,
            "message": "Queued for processing..."
        }

        # Spawn pipeline thread
        t = threading.Thread(
            target=self._run_pipeline_worker,
            args=(job_id, input_target, duration_preset, max_clips, caption_preset, layout_mode),
            daemon=True
        )
        t.start()

        # Respond with job ID
        resp = json.dumps({"job_id": job_id}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def _run_pipeline_worker(
        self,
        job_id: str,
        input_target: str,
        duration_preset: str,
        max_clips: int,
        caption_preset: str,
        layout_mode: str
    ):
        try:
            JOBS[job_id]["status"] = "processing"

            def on_progress(msg: str, pct: float):
                JOBS[job_id]["message"] = msg
                JOBS[job_id]["progress"] = round(pct, 2)

            res: PipelineResult = self.pipeline.process(
                input_source=input_target,
                job_id=job_id,
                duration_preset=duration_preset,
                max_clips=max_clips,
                caption_preset=caption_preset,
                layout_mode=layout_mode,
                progress_callback=on_progress
            )

            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["progress"] = 1.0
            JOBS[job_id]["message"] = "Completed successfully!"
            JOBS[job_id]["result"] = res

        except Exception as e:
            logger.exception(f"Pipeline error for job {job_id}: {e}")
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
            JOBS[job_id]["message"] = f"Failed: {e}"


def run_server(host: str = "127.0.0.1", port: int = 8000):
    server_address = (host, port)
    httpd = HTTPServer(server_address, ClipperServerHandler)
    print(f"🎬 AutoClip AI Studio Server running at: http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    run_server(host=host, port=port)
