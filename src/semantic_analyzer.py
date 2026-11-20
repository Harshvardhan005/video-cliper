"""
Semantic Content Analyzer Module
Extracts semantic cues, dialog structures, actionable insights, and emotional tone from transcripts.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.transcription import TranscriptSegment

logger = logging.getLogger(__name__)


@dataclass
class SemanticWindow:
    start_seg_idx: int
    end_seg_idx: int
    start_time: float
    end_time: float
    duration: float
    text: str
    is_question_answer: bool
    sentiment_score: float        # -1.0 to +1.0
    information_density: float     # 0.0 to 1.0
    actionability_score: float     # 0.0 to 1.0
    controversy_score: float       # 0.0 to 1.0
    humor_or_energy_score: float   # 0.0 to 1.0
    summary: str


class SemanticAnalyzer:
    """Analyzes transcript segments to score semantic density and contextual value."""

    STRONG_OPINION_MARKERS = [
        r"\bi believe\b", r"\bin my opinion\b", r"\bthe truth is\b", r"\bhonestly\b",
        r"\bthe problem with\b", r"\beveryone is wrong\b", r"\bnever do\b", r"\balways\b",
        r"\bworst mistake\b", r"\bbiggest lie\b", r"\bunderrated\b", r"\boverrated\b",
        r"\bsecret\b", r"\bgame changer\b", r"\brevolutionary\b", r"\bfail\b", r"\binsane\b"
    ]

    ACTIONABLE_MARKERS = [
        r"\bhow to\b", r"\bstep one\b", r"\bfirst thing\b", r"\byou should\b",
        r"\bmake sure you\b", r"\bthe key is\b", r"\bpro tip\b", r"\btry this\b",
        r"\bformula\b", r"\bstrategy\b", r"\bframework\b", r"\bmethod\b", r"\bguide\b"
    ]

    SURPRISE_MARKERS = [
        r"\bshocking\b", r"\bwait until\b", r"\bcan't believe\b", r"\bunbelievable\b",
        r"\bplot twist\b", r"\bactually\b", r"\bno way\b", r"\bcrazy thing is\b",
        r"\bhere's the catch\b", r"\bwhat happened was\b", r"\bnever expected\b"
    ]

    POSITIVE_WORDS = {
        "amazing", "incredible", "great", "best", "brilliant", "love", "awesome",
        "genius", "mastery", "huge", "massive", "win", "legendary", "super"
    }

    NEGATIVE_WORDS = {
        "terrible", "worst", "hate", "scam", "ruined", "disaster", "fail",
        "toxic", "horrible", "awful", "destroyed", "nightmare", "deadly"
    }

    def __init__(self):
        pass

    def analyze_segments(
        self,
        segments: List[TranscriptSegment],
        window_duration_target: float = 35.0,
        min_duration: float = 15.0,
        max_duration: float = 65.0
    ) -> List[SemanticWindow]:
        """
        Groups transcript segments into semantic windows and scores each window.
        """
        if not segments:
            return []

        windows: List[SemanticWindow] = []
        n = len(segments)

        for i in range(n):
            current_text_list = []
            start_time = segments[i].start

            for j in range(i, n):
                end_time = segments[j].end
                duration = end_time - start_time

                if duration > max_duration:
                    break

                current_text_list.append(segments[j].text.strip())
                full_text = " ".join(current_text_list)

                # If duration fits target window and ends on a logical boundary (. ! ?)
                if duration >= min_duration:
                    ends_on_sentence = bool(re.search(r"[.!?]$", full_text.strip()))
                    if ends_on_sentence or duration >= window_duration_target:
                        window = self._score_window(
                            segments=segments,
                            start_idx=i,
                            end_idx=j,
                            start_time=start_time,
                            end_time=end_time,
                            text=full_text
                        )
                        windows.append(window)

        # De-duplicate windows that have almost identical boundaries
        unique_windows = self._deduplicate_windows(windows)
        return unique_windows

    def _score_window(
        self,
        segments: List[TranscriptSegment],
        start_idx: int,
        end_idx: int,
        start_time: float,
        end_time: float,
        text: str
    ) -> SemanticWindow:
        duration = max(end_time - start_time, 0.1)
        text_lower = text.lower()
        words = re.findall(r"\b\w+\b", text_lower)
        word_count = len(words)

        # 1. Information density: words per second (optimal conversational rate is ~2.5 - 3.5 words/sec)
        wps = word_count / duration
        info_density = min(1.0, max(0.0, (wps - 1.0) / 3.0))

        # 2. Q&A pattern detection
        has_question = "?" in text[:int(len(text) * 0.45)]
        has_answer = ("because" in text_lower or "so" in text_lower or "is that" in text_lower or "." in text)
        is_qa = has_question and has_answer

        # 3. Actionability & Advice
        action_hits = sum(1 for m in self.ACTIONABLE_MARKERS if re.search(m, text_lower))
        actionability = min(1.0, action_hits * 0.35)

        # 4. Controversy & Strong opinions
        opinion_hits = sum(1 for m in self.STRONG_OPINION_MARKERS if re.search(m, text_lower))
        controversy = min(1.0, opinion_hits * 0.3)

        # 5. Surprise & Emotional hooks
        surprise_hits = sum(1 for m in self.SURPRISE_MARKERS if re.search(m, text_lower))
        pos_hits = sum(1 for w in words if w in self.POSITIVE_WORDS)
        neg_hits = sum(1 for w in words if w in self.NEGATIVE_WORDS)
        sentiment_score = (pos_hits - neg_hits) / max(pos_hits + neg_hits, 1)
        humor_energy = min(1.0, (surprise_hits * 0.4) + (abs(sentiment_score) * 0.3))

        summary = text[:80] + "..." if len(text) > 80 else text

        return SemanticWindow(
            start_seg_idx=start_idx,
            end_seg_idx=end_idx,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            text=text,
            is_question_answer=is_qa,
            sentiment_score=sentiment_score,
            information_density=round(info_density, 3),
            actionability_score=round(actionability, 3),
            controversy_score=round(controversy, 3),
            humor_or_energy_score=round(humor_energy, 3),
            summary=summary
        )

    def _deduplicate_windows(self, windows: List[SemanticWindow], overlap_thresh: float = 0.7) -> List[SemanticWindow]:
        if not windows:
            return []

        sorted_wins = sorted(
            windows,
            key=lambda w: (w.actionability_score + w.controversy_score + w.humor_or_energy_score),
            reverse=True
        )

        chosen: List[SemanticWindow] = []
        for cand in sorted_wins:
            overlap = False
            for c in chosen:
                inter_start = max(cand.start_time, c.start_time)
                inter_end = min(cand.end_time, c.end_time)
                if inter_end > inter_start:
                    inter_len = inter_end - inter_start
                    union_len = max(cand.end_time, c.end_time) - min(cand.start_time, c.start_time)
                    iou = inter_len / max(union_len, 0.1)
                    if iou > overlap_thresh:
                        overlap = True
                        break
            if not overlap:
                chosen.append(cand)

        chosen.sort(key=lambda w: w.start_time)
        return chosen

