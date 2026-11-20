"""
Retention Scorer Module
Calculates multi-signal viral retention potential score (0 - 100) combining
hook strength, emotional tone, information density, narrative structure, and audio/visual energy.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

from src.hook_detector import HookDetector, HookScore
from src.semantic_analyzer import SemanticWindow

logger = logging.getLogger(__name__)


@dataclass
class RetentionBreakdown:
    hook_strength: float           # 0 - 100 (weight 25%)
    emotional_engagement: float    # 0 - 100 (weight 20%)
    information_value: float       # 0 - 100 (weight 20%)
    narrative_completeness: float  # 0 - 100 (weight 15%)
    visual_engagement: float       # 0 - 100 (weight 10%)
    audio_quality: float           # 0 - 100 (weight 10%)
    total_score: float             # 0 - 100

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


class RetentionScorer:
    """Calculates weighted retention potential score for video moments."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        hook_detector: Optional[HookDetector] = None
    ):
        self.weights = weights or {
            "hook_strength": 0.25,
            "emotional_engagement": 0.20,
            "information_value": 0.20,
            "narrative_completeness": 0.15,
            "visual_engagement": 0.10,
            "audio_quality": 0.10,
        }
        self.hook_detector = hook_detector or HookDetector()

    def score_window(
        self,
        window: SemanticWindow,
        visual_activity_score: float = 70.0,
        audio_energy_score: float = 75.0
    ) -> Tuple[float, RetentionBreakdown, HookScore]:
        """
        Computes composite retention score based on semantic signals and video/audio hints.
        """
        # 1. Hook strength (0-100)
        hook_eval = self.hook_detector.evaluate_hook(window.text)
        hook_score = hook_eval.score

        # 2. Emotional engagement (0-100)
        # Driven by sentiment extremity, humor/surprise, or controversy
        emotion_raw = (window.humor_or_energy_score * 0.5) + (window.controversy_score * 0.5)
        emotion_score = min(100.0, max(20.0, emotion_raw * 100.0 + 30.0))

        # 3. Information value (0-100)
        info_raw = (window.information_density * 0.5) + (window.actionability_score * 0.5)
        if window.is_question_answer:
            info_raw = min(1.0, info_raw + 0.2)
        info_score = min(100.0, max(25.0, info_raw * 100.0 + 20.0))

        # 4. Narrative completeness (0-100)
        # Evaluates if it starts cleanly and finishes on a strong period/question
        ends_well = window.text.strip().endswith((".", "!", "?"))
        narrative_score = 85.0 if ends_well else 50.0
        if 20.0 <= window.duration <= 50.0:
            narrative_score += 15.0  # sweet spot for short-form retention
        narrative_score = min(100.0, max(20.0, narrative_score))

        # 5. Visual engagement & 6. Audio quality
        vis_score = min(100.0, max(10.0, visual_activity_score))
        aud_score = min(100.0, max(10.0, audio_energy_score))

        # Weighted calculation
        total = (
            hook_score * self.weights["hook_strength"] +
            emotion_score * self.weights["emotional_engagement"] +
            info_score * self.weights["information_value"] +
            narrative_score * self.weights["narrative_completeness"] +
            vis_score * self.weights["visual_engagement"] +
            aud_score * self.weights["audio_quality"]
        )
        total = round(max(0.0, min(100.0, total)), 1)

        breakdown = RetentionBreakdown(
            hook_strength=hook_score,
            emotional_engagement=round(emotion_score, 1),
            information_value=round(info_score, 1),
            narrative_completeness=round(narrative_score, 1),
            visual_engagement=round(vis_score, 1),
            audio_quality=round(aud_score, 1),
            total_score=total
        )

        return total, breakdown, hook_eval
