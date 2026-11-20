"""
Automated Thumbnail Generator Module
Selects high-impact frames with clear facial expressions and applies
bold typography and viral visual hooks using FFmpeg and Pillow.
"""

import logging
import os
import shutil
import subprocess
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageStat

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """Generates high-CTR 1080x1920 vertical thumbnails for short-form clips."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()

    @staticmethod
    def _find_ffmpeg() -> str:
        local_bin = os.path.abspath("bin/ffmpeg.exe")
        if os.path.exists(local_bin):
            return local_bin
        return shutil.which("ffmpeg") or "ffmpeg"

    def generate_thumbnail(
        self,
        clip_path: str,
        headline_text: str,
        output_thumb_path: str,
        badge_text: str = "VIRAL MOMENT"
    ) -> str:
        """
        Extracts optimal frame from the clip and overlays branded thumbnail typography.
        """
        os.makedirs(os.path.dirname(output_thumb_path), exist_ok=True)

        # 1. Extract best frame
        frame_img = self._find_best_frame(clip_path)

        # 2. Resize to 1080x1920 canvas
        thumb_image = frame_img.resize((1080, 1920), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(thumb_image, "RGBA")

        # 3. Top viral badge
        if badge_text:
            badge_bg = (235, 30, 30, 235)  # Viral punchy red
            draw.rounded_rectangle([(60, 240), (460, 320)], radius=18, fill=badge_bg)
            try:
                badge_font = ImageFont.truetype("arialbd.ttf", 38)
            except Exception:
                badge_font = ImageFont.load_default()
            draw.text((80, 258), badge_text.upper(), font=badge_font, fill=(255, 255, 255, 255))

        # 4. Main Headline
        clean_headline = headline_text.upper().strip()
        lines = self._wrap_text(clean_headline, max_chars_per_line=15)

        try:
            title_font = ImageFont.truetype("impact.ttf", 84)
        except Exception:
            try:
                title_font = ImageFont.truetype("arialbd.ttf", 74)
            except Exception:
                title_font = ImageFont.load_default()

        start_y = 360
        line_height = 98

        for idx, line in enumerate(lines[:3]):
            y = start_y + (idx * line_height)
            # Text outline / shadow for crisp readability
            for ox in range(-4, 5):
                for oy in range(-4, 5):
                    draw.text((70 + ox, y + oy), line, font=title_font, fill=(0, 0, 0, 255))
            # Text fill (gold highlight for middle line, white for others)
            fill_color = (255, 235, 50, 255) if idx == 1 else (255, 255, 255, 255)
            draw.text((70, y), line, font=title_font, fill=fill_color)

        # Save thumbnail
        thumb_image.convert("RGB").save(output_thumb_path, format="JPEG", quality=92)
        logger.info(f"Generated thumbnail at: {output_thumb_path}")
        return output_thumb_path

    def _find_best_frame(self, clip_path: str) -> Image.Image:
        """Samples frames across the clip using FFmpeg and selects the one with highest visual contrast."""
        temp_dir = os.path.abspath("temp")
        os.makedirs(temp_dir, exist_ok=True)

        # Sample at 1s, 2s, 3s
        best_img = None
        best_variance = -1.0

        for offset in [1.5, 2.5, 3.5]:
            sample_file = os.path.join(temp_dir, f"sample_{offset:.1f}.jpg")
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss", f"{offset:.1f}",
                "-i", clip_path,
                "-vframes", "1",
                "-q:v", "2",
                sample_file
            ]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0 and os.path.exists(sample_file):
                try:
                    img = Image.open(sample_file)
                    stat = ImageStat.Stat(img.convert("L"))
                    variance = stat.var[0] if stat.var else 0.0
                    if variance > best_variance:
                        best_variance = variance
                        best_img = img.copy()
                    img.close()
                except Exception:
                    pass

        if best_img is None:
            # Fallback black canvas
            best_img = Image.new("RGB", (1080, 1920), color=(15, 20, 34))

        return best_img

    @staticmethod
    def _wrap_text(text: str, max_chars_per_line: int = 15) -> List[str]:
        words = text.split()
        lines = []
        cur = []
        for w in words:
            if sum(len(x) for x in cur) + len(cur) + len(w) <= max_chars_per_line:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        return lines
