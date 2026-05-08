"""
一键运行完整调研流程 v5 — 从0到1实战指南 + 频道制作优化
Full Pipeline Runner v5

v5 核心改进（基于 v4 自评估 + 用户反馈）：
1. 增长分析：统一固定时间窗口，去掉前25/后25回退逻辑
2. 三份报告：DeepSeek报告 + Copilot数据报告 + 评估报告
3. 重心转向「从0到1实战指南」：选题方法论、SEO优化、冷启动、频道制作流程
4. 增加频道制作与视觉风格建议
5. 新增 SEO/关键词竞争分析模块
6. Copilot报告是纯数据驱动的统计分析，不依赖AI
"""

import os
import sys
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import numpy as np

from core.competitor_radar import build_competitor_radar
from core.decline_analyzer import analyze_decline_drivers, format_decline_diagnostics
from core.reverse_engineering import build_reverse_engineering_playbook
from core.strategy_models import ContentDirection, PrimaryGoal, StrategyBrief
from core.strategy_advisor import generate_strategy_plan
from core.transcript_analyzer import analyze_transcript_patterns
from core.workflow_monitor import WorkflowMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            cleaned = [str(item).strip() for item in parsed if str(item).strip()]
            if cleaned:
                return cleaned
    except json.JSONDecodeError:
        pass

    parts = re.split(r"[\n,|;]+", raw)
    cleaned = [part.strip() for part in parts if part.strip()]
    return cleaned or default


def _env_value(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _default_search_keywords() -> list[str]:
    return [
        "ai workflow tutorial",
        "ai agent tutorial",
        "chatgpt workflow tutorial",
        "cursor tutorial",
        "ai automation tutorial",
        "n8n ai agent tutorial",
        "claude workflow tutorial",
        "ai tools for creators",
    ]


def _build_research_profile() -> dict[str, str | list[str]]:
    return {
        "language": os.environ.get("YT_RESEARCH_LANGUAGE", "英文"),
        "topic": os.environ.get(
            "YT_RESEARCH_TOPIC",
            "AI workflow tutorials for creators and operators",
        ),
        "niche": os.environ.get(
            "YT_RESEARCH_NICHE",
            "AI Workflow Tutorials — 英文不露脸教程频道，用录屏 + 旁白拆解 AI agent、automation 与创作者工作流",
        ),
        "differentiation": os.environ.get(
            "YT_RESEARCH_DIFFERENTIATION",
            "用真实工作流、结果演示和低废话拆解 AI 工具的实际使用场景",
        ),
        "target_audience": os.environ.get(
            "YT_RESEARCH_AUDIENCE",
            "独立创作者、运营者、小团队负责人、想用 AI 提升工作效率的人",
        ),
        "channel_style": os.environ.get(
            "YT_RESEARCH_CHANNEL_STYLE",
            "不露脸教程频道，视觉风格偏向录屏、产品界面展示、画外音和轻量标注动画",
        ),
        "title_language": os.environ.get("YT_RESEARCH_TITLE_LANGUAGE", "英文"),
        "content_direction": os.environ.get("YT_RESEARCH_CONTENT_DIRECTION", "ai_tool_tutorial"),
        "search_keywords": _env_list("YT_RESEARCH_SEARCH_KEYWORDS", _default_search_keywords()),
        "topic_label": os.environ.get("YT_RESEARCH_TOPIC_LABEL", "ai_workflow_tutorials"),
    }


RESEARCH_PROFILE = _build_research_profile()


def _profile_text() -> str:
    return (
        f"- 频道语言：{RESEARCH_PROFILE['language']}\n"
        f"- 主题：{RESEARCH_PROFILE['topic']}\n"
        f"- 赛道描述：{RESEARCH_PROFILE['niche']}\n"
        f"- 差异化：{RESEARCH_PROFILE['differentiation']}\n"
        f"- 目标受众：{RESEARCH_PROFILE['target_audience']}\n"
        f"- 频道形式：{RESEARCH_PROFILE['channel_style']}\n"
        f"- 标题语言：{RESEARCH_PROFILE['title_language']}"
    )

# ── 配置 ────────────────────────────────────────────────────
YOUTUBE_API_KEY = _env_value("YOUTUBE_API_KEY")
DEEPSEEK_API_KEY = _env_value("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = _env_value("DEEPSEEK_MODEL", "deepseek-v4-flash") or "deepseek-v4-flash"

NICHE = str(RESEARCH_PROFILE["niche"])
CHANNEL_STYLE = str(RESEARCH_PROFILE["channel_style"])

SEARCH_KEYWORDS = list(RESEARCH_PROFILE["search_keywords"])

MIN_SUBSCRIBER_COUNT = 3_000
MAX_SUBSCRIBER_COUNT = 15_000_000
MIN_AVG_VIEWS = 500
MIN_VIDEO_VIEWS_FOR_COMMENT = 10_000
MIN_VIDEO_VIEWS_FOR_TRANSCRIPT = 20_000

OUTPUT_DIR = str(REPO_ROOT / "output")

MAX_CHANNELS_PER_KEYWORD = 5
MAX_CHANNELS_TOTAL = 15
MAX_VIDEOS_PER_CHANNEL = 50
TOP_N_COMMENTS_VIDEOS = 10
MAX_COMMENTS_PER_VIDEO = 100
TOP_N_TRANSCRIPT_VIDEOS = 15

# v5: 固定时间窗口，不再回退
GROWTH_WINDOW_MONTHS = 3

TOPIC_ALIGNMENT_HINTS = {
    "ai", "agent", "agents", "workflow", "automation", "tutorial", "tutorials", "creator", "creators",
    "operator", "operators", "chatgpt", "claude", "cursor", "n8n", "prompt", "prompts", "tool", "tools",
    "build", "builder", "research", "system", "systems", "content", "code",
}


def _alignment_terms() -> set[str]:
    terms = set(TOPIC_ALIGNMENT_HINTS)
    for text in list(SEARCH_KEYWORDS) + [NICHE, CHANNEL_STYLE, str(RESEARCH_PROFILE["topic"])]:
        for token in re.findall(r"[a-zA-Z0-9\-]+", str(text).lower()):
            if len(token) >= 3:
                terms.add(token)
    return terms


ALIGNMENT_TERMS = _alignment_terms()


def _topic_alignment_score(title: str, channel_title: str = "") -> int:
    text = f"{title} {channel_title}".lower()
    score = 0
    for term in ALIGNMENT_TERMS:
        if term in text:
            score += 2 if term in TOPIC_ALIGNMENT_HINTS else 1
    return score


def _select_research_videos(videos_df: pd.DataFrame, min_views: int, limit: int) -> pd.DataFrame:
    if videos_df.empty:
        return videos_df

    candidates = videos_df[videos_df["view_count"] >= min_views].copy()
    if candidates.empty:
        candidates = videos_df.copy()

    candidates["topic_alignment"] = candidates.apply(
        lambda row: _topic_alignment_score(row.get("title", ""), row.get("channel_title", "")),
        axis=1,
    )

    aligned = candidates[candidates["topic_alignment"] > 0]
    if len(aligned) >= limit:
        pool = aligned
    elif not aligned.empty:
        fallback = candidates.loc[~candidates.index.isin(aligned.index)]
        pool = pd.concat([aligned, fallback], ignore_index=False)
    else:
        pool = candidates

    sort_cols = ["topic_alignment", "view_count"]
    ascending = [False, False]
    if "engagement_rate" in pool.columns:
        sort_cols.append("engagement_rate")
        ascending.append(False)

    return pool.sort_values(sort_cols, ascending=ascending).head(limit).copy()


# ══════════════════════════════════════════════════════════════
# 增长检测 v5 — 统一固定时间窗口
# ══════════════════════════════════════════════════════════════

def detect_growth_v5(videos_df: pd.DataFrame) -> dict:
    """
    v5: 严格使用固定时间窗口，不回退到前后对半分。
    如果某窗口数据不足，标注"数据不足"而非用不同口径计算。
    """
    if videos_df.empty or len(videos_df) < 4:
        return {
            "growth_ratio": None,
            "status": "数据不足",
            "status_emoji": "❓",
            "avg_recent_views": 0,
            "avg_older_views": 0,
            "time_window": f"近{GROWTH_WINDOW_MONTHS}个月(数据不足)",
            "recent_count": 0,
            "older_count": 0,
            "reliable": False,
        }

    now = datetime.now(timezone.utc)
    cutoff_recent = now - timedelta(days=GROWTH_WINDOW_MONTHS * 30)
    cutoff_older = cutoff_recent - timedelta(days=GROWTH_WINDOW_MONTHS * 30)

    df = videos_df.copy()
    if df["published_at"].dt.tz is None:
        df["published_at"] = df["published_at"].dt.tz_localize("UTC")

    recent = df[df["published_at"] >= cutoff_recent]
    older = df[(df["published_at"] >= cutoff_older) & (df["published_at"] < cutoff_recent)]

    time_window = f"近{GROWTH_WINDOW_MONTHS}个月 vs 前{GROWTH_WINDOW_MONTHS}个月"
    reliable = len(recent) >= 3 and len(older) >= 3

    avg_recent = recent["view_count"].mean() if not recent.empty else 0
    avg_older = older["view_count"].mean() if not older.empty else 0

    if not reliable:
        return {
            "growth_ratio": None,
            "status": f"窗口数据不足(近期{len(recent)}个/早期{len(older)}个视频)",
            "status_emoji": "❓",
            "avg_recent_views": int(avg_recent),
            "avg_older_views": int(avg_older),
            "time_window": time_window,
            "recent_count": len(recent),
            "older_count": len(older),
            "reliable": False,
        }

    if avg_older > 0:
        growth_ratio = avg_recent / avg_older
    else:
        growth_ratio = float("inf") if avg_recent > 0 else 1.0

    if growth_ratio >= 5:
        status, emoji = "爆发增长", "🚀"
    elif growth_ratio >= 3:
        status, emoji = "快速增长", "📈"
    elif growth_ratio >= 1.5:
        status, emoji = "稳步增长", "↗️"
    elif growth_ratio >= 0.7:
        status, emoji = "平稳", "➡️"
    else:
        status, emoji = "下滑", "📉"

    return {
        "growth_ratio": round(growth_ratio, 2),
        "status": status,
        "status_emoji": emoji,
        "avg_recent_views": int(avg_recent),
        "avg_older_views": int(avg_older),
        "time_window": time_window,
        "recent_count": len(recent),
        "older_count": len(older),
        "reliable": True,
    }


def analyze_publish_patterns_per_channel(channels_data: dict) -> dict:
    """按频道单独分析发布模式"""
    results = {}
    for ch_id, data in channels_data.items():
        info = data["info"]
        vids = data["videos"]
        if vids.empty or len(vids) < 5:
            continue

        df = vids.copy()
        if "published_at" not in df.columns:
            continue

        df["day_of_week"] = df["published_at"].dt.day_name()
        day_avg_views = df.groupby("day_of_week")["view_count"].mean()

        df["hour"] = df["published_at"].dt.hour
        hour_avg_views = df.groupby("hour")["view_count"].mean()

        date_range = (df["published_at"].max() - df["published_at"].min()).days
        freq = f"{len(df) / max(date_range / 7, 1):.1f} videos/week" if date_range > 0 else "N/A"

        best_day = day_avg_views.idxmax() if not day_avg_views.empty else "N/A"
        best_hour = int(hour_avg_views.idxmax()) if not hour_avg_views.empty else 0

        results[info["title"]] = {
            "best_day": best_day,
            "best_hour": best_hour,
            "avg_views_by_day": day_avg_views.to_dict(),
            "frequency": freq,
            "total_videos": len(df),
            "subscriber_count": info.get("subscriber_count", 0),
        }
    return results


# ══════════════════════════════════════════════════════════════
# Copilot 统计分析（纯 Python，不依赖 AI）
# ══════════════════════════════════════════════════════════════

def _build_copilot_report(
    channels_data, combined_df, duration_analysis,
    publish_patterns_by_channel, transcripts, video_info_map,
    all_comments, timestamp, radar_results=None, strategy_brief=None,
    reverse_engineering_playbook=None, strategy_plan=None, decline_diagnostics=None
):
    """
    Copilot 数据分析报告 — 纯统计驱动，无 AI 依赖。
    提供独立于 DeepSeek 的第二视角。
    """
    lines = []
    lines.append("# Copilot 独立数据分析报告")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**分析方法**: 纯统计分析（Python），独立于 DeepSeek AI")
    lines.append(f"**数据规模**: {len(channels_data)} 频道 | {len(combined_df)} 视频 | {len(all_comments)} 条评论 | {len(transcripts)} 份字幕")
    lines.append("")

    if strategy_brief:
        lines.append("---")
        lines.append("## 0. Strategy Brief & Competitor Radar")
        lines.append("")
        lines.append(f"- 内容方向: {strategy_brief.content_direction}")
        lines.append(f"- 主要目标: {strategy_brief.primary_goal}")
        lines.append(f"- Brief 关键词: {', '.join(strategy_brief.strategy_keywords or strategy_brief.discovery_keywords[:5])}")
        lines.append("")

    if radar_results and radar_results.get("top_channels"):
        lines.append("**雷达短名单频道**")
        for channel in radar_results.get("top_channels", [])[:5]:
            reasons = "; ".join(channel.get("score_reasons", [])[:3])
            lines.append(
                f"- {channel.get('channel_title', 'Unknown')} | radar={channel.get('radar_score', 0):.2f} | "
                f"views/sub={channel.get('avg_views_to_subs_ratio', 0):.2f} | growth={channel.get('growth_ratio', 0):.2f}x"
                f"{f' | {reasons}' if reasons else ''}"
            )
        lines.append("")

    if reverse_engineering_playbook:
        lines.append("**反向拆解摘要**")
        if reverse_engineering_playbook.get("channel_archetype"):
            lines.append(f"- 频道原型: {reverse_engineering_playbook.get('channel_archetype')}")
        for item in reverse_engineering_playbook.get("recommended_adaptations", [])[:4]:
            lines.append(f"- {item}")
        lines.append("")

    if strategy_plan:
        lines.append("**策略规划摘要**")
        lines.append(f"- 北极星目标: {strategy_plan.get('north_star_goal', '')}")
        for note in strategy_plan.get("confidence_notes", [])[:3]:
            lines.append(f"- {note}")
        lines.append("")

    # ── 1. 频道增长排名（仅可靠数据）──
    lines.append("---")
    lines.append("## 1. 频道增长排名（仅统计可靠的数据）")
    lines.append("")
    lines.append(f"增长分析标准：固定 {GROWTH_WINDOW_MONTHS} 个月时间窗口，双窗口均需 ≥3 个视频才纳入排名。")
    lines.append("")

    reliable_channels = []
    unreliable_channels = []
    for ch_id, data in channels_data.items():
        info = data["info"]
        growth = data["growth"]
        entry = {
            "name": info["title"],
            "subs": info.get("subscriber_count", 0),
            "growth": growth,
        }
        if growth.get("reliable"):
            reliable_channels.append(entry)
        else:
            unreliable_channels.append(entry)

    if reliable_channels:
        reliable_channels.sort(key=lambda x: x["growth"]["growth_ratio"] or 0, reverse=True)
        lines.append("### 数据可靠的频道（按增长倍率排序）")
        lines.append("| 排名 | 频道 | 订阅 | 近期均播 | 早期均播 | 增长倍率 | 近期样本 | 早期样本 | 状态 |")
        lines.append("|------|------|------|----------|----------|---------|---------|---------|------|")
        for i, ch in enumerate(reliable_channels, 1):
            g = ch["growth"]
            lines.append(
                f"| {i} | {ch['name']} | {ch['subs']:,} | "
                f"{g['avg_recent_views']:,} | {g['avg_older_views']:,} | "
                f"{g['growth_ratio']}x | {g['recent_count']}个 | {g['older_count']}个 | "
                f"{g['status_emoji']} {g['status']} |"
            )
        lines.append("")

    if unreliable_channels:
        lines.append("### 数据不足的频道（不纳入增长排名）")
        lines.append("| 频道 | 订阅 | 原因 |")
        lines.append("|------|------|------|")
        for ch in unreliable_channels:
            lines.append(f"| {ch['name']} | {ch['subs']:,} | {ch['growth']['status']} |")
        lines.append("")

    if decline_diagnostics:
        lines.append("### 下滑原因诊断")
        for item in decline_diagnostics:
            lines.append(f"- **{item['channel_title']}** | {item['classification_label']} | {item['summary']}")
            for reason in item.get("objective_factors", [])[:2]:
                lines.append(f"  - 客观因素：{reason}")
            for reason in item.get("strategy_factors", [])[:2]:
                lines.append(f"  - 策略因素：{reason}")
        lines.append("")

    # ── 2. 视频表现统计分析 ──
    lines.append("---")
    lines.append("## 2. 视频表现统计分析")
    lines.append("")

    if not combined_df.empty:
        # 基础统计
        lines.append("### 2.1 播放量分布")
        view_stats = combined_df["view_count"].describe()
        lines.append(f"- 最小值: {int(view_stats['min']):,}")
        lines.append(f"- 25%分位: {int(view_stats['25%']):,}")
        lines.append(f"- 中位数: {int(view_stats['50%']):,}")
        lines.append(f"- 75%分位: {int(view_stats['75%']):,}")
        lines.append(f"- 最大值: {int(view_stats['max']):,}")
        lines.append(f"- 平均值: {int(view_stats['mean']):,}")
        lines.append(f"- 中位数与平均值差距: {int(view_stats['mean']) / max(int(view_stats['50%']), 1):.1f}x（越大说明少数爆款拉高均值）")
        lines.append("")

        # 参与率分析
        if "engagement_rate" in combined_df.columns:
            lines.append("### 2.2 参与率分布")
            eng_df = combined_df[combined_df["view_count"] >= 1000]  # 过滤低播放量噪声
            if not eng_df.empty:
                eng_stats = eng_df["engagement_rate"].describe()
                lines.append(f"- 中位数参与率: {eng_stats['50%']:.2%}")
                lines.append(f"- 前25%门槛: {eng_stats['75%']:.2%}")
                lines.append(f"- 参与率冠军（≥1000播放）:")
                top_eng = eng_df.nlargest(5, "engagement_rate")
                for _, v in top_eng.iterrows():
                    lines.append(f"  - [{v['engagement_rate']:.2%}] {v['title'][:60]} ({v['view_count']:,} views)")
                lines.append("")

        # 时长甜点分析
        if "duration_minutes" in combined_df.columns:
            lines.append("### 2.3 时长 vs 播放量（甜点分析）")
            dur_df = combined_df[combined_df["duration_minutes"] > 0].copy()
            if not dur_df.empty:
                bins = [0, 3, 5, 8, 12, 18, 25, 40, 60, float("inf")]
                labels = ["0-3min", "3-5min", "5-8min", "8-12min", "12-18min", "18-25min", "25-40min", "40-60min", "60+min"]
                dur_df["dur_bin"] = pd.cut(dur_df["duration_minutes"], bins=bins, labels=labels)
                bin_stats = dur_df.groupby("dur_bin", observed=True).agg(
                    count=("view_count", "count"),
                    median_views=("view_count", "median"),
                    mean_views=("view_count", "mean"),
                ).reset_index()
                lines.append("| 时长区间 | 视频数 | 中位播放量 | 平均播放量 |")
                lines.append("|---------|--------|-----------|-----------|")
                best_median = 0
                best_bin = ""
                for _, row in bin_stats.iterrows():
                    if row["count"] >= 3:  # 至少3个样本
                        lines.append(
                            f"| {row['dur_bin']} | {row['count']} | "
                            f"{int(row['median_views']):,} | {int(row['mean_views']):,} |"
                        )
                        if row["median_views"] > best_median:
                            best_median = row["median_views"]
                            best_bin = row["dur_bin"]
                lines.append(f"\n**统计最佳时长区间**: {best_bin}（中位播放量最高）")
                lines.append("")

        # 标题模式分析
        lines.append("### 2.4 标题模式分析")
        lines.append("")

        # 标题长度 vs 播放量
        combined_df["title_len"] = combined_df["title"].str.len()
        combined_df["title_words"] = combined_df["title"].str.split().str.len()

        # 高播放量 vs 低播放量标题对比
        median_views = combined_df["view_count"].median()
        high_perf = combined_df[combined_df["view_count"] >= combined_df["view_count"].quantile(0.75)]
        low_perf = combined_df[combined_df["view_count"] <= combined_df["view_count"].quantile(0.25)]

        lines.append("**高vs低播放量视频的标题对比:**")
        lines.append(f"- 高播放量（前25%）平均标题长度: {high_perf['title_len'].mean():.0f}字符 / {high_perf['title_words'].mean():.0f}词")
        lines.append(f"- 低播放量（后25%）平均标题长度: {low_perf['title_len'].mean():.0f}字符 / {low_perf['title_words'].mean():.0f}词")
        lines.append("")

        # 标题是否含数字
        combined_df["has_number"] = combined_df["title"].str.contains(r'\d+', regex=True)
        num_vs_no = combined_df.groupby("has_number")["view_count"].agg(["median", "mean", "count"])
        lines.append("**标题含数字 vs 不含数字:**")
        for has_num, row in num_vs_no.iterrows():
            label = "含数字" if has_num else "无数字"
            lines.append(f"- {label}: 中位播放 {int(row['median']):,} | 平均播放 {int(row['mean']):,} | {int(row['count'])}个视频")
        lines.append("")

        # 标题是否含问号（问题式标题）
        combined_df["has_question"] = combined_df["title"].str.contains(r'\?', regex=True)
        q_vs_no = combined_df.groupby("has_question")["view_count"].agg(["median", "mean", "count"])
        lines.append("**问句标题 vs 陈述标题:**")
        for has_q, row in q_vs_no.iterrows():
            label = "问句" if has_q else "陈述"
            lines.append(f"- {label}: 中位播放 {int(row['median']):,} | 平均播放 {int(row['mean']):,} | {int(row['count'])}个视频")
        lines.append("")

        # 标题含 "How to" 类
        combined_df["is_howto"] = combined_df["title"].str.lower().str.contains(r'how to|ways to|tips|guide|rules', regex=True)
        howto = combined_df.groupby("is_howto")["view_count"].agg(["median", "mean", "count"])
        lines.append("**How-to/Tips型 vs 其他:**")
        for is_h, row in howto.iterrows():
            label = "How-to型" if is_h else "其他"
            lines.append(f"- {label}: 中位播放 {int(row['median']):,} | 平均播放 {int(row['mean']):,} | {int(row['count'])}个视频")
        lines.append("")

        # 高频标题词（高播放量视频）
        lines.append("**高播放量视频（前25%）的高频标题词:**")
        all_words = []
        stop_words = {"the", "a", "an", "of", "to", "in", "for", "and", "is", "it", "on",
                       "that", "this", "with", "you", "your", "my", "are", "was", "be",
                       "by", "at", "or", "from", "not", "but", "what", "how", "all", "can",
                       "will", "do", "if", "about", "its", "has", "have", "had", "i", "me",
                       "we", "they", "he", "she", "his", "her", "-", "—", "|", "&", "no"}
        for _, v in high_perf.iterrows():
            words = re.findall(r"[a-zA-Z']+", v["title"].lower())
            all_words.extend([w for w in words if w not in stop_words and len(w) > 2])
        word_freq = Counter(all_words).most_common(20)
        lines.append("| 排名 | 词 | 出现次数 |")
        lines.append("|------|-----|---------|")
        for i, (word, count) in enumerate(word_freq, 1):
            lines.append(f"| {i} | {word} | {count} |")
        lines.append("")

    # ── 3. 发布模式统计 ──
    lines.append("---")
    lines.append("## 3. 发布模式分析")
    lines.append("")

    if publish_patterns_by_channel:
        lines.append("### 3.1 各频道发布模式")
        lines.append("| 频道 | 最佳日 | 最佳时(UTC) | 频率 | 订阅 |")
        lines.append("|------|-------|-----------|------|------|")
        for ch_name, pat in publish_patterns_by_channel.items():
            lines.append(
                f"| {ch_name} | {pat['best_day']} | {pat['best_hour']}:00 | "
                f"{pat['frequency']} | {pat['subscriber_count']:,} |"
            )
        lines.append("")

        # 汇总统计
        all_best_days = [p["best_day"] for p in publish_patterns_by_channel.values()]
        day_counter = Counter(all_best_days)
        lines.append("### 3.2 最佳发布日汇总（多少频道选择该日）")
        lines.append("| 日期 | 频道数 |")
        lines.append("|------|-------|")
        for day, count in day_counter.most_common():
            lines.append(f"| {day} | {count} |")
        lines.append("")

        all_best_hours = [p["best_hour"] for p in publish_patterns_by_channel.values()]
        hour_counter = Counter(all_best_hours)
        lines.append("### 3.3 最佳发布小时汇总")
        top_hours = hour_counter.most_common(5)
        lines.append("| 小时(UTC) | 频道数 |")
        lines.append("|----------|-------|")
        for hour, count in top_hours:
            lines.append(f"| {hour}:00 | {count} |")
        lines.append("")

    # ── 4. 评论关键词分析 ──
    lines.append("---")
    lines.append("## 4. 评论关键词分析（观众真实关注点）")
    lines.append("")

    if all_comments:
        comment_texts = [c.get("text", "") for c in all_comments if c.get("text")]
        all_comment_words = []
        comment_stop = stop_words | {"video", "like", "just", "one", "really", "would",
                                      "much", "make", "get", "know", "think", "even",
                                      "also", "could", "good", "more", "very", "than",
                                      "been", "still", "way", "see", "need", "let",
                                      "every", "most", "find", "many", "some", "great",
                                      "things", "people", "thank", "thanks", "love"}
        for text in comment_texts:
            words = re.findall(r"[a-zA-Z']+", text.lower())
            all_comment_words.extend([w for w in words if w not in comment_stop and len(w) > 3])

        comment_freq = Counter(all_comment_words).most_common(30)
        lines.append("### 4.1 评论高频词（去除常见停用词后）")
        lines.append("| 排名 | 词 | 出现次数 | 可能含义 |")
        lines.append("|------|-----|---------|---------|")

        # 简单的语义分类
        categories = {
            "情感/心理": {"anxiety", "fear", "stress", "peace", "calm", "happy", "sad", "angry",
                         "depression", "mental", "mindset", "confidence", "courage", "hope",
                         "struggle", "suffering", "pain", "emotion", "feeling", "worry"},
            "哲学/智慧": {"wisdom", "philosophy", "stoic", "stoicism", "meditations", "virtue",
                         "truth", "meaning", "purpose", "enlightenment", "consciousness",
                         "spirituality", "mindfulness", "awareness", "tao", "zen", "buddha"},
            "职场/生活": {"work", "career", "job", "boss", "money", "success", "goal",
                         "interview", "business", "leadership", "productivity", "habit",
                         "discipline", "morning", "routine", "health", "relationship"},
            "内容反馈": {"content", "channel", "subscribe", "amazing", "beautiful",
                         "recommend", "listen", "watching", "learned", "helpful", "best"},
        }

        for i, (word, count) in enumerate(comment_freq, 1):
            category = "—"
            for cat, words_set in categories.items():
                if word in words_set:
                    category = cat
                    break
            lines.append(f"| {i} | {word} | {count} | {category} |")
        lines.append("")

        # 情感倾向粗略统计
        positive_words = {"love", "great", "amazing", "beautiful", "excellent", "wonderful",
                          "best", "perfect", "awesome", "helpful", "inspiring", "brilliant",
                          "thank", "thanks", "learned", "changed", "powerful"}
        negative_words = {"bad", "hate", "worst", "terrible", "boring", "wrong",
                          "waste", "disappointed", "unfortunately", "problem", "struggle",
                          "anxiety", "stress", "fear", "depression", "pain"}

        all_lower = " ".join(comment_texts).lower()
        pos_count = sum(all_lower.count(w) for w in positive_words)
        neg_count = sum(all_lower.count(w) for w in negative_words)
        total_sent = pos_count + neg_count
        lines.append("### 4.2 评论情感倾向")
        if total_sent > 0:
            lines.append(f"- 正面词频: {pos_count} ({pos_count/total_sent:.0%})")
            lines.append(f"- 负面/痛点词频: {neg_count} ({neg_count/total_sent:.0%})")
            lines.append(f"- 解读: 正面词代表内容共鸣，负面/痛点词代表观众真实困境 → 两者都是选题灵感来源")
        lines.append("")

    # ── 5. 频道规模 vs 增长交叉分析 ──
    lines.append("---")
    lines.append("## 5. 频道规模 vs 增长率交叉分析")
    lines.append("")

    if reliable_channels:
        lines.append("| 频道 | 订阅量级 | 增长倍率 | 值得关注原因 |")
        lines.append("|------|---------|---------|------------|")
        for ch in reliable_channels:
            subs = ch["subs"]
            ratio = ch["growth"]["growth_ratio"]
            if subs < 50000:
                size = "小型(<50K)"
            elif subs < 500000:
                size = "中型(50K-500K)"
            else:
                size = "大型(>500K)"

            reason = ""
            if ratio and ratio >= 2 and subs < 100000:
                reason = "⭐ 小频道高增长 — 最值得研究其冷启动方法"
            elif ratio and ratio >= 1.5 and subs >= 100000:
                reason = "📌 大频道仍在增长 — 内容策略值得借鉴"
            elif ratio and ratio < 0.7:
                reason = "⚠️ 下滑中 — 研究其错误以避免"
            else:
                reason = "参考价值中等"

            lines.append(f"| {ch['name']} | {size} | {ratio}x | {reason} |")
        lines.append("")

    # ── 6. 关键发现与建议 ──
    lines.append("---")
    lines.append("## 6. Copilot 关键发现与建议")
    lines.append("")
    lines.append("以下建议基于纯数据统计，不含 AI 推测：")
    lines.append("")

    findings = []
    # 时长建议
    if "duration_minutes" in combined_df.columns:
        dur_df = combined_df[combined_df["duration_minutes"] > 0]
        if not dur_df.empty:
            bins = [0, 5, 10, 15, 25, float("inf")]
            labels = ["<5min", "5-10min", "10-15min", "15-25min", ">25min"]
            dur_df = dur_df.copy()
            dur_df["dur_bin"] = pd.cut(dur_df["duration_minutes"], bins=bins, labels=labels)
            bin_median = dur_df.groupby("dur_bin", observed=True)["view_count"].median()
            if not bin_median.empty:
                best = bin_median.idxmax()
                findings.append(f"1. **最佳视频时长**: 数据显示 **{best}** 的中位播放量最高。新频道建议先从这个区间开始测试。")

    # 标题建议
    if not combined_df.empty:
        num_median = combined_df[combined_df["has_number"]]["view_count"].median() if combined_df["has_number"].any() else 0
        no_num_median = combined_df[~combined_df["has_number"]]["view_count"].median()
        if num_median > no_num_median * 1.2:
            findings.append(f"2. **标题含数字更好**: 含数字标题中位播放 {int(num_median):,} vs 无数字 {int(no_num_median):,}，建议多用\"5 Ways...\"\"7 Rules...\"等格式。")
        else:
            findings.append(f"2. **标题数字效果不显著**: 含数字 {int(num_median):,} vs 无数字 {int(no_num_median):,}，标题是否含数字对播放量影响不大。")

        q_median = combined_df[combined_df["has_question"]]["view_count"].median() if combined_df["has_question"].any() else 0
        no_q_median = combined_df[~combined_df["has_question"]]["view_count"].median()
        if q_median > no_q_median * 1.2:
            findings.append(f"3. **问句标题更吸引人**: 问句中位播放 {int(q_median):,} vs 陈述 {int(no_q_median):,}。")
        else:
            findings.append(f"3. **问句 vs 陈述差异不大**: 问句 {int(q_median):,} vs 陈述 {int(no_q_median):,}。")

    # 发布模式建议
    if publish_patterns_by_channel:
        all_best_days = [p["best_day"] for p in publish_patterns_by_channel.values()]
        most_common_day = Counter(all_best_days).most_common(1)[0]
        findings.append(f"4. **最热门发布日**: {most_common_day[0]}（{most_common_day[1]}/{len(publish_patterns_by_channel)}个频道），但每个频道差异大，建议自行测试。")

    # 增长模式发现
    if reliable_channels:
        small_growers = [ch for ch in reliable_channels if ch["subs"] < 100000 and ch["growth"]["growth_ratio"] and ch["growth"]["growth_ratio"] >= 1.5]
        if small_growers:
            names = ", ".join(ch["name"] for ch in small_growers[:3])
            findings.append(f"5. **重点研究对象**: {names} — 这些小频道（<100K订阅）仍保持增长，其冷启动和内容策略最值得新频道借鉴。")

    findings.append(f"6. **数据局限性提醒**: 本分析基于 {len(combined_df)} 个视频样本，部分频道在固定时间窗口内视频数不足，增长数据可能不够稳健。建议结合 Social Blade 等工具交叉验证。")

    for f in findings:
        lines.append(f)
        lines.append("")

    return "\n".join(lines)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    monitor = WorkflowMonitor(
        phase="CLI Pipeline v5",
        keyword=NICHE,
        metadata={
            "style": CHANNEL_STYLE,
            "search_keywords": len(SEARCH_KEYWORDS),
            "growth_window_months": GROWTH_WINDOW_MONTHS,
        },
    )
    monitor_path = os.path.join(OUTPUT_DIR, f"workflow_monitor_v5_{timestamp}.json")

    print("=" * 70)
    print("🎯 YouTube Competitive Research v5 — 从0到1实战指南")
    print(f"   Niche: {NICHE}")
    print(f"   Style: {CHANNEL_STYLE}")
    print(f"   Keywords: {len(SEARCH_KEYWORDS)}")
    print(f"   Growth window: {GROWTH_WINDOW_MONTHS} months (fixed, no fallback)")
    print("=" * 70)

    strategy_brief = StrategyBrief(
        content_direction=str(RESEARCH_PROFILE["content_direction"]),
        creator_stage="cold_start",
        primary_goal=PrimaryGoal.BREAKOUT_GROWTH.value,
        workflow_mode="analysis_quality",
        output_language="zh",
        delivery_mode="single_report",
        niche=NICHE,
        strategy_keywords=list(SEARCH_KEYWORDS[:4]),
        discovery_keywords=SEARCH_KEYWORDS,
        format_preferences=["screen recording", "voiceover", "result demo"],
        production_constraints={"team_model": "solo"},
        success_definition={"primary_goal": PrimaryGoal.BREAKOUT_GROWTH.value},
    )
    channel_evolution = {}
    viral_outliers = {}
    decline_diagnostics = []
    decline_summary = "当前样本中没有进入可靠下滑诊断范围的频道。"

    # ══════════════════════════════════════════════════════════
    # PHASE 1: 数据采集（同 v4）
    # ══════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("📡 PHASE 1: DATA COLLECTION")
    print("─" * 70)

    with monitor.stage("initialize_apis"):
        print("\n[1/6] Initializing APIs...")
        missing_env = [
            name
            for name, value in (
                ("YOUTUBE_API_KEY", YOUTUBE_API_KEY),
                ("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY),
            )
            if not value
        ]
        if missing_env:
            print("❌ Missing required environment variables: " + ", ".join(missing_env))
            monitor.write_json(monitor_path)
            return 1

        from core.fetcher import YouTubeFetcher
        from core.ai_analyzer import AIAnalyzer

        fetcher = YouTubeFetcher(YOUTUBE_API_KEY)
        if not fetcher.validate_api_key():
            print("❌ YouTube API Key 无效")
            monitor.write_json(monitor_path)
            return 1
        print("   ✅ YouTube API ready")

        ai = AIAnalyzer(DEEPSEEK_API_KEY, model=DEEPSEEK_MODEL, profile=RESEARCH_PROFILE)
        if not ai.validate_key():
            print("❌ DeepSeek API Key 无效")
            monitor.write_json(monitor_path)
            return 1
        print(f"   ✅ DeepSeek AI ready ({DEEPSEEK_MODEL})")

    # ── Step 2: 搜索频道 ──
    with monitor.stage("search_channels"):
        print(f"\n[2/6] Searching channels ({len(SEARCH_KEYWORDS)} keywords)...")
        all_channels = {}
        for kw in SEARCH_KEYWORDS:
            print(f"   🔍 '{kw}'...", end=" ", flush=True)
            try:
                channels = fetcher.search_channels(kw, max_results=MAX_CHANNELS_PER_KEYWORD)
                new_count = sum(1 for ch in channels if ch["channel_id"] not in all_channels)
                for ch in channels:
                    if ch["channel_id"] not in all_channels:
                        all_channels[ch["channel_id"]] = ch
                print(f"{len(channels)} found ({new_count} new)")
            except Exception as e:
                print(f"⚠️ {e}")

        if not all_channels:
            print("❌ 未找到任何频道")
            monitor.write_json(monitor_path)
            return 1

        print(f"\n   🧹 Filtering {len(all_channels)} raw channels...")
        filtered = {}
        for k, v in all_channels.items():
            subs = v.get("subscriber_count", 0)
            total_views = v.get("view_count", 0)
            video_count = max(v.get("video_count", 1), 1)
            avg_views = total_views / video_count
            if subs < MIN_SUBSCRIBER_COUNT or subs > MAX_SUBSCRIBER_COUNT or avg_views < MIN_AVG_VIEWS:
                continue
            filtered[k] = v

        if not filtered:
            filtered = {k: v for k, v in all_channels.items() if v.get("subscriber_count", 0) >= 1000}
            if not filtered:
                filtered = all_channels

        sorted_channels = sorted(filtered.values(), key=lambda x: x.get("subscriber_count", 0), reverse=True)
        top_channels = sorted_channels[:MAX_CHANNELS_TOTAL]

        print(f"   ✅ Selected {len(top_channels)} channels:")
        for ch in top_channels:
            print(f"      • {ch['title']} ({ch['subscriber_count']:,} subs)")

    # ── Step 3: 抓取视频 ──
    with monitor.stage("fetch_videos"):
        print(f"\n[3/6] Fetching videos ({MAX_VIDEOS_PER_CHANNEL}/channel)...")
        channels_data = {}
        all_videos_list = []

        for i, ch in enumerate(top_channels):
            ch_id = ch["channel_id"]
            print(f"   [{i+1}/{len(top_channels)}] {ch['title']}...", end=" ", flush=True)
            try:
                videos_df = fetcher.get_channel_videos(ch_id, max_videos=MAX_VIDEOS_PER_CHANNEL)
                growth = detect_growth_v5(videos_df)
                channels_data[ch_id] = {"info": ch, "videos": videos_df, "growth": growth}
                if not videos_df.empty:
                    all_videos_list.append(videos_df)
                ratio_str = f"{growth['growth_ratio']}x" if growth['growth_ratio'] is not None else "N/A"
                print(f"✅ {len(videos_df)} videos | {growth['status_emoji']} {ratio_str} ({growth['time_window']})")
            except Exception as e:
                print(f"⚠️ {e}")

        if not all_videos_list:
            print("❌ 未获取到视频数据")
            monitor.write_json(monitor_path)
            return 1

        combined_df = pd.concat(all_videos_list, ignore_index=True)
        print(f"\n   📊 Total: {len(combined_df)} videos from {len(channels_data)} channels")

    # ── Step 4: 抓取评论 ──
    with monitor.stage("fetch_comments"):
        print(f"\n[4/6] Fetching comments (prioritizing topic-aligned videos with >{MIN_VIDEO_VIEWS_FOR_COMMENT:,} views)...")
        all_comments = []
        qualified = _select_research_videos(combined_df, MIN_VIDEO_VIEWS_FOR_COMMENT, TOP_N_COMMENTS_VIDEOS)

        for _, vid in qualified.iterrows():
            print(f"   💬 [{vid['view_count']:,}] {vid['title'][:50]}...", end=" ", flush=True)
            try:
                comments = fetcher.get_video_comments(vid["video_id"], max_comments=MAX_COMMENTS_PER_VIDEO)
                all_comments.extend(comments)
                print(f"✅ {len(comments)}")
            except Exception as e:
                print(f"⚠️ {e}")

        print(f"   📝 Total: {len(all_comments)} comments")

    # ── Step 5: 抓取字幕 ──
    with monitor.stage("fetch_transcripts"):
        print(f"\n[5/6] Fetching transcripts (prioritizing topic-aligned videos)...")
        transcripts = {}
        video_info_map = {}

        transcript_candidates = _select_research_videos(combined_df, MIN_VIDEO_VIEWS_FOR_TRANSCRIPT, TOP_N_TRANSCRIPT_VIDEOS)

        for _, vid in transcript_candidates.iterrows():
            vid_id = vid["video_id"]
            video_info_map[vid_id] = {
                "title": vid["title"],
                "channel_title": vid.get("channel_title", ""),
                "view_count": vid["view_count"],
                "thumbnail": vid.get("thumbnail", ""),
            }
            print(f"   📝 [{vid['view_count']:,}] {vid['title'][:50]}...", end=" ", flush=True)
            try:
                text = fetcher.get_video_transcript(vid_id, languages=["en", "en-US", "en-GB"])
                if text and len(text) > 100:
                    transcripts[vid_id] = text
                    print(f"✅ {len(text)} chars")
                else:
                    print("⚠️ no transcript")
            except Exception as e:
                print(f"⚠️ {e}")

        print(f"   📝 Got transcripts for {len(transcripts)}/{len(transcript_candidates)} videos")

    # ── Step 6: 计算基础指标 ──
    with monitor.stage("compute_metrics"):
        print(f"\n[6/6] Computing metrics...")
        from core.analyzer import compute_metrics, analyze_duration_sweet_spot, analyze_channel_evolution
        from core.growth_detector import detect_viral_outliers

        combined_df = compute_metrics(combined_df)
        for ch_id, data in channels_data.items():
            if not data["videos"].empty:
                data["videos"] = compute_metrics(data["videos"])
                channel_evolution[ch_id] = analyze_channel_evolution(data["videos"])
                viral_outliers[ch_id] = detect_viral_outliers(data["videos"])

        duration_analysis = analyze_duration_sweet_spot(combined_df)
        publish_patterns_by_channel = analyze_publish_patterns_per_channel(channels_data)
        transcript_insights = analyze_transcript_patterns(transcripts, video_info_map) if transcripts else {"has_data": False}

        for _, vid in combined_df.iterrows():
            if vid["video_id"] not in video_info_map:
                video_info_map[vid["video_id"]] = {
                    "title": vid["title"],
                    "channel_title": vid.get("channel_title", ""),
                    "view_count": vid["view_count"],
                    "thumbnail": vid.get("thumbnail", ""),
                }

        print("   ✅ Done")

    with monitor.stage("competitor_radar"):
        print("\n[Strategy] Building deterministic competitor radar...")
        radar_results = build_competitor_radar(channels_data, strategy_brief)
        shortlist_titles = radar_results.get("summary", {}).get("shortlist_titles", [])
        if shortlist_titles:
            print("   ✅ Radar shortlist: " + " | ".join(shortlist_titles[:5]))
        else:
            print("   ⚠️ Radar shortlist empty")

    reverse_engineering_playbook = build_reverse_engineering_playbook(
        brief=strategy_brief,
        radar_results=radar_results,
        transcript_insights=transcript_insights,
        top_videos_df=_select_research_videos(combined_df, 0, 10),
    )
    decline_diagnostics = analyze_decline_drivers(
        channels_data,
        strategy_brief=strategy_brief,
        viral_outliers=viral_outliers,
        evolution_insights=channel_evolution,
    )
    decline_summary = format_decline_diagnostics(decline_diagnostics)
    strategy_plan = generate_strategy_plan(
        channels_data=channels_data,
        niche_description=NICHE,
        strategy_brief=strategy_brief,
        radar_results=radar_results,
        reverse_engineering_playbook=reverse_engineering_playbook,
        transcript_insights=transcript_insights,
    )

    # ══════════════════════════════════════════════════════════
    # PHASE 2: AI 深度分析 (10 轮)
    # ══════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("🧠 PHASE 2: AI DEEP ANALYSIS (DeepSeek)")
    print("─" * 70)

    with monitor.stage("ai_deep_analysis"):
        # ── AI 1: TOP 3 频道 ──
        print("\n[AI 1/10] Analyzing top 3 channels...")
        top3_result = _ai_top3_channels(ai, channels_data)
        print("   ✅ Done")

        # ── AI 2: TOP 10 视频（含视觉制作分析）──
        print("\n[AI 2/10] Analyzing top 10 videos (visual production patterns)...")
        top10_result = _ai_top10_videos(ai, combined_df, transcripts, video_info_map)
        print("   ✅ Done")

        # ── AI 3: 字幕内容结构分析 ──
        print("\n[AI 3/10] Deep analyzing transcript content patterns...")
        if transcripts:
            transcript_result = ai.analyze_transcripts_deep(transcripts, video_info_map)
        else:
            transcript_result = "未获取到足够字幕数据"
        print("   ✅ Done")

        # ── AI 4: 评论痛点分析 ──
        print("\n[AI 4/10] Deep analyzing audience pain points...")
        if all_comments:
            comment_result = ai.analyze_comments_deep(all_comments, video_info_map)
        else:
            comment_result = "未获取到评论数据"
        print("   ✅ Done")

        # ── AI 5: 从0到1完整实战指南 ──
        print("\n[AI 5/10] Generating 0-to-1 practical guide...")
        practical_guide = _ai_practical_guide_v5(
            ai, top3_result, top10_result, transcript_result, comment_result, channels_data
        )
        print("   ✅ Done")

        # ── AI 6: 频道制作指南 ──
        print("\n[AI 6/10] Channel production guide...")
        noface_guide = _ai_noface_production_guide(ai, transcript_result, top10_result)
        print("   ✅ Done")

        # ── AI 7: SEO 策略 ──
        print("\n[AI 7/10] SEO & keyword strategy...")
        seo_result = _ai_seo_strategy(ai, combined_df, channels_data, top10_result)
        print("   ✅ Done")

        # ── AI 8: 变现路径 ──
        print("\n[AI 8/10] Analyzing monetization paths...")
        monetization_result = _ai_monetization_analysis(ai, channels_data, comment_result)
        print("   ✅ Done")

        print("\n[AI 9/10] Building concise analysis digest...")
        analysis_digest = _ai_analysis_digest(
            ai,
            top3_result,
            top10_result,
            transcript_result,
            comment_result,
            seo_result,
            monetization_result,
            decline_summary,
            strategy_plan,
        )
        print("   ✅ Done")

        print("\n[AI 10/10] Building execution manual...")
        execution_manual = _ai_execution_manual(
            ai,
            practical_guide,
            noface_guide,
            seo_result,
            decline_summary,
            strategy_plan,
        )
        print("   ✅ Done")

    # ══════════════════════════════════════════════════════════
    # PHASE 3: 生成四份报告
    # ══════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("📄 PHASE 3: GENERATING 4 REPORTS")
    print("─" * 70)

    with monitor.stage("generate_reports"):
        # ── 报告 1: DeepSeek AI 分析报告 ──
        print("\n[Report 1/4] DeepSeek AI analysis report...")
        report_md = _build_deepseek_report(
            channels_data, combined_df, duration_analysis, publish_patterns_by_channel,
            analysis_digest, decline_diagnostics,
            transcripts, video_info_map, timestamp, strategy_plan=strategy_plan
        )
        md_path = os.path.join(OUTPUT_DIR, f"DeepSeek分析报告_v5_{timestamp}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"   ✅ {md_path}")

        # ── 报告 2: 执行手册 ──
        print("\n[Report 2/4] Execution manual...")
        execution_manual_path = os.path.join(OUTPUT_DIR, f"执行手册_v5_{timestamp}.md")
        with open(execution_manual_path, "w", encoding="utf-8") as f:
            f.write(execution_manual)
        print(f"   ✅ {execution_manual_path}")

        # ── 报告 3: Copilot 数据分析报告 ──
        print("\n[Report 3/4] Copilot statistical analysis report...")
        copilot_md = _build_copilot_report(
            channels_data, combined_df, duration_analysis,
            publish_patterns_by_channel, transcripts, video_info_map,
            all_comments, timestamp, radar_results=radar_results, strategy_brief=strategy_brief,
            reverse_engineering_playbook=reverse_engineering_playbook, strategy_plan=strategy_plan,
            decline_diagnostics=decline_diagnostics,
        )
        copilot_path = os.path.join(OUTPUT_DIR, f"Copilot数据报告_v5_{timestamp}.md")
        with open(copilot_path, "w", encoding="utf-8") as f:
            f.write(copilot_md)
        print(f"   ✅ {copilot_path}")

        # ── 报告 4: 评估报告 ──
        print("\n[Report 4/4] Evaluation report...")
        eval_report = _ai_self_evaluation(ai, report_md, copilot_md)
        eval_path = os.path.join(OUTPUT_DIR, f"报告评估_v5_{timestamp}.md")
        with open(eval_path, "w", encoding="utf-8") as f:
            f.write(eval_report)
        print(f"   ✅ {eval_path}")

        # ── 保存数据文件 ──
        csv_path = os.path.join(OUTPUT_DIR, "videos_data_v5.csv")
        export_cols = [c for c in combined_df.columns if c not in ("thumbnail",)]
        combined_df[export_cols].to_csv(csv_path, index=False, encoding="utf-8-sig")

        if all_comments:
            comments_csv = os.path.join(OUTPUT_DIR, "comments_data_v5.csv")
            comments_df = pd.DataFrame(all_comments)
            comments_df.to_csv(comments_csv, index=False, encoding="utf-8-sig")

        if transcripts:
            transcripts_path = os.path.join(OUTPUT_DIR, f"transcripts_v5_{timestamp}.json")
            transcript_export = {
                vid_id: {
                    "title": video_info_map.get(vid_id, {}).get("title", ""),
                    "channel": video_info_map.get(vid_id, {}).get("channel_title", ""),
                    "views": video_info_map.get(vid_id, {}).get("view_count", 0),
                    "text": text,
                }
                for vid_id, text in transcripts.items()
            }
            with open(transcripts_path, "w", encoding="utf-8") as f:
                json.dump(transcript_export, f, ensure_ascii=False, indent=2)

    # ── 完成 ──
    print("\n" + "=" * 70)
    print("🎉 v5 Analysis Complete!")
    print(f"   📄 DeepSeek Report: {md_path}")
    print(f"   📘 Execution Manual: {execution_manual_path}")
    print(f"   📊 Copilot Report:  {copilot_path}")
    print(f"   📝 Evaluation:      {eval_path}")
    print(f"   📺 Channels: {len(channels_data)}")
    print(f"   📹 Videos: {len(combined_df)}")
    print(f"   💬 Comments: {len(all_comments)}")
    print(f"   📝 Transcripts: {len(transcripts)}")
    print(f"   🧠 AI analyses: 10 + evaluation")
    print(f"   🧪 Workflow Monitor: {monitor_path}")
    print("=" * 70)

    monitor.set_summary(
        channels=len(channels_data),
        videos=len(combined_df),
        comments=len(all_comments),
        transcripts=len(transcripts),
    )
    monitor.add_metadata(
        deepseek_report=md_path,
        execution_manual=execution_manual_path,
        copilot_report=copilot_path,
        evaluation_report=eval_path,
        strategy_brief=strategy_brief.to_dict(),
        radar_shortlist=radar_results.get("summary", {}).get("shortlist_titles", []),
        strategy_plan=strategy_plan,
        decline_diagnostics=decline_diagnostics,
    )
    monitor.write_json(monitor_path)
    return 0


# ══════════════════════════════════════════════════════════════
# AI 分析函数 v5
# ══════════════════════════════════════════════════════════════

def _ai_top3_channels(ai, channels_data):
    """分析最值得关注的3个频道"""
    system = f"""你是一位资深 YouTube 频道增长策略专家。
用户当前频道画像：
{_profile_text()}

你的任务：从竞品数据中挑出最值得关注的 3 个频道。

注意：
- 增长数据标注了"可靠"或"不可靠"，不可靠的增长倍率请谨慎引用
- 分析时引用具体的时间窗口数据
- 不要笼统建议，要具体到「这个频道的XX视频用了XX手法，播放量是均值的XX倍」
用中文回答。"""

    channel_summaries = []
    for ch_id, data in channels_data.items():
        info = data.get("info", {})
        growth = data.get("growth", {})
        vids = data.get("videos", pd.DataFrame())

        top5 = ""
        if not vids.empty:
            top = vids.nlargest(5, "view_count")
            top5 = "\n".join(
                f"    - [{r['view_count']:,} views] {r['title']}"
                for _, r in top.iterrows()
            )

        avg_views = int(vids["view_count"].mean()) if not vids.empty else 0
        max_views = int(vids["view_count"].max()) if not vids.empty else 0
        avg_dur = round(vids["duration_minutes"].mean(), 1) if not vids.empty and "duration_minutes" in vids.columns else 0
        ratio_str = str(growth.get("growth_ratio", "N/A"))
        reliable = "✅可靠" if growth.get("reliable") else "⚠️不可靠"

        channel_summaries.append(
            f"""频道: {info.get('title', 'Unknown')}
  订阅: {info.get('subscriber_count', 0):,}
  平均播放: {avg_views:,} | 最高播放: {max_views:,}
  增长倍率: {ratio_str}x ({growth.get('status', '')}) [{reliable}]
  增长时间窗口: {growth.get('time_window', 'N/A')}
  近期均播: {growth.get('avg_recent_views', 0):,} | 早期均播: {growth.get('avg_older_views', 0):,}
  平均时长: {avg_dur}分钟
  TOP 5 视频:
{top5}"""
        )

    user = f"""以下是 {len(channels_data)} 个竞品频道数据。

请选出最值得关注的 3 个频道，每个频道分析：
1. 为什么值得关注（数据支撑，引用时间窗口）
2. 内容策略（从标题和播放量差异推断）
3. 增长模式（仅引用标注为"可靠"的数据）
4. 可借鉴的具体做法（至少3条可执行）
5. 与用户频道画像的关联度

频道数据：
{'='*60}
{chr(10).join(channel_summaries)}
"""
    return ai._call(system, user, max_tokens=4096)


def _ai_top10_videos(ai, videos_df, transcripts, video_info_map):
    """Top 10 视频分析，增加视觉制作风格分析"""
    system = f"""你是一位资深 YouTube 内容策略专家。
用户当前频道画像：
{_profile_text()}

你的任务：挑出最值得深入研究的 10 个视频。

对每个视频分析：
1. 为什么值得研究（数据支撑）
2. 标题套路分析
3. 缩略图/封面风格（从URL推断：深色/浅色、文字/人物、插画风格）
4. 内容结构（如有字幕：开头hook、展开方式、结尾CTA）
5. **当前频道形式如何复制此视频的视觉呈现**（具体到：用什么画面、什么动画风格、什么工具）
6. 类似选题建议（结合当前频道画像，标题必须符合频道语言要求）

用中文回答。"""

    if videos_df.empty:
        return "无视频数据"

    prioritized = _select_research_videos(videos_df, 0, 40)
    top_views = prioritized.nlargest(30, "view_count")
    top_eng = prioritized[prioritized["view_count"] >= 5000].nlargest(20, "engagement_rate") if "engagement_rate" in prioritized.columns else pd.DataFrame()
    candidates = pd.concat([top_views, top_eng]).drop_duplicates(subset="video_id") if not top_eng.empty else top_views

    video_entries = []
    for _, v in candidates.iterrows():
        vid_id = v["video_id"]
        transcript_text = transcripts.get(vid_id, "")
        transcript_preview = transcript_text[:500] + "..." if len(transcript_text) > 500 else transcript_text
        thumbnail_url = v.get("thumbnail", video_info_map.get(vid_id, {}).get("thumbnail", ""))

        video_entries.append(
            f"""视频: {v['title']}
  频道: {v.get('channel_title', '')}
  播放量: {v['view_count']:,} | 点赞: {v['like_count']:,} | 评论: {v['comment_count']:,}
  参与率: {v.get('engagement_rate', 0):.2%}
  时长: {v.get('duration_minutes', 0):.1f}分钟
  缩略图URL: {thumbnail_url}
  字幕摘要: {transcript_preview if transcript_preview else '（无字幕）'}"""
        )

    user = f"""以下是 {len(candidates)} 个候选视频。请选出10个最值得深入研究的，按推荐优先级排序。

重点：
- 分析每个视频如果用当前频道形式应该如何制作
- 建议的选题标题必须符合当前频道设定的语言

{chr(10).join(video_entries)}
"""
    return ai._call(system, user, max_tokens=6000)


def _ai_practical_guide_v5(ai, top3, top10, transcript, comment, channels_data):
    """v5: 从0到1完整实战指南"""
    system = f"""你是一位资深 YouTube 增长教练，专门帮助0订阅新频道实现冷启动。

用户情况：
- 全新频道（0订阅）
{_profile_text()}
- 一个人操作，时间精力有限

**你必须输出一份详尽的从0到1实战手册，包含以下所有章节：**

### 第一章：选题方法论
- 如何找到高潜力选题的完整步骤（工具、流程、判断标准）
- 选题公式（至少3种可复制的选题套路）
- 前10个视频的具体选题+英文标题+选择理由

### 第二章：SEO 完整优化指南
- 标题SEO：关键词选择、标题结构、A/B测试方法
- 描述SEO：前3行写什么、关键词植入位置、模板
- 标签策略：核心标签、长尾标签、竞品标签
- 缩略图优化：当前频道形式下的缩略图设计规则
- 发布时间优化：基于数据的最佳发布策略

### 第三章：账号冷启动策略
- 第一个月的每周详细行动计划
- 获取前100个订阅者的具体方法（至少5种渠道）
- 如何利用YouTube Shorts做引流
- Reddit/Quora/社群推广的具体操作
- 算法如何对待新频道（你必须知道的规则）

### 第四章：视频制作流程
- 当前频道形式的完整制作pipeline（从选题到发布）
- 每集视频的时间投入估算
- 推荐工具清单

用中文回答。所有视频标题必须符合当前频道设定的语言。"""

    user = f"""以下是基于数据分析得出的洞察：

═══ TOP 3 频道分析（摘要）═══
{top3[:2000]}

═══ TOP 10 视频分析（摘要）═══
{top10[:2000]}

═══ 内容结构分析（摘要）═══
{transcript[:2000]}

═══ 观众痛点（摘要）═══
{comment[:2000]}

请基于以上数据输出完整的从0到1实战手册。
注意：这不是建议清单，而是可以直接执行的操作手册，每一步都要具体到"打开XX → 搜索XX → 选择XX"的程度。
"""
    return ai._call(system, user, max_tokens=8000)


def _ai_noface_production_guide(ai, transcript_result, top10_result):
    """频道制作完整指南"""
    system = f"""你是一位专精 YouTube 教程频道视觉设计和制作流程的专家。

用户当前频道画像：
{_profile_text()}

**你必须分析并给出以下内容：**

### 1. 频道视觉风格对比分析
列出至少5种适合当前频道形式的视觉风格（如：录屏+旁白、PPT动画、stock footage拼接、AI生成图片、白板动画、kinetic typography），对比每种的：
- 制作成本（时间和金钱）
- 视觉效果评分
- 观众接受度
- 适合的内容类型
- 推荐工具

### 2. 推荐的视觉风格方案
- 基于用户当前频道形式，给出：
- 具体实现方案（什么工具录屏、什么工具做标注动画、哪里找可用素材）
- 一个完整视频的视觉分镜示例（以当前频道画像下的代表选题为例）
- 每个场景的画面描述、时长、文字叠加

### 3. 缩略图设计规则
- 在当前频道形式下，缩略图如何吸引点击
- 5个具体的缩略图设计模板（含颜色方案、字体、构图）
- 推荐工具（Canva模板、Photopea等免费工具）

### 4. 制作一集视频的完整SOP
- 从脚本到成品的每个步骤
- 每步所需时间估算
- 总时间预算

用中文回答。"""

    user = f"""以下是竞品视频的内容结构和视觉分析：

═══ 视频内容结构 ═══
{transcript_result[:2000]}

═══ TOP 视频分析 ═══
{top10_result[:2000]}

请输出完整的频道制作指南。
"""
    return ai._call(system, user, max_tokens=6000)


def _ai_seo_strategy(ai, combined_df, channels_data, top10_result):
    """SEO关键词竞争分析"""
    system = f"""你是一位 YouTube SEO 专家。你精通 YouTube 搜索算法、关键词研究和内容优化。

用户要做的频道：
{_profile_text()}
- 当前是 0 订阅新频道

**你必须输出：**

### 1. 关键词竞争分析
分析以下每个关键词类别的搜索竞争程度，给出：
- 搜索量预估（高/中/低）
- 竞争激烈程度（红海/蓝海/中等）
- 新频道是否有机会排名
- 推荐的长尾变体

关键词类别：
- 直接赛道关键词
- 工具/任务型关键词
- 长尾问题型关键词
- 对标替代关键词
- 高意图教程型关键词
- 冷启动可切入关键词

### 2. 蓝海关键词机会
列出至少10个可能的蓝海关键词（搜索有需求但竞争低），附上推断理由

### 3. 前10个视频的SEO优化方案
对于每个建议的视频选题，给出：
- 主标题（SEO优化版，含核心关键词）
- 描述前3行（含关键词，引导点击）
- 标签建议（10-15个）
- 目标搜索意图

### 4. 频道级SEO设置
- 频道名称建议（3个选项，含SEO考量）
- 频道描述模板
- 频道关键词
- 播放列表分类策略

用中文回答。所有面向YouTube的内容（标题、描述、标签）必须符合当前频道设定的语言。"""

    # 提取标题词频作为输入
    if not combined_df.empty:
        all_titles = combined_df["title"].tolist()
        title_sample = "\n".join(f"- [{combined_df.iloc[i]['view_count']:,}] {t}" for i, t in enumerate(all_titles[:50]))
    else:
        title_sample = ""

    user = f"""以下是竞品频道和视频数据：

═══ 竞品视频标题（前50个，按播放量排序）═══
{title_sample}

═══ TOP 10 视频分析 ═══
{top10_result[:2000]}

请输出完整的 SEO 策略。
"""
    return ai._call(system, user, max_tokens=6000)


def _ai_monetization_analysis(ai, channels_data, comment_result):
    """变现路径分析"""
    system = f"""你是一位内容创作者变现策略专家。
用户要做的频道：
{_profile_text()}

输出：
1. 竞品变现模式分析
2. 分阶段变现路径规划（0-1K / 1K-10K / 10K+）
3. 具体产品建议（至少3个，含定价）
4. 变现时间线
5. 风险与注意事项

用中文回答。"""

    channel_info = []
    for ch_id, data in channels_data.items():
        info = data["info"]
        channel_info.append(
            f"- {info['title']} ({info.get('subscriber_count', 0):,} subs): "
            f"描述 = {info.get('description', '')[:200]}"
        )

    user = f"""竞品频道：
{chr(10).join(channel_info)}

观众痛点：
{comment_result[:2000]}

请输出变现策略分析。"""
    return ai._call(system, user, max_tokens=4000)


def _ai_analysis_digest(
    ai,
    top3_result,
    top10_result,
    transcript_result,
    comment_result,
    seo_result,
    monetization_result,
    decline_summary,
    strategy_plan,
):
    """将长分析压缩成适合快速阅读的短报告。"""
    system = f"""你是一位资深的 YouTube 策略总编。

用户当前频道画像：
{_profile_text()}

请把长分析材料压缩成一份精简分析报告。

要求：
1. 只保留最关键的判断和决策含义。
2. 必须包含：赛道结论、优先学习对象、包装/选题信号、下滑分析、30天战略建议、风险提示。
3. 如果字幕证据弱，要明确指出是代理信号，不要装作高确定性结论。
4. 用中文回答，控制在 6 个一级小节以内。
"""

    user = f"""请基于以下材料输出精简分析报告：

═══ Top Channels ═══
{top3_result[:2500]}

═══ Top Videos ═══
{top10_result[:2500]}

═══ Transcript Analysis ═══
{transcript_result[:1800]}

═══ Audience Pain Points ═══
{comment_result[:1800]}

═══ SEO ═══
{seo_result[:1800]}

═══ Monetization ═══
{monetization_result[:1500]}

═══ Decline Diagnostics ═══
{decline_summary[:1500]}

═══ Strategy Plan Snapshot ═══
北极星目标：{strategy_plan.get('north_star_goal', '')}
关键指标：{json.dumps(strategy_plan.get('key_metrics', {}), ensure_ascii=False)}
信心备注：{json.dumps(strategy_plan.get('confidence_notes', [])[:4], ensure_ascii=False)}
"""
    return ai._call(system, user, max_tokens=3500)


def _ai_execution_manual(ai, practical_guide, production_guide, seo_result, decline_summary, strategy_plan):
    """生成可直接照做的执行手册。"""
    system = f"""你是一位 YouTube 频道运营教练，擅长把研究结果压缩成执行手册。

用户当前频道画像：
{_profile_text()}

请输出一份“30天执行手册”，必须包含：
1. 一句话定位
2. 前10个视频 backlog（标题、目标、形式、为什么先做）
3. 第1-4周执行节奏
4. 单条视频 SOP
5. 发布前检查清单
6. 从下滑频道学到的避坑清单

要求：
- 以直接执行为目标，不要写成长分析报告
- 让新频道可以按表操作
- 用中文回答，但标题保持频道设定语言
"""

    user = f"""请基于以下材料输出执行手册：

═══ Practical Guide ═══
{practical_guide[:3500]}

═══ Production Guide ═══
{production_guide[:3000]}

═══ SEO Strategy ═══
{seo_result[:2200]}

═══ Decline Diagnostics ═══
{decline_summary[:1800]}

═══ Strategy Plan Snapshot ═══
北极星目标：{strategy_plan.get('north_star_goal', '')}
里程碑：{json.dumps(strategy_plan.get('milestones', [])[:3], ensure_ascii=False)}
每周规则：{json.dumps(strategy_plan.get('weekly_operating_rules', [])[:6], ensure_ascii=False)}
"""
    manual_body = ai._call(system, user, max_tokens=5000)
    return f"""# YouTube 执行手册 v5
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**赛道**: {NICHE}
**频道风格**: {CHANNEL_STYLE}

---

{manual_body}
"""


def _ai_self_evaluation(ai, deepseek_report, copilot_report):
    """评估 DeepSeek 报告 + 与 Copilot 报告对比"""
    system = """你是一位严格的报告审核专家。你要审核两份报告：
1. DeepSeek AI 分析报告：AI生成的竞品分析和策略建议
2. Copilot 数据报告：纯统计驱动的数据分析

审核维度（每项5分制）：
1. **数据可靠性**：增长倍率是否有统一口径？样本量是否标注？是否过度推断？
2. **逻辑严谨性**：推理有无跳跃？归因是否合理？
3. **可操作性**：建议是否具体到可立即执行？
4. **冷启动现实性**：对0订阅新频道是否现实？有无考虑资源限制？
5. **频道形式适配性**：视觉建议是否充分考虑了当前频道形式的限制？
6. **两份报告一致性**：AI结论与统计数据是否矛盾？矛盾点在哪？

你是审核者。请直接指出问题，给出修改方向。
用中文回答。"""

    # 截取两份报告的关键部分
    ds_preview = deepseek_report[:10000]
    copilot_preview = copilot_report[:5000]

    user = f"""请审核以下两份报告：

══════ 报告一：DeepSeek AI 分析报告 ══════
{ds_preview}

══════ 报告二：Copilot 数据报告 ══════
{copilot_preview}

请输出：

## 总体评分

## 各维度评估
### 数据可靠性 (X/5)
### 逻辑严谨性 (X/5)
### 可操作性 (X/5)
### 冷启动现实性 (X/5)
### 频道形式适配性 (X/5)
### 两份报告一致性 (X/5)

## 两份报告的关键矛盾/差异

## 具体问题清单

## 修改建议

## 综合评价
"""
    eval_result = ai._call(system, user, max_tokens=4000, temperature=0.5)

    return f"""# YouTube 竞品分析报告 — 综合评估
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**评估对象**: DeepSeek AI 报告 v5 + Copilot 数据报告 v5
**评估方法**: DeepSeek AI 独立审核（评估prompt与分析prompt完全独立）

---

{eval_result}

---
*注：此评估同时审核了 DeepSeek AI 报告和 Copilot 统计报告，对比两份报告的一致性与差异。*
"""


# ══════════════════════════════════════════════════════════════
# 报告生成
# ══════════════════════════════════════════════════════════════

def _build_deepseek_report(
    channels_data, combined_df, duration_analysis, publish_patterns_by_channel,
    analysis_digest, decline_diagnostics,
    transcripts, video_info_map, timestamp, strategy_plan=None
):
    """构建精简版的 DeepSeek 分析报告 v5"""
    lines = []
    lines.append("# YouTube 竞品分析报告 v5 — 精简版")
    lines.append(f"**赛道**: {NICHE}")
    lines.append(f"**频道风格**: {CHANNEL_STYLE}")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**数据规模**: {len(channels_data)} 频道 | {len(combined_df)} 视频 | {len(transcripts)} 字幕")
    lines.append(f"**增长分析窗口**: 固定 {GROWTH_WINDOW_MONTHS} 个月（无回退）")
    lines.append("")

    # ── 数据概览 ──
    lines.append("---")
    lines.append("## 1. 📊 数据概览")
    lines.append("")
    lines.append("### 频道增长分析")
    lines.append("| 频道 | 订阅 | 近期均播 | 早期均播 | 增长倍率 | 时间窗口 | 数据可靠性 | 状态 |")
    lines.append("|------|------|----------|----------|---------|---------|-----------|------|")
    for ch_id, data in channels_data.items():
        info = data["info"]
        growth = data["growth"]
        ratio_str = str(growth["growth_ratio"]) + "x" if growth["growth_ratio"] is not None else "N/A"
        reliable = "✅" if growth.get("reliable") else "⚠️不足"
        lines.append(
            f"| {info['title']} | {info['subscriber_count']:,} | "
            f"{growth.get('avg_recent_views', 0):,} | {growth.get('avg_older_views', 0):,} | "
            f"{ratio_str} | {growth.get('time_window', 'N/A')} | "
            f"{reliable} | {growth['status_emoji']} {growth['status']} |"
        )
    lines.append("")

    # 发布模式
    lines.append("### 各频道发布模式")
    lines.append("| 频道 | 最佳日 | 最佳时(UTC) | 频率 | 订阅 |")
    lines.append("|------|-------|-----------|------|------|")
    for ch_name, pat in publish_patterns_by_channel.items():
        lines.append(
            f"| {ch_name} | {pat['best_day']} | {pat['best_hour']}:00 | "
            f"{pat['frequency']} | {pat['subscriber_count']:,} |"
        )
    lines.append("")
    lines.append(f"**最佳视频时长**: {duration_analysis.get('best_range', 'N/A')}")
    lines.append("")

    lines.append("---")
    lines.append("## 2. 🧠 精简策略判断")
    lines.append("")
    lines.append(analysis_digest)
    lines.append("")

    if decline_diagnostics:
        lines.append("---")
        lines.append("## 3. 📉 下滑原因诊断")
        lines.append("")
        for item in decline_diagnostics:
            lines.append(f"### {item['channel_title']}")
            lines.append(f"- 判定：{item['classification_label']}")
            lines.append(f"- 结论：{item['summary']}")
            for reason in item.get("objective_factors", []):
                lines.append(f"- 客观因素：{reason}")
            for reason in item.get("strategy_factors", []):
                lines.append(f"- 策略因素：{reason}")
            lines.append("")

    if strategy_plan:
        lines.append("---")
        lines.append("## 4. 🎯 策略计划快照")
        lines.append("")
        if strategy_plan.get("north_star_goal"):
            lines.append(f"- 北极星目标：{strategy_plan.get('north_star_goal')}")
        for note in strategy_plan.get("confidence_notes", [])[:4]:
            lines.append(f"- {note}")
        lines.append("")

    # 附录
    lines.append("---")
    lines.append("## 📎 附录：字幕样本摘要")
    lines.append("")
    for vid_id, text in list(transcripts.items())[:5]:
        info = video_info_map.get(vid_id, {})
        lines.append(f"### {info.get('title', vid_id)}")
        lines.append(f"*{info.get('channel_title', '')} | {info.get('view_count', 0):,} views*")
        lines.append("```")
        lines.append(text[:800])
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
