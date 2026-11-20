"""
AutoClip AI - Comprehensive Automated Test Suite
Validates all pipeline stages using synthetic video and audio media.
"""

import os
import shutil
import subprocess
import sys
import unittest

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.caption_generator import CaptionGenerator
from src.clip_selector import ClipSelector
from src.hook_detector import HookDetector
from src.media_inspector import MediaInspector
from src.metadata_generator import MetadataGenerator
from src.quality_control import QualityControl
from src.retention_scorer import RetentionScorer
from src.smart_crop import SmartCropper
from src.thumbnail_generator import ThumbnailGenerator
from src.transcription import Transcriber, TranscriptSegment, WordSegment
from src.video_editor import VideoEditor


class TestAutoClipPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.abspath("temp/tests")
        os.makedirs(cls.test_dir, exist_ok=True)

        cls.ffmpeg = os.path.abspath("bin/ffmpeg.exe")
        cls.ffprobe = os.path.abspath("bin/ffprobe.exe")

        # Generate synthetic 16:9 test video (1920x1080, 20 seconds, color bars with audio tone)
        cls.synthetic_video = os.path.join(cls.test_dir, "synthetic_input.mp4")
        cmd = [
            cls.ffmpeg, "-y",
            "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", "20",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            cls.synthetic_video
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Synthetic video generation failed: {res.stderr}"

    def test_01_ffmpeg_and_inspector(self):
        """Tests media inspection using ffprobe."""
        inspector = MediaInspector(ffprobe_path=self.ffprobe)
        meta = inspector.inspect(self.synthetic_video)
        self.assertEqual(meta.width, 1920)
        self.assertEqual(meta.height, 1080)
        self.assertAlmostEqual(meta.duration, 20.0, delta=1.0)
        self.assertTrue(meta.has_audio)
        self.assertTrue(meta.has_video)
        print("✓ Test 1: FFmpeg & Media Inspector verified.")

    def test_02_hook_and_retention_scoring(self):
        """Tests semantic hook detection and weighted retention scoring."""
        hook_det = HookDetector()

        # Strong hook
        strong_hook = hook_det.evaluate_hook("Why does nobody talk about this insane productivity secret?")
        self.assertGreaterEqual(strong_hook.score, 70.0)

        # Weak start
        weak_hook = hook_det.evaluate_hook("And then as I mentioned earlier uh we did that.")
        self.assertLessEqual(weak_hook.score, 40.0)

        scorer = RetentionScorer(hook_detector=hook_det)
        from src.semantic_analyzer import SemanticWindow
        win = SemanticWindow(
            start_seg_idx=0,
            end_seg_idx=1,
            start_time=0.0,
            end_time=15.0,
            duration=15.0,
            text="Stop making this mistake right now! If you want to grow your business, this is the one key framework.",
            is_question_answer=True,
            sentiment_score=0.4,
            information_density=0.8,
            actionability_score=0.9,
            controversy_score=0.7,
            humor_or_energy_score=0.8,
            summary="Stop making this mistake..."
        )
        score, breakdown, h_eval = scorer.score_window(win)
        self.assertGreaterEqual(score, 60.0)
        print(f"✓ Test 2: Hook & Retention Scorer verified (Calculated Score: {score}/100).")

    def test_03_caption_generation(self):
        """Tests ASS animated subtitle generation with word highlights."""
        words = [
            WordSegment(word="Why", start=0.0, end=0.4, probability=0.99),
            WordSegment(word="nobody", start=0.4, end=0.8, probability=0.98),
            WordSegment(word="talks", start=0.8, end=1.2, probability=0.97),
            WordSegment(word="about", start=1.2, end=1.5, probability=0.99),
            WordSegment(word="this", start=1.5, end=1.8, probability=0.99),
            WordSegment(word="secret?", start=1.8, end=2.3, probability=0.95),
        ]
        cap_gen = CaptionGenerator()
        ass_path = os.path.join(self.test_dir, "test_captions.ass")
        cap_gen.generate_ass(words, ass_path, style_preset="hormozi", clip_start_time=0.0)

        self.assertTrue(os.path.exists(ass_path))
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[Script Info]", content)
        self.assertIn("PlayResX: 1080", content)
        self.assertIn("PlayResY: 1920", content)
        self.assertIn("Dialogue:", content)
        print("✓ Test 3: Animated ASS Caption Generator verified.")

    def test_04_smart_cropping_and_video_render(self):
        """Tests 9:16 vertical video reframing with subtitle burn-in."""
        editor = VideoEditor(ffmpeg_path=self.ffmpeg)
        ass_path = os.path.join(self.test_dir, "test_captions.ass")
        output_clip = os.path.join(self.test_dir, "test_rendered_916.mp4")

        editor.render_clip(
            source_video_path=self.synthetic_video,
            start_time=0.0,
            end_time=10.0,
            output_clip_path=output_clip,
            ass_caption_path=ass_path,
            layout_mode="blurred_bg",
            burn_captions=True
        )

        self.assertTrue(os.path.exists(output_clip))
        qc = QualityControl(ffmpeg_path=self.ffmpeg)
        report = qc.verify_clip(output_clip, expected_width=1080, expected_height=1920)
        self.assertTrue(report.is_valid, f"Quality control failed: {report.errors}")
        self.assertTrue(report.resolution_valid)
        self.assertTrue(report.aspect_ratio_valid)
        self.assertTrue(report.has_audio)
        print(f"✓ Test 4: 9:16 Video Editor & QC verified (Rendered: {report.duration_actual}s, {report.file_size_mb} MB).")

    def test_05_thumbnail_and_metadata(self):
        """Tests high-CTR 1080x1920 thumbnail rendering and social metadata generation."""
        thumb_gen = ThumbnailGenerator(ffmpeg_path=self.ffmpeg)
        clip_path = os.path.join(self.test_dir, "test_rendered_916.mp4")
        thumb_path = os.path.join(self.test_dir, "test_thumb.jpg")

        thumb_gen.generate_thumbnail(
            clip_path=clip_path,
            headline_text="THE BIGGEST LIE",
            output_thumb_path=thumb_path,
            badge_text="MUST WATCH"
        )
        self.assertTrue(os.path.exists(thumb_path))

        meta_gen = MetadataGenerator()
        meta = meta_gen.generate_metadata(
            clip_id=1,
            clip_text="Why does nobody talk about this insane productivity secret that changes everything?",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            retention_score=88.5,
            hook_phrase="Why does nobody talk about this"
        )
        self.assertIn("#Shorts", meta.youtube_shorts.formatted_post)
        self.assertIn("#reels", meta.instagram_reels.formatted_post)
        self.assertIn("#fyp", meta.tiktok.formatted_post)
        print("✓ Test 5: Thumbnail Generator & Social Metadata verified.")


if __name__ == "__main__":
    unittest.main()

