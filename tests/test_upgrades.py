import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))
from src.live_stream_monitor import LiveStreamClipperDaemon

class TestUpgrades(unittest.TestCase):
    def setUp(self):
        self.daemon = LiveStreamClipperDaemon(stream_url="https://www.youtube.com/live/dummy")

    def test_sentence_boundary_snapping(self):
        words = [
            {"word": "Hey", "start": 1.0, "end": 1.3},
            {"word": "guys", "start": 1.4, "end": 1.8},
            {"word": "look", "start": 2.0, "end": 2.4},
            {"word": "at", "start": 2.5, "end": 2.6},
            {"word": "this", "start": 2.7, "end": 2.9},
            {"word": "car!", "start": 3.0, "end": 3.5},
            {"word": "We", "start": 4.5, "end": 4.8},
            {"word": "are", "start": 4.9, "end": 5.1},
            {"word": "going", "start": 5.2, "end": 5.5},
            {"word": "fast.", "start": 5.6, "end": 6.0},
            {"word": "Is", "start": 28.0, "end": 28.3},
            {"word": "that", "start": 28.4, "end": 28.6},
            {"word": "a", "start": 28.7, "end": 28.8},
            {"word": "cop?", "start": 28.9, "end": 29.3},
            {"word": "Oh", "start": 30.5, "end": 30.8},
            {"word": "no!", "start": 30.9, "end": 31.4},
            {"word": "Run!", "start": 32.0, "end": 32.5},
            {"word": "Okay", "start": 40.0, "end": 40.4},
        ]
        snapped_start, snapped_end, adjusted_words = self.daemon.snap_to_sentence_boundaries(
            words=words,
            raw_start=2.0,
            raw_end=33.0,
            min_dur=24.0,
            max_dur=45.0
        )
        self.assertTrue(snapped_start <= 2.0)
        self.assertTrue(snapped_end >= 28.0)
        dur = snapped_end - snapped_start
        self.assertTrue(24.0 <= dur <= 46.0)
        self.assertTrue(len(adjusted_words) > 0)
        # Check relative offsets
        self.assertAlmostEqual(adjusted_words[0]["start"], 0.0, delta=1.5)

    def test_dynamic_quote_hook(self):
        text = "Wait bro is that a real supercar or what? Bro look at that speed!"
        words = [{"word": w, "start": i*0.5, "end": i*0.5 + 0.4} for i, w in enumerate(text.split())]
        style, lines, title = self.daemon.extract_dynamic_quote_hook(
            clip_id=99,
            transcript_text=text,
            words=words
        )
        self.assertIn(style, ["tiktok_bubble", "heavy_stroke", "condensed_pov", "minimal_white"])
        self.assertTrue(len(lines) >= 1)
        self.assertTrue(len(title) > 0)

    def test_all_screenshot_banners(self):
        temp_dir = self.daemon.temp_dir
        for style in ["tiktok_bubble", "heavy_stroke", "condensed_pov", "minimal_white"]:
            out_png = os.path.join(temp_dir, f"test_banner_{style}.png")
            self.daemon.render_screenshot_style_banner(
                style_type=style,
                lines=["LINE ONE TEST", "LINE TWO TEST \U0001F480"],
                output_png_path=out_png
            )
            self.assertTrue(os.path.exists(out_png))
            self.assertTrue(os.path.getsize(out_png) > 1000)
            os.remove(out_png)

if __name__ == "__main__":
    unittest.main()
