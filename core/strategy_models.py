from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, MutableMapping


class ContentDirection(str, Enum):
    AI_TOOL_TUTORIAL = "ai_tool_tutorial"
    BUILD_IN_PUBLIC = "build_in_public"
    MIXED = "mixed_strategy"


class CreatorStage(str, Enum):
    COLD_START = "cold_start"
    GROWTH = "growth"
    MONETIZATION = "monetization"
    PLATEAU = "plateau"


class PrimaryGoal(str, Enum):
    BREAKOUT_GROWTH = "breakout_growth"
    SUBSCRIBER_CONVERSION = "subscriber_conversion"
    HIGH_RETENTION_LONGFORM = "high_retention_longform"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generated_brief_id() -> str:
    return datetime.now(timezone.utc).strftime("brief_%Y%m%d_%H%M%S")


def _clean_string_list(values: Any) -> list[str]:
    if not values:
        return []

    if isinstance(values, str):
        values = values.splitlines()

    cleaned = []
    for value in values:
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


@dataclass
class StrategyBrief:
    brief_id: str = field(default_factory=_generated_brief_id)
    created_at: str = field(default_factory=_utc_now_iso)
    content_direction: str = ContentDirection.AI_TOOL_TUTORIAL.value
    creator_stage: str = CreatorStage.COLD_START.value
    primary_goal: str = PrimaryGoal.BREAKOUT_GROWTH.value
    workflow_mode: str = "analysis_quality"
    output_language: str = "zh"
    delivery_mode: str = "single_report"
    niche: str = ""
    strategy_keywords: list[str] = field(default_factory=list)
    discovery_keywords: list[str] = field(default_factory=list)
    format_preferences: list[str] = field(default_factory=list)
    production_constraints: dict[str, Any] = field(default_factory=dict)
    channel_context: dict[str, Any] = field(default_factory=dict)
    success_definition: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "StrategyBrief":
        if not payload:
            return cls()

        data = dict(payload)
        data["strategy_keywords"] = _clean_string_list(data.get("strategy_keywords", []))
        data["discovery_keywords"] = _clean_string_list(data.get("discovery_keywords", []))
        data["format_preferences"] = _clean_string_list(data.get("format_preferences", []))
        data["production_constraints"] = dict(data.get("production_constraints") or {})
        data["channel_context"] = dict(data.get("channel_context") or {})
        data["success_definition"] = dict(data.get("success_definition") or {})
        return cls(**data)


@dataclass
class ChannelEvidence:
    channel_id: str
    channel_title: str
    subscriber_count: int = 0
    total_view_count: int = 0
    avg_recent_views: int = 0
    max_views: int = 0
    avg_views_to_subs_ratio: float = 0.0
    growth_ratio: float = 0.0
    reliability_level: str = "red"
    reliability_score: int = 0
    freshness_days: int = 9999
    keyword_relevance: float = 0.0
    format_fit: float = 0.0
    execution_match: float = 0.0
    radar_score: float = 0.0
    score_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoEvidence:
    video_id: str
    channel_id: str
    title: str
    published_at: str = ""
    view_count: int = 0
    engagement_rate: float = 0.0
    baseline_lift: float = 0.0
    views_to_subs_ratio: float = 0.0
    keyword_relevance: float = 0.0
    format_guess: str = "unknown"
    breakout_score: float = 0.0
    score_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RadarScoreCard:
    channel_id: str
    blackhorse_score: float = 0.0
    growth_quality_score: float = 0.0
    relevance_score: float = 0.0
    format_fit_score: float = 0.0
    execution_match_score: float = 0.0
    freshness_score: float = 0.0
    total_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationEvidence:
    recommendation_id: str
    recommendation_type: str
    supporting_channels: list[str] = field(default_factory=list)
    supporting_videos: list[str] = field(default_factory=list)
    deterministic_signals: list[str] = field(default_factory=list)
    llm_synthesis_summary: str = ""
    confidence_grade: str = "exploratory"
    why_this_matters: str = ""
    when_not_to_use: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReverseEngineeringPlaybook:
    channel_archetype: str = ""
    winning_topic_clusters: list[str] = field(default_factory=list)
    winning_title_formulas: list[str] = field(default_factory=list)
    winning_hook_formulas: list[str] = field(default_factory=list)
    dominant_formats: list[str] = field(default_factory=list)
    viewer_praise_patterns: list[str] = field(default_factory=list)
    viewer_gap_patterns: list[str] = field(default_factory=list)
    copy_constraints: list[str] = field(default_factory=list)
    recommended_adaptations: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyCheckpoint:
    phase: str
    target: str
    duration: str
    actions: list[str] = field(default_factory=list)
    kpi: str = ""
    decision_rule: str = ""
    fallback_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyPlan:
    north_star_goal: str
    estimated_timeline: str
    key_metrics: dict[str, Any] = field(default_factory=dict)
    milestones: list[dict[str, Any]] = field(default_factory=list)
    checkpoint_rules: list[dict[str, str]] = field(default_factory=list)
    weekly_operating_rules: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)
    recommended_formats: list[str] = field(default_factory=list)
    strategy_source_summary: dict[str, Any] = field(default_factory=dict)
    niche_insights: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_strategy_brief(session_state: Mapping[str, Any], niche_override: str | None = None) -> StrategyBrief:
    stored = session_state.get("strategy_brief") or {}
    payload = {
        "brief_id": stored.get("brief_id", _generated_brief_id()),
        "created_at": stored.get("created_at", _utc_now_iso()),
        "content_direction": session_state.get("content_direction", ContentDirection.AI_TOOL_TUTORIAL.value),
        "creator_stage": session_state.get("creator_stage", CreatorStage.COLD_START.value),
        "primary_goal": session_state.get("primary_goal", PrimaryGoal.BREAKOUT_GROWTH.value),
        "workflow_mode": session_state.get("workflow_mode", "analysis_quality"),
        "output_language": session_state.get("output_language", "zh"),
        "delivery_mode": session_state.get("delivery_mode", "single_report"),
        "niche": niche_override if niche_override is not None else session_state.get("niche", ""),
        "strategy_keywords": _clean_string_list(session_state.get("strategy_keywords", [])),
        "discovery_keywords": _clean_string_list(session_state.get("keywords", [])),
        "format_preferences": _clean_string_list(session_state.get("format_preferences", [])),
        "production_constraints": dict(session_state.get("production_constraints") or {}),
        "channel_context": dict(session_state.get("channel_context") or {}),
        "success_definition": dict(session_state.get("success_definition") or {}),
    }
    return StrategyBrief.from_dict(payload)


def get_strategy_brief(session_state: Mapping[str, Any], niche_override: str | None = None) -> StrategyBrief:
    stored = session_state.get("strategy_brief")
    if stored:
        payload = dict(stored)
        payload["content_direction"] = session_state.get("content_direction", payload.get("content_direction", ContentDirection.AI_TOOL_TUTORIAL.value))
        payload["creator_stage"] = session_state.get("creator_stage", payload.get("creator_stage", CreatorStage.COLD_START.value))
        payload["primary_goal"] = session_state.get("primary_goal", payload.get("primary_goal", PrimaryGoal.BREAKOUT_GROWTH.value))
        payload["workflow_mode"] = session_state.get("workflow_mode", payload.get("workflow_mode", "analysis_quality"))
        payload["output_language"] = session_state.get("output_language", payload.get("output_language", "zh"))
        payload["delivery_mode"] = session_state.get("delivery_mode", payload.get("delivery_mode", "single_report"))
        payload["niche"] = niche_override if niche_override is not None else session_state.get("niche", payload.get("niche", ""))
        payload["strategy_keywords"] = _clean_string_list(session_state.get("strategy_keywords", payload.get("strategy_keywords", [])))
        payload["discovery_keywords"] = _clean_string_list(session_state.get("keywords", payload.get("discovery_keywords", [])))
        payload["format_preferences"] = _clean_string_list(session_state.get("format_preferences", payload.get("format_preferences", [])))
        payload["production_constraints"] = dict(session_state.get("production_constraints") or payload.get("production_constraints") or {})
        payload["channel_context"] = dict(session_state.get("channel_context") or payload.get("channel_context") or {})
        payload["success_definition"] = dict(session_state.get("success_definition") or payload.get("success_definition") or {})
        return StrategyBrief.from_dict(payload)
    return build_strategy_brief(session_state, niche_override=niche_override)


def sync_strategy_brief(session_state: MutableMapping[str, Any], brief: StrategyBrief) -> StrategyBrief:
    session_state["strategy_brief"] = brief.to_dict()
    session_state["workflow_mode"] = brief.workflow_mode
    session_state["creator_stage"] = brief.creator_stage
    session_state["output_language"] = brief.output_language
    session_state["delivery_mode"] = brief.delivery_mode
    session_state["strategy_keywords"] = list(brief.strategy_keywords)
    session_state["keywords"] = list(brief.discovery_keywords)
    session_state["niche"] = brief.niche
    session_state["content_direction"] = brief.content_direction
    session_state["primary_goal"] = brief.primary_goal
    session_state["format_preferences"] = list(brief.format_preferences)
    session_state["production_constraints"] = dict(brief.production_constraints)
    session_state["channel_context"] = dict(brief.channel_context)
    session_state["success_definition"] = dict(brief.success_definition)
    return brief