"""
Media Ingestion Module
Handles local video files, URL downloading via yt-dlp, and audio extraction/normalization.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

from src.media_inspector import MediaInspector, MediaMetadata

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    source_type: str  # "local" or "url"
    original_input: str
    video_path: str
    audio_path: str
    metadata: MediaMetadata


class MediaIngestor:
    def __init__(
        self,
        output_dir: str = "temp",
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.inspector = MediaInspector(ffprobe_path=ffprobe_path)
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()

    @staticmethod
    def _find_ffmpeg() -> str:
        local_bin = os.path.abspath("bin/ffmpeg.exe")
        if os.path.exists(local_bin):
            return local_bin
        found = shutil.which("ffmpeg")
        if found:
            return found
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin\ffmpeg.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\ffmpeg\bin\ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "ffmpeg"

    def is_url(self, path_or_url: str) -> bool:
        """Determines if the provided input is a web URL."""
        try:
            parsed = urlparse(path_or_url)
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    def ingest(
        self,
        input_source: str,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> IngestionResult:
        """
        Accepts a local file path or web URL, downloads if needed,
        verifies metadata, and extracts normalized 16kHz mono audio.
        """
        if self.is_url(input_source):
            if progress_callback:
                progress_callback("Downloading media from URL...", 0.1)
            video_path = self._download_url(input_source)
            source_type = "url"
        else:
            if not os.path.isfile(input_source):
                raise FileNotFoundError(f"Input video file not found: {input_source}")
            video_path = os.path.abspath(input_source)
            source_type = "local"

        if progress_callback:
            progress_callback("Extracting video metadata...", 0.3)

        metadata = self.inspector.inspect(video_path)

        if not metadata.has_video:
            raise ValueError(f"Input file contains no video stream: {video_path}")

        if progress_callback:
            progress_callback("Extracting and normalizing audio...", 0.5)

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        audio_path = os.path.join(self.output_dir, f"{base_name}_audio16k.wav")

        self._extract_audio(video_path, audio_path)

        if progress_callback:
            progress_callback("Ingestion complete.", 1.0)

        return IngestionResult(
            source_type=source_type,
            original_input=input_source,
            video_path=video_path,
            audio_path=audio_path,
            metadata=metadata
        )

    def _download_url(self, url: str) -> str:
        """Downloads video using yt-dlp to output_dir."""
        try:
            import yt_dlp
        except ImportError:
            raise RuntimeError("yt-dlp package is required for URL downloads.")

        output_template = os.path.join(self.output_dir, "%(id)s.%(ext)s")
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = ydl.prepare_filename(info)
            if not os.path.exists(downloaded):
                # Check for possible ext change e.g. .mkv
                root, _ = os.path.splitext(downloaded)
                for ext in [".mp4", ".mkv", ".webm"]:
                    if os.path.exists(root + ext):
                        downloaded = root + ext
                        break
            return os.path.abspath(downloaded)

    def _extract_audio(self, video_path: str, audio_path: str) -> str:
        """Extracts 16kHz mono WAV for high-accuracy Whisper speech recognition."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            audio_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"FFmpeg audio extraction failed: {res.stderr}. Checking fallback...")
            # If video has no audio track, generate silent WAV to maintain pipeline integrity
            self._generate_silent_audio(audio_path, duration=10.0)

        return audio_path

    def _generate_silent_audio(self, audio_path: str, duration: float = 10.0):
        """Generates a brief silent WAV file if source has no audio."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=16000:cl=mono",
            "-t", str(duration),
            audio_path
        ]
        subprocess.run(cmd, capture_output=True)
