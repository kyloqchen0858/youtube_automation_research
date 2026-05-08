from __future__ import annotations

from datetime import timezone
import math
import re
from typing import Any

import pandas as pd

from core.strategy_models import (
    ChannelEvidence,
    ContentDirection,
    RadarScoreCard,
    StrategyBrief,
    VideoEvidence,
)


AI_TOOL_HINTS = {
    "ai", "tool", "tools", "automation", "workflow", "tutorial", "guide", "how", "setup",
    "walkthrough", "demo", "prompt", "agent", "app", "software", "extension",
}
BUILD_IN_PUBLIC_HINTS = {
    "build", "building", "public", "launch", "launched", "ship", "shipped", "indie", "startup",
    "founder", "devlog", "week", "progress", "roadmap", "saas", "mrr", "revenue",
}


def build_competitor_radar(
    channels_data: dict[str, dict[str, Any]],
    brief: StrategyBrief,
    max_channels: int = 5,
    max_videos: int = 10,
) -> dict[str, Any]:
    channel_evidence: list[ChannelEvidence] = []
    scorecards: list[RadarScoreCard] = []
    video_evidence: list[VideoEvidence] = []
    keyword_bank = _build_keyword_bank(brief)

    for channel_id, payload in channels_data.items():
        info = payload.get("info", {})
        videos_df = payload.get("videos", pd.DataFrame()).copy()
        growth = payload.get("growth", {})
        if videos_df.empty:
            continue

        if "published_at" in videos_df.columns:
            videos_df = videos_df.sort_values("published_at")

        channel_title = info.get("title", channel_id)
        subscriber_count = int(info.get("subscriber_count", 0) or 0)
        avg_views = float(videos_df["view_count"].mean()) if "view_count" in videos_df.columns else 0.0
        recent_views = float(videos_df.tail(min(10, len(videos_df)))["view_count"].mean()) if "view_count" in videos_df.columns else avg_views
        max_views = int(videos_df["view_count"].max()) if "view_count" in videos_df.columns else 0
        avg_views_to_subs_ratio = recent_views / max(subscriber_count, 1)
        keyword_relevance = _keyword_relevance(channel_title, videos_df, keyword_bank)
        format_fit = _format_fit(videos_df, brief)
        execution_match = _execution_match(videos_df, brief)
        freshness_days = _freshness_days(videos_df)
        growth_ratio = float(growth.get("growth_ratio") or 0.0)
        reliability_score = int(growth.get("reliability_score") or 0)

        scorecard = _score_channel(
            brief=brief,
            channel_id=channel_id,
            subscriber_count=subscriber_count,
            avg_views_to_subs_ratio=avg_views_to_subs_ratio,
            growth_ratio=growth_ratio,
            reliability_score=reliability_score,
            keyword_relevance=keyword_relevance,
            format_fit=format_fit,
            execution_match=execution_match,
            freshness_days=freshness_days,
        )
        scorecards.append(scorecard)

        channel_evidence.append(
            ChannelEvidence(
                channel_id=channel_id,
                channel_title=channel_title,
                subscriber_count=subscriber_count,
                total_view_count=int(info.get("view_count", 0) or 0),
                avg_recent_views=int(recent_views),
                max_views=max_views,
                avg_views_to_subs_ratio=round(avg_views_to_subs_ratio, 2),
                growth_ratio=round(growth_ratio, 2),
                reliability_level=growth.get("reliability_level", "red"),
                reliability_score=reliability_score,
                freshness_days=freshness_days,
                keyword_relevance=round(keyword_relevance, 2),
                format_fit=round(format_fit, 2),
                execution_match=round(execution_match, 2),
                radar_score=round(scorecard.total_score, 2),
                score_reasons=_channel_score_reasons(
                    avg_views_to_subs_ratio,
                    growth_ratio,
                    reliability_score,
                    keyword_relevance,
                    format_fit,
                    freshness_days,
                ),
            )
        )

        video_evidence.extend(
            _collect_video_evidence(
                videos_df=videos_df,
                brief=brief,
                channel_id=channel_id,
                subscriber_count=subscriber_count,
                avg_views=avg_views,
                keyword_bank=keyword_bank,
            )
        )

    ranked_channels = sorted(channel_evidence, key=lambda item: item.radar_score, reverse=True)
    ranked_videos = sorted(video_evidence, key=lambda item: item.breakout_score, reverse=True)
    channel_lookup = {item.channel_id: item for item in ranked_channels}

    return {
        "brief": brief.to_dict(),
        "top_channels": [item.to_dict() for item in ranked_channels[:max_channels]],
        "top_videos": [item.to_dict() for item in ranked_videos[:max_videos]],
        "channel_scorecards": [card.to_dict() for card in sorted(scorecards, key=lambda item: item.total_score, reverse=True)],
        "shortlist_channel_ids": [item.channel_id for item in ranked_channels[:max_channels]],
        "summary": _build_summary(ranked_channels[:max_channels], ranked_videos[:max_videos], brief, channel_lookup),
    }


def _build_keyword_bank(brief: StrategyBrief) -> set[str]:
    tokens: set[str] = set()
    for raw in [brief.niche, *brief.strategy_keywords, *brief.discovery_keywords]:
        tokens.update(_tokenize(raw))

    if brief.content_direction == ContentDirection.AI_TOOL_TUTORIAL.value:
        tokens.update(AI_TOOL_HINTS)
    elif brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        tokens.update(BUILD_IN_PUBLIC_HINTS)
    else:
        tokens.update(AI_TOOL_HINTS)
        tokens.update(BUILD_IN_PUBLIC_HINTS)
    return tokens


def _collect_video_evidence(
    videos_df: pd.DataFrame,
    brief: StrategyBrief,
    channel_id: str,
    subscriber_count: int,
    avg_views: float,
    keyword_bank: set[str],
) -> list[VideoEvidence]:
    evidence_rows: list[VideoEvidence] = []
    if videos_df.empty:
        return evidence_rows

    sample_df = videos_df.nlargest(min(8, len(videos_df)), "view_count")
    for _, row in sample_df.iterrows():
        title = str(row.get("title", ""))
        view_count = int(row.get("view_count", 0) or 0)
        baseline_lift = view_count / max(avg_views, 1.0)
        views_to_subs_ratio = view_count / max(subscriber_count, 1)
        keyword_relevance = _keyword_match_ratio(_tokenize(title), keyword_bank)
        format_guess = _guess_format(title)
        engagement_rate = float(row.get("engagement_rate", 0.0) or 0.0)
        breakout_score = _score_video(
            baseline_lift=baseline_lift,
            views_to_subs_ratio=views_to_subs_ratio,
            engagement_rate=engagement_rate,
            keyword_relevance=keyword_relevance,
            brief=brief,
            format_guess=format_guess,
        )
        evidence_rows.append(
            VideoEvidence(
                video_id=str(row.get("video_id", "")),
                channel_id=channel_id,
                title=title,
                published_at=str(row.get("published_at", "")),
                view_count=view_count,
                engagement_rate=round(engagement_rate, 4),
                baseline_lift=round(baseline_lift, 2),
                views_to_subs_ratio=round(views_to_subs_ratio, 2),
                keyword_relevance=round(keyword_relevance, 2),
                format_guess=format_guess,
                breakout_score=round(breakout_score, 2),
                score_reasons=_video_score_reasons(baseline_lift, views_to_subs_ratio, keyword_relevance, engagement_rate),
            )
        )
    return evidence_rows


def _score_channel(
    brief: StrategyBrief,
    channel_id: str,
    subscriber_count: int,
    avg_views_to_subs_ratio: float,
    growth_ratio: float,
    reliability_score: int,
    keyword_relevance: float,
    format_fit: float,
    execution_match: float,
    freshness_days: int,
) -> RadarScoreCard:
    blackhorse_score = min(avg_views_to_subs_ratio * 40, 100)
    if subscriber_count > 300_000:
        blackhorse_score *= 0.65
    elif subscriber_count > 100_000:
        blackhorse_score *= 0.8

    growth_quality_score = min(growth_ratio * 18, 100) * (max(reliability_score, 25) / 100)
    relevance_score = keyword_relevance * 100
    format_fit_score = format_fit * 100
    execution_match_score = execution_match * 100
    freshness_score = max(0.0, 100 - min(freshness_days, 120) * 0.8)

    weights = _channel_weights(brief)
    total_score = (
        blackhorse_score * weights["blackhorse"] +
        growth_quality_score * weights["growth"] +
        relevance_score * weights["relevance"] +
        format_fit_score * weights["format_fit"] +
        execution_match_score * weights["execution"] +
        freshness_score * weights["freshness"]
    )

    return RadarScoreCard(
        channel_id=channel_id,
        blackhorse_score=round(blackhorse_score, 2),
        growth_quality_score=round(growth_quality_score, 2),
        relevance_score=round(relevance_score, 2),
        format_fit_score=round(format_fit_score, 2),
        execution_match_score=round(execution_match_score, 2),
        freshness_score=round(freshness_score, 2),
        total_score=round(total_score, 2),
    )


def _channel_weights(brief: StrategyBrief) -> dict[str, float]:
    if brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        return {
            "blackhorse": 0.22,
            "growth": 0.18,
            "relevance": 0.2,
            "format_fit": 0.15,
            "execution": 0.1,
            "freshness": 0.15,
        }
    if brief.content_direction == ContentDirection.MIXED.value:
        return {
            "blackhorse": 0.24,
            "growth": 0.2,
            "relevance": 0.2,
            "format_fit": 0.14,
            "execution": 0.1,
            "freshness": 0.12,
        }
    return {
        "blackhorse": 0.24,
        "growth": 0.22,
        "relevance": 0.2,
        "format_fit": 0.18,
        "execution": 0.08,
        "freshness": 0.08,
    }


def _score_video(
    baseline_lift: float,
    views_to_subs_ratio: float,
    engagement_rate: float,
    keyword_relevance: float,
    brief: StrategyBrief,
    format_guess: str,
) -> float:
    format_bonus = 1.0
    if brief.content_direction == ContentDirection.AI_TOOL_TUTORIAL.value and format_guess in {"tutorial", "demo"}:
        format_bonus = 1.1
    if brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value and format_guess in {"devlog", "progress_update"}:
        format_bonus = 1.1

    raw_score = (
        min(baseline_lift * 18, 100) * 0.35 +
        min(views_to_subs_ratio * 28, 100) * 0.35 +
        min(engagement_rate * 2000, 100) * 0.15 +
        (keyword_relevance * 100) * 0.15
    )
    return raw_score * format_bonus


def _keyword_relevance(channel_title: str, videos_df: pd.DataFrame, keyword_bank: set[str]) -> float:
    title_tokens = set(_tokenize(channel_title))
    top_titles = " ".join(videos_df["title"].head(min(10, len(videos_df))).astype(str).tolist()) if "title" in videos_df.columns else ""
    title_tokens.update(_tokenize(top_titles))
    return _keyword_match_ratio(title_tokens, keyword_bank)


def _keyword_match_ratio(tokens: set[str], keyword_bank: set[str]) -> float:
    if not tokens or not keyword_bank:
        return 0.0
    overlap = tokens & keyword_bank
    return min(len(overlap) / max(min(len(keyword_bank), 12), 1), 1.0)


def _format_fit(videos_df: pd.DataFrame, brief: StrategyBrief) -> float:
    if videos_df.empty or "title" not in videos_df.columns:
        return 0.0

    scored_titles = 0
    matched_titles = 0
    for title in videos_df["title"].head(min(15, len(videos_df))).astype(str):
        format_guess = _guess_format(title)
        scored_titles += 1
        if brief.content_direction == ContentDirection.AI_TOOL_TUTORIAL.value and format_guess in {"tutorial", "demo", "case_study"}:
            matched_titles += 1
        elif brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value and format_guess in {"devlog", "progress_update", "case_study"}:
            matched_titles += 1
        elif brief.content_direction == ContentDirection.MIXED.value and format_guess != "unknown":
            matched_titles += 1

    if scored_titles == 0:
        return 0.0
    return matched_titles / scored_titles


def _execution_match(videos_df: pd.DataFrame, brief: StrategyBrief) -> float:
    if videos_df.empty:
        return 0.0

    avg_duration = float(videos_df.get("duration_minutes", pd.Series(dtype=float)).fillna(0).mean()) if "duration_minutes" in videos_df.columns else 0.0
    duration_score = 1.0
    if avg_duration >= 18:
        duration_score = 0.6
    elif avg_duration >= 12:
        duration_score = 0.8

    if brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        return round((duration_score * 0.6) + 0.4, 2)
    return round((duration_score * 0.7) + (_format_fit(videos_df, brief) * 0.3), 2)


def _freshness_days(videos_df: pd.DataFrame) -> int:
    if "published_at" not in videos_df.columns or videos_df.empty:
        return 9999
    latest = pd.to_datetime(videos_df["published_at"], errors="coerce").dropna().max()
    if pd.isna(latest):
        return 9999
    if latest.tzinfo is None:
        latest = latest.tz_localize(timezone.utc)
    else:
        latest = latest.tz_convert(timezone.utc)
    now = pd.Timestamp.now(tz=timezone.utc)
    return max(int((now - latest).days), 0)


def _channel_score_reasons(
    avg_views_to_subs_ratio: float,
    growth_ratio: float,
    reliability_score: int,
    keyword_relevance: float,
    format_fit: float,
    freshness_days: int,
) -> list[str]:
    reasons = []
    if avg_views_to_subs_ratio >= 0.3:
        reasons.append(f"High views/subs ratio ({avg_views_to_subs_ratio:.2f})")
    if growth_ratio >= 1.5:
        reasons.append(f"Recent growth ratio {growth_ratio:.2f}x")
    if reliability_score >= 70:
        reasons.append(f"Reliable growth score {reliability_score}")
    if keyword_relevance >= 0.2:
        reasons.append("Strong topical relevance to the active brief")
    if format_fit >= 0.5:
        reasons.append("Format pattern aligns with the chosen content direction")
    if freshness_days <= 30:
        reasons.append("Recently active channel")
    return reasons[:4]


def _video_score_reasons(
    baseline_lift: float,
    views_to_subs_ratio: float,
    keyword_relevance: float,
    engagement_rate: float,
) -> list[str]:
    reasons = []
    if baseline_lift >= 1.8:
        reasons.append(f"Lifted {baseline_lift:.2f}x above channel baseline")
    if views_to_subs_ratio >= 0.5:
        reasons.append(f"High views/subs ratio at video level ({views_to_subs_ratio:.2f})")
    if keyword_relevance >= 0.2:
        reasons.append("Strong match with brief keywords")
    if engagement_rate >= 0.04:
        reasons.append(f"Healthy engagement rate ({engagement_rate:.2%})")
    return reasons[:4]


def _build_summary(
    top_channels: list[ChannelEvidence],
    top_videos: list[VideoEvidence],
    brief: StrategyBrief,
    channel_lookup: dict[str, ChannelEvidence],
) -> dict[str, Any]:
    lead_channel = top_channels[0] if top_channels else None
    lead_video = top_videos[0] if top_videos else None

    return {
        "content_direction": brief.content_direction,
        "primary_goal": brief.primary_goal,
        "lead_channel": lead_channel.to_dict() if lead_channel else None,
        "lead_video": lead_video.to_dict() if lead_video else None,
        "why_it_matters": _summary_reason(lead_channel, lead_video),
        "shortlist_titles": [item.channel_title for item in top_channels],
        "video_channel_titles": [channel_lookup.get(item.channel_id).channel_title for item in top_videos if item.channel_id in channel_lookup],
    }


def _summary_reason(lead_channel: ChannelEvidence | None, lead_video: VideoEvidence | None) -> str:
    if not lead_channel:
        return "No ranked competitors yet."
    if not lead_video:
        return (
            f"{lead_channel.channel_title} leads because it combines breakout efficiency "
            f"({lead_channel.avg_views_to_subs_ratio:.2f} views/sub) with a radar score of {lead_channel.radar_score:.2f}."
        )
    return (
        f"{lead_channel.channel_title} leads the shortlist, and the breakout reference video "
        f"'{lead_video.title}' is scoring {lead_video.breakout_score:.2f} with {lead_video.baseline_lift:.2f}x baseline lift."
    )


def _guess_format(title: str) -> str:
    low = title.lower()
    if any(token in low for token in ["tutorial", "how to", "guide", "walkthrough", "setup"]):
        return "tutorial"
    if any(token in low for token in ["demo", "example", "use case", "case study"]):
        return "demo"
    if any(token in low for token in ["building", "build", "ship", "launched", "week", "day ", "devlog"]):
        return "devlog"
    if any(token in low for token in ["update", "progress", "roadmap", "lessons learned"]):
        return "progress_update"
    return "unknown"


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z]{2,}|[\u4e00-\u9fff]{2,}", str(text).lower())
        if token.strip()
    }