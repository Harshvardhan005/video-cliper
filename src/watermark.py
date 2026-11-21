"""
Watermark & Branding Engine
Generates and injects customizable creator watermarks (e.g. @BallQ_FC)
into video streams, subtitle tracks, and composite overlays.
"""

import logging
import os
import re
from typing import Optional, Tuple
import yaml
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class WatermarkManager:
    """Manages watermark branding across video renders and caption tracks."""

    DEFAULT_WATERMARK = "@BallQ_FC"

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

        branding = self.config.get("branding", {})
        self.text: str = branding.get("watermark", self.DEFAULT_WATERMARK)
        self.enabled: bool = branding.get("enabled", True)
        self.opacity: float = branding.get("opacity", 0.85)
        self.font_size: int = branding.get("font_size", 34)
        self.position: str = branding.get("position", "center_below_video")

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return data or {}
            except Exception as e:
                logger.warning(f"Could not read settings from {self.config_path}: {e}")
        return {}

    def get_coordinates(self, width: int = 1080, height: int = 1920) -> Tuple[int, int]:
        """Returns (x, y) center anchor coordinates based on configured position."""
        pos = self.position.lower()
        if pos == "center_below_video":
            return (width // 2, 1285)
        elif pos == "center_above_video":
            return (width // 2, 620)
        elif pos == "top_right":
            return (width - 150, 100)
        elif pos == "top_left":
            return (150, 100)
        elif pos == "bottom_right":
            return (width - 150, height - 120)
        else:
            return (width // 2, 1285)

    def get_ass_style_and_event(self, clip_duration: float = 3600.0) -> Tuple[str, str]:
        """
        Returns the ASS Style definition and Dialogue event for burning the watermark.
        """
        if not self.enabled or not self.text:
            return "", ""

        # Calculate alpha for ASS (&H<AA><BB><GG><RR>& where 00 is opaque, FF is transparent)
        alpha_int = int((1.0 - max(0.1, min(1.0, self.opacity))) * 255)
        alpha_hex = f"{alpha_int:02X}"

        # Style definition
        style_line = (
            f"Style: Watermark,Arial,{self.font_size},"
            f"&H{alpha_hex}FFFFFF,&H000000FF,&H80000000,&H90000000,"
            f"-1,0,0,0,100,100,0,0,1,3,2,5,0,0,0,1"
        )

        cx, cy = self.get_coordinates()
        # Convert duration to ASS timestamp (H:MM:SS.cs)
        hours = int(clip_duration // 3600)
        minutes = int((clip_duration % 3600) // 60)
        seconds = clip_duration % 60
        end_time_str = f"{hours}:{minutes:02d}:{seconds:05.2f}"

        dialogue_line = (
            f"Dialogue: 2,0:00:00.00,{end_time_str},Watermark,,0,0,0,,"
            f"{{\\an5\\pos({cx},{cy})\\fad(400,400)}}{self.text}"
        )
        return style_line, dialogue_line

    def inject_into_ass_file(self, ass_file_path: str, clip_duration: float = 3600.0) -> bool:
        """
        Injects the watermark style and dialogue event into an existing ASS subtitle file.
        """
        if not self.enabled or not self.text or not os.path.exists(ass_file_path):
            return False

        with open(ass_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if f"Style: Watermark" in content or self.text in content:
            return True  # Already injected

        style_line, dialogue_line = self.get_ass_style_and_event(clip_duration)
        if not style_line:
            return False

        # Insert style under [V4+ Styles]
        if "[V4+ Styles]" in content:
            parts = content.split("[V4+ Styles]", 1)
            header_and_before = parts[0] + "[V4+ Styles]"
            rest = parts[1]

            # Find the end of styles (before [Events])
            if "[Events]" in rest:
                style_body, events_body = rest.split("[Events]", 1)
                new_style_body = style_body.rstrip() + "\n" + style_line + "\n\n"
                new_events_body = "[Events]" + events_body.rstrip() + "\n" + dialogue_line + "\n"
                new_content = header_and_before + new_style_body + new_events_body
            else:
                new_content = content + "\n" + style_line + "\n" + dialogue_line
        else:
            new_content = content + "\n" + style_line + "\n" + dialogue_line

        with open(ass_file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"Injected watermark '{self.text}' into {ass_file_path}")
        return True

    def create_watermark_image(
        self,
        output_png_path: str,
        width: int = 1080,
        height: int = 1920
    ) -> str:
        """
        Creates a full transparent 1080x1920 PNG overlay with the aesthetic watermark pill.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_png_path)), exist_ok=True)
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if not self.enabled or not self.text:
            img.save(output_png_path)
            return output_png_path

        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", self.font_size)
        bbox = draw.textbbox((0, 0), self.text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        cx, cy = self.get_coordinates(width, height)
        tx = cx - (tw // 2)
        ty = cy - (th // 2)

        # Draw semi-transparent rounded pill behind watermark
        pad_x, pad_y = 22, 10
        pill_box = [tx - pad_x, ty - pad_y, tx + tw + pad_x, ty + th + pad_y]
        alpha_val = int(self.opacity * 255)

        draw.rounded_rectangle(
            pill_box,
            radius=16,
            fill=(10, 10, 10, int(alpha_val * 0.75)),
            outline=(255, 255, 255, int(alpha_val * 0.25)),
            width=1
        )

        # Text with subtle drop shadow
        draw.text((tx + 1, ty + 1), self.text, font=font, fill=(0, 0, 0, int(alpha_val * 0.85)))
        draw.text((tx, ty), self.text, font=font, fill=(255, 255, 255, alpha_val))

        img.save(output_png_path)
        logger.info(f"Rendered watermark badge overlay to {output_png_path}")
        return output_png_path
