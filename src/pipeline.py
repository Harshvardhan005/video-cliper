"""
Autonomous AI Video Clipper Pipeline Orchestrator
Master pipeline executing ingestion, speech recognition, viral moment discovery,
9:16 vertical reframing, animated captions, audio mastering, thumbnail creation, and QC.
"""

import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Callable, Dict, List, Optional

from src.caption_generator import CaptionGenerator
from src.clip_selector import CandidateClip, ClipSelector
from src.ingestion import IngestionResult, MediaIngestor
from src.metadata_generator import ClipMetadata, MetadataGenerator
from src.quality_control import QualityControl, QualityReport
from src.thumbnail_generator import ThumbnailGenerator
from src.transcription import Transcriber, TranscriptionResult
from src.video_editor import VideoEditor

logger = logging.getLogger(__name__)


@dataclass
class ProcessedClipOutput:
    clip_id: int
    title: str
    clip_video_path: str
    thumbnail_path: str
    ass_caption_path: str
    metadata_json_path: str
    retention_score: float
    duration: float
    start_time: float
    end_time: float
    quality: QualityReport
    metadata: ClipMetadata

    def to_dict(self) -> Dict:
        return {
            "clip_id": self.clip_id,
            "title": self.title,
            "clip_video_path": os.path.abspath(self.clip_video_path),
            "thumbnail_path": os.path.abspath(self.thumbnail_path),
            "ass_caption_path": os.path.abspath(self.ass_caption_path),
            "metadata_json_path": os.path.abspath(self.metadata_json_path),
            "retention_score": self.retention_score,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_valid": self.quality.is_valid,
            "quality_errors": self.quality.errors,
            "platforms": {
                "youtube": self.metadata.youtube_shorts.formatted_post,
                "reels": self.metadata.instagram_reels.formatted_post,
                "tiktok": self.metadata.tiktok.formatted_post
            }
        }


@dataclass
class PipelineResult:
    job_id: str
    source_input: str
    transcription: TranscriptionResult
    clips: List[ProcessedClipOutput]
    total_processing_time: float
    status: str

    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "source_input": self.source_input,
            "total_processing_time": self.total_processing_time,
            "status": self.status,
            "clip_count": len(self.clips),
            "clips": [c.to_dict() for c in self.clips]
        }


class VideoClipperPipeline:
    """End-to-end autonomous video clipping system."""

    def __init__(
        self,
        output_dir: str = "output",
        temp_dir: str = "temp",
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        self.ingestor = MediaIngestor(output_dir=self.temp_dir)
        self.transcriber = Transcriber(
            model_size=model_size,
            device=device,
            compute_type=compute_type
        )
        self.clip_selector = ClipSelector()
        self.caption_generator = CaptionGenerator()
        self.video_editor = VideoEditor()
        self.thumbnail_generator = ThumbnailGenerator()
        self.metadata_generator = MetadataGenerator()
        self.quality_control = QualityControl()

    def process(
        self,
        input_source: str,
        job_id: Optional[str] = None,
        duration_preset: str = "medium",
        max_clips: int = 5,
        min_retention_score: float = 50.0,
        caption_preset: str = "hormozi",
        layout_mode: str = "smart_auto",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> PipelineResult:
        """Executes full autonomous pipeline from video input to finished short-form clips."""
        start_time_all = time.time()
        job_id = job_id or f"job_{int(start_time_all)}"

        job_clip_dir = os.path.join(self.output_dir, "clips", job_id)
        job_thumb_dir = os.path.join(self.output_dir, "thumbnails", job_id)
        job_cap_dir = os.path.join(self.output_dir, "captions", job_id)
        job_meta_dir = os.path.join(self.output_dir, "metadata", job_id)

        for d in [job_clip_dir, job_thumb_dir, job_cap_dir, job_meta_dir]:
            os.makedirs(d, exist_ok=True)

        # 1. Ingestion
        if progress_callback:
            progress_callback("Phase 1/6: Media ingestion and audio normalization...", 0.05)
        ingest_res: IngestionResult = self.ingestor.ingest(
            input_source,
            progress_callback=lambda msg, p: progress_callback(f"Ingestion: {msg}", 0.05 + (p * 0.15)) if progress_callback else None
        )

        # 2. Transcription
        if progress_callback:
            progress_callback("Phase 2/6: Speech recognition & word alignment...", 0.20)
        transcript_res: TranscriptionResult = self.transcriber.transcribe(
            audio_path=ingest_res.audio_path,
            progress_callback=lambda msg, p: progress_callback(f"Transcription: {msg}", 0.20 + (p * 0.20)) if progress_callback else None
        )

        # Save complete transcript
        transcript_json_path = os.path.join(job_meta_dir, "full_transcript.json")
        transcript_srt_path = os.path.join(job_meta_dir, "full_transcript.srt")
        transcript_res.save_json(transcript_json_path)
        transcript_res.save_srt(transcript_srt_path)

        # 3. Viral Moment Detection & Clip Selection
        if progress_callback:
            progress_callback("Phase 3/6: Semantic analysis & retention scoring...", 0.45)

        candidate_clips: List[CandidateClip] = self.clip_selector.select_clips(
            transcript_segments=transcript_res.segments,
            duration_preset=duration_preset,
            min_retention_score=min_retention_score,
            max_clips=max_clips
        )

        if not candidate_clips:
            # Fallback if no moments met high retention threshold: select top 1-2 default windows
            logger.warning("No clips met the retention threshold. Generating fallback highlight window.")
            candidate_clips = self.clip_selector.select_clips(
                transcript_segments=transcript_res.segments,
                duration_preset=duration_preset,
                min_retention_score=20.0,
                max_clips=max(1, max_clips)
            )

        # 4. Rendering, Captions, Thumbnails, Metadata & QC per Clip
        processed_outputs: List[ProcessedClipOutput] = []
        total_clips = len(candidate_clips)

        for i, clip in enumerate(candidate_clips):
            clip_idx = i + 1
            clip_base = f"clip_{clip_idx:02d}"
            progress_base = 0.50 + ((i / max(total_clips, 1)) * 0.45)

            if progress_callback:
                progress_callback(f"Phase 4/6: Processing clip {clip_idx}/{total_clips} ('{clip.title}')...", progress_base)

            # A. Generate ASS animated captions
            ass_path = os.path.join(job_cap_dir, f"{clip_base}.ass")
            self.caption_generator.generate_ass(
                words=clip.words,
                output_ass_path=ass_path,
                style_preset=caption_preset,
                clip_start_time=clip.start_time
            )

            # B. Render 9:16 Video with burn-in captions & audio mastering
            clip_video_path = os.path.join(job_clip_dir, f"{clip_base}.mp4")
            self.video_editor.render_clip(
                source_video_path=ingest_res.video_path,
                start_time=clip.start_time,
                end_time=clip.end_time,
                output_clip_path=clip_video_path,
                ass_caption_path=ass_path,
                layout_mode=layout_mode,
                burn_captions=True
            )

            # C. Generate 1080x1920 Viral Thumbnail
            thumb_path = os.path.join(job_thumb_dir, f"{clip_base}_thumb.jpg")
            self.thumbnail_generator.generate_thumbnail(
                clip_path=clip_video_path,
                headline_text=clip.hook_phrase,
                output_thumb_path=thumb_path,
                badge_text="VIRAL MOMENT"
            )

            # D. Generate Social Media Metadata
            clip_metadata: ClipMetadata = self.metadata_generator.generate_metadata(
                clip_id=clip_idx,
                clip_text=clip.text,
                start_time=clip.start_time,
                end_time=clip.end_time,
                duration=clip.duration,
                retention_score=clip.retention_score,
                hook_phrase=clip.hook_phrase
            )
            meta_json_path = os.path.join(job_meta_dir, f"{clip_base}_metadata.json")
            clip_metadata.save_json(meta_json_path)

            # E. Quality Control Verification
            qc_report = self.quality_control.verify_clip(
                clip_path=clip_video_path,
                expected_width=1080,
                expected_height=1920
            )

            out = ProcessedClipOutput(
                clip_id=clip_idx,
                title=clip.title,
                clip_video_path=clip_video_path,
                thumbnail_path=thumb_path,
                ass_caption_path=ass_path,
                metadata_json_path=meta_json_path,
                retention_score=clip.retention_score,
                duration=clip.duration,
                start_time=clip.start_time,
                end_time=clip.end_time,
                quality=qc_report,
                metadata=clip_metadata
            )
            processed_outputs.append(out)

        total_elapsed = round(time.time() - start_time_all, 2)
        if progress_callback:
            progress_callback("Phase 6/6: Pipeline execution complete!", 1.0)

        return PipelineResult(
            job_id=job_id,
            source_input=input_source,
            transcription=transcript_res,
            clips=processed_outputs,
            total_processing_time=total_elapsed,
            status="completed"
        )

