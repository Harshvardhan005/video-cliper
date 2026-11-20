"""
Audio Processor Module
Performs professional audio loudness normalization (EBU R128),
peak limiting, and noise cleanup for social media publication.
"""

import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Applies professional loudness normalization and audio mastering filters."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def build_audio_filter(
        self,
        target_loudness_lufs: float = -14.0,  # Standard for YouTube Shorts, Reels & TikTok
        loudness_range: float = 8.0,
        true_peak: float = -1.5
    ) -> str:
        """
        Generates FFmpeg audio filter for two-pass or single-pass dynamic EBU R128 loudness.
        """
        # loudnorm filter provides broadcast compliance and punchy social presence
        return (
            f"loudnorm=I={target_loudness_lufs}:LRA={loudness_range}:tp={true_peak}:print_format=summary,"
            f"alimiter=limit=-1.0dB:attack=5:release=50"
        )

