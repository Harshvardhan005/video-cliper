"""
Autonomous Continuous Livestream Clipper Daemon
Monitors an active YouTube livestream, extracts rolling footage buffers, detects peak surprise
and action moments via audio energy & speech analysis, and autonomously renders 9:16 vertical
viral shorts with Hinglish/meme styling and word-by-word karaoke captions.
"""

import json
import logging
import math
import os
import re
import struct
import subprocess
import sys
import time
import wave
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.abspath("."))
from src.media_inspector import MediaInspector
from src.quality_control import QualityControl
from src.transcription import Transcriber
from src.transliteration import to_hinglish, transliterate_word, is_devanagari
from src.watermark import WatermarkManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("LiveStreamMonitor")

FFMPEG = os.path.abspath("bin/ffmpeg.exe")
FFPROBE = os.path.abspath("bin/ffprobe.exe")
PYTHON_EXE = os.path.abspath("venv/Scripts/python.exe") if os.path.exists("venv/Scripts/python.exe") else sys.executable


def sec_to_ass(seconds: float) -> str:
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:01d}:{mins:02d}:{secs:02d}.{centis:02d}"


class LiveStreamClipperDaemon:
    def __init__(
        self,
        stream_url: str,
        output_dir: str = "final_clips",
        temp_dir: str = "temp_work",
        capture_duration_sec: int = 120,
        clip_target_duration_sec: int = 34
    ):
        self.stream_url = stream_url
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.capture_duration_sec = capture_duration_sec
        self.clip_target_duration_sec = clip_target_duration_sec
        self.processed_log_file = os.path.join(temp_dir, "processed_stream_intervals.json")

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        self.inspector = MediaInspector(FFPROBE)
        self.qc = QualityControl(inspector=self.inspector, ffmpeg_path=FFMPEG)
        self.transcriber = Transcriber(model_size="tiny", device="cpu", compute_type="int8")
        self.watermark_mgr = WatermarkManager()
        self.history = self._load_history()

    def _load_history(self) -> List[Dict]:
        if os.path.exists(self.processed_log_file):
            try:
                with open(self.processed_log_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self):
        with open(self.processed_log_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def get_hls_stream_urls(self) -> Tuple[Optional[str], Optional[str]]:
        """Retrieves direct video and audio HLS m3u8 URLs using yt-dlp."""
        cmd_v = [PYTHON_EXE, "-m", "yt_dlp", "-g", "-f", "311", self.stream_url]
        cmd_a = [PYTHON_EXE, "-m", "yt_dlp", "-g", "-f", "234", self.stream_url]

        logger.info("Querying live HLS stream URLs...")
        res_v = subprocess.run(cmd_v, capture_output=True, text=True)
        res_a = subprocess.run(cmd_a, capture_output=True, text=True)

        v_url = res_v.stdout.strip().split("\n")[-1] if res_v.returncode == 0 else None
        a_url = res_a.stdout.strip().split("\n")[-1] if res_a.returncode == 0 else None

        if v_url and a_url and v_url.startswith("http") and a_url.startswith("http"):
            return v_url, a_url
        logger.warning(f"Failed to extract stream URLs: {res_v.stderr}")
        return None, None

    def capture_rolling_buffer(self, v_url: str, a_url: str, target_file: str) -> bool:
        """Captures a rolling live segment via FFmpeg."""
        logger.info(f"Capturing {self.capture_duration_sec}s rolling livestream buffer...")
        cmd = [
            FFMPEG, "-y",
            "-i", v_url,
            "-i", a_url,
            "-t", str(self.capture_duration_sec),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            target_file
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0 and os.path.exists(target_file) and os.path.getsize(target_file) > 1000000

    def generate_screenshot_inspired_hook(self, clip_id: int, text_snippet: str) -> Tuple[str, List[str], str]:
        """
        Generates viral titles inspired directly by the user's uploaded screenshots:
        Style Types:
        1. 'tiktok_bubble' (Screenshots 3 & 6): White rounded card pill with dark text
        2. 'heavy_stroke'  (Screenshots 1, 5, 7): Heavy bold white text with thick black border
        3. 'condensed_pov' (Screenshot 4): Condensed white font 'Pov: ...' with black stroke
        4. 'minimal_white' (Screenshots 2 & 8): Clean modern white text, sentence or uppercase
        """
        used_titles = set()
        for item in self.history:
            if "title" in item:
                used_titles.add(item["title"].strip().lower())

        text_lower = text_snippet.lower()
        candidates = []

        # Content-specific hooks based on transcript
        if any(w in text_lower for w in ["car", "supercar", "drive", "speed", "fast", "bentley", "bike", "lamborghini", "ferrari"]):
            candidates.append((
                "heavy_stroke",
                ["BRO FOUND THE FASTEST CAR", "IN GTA 6 \U0001F480"],
                "BRO FOUND THE FASTEST CAR IN GTA 6 \U0001F480"
            ))
            candidates.append((
                "tiktok_bubble",
                ["Driving a 300 KM/H Supercar", "in GTA 6 \U0001F62D"],
                "Driving a 300 KM/H Supercar in GTA 6 \U0001F62D"
            ))
            candidates.append((
                "heavy_stroke",
                ["FIRST SUPERCAR I FOUND", "IN GTA 6"],
                "FIRST SUPERCAR I FOUND IN GTA 6"
            ))
            candidates.append((
                "condensed_pov",
                ["Pov: Driving At 300 KM/H In GTA 6."],
                "Pov: Driving At 300 KM/H In GTA 6."
            ))

        if any(w in text_lower for w in ["map", "explore", "secret", "island", "city", "place", "location"]):
            candidates.append((
                "tiktok_bubble",
                ["Exploring the secret map location", "in GTA 6 \U0001F62D"],
                "Exploring the secret map location in GTA 6 \U0001F62D"
            ))
            candidates.append((
                "heavy_stroke",
                ["HIDDEN MAP LOCATION", "FOUND IN GTA 6 \U0001F480"],
                "HIDDEN MAP LOCATION FOUND IN GTA 6 \U0001F480"
            ))

        if any(w in text_lower for w in ["npc", "people", "guy", "police", "cop"]):
            candidates.append((
                "tiktok_bubble",
                ["The NPCs are crazy", "in GTA 6 \U0001F62D"],
                "The NPCs are crazy in GTA 6 \U0001F62D"
            ))
            candidates.append((
                "tiktok_bubble",
                ["NPC was NOT giving up that", "Bentley in GTA 6 \U0001F62D"],
                "NPC was NOT giving up that Bentley in GTA 6 \U0001F62D"
            ))

        if any(w in text_lower for w in ["water", "crash", "stunt", "jump", "fall", "fly"]):
            candidates.append((
                "heavy_stroke",
                ["BRO ACCIDENTALLY JUMPED", "INTO THE WATER \U0001F480"],
                "BRO ACCIDENTALLY JUMPED INTO THE WATER \U0001F480"
            ))

        # Diverse general presets from user's screenshots
        general_presets = [
            (
                "tiktok_bubble",
                ["The NPCs are crazy", "in GTA 6 \U0001F62D"],
                "The NPCs are crazy in GTA 6 \U0001F62D"
            ),
            (
                "heavy_stroke",
                ["BRO USED A CHAMELEON", "AS A WEAPON \U0001F480"],
                "BRO USED A CHAMELEON AS A WEAPON \U0001F480"
            ),
            (
                "condensed_pov",
                ["Pov: Bro After 22 Hours Non-Stop."],
                "Pov: Bro After 22 Hours Non-Stop."
            ),
            (
                "minimal_white",
                ["13 years Feel worth it"],
                "13 years Feel worth it"
            ),
            (
                "heavy_stroke",
                ["First Bike I found", "In GTA 6"],
                "First Bike I found In GTA 6"
            ),
            (
                "tiktok_bubble",
                ["NPC was NOT giving up that", "Bentley in GTA 6 \U0001F62D"],
                "NPC was NOT giving up that Bentley in GTA 6 \U0001F62D"
            ),
            (
                "minimal_white",
                ["GTA VI LUCIA'S BABY \U0001F633\U0001F62D"],
                "GTA VI LUCIA'S BABY \U0001F633\U0001F62D"
            ),
            (
                "condensed_pov",
                ["Pov: Speed In The Final Mission."],
                "Pov: Speed In The Final Mission."
            ),
            (
                "heavy_stroke",
                ["LUCIA'S MOM GOT BIT", "BY AN ALLIGATOR"],
                "LUCIA'S MOM GOT BIT BY AN ALLIGATOR"
            )
        ]

        candidates.extend(general_presets)

        for style_type, lines, title_str in candidates:
            if title_str.strip().lower() not in used_titles:
                return style_type, lines, title_str

        # Fallback with clip ID
        suffix = f"part {clip_id}"
        return "tiktok_bubble", [f"Speed in GTA 6 {suffix}", "watch till the end \U0001F62D"], f"Speed in GTA 6 {suffix} watch till the end \U0001F62D"

    def detect_top_action_windows(self, video_path: str, max_windows: int = 2) -> List[Tuple[float, float, float]]:
        """Detects top non-overlapping action/surprise windows based on audio RMS energy."""
        wav_path = os.path.join(self.temp_dir, "temp_live_audio.wav")
        subprocess.run([
            FFMPEG, "-y",
            "-i", video_path,
            "-vn", "-ar", "16000", "-ac", "1",
            wav_path
        ], capture_output=True)

        if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
            return [(0.0, float(self.clip_target_duration_sec), 0.0)]

        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            sample_rate = wf.getframerate()
            duration = n_frames / sample_rate
            raw_data = wf.readframes(n_frames)

        chunk_size = int(sample_rate * 0.5)
        samples = struct.unpack(f"<{n_frames}h", raw_data)

        rms_scores = []
        for i in range(0, n_frames, chunk_size):
            chunk = samples[i : i + chunk_size]
            if not chunk:
                continue
            rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
            sec = i / sample_rate
            rms_scores.append((sec, rms))

        if not rms_scores:
            return [(0.0, min(self.clip_target_duration_sec, duration), 0.0)]

        window_chunks = int(self.clip_target_duration_sec / 0.5)
        all_candidates = []

        for i in range(len(rms_scores) - window_chunks + 1):
            win_sum = sum(rms_scores[j][1] for j in range(i, i + window_chunks))
            start_sec = rms_scores[i][0]
            end_sec = min(duration, start_sec + self.clip_target_duration_sec)
            peak_sec = max(rms_scores[i : i + window_chunks], key=lambda x: x[1])[0]
            all_candidates.append((win_sum, start_sec, end_sec, peak_sec))

        # Sort by energy descending
        all_candidates.sort(key=lambda x: x[0], reverse=True)

        selected_windows = []
        for cand in all_candidates:
            c_start = cand[1]
            c_end = cand[2]
            c_peak = cand[3]

            # Ensure at least 15s separation from previously selected windows
            overlap = any(abs(c_start - sw[0]) < 20.0 for sw in selected_windows)
            if not overlap:
                selected_windows.append((c_start, c_end, c_peak))
                if len(selected_windows) >= max_windows:
                    break

        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass

        return selected_windows

    def render_screenshot_style_banner(
        self,
        style_type: str,
        lines: List[str],
        output_png_path: str,
        width: int = 1080,
        height: int = 360
    ) -> str:
        """
        Renders titles exactly matching the user's reference screenshots:
        1. 'tiktok_bubble': White rounded rectangle card with dark text (Screenshots 3 & 6)
        2. 'heavy_stroke': Heavy white bold font with 6px thick solid black outline (Screenshots 1, 5, 7)
        3. 'condensed_pov': Condensed white font with thin black stroke (Screenshot 4)
        4. 'minimal_white': Crisp white modern bold font (Screenshots 2 & 8)
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if style_type == "tiktok_bubble":
            # Screenshots 3 & 6: Clean white rounded sticker card with dark text
            font_size = 46
            font_text = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)

            line_spacing = 58
            total_text_h = len(lines) * line_spacing

            # Measure max line width
            max_line_w = 0
            for l in lines:
                bbox = draw.textbbox((0, 0), l, font=font_text)
                lw = bbox[2] - bbox[0]
                if lw > max_line_w:
                    max_line_w = lw

            pad_x = 42
            pad_y = 28
            pill_w = max_line_w + (pad_x * 2)
            pill_h = total_text_h + (pad_y * 2) - 10

            pill_x = (width - pill_w) // 2
            pill_y = (height - pill_h) // 2

            # Render rounded pill background
            draw.rounded_rectangle(
                [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                radius=24,
                fill=(255, 255, 255, 250),
                outline=(0, 0, 0, 35),
                width=2
            )

            # Render text inside pill
            for idx, l in enumerate(lines):
                bbox = draw.textbbox((0, 0), l, font=font_text)
                lw = bbox[2] - bbox[0]
                tx = (width - lw) // 2
                ty = pill_y + pad_y + (idx * line_spacing)
                draw.text((tx, ty), l, font=font_text, fill=(12, 12, 12, 255), embedded_color=True)

        elif style_type == "heavy_stroke":
            # Screenshots 1, 5, 7: Heavy white text with thick 6px black outline
            font_size = 62
            font_heavy = ImageFont.truetype("C:/Windows/Fonts/seguibl.ttf", font_size)

            line_spacing = 76
            total_text_h = len(lines) * line_spacing
            start_y = (height - total_text_h) // 2

            stroke_w = 6
            for idx, l in enumerate(lines):
                bbox = draw.textbbox((0, 0), l, font=font_heavy)
                lw = bbox[2] - bbox[0]
                tx = (width - lw) // 2
                ty = start_y + (idx * line_spacing)

                # Draw outer black stroke
                for dx in range(-stroke_w, stroke_w + 1):
                    for dy in range(-stroke_w, stroke_w + 1):
                        if dx * dx + dy * dy <= stroke_w * stroke_w:
                            draw.text((tx + dx, ty + dy), l, font=font_heavy, fill=(0, 0, 0, 255))

                # Draw crisp white fill
                draw.text((tx, ty), l, font=font_heavy, fill=(255, 255, 255, 255), embedded_color=True)

        elif style_type == "condensed_pov":
            # Screenshot 4: Condensed white font with black outline
            font_size = 56
            font_cond = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", font_size)

            line_spacing = 68
            total_text_h = len(lines) * line_spacing
            start_y = (height - total_text_h) // 2

            stroke_w = 4
            for idx, l in enumerate(lines):
                bbox = draw.textbbox((0, 0), l, font=font_cond)
                lw = bbox[2] - bbox[0]
                tx = (width - lw) // 2
                ty = start_y + (idx * line_spacing)

                for dx in range(-stroke_w, stroke_w + 1):
                    for dy in range(-stroke_w, stroke_w + 1):
                        if dx * dx + dy * dy <= stroke_w * stroke_w:
                            draw.text((tx + dx, ty + dy), l, font=font_cond, fill=(0, 0, 0, 255))

                draw.text((tx, ty), l, font=font_cond, fill=(255, 255, 255, 255), embedded_color=True)

        else:
            # Screenshots 2 & 8: Minimalist white bold text with clean shadow
            font_size = 54
            font_clean = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)

            line_spacing = 66
            total_text_h = len(lines) * line_spacing
            start_y = (height - total_text_h) // 2

            for idx, l in enumerate(lines):
                bbox = draw.textbbox((0, 0), l, font=font_clean)
                lw = bbox[2] - bbox[0]
                tx = (width - lw) // 2
                ty = start_y + (idx * line_spacing)

                for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                    draw.text((tx + dx, ty + dy), l, font=font_clean, fill=(0, 0, 0, 220))
                draw.text((tx, ty), l, font=font_clean, fill=(255, 255, 255, 255), embedded_color=True)

        img.save(output_png_path)
        return output_png_path
        return output_png_path

    def generate_dialogue_ass(self, words: List[Dict], ass_path: str) -> str:
        """Generates synchronized ASS subtitles with yellow active-word highlights."""
        header = """[Script Info]
Title: Live Stream Dialogue Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,54,&H00FFFFFF,&H000000FF,&H00050505,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,60,60,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        clean_words = []
        for w in words:
            clean_text = w["word"].strip()
            if re.search(r"\(.*music.*\)|\(gunshot\)|\[MUSIC|PLAYING\]", clean_text, re.I):
                continue
            if is_devanagari(clean_text):
                clean_text = transliterate_word(clean_text)
            clean_words.append({
                "word": clean_text,
                "start": w["start"],
                "end": w["end"]
            })

        words_per_group = 3
        for i in range(0, len(clean_words), words_per_group):
            chunk = clean_words[i : i + words_per_group]
            if not chunk:
                continue

            for active_idx, active_word in enumerate(chunk):
                w_start = active_word["start"]
                w_end = active_word["end"]

                line_parts = []
                for idx, cw in enumerate(chunk):
                    word_str = cw["word"]
                    if idx == active_idx:
                        line_parts.append(f"{{\\c&H0000FFFF&\\fscx108\\fscy108}}{word_str}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}")
                    else:
                        line_parts.append(word_str)

                dialogue_text = " ".join(line_parts)
                events.append(f"Dialogue: 0,{sec_to_ass(w_start)},{sec_to_ass(w_end)},Default,,0,0,0,,{dialogue_text}")

        # Inject creator watermark
        wm_style, wm_event = self.watermark_mgr.get_ass_style_and_event(clip_duration=3600.0)
        if wm_style:
            header = header.replace("[Events]", f"{wm_style}\n\n[Events]")
            events.insert(0, wm_event)

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events) + "\n")
        return ass_path

    def render_vertical_clip(
        self,
        raw_video: str,
        offset_start: float,
        duration: float,
        banner_png: str,
        ass_path: str,
        output_mp4: str
    ) -> bool:
        """Renders 1080x1920 60fps vertical short with NVENC hardware encoding."""
        escaped_ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        filter_complex = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,eq=brightness=-0.15[blurred];"
            f"[fg]scale=1080:608:flags=lanczos[sharp_fg];"
            f"[blurred][sharp_fg]overlay=0:656[with_fg];"
            f"[with_fg][1:v]overlay=0:150,fps=60,ass='{escaped_ass}'"
        )
        af = "loudnorm=I=-14:LRA=7:tp=-1.5,alimiter=limit=-1.0dB:attack=5:release=50"

        cmd = [
            FFMPEG, "-y",
            "-ss", str(offset_start),
            "-t", str(duration),
            "-i", raw_video,
            "-i", banner_png,
            "-filter_complex", filter_complex,
            "-af", af,
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-pix_fmt", "yuv420p",
            "-r", "60",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-movflags", "+faststart",
            output_mp4
        ]

        logger.info(f"Rendering {output_mp4} with h264_nvenc 60FPS...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning("NVENC failed, attempting libx264 software fallback...")
            cmd[cmd.index("h264_nvenc")] = "libx264"
            cmd[cmd.index("-preset") + 1] = "fast"
            res_fb = subprocess.run(cmd, capture_output=True, text=True)
            if res_fb.returncode != 0:
                logger.error(f"Render failed: {res_fb.stderr}")
                return False
        return True

    def process_one_cycle(self) -> List[str]:
        """Runs a full detection and clipping cycle, generating distinct clips with unique English titles."""
        v_url, a_url = self.get_hls_stream_urls()
        if not v_url or not a_url:
            logger.warning("Could not reach livestream HLS feed. Retrying next cycle...")
            return []

        raw_buffer = os.path.join(self.temp_dir, "current_live_buffer.mp4")
        if not self.capture_rolling_buffer(v_url, a_url, raw_buffer):
            logger.warning("Failed to capture rolling buffer.")
            return []

        action_windows = self.detect_top_action_windows(raw_buffer, max_windows=2)
        generated_clips = []

        for window_idx, (start_sec, end_sec, peak_sec) in enumerate(action_windows):
            duration = end_sec - start_sec
            logger.info(f"Processing Action Window {window_idx+1}: {start_sec:.1f}s - {end_sec:.1f}s (peak at {peak_sec:.1f}s)")

            # Extract audio for speech recognition
            clip_audio_wav = os.path.join(self.temp_dir, f"current_action_audio_{window_idx}.wav")
            subprocess.run([
                FFMPEG, "-y",
                "-ss", str(start_sec),
                "-t", str(duration),
                "-i", raw_buffer,
                "-ar", "16000", "-ac", "1",
                clip_audio_wav
            ], capture_output=True)

            # Transcribe (auto-detect language for Hindi/Hinglish and English commentary)
            t_res = self.transcriber.transcribe(clip_audio_wav, language=None)
            words = [{"word": w.word, "start": w.start, "end": w.end} for seg in t_res.segments for w in (seg.words or [])]
            logger.info(f"Transcribed {len(words)} words: '{t_res.full_text[:80]}...'")

            # Generate unique clip filename
            clip_id = len(self.history) + 1
            timestamp_str = datetime.now().strftime("%H%M%S")
            clip_filename = f"viral_clip_{clip_id}_{timestamp_str}.mp4"
            output_mp4 = os.path.join(self.output_dir, clip_filename)

            # Generate 100% English unique viral hook banner matching user reference screenshots
            style_type, lines, title_text = self.generate_screenshot_inspired_hook(clip_id, t_res.full_text)
            banner_png = os.path.join(self.temp_dir, f"hook_{clip_id}.png")
            self.render_screenshot_style_banner(style_type, lines, banner_png)

            # Generate ASS dialogue captions (Hinglish/English speech with yellow active highlights)
            ass_path = os.path.join(self.temp_dir, f"captions_{clip_id}.ass")
            self.generate_dialogue_ass(words, ass_path)

            # Render Vertical Clip
            success = self.render_vertical_clip(raw_buffer, start_sec, duration, banner_png, ass_path, output_mp4)
            if not success:
                logger.error(f"Failed to render clip {clip_filename}.")
                continue

            # Verify QC
            qc_report = self.qc.verify_clip(output_mp4, expected_width=1080, expected_height=1920, min_duration=15.0, max_duration=60.0)
            logger.info(f"Clip {clip_filename} QC: Valid={qc_report.is_valid}, Size={qc_report.file_size_mb}MB, Errors={qc_report.errors}")

            record = {
                "clip_id": clip_id,
                "filename": clip_filename,
                "title": title_text,
                "created_at": datetime.now().isoformat(),
                "duration": qc_report.duration_actual,
                "file_size_mb": qc_report.file_size_mb,
                "transcription_snippet": t_res.full_text[:120],
                "stream_url": self.stream_url,
                "qc_valid": qc_report.is_valid
            }
            self.history.append(record)
            self._save_history()

            manifest_file = os.path.join(self.output_dir, "live_stream_clips_manifest.json")
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)

            generated_clips.append(output_mp4)
            logger.info(f"SUCCESS: Rendered deliverable -> {output_mp4}")

            # Clean temporary files for this window
            for f in [clip_audio_wav, banner_png, ass_path]:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except Exception:
                    pass

        try:
            if os.path.exists(raw_buffer):
                os.remove(raw_buffer)
        except Exception:
            pass

        return generated_clips


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Live Stream Clipper")
    parser.add_argument("--url", default="https://www.youtube.com/live/jSZK6H7AgBI", help="Live stream URL to monitor and clip")
    parser.add_argument("--max-cycles", type=int, default=1, help="Number of clipping cycles to run")
    args = parser.parse_args()

    clipper = LiveStreamClipperDaemon(stream_url=args.url)

    logger.info(f"Executing continuous live stream clipper on: {args.url}")
    new_clips = clipper.process_one_cycle()
    logger.info(f"Cycle completed. Generated {len(new_clips)} new clips: {new_clips}")


if __name__ == "__main__":
    main()

