"""
Smart 9:16 Video Reframing Module
Calculates crop geometries and generates FFmpeg filter expressions for:
- Dynamic face-tracked vertical crop
- Blurred background pillarbox / letterbox
- Split-screen podcast layout
- Direct scaling
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.face_tracker import FaceTracker

logger = logging.getLogger(__name__)


class SmartCropper:
    """Builds optimal 9:16 (1080x1920) video transformation pipelines."""

    def __init__(
        self,
        target_width: int = 1080,
        target_height: int = 1920,
        face_tracker: Optional[FaceTracker] = None
    ):
        self.target_width = target_width
        self.target_height = target_height
        self.face_tracker = face_tracker or FaceTracker()

    def build_crop_filter(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        source_width: int,
        source_height: int,
        layout_mode: str = "smart_auto"  # "smart_auto", "face_crop", "blurred_bg", "split_screen"
    ) -> str:
        """
        Produces an FFmpeg video filter (-vf) string for 1080x1920 output.
        """
        source_aspect = source_width / max(source_height, 1)
        target_aspect = self.target_width / self.target_height  # 9/16 = 0.5625

        # If source is already vertical or close (e.g. 9:16)
        if abs(source_aspect - target_aspect) < 0.05:
            return f"scale={self.target_width}:{self.target_height}:force_original_aspect_ratio=decrease,pad={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2"

        # Determine mode
        if layout_mode == "smart_auto":
            # For wide 16:9 videos, default to smart face crop with fallback to blurred background
            layout_mode = "face_crop"

        if layout_mode == "face_crop":
            # In landscape (e.g. 1920x1080), crop window height matches source_height (1080)
            # Crop window width = 1080 * (9/16) = 607.5 -> 608 pixels
            crop_h = source_height
            crop_w = int(round(crop_h * target_aspect))
            if crop_w % 2 != 0:
                crop_w += 1

            if crop_w <= source_width:
                # Track face across the clip
                trajectory = self.face_tracker.track_video_crop_center(
                    video_path=video_path,
                    start_time=start_time,
                    end_time=end_time,
                    source_width=source_width,
                    source_height=source_height,
                    crop_width=crop_w
                )

                # Compute weighted average crop_x for stable cinematic framing
                avg_crop_x = int(sum(x for _, x in trajectory) / max(len(trajectory), 1))
                avg_crop_x = max(0, min(source_width - crop_w, avg_crop_x))

                # Crop followed by scale to 1080x1920
                return f"crop={crop_w}:{crop_h}:{avg_crop_x}:0,scale={self.target_width}:{self.target_height}"

        if layout_mode == "split_screen":
            # Dual stacked panels (top: speaker crop, bottom: wide contextual view)
            top_h = int(self.target_height / 2)
            bot_h = self.target_height - top_h
            return (
                f"[0:v]split=2[vtop][vbot];"
                f"[vtop]crop=iw*0.5:ih:iw*0.25:0,scale={self.target_width}:{top_h}[top];"
                f"[vbot]scale={self.target_width}:{bot_h}:force_original_aspect_ratio=increase,crop={self.target_width}:{bot_h}[bot];"
                f"[top][bot]vstack=inputs=2"
            )

        # Fallback: Blurred Background Layout (Ultra-reliable, aesthetic for landscape clips)
        # Background: scaled & blurred with boxblur. Foreground: scaled to fit width, centered on top.
        return (
            f"split=2[bg][fg];"
            f"[bg]scale={self.target_width}:{self.target_height}:force_original_aspect_ratio=increase,"
            f"crop={self.target_width}:{self.target_height},boxblur=25:5[blurred];"
            f"[fg]scale={self.target_width}:-1[scaled_fg];"
            f"[blurred][scaled_fg]overlay=(W-w)/2:(H-h)/2"
        )

