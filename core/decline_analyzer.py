from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Optional

import pandas as pd

from core.growth_detector import GROWTH_WINDOW_MONTHS
from core.strategy_models import StrategyBrief


def analyze_decline_drivers(
    channels_data: dict[str, dict],
    strategy_brief: Optional[StrategyBrief] = None,
    viral_outliers: Optional[dict[str, dict]] = None,
    evolution_insights: Optional[dict[str, dict]] = None,
) -> list[dict]:
    diagnostics = []
    viral_outliers = viral_outliers or {}
    evolution_insights = evolution_insights or {}

    for channel_id, payload in channels_data.items():
        growth = payload.get("growth", {})
        growth_ratio = growth.get("growth_ratio")
        if not growth.get("reliable"):
            continue
        if growth_ratio is None or growth_ratio >= 0.7:
            continue

        diagnosis = diagnose_channel_decline(
            channel_id=channel_id,
            info=payload.get("info", {}),
            videos_df=payload.get("videos", pd.DataFrame()),
            growth=growth,
            strategy_brief=strategy_brief,
            viral_outlier=viral_outliers.get(channel_id),
            evolution=evolution_insights.get(channel_id),
        )
        diagnostics.append(diagnosis)

    diagnostics.sort(key=lambda item: item.get("severity_score", 0), reverse=True)
    return diagnostics


def diagnose_channel_decline(
    channel_id: str,
    info: dict,
    videos_df: pd.DataFrame,
    growth: dict,
    strategy_brief: Optional[StrategyBrief] = None,
    viral_outlier: Optional[dict] = None,
    evolution: Optional[dict] = None,
) -> dict:
    if videos_df.empty or "published_at" not in videos_df.columns:
        return {
            "channel_id": channel_id,
            "channel_title": info.get("title", channel_id),
            "classification": "unclear",
            "classification_label": "无法判断",
            "summary": "缺少足够的视频时间序列，无法判断下滑原因。",
            "objective_factors": [],
            "strategy_factors": [],
            "severity_score": 0,
        }

    df = videos_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["published_at"]):
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df = df.dropna(subset=["published_at"]).copy()
    if df.empty:
        return {
            "channel_id": channel_id,
            "channel_title": info.get("title", channel_id),
            "classification": "unclear",
            "classification_label": "无法判断",
            "summary": "发布时间数据不足，无法判断下滑原因。",
            "objective_factors": [],
            "strategy_factors": [],
            "severity_score": 0,
        }

    if df["published_at"].dt.tz is None:
        df["published_at"] = df["published_at"].dt.tz_localize("UTC")
    else:
        df["published_at"] = df["published_at"].dt.tz_convert("UTC")

    recent, older = _split_recent_and_older(df)
    topic_terms = _brief_terms(strategy_brief)

    recent_alignment = _avg_alignment_score(recent, topic_terms)
    older_alignment = _avg_alignment_score(older, topic_terms)
    alignment_drop = older_alignment - recent_alignment

    recent_duration = float(recent.get("duration_minutes", pd.Series(dtype=float)).mean() or 0)
    older_duration = float(older.get("duration_minutes", pd.Series(dtype=float)).mean() or 0)
    duration_shift_pct = 0.0
    if older_duration > 0:
        duration_shift_pct = (recent_duration - older_duration) / older_duration

    recent_median = float(recent["view_count"].median()) if not recent.empty else 0.0
    older_median = float(older["view_count"].median()) if not older.empty else 0.0
    median_ratio = recent_median / older_median if older_median > 0 else 1.0

    recent_top_share = _top_share(recent)
    older_top_share = _top_share(older)

    objective_factors = []
    strategy_factors = []

    publish_change = float(growth.get("publish_frequency_change", 0.0) or 0.0)
    if publish_change <= -25:
        objective_factors.append(
            f"发布频率较前一窗口下降 {abs(publish_change):.0f}%，先看产能、团队节奏或选题供给是否收缩。"
        )

    if older_top_share >= 0.45 and median_ratio >= 0.8:
        objective_factors.append(
            "前一窗口的均值明显被少数爆款抬高，当前更像爆款回落后的基数修正，而不是全面内容失效。"
        )

    if viral_outlier and viral_outlier.get("has_outliers") and not viral_outlier.get("baseline_reliable", True):
        objective_factors.append(
            "频道历史里有强烈单爆款异常，增长判断容易被极端视频放大。"
        )

    if growth.get("engagement_trend") == "↘️ 下降":
        strategy_factors.append("近期互动率同步下降，说明不只是曝光变少，内容吸引力或讨论度也在变弱。")

    if alignment_drop >= 0.75:
        strategy_factors.append(
            f"近期标题与当前目标赛道的对齐度从 {older_alignment:.1f} 降到 {recent_alignment:.1f}，说明题材或包装开始偏离核心需求。"
        )

    if abs(duration_shift_pct) >= 0.35:
        strategy_factors.append(
            f"近期平均时长变化 {duration_shift_pct:+.0%}，形式变化过大，可能让原有受众预期失配。"
        )

    if evolution and evolution.get("trend") == "declining":
        strategy_factors.append(evolution.get("inflection", "近期内容演化信号偏弱。"))

    classification, classification_label = _classify_decline(objective_factors, strategy_factors)
    summary = _build_summary(classification)
    severity_score = _severity_score(growth, objective_factors, strategy_factors)

    return {
        "channel_id": channel_id,
        "channel_title": info.get("title", channel_id),
        "classification": classification,
        "classification_label": classification_label,
        "summary": summary,
        "objective_factors": objective_factors,
        "strategy_factors": strategy_factors,
        "recent_alignment": round(recent_alignment, 2),
        "older_alignment": round(older_alignment, 2),
        "recent_median_views": int(recent_median),
        "older_median_views": int(older_median),
        "median_ratio": round(median_ratio, 2),
        "recent_top_share": round(recent_top_share, 2),
        "older_top_share": round(older_top_share, 2),
        "duration_shift_pct": round(duration_shift_pct, 2),
        "severity_score": severity_score,
    }


def format_decline_diagnostics(diagnostics: list[dict]) -> str:
    if not diagnostics:
        return "当前样本中没有进入可靠下滑诊断范围的频道。"

    lines = []
    for item in diagnostics:
        lines.append(
            f"- {item['channel_title']} | 判定：{item['classification_label']} | {item['summary']}"
        )
        for reason in item.get("objective_factors", []):
            lines.append(f"  - 客观因素：{reason}")
        for reason in item.get("strategy_factors", []):
            lines.append(f"  - 策略因素：{reason}")
    return "\n".join(lines)


def _split_recent_and_older(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    now = datetime.now(timezone.utc)
    cutoff_recent = now - timedelta(days=GROWTH_WINDOW_MONTHS * 30)
    cutoff_older = cutoff_recent - timedelta(days=GROWTH_WINDOW_MONTHS * 30)
    recent = df[df["published_at"] >= cutoff_recent].copy()
    older = df[(df["published_at"] >= cutoff_older) & (df["published_at"] < cutoff_recent)].copy()
    return recent, older


def _brief_terms(strategy_brief: Optional[StrategyBrief]) -> set[str]:
    terms = set()
    if not strategy_brief:
        return terms

    values = []
    values.extend(strategy_brief.strategy_keywords)
    values.extend(strategy_brief.discovery_keywords)
    values.extend(strategy_brief.format_preferences)
    values.extend([strategy_brief.niche, strategy_brief.content_direction, strategy_brief.primary_goal])

    for value in values:
        for token in re.findall(r"[a-zA-Z0-9\-]+", str(value).lower()):
            if len(token) >= 3:
                terms.add(token)
    return terms


def _avg_alignment_score(df: pd.DataFrame, terms: set[str]) -> float:
    if df.empty or not terms or "title" not in df.columns:
        return 0.0

    def _score(title: str) -> int:
        title_lower = str(title).lower()
        return sum(1 for term in terms if term in title_lower)

    scores = df["title"].fillna("").apply(_score)
    return float(scores.mean()) if not scores.empty else 0.0


def _top_share(df: pd.DataFrame, top_n: int = 2) -> float:
    if df.empty:
        return 0.0
    total_views = float(df["view_count"].sum())
    if total_views <= 0:
        return 0.0
    return float(df.nlargest(top_n, "view_count")["view_count"].sum() / total_views)


def _classify_decline(objective_factors: list[str], strategy_factors: list[str]) -> tuple[str, str]:
    if objective_factors and not strategy_factors:
        return "objective", "更像客观回落"
    if strategy_factors and not objective_factors:
        return "strategy", "更像策略失效"
    if objective_factors and strategy_factors:
        return "mixed", "客观与策略混合"
    return "unclear", "证据不足"


def _build_summary(classification: str) -> str:
    if classification == "objective":
        return "当前回落更像样本基数、爆款退潮或发布节奏变化带来的客观修正。"
    if classification == "strategy":
        return "当前回落更像内容策略、包装对齐度或形式变化出了问题。"
    if classification == "mixed":
        return "当前回落同时受到外部基数回调和近期内容策略转弱的影响。"
    return "现有证据不足以把回落归因为单一原因。"


def _severity_score(growth: dict, objective_factors: list[str], strategy_factors: list[str]) -> int:
    growth_ratio = float(growth.get("growth_ratio") or 1.0)
    base = int(max(0, (1 - growth_ratio) * 100))
    return base + len(objective_factors) * 5 + len(strategy_factors) * 8