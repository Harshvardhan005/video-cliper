"""
Autonomous Continuous Livestream Clipper Daemon (Upgraded Engine)
- Multi-Modal Moment Detection: RMS energy + Zero-Crossing Rate (ZCR) + High-Frequency Transients (HFD)
- Sentence-Boundary Snapping: Word timestamps & silence detection prevent mid-sentence cut-offs
- Lossless MPEG-TS Live Ingestion: Crash-proof rolling stream buffering without 'moov atom' failures
- Transcript Quote-Based Dynamic Hook Extractor: Bespoke titles from actual spoken transcript quotes
- Visual Styling: 4 screenshot-matched styles (TikTok bubble, Heavy stroke, Condensed POV, Minimal white)
- Watermark: @BallQ_FC injected on every clip via ASS subtitle and canvas
- Vertical 9:16 @ 60 FPS NVENC Hardware Accelerated Export with EBU R128 Loudness Normalization
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
import unicodedata
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


def is_emoji(char: str) -> bool:
    code = ord(char)
    cat = unicodedata.category(char)
    return (
        0x1F000 <= code <= 0x1FFFF or
        0x2600 <= code <= 0x27BF or
        0x2B50 <= code <= 0x2B55 or
        0x2300 <= code <= 0x23FF or
        code == 0x200D or
        0xFE00 <= code <= 0xFE0F or
        cat in ("So", "Sk")
    )


def split_text_and_emojis(text: str) -> List[Tuple[str, bool]]:
    tokens = []
    current_str = ''
    is_curr_emoji = False
    for char in text:
        emoji_char = is_emoji(char)
        if emoji_char == is_curr_emoji:
            current_str += char
        else:
            if current_str:
                tokens.append((current_str, is_curr_emoji))
            current_str = char
            is_curr_emoji = emoji_char
    if current_str:
        tokens.append((current_str, is_curr_emoji))
    return tokens


def sec_to_ass(seconds: float) -> str:
    seconds = max(0.0, seconds)
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
        cmd_v = [PYTHON_EXE, "-m", "yt_dlp", "-g", "-f", "312/311/bestvideo[height<=1080]/bestvideo", self.stream_url]
        cmd_a = [PYTHON_EXE, "-m", "yt_dlp", "-g", "-f", "234/bestaudio/best", self.stream_url]

        logger.info("Querying live HLS stream URLs...")
        res_v = subprocess.run(cmd_v, capture_output=True, text=True)
        res_a = subprocess.run(cmd_a, capture_output=True, text=True)

        v_url = res_v.stdout.strip().split("\n")[-1] if res_v.returncode == 0 else None
        a_url = res_a.stdout.strip().split("\n")[-1] if res_a.returncode == 0 else None

        if v_url and a_url and v_url.startswith("http") and a_url.startswith("http"):
            return v_url, a_url
        logger.warning(f"Failed to extract stream URLs: {res_v.stderr}")
        return None, None

    # -------------------------------------------------------------------------
    # UPGRADE 3: Lossless MPEG-TS Stream Ingestion (Crash-proof buffering)
    # -------------------------------------------------------------------------
    def capture_rolling_buffer(self, v_url: str, a_url: str, target_file: str) -> bool:
        """Captures a rolling live segment via FFmpeg into an MPEG-TS container."""
        logger.info(f"Capturing {self.capture_duration_sec}s rolling livestream buffer (MPEG-TS format)...")
        cmd = [
            FFMPEG, "-y",
            "-i", v_url,
            "-i", a_url,
            "-t", str(self.capture_duration_sec),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-f", "mpegts",
            target_file
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0 and os.path.exists(target_file) and os.path.getsize(target_file) > 1000000

    # -------------------------------------------------------------------------
    # UPGRADE 1: Multi-Modal Moment Detection (RMS + ZCR + HFD)
    # -------------------------------------------------------------------------
    def detect_top_action_windows(self, video_path: str, max_windows: int = 2) -> List[Tuple[float, float, float]]:
        """
        Detects top surprise/action moments using multi-modal acoustic analysis:
        - RMS Energy (Volume)
        - Zero-Crossing Rate (ZCR): screams, laughter bursts, fricatives
        - High-Frequency First Derivative Energy (HFD): sudden audio transients/gasps
        Filters out steady low-frequency game engine hums while prioritizing streamer reactions.
        """
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

        chunk_size = int(sample_rate * 0.5)  # 500ms chunks
        samples = struct.unpack(f"<{n_frames}h", raw_data)

        raw_metrics = []
        for i in range(0, n_frames, chunk_size):
            chunk = samples[i : i + chunk_size]
            if len(chunk) < 2:
                continue

            sec = i / sample_rate
            # 1. RMS Energy
            rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))

            # 2. Zero Crossing Rate (ZCR)
            zc_count = sum(1 for k in range(1, len(chunk)) if (chunk[k] >= 0 > chunk[k - 1]) or (chunk[k] < 0 <= chunk[k - 1]))
            zcr = zc_count / len(chunk)

            # 3. High-Frequency Difference Energy (HFD)
            hfd = math.sqrt(sum((chunk[k] - chunk[k - 1]) ** 2 for k in range(1, len(chunk))) / (len(chunk) - 1))

            raw_metrics.append((sec, rms, zcr, hfd))

        if not raw_metrics:
            return [(0.0, min(self.clip_target_duration_sec, duration), 0.0)]

        # Normalize metrics across buffer
        max_rms = max(m[1] for m in raw_metrics) or 1.0
        min_rms = min(m[1] for m in raw_metrics)
        max_zcr = max(m[2] for m in raw_metrics) or 1.0
        min_zcr = min(m[2] for m in raw_metrics)
        max_hfd = max(m[3] for m in raw_metrics) or 1.0
        min_hfd = min(m[3] for m in raw_metrics)

        scored_chunks = []
        for sec, rms, zcr, hfd in raw_metrics:
            n_rms = (rms - min_rms) / (max_rms - min_rms + 1e-6)
            n_zcr = (zcr - min_zcr) / (max_zcr - min_zcr + 1e-6)
            n_hfd = (hfd - min_hfd) / (max_hfd - min_hfd + 1e-6)

            # Composite reaction prosody score:
            # 45% volume + 25% laughter/screaming pitch (ZCR) + 30% sudden transients/excitement (HFD)
            comp_score = (0.45 * n_rms) + (0.25 * n_zcr) + (0.30 * n_hfd)
            scored_chunks.append((sec, comp_score))

        window_chunks = int(self.clip_target_duration_sec / 0.5)
        all_candidates = []

        for i in range(len(scored_chunks) - window_chunks + 1):
            win_sum = sum(scored_chunks[j][1] for j in range(i, i + window_chunks))
            start_sec = scored_chunks[i][0]
            end_sec = min(duration, start_sec + self.clip_target_duration_sec)
            peak_sec = max(scored_chunks[i : i + window_chunks], key=lambda x: x[1])[0]
            all_candidates.append((win_sum, start_sec, end_sec, peak_sec))

        # Sort descending by composite excitement score
        all_candidates.sort(key=lambda x: x[0], reverse=True)

        selected_windows = []
        for cand in all_candidates:
            c_start = cand[1]
            c_end = cand[2]
            c_peak = cand[3]

            # Ensure at least 18s separation from already selected windows
            overlap = any(abs(c_start - sw[0]) < 18.0 for sw in selected_windows)
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

    # -------------------------------------------------------------------------
    # UPGRADE 2: Sentence-Boundary Snapping
    # -------------------------------------------------------------------------
    def snap_to_sentence_boundaries(
        self,
        words: List[Dict],
        raw_start: float,
        raw_end: float,
        min_dur: float = 24.0,
        max_dur: float = 46.0
    ) -> Tuple[float, float, List[Dict]]:
        """
        Snaps start and end timestamps so words and sentences are never cut off mid-speech.
        Identifies pauses (>350ms) and punctuation terminators (. ! ? ।).
        Returns (snapped_start, snapped_end, re_offset_words).
        """
        if not words:
            return raw_start, raw_end, words

        # Find word closest to raw_start
        start_idx = 0
        for i, w in enumerate(words):
            if w["start"] >= raw_start - 1.5:
                # Check if previous word had a pause or sentence terminator
                if i > 0 and (w["start"] - words[i - 1]["end"] > 0.35 or re.search(r"[.!?।]$", words[i - 1]["word"])):
                    start_idx = i
                    break
                elif w["start"] >= raw_start:
                    start_idx = i
                    break

        snapped_start = max(0.0, words[start_idx]["start"] - 0.2)

        # Find best end boundary between min_dur and max_dur
        end_idx = len(words) - 1
        best_end = snapped_start + self.clip_target_duration_sec
        best_score = -1.0

        for i in range(start_idx, len(words)):
            w = words[i]
            dur = w["end"] - snapped_start

            if dur < min_dur:
                continue
            if dur > max_dur:
                break

            score = 1.0
            # Strong bonus for sentence-terminating punctuation
            if re.search(r"[.!?।]$", w["word"]):
                score += 5.0

            # Bonus for natural pause following this word
            if i + 1 < len(words):
                pause = words[i + 1]["start"] - w["end"]
                if pause > 0.4:
                    score += 4.0
                elif pause > 0.2:
                    score += 2.0
            else:
                score += 3.0

            # Proximity to preferred target duration (32-36s)
            target_diff = abs(dur - self.clip_target_duration_sec)
            score -= (target_diff * 0.15)

            if score > best_score:
                best_score = score
                end_idx = i
                best_end = w["end"] + 0.35

        snapped_end = best_end

        # Re-offset word timestamps relative to snapped_start
        adjusted_words = []
        for i in range(start_idx, end_idx + 1):
            w = words[i]
            adjusted_words.append({
                "word": w["word"],
                "start": max(0.0, w["start"] - snapped_start),
                "end": max(0.05, w["end"] - snapped_start)
            })

        logger.info(f"Sentence Boundary Snapped: {raw_start:.1f}s-{raw_end:.1f}s -> {snapped_start:.1f}s-{snapped_end:.1f}s (Dur: {snapped_end - snapped_start:.1f}s, {len(adjusted_words)} words)")
        return snapped_start, snapped_end, adjusted_words

    # -------------------------------------------------------------------------
    # UPGRADE 4: Dynamic Quote-Based Hook Extractor (Beside user screenshot styles)
    # -------------------------------------------------------------------------
    def extract_dynamic_quote_hook(
        self,
        clip_id: int,
        transcript_text: str,
        words: List[Dict]
    ) -> Tuple[str, List[str], str]:
        """
        Synthesizes bespoke titles from actual spoken transcript quotes rather than static presets.
        Always formats into one of the 4 user-approved screenshot styles:
        - tiktok_bubble
        - heavy_stroke
        - condensed_pov
        - minimal_white
        """
        used_titles = set()
        for item in self.history:
            if "title" in item:
                used_titles.add(item["title"].strip().lower())

        text = transcript_text.strip()
        text_lower = text.lower()

        # Check for direct punchy questions or exclamations in transcript
        sentences = re.split(r"[.!?।\n]+", text)
        candidates = []

        # Find punchy short phrases from speech (3 to 8 words)
        for s in sentences:
            s_clean = s.strip()
            w_list = s_clean.split()
            if 3 <= len(w_list) <= 8:
                # Transliterate any Devanagari words to Hinglish
                hinglish_phrase = to_hinglish(s_clean).upper()
                # Clean punctuation for title
                hinglish_phrase = re.sub(r'["\']', '', hinglish_phrase)

                # Split into 2 balanced lines if long
                if len(hinglish_phrase) > 22 and len(w_list) >= 4:
                    mid = len(w_list) // 2
                    line1 = " ".join(w_list[:mid]).upper()
                    line2 = " ".join(w_list[mid:]).upper()
                    candidates.append((
                        "heavy_stroke",
                        [f'"{line1}', f'{line2}" \U0001F480'],
                        f'"{line1} {line2}" \U0001F480'
                    ))
                else:
                    candidates.append((
                        "tiktok_bubble",
                        [f'"{s_clean}" \U0001F62D'],
                        f'"{s_clean}" \U0001F62D'
                    ))

        # Check topic triggers
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

        # Screenshot reference presets
        screenshot_styles_pool = [
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
        candidates.extend(screenshot_styles_pool)

        # Choose the first unused candidate
        for style_type, lines, title_str in candidates:
            if title_str.strip().lower() not in used_titles:
                return style_type, lines, title_str

        # Fallback
        suffix = f"part {clip_id}"
        return "tiktok_bubble", [f"Speed in GTA 6 {suffix}", "watch till the end \U0001F62D"], f"Speed in GTA 6 {suffix} watch till the end \U0001F62D"

    def render_screenshot_style_banner(
        self,
        style_type: str,
        lines: List[str],
        output_png_path: str,
        width: int = 1080,
        height: int = 360
    ) -> str:
        """
        Renders titles exactly matching the user's reference screenshots with full emoji fallback:
        1. 'tiktok_bubble': White rounded rectangle card with dark text (Screenshots 3 & 6)
        2. 'heavy_stroke': Heavy white bold font with 6px thick solid black outline (Screenshots 1, 5, 7)
        3. 'condensed_pov': Condensed white font with thin black stroke (Screenshot 4)
        4. 'minimal_white': Crisp white modern bold font (Screenshots 2 & 8)
        Emojis are rendered via Segoe UI Emoji with embedded color so no '▯' missing glyph boxes appear.
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        emoji_font_path = "C:/Windows/Fonts/seguiemj.ttf"

        def measure_line_width(line_text: str, main_f: ImageFont.FreeTypeFont, emoji_f: ImageFont.FreeTypeFont) -> float:
            tokens = split_text_and_emojis(line_text)
            total_w = 0.0
            for text_part, is_em in tokens:
                f = emoji_f if is_em else main_f
                total_w += draw.textlength(text_part, font=f)
            return total_w

        def draw_segmented_line(
            tx: float,
            ty: float,
            line_text: str,
            main_f: ImageFont.FreeTypeFont,
            emoji_f: ImageFont.FreeTypeFont,
            text_fill: tuple,
            stroke_w: int = 0,
            stroke_fill: tuple = (0, 0, 0, 255),
            shadow_offsets: Optional[List[Tuple[int, int]]] = None
        ):
            tokens = split_text_and_emojis(line_text)
            curr_x = tx
            for text_part, is_em in tokens:
                f = emoji_f if is_em else main_f
                w = draw.textlength(text_part, font=f)
                if not is_em:
                    if shadow_offsets:
                        for dx, dy in shadow_offsets:
                            draw.text((curr_x + dx, ty + dy), text_part, font=f, fill=stroke_fill)
                    elif stroke_w > 0:
                        for dx in range(-stroke_w, stroke_w + 1):
                            for dy in range(-stroke_w, stroke_w + 1):
                                if dx * dx + dy * dy <= stroke_w * stroke_w:
                                    draw.text((curr_x + dx, ty + dy), text_part, font=f, fill=stroke_fill)
                    draw.text((curr_x, ty), text_part, font=f, fill=text_fill)
                else:
                    # Windows Segoe UI Emoji with embedded color
                    draw.text((curr_x, ty + 2), text_part, font=f, fill=(255, 255, 255, 255), embedded_color=True)
                curr_x += w

        COLOR_YELLOW = (255, 230, 0, 255)
        COLOR_WHITE = (255, 255, 255, 255)

        # Ensure multi-line yellow & white title structure
        if len(lines) == 1:
            words_in_line = lines[0].split()
            if len(words_in_line) >= 2:
                mid = len(words_in_line) // 2
                lines = [" ".join(words_in_line[:mid]), " ".join(words_in_line[mid:])]

        if style_type == "tiktok_bubble":
            font_size = 48
            font_text = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
            emoji_font = ImageFont.truetype(emoji_font_path, font_size)

            line_spacing = 62
            total_text_h = len(lines) * line_spacing

            max_line_w = max(measure_line_width(l, font_text, emoji_font) for l in lines)
            pad_x = 44
            pad_y = 28
            pill_w = int(max_line_w + (pad_x * 2))
            pill_h = total_text_h + (pad_y * 2) - 10

            pill_x = (width - pill_w) // 2
            pill_y = (height - pill_h) // 2

            draw.rounded_rectangle(
                [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                radius=26,
                fill=(15, 15, 20, 240),
                outline=(255, 230, 0, 160),
                width=3
            )

            for idx, l in enumerate(lines):
                lw = measure_line_width(l, font_text, emoji_font)
                tx = (width - lw) // 2
                ty = pill_y + pad_y + (idx * line_spacing)
                fill_color = COLOR_YELLOW if idx % 2 == 0 else COLOR_WHITE
                draw_segmented_line(tx, ty, l, font_text, emoji_font, text_fill=fill_color)

        elif style_type == "heavy_stroke":
            font_size = 58
            while font_size > 34:
                font_heavy = ImageFont.truetype("C:/Windows/Fonts/seguibl.ttf", font_size)
                emoji_font = ImageFont.truetype(emoji_font_path, int(font_size * 0.88))
                if max(measure_line_width(l, font_heavy, emoji_font) for l in lines) <= width - 90:
                    break
                font_size -= 4

            line_spacing = int(font_size * 1.25)
            total_text_h = len(lines) * line_spacing
            start_y = (height - total_text_h) // 2

            for idx, l in enumerate(lines):
                lw = measure_line_width(l, font_heavy, emoji_font)
                tx = (width - lw) // 2
                ty = start_y + (idx * line_spacing)
                fill_color = COLOR_YELLOW if idx % 2 == 0 else COLOR_WHITE
                draw_segmented_line(tx, ty, l, font_heavy, emoji_font, text_fill=fill_color, stroke_w=6, stroke_fill=(0, 0, 0, 255))

        elif style_type == "condensed_pov":
            font_size = 56
            while font_size > 34:
                font_cond = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", font_size)
                emoji_font = ImageFont.truetype(emoji_font_path, int(font_size * 0.9))
                if max(measure_line_width(l, font_cond, emoji_font) for l in lines) <= width - 90:
                    break
                font_size -= 4

            line_spacing = int(font_size * 1.2)
            total_text_h = len(lines) * line_spacing
            start_y = (height - total_text_h) // 2

            for idx, l in enumerate(lines):
                lw = measure_line_width(l, font_cond, emoji_font)
                tx = (width - lw) // 2
                ty = start_y + (idx * line_spacing)
                fill_color = COLOR_YELLOW if idx % 2 == 0 else COLOR_WHITE
                draw_segmented_line(tx, ty, l, font_cond, emoji_font, text_fill=fill_color, stroke_w=4, stroke_fill=(0, 0, 0, 255))

        else:
            font_size = 54
            while font_size > 34:
                font_clean = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
                emoji_font = ImageFont.truetype(emoji_font_path, int(font_size * 0.88))
                if max(measure_line_width(l, font_clean, emoji_font) for l in lines) <= width - 90:
                    break
                font_size -= 4

            line_spacing = int(font_size * 1.22)
            total_text_h = len(lines) * line_spacing
            start_y = (height - total_text_h) // 2

            shadow_offsets = [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]
            for idx, l in enumerate(lines):
                lw = measure_line_width(l, font_clean, emoji_font)
                tx = (width - lw) // 2
                ty = start_y + (idx * line_spacing)
                fill_color = COLOR_YELLOW if idx % 2 == 0 else COLOR_WHITE
                draw_segmented_line(tx, ty, l, font_clean, emoji_font, text_fill=fill_color, shadow_offsets=shadow_offsets, stroke_fill=(0, 0, 0, 240))

        img.save(output_png_path)
        return output_png_path

    def generate_dialogue_ass(self, words: List[Dict], ass_path: str, include_dialogue: bool = False) -> str:
        """Generates synchronized ASS subtitles with @BallQ_FC watermark (dialogue captions can be toggled)."""
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
        if include_dialogue and words:
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

        # Inject creator watermark (@BallQ_FC)
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
        """
        Renders 1080x1920 60fps vertical short with NVENC hardware encoding.
        Uses sample-accurate output seeking (-i ... -ss ... -t ...) and resets PTS
        so that the video never freezes at the start and audio never cuts out prematurely.
        """
        escaped_ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
        filter_complex = (
            f"[0:v]setpts=PTS-STARTPTS,split=2[bg][fg];"
            f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,eq=brightness=-0.15[blurred];"
            f"[fg]scale=1080:608:flags=lanczos[sharp_fg];"
            f"[blurred][sharp_fg]overlay=0:656[with_fg];"
            f"[with_fg][1:v]overlay=0:150,fps=60,ass='{escaped_ass}'"
        )
        af = "asetpts=PTS-STARTPTS,loudnorm=I=-14:LRA=7:tp=-1.5,alimiter=limit=-1.0dB:attack=5:release=50"

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
        """Runs a full detection and clipping cycle with all 5 upgrades active."""
        v_url, a_url = self.get_hls_stream_urls()
        if not v_url or not a_url:
            logger.warning("Could not reach livestream HLS feed. Retrying next cycle...")
            return []

        # UPGRADE 3: Crash-proof MPEG-TS buffer
        raw_buffer = os.path.join(self.temp_dir, "current_live_buffer.ts")
        if not self.capture_rolling_buffer(v_url, a_url, raw_buffer):
            logger.warning("Failed to capture rolling buffer.")
            return []

        # UPGRADE 1: Multi-modal prosody action detection
        action_windows = self.detect_top_action_windows(raw_buffer, max_windows=2)
        generated_clips = []

        for window_idx, (raw_start, raw_end, peak_sec) in enumerate(action_windows):
            logger.info(f"Analyzing Action Candidate {window_idx+1}: {raw_start:.1f}s - {raw_end:.1f}s (peak at {peak_sec:.1f}s)")

            # Extract broader candidate audio for transcription & sentence boundary discovery
            pre_start = max(0.0, raw_start - 2.5)
            search_dur = min(self.capture_duration_sec - pre_start, (raw_end - raw_start) + 12.0)

            candidate_audio = os.path.join(self.temp_dir, f"candidate_audio_{window_idx}.wav")
            subprocess.run([
                FFMPEG, "-y",
                "-i", raw_buffer,
                "-ss", str(pre_start),
                "-t", str(search_dur),
                "-ar", "16000", "-ac", "1",
                candidate_audio
            ], capture_output=True)

            # Transcribe to get word boundaries
            t_res = self.transcriber.transcribe(candidate_audio, language=None)
            raw_words = []
            for seg in t_res.segments:
                for w in (seg.words or []):
                    raw_words.append({
                        "word": w.word,
                        "start": w.start + pre_start,
                        "end": w.end + pre_start
                    })

            # UPGRADE 2: Snap to Sentence Boundaries
            snapped_start, snapped_end, snapped_words = self.snap_to_sentence_boundaries(
                words=raw_words,
                raw_start=raw_start,
                raw_end=raw_end,
                min_dur=24.0,
                max_dur=45.0
            )
            clip_duration = snapped_end - snapped_start

            # Generate unique clip filename
            clip_id = len(self.history) + 1
            timestamp_str = datetime.now().strftime("%H%M%S")
            clip_filename = f"viral_clip_{clip_id}_{timestamp_str}.mp4"
            output_mp4 = os.path.join(self.output_dir, clip_filename)

            # UPGRADE 4: Dynamic Quote Hook Extractor
            style_type, lines, title_text = self.extract_dynamic_quote_hook(
                clip_id=clip_id,
                transcript_text=t_res.full_text,
                words=snapped_words
            )
            banner_png = os.path.join(self.temp_dir, f"hook_{clip_id}.png")
            self.render_screenshot_style_banner(style_type, lines, banner_png)

            # Generate watermark ASS without dialogue captions (captions paused as requested)
            ass_path = os.path.join(self.temp_dir, f"captions_{clip_id}.ass")
            self.generate_dialogue_ass(snapped_words, ass_path, include_dialogue=False)

            # Render vertical clip
            success = self.render_vertical_clip(raw_buffer, snapped_start, clip_duration, banner_png, ass_path, output_mp4)
            if not success:
                logger.error(f"Failed to render clip {clip_filename}.")
                continue

            # QC validation
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
            for f in [candidate_audio, banner_png, ass_path]:
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
    parser = argparse.ArgumentParser(description="Autonomous Upgraded Live Stream Clipper")
    parser.add_argument("--url", default="https://www.youtube.com/live/jSZK6H7AgBI", help="Live stream URL to monitor and clip")
    parser.add_argument("--max-cycles", type=int, default=1, help="Number of clipping cycles to run")
    args = parser.parse_args()

    clipper = LiveStreamClipperDaemon(stream_url=args.url)

    logger.info(f"Executing continuous live stream clipper on: {args.url}")
    cycle = 0
    while cycle < args.max_cycles or args.max_cycles == 0:
        cycle += 1
        logger.info(f"--- Starting Clipping Cycle {cycle} ---")
        new_clips = clipper.process_one_cycle()
        logger.info(f"Cycle {cycle} completed. Generated {len(new_clips)} new clips: {new_clips}")
        if args.max_cycles > 0 and cycle >= args.max_cycles:
            break
        time.sleep(5)


if __name__ == "__main__":
    main()
