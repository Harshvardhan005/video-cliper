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
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.abspath("."))
from src.media_inspector import MediaInspector
from src.quality_control import QualityControl
from src.transcription import Transcriber
from src.transliteration import to_hinglish, transliterate_word, is_devanagari

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

    def generate_unique_english_hook(self, clip_id: int, text_snippet: str) -> List[List[Tuple[str, Optional[Tuple[int, int, int, int]], bool]]]:
        """
        Generates 100% English viral meme hook titles with dynamic keywords and emojis.
        Strictly English only as requested by user.
        """
        WHITE = (255, 255, 255, 255)
        YELLOW = (255, 235, 10, 255)

        text_lower = text_snippet.lower()

        if "trailer" in text_lower or "music" in text_lower:
            return [
                [("speed's genuine reaction to", WHITE, False)],
                [("the GTA 6 soundtrack ", YELLOW, False)],
                [("he was terrified ", YELLOW, False), ("\U0001F62D\U0001F940", None, True)]
            ]
        elif "five" in text_lower or "minute" in text_lower or "time" in text_lower:
            return [
                [("speed was not ready for", WHITE, False)],
                [("the 5 minute timer ", YELLOW, False)],
                [("wait for the end ", YELLOW, False), ("\U0001F62D\U0001F480", None, True)]
            ]
        elif "gunshot" in text_lower or "crap" in text_lower or "god" in text_lower:
            return [
                [("he couldn't believe what", WHITE, False)],
                [("just happened in GTA 6 ", YELLOW, False)],
                [("his mic was peaking ", YELLOW, False), ("\U0001F480\U0001F525", None, True)]
            ]
        elif "bye" in text_lower or "head" in text_lower:
            return [
                [("bro really thought he could", WHITE, False)],
                [("survive the finale ", YELLOW, False)],
                [("watch till the end ", YELLOW, False), ("\U0001F62D\U0001F480", None, True)]
            ]
        else:
            english_templates = [
                [
                    [("speed was not ready for", WHITE, False)],
                    [("this GTA 6 mission ", YELLOW, False)],
                    [("ending was crazy ", YELLOW, False), ("\U0001F62D\U0001F480", None, True)]
                ],
                [
                    [("i wonder where they used", WHITE, False)],
                    [("2 billion $ and ", YELLOW, False)],
                    [("13 years ", YELLOW, False), ("\U0001F62D\U0001F940", None, True)]
                ],
                [
                    [("bro had a heart attack", WHITE, False)],
                    [("from this GTA 6 action ", YELLOW, False)],
                    [("nobody expected this ", YELLOW, False), ("\U0001F480\U0001F525", None, True)]
                ],
                [
                    [("the loudest scream in", WHITE, False)],
                    [("GTA 6 finale history ", YELLOW, False)],
                    [("watch till the end ", YELLOW, False), ("\U0001F62D\U0001F480", None, True)]
                ]
            ]
            return english_templates[(clip_id - 1) % len(english_templates)]

    def detect_top_action_windows(self, video_path: str, max_windows: int = 2) -> List[Tuple[float, float, float]]:
        """Detects top non-overlapping action/surprise windows based on audio RMS energy."""
        wav_path = os.path.join(self.temp_dir, "temp_live_audio.wav")
        subprocess.run([
            FFMPEG, "-y",
            "-i", video_path,
            "-vn", "-ar", "16000", "-ac", "1",
            wav_path
        ], capture_output=True)

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
            os.remove(wav_path)
        except Exception:
            pass

        return selected_windows

    def render_viral_hook_banner(
        self,
        lines: List[List[Tuple[str, Optional[Tuple[int, int, int, int]], bool]]],
        output_png_path: str,
        width: int = 1080,
        height: int = 360,
        font_size: int = 56
    ) -> str:
        """Renders authentic viral meme hook text with full-color emojis and bold Arial."""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        font_text = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
        font_emoji = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", int(font_size * 0.95))

        line_spacing = int(font_size * 1.35)
        total_text_height = len(lines) * line_spacing
        start_y = (height - total_text_height) // 2

        for line_idx, segments in enumerate(lines):
            line_w = 0
            for text, color, is_emoji in segments:
                f = font_emoji if is_emoji else font_text
                bbox = draw.textbbox((0, 0), text, font=f)
                line_w += (bbox[2] - bbox[0])

            current_x = (width - line_w) // 2
            current_y = start_y + (line_idx * line_spacing)

            for text, color, is_emoji in segments:
                f = font_emoji if is_emoji else font_text
                bbox = draw.textbbox((0, 0), text, font=f)
                seg_w = bbox[2] - bbox[0]

                if is_emoji:
                    draw.text((current_x, current_y), text, font=f, embedded_color=True)
                else:
                    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                        draw.text((current_x + dx, current_y + dy), text, font=f, fill=(0, 0, 0, 220))
                    draw.text((current_x, current_y), text, font=f, fill=color)

                current_x += seg_w

        img.save(output_png_path)
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

            # Transcribe
            t_res = self.transcriber.transcribe(clip_audio_wav, language="en")
            words = [{"word": w.word, "start": w.start, "end": w.end} for seg in t_res.segments for w in (seg.words or [])]
            logger.info(f"Transcribed {len(words)} words: '{t_res.full_text[:80]}...'")

            # Generate unique clip filename
            clip_id = len(self.history) + 1
            timestamp_str = datetime.now().strftime("%H%M%S")
            clip_filename = f"speed_action_clip_{clip_id}_{timestamp_str}.mp4"
            output_mp4 = os.path.join(self.output_dir, clip_filename)

            # Generate 100% English unique viral hook banner matching user reference
            chosen_hook = self.generate_unique_english_hook(clip_id, t_res.full_text)
            banner_png = os.path.join(self.temp_dir, f"hook_{clip_id}.png")
            self.render_viral_hook_banner(chosen_hook, banner_png)

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

            # Reconstruct title text for manifest
            title_text = " ".join("".join(seg[0] for seg in line) for line in chosen_hook)

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
    stream_url = "https://www.youtube.com/live/OIeLbmyraRQ"
    clipper = LiveStreamClipperDaemon(stream_url=stream_url)

    logger.info("Executing continuous live stream clipper cycle...")
    new_clips = clipper.process_one_cycle()
    logger.info(f"Cycle completed. Generated {len(new_clips)} new clips: {new_clips}")


if __name__ == "__main__":
    main()

