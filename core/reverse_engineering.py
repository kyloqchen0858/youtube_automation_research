from __future__ import annotations

from collections import Counter
import re
from typing import Any

import pandas as pd

from core.strategy_models import ContentDirection, ReverseEngineeringPlaybook, StrategyBrief


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "into", "how", "why", "what",
    "guide", "tips", "best", "video", "channel", "tool", "tools", "build", "using", "use",
}


def build_reverse_engineering_playbook(
    brief: StrategyBrief,
    radar_results: dict[str, Any] | None = None,
    transcript_insights: dict[str, Any] | None = None,
    top_videos_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    radar_results = radar_results or {}
    transcript_insights = transcript_insights or {}
    top_channels = radar_results.get("top_channels", []) or []
    top_videos = radar_results.get("top_videos", []) or []

    dominant_formats = _dominant_formats(top_videos)
    title_formulas = _winning_title_formulas(top_videos, top_videos_df)
    hook_formulas = _winning_hook_formulas(transcript_insights)
    topic_clusters = _winning_topic_clusters(top_videos, top_videos_df)
    archetype = _channel_archetype(brief, dominant_formats, top_channels)
    viewer_praise = _viewer_praise_patterns(brief, transcript_insights, dominant_formats)
    viewer_gaps = _viewer_gap_patterns(brief, transcript_insights, dominant_formats)
    copy_constraints = _copy_constraints(brief, dominant_formats)
    recommended_adaptations = _recommended_adaptations(brief, dominant_formats, hook_formulas)
    confidence_notes = _confidence_notes(radar_results, transcript_insights)

    return ReverseEngineeringPlaybook(
        channel_archetype=archetype,
        winning_topic_clusters=topic_clusters,
        winning_title_formulas=title_formulas,
        winning_hook_formulas=hook_formulas,
        dominant_formats=dominant_formats,
        viewer_praise_patterns=viewer_praise,
        viewer_gap_patterns=viewer_gaps,
        copy_constraints=copy_constraints,
        recommended_adaptations=recommended_adaptations,
        confidence_notes=confidence_notes,
    ).to_dict()


def _dominant_formats(top_videos: list[dict[str, Any]]) -> list[str]:
    counter = Counter(video.get("format_guess", "unknown") for video in top_videos if video.get("format_guess"))
    formats = [name for name, _ in counter.most_common(3) if name != "unknown"]
    return formats or ["unknown"]


def _winning_title_formulas(top_videos: list[dict[str, Any]], top_videos_df: pd.DataFrame | None) -> list[str]:
    titles = [video.get("title", "") for video in top_videos]
    if top_videos_df is not None and not top_videos_df.empty and "title" in top_videos_df.columns:
        titles.extend(top_videos_df["title"].astype(str).head(5).tolist())

    formulas = []
    if any(any(char.isdigit() for char in title) for title in titles):
        formulas.append("[Number] + concrete outcome + workflow/tool context")
    if any("how to" in title.lower() or "guide" in title.lower() for title in titles):
        formulas.append("How to + specific workflow outcome + low-friction promise")
    if any(any(token in title.lower() for token in ["i built", "i shipped", "week", "day"]) for title in titles):
        formulas.append("Progress narrative + concrete milestone + time box")
    if any(any(token in title.lower() for token in ["why", "stop", "don’t", "dont", "never"]) for title in titles):
        formulas.append("Belief challenge / warning + concrete consequence")
    return formulas[:4] or ["Specific problem + concrete result + low-ambiguity packaging"]


def _winning_hook_formulas(transcript_insights: dict[str, Any]) -> list[str]:
    hooks = transcript_insights.get("hook_patterns", []) or []
    formulas = []
    for item in hooks[:3]:
        label = item.get("label", "Hook")
        formulas.append(f"Lead with {label.lower()} in the first 10-20 seconds")
    return formulas or ["Open with the viewer problem before any backstory"]


def _winning_topic_clusters(top_videos: list[dict[str, Any]], top_videos_df: pd.DataFrame | None) -> list[str]:
    titles = [video.get("title", "") for video in top_videos]
    if top_videos_df is not None and not top_videos_df.empty and "title" in top_videos_df.columns:
        titles.extend(top_videos_df["title"].astype(str).head(8).tolist())

    token_counter: Counter[str] = Counter()
    for title in titles:
        tokens = re.findall(r"[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}", str(title).lower())
        for token in tokens:
            if token in STOPWORDS:
                continue
            token_counter[token] += 1

    return [token for token, _ in token_counter.most_common(5)]


def _channel_archetype(
    brief: StrategyBrief,
    dominant_formats: list[str],
    top_channels: list[dict[str, Any]],
) -> str:
    lead = top_channels[0] if top_channels else {}
    lead_name = lead.get("channel_title", "shortlisted channels")
    if brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        return f"{lead_name}: builder-led progress narrative with observable milestones"
    if brief.content_direction == ContentDirection.MIXED.value:
        return f"{lead_name}: hybrid operator channel mixing tactical tutorials with progress proof"
    if "tutorial" in dominant_formats or "demo" in dominant_formats:
        return f"{lead_name}: tactical tutorial channel built on transferable workflows"
    return f"{lead_name}: explainer-led operator channel with pragmatic packaging"


def _viewer_praise_patterns(
    brief: StrategyBrief,
    transcript_insights: dict[str, Any],
    dominant_formats: list[str],
) -> list[str]:
    praise = []
    if dominant_formats and dominant_formats[0] in {"tutorial", "demo"}:
        praise.append("Step-by-step demonstrations reduce ambiguity and make the content feel immediately usable")
    if dominant_formats and dominant_formats[0] in {"devlog", "progress_update"}:
        praise.append("Time-boxed progress framing creates narrative tension and credibility")
    if transcript_insights.get("structure_patterns"):
        praise.append("Clear structural framing improves retention because viewers know what is coming next")
    if brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        praise.append("Specific milestones and honest constraints are more believable than broad motivational claims")
    else:
        praise.append("Concrete workflow promises outperform vague inspiration in cold-start education content")
    return praise[:4]


def _viewer_gap_patterns(
    brief: StrategyBrief,
    transcript_insights: dict[str, Any],
    dominant_formats: list[str],
) -> list[str]:
    gaps = []
    if dominant_formats and dominant_formats[0] == "unknown":
        gaps.append("The public sample does not expose a dominant format yet, so format conclusions are still exploratory")
    if not transcript_insights.get("has_data"):
        gaps.append("Transcript coverage is limited, so hook and structure recommendations rely more on packaging proxies")
    if brief.content_direction == ContentDirection.AI_TOOL_TUTORIAL.value:
        gaps.append("Most competitors do not explain implementation constraints clearly enough for beginners")
    else:
        gaps.append("Many competitors show progress, but fewer explain the decision logic behind each build step")
    return gaps[:3]


def _copy_constraints(brief: StrategyBrief, dominant_formats: list[str]) -> list[str]:
    constraints = []
    team_model = brief.production_constraints.get("team_model", "solo")
    if team_model == "solo":
        constraints.append("Do not copy formats that require high-frequency cinematic editing or multi-person production")
    if brief.content_direction == ContentDirection.AI_TOOL_TUTORIAL.value:
        constraints.append("Avoid abstract thought-leadership packaging if the video does not demonstrate an actual workflow")
    if brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        constraints.append("Avoid pretending certainty; the format works better when tradeoffs and unknowns are visible")
    if dominant_formats and dominant_formats[0] == "tutorial":
        constraints.append("Screen-led tutorials still need a visible payoff in the first 15 seconds or they will feel generic")
    return constraints[:4]


def _recommended_adaptations(
    brief: StrategyBrief,
    dominant_formats: list[str],
    hook_formulas: list[str],
) -> list[str]:
    adaptations = []
    if brief.content_direction == ContentDirection.AI_TOOL_TUTORIAL.value:
        adaptations.append("Lead with the final output or end-state before showing setup steps")
        adaptations.append("Turn each shortlisted competitor theme into one workflow problem and one tutorial result")
    elif brief.content_direction == ContentDirection.BUILD_IN_PUBLIC.value:
        adaptations.append("Frame each video around a milestone, constraint, or decision rather than general productivity advice")
        adaptations.append("Use weekly or time-boxed progress framing to create continuity across episodes")
    else:
        adaptations.append("Alternate tutorial proof with narrative proof so the channel earns both trust and momentum")

    if hook_formulas:
        adaptations.append(hook_formulas[0])
    if dominant_formats and dominant_formats[0] in {"tutorial", "demo"}:
        adaptations.append("Prefer screen-led or artifact-led explanation over decorative animation unless it clarifies a hard concept")
    return adaptations[:5]


def _confidence_notes(radar_results: dict[str, Any], transcript_insights: dict[str, Any]) -> list[str]:
    notes = []
    top_channels = radar_results.get("top_channels", []) or []
    if len(top_channels) >= 3:
        notes.append("Radar shortlist is based on multiple ranked competitors, so channel-level direction is moderately reliable")
    elif top_channels:
        notes.append("Radar shortlist exists but is thin, so treat channel selection as provisional")
    else:
        notes.append("No radar shortlist was available, so this playbook is exploratory")

    if transcript_insights.get("has_data"):
        coverage = transcript_insights.get("coverage", {})
        notes.append(
            f"Transcript evidence covers {coverage.get('analyzed_videos', 0)} videos across {coverage.get('analyzed_channels', 0)} channels"
        )
    else:
        notes.append("Transcript evidence is missing, so hook and structure recommendations rely on title/format proxies")
    return notes[:3]