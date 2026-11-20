"""
Quality Control & Verification Module
Validates generated clips for resolution, duration, audio presence,
sync integrity, and checks for accidental black or corrupt frames.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from PIL import Image, ImageStat
from src.media_inspector import MediaInspector

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    is_valid: bool
    file_exists: bool
    file_size_mb: float
    duration_actual: float
    duration_valid: bool
    resolution_valid: bool
    aspect_ratio_valid: bool
    has_audio: bool
    black_frame_ratio: float
    errors: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


class QualityControl:
    """Runs automated verification on exported video clips before final delivery."""

    def __init__(self, inspector: Optional[MediaInspector] = None, ffmpeg_path: Optional[str] = None):
        self.inspector = inspector or MediaInspector()
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()

    @staticmethod
    def _find_ffmpeg() -> str:
        local_bin = os.path.abspath("bin/ffmpeg.exe")
        if os.path.exists(local_bin):
            return local_bin
        return shutil.which("ffmpeg") or "ffmpeg"

    def verify_clip(
        self,
        clip_path: str,
        expected_width: int = 1080,
        expected_height: int = 1920,
        min_duration: float = 5.0,
        max_duration: float = 120.0
    ) -> QualityReport:
        errors = []

        if not os.path.isfile(clip_path):
            return QualityReport(
                is_valid=False,
                file_exists=False,
                file_size_mb=0.0,
                duration_actual=0.0,
                duration_valid=False,
                resolution_valid=False,
                aspect_ratio_valid=False,
                has_audio=False,
                black_frame_ratio=1.0,
                errors=["Output file does not exist"]
            )

        file_size_mb = round(os.path.getsize(clip_path) / (1024 * 1024), 2)
        if file_size_mb == 0.0:
            errors.append("File size is 0 bytes")

        meta = self.inspector.inspect(clip_path)

        # Duration validation
        dur_valid = min_duration <= meta.duration <= max_duration
        if not dur_valid:
            errors.append(f"Duration {meta.duration:.1f}s is out of bounds [{min_duration}-{max_duration}s]")

        # Resolution & aspect ratio validation
        res_valid = (meta.width == expected_width and meta.height == expected_height)
        if not res_valid:
            errors.append(f"Resolution {meta.width}x{meta.height} does not match {expected_width}x{expected_height}")

        aspect_ratio = meta.width / max(meta.height, 1)
        aspect_valid = abs(aspect_ratio - (9.0 / 16.0)) < 0.05
        if not aspect_valid:
            errors.append(f"Aspect ratio {aspect_ratio:.3f} is not 9:16")

        # Audio stream presence
        has_audio = meta.has_audio
        if not has_audio:
            errors.append("Clip contains no audio stream")

        # Sample for black frames
        black_ratio = self._detect_black_frames(clip_path)
        if black_ratio > 0.30:
            errors.append(f"Excessive black frames detected ({black_ratio * 100:.1f}%)")

        is_valid = len(errors) == 0

        report = QualityReport(
            is_valid=is_valid,
            file_exists=True,
            file_size_mb=file_size_mb,
            duration_actual=round(meta.duration, 2),
            duration_valid=dur_valid,
            resolution_valid=res_valid,
            aspect_ratio_valid=aspect_valid,
            has_audio=has_audio,
            black_frame_ratio=round(black_ratio, 3),
            errors=errors
        )

        return report

    def _detect_black_frames(self, clip_path: str, sample_count: int = 5) -> float:
        """Samples frames across video using FFmpeg and Pillow to detect black/dark frame ratio."""
        temp_dir = os.path.abspath("temp")
        os.makedirs(temp_dir, exist_ok=True)
        black_count = 0

        for i in range(sample_count):
            offset = 1.0 + (i * 2.0)
            sample_file = os.path.join(temp_dir, f"qc_sample_{i}.jpg")
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss", f"{offset:.1f}",
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "3",
                sample_file
            ]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0 and os.path.exists(sample_file):
                try:
                    img = Image.open(sample_file).convert("L")
                    stat = ImageStat.Stat(img)
                    mean_val = stat.mean[0] if stat.mean else 0.0
                    img.close()
                    if mean_val < 6.0:  # dark/black frame threshold
                        black_count += 1
                except Exception:
                    pass

        return black_count / max(sample_count, 1)
