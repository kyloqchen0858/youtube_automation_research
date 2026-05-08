"""
Data Analyzer — 数据分析模块
计算互动率、最佳时长、关键词提取、频道横向对比
"""

import re
import logging
from collections import Counter

import numpy as np
import pandas as pd
import jieba
import jieba.analyse

logger = logging.getLogger(__name__)

# 中英文停用词
STOPWORDS_ZH = set(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 "
    "自己 这 他 她 它 们 那 里 为 什么 呢 吗 吧 啊 哦 嗯 把 被 从 与 及 其 之 以 而 "
    "但 对 可以 这个 那个 如何 怎么 什么 为什么 如果 因为 所以 已经 还是 或者 只是 "
    "知道 觉得 可能 应该 需要 喜欢 想要 真的 其实 非常 比较 很多 更多 最 还 就是 "
    "视频 频道 订阅 点赞 评论".split()
)

STOPWORDS_EN = set(
    "the a an is are was were be been being have has had do does did will would "
    "shall should may might can could this that these those i me my we our you "
    "your he him his she her it its they them their what which who whom how where "
    "when why all each every both few more most other some such no not only own "
    "same so than too very just don t s d ll re ve m about above after again "
    "against into through during before to from up down in out on off over under "
    "between here there then once and but or if while at by for with as of".split()
)

STOPWORDS = STOPWORDS_ZH | STOPWORDS_EN


def compute_metrics(videos_df: pd.DataFrame) -> pd.DataFrame:
    """计算每个视频的核心指标"""
    df = videos_df.copy()
    if df.empty:
        return df

    # 互动率
    df["engagement_rate"] = df.apply(
        lambda r: (r["like_count"] + r["comment_count"]) / r["view_count"]
        if r["view_count"] > 0
        else 0,
        axis=1,
    )

    # 点赞率
    df["like_rate"] = df.apply(
        lambda r: r["like_count"] / r["view_count"] if r["view_count"] > 0 else 0,
        axis=1,
    )

    # 评论率
    df["comment_rate"] = df.apply(
        lambda r: r["comment_count"] / r["view_count"] if r["view_count"] > 0 else 0,
        axis=1,
    )

    # 发布时段
    if "published_at" in df.columns:
        df["publish_hour"] = df["published_at"].dt.hour
        df["publish_day"] = df["published_at"].dt.day_name()

    return df


def find_top_videos(videos_df: pd.DataFrame, metric: str = "view_count", n: int = 10) -> pd.DataFrame:
    """按指定指标排序取 Top N"""
    if videos_df.empty or metric not in videos_df.columns:
        return pd.DataFrame()
    return videos_df.nlargest(n, metric)


def analyze_duration_sweet_spot(videos_df: pd.DataFrame) -> dict:
    """分析最佳视频时长区间"""
    if videos_df.empty:
        return {"best_range": "N/A", "best_range_avg_views": 0, "ranges": []}

    df = videos_df[videos_df["duration_minutes"] > 0].copy()
    if df.empty:
        return {"best_range": "N/A", "best_range_avg_views": 0, "ranges": []}

    # 按时长分段
    bins = [0, 3, 5, 10, 15, 20, 30, 60, float("inf")]
    labels = ["0-3m", "3-5m", "5-10m", "10-15m", "15-20m", "20-30m", "30-60m", "60m+"]
    df["duration_bin"] = pd.cut(df["duration_minutes"], bins=bins, labels=labels)

    agg = df.groupby("duration_bin", observed=True).agg(
        avg_views=("view_count", "mean"),
        avg_engagement=("engagement_rate", "mean") if "engagement_rate" in df.columns else ("view_count", "count"),
        count=("video_id", "count"),
    ).reset_index()

    if agg.empty:
        return {"best_range": "N/A", "best_range_avg_views": 0, "ranges": []}

    # 至少有3个视频的分段才有统计意义
    significant = agg[agg["count"] >= 3]
    if significant.empty:
        significant = agg

    best_row = significant.loc[significant["avg_views"].idxmax()]

    ranges_list = []
    for _, row in agg.iterrows():
        ranges_list.append({
            "range": str(row["duration_bin"]),
            "avg_views": int(row["avg_views"]),
            "count": int(row["count"]),
        })

    return {
        "best_range": str(best_row["duration_bin"]),
        "best_range_avg_views": int(best_row["avg_views"]),
        "ranges": ranges_list,
    }


def analyze_publish_patterns(videos_df: pd.DataFrame) -> dict:
    """分析发布时间模式"""
    if videos_df.empty or "published_at" not in videos_df.columns:
        return {"best_day": "N/A", "best_hour": 0, "heatmap_data": None}

    df = videos_df.copy()
    df["hour"] = df["published_at"].dt.hour
    df["day_of_week"] = df["published_at"].dt.dayofweek  # 0=Mon

    day_names = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

    # 热力图数据：day × hour 的视频数矩阵
    heatmap = pd.crosstab(df["day_of_week"], df["hour"])
    # 确保所有列（0-23）和行（0-6）存在
    for h in range(24):
        if h not in heatmap.columns:
            heatmap[h] = 0
    for d in range(7):
        if d not in heatmap.index:
            heatmap.loc[d] = 0
    heatmap = heatmap.sort_index(axis=0).sort_index(axis=1)
    heatmap.index = [day_names[i] for i in heatmap.index]

    # 最佳发布日和时间
    best_day = df.groupby("day_of_week")["view_count"].mean().idxmax()
    best_hour = df.groupby("hour")["view_count"].mean().idxmax()

    return {
        "best_day": day_names.get(best_day, "N/A"),
        "best_hour": int(best_hour),
        "heatmap_data": heatmap,
    }


def analyze_channel_evolution(videos_df: pd.DataFrame) -> dict:
    """
    频道纵向演化分析：将视频分为 early/mid/recent 三段，判断优化趋势。
    """
    if videos_df.empty or len(videos_df) < 9:
        return {
            "trend": "insufficient",
            "trend_label": "样本不足",
            "improvement_rate": 0.0,
            "periods": {},
            "inflection": "视频样本不足，无法判断阶段变化",
        }

    df = videos_df.copy()
    if "published_at" in df.columns:
        df = df.sort_values("published_at", ascending=True)
    df = df.reset_index(drop=True)

    if "engagement_rate" not in df.columns and {"view_count", "like_count", "comment_count"}.issubset(df.columns):
        df["engagement_rate"] = df.apply(
            lambda r: (r["like_count"] + r["comment_count"]) / r["view_count"] if r["view_count"] > 0 else 0,
            axis=1,
        )

    index_chunks = np.array_split(df.index.to_numpy(), 3)
    chunks = [df.loc[idx_chunk].copy() for idx_chunk in index_chunks]
    names = ["early", "mid", "recent"]

    periods = {}
    for name, chunk in zip(names, chunks):
        periods[name] = {
            "videos": int(len(chunk)),
            "avg_views": int(chunk["view_count"].mean()) if "view_count" in chunk.columns else 0,
            "median_views": int(chunk["view_count"].median()) if "view_count" in chunk.columns else 0,
            "avg_engagement": float(chunk["engagement_rate"].mean()) if "engagement_rate" in chunk.columns else 0.0,
            "avg_duration": round(float(chunk["duration_minutes"].mean()), 1) if "duration_minutes" in chunk.columns else 0.0,
        }

    early_views = periods["early"]["avg_views"]
    recent_views = periods["recent"]["avg_views"]
    if early_views <= 0:
        improvement_rate = 0.0
    else:
        improvement_rate = (recent_views - early_views) / early_views

    if improvement_rate > 0.2:
        trend = "improving"
        trend_label = "持续优化"
    elif improvement_rate < -0.2:
        trend = "declining"
        trend_label = "增长回落"
    else:
        trend = "plateau"
        trend_label = "进入平台期"

    inflection = _describe_evolution_inflection(periods)

    return {
        "trend": trend,
        "trend_label": trend_label,
        "improvement_rate": round(float(improvement_rate), 2),
        "periods": periods,
        "inflection": inflection,
    }


def _describe_evolution_inflection(periods: dict) -> str:
    early = periods.get("early", {})
    mid = periods.get("mid", {})
    recent = periods.get("recent", {})

    view_up_mid = mid.get("avg_views", 0) - early.get("avg_views", 0)
    view_up_recent = recent.get("avg_views", 0) - mid.get("avg_views", 0)

    if view_up_mid > 0 and view_up_recent > 0:
        return "两个阶段都在提升，建议保持当前选题与发布节奏"
    if view_up_mid > 0 and view_up_recent < 0:
        return "中期上升但近期回落，建议复盘最近标题和时长变化"
    if view_up_mid < 0 and view_up_recent > 0:
        return "近期出现反弹，建议继续放大最近有效内容格式"
    return "整体波动或下降，建议先做低风险 A/B 选题测试"


def extract_title_keywords(videos_df: pd.DataFrame, top_n: int = 50) -> dict[str, float]:
    """
    从视频标题中提取高频关键词
    使用 jieba 分词处理中英文混合文本
    """
    if videos_df.empty:
        return {}

    all_titles = " ".join(videos_df["title"].tolist())
    return _extract_keywords(all_titles, top_n)


def extract_comment_keywords(comments: list[dict], top_n: int = 50) -> dict[str, float]:
    """从评论文本中提取高频关键词"""
    if not comments:
        return {}

    all_text = " ".join(c["text"] for c in comments)
    return _extract_keywords(all_text, top_n)


def _extract_keywords(text: str, top_n: int = 50) -> dict[str, float]:
    """通用关键词提取（jieba TF-IDF + 手动词频统计融合）"""
    if not text.strip():
        return {}

    # jieba TF-IDF 提取
    tfidf_keywords = jieba.analyse.extract_tags(text, topK=top_n, withWeight=True)
    keywords = {word: weight for word, weight in tfidf_keywords}

    # 过滤停用词和太短的词
    keywords = {
        k: v
        for k, v in keywords.items()
        if k.lower() not in STOPWORDS and len(k) > 1 and not k.isdigit()
    }

    return dict(sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:top_n])


def compare_channels(channels_data: dict[str, dict]) -> pd.DataFrame:
    """
    多频道横向对比

    Args:
        channels_data: {channel_id: {'info': ch_info_dict, 'videos': videos_df, 'growth': growth_dict}}

    Returns:
        频道对比 DataFrame
    """
    rows = []
    for ch_id, data in channels_data.items():
        info = data.get("info", {})
        videos_df = data.get("videos", pd.DataFrame())
        growth = data.get("growth", {})

        row = {
            "频道名": info.get("title", ch_id),
            "订阅数": info.get("subscriber_count", 0),
            "视频总数": info.get("video_count", 0),
            "总播放量": info.get("view_count", 0),
        }

        if not videos_df.empty:
            row["平均播放量"] = int(videos_df["view_count"].mean())
            row["最高播放量"] = int(videos_df["view_count"].max())
            row["平均时长(分)"] = round(videos_df["duration_minutes"].mean(), 1) if "duration_minutes" in videos_df.columns else 0
            if "engagement_rate" in videos_df.columns:
                row["平均互动率"] = f"{videos_df['engagement_rate'].mean():.2%}"
        else:
            row["平均播放量"] = 0
            row["最高播放量"] = 0
            row["平均时长(分)"] = 0
            row["平均互动率"] = "0%"

        row["增长状态"] = f"{growth.get('status_emoji', '')} {growth.get('status', '未知')}"
        row["增长倍率"] = growth.get("growth_ratio", 1.0)

        rows.append(row)

    return pd.DataFrame(rows)
