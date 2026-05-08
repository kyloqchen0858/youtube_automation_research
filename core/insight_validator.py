"""
Insight Validator — 数据可信度与策略一致性校验

v6 目标：
1. 输出可靠性摘要（可靠频道占比、分级分布）
2. 校验时长建议与高增长频道证据是否冲突
"""

import re
from typing import Optional

import pandas as pd


def summarize_reliability(channels_data: dict) -> dict:
    """汇总频道数据可靠性分布。"""
    total = len(channels_data)
    if total == 0:
        return {
            "total_channels": 0,
            "reliable_channels": 0,
            "reliable_ratio": 0.0,
            "average_score": 0,
            "levels": {"gold": 0, "silver": 0, "bronze": 0, "red": 0},
        }

    levels = {"gold": 0, "silver": 0, "bronze": 0, "red": 0}
    scores = []

    for _, payload in channels_data.items():
        growth = payload.get("growth", {})
        level = growth.get("reliability_level")
        if level not in levels:
            level = "silver" if growth.get("reliable") else "red"
        levels[level] += 1

        score = growth.get("reliability_score", 0)
        try:
            scores.append(float(score))
        except Exception:
            scores.append(0.0)

    reliable_channels = levels["gold"] + levels["silver"]
    reliable_ratio = reliable_channels / total if total else 0.0
    avg_score = int(sum(scores) / len(scores)) if scores else 0

    return {
        "total_channels": total,
        "reliable_channels": reliable_channels,
        "reliable_ratio": round(reliable_ratio, 2),
        "average_score": avg_score,
        "levels": levels,
    }


def validate_duration_recommendation(duration_analysis: dict, channels_data: dict) -> dict:
    """
    校验最佳时长建议是否与“可靠且增长频道”的实际时长冲突。

    冲突判定（简化）：
    - 使用 best_range 的中点作为推荐时长
    - 计算 reliable 且 growth_ratio>=1.5 频道的平均时长
    - 相对偏差 >= 60% 判定为冲突
    """
    best_range = duration_analysis.get("best_range", "N/A")
    range_mid = _extract_range_midpoint(best_range)

    reliable_durations = []
    fast_growth_durations = []

    for _, payload in channels_data.items():
        growth = payload.get("growth", {})
        videos_df = payload.get("videos", pd.DataFrame())
        if videos_df.empty or "duration_minutes" not in videos_df.columns:
            continue

        ch_avg_duration = float(videos_df["duration_minutes"].mean())
        if growth.get("reliable"):
            reliable_durations.append(ch_avg_duration)

            ratio = growth.get("growth_ratio", 0) or 0
            if ratio >= 1.5:
                fast_growth_durations.append(ch_avg_duration)

    total_channels = len(channels_data)
    reliable_count = len(reliable_durations)

    if range_mid is None or reliable_count == 0 or len(fast_growth_durations) == 0:
        return {
            "has_conflict": False,
            "confidence": 0.35 if reliable_count == 0 else 0.55,
            "best_range": best_range,
            "recommended_range": best_range,
            "fast_growth_avg_duration": None,
            "issues": [],
            "reliable_channel_count": reliable_count,
            "total_channels": total_channels,
        }

    fast_growth_avg = float(sum(fast_growth_durations) / len(fast_growth_durations))
    delta_ratio = abs(fast_growth_avg - range_mid) / max(range_mid, 1.0)
    has_conflict = delta_ratio >= 0.6

    issues = []
    recommended_range = best_range
    if has_conflict:
        recommended_range = _duration_bucket(fast_growth_avg)
        issues.append(
            (
                f"最佳时长建议 {best_range} 与高增长频道平均时长 "
                f"{fast_growth_avg:.1f}m 差异较大，建议优先测试 {recommended_range}。"
            )
        )

    coverage = reliable_count / max(total_channels, 1)
    sample_factor = min(1.0, len(fast_growth_durations) / 5)
    confidence = round(min(0.98, 0.45 + 0.35 * coverage + 0.2 * sample_factor), 2)

    return {
        "has_conflict": has_conflict,
        "confidence": confidence,
        "best_range": best_range,
        "recommended_range": recommended_range,
        "fast_growth_avg_duration": round(fast_growth_avg, 1),
        "issues": issues,
        "reliable_channel_count": reliable_count,
        "total_channels": total_channels,
    }


def _extract_range_midpoint(label: str) -> Optional[float]:
    if not label or label == "N/A":
        return None

    m = re.search(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)", str(label))
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2

    m_plus = re.search(r"(\d+(?:\.\d+)?)\s*\+", str(label))
    if m_plus:
        return float(m_plus.group(1))

    m_single = re.search(r"(\d+(?:\.\d+)?)", str(label))
    if m_single:
        return float(m_single.group(1))

    return None


def _duration_bucket(minutes: float) -> str:
    if minutes < 3:
        return "0-3m"
    if minutes < 5:
        return "3-5m"
    if minutes < 10:
        return "5-10m"
    if minutes < 15:
        return "10-15m"
    if minutes < 20:
        return "15-20m"
    if minutes < 30:
        return "20-30m"
    if minutes < 60:
        return "30-60m"
    return "60m+"
