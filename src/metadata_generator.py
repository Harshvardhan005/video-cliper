"""
AI Metadata & Social Media Optimization Module
Generates viral titles, descriptions, hashtags, keywords, and platform-specific
copy for YouTube Shorts, Instagram Reels, and TikTok.
"""

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlatformMetadata:
    title: str
    description: str
    hashtags: List[str]
    formatted_post: str


@dataclass
class ClipMetadata:
    clip_id: int
    title: str
    summary: str
    thumbnail_hook: str
    source_timestamp_start: float
    source_timestamp_end: float
    duration: float
    retention_score: float
    keywords: List[str]
    youtube_shorts: PlatformMetadata
    instagram_reels: PlatformMetadata
    tiktok: PlatformMetadata

    def to_dict(self) -> Dict:
        return asdict(self)

    def save_json(self, output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class MetadataGenerator:
    """Creates platform-optimized viral social metadata."""

    COMMON_HASHTAGS = ["#shorts", "#viral", "#trending", "#fyp", "#podcast", "#mindset", "#growth"]

    def generate_metadata(
        self,
        clip_id: int,
        clip_text: str,
        start_time: float,
        end_time: float,
        duration: float,
        retention_score: float,
        hook_phrase: str
    ) -> ClipMetadata:
        """Synthesizes high-performing social metadata from clip transcript and hook."""

        # 1. Clean title derivation
        words = clip_text.strip().split()
        clean_hook = hook_phrase.strip().capitalize()
        if len(clean_hook) < 15 and len(words) >= 6:
            clean_hook = " ".join(words[:6]).capitalize()

        viral_title = f"{clean_hook} 🤯" if not clean_hook.endswith(("?", "!")) else clean_hook
        thumbnail_hook = " ".join(clean_hook.split()[:4]).upper()

        # 2. Extract keywords
        clean_words = re.findall(r"\b[a-zA-Z]{4,15}\b", clip_text.lower())
        stop_words = {"this", "that", "there", "their", "with", "from", "about", "what", "which", "when", "just"}
        keywords = list(dict.fromkeys([w for w in clean_words if w not in stop_words]))[:8]

        # 3. Dynamic hashtags
        tags = [f"#{k}" for k in keywords[:4]]
        yt_tags = ["#Shorts", "#viral", "#trending"] + tags
        reels_tags = ["#reels", "#reelsinstagram", "#explorepage"] + tags
        tiktok_tags = ["#fyp", "#foryou", "#tiktokviral"] + tags

        # 4. Summary
        summary = clip_text[:140] + ("..." if len(clip_text) > 140 else "")

        # 5. YouTube Shorts copy
        yt_post = f"{viral_title}\n\n{summary}\n\n{' '.join(yt_tags[:5])}"
        yt_meta = PlatformMetadata(
            title=viral_title[:95],
            description=yt_post,
            hashtags=yt_tags,
            formatted_post=yt_post
        )

        # 6. Instagram Reels copy
        ig_post = f"{viral_title}\n.\n{summary}\n.\nDrop your thoughts below 👇\n.\n{' '.join(reels_tags[:7])}"
        ig_meta = PlatformMetadata(
            title=viral_title,
            description=summary,
            hashtags=reels_tags,
            formatted_post=ig_post
        )

        # 7. TikTok copy
        tt_post = f"{viral_title} 👀 wait for the end! {' '.join(tiktok_tags[:6])}"
        tt_meta = PlatformMetadata(
            title=viral_title,
            description=summary,
            hashtags=tiktok_tags,
            formatted_post=tt_post
        )

        return ClipMetadata(
            clip_id=clip_id,
            title=viral_title,
            summary=summary,
            thumbnail_hook=thumbnail_hook,
            source_timestamp_start=start_time,
            source_timestamp_end=end_time,
            duration=round(duration, 2),
            retention_score=retention_score,
            keywords=keywords,
            youtube_shorts=yt_meta,
            instagram_reels=ig_meta,
            tiktok=tt_meta
        )

