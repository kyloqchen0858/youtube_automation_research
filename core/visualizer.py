"""
Visualizer — 数据可视化模块
生成 Plotly 交互图表（Streamlit 渲染）+ 静态图片导出（PDF 用）
中文字体全局配置，确保图表中文不乱码
"""

import io
import os
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from wordcloud import WordCloud

logger = logging.getLogger(__name__)

# ── 中文字体配置 ───────────────────────────────────────────
_FONT_CANDIDATES = ["SimHei", "Microsoft YaHei", "PingFang SC", "WenQuanYi Micro Hei", "Arial Unicode MS"]

def _get_chinese_font_path() -> str:
    """查找可用的中文字体文件路径"""
    # 先检查项目内置字体
    project_font = Path(__file__).parent.parent / "assets" / "fonts" / "SimHei.ttf"
    if project_font.exists():
        return str(project_font)

    # Windows 系统字体
    win_fonts = [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
    ]
    for f in win_fonts:
        if os.path.exists(f):
            return f

    # macOS
    mac_fonts = [
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for f in mac_fonts:
        if os.path.exists(f):
            return f

    # Linux
    linux_fonts = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for f in linux_fonts:
        if os.path.exists(f):
            return f

    return ""


_CHINESE_FONT_PATH = _get_chinese_font_path()

# matplotlib 中文配置
plt.rcParams["font.sans-serif"] = _FONT_CANDIDATES
plt.rcParams["axes.unicode_minus"] = False


# ── Plotly 图表 ────────────────────────────────────────────

def plot_top_videos_bar(videos_df: pd.DataFrame, metric: str = "view_count", n: int = 10) -> go.Figure:
    """播放量 TOP N 水平柱状图"""
    if videos_df.empty:
        return _empty_figure("无数据")

    top = videos_df.nlargest(n, metric).copy()
    top["short_title"] = top["title"].apply(lambda t: t[:30] + "..." if len(t) > 30 else t)
    top = top.sort_values(metric)

    metric_labels = {
        "view_count": "播放量",
        "like_count": "点赞数",
        "comment_count": "评论数",
        "engagement_rate": "互动率",
    }
    label = metric_labels.get(metric, metric)

    fig = px.bar(
        top,
        x=metric,
        y="short_title",
        orientation="h",
        title=f"🏆 {label} TOP {n} Videos",
        labels={metric: label, "short_title": "Video Title"},
        color=metric,
        color_continuous_scale="Viridis",
        hover_data={"title": True, metric: True, "channel_title": True},
    )
    fig.update_layout(
        height=max(400, n * 45),
        showlegend=False,
        yaxis_title="",
        coloraxis_showscale=False,
    )
    return fig


def plot_duration_scatter(videos_df: pd.DataFrame) -> go.Figure:
    """时长 vs 播放量散点图（颜色=互动率）"""
    if videos_df.empty:
        return _empty_figure("无数据")

    df = videos_df[videos_df["duration_minutes"] > 0].copy()
    if df.empty:
        return _empty_figure("无有效时长数据")

    color_col = "engagement_rate" if "engagement_rate" in df.columns else None

    fig = px.scatter(
        df,
        x="duration_minutes",
        y="view_count",
        color=color_col,
        size="view_count",
        hover_data={"title": True, "channel_title": True, "duration_minutes": ":.1f"},
        title="⏱️ Duration vs Views (Color = Engagement Rate)",
        labels={
            "duration_minutes": "Duration (minutes)",
            "view_count": "Views",
            "engagement_rate": "Engagement Rate",
        },
        color_continuous_scale="RdYlGn",
        size_max=20,
    )
    fig.update_layout(height=500)
    return fig


def plot_publish_heatmap(heatmap_data: pd.DataFrame) -> go.Figure:
    """发布时间热力图（星期 × 小时）"""
    if heatmap_data is None or heatmap_data.empty:
        return _empty_figure("无发布时间数据")

    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data.values,
            x=[f"{h}:00" for h in heatmap_data.columns],
            y=heatmap_data.index.tolist(),
            colorscale="YlOrRd",
            hoverongaps=False,
        )
    )
    fig.update_layout(
        title="📅 Publish Time Heatmap (Day × Hour)",
        xaxis_title="Hour (UTC)",
        yaxis_title="Day of Week",
        height=350,
    )
    return fig


def plot_channel_comparison_radar(comparison_df: pd.DataFrame) -> go.Figure:
    """频道对比雷达图"""
    if comparison_df.empty:
        return _empty_figure("无对比数据")

    # 标准化各指标到 0-100
    metrics = ["订阅数", "平均播放量", "最高播放量", "平均时长(分)", "增长倍率"]
    available_metrics = [m for m in metrics if m in comparison_df.columns]

    if not available_metrics:
        return _empty_figure("无可对比指标")

    df = comparison_df.copy()
    for m in available_metrics:
        col_max = pd.to_numeric(df[m], errors="coerce").max()
        if col_max > 0:
            df[f"{m}_norm"] = pd.to_numeric(df[m], errors="coerce") / col_max * 100
        else:
            df[f"{m}_norm"] = 0

    norm_cols = [f"{m}_norm" for m in available_metrics]

    fig = go.Figure()
    for _, row in df.iterrows():
        values = [row[c] for c in norm_cols]
        values.append(values[0])  # 闭合

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=available_metrics + [available_metrics[0]],
                fill="toself",
                name=row["频道名"],
                opacity=0.6,
            )
        )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="📊 Channel Comparison Radar",
        height=500,
        showlegend=True,
    )
    return fig


def plot_growth_trend(videos_df: pd.DataFrame, channel_title: str = "") -> go.Figure:
    """视频播放量趋势线（按发布时间）"""
    if videos_df.empty:
        return _empty_figure("无数据")

    df = videos_df.sort_values("published_at").copy()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["published_at"],
            y=df["view_count"],
            mode="lines+markers",
            name="Views",
            line=dict(color="#636EFA"),
            hovertext=df["title"],
        )
    )

    # 添加趋势线
    if len(df) > 3:
        x_num = np.arange(len(df))
        z = np.polyfit(x_num, df["view_count"].values, 1)
        p = np.poly1d(z)
        fig.add_trace(
            go.Scatter(
                x=df["published_at"],
                y=p(x_num),
                mode="lines",
                name="Trend",
                line=dict(color="red", dash="dash"),
            )
        )

    fig.update_layout(
        title=f"📈 Views Trend — {channel_title}" if channel_title else "📈 Views Trend",
        xaxis_title="Publish Date",
        yaxis_title="Views",
        height=400,
    )
    return fig


# ── Matplotlib 词云 ────────────────────────────────────────

def plot_title_wordcloud(keywords: dict[str, float], title: str = "📝 Title Keywords Word Cloud") -> plt.Figure:
    """标题高频词云（jieba 分词，中文字体）"""
    return _generate_wordcloud(keywords, title)


def plot_comment_wordcloud(keywords: dict[str, float], title: str = "💬 Comment Keywords Word Cloud") -> plt.Figure:
    """评论高频词云"""
    return _generate_wordcloud(keywords, title, colormap="magma")


def _generate_wordcloud(keywords: dict[str, float], title: str, colormap: str = "viridis") -> plt.Figure:
    """通用词云生成"""
    if not keywords:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No keywords data", ha="center", va="center", fontsize=16)
        ax.axis("off")
        return fig

    wc_params = dict(
        width=1200,
        height=600,
        background_color="white",
        max_words=100,
        colormap=colormap,
        prefer_horizontal=0.7,
    )

    if _CHINESE_FONT_PATH:
        wc_params["font_path"] = _CHINESE_FONT_PATH

    wc = WordCloud(**wc_params)
    wc.generate_from_frequencies(keywords)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(wc, interpolation="bilinear")
    ax.set_title(title, fontsize=16, pad=10)
    ax.axis("off")
    plt.tight_layout()
    return fig


# ── 工具函数 ───────────────────────────────────────────────

def _empty_figure(message: str = "No data") -> go.Figure:
    """生成空占位图"""
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font_size=20)
    fig.update_layout(height=300)
    return fig


def save_plotly_as_image(fig: go.Figure, filepath: str, width: int = 1000, height: int = 600):
    """将 Plotly 图表保存为 PNG（PDF 报告用）"""
    fig.write_image(filepath, width=width, height=height, scale=2)


def save_matplotlib_as_image(fig: plt.Figure, filepath: str, dpi: int = 150):
    """将 Matplotlib 图表保存为 PNG"""
    fig.savefig(filepath, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
