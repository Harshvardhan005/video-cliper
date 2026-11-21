"""
Video Editor & Rendering Engine
Composes smart reframing, animated subtitles burning, and audio mastering into high-fidelity 9:16 MP4s.
"""

import logging
import os
import shutil
import subprocess
from typing import Callable, Optional

from src.audio_processor import AudioProcessor
from src.media_inspector import MediaInspector
from src.smart_crop import SmartCropper
from src.watermark import WatermarkManager

logger = logging.getLogger(__name__)


class VideoEditor:
    """Orchestrates FFmpeg rendering pipeline with hardware acceleration and subtitle integration."""

    def __init__(
        self,
        smart_cropper: Optional[SmartCropper] = None,
        audio_processor: Optional[AudioProcessor] = None,
        ffmpeg_path: Optional[str] = None
    ):
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self.smart_cropper = smart_cropper or SmartCropper()
        self.audio_processor = audio_processor or AudioProcessor(ffmpeg_path=self.ffmpeg_path)
        self.inspector = MediaInspector()
        self.watermark_mgr = WatermarkManager()
        self.nvenc_available = self._test_nvenc()

    @staticmethod
    def _find_ffmpeg() -> str:
        local_bin = os.path.abspath("bin/ffmpeg.exe")
        if os.path.exists(local_bin):
            return local_bin
        return shutil.which("ffmpeg") or "ffmpeg"

    def _test_nvenc(self) -> bool:
        """Checks if NVENC hardware encoder is functional on this system."""
        try:
            cmd = [
                self.ffmpeg_path,
                "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                "-c:v", "h264_nvenc",
                "-f", "null", "-"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                logger.info("NVIDIA NVENC hardware encoding is available.")
                return True
        except Exception:
            pass
        return False

    def render_clip(
        self,
        source_video_path: str,
        start_time: float,
        end_time: float,
        output_clip_path: str,
        ass_caption_path: Optional[str] = None,
        layout_mode: str = "smart_auto",
        burn_captions: bool = True,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """
        Renders a polished 9:16 vertical video clip from source video.
        """
        os.makedirs(os.path.dirname(output_clip_path), exist_ok=True)
        duration = max(0.5, end_time - start_time)

        meta = self.inspector.inspect(source_video_path)

        if progress_callback:
            progress_callback("Calculating crop framing and video filters...", 0.2)

        # 1. Build video crop filter
        crop_filter = self.smart_cropper.build_crop_filter(
            video_path=source_video_path,
            start_time=start_time,
            end_time=end_time,
            source_width=meta.width,
            source_height=meta.height,
            layout_mode=layout_mode
        )

        # 2. Append ASS subtitle burning filter & watermark
        video_filters = [crop_filter]
        temp_wm_ass = None
        if burn_captions and ass_caption_path and os.path.isfile(ass_caption_path):
            self.watermark_mgr.inject_into_ass_file(ass_caption_path, clip_duration=duration)
            escaped_ass = os.path.abspath(ass_caption_path).replace("\\", "/").replace(":", "\\:")
            video_filters.append(f"ass='{escaped_ass}'")
        elif self.watermark_mgr.enabled and self.watermark_mgr.text:
            temp_wm_ass = os.path.join(os.path.dirname(output_clip_path), "temp_wm.ass")
            wm_style, wm_event = self.watermark_mgr.get_ass_style_and_event(clip_duration=duration)
            wm_content = f"""[Script Info]
Title: Watermark
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{wm_style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{wm_event}
"""
            with open(temp_wm_ass, "w", encoding="utf-8") as f:
                f.write(wm_content)
            escaped_wm = os.path.abspath(temp_wm_ass).replace("\\", "/").replace(":", "\\:")
            video_filters.append(f"ass='{escaped_wm}'")

        full_vf = ",".join(video_filters)

        # 3. Build audio filter
        af = self.audio_processor.build_audio_filter()

        # 4. Choose encoder
        vcodec = "h264_nvenc" if self.nvenc_available else "libx264"

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss", f"{start_time:.3f}",
            "-t", f"{duration:.3f}",
            "-i", source_video_path,
            "-vf", full_vf,
            "-af", af,
            "-c:v", vcodec,
            "-preset", "p4" if self.nvenc_available else "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-movflags", "+faststart",
            output_clip_path
        ]

        if progress_callback:
            progress_callback(f"Encoding 1080x1920 video with {vcodec}...", 0.5)

        logger.info(f"Running video render command: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0:
            logger.warning(f"Render failed with {vcodec}: {res.stderr}. Retrying with CPU libx264 fallback...")
            # Fallback to software libx264
            cmd[cmd.index(vcodec)] = "libx264"
            if "-preset" in cmd:
                cmd[cmd.index("-preset") + 1] = "fast"
            res_fb = subprocess.run(cmd, capture_output=True, text=True)
            if res_fb.returncode != 0:
                raise RuntimeError(f"FFmpeg render failure: {res_fb.stderr}")

        if temp_wm_ass and os.path.exists(temp_wm_ass):
            try:
                os.remove(temp_wm_ass)
            except Exception:
                pass

        if progress_callback:
            progress_callback("Video clip rendered successfully.", 1.0)

        return output_clip_path
