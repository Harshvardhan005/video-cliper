"""
Unit tests for WatermarkManager and branding integration.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))
from src.watermark import WatermarkManager


class TestWatermarkManager(unittest.TestCase):

    def setUp(self):
        self.wm = WatermarkManager()

    def test_default_watermark_text(self):
        self.assertEqual(self.wm.text, "@BallQ_FC")
        self.assertTrue(self.wm.enabled)

    def test_coordinates_positions(self):
        self.wm.position = "center_below_video"
        cx, cy = self.wm.get_coordinates(1080, 1920)
        self.assertEqual(cx, 540)
        self.assertEqual(cy, 1285)

        self.wm.position = "center_above_video"
        cx, cy = self.wm.get_coordinates(1080, 1920)
        self.assertEqual(cx, 540)
        self.assertEqual(cy, 620)

    def test_ass_style_and_dialogue_generation(self):
        style, dialogue = self.wm.get_ass_style_and_event(clip_duration=34.0)
        self.assertIn("Style: Watermark", style)
        self.assertIn("@BallQ_FC", dialogue)
        self.assertIn("0:00:34.00", dialogue)
        self.assertIn("\\pos(540,1285)", dialogue)

    def test_inject_into_ass_file(self):
        test_ass = "temp_work/watermark_test/inject_test.ass"
        os.makedirs(os.path.dirname(test_ass), exist_ok=True)
        with open(test_ass, "w", encoding="utf-8") as f:
            f.write("""[Script Info]
Title: Sample
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname
Style: Default,Arial

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:01.00,0:00:03.00,Default,Hello
""")

        success = self.wm.inject_into_ass_file(test_ass, clip_duration=10.0)
        self.assertTrue(success)

        with open(test_ass, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Style: Watermark", content)
        self.assertIn("@BallQ_FC", content)

    def test_create_watermark_image(self):
        out_png = "temp_work/watermark_test/test_badge.png"
        res = self.wm.create_watermark_image(out_png)
        self.assertTrue(os.path.exists(res))
        self.assertGreater(os.path.getsize(res), 1000)


if __name__ == "__main__":
    unittest.main()

