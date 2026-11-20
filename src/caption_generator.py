"""
Animated Caption Generator Module
Generates Advanced SubStation Alpha (.ass) subtitles with dynamic word-level highlights,
color styling, and mobile-safe margins for viral short-form video formats.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml
from src.transcription import WordSegment
from src.transliteration import to_hinglish, transliterate_word, is_devanagari

logger = logging.getLogger(__name__)


class CaptionGenerator:
    """Generates styled ASS subtitle files with word-level highlighting."""

    def __init__(self, presets_path: str = "config/presets.yaml"):
        self.presets = self._load_presets(presets_path)

    @staticmethod
    def _load_presets(presets_path: str) -> Dict:
        if os.path.exists(presets_path):
            with open(presets_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("presets", {})
        return {}

    def generate_ass(
        self,
        words: List[WordSegment],
        output_ass_path: str,
        style_preset: str = "hormozi",
        clip_start_time: float = 0.0,
        use_hinglish: bool = True
    ) -> str:
        """
        Creates an ASS subtitle file with word-by-word highlight synchronization.
        `clip_start_time` is subtracted from word timestamps to align with clipped video start.
        If `use_hinglish` is True, Devanagari text is automatically transliterated into readable Hinglish.
        """
        os.makedirs(os.path.dirname(output_ass_path), exist_ok=True)
        preset = self.presets.get(style_preset, self.presets.get("hormozi", {}))

        font_name = preset.get("font_family", "Century Gothic").split(",")[0].strip()
        font_size = preset.get("font_size", 54)
        is_bold = -1 if preset.get("font_weight", "bold") == "bold" else 0
        primary_color = preset.get("color_primary", "&H00FFFFFF")
        highlight_color = preset.get("color_highlight", "&H00FFFF00")
        outline_color = preset.get("outline_color", "&H000A0A0A")
        outline_w = preset.get("outline_width", 3)
        shadow_w = preset.get("shadow_offset", 2)
        margin_v = preset.get("margin_v", 260)
        is_uppercase = preset.get("text_transform") == "uppercase"
        words_per_group = preset.get("words_per_line", 3)

        header = f"""[Script Info]
Title: AI Video Clipper Animated Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,{is_bold},0,0,0,100,100,0,0,1,{outline_w},{shadow_w},2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []

        # Filter words belonging to clip and offset timestamps
        relative_words: List[WordSegment] = []
        for w in words:
            rel_start = max(0.0, w.start - clip_start_time)
            rel_end = max(rel_start + 0.1, w.end - clip_start_time)
            clean_text = w.word.strip()
            if use_hinglish and is_devanagari(clean_text):
                clean_text = transliterate_word(clean_text)

            relative_words.append(
                WordSegment(
                    word=clean_text,
                    start=rel_start,
                    end=rel_end,
                    probability=w.probability
                )
            )

        # Chunk into small mobile-readable phrases (e.g. 2-4 words)
        for i in range(0, len(relative_words), words_per_group):
            chunk = relative_words[i : i + words_per_group]
            if not chunk:
                continue

            chunk_start = chunk[0].start
            chunk_end = chunk[-1].end

            # Create word-by-word highlight events within this chunk
            for active_idx, active_word in enumerate(chunk):
                w_start = active_word.start
                w_end = active_word.end

                # Build line text where active word is highlighted
                line_parts = []
                for idx, w in enumerate(chunk):
                    clean_w = w.word.upper() if is_uppercase else w.word
                    if idx == active_idx:
                        # Highlight active word with color override
                        line_parts.append(f"{{\\c{highlight_color}\\b1}}{clean_w}{{\\c{primary_color}\\b{abs(is_bold)}}}")
                    else:
                        line_parts.append(clean_w)

                dialogue_text = " ".join(line_parts)
                start_str = self._format_ass_time(w_start)
                end_str = self._format_ass_time(w_end)

                events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{dialogue_text}")

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events) + "\n")

        logger.info(f"Generated ASS captions ({style_preset}) at: {output_ass_path}")
        return output_ass_path

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            centis = 99
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:01d}:{mins:02d}:{secs:02d}.{centis:02d}"

