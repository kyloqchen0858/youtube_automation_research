"""
Report Generator — PDF 报告生成模块
使用 fpdf2 生成结构化的中英双语 PDF 报告
"""

import io
import os
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
import pandas as pd

logger = logging.getLogger(__name__)


def _normalize_output_language(output_language: str | None) -> str:
    return "en" if str(output_language or "").lower().startswith("en") else "zh"


def _t(output_language: str | None, zh: str, en: str) -> str:
    return en if _normalize_output_language(output_language) == "en" else zh


class ReportPDF(FPDF):
    """自定义 PDF 类，支持中文字体和页眉页脚"""

    def __init__(self, *args, output_language: str = "zh", **kwargs):
        super().__init__(*args, **kwargs)
        self.output_language = _normalize_output_language(output_language)
        self._font_registered = False
        self._register_chinese_font()

    def _register_chinese_font(self):
        """注册中文字体"""
        font_paths = [
            Path(__file__).parent.parent / "assets" / "fonts" / "SimHei.ttf",
            Path(r"C:\Windows\Fonts\simhei.ttf"),
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        ]

        for fp in font_paths:
            if fp.exists():
                try:
                    self.add_font("zh", "", str(fp), uni=True)
                    self.add_font("zh", "B", str(fp), uni=True)
                    self._font_registered = True
                    return
                except Exception as e:
                    logger.debug(f"字体注册失败 {fp}: {e}")

        logger.warning("未找到中文字体，PDF 中文可能显示异常")

    def _set_font_safe(self, style: str = "", size: int = 10):
        """安全设置字体"""
        if self._font_registered:
            self.set_font("zh", style, size)
        else:
            self.set_font("Helvetica", style, size)

    def header(self):
        if self.page_no() > 1:
            self._set_font_safe("", 8)
            self.set_text_color(150, 150, 150)
            self.cell(
                0,
                8,
                _t(self.output_language, "YouTube 竞品调研报告", "YouTube Competitive Research Report"),
                align="R",
            )
            self.ln(10)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), self.w - 10, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self._set_font_safe("", 8)
        self.set_text_color(150, 150, 150)
        self.cell(
            0,
            10,
            _t(self.output_language, f"第 {self.page_no()} 页 / {{nb}}", f"Page {self.page_no()}/{{nb}}"),
            align="C",
        )

    def chapter_title(self, title: str):
        self._set_font_safe("B", 16)
        self.set_text_color(30, 30, 30)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(66, 133, 244)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(8)

    def section_title(self, title: str):
        self._set_font_safe("B", 12)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text: str):
        self._set_font_safe("", 10)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def bullet_point(self, text: str):
        self._set_font_safe("", 10)
        self.set_text_color(60, 60, 60)
        self.cell(6, 6, "-")
        self.multi_cell(0, 6, text)
        self.ln(1)

    def add_kv_row(self, key: str, value: str):
        self._set_font_safe("B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(60, 7, key)
        self._set_font_safe("", 10)
        self.set_text_color(30, 30, 30)
        self.cell(0, 7, str(value), new_x="LMARGIN", new_y="NEXT")

    def add_simple_table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] = None):
        """添加简单表格"""
        if not col_widths:
            available = self.w - 20
            col_widths = [int(available / len(headers))] * len(headers)

        # Header
        self._set_font_safe("B", 9)
        self.set_fill_color(66, 133, 244)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, h[:15], border=1, fill=True, align="C")
        self.ln()

        # Rows
        self._set_font_safe("", 9)
        self.set_text_color(60, 60, 60)
        fill = False
        for row in rows:
            if self.get_y() > self.h - 30:
                self.add_page()
            if fill:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            for i, cell in enumerate(row):
                text = str(cell)[:20]
                self.cell(col_widths[i], 7, text, border=1, fill=True, align="C")
            self.ln()
            fill = not fill

    def safe_add_image(self, image_path: str, w: int = 180):
        """安全添加图片（自动处理分页）"""
        if not os.path.exists(image_path):
            self.body_text(_t(self.output_language, f"[未找到图片: {image_path}]", f"[Image not found: {image_path}]"))
            return
        if self.get_y() > self.h - 120:
            self.add_page()
        try:
            self.image(image_path, x=15, w=w)
            self.ln(5)
        except Exception as e:
            self.body_text(_t(self.output_language, f"[图片加载失败: {e}]", f"[Image load error: {e}]"))


def generate_report(
    niche: str,
    channels_data: dict,
    comparison_df: pd.DataFrame,
    top_videos_df: pd.DataFrame,
    duration_analysis: dict,
    publish_patterns: dict,
    title_keywords: dict,
    comment_keywords: dict,
    milestone_plan: dict,
    monetization: dict,
    content_strategy: dict,
    chart_paths: dict,
    rising_channels_df: pd.DataFrame = None,
    reliability_summary: dict = None,
    consistency_check: dict = None,
    viral_outliers: dict = None,
    evolution_insights: dict = None,
    transcript_insights: dict = None,
    output_language: str = "zh",
) -> bytes:
    """
    生成完整 PDF 报告

    Args:
        niche: 赛道描述
        channels_data: 频道数据 {channel_id: {'info':..., 'videos':..., 'growth':...}}
        comparison_df: 频道对比 DataFrame
        top_videos_df: TOP 视频 DataFrame
        duration_analysis: 时长分析结果
        publish_patterns: 发布模式分析结果
        title_keywords: 标题关键词
        comment_keywords: 评论关键词
        milestone_plan: 阶段目标
        monetization: 盈利预估
        content_strategy: 内容策略
        chart_paths: 图表文件路径 dict
        rising_channels_df: 暴涨频道 DataFrame
        reliability_summary: 数据可靠性摘要
        consistency_check: 建议一致性校验结果
        viral_outliers: 单爆款异常检测结果
        evolution_insights: 频道纵向演化结果
        transcript_insights: 字幕内容结构洞察结果

    Returns:
        PDF bytes
    """
    output_language = _normalize_output_language(output_language)
    translate = lambda zh, en: _t(output_language, zh, en)

    pdf = ReportPDF("P", "mm", "A4", output_language=output_language)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=25)

    # ── 封面 ────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(40)
    pdf._set_font_safe("B", 28)
    pdf.set_text_color(30, 30, 30)
    if output_language == "en":
        pdf.cell(0, 15, "YouTube Competitive", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 15, "Research Report", align="C", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 15, "YouTube 竞品调研报告", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf._set_font_safe("", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, f"{translate('赛道', 'Niche')}: {niche}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.cell(
        0,
        10,
        f"{translate('生成时间', 'Generated')}: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(20)

    pdf._set_font_safe("", 11)
    pdf.set_text_color(120, 120, 120)
    num_channels = len(channels_data)
    total_videos = sum(len(d.get("videos", [])) for d in channels_data.values())
    pdf.cell(
        0,
        8,
        translate(
            f"分析频道数: {num_channels}  |  扫描视频数: {total_videos}",
            f"Channels Analyzed: {num_channels}  |  Videos Scanned: {total_videos}",
        ),
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    # ── 第一章：赛道概览 ────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("1. 赛道概览", "1. Niche Overview"))

    pdf.section_title(translate("调研范围", "Research Scope"))
    pdf.add_kv_row(translate("赛道", "Niche"), niche)
    pdf.add_kv_row(translate("频道数", "Channels"), str(num_channels))
    pdf.add_kv_row(translate("视频数", "Videos"), str(total_videos))
    pdf.ln(5)

    if milestone_plan and milestone_plan.get("key_metrics"):
        pdf.section_title(translate("核心指标", "Key Metrics"))
        for k, v in milestone_plan["key_metrics"].items():
            pdf.add_kv_row(k, str(v))

    if reliability_summary:
        pdf.ln(4)
        pdf.section_title(translate("数据可信度", "Data Trust"))
        pdf.add_kv_row(
            translate("可靠频道", "Reliable Channels"),
            f"{reliability_summary.get('reliable_channels', 0)}/{reliability_summary.get('total_channels', 0)}",
        )
        pdf.add_kv_row(translate("平均可靠性评分", "Average Reliability Score"), f"{reliability_summary.get('average_score', 0)}/100")
        levels = reliability_summary.get("levels", {})
        pdf.add_kv_row(
            translate("可靠性等级", "Reliability Levels"),
            (
                f"gold:{levels.get('gold', 0)} "
                f"silver:{levels.get('silver', 0)} "
                f"bronze:{levels.get('bronze', 0)} "
                f"red:{levels.get('red', 0)}"
            ),
        )

    if consistency_check and consistency_check.get("has_conflict"):
        pdf.ln(4)
        pdf.section_title(translate("一致性预警", "Consistency Warning"))
        for issue in consistency_check.get("issues", []):
            pdf.bullet_point(issue)
        pdf.add_kv_row(translate("建议覆盖时长", "Recommended Duration Override"), consistency_check.get("recommended_range", "N/A"))

    # ── 第二章：对标频道分析 ────────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("2. 对标频道分析", "2. Channel Analysis"))

    if not comparison_df.empty:
        headers = list(comparison_df.columns)[:7]
        rows = []
        for _, row in comparison_df.head(10).iterrows():
            rows.append([str(row[h])[:18] for h in headers])
        col_w = [28, 22, 20, 25, 25, 22, 25][:len(headers)]
        pdf.add_simple_table(headers, rows, col_w)
        pdf.ln(5)

    if "radar" in chart_paths:
        pdf.safe_add_image(chart_paths["radar"])

    # ── 第三章：爆款内容解码 ────────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("3. 爆款内容解码", "3. Viral Content Decoded"))

    pdf.section_title(translate("互动率 TOP 5 视频", "Top Videos by Engagement"))
    if not top_videos_df.empty:
        eng_top = top_videos_df.head(5)
        for _, v in eng_top.iterrows():
            eng_rate = v.get("engagement_rate", 0)
            views = v.get("view_count", 0)
            pdf.bullet_point(
                translate(
                    f'"{v["title"][:50]}" — 播放量: {views:,} | 互动率: {eng_rate:.2%}',
                    f'"{v["title"][:50]}" — Views: {views:,} | Engagement: {eng_rate:.2%}',
                )
            )
        pdf.ln(3)

    if "top10_bar" in chart_paths:
        pdf.safe_add_image(chart_paths["top10_bar"])

    if viral_outliers:
        pdf.section_title(translate("单爆款异常检测", "Single Viral Outlier Check"))
        found_outlier = False
        for ch_id, insight in viral_outliers.items():
            if not insight.get("has_outliers"):
                continue
            found_outlier = True
            ch_title = channels_data.get(ch_id, {}).get("info", {}).get("title", ch_id)
            pdf.bullet_point(
                translate(
                    f"{ch_title}: {insight.get('outlier_count', 0)} 个异常爆款，基线增长 {insight.get('baseline_growth_ratio', 'N/A')}x",
                    f"{ch_title}: {insight.get('outlier_count', 0)} outlier(s), baseline growth {insight.get('baseline_growth_ratio', 'N/A')}x",
                )
            )
            for outlier in insight.get("outliers", [])[:2]:
                pdf.body_text(
                    translate(
                        f"- {outlier.get('title', 'N/A')[:60]} | 播放量: {outlier.get('view_count', 0):,} | z值: {outlier.get('zscore', 0)}",
                        f"- {outlier.get('title', 'N/A')[:60]} | views: {outlier.get('view_count', 0):,} | z: {outlier.get('zscore', 0)}",
                    )
                )
        if not found_outlier:
            pdf.body_text(translate("当前样本中没有明显的异常爆款。", "No strong viral outlier detected in this dataset."))

    if "duration_scatter" in chart_paths:
        pdf.add_page()
        pdf.section_title(translate("时长与播放量", "Duration vs Views"))
        duration_best = duration_analysis.get("best_range", "N/A")
        pdf.body_text(translate(f"观察到的更强时长区间: {duration_best}", f"Observed stronger duration range: {duration_best}"))
        pdf.safe_add_image(chart_paths["duration_scatter"])

    # ── 第四章：字幕洞察与内容策略 ─────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("4. 字幕洞察与内容策略", "4. Transcript Intelligence & Strategy"))

    if transcript_insights and transcript_insights.get("has_data"):
        coverage = transcript_insights.get("coverage", {})
        pdf.section_title(translate("字幕覆盖情况", "Transcript Coverage"))
        pdf.add_kv_row(translate("分析字幕数", "Analyzed Transcripts"), str(coverage.get("analyzed_videos", 0)))
        pdf.add_kv_row(translate("覆盖频道数", "Channels Covered"), str(coverage.get("analyzed_channels", 0)))
        pdf.add_kv_row(translate("解析词数", "Words Parsed"), f"{coverage.get('total_words', 0):,}")
        pdf.body_text(transcript_insights.get("method_note", ""))

        signal_terms = transcript_insights.get("signal_terms", [])
        if signal_terms:
            pdf.body_text(translate("信号词: ", "Signal Terms: ") + ", ".join(signal_terms[:10]))

        pattern_blocks = [
            (translate("开场 Hook", "Opening Hooks"), transcript_insights.get("hook_patterns", [])),
            (translate("内容结构", "Structure Patterns"), transcript_insights.get("structure_patterns", [])),
            (translate("结尾 CTA", "CTA Patterns"), transcript_insights.get("cta_patterns", [])),
        ]
        for section_name, patterns in pattern_blocks:
            if not patterns:
                continue
            pdf.section_title(section_name)
            for pattern in patterns[:2]:
                share = int(pattern.get("share", 0) * 100)
                pdf.bullet_point(
                    f"{pattern.get('label', translate('模式', 'Pattern'))} ({share}% | {pattern.get('count', 0)} {translate('个视频', 'videos')})"
                )
                pdf.body_text(pattern.get("description", ""))
                examples = pattern.get("examples", [])
                if examples:
                    pdf.body_text(translate("示例: ", "Examples: ") + "; ".join(examples[:2]))
                if pdf.get_y() > pdf.h - 55:
                    pdf.add_page()

        channel_signatures = transcript_insights.get("channel_signatures", [])
        if channel_signatures:
            pdf.section_title(translate("频道内容指纹", "Channel Content Signatures"))
            for channel in channel_signatures[:4]:
                pdf.bullet_point(
                    translate(
                        f"{channel.get('channel', 'Unknown')} ({channel.get('videos', 0)} 个视频 | 平均 {channel.get('avg_views', 0):,} 播放)",
                        f"{channel.get('channel', 'Unknown')} ({channel.get('videos', 0)} videos | avg {channel.get('avg_views', 0):,} views)",
                    )
                )
                pdf.body_text(channel.get("summary", ""))
                if pdf.get_y() > pdf.h - 55:
                    pdf.add_page()

        strategy_recommendations = transcript_insights.get("strategy_recommendations", [])
        if strategy_recommendations:
            pdf.section_title(translate("基于字幕的策略动作", "Transcript-Grounded Strategy Moves"))
            for rec in strategy_recommendations[:4]:
                pdf.bullet_point(f"{rec.get('title', '')}: {rec.get('recommendation', '')}")
                pdf.body_text(
                    translate(
                        f"证据: {rec.get('evidence', '')} | 置信度: {rec.get('confidence', '')}",
                        f"Evidence: {rec.get('evidence', '')} | Confidence: {rec.get('confidence', '')}",
                    )
                )
                if pdf.get_y() > pdf.h - 55:
                    pdf.add_page()

        script_templates = transcript_insights.get("script_templates", [])
        if script_templates:
            pdf.section_title(translate("可复用脚本模板", "Reusable Script Templates"))
            for template in script_templates[:3]:
                pdf.bullet_point(template.get("name", "Template"))
                pdf.body_text(template.get("why_it_works", ""))
                pdf.body_text(translate("证据: ", "Evidence: ") + template.get("evidence", ""))
                for step in template.get("steps", [])[:5]:
                    pdf.body_text(f"- {step}")
                examples = template.get("example_titles", [])
                if examples:
                    pdf.body_text(translate("示例标题: ", "Example Titles: ") + " | ".join(examples[:2]))
                if pdf.get_y() > pdf.h - 60:
                    pdf.add_page()
    else:
        pdf.section_title(translate("字幕洞察", "Transcript Intelligence"))
        pdf.body_text(
            translate(
                "本次运行未收集到字幕数据。启用字幕抓取，或复用历史字幕文件后，才能获得内容结构分析。",
                "No transcript data collected for this run. Enable transcript fetching or reuse a saved transcript archive to unlock content-structure analysis.",
            )
        )

    if pdf.get_y() > pdf.h - 90:
        pdf.add_page()

    pdf.section_title(translate("内容策略地图", "Content Strategy Map"))

    if content_strategy:
        painpoint = content_strategy.get("painpoint_hypothesis", {})
        if painpoint:
            pdf.section_title(translate("核心痛点诊断", "Core Painpoint Diagnosis"))
            pdf.bullet_point(f"{translate('主要问题', 'Primary')}: {painpoint.get('primary', '')}")
            for item in painpoint.get("secondary", []):
                pdf.body_text(f"- {item}")
            pdf.body_text(f"{translate('内容目标', 'Content Goal')}: {painpoint.get('content_goal', '')}")

        pdf.section_title(translate("标题公式", "Title Formulas"))
        for formula in content_strategy.get("title_formulas", []):
            pdf.bullet_point(formula)
        pdf.ln(3)

        pdf.section_title(translate("建议时长", "Duration Guidance"))
        pdf.body_text(content_strategy.get("optimal_duration", ""))

        pdf.section_title(translate("发布节奏", "Publishing Schedule"))
        pdf.body_text(content_strategy.get("publish_schedule", ""))

        pdf.section_title(translate("缩略图建议", "Thumbnail Tips"))
        for tip in content_strategy.get("thumbnail_tips", []):
            pdf.bullet_point(tip)

        cold_start = content_strategy.get("cold_start_plan", {})
        if cold_start:
            pdf.ln(3)
            pdf.section_title(translate("冷启动周计划", "Cold Start Weekly Plan"))
            weekly_plan = cold_start.get("weekly_plan", [])
            for item in weekly_plan[:8]:
                pdf.bullet_point(
                    f"W{item.get('week', 0)}-{item.get('order', 0)} | "
                    f"{item.get('topic', '')[:50]} | {item.get('target_duration', '')}"
                )

            pdf.section_title(translate("测试矩阵", "Experiment Matrix"))
            for exp in cold_start.get("experiment_matrix", [])[:6]:
                pdf.body_text(
                    f"{exp.get('test_id', '')}: {exp.get('keyword', '')} | "
                    f"{exp.get('format', '')} | {exp.get('hook', '')}"
                )

    if "title_wordcloud" in chart_paths:
        pdf.add_page()
        pdf.section_title(translate("标题关键词", "Title Keywords"))
        pdf.safe_add_image(chart_paths["title_wordcloud"])

    if "publish_heatmap" in chart_paths:
        pdf.section_title(translate("发布时间热力图", "Publish Heatmap"))
        pdf.safe_add_image(chart_paths["publish_heatmap"])

    # ── 第五章：暴涨频道速报 ────────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("5. 上升频道观察", "5. Rising Channels"))

    if rising_channels_df is not None and not rising_channels_df.empty:
        rising = rising_channels_df.head(5)
        for _, ch in rising.iterrows():
            emoji = ch.get("status_emoji", "")
            status = ch.get("status", "")
            ratio = ch.get("growth_ratio", 1.0)
            pdf.bullet_point(
                translate(
                    f'{emoji} {ch.get("title", "N/A")} — 增长: {ratio}x | 订阅: {ch.get("subscriber_count", 0):,} | 状态: {status}',
                    f'{emoji} {ch.get("title", "N/A")} — Growth: {ratio}x | Subs: {ch.get("subscriber_count", 0):,} | Status: {status}',
                )
            )
    else:
        pdf.body_text(translate("本次样本中没有识别出明显的上升频道。", "No rising channels detected in this niche scan."))

    if "growth_trend" in chart_paths:
        pdf.safe_add_image(chart_paths["growth_trend"])

    if evolution_insights:
        pdf.section_title(translate("频道纵向演化", "Channel Evolution Snapshot"))
        shown = 0
        for ch_id, evo in evolution_insights.items():
            if shown >= 5:
                break
            if evo.get("trend") == "insufficient":
                continue
            ch_title = channels_data.get(ch_id, {}).get("info", {}).get("title", ch_id)
            pdf.bullet_point(
                f"{ch_title}: {evo.get('trend_label', 'N/A')} "
                f"({evo.get('improvement_rate', 0):+.0%})"
            )
            pdf.body_text(evo.get("inflection", ""))
            shown += 1

    # ── 第六章：观众痛点洞察 ────────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("6. 观众痛点洞察", "6. Audience Pain Points"))

    if comment_keywords:
        pdf.section_title(translate("评论高频主题", "Hot Topics from Comments"))
        top_words = list(comment_keywords.keys())[:20]
        for i in range(0, len(top_words), 4):
            line = " | ".join(top_words[i:i+4])
            pdf.body_text(line)
    else:
        pdf.body_text(translate("本次没有采集到评论数据。重新分析并开启评论抓取后可获得这部分洞察。", "No comment data collected. Re-run analysis with comment fetching enabled."))

    if "comment_wordcloud" in chart_paths:
        pdf.safe_add_image(chart_paths["comment_wordcloud"])

    # ── 第七章：阶段目标与盈利规划 ──────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("7. 增长规划与变现", "7. Growth Plan & Monetization"))

    if milestone_plan:
        pdf.section_title(f"{translate('时间线', 'Timeline')}: {milestone_plan.get('estimated_timeline', '')}")
        pdf.ln(3)

        for ms in milestone_plan.get("milestones", []):
            pdf.section_title(ms["phase"])
            pdf.body_text(f"{translate('目标', 'Target')}: {ms['target']} | {translate('周期', 'Duration')}: {ms['duration']}")
            for action in ms.get("actions", []):
                pdf.bullet_point(action)
            pdf.body_text(f"KPI: {ms.get('kpi', '')}")
            pdf.ln(3)

            if pdf.get_y() > pdf.h - 60:
                pdf.add_page()

    if monetization:
        pdf.add_page()
        pdf.section_title(translate("收入区间估算", "Revenue Projection"))

        adsense = monetization.get("adsense", {})
        pdf.add_kv_row(translate("AdSense（低）", "AdSense (Low)"), f"${adsense.get('low', 0):.0f}/mo")
        pdf.add_kv_row(translate("AdSense（中）", "AdSense (Mid)"), f"${adsense.get('mid', 0):.0f}/mo")
        pdf.add_kv_row(translate("AdSense（高）", "AdSense (High)"), f"${adsense.get('high', 0):.0f}/mo")
        pdf.ln(3)

        pdf.section_title(translate("知识产品", "Knowledge Products"))
        for p in monetization.get("knowledge_products", []):
            pdf.add_kv_row(
                p["name"],
                f"${p['price']} x {p['monthly_sales']:.0f}/mo = ${p['monthly_revenue']:.0f}/mo",
            )
        pdf.ln(3)

        mem = monetization.get("membership", {})
        pdf.add_kv_row(
            translate("会员", "Membership"),
            translate(
                f"${mem.get('monthly_revenue', 0):.0f}/月（{mem.get('members', 0)} 位成员）",
                f"${mem.get('monthly_revenue', 0):.0f}/mo ({mem.get('members', 0)} members)",
            ),
        )
        aff = monetization.get("affiliate", {})
        pdf.add_kv_row(translate("联盟分成", "Affiliate"), f"${aff.get('monthly_revenue', 0):.0f}/mo")
        pdf.ln(5)

        total = monetization.get("total_estimated", {})
        pdf._set_font_safe("B", 12)
        pdf.set_text_color(34, 139, 34)
        pdf.cell(
            0,
            10,
            translate(
                f"预估月收入区间: ${total.get('low',0):.0f} ~ ${total.get('high',0):.0f}",
                f"Estimated Monthly Revenue Range: ${total.get('low',0):.0f} ~ ${total.get('high',0):.0f}",
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

    # ── 第八章：执行建议 ────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title(translate("8. 执行清单", "8. Action Checklist"))

    checklist = [
        translate("[ ] 完成 YouTube 频道包装（头像、横幅、简介）", "[ ] Complete YouTube channel branding (avatar, banner, about section)"),
        translate("[ ] 准备一个免费资料入口（PDF / 思维导图）和基础收集链路", "[ ] Set up a free lead magnet (PDF / mind map) and a basic collection flow"),
        translate("[ ] 先按上面的高表现主题做出前 5 支视频", "[ ] Produce the first 5 videos using the strongest themes above"),
        translate("[ ] 用第 4 章的标题公式优化视频标题", "[ ] Optimize video titles using the title formulas in Chapter 4"),
        translate("[ ] 用第 4 章的建议统一缩略图规则", "[ ] Create thumbnails using the guidance in Chapter 4"),
        translate("[ ] 建立 Shorts / 切片复用流程", "[ ] Set up a Shorts repurposing workflow"),
        translate("[ ] 加入 3-5 个相关社区，做高质量互动而不是刷屏", "[ ] Join 3-5 relevant online communities and contribute without spamming"),
        translate("[ ] 按建议时段排期发布并持续记录结果", "[ ] Schedule videos at optimal publish times and record results"),
        translate("[ ] 做完 15 支视频后复盘数据，放大表现最强的主题", "[ ] After 15 videos, review analytics and double down on best-performing topics"),
        translate("[ ] 到 500 订阅时准备知识产品雏形", "[ ] At 500 subscribers, prepare a first knowledge product outline"),
        translate("[ ] 到 1000 订阅时申请 YouTube Partner Program", "[ ] At 1000 subscribers, apply for YouTube Partner Program"),
        translate("[ ] 到 1000 订阅时测试首个付费产品", "[ ] At 1000 subscribers, test the first paid product"),
    ]

    for item in checklist:
        pdf.bullet_point(item)

    # 输出
    return bytes(pdf.output())
