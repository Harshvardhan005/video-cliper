"""
Media Inspector Module
Robust extraction of media metadata using ffprobe with OpenCV/Python fallback.
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MediaMetadata:
    file_path: str
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: Optional[str]
    audio_channels: int
    audio_sample_rate: int
    bitrate: int
    rotation: int
    has_audio: bool
    has_video: bool
    subtitle_tracks: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MediaInspector:
    def __init__(self, ffprobe_path: Optional[str] = None):
        self.ffprobe_path = ffprobe_path or self._find_ffprobe()

    @staticmethod
    def _find_ffprobe() -> str:
        # Check local bin first
        local_bin = os.path.abspath("bin/ffprobe.exe")
        if os.path.exists(local_bin):
            return local_bin

        # Check standard PATH
        found = shutil.which("ffprobe")
        if found:
            return found

        # Common Windows paths for winget / Gyan / scoop
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin\ffprobe.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\ffmpeg\bin\ffprobe.exe"),
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\ProgramData\chocolatey\bin\ffprobe.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "ffprobe"

    def inspect(self, media_path: str) -> MediaMetadata:
        """Inspects media file and returns structured metadata."""
        if not os.path.isfile(media_path):
            raise FileNotFoundError(f"Media file not found: {media_path}")

        try:
            return self._inspect_ffprobe(media_path)
        except Exception as e:
            logger.warning(f"ffprobe extraction failed ({e}), falling back to OpenCV/fallback inspector.")
            return self._inspect_opencv_fallback(media_path)

    def _inspect_ffprobe(self, media_path: str) -> MediaMetadata:
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            media_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)

        video_stream = None
        audio_stream = None
        subtitle_tracks = []

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream
            elif codec_type == "subtitle":
                subtitle_tracks.append({
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name"),
                    "language": stream.get("tags", {}).get("language", "und")
                })

        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0.0))
        bitrate = int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else 0

        width = 0
        height = 0
        fps = 30.0
        video_codec = "none"
        rotation = 0

        if video_stream:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            video_codec = video_stream.get("codec_name", "unknown")

            # Parse rotation
            tags = video_stream.get("tags", {})
            side_data = video_stream.get("side_data_list", [])
            for sd in side_data:
                if "rotation" in sd:
                    rotation = int(sd["rotation"])
            if "rotate" in tags:
                rotation = int(tags["rotate"])

            # FPS parsing
            r_frame_rate = video_stream.get("r_frame_rate", "30/1")
            try:
                num, den = map(int, r_frame_rate.split("/"))
                fps = round(num / den, 2) if den > 0 else 30.0
            except Exception:
                fps = 30.0

            if duration == 0.0 and "duration" in video_stream:
                try:
                    duration = float(video_stream["duration"])
                except Exception:
                    pass

        has_audio = audio_stream is not None
        audio_codec = audio_stream.get("codec_name") if audio_stream else None
        audio_channels = int(audio_stream.get("channels", 0)) if audio_stream else 0
        audio_sample_rate = int(audio_stream.get("sample_rate", 0)) if audio_stream else 0

        return MediaMetadata(
            file_path=os.path.abspath(media_path),
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            video_codec=video_codec,
            audio_codec=audio_codec,
            audio_channels=audio_channels,
            audio_sample_rate=audio_sample_rate,
            bitrate=bitrate,
            rotation=rotation,
            has_audio=has_audio,
            has_video=video_stream is not None,
            subtitle_tracks=subtitle_tracks
        )

    def _inspect_opencv_fallback(self, media_path: str) -> MediaMetadata:
        try:
            import cv2
            cap = cv2.VideoCapture(media_path)
            if not cap.isOpened():
                raise RuntimeError(f"Unable to open media file: {media_path}")

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = float(frame_count / fps) if fps > 0 else 0.0
            cap.release()

            return MediaMetadata(
                file_path=os.path.abspath(media_path),
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                video_codec="unknown_cv2",
                audio_codec=None,
                audio_channels=0,
                audio_sample_rate=0,
                bitrate=0,
                rotation=0,
                has_audio=False,
                has_video=True,
                subtitle_tracks=[]
            )
        except Exception as e:
            raise RuntimeError(f"Could not inspect media: {e}")
