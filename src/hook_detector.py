"""
Hook Detector Module
Identifies high-impact opening seconds (first 3-5s) of potential short-form video clips.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HookScore:
    score: float           # 0.0 to 100.0
    hook_type: str         # "question", "revelation", "curiosity", "negative_callout", "standard"
    first_phrase: str
    reasons: List[str]


class HookDetector:
    """Evaluates the first 3-5 seconds of speech in a window for retention hook power."""

    QUESTION_HOOKS = [
        r"^why\b", r"^how\b", r"^what if\b", r"^have you ever\b", r"^did you know\b",
        r"^do you know\b", r"^is it true\b", r"^can you\b", r"^would you\b"
    ]

    REVELATION_HOOKS = [
        r"\bthe real reason\b", r"\bnobody talks about\b", r"\bhere's the truth\b",
        r"\bthis is why\b", r"\bi found out\b", r"\bthe biggest secret\b",
        r"\bwhat they don't tell you\b", r"\bnever do this\b"
    ]

    NEGATIVE_CALLOUT_HOOKS = [
        r"\bstop doing\b", r"\bdon't make this mistake\b", r"\byou're doing it wrong\b",
        r"\bthis will destroy\b", r"\bthe worst thing\b", r"\bwaste of money\b"
    ]

    DISQUALIFYING_WEAK_STARTS = [
        r"^and then\b", r"^like i said\b", r"^as i mentioned\b", r"^so anyway\b",
        r"^in that case\b", r"^yeah but\b", r"^which means that\b", r"^uh\b", r"^um\b"
    ]

    def evaluate_hook(self, text: str, first_n_words: int = 15) -> HookScore:
        """Evaluates whether the beginning of the text forms a viral hook."""
        clean_text = text.strip()
        words = clean_text.split()
        lead = " ".join(words[:first_n_words]).lower()
        first_phrase = " ".join(words[:min(len(words), 8)])

        score = 50.0  # Baseline
        hook_type = "standard"
        reasons = []

        # Check disqualifiers (poor context starts)
        for weak in self.DISQUALIFYING_WEAK_STARTS:
            if re.search(weak, lead):
                score -= 30.0
                reasons.append("Weak conversational connector at start")
                break

        # 1. Question hooks
        for q in self.QUESTION_HOOKS:
            if re.search(q, lead) or lead.endswith("?"):
                score += 28.0
                hook_type = "question"
                reasons.append("High curiosity question opening")
                break

        # 2. Revelation hooks
        for rev in self.REVELATION_HOOKS:
            if re.search(rev, lead):
                score += 32.0
                hook_type = "revelation"
                reasons.append("Compelling revelation / truth statement")
                break

        # 3. Negative callout / Warning hooks
        for neg in self.NEGATIVE_CALLOUT_HOOKS:
            if re.search(neg, lead):
                score += 30.0
                hook_type = "negative_callout"
                reasons.append("High-urgency pattern interrupt / warning")
                break

        # Punctuation emphasis
        if re.search(r"^[A-Z0-9].{3,35}\?", clean_text):
            score += 10.0
            reasons.append("Punchy opening question sentence")

        # Clamp score
        final_score = round(max(5.0, min(100.0, score)), 1)

        return HookScore(
            score=final_score,
            hook_type=hook_type,
            first_phrase=first_phrase,
            reasons=reasons or ["Standard conversational start"]
        )

