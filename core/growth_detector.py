"""
Growth Detector — 暴涨频道识别模块

v6 更新：
1. 增长口径统一为固定时间窗口（近3个月 vs 前3个月）
2. 增加可靠性分级（gold/silver/bronze/red）
3. 增加单爆款异常检测（viral outlier）
"""

import logging
import math
from datetime import datetime, timedelta, timezone

import pandas as pd

logger = logging.getLogger(__name__)

GROWTH_WINDOW_MONTHS = 3


def detect_growth(videos_df: pd.DataFrame) -> dict:
    """
    分析单个频道的增长趋势
    通过对比最近 N 个视频和更早 N 个视频的播放量来判断

    返回:
        {
            'growth_ratio': float,       # 近期/早期播放量比值
            'status': str,               # 增长状态标签
            'status_emoji': str,         # 状态图标
            'avg_recent_views': int,     # 近期平均播放量
            'avg_older_views': int,      # 早期平均播放量
            'publish_frequency_change': float,  # 发布频率变化
            'engagement_trend': str,     # 互动率趋势
        }
    """
    if videos_df.empty or "published_at" not in videos_df.columns:
        return _empty_growth_result()

    df = videos_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["published_at"]):
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df = df.dropna(subset=["published_at"])  # 只保留有效时间
    if df.empty:
        return _empty_growth_result()

    # 统一到 UTC，避免窗口切分偏差
    if df["published_at"].dt.tz is None:
        df["published_at"] = df["published_at"].dt.tz_localize("UTC")
    else:
        df["published_at"] = df["published_at"].dt.tz_convert("UTC")

    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=GROWTH_WINDOW_MONTHS * 30)
    older_cutoff = recent_cutoff - timedelta(days=GROWTH_WINDOW_MONTHS * 30)

    recent = df[df["published_at"] >= recent_cutoff]
    older = df[(df["published_at"] >= older_cutoff) & (df["published_at"] < recent_cutoff)]

    avg_recent = recent["view_count"].mean() if not recent.empty else 0.0
    avg_older = older["view_count"].mean() if not older.empty else 0.0
    raw_growth_ratio = _safe_growth_ratio(avg_recent, avg_older)

    reliability = _build_reliability(
        recent_count=len(recent),
        older_count=len(older),
        total_videos=len(df),
    )

    reliable = reliability["level"] in {"gold", "silver"}
    growth_ratio = raw_growth_ratio if reliable and math.isfinite(raw_growth_ratio) else 0.0

    if not reliable:
        status, emoji = "窗口数据不足", "❓"
    else:
        status, emoji = _growth_status(growth_ratio)

    freq_change = _calc_publish_frequency_change(recent, older)
    engagement_trend = _calc_engagement_trend(recent, older)

    return {
        "growth_ratio": round(float(growth_ratio), 2),
        "raw_growth_ratio": round(float(raw_growth_ratio), 2) if math.isfinite(raw_growth_ratio) else None,
        "status": status,
        "status_emoji": emoji,
        "avg_recent_views": int(avg_recent),
        "avg_older_views": int(avg_older),
        "time_window": f"近{GROWTH_WINDOW_MONTHS}个月 vs 前{GROWTH_WINDOW_MONTHS}个月",
        "recent_count": len(recent),
        "older_count": len(older),
        "reliable": reliable,
        "reliability_level": reliability["level"],
        "reliability_score": reliability["score"],
        "reliability_reason": reliability["reason"],
        "publish_frequency_change": round(freq_change, 1),
        "engagement_trend": engagement_trend,
    }


def detect_viral_outliers(
    videos_df: pd.DataFrame,
    z_threshold: float = 2.0,
    min_views: int = 1000,
) -> dict:
    """
    检测单爆款异常，区分“可复制增长”与“偶发爆款”。
    """
    if videos_df.empty or "view_count" not in videos_df.columns:
        return {
            "has_outliers": False,
            "outlier_count": 0,
            "outliers": [],
            "baseline_growth_ratio": None,
            "baseline_reliable": False,
        }

    df = videos_df.copy()
    df = df.dropna(subset=["view_count"])
    if len(df) < 6:
        return {
            "has_outliers": False,
            "outlier_count": 0,
            "outliers": [],
            "baseline_growth_ratio": None,
            "baseline_reliable": False,
        }

    mean_views = df["view_count"].mean()
    std_views = df["view_count"].std()

    if std_views == 0 or pd.isna(std_views):
        baseline = detect_growth(df)
        return {
            "has_outliers": False,
            "outlier_count": 0,
            "outliers": [],
            "baseline_growth_ratio": baseline.get("growth_ratio"),
            "baseline_reliable": baseline.get("reliable", False),
        }

    df["view_zscore"] = (df["view_count"] - mean_views) / std_views
    outliers = df[(df["view_zscore"] >= z_threshold) & (df["view_count"] >= min_views)]

    if outliers.empty:
        baseline = detect_growth(df)
        return {
            "has_outliers": False,
            "outlier_count": 0,
            "outliers": [],
            "baseline_growth_ratio": baseline.get("growth_ratio"),
            "baseline_reliable": baseline.get("reliable", False),
        }

    baseline_df = df[df["view_zscore"] < z_threshold].copy()
    baseline = detect_growth(baseline_df)

    outlier_rows = []
    cols = ["video_id", "title", "view_count", "view_zscore"]
    for _, row in outliers.sort_values("view_zscore", ascending=False).head(5)[cols].iterrows():
        outlier_rows.append(
            {
                "video_id": row.get("video_id", ""),
                "title": row.get("title", "N/A"),
                "view_count": int(row.get("view_count", 0)),
                "zscore": round(float(row.get("view_zscore", 0.0)), 2),
            }
        )

    return {
        "has_outliers": True,
        "outlier_count": int(len(outliers)),
        "threshold_zscore": z_threshold,
        "outliers": outlier_rows,
        "baseline_growth_ratio": baseline.get("growth_ratio"),
        "baseline_reliable": baseline.get("reliable", False),
        "baseline_status": baseline.get("status", "N/A"),
    }


def _calc_publish_frequency_change(recent: pd.DataFrame, older: pd.DataFrame) -> float:
    """计算发布频率变化百分比 (正数=加速，负数=减速)"""
    if len(recent) < 2 or len(older) < 2:
        return 0.0

    recent_dates = recent["published_at"].sort_values()
    older_dates = older["published_at"].sort_values()

    recent_span = (recent_dates.iloc[-1] - recent_dates.iloc[0]).total_seconds()
    older_span = (older_dates.iloc[-1] - older_dates.iloc[0]).total_seconds()

    if recent_span <= 0 or older_span <= 0:
        return 0.0

    recent_freq = len(recent) / (recent_span / 86400)  # 每天发布数
    older_freq = len(older) / (older_span / 86400)

    if older_freq == 0:
        return 0.0

    return ((recent_freq - older_freq) / older_freq) * 100


def _calc_engagement_trend(recent: pd.DataFrame, older: pd.DataFrame) -> str:
    """计算互动率趋势"""

    def _engagement(df):
        views = df["view_count"].sum()
        if views == 0:
            return 0.0
        return (df["like_count"].sum() + df["comment_count"].sum()) / views

    recent_eng = _engagement(recent)
    older_eng = _engagement(older)

    if older_eng == 0:
        return "↗️ 上升" if recent_eng > 0 else "➡️ 持平"

    change = (recent_eng - older_eng) / older_eng
    if change > 0.2:
        return "↗️ 上升"
    elif change < -0.2:
        return "↘️ 下降"
    else:
        return "➡️ 持平"


def _safe_growth_ratio(avg_recent: float, avg_older: float) -> float:
    if avg_older > 0:
        return avg_recent / avg_older
    if avg_recent > 0:
        return float("inf")
    return 1.0


def _growth_status(growth_ratio: float) -> tuple[str, str]:
    if growth_ratio >= 5:
        return "爆发增长", "🚀"
    if growth_ratio >= 3:
        return "快速增长", "📈"
    if growth_ratio >= 1.5:
        return "稳步增长", "↗️"
    if growth_ratio >= 0.7:
        return "平稳", "➡️"
    return "下滑", "📉"


def _build_reliability(recent_count: int, older_count: int, total_videos: int) -> dict:
    """
    可靠性分级：
    - gold: 双窗口 >= 5
    - silver: 双窗口 >= 3
    - bronze: 双窗口 >= 2
    - red: 其他
    """
    if recent_count >= 5 and older_count >= 5:
        level = "gold"
        score = 92
        reason = "双窗口样本充足（>=5）"
    elif recent_count >= 3 and older_count >= 3:
        level = "silver"
        score = 78
        reason = "双窗口达到最小可靠样本（>=3）"
    elif recent_count >= 2 and older_count >= 2:
        level = "bronze"
        score = 58
        reason = "样本偏少，结论仅供参考"
    else:
        level = "red"
        score = 30
        reason = "窗口样本不足，建议补充数据"

    # 轻微根据样本总量修正（最多 +8）
    coverage_bonus = min(8, int((total_videos / 30) * 8)) if total_videos > 0 else 0
    score = min(100, score + coverage_bonus)
    return {
        "level": level,
        "score": score,
        "reason": reason,
    }


def _empty_growth_result() -> dict:
    return {
        "growth_ratio": 0.0,
        "raw_growth_ratio": None,
        "status": "数据不足",
        "status_emoji": "❓",
        "avg_recent_views": 0,
        "avg_older_views": 0,
        "time_window": f"近{GROWTH_WINDOW_MONTHS}个月 vs 前{GROWTH_WINDOW_MONTHS}个月",
        "recent_count": 0,
        "older_count": 0,
        "reliable": False,
        "reliability_level": "red",
        "reliability_score": 0,
        "reliability_reason": "无可用视频数据",
        "publish_frequency_change": 0,
        "engagement_trend": "未知",
    }


def find_rising_channels(
    fetcher,
    keywords: list[str],
    min_subscribers: int = 100,
    max_subscribers: int = 500000,
    progress_callback=None,
) -> pd.DataFrame:
    """
    搜索关键词 → 发现频道 → 计算增长率 → 按增长率排序
    用于识别近期暴涨的新频道

    Args:
        fetcher: YouTubeFetcher 实例
        keywords: 搜索关键词列表
        min_subscribers: 最小订阅数过滤
        max_subscribers: 最大订阅数过滤（排除大号）
        progress_callback: 进度回调函数

    Returns:
        DataFrame，包含频道信息 + 增长指标
    """
    # Step 1: 搜索频道（去重）
    all_channels = {}
    for kw in keywords:
        channels = fetcher.search_channels(kw, max_results=5)
        for ch in channels:
            if ch["channel_id"] not in all_channels:
                if min_subscribers <= ch["subscriber_count"] <= max_subscribers:
                    all_channels[ch["channel_id"]] = ch

    if not all_channels:
        return pd.DataFrame()

    # Step 2: 获取每个频道的视频并计算增长率
    results = []
    total = len(all_channels)
    for idx, (ch_id, ch_info) in enumerate(all_channels.items()):
        try:
            videos_df = fetcher.get_channel_videos(ch_id, max_videos=30)
            growth = detect_growth(videos_df)

            results.append(
                {
                    **ch_info,
                    **growth,
                }
            )
        except Exception as e:
            logger.warning(f"分析频道 {ch_id} 失败: {e}")

        if progress_callback:
            progress_callback((idx + 1) / total)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    # 仅按可靠增长排序，避免低样本误导
    if "reliable" in df.columns:
        df["reliable_rank_boost"] = df["reliable"].apply(lambda x: 1 if x else 0)
        df = df.sort_values(["reliable_rank_boost", "growth_ratio"], ascending=[False, False])
        df = df.drop(columns=["reliable_rank_boost"])
    else:
        df = df.sort_values("growth_ratio", ascending=False)
    return df
