"""
Clip Selector Module
Selects and ranks candidate clips according to duration constraints,
sentence alignment, and retention scoring.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from src.hook_detector import HookScore
from src.retention_scorer import RetentionBreakdown, RetentionScorer
from src.semantic_analyzer import SemanticAnalyzer, SemanticWindow
from src.transcription import TranscriptSegment, WordSegment

logger = logging.getLogger(__name__)


@dataclass
class CandidateClip:
    id: int
    title: str
    start_time: float
    end_time: float
    duration: float
    text: str
    hook_type: str
    hook_phrase: str
    retention_score: float
    breakdown: RetentionBreakdown
    segments: List[TranscriptSegment]
    words: List[WordSegment]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "text": self.text,
            "hook_type": self.hook_type,
            "hook_phrase": self.hook_phrase,
            "retention_score": self.retention_score,
            "breakdown": self.breakdown.to_dict(),
            "word_count": len(self.words)
        }


class ClipSelector:
    """Ranks and filters moments into short-form candidate clips."""

    DURATION_PRESETS = {
        "short": (15.0, 30.0),
        "medium": (30.0, 45.0),
        "long": (45.0, 60.0),
        "extended": (60.0, 90.0)
    }

    def __init__(
        self,
        retention_scorer: Optional[RetentionScorer] = None,
        semantic_analyzer: Optional[SemanticAnalyzer] = None
    ):
        self.retention_scorer = retention_scorer or RetentionScorer()
        self.semantic_analyzer = semantic_analyzer or SemanticAnalyzer()

    def select_clips(
        self,
        transcript_segments: List[TranscriptSegment],
        duration_preset: str = "medium",
        min_retention_score: float = 50.0,
        max_clips: int = 5,
        target_clip_duration: Optional[float] = None
    ) -> List[CandidateClip]:
        """
        Analyzes transcript and returns the highest-ranking non-overlapping candidate clips.
        """
        total_audio_dur = transcript_segments[-1].end if transcript_segments else 60.0
        min_dur, max_dur = self.DURATION_PRESETS.get(duration_preset, (20.0, 50.0))

        # Dynamically adapt duration bounds if source media is short
        if total_audio_dur < min_dur:
            min_dur = max(3.0, total_audio_dur * 0.5)
            max_dur = max(min_dur + 1.0, total_audio_dur)

        target_dur = target_clip_duration or ((min_dur + max_dur) / 2.0)

        # 1. Segment grouping & semantic window generation
        windows = self.semantic_analyzer.analyze_segments(
            segments=transcript_segments,
            window_duration_target=target_dur,
            min_duration=min_dur,
            max_duration=max_dur
        )

        scored_candidates: List[CandidateClip] = []

        for idx, win in enumerate(windows):
            score, breakdown, hook_eval = self.retention_scorer.score_window(win)

            if score < min_retention_score:
                continue

            # Gather sub-segments and word-level timestamps
            clip_segs = transcript_segments[win.start_seg_idx : win.end_seg_idx + 1]
            clip_words: List[WordSegment] = []
            for seg in clip_segs:
                clip_words.extend(seg.words)

            # Fine-tune start and end timestamps using exact first and last word timestamps
            refined_start = clip_words[0].start if clip_words else win.start_time
            refined_end = clip_words[-1].end if clip_words else win.end_time
            refined_duration = round(refined_end - refined_start, 2)

            # Generate punchy working title from hook phrase
            clean_phrase = hook_eval.first_phrase.strip().capitalize()
            title = f"{clean_phrase}..." if len(clean_phrase) > 10 else f"Highlight #{idx + 1}"

            candidate = CandidateClip(
                id=idx + 1,
                title=title,
                start_time=refined_start,
                end_time=refined_end,
                duration=refined_duration,
                text=win.text,
                hook_type=hook_eval.hook_type,
                hook_phrase=hook_eval.first_phrase,
                retention_score=score,
                breakdown=breakdown,
                segments=clip_segs,
                words=clip_words
            )
            scored_candidates.append(candidate)

        # Sort descending by retention score
        scored_candidates.sort(key=lambda c: c.retention_score, reverse=True)

        # De-duplicate clips that share more than 30% time overlap
        selected_clips: List[CandidateClip] = []
        for cand in scored_candidates:
            if len(selected_clips) >= max_clips:
                break

            overlap = False
            for sel in selected_clips:
                inter_start = max(cand.start_time, sel.start_time)
                inter_end = min(cand.end_time, sel.end_time)
                if inter_end > inter_start:
                    inter_dur = inter_end - inter_start
                    if inter_dur > (min(cand.duration, sel.duration) * 0.35):
                        overlap = True
                        break

            if not overlap:
                cand.id = len(selected_clips) + 1
                selected_clips.append(cand)

        logger.info(f"Selected {len(selected_clips)} viral candidate clips.")
        return selected_clips
