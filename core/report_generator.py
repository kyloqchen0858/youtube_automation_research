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


class ReportPDF(FPDF):
    """自定义 PDF 类，支持中文字体和页眉页脚"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            self.cell(0, 8, "YouTube Competitive Research Report", align="R")
            self.ln(10)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), self.w - 10, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self._set_font_safe("", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

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
        x = self.get_x()
        self.cell(6, 6, chr(8226))
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
            self.body_text(f"[Image not found: {image_path}]")
            return
        if self.get_y() > self.h - 120:
            self.add_page()
        try:
            self.image(image_path, x=15, w=w)
            self.ln(5)
        except Exception as e:
            self.body_text(f"[Image load error: {e}]")


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
    pdf = ReportPDF("P", "mm", "A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=25)

    # ── 封面 ────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(40)
    pdf._set_font_safe("B", 28)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 15, "YouTube Competitive", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 15, "Research Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf._set_font_safe("", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, f"Niche: {niche}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)

    pdf._set_font_safe("", 11)
    pdf.set_text_color(120, 120, 120)
    num_channels = len(channels_data)
    total_videos = sum(len(d.get("videos", [])) for d in channels_data.values())
    pdf.cell(0, 8, f"Channels Analyzed: {num_channels}  |  Videos Scanned: {total_videos}", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── 第一章：赛道概览 ────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("1. Niche Overview / \u8d5b\u9053\u6982\u89c8")

    pdf.section_title("Research Scope / \u8c03\u7814\u8303\u56f4")
    pdf.add_kv_row("Niche / \u8d5b\u9053", niche)
    pdf.add_kv_row("Channels / \u9891\u9053\u6570", str(num_channels))
    pdf.add_kv_row("Videos / \u89c6\u9891\u6570", str(total_videos))
    pdf.ln(5)

    if milestone_plan and milestone_plan.get("key_metrics"):
        pdf.section_title("Key Metrics / \u6838\u5fc3\u6307\u6807")
        for k, v in milestone_plan["key_metrics"].items():
            pdf.add_kv_row(k, str(v))

    if reliability_summary:
        pdf.ln(4)
        pdf.section_title("Data Trust / \u6570\u636e\u53ef\u4fe1\u5ea6")
        pdf.add_kv_row(
            "Reliable Channels",
            f"{reliability_summary.get('reliable_channels', 0)}/{reliability_summary.get('total_channels', 0)}",
        )
        pdf.add_kv_row("Average Reliability Score", f"{reliability_summary.get('average_score', 0)}/100")
        levels = reliability_summary.get("levels", {})
        pdf.add_kv_row(
            "Reliability Levels",
            (
                f"gold:{levels.get('gold', 0)} "
                f"silver:{levels.get('silver', 0)} "
                f"bronze:{levels.get('bronze', 0)} "
                f"red:{levels.get('red', 0)}"
            ),
        )

    if consistency_check and consistency_check.get("has_conflict"):
        pdf.ln(4)
        pdf.section_title("Consistency Warning / \u4e00\u81f4\u6027\u9884\u8b66")
        for issue in consistency_check.get("issues", []):
            pdf.bullet_point(issue)
        pdf.add_kv_row("Recommended Duration Override", consistency_check.get("recommended_range", "N/A"))

    # ── 第二章：对标频道分析 ────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("2. Channel Analysis / \u5bf9\u6807\u9891\u9053\u5206\u6790")

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
    pdf.chapter_title("3. Viral Content Decoded / \u7206\u6b3e\u5185\u5bb9\u89e3\u7801")

    pdf.section_title("Top Videos by Engagement / \u4e92\u52a8\u7387 TOP 5")
    if not top_videos_df.empty:
        eng_top = top_videos_df.head(5)
        for _, v in eng_top.iterrows():
            eng_rate = v.get("engagement_rate", 0)
            views = v.get("view_count", 0)
            pdf.bullet_point(
                f'"{v["title"][:50]}" — Views: {views:,} | Engagement: {eng_rate:.2%}'
            )
        pdf.ln(3)

    if "top10_bar" in chart_paths:
        pdf.safe_add_image(chart_paths["top10_bar"])

    if viral_outliers:
        pdf.section_title("Single Viral Outlier Check / \u5355\u7206\u6b3e\u5f02\u5e38\u68c0\u6d4b")
        found_outlier = False
        for ch_id, insight in viral_outliers.items():
            if not insight.get("has_outliers"):
                continue
            found_outlier = True
            ch_title = channels_data.get(ch_id, {}).get("info", {}).get("title", ch_id)
            pdf.bullet_point(
                f"{ch_title}: {insight.get('outlier_count', 0)} outlier(s), "
                f"baseline growth {insight.get('baseline_growth_ratio', 'N/A')}x"
            )
            for outlier in insight.get("outliers", [])[:2]:
                pdf.body_text(
                    f"- {outlier.get('title', 'N/A')[:60]} | "
                    f"views: {outlier.get('view_count', 0):,} | z: {outlier.get('zscore', 0)}"
                )
        if not found_outlier:
            pdf.body_text("No strong viral outlier detected in this dataset.")

    if "duration_scatter" in chart_paths:
        pdf.add_page()
        pdf.section_title("Duration vs Views / \u65f6\u957f\u4e0e\u64ad\u653e\u91cf")
        duration_best = duration_analysis.get("best_range", "N/A")
        pdf.body_text(f"Optimal Duration / \u6700\u4f73\u65f6\u957f: {duration_best}")
        pdf.safe_add_image(chart_paths["duration_scatter"])

    # ── 第四章：字幕洞察与内容策略 ─────────────────────────────
    pdf.add_page()
    pdf.chapter_title("4. Transcript Intelligence & Strategy / \u5b57\u5e55\u6d1e\u5bdf\u4e0e\u5185\u5bb9\u7b56\u7565")

    if transcript_insights and transcript_insights.get("has_data"):
        coverage = transcript_insights.get("coverage", {})
        pdf.section_title("Transcript Coverage / \u5b57\u5e55\u8986\u76d6")
        pdf.add_kv_row("Analyzed Transcripts", str(coverage.get("analyzed_videos", 0)))
        pdf.add_kv_row("Channels Covered", str(coverage.get("analyzed_channels", 0)))
        pdf.add_kv_row("Words Parsed", f"{coverage.get('total_words', 0):,}")
        pdf.body_text(transcript_insights.get("method_note", ""))

        signal_terms = transcript_insights.get("signal_terms", [])
        if signal_terms:
            pdf.body_text("Signal Terms: " + ", ".join(signal_terms[:10]))

        pattern_blocks = [
            ("Opening Hooks / \u5f00\u573a Hook", transcript_insights.get("hook_patterns", [])),
            ("Structure Patterns / \u5185\u5bb9\u7ed3\u6784", transcript_insights.get("structure_patterns", [])),
            ("CTA Patterns / \u7ed3\u5c3e CTA", transcript_insights.get("cta_patterns", [])),
        ]
        for section_name, patterns in pattern_blocks:
            if not patterns:
                continue
            pdf.section_title(section_name)
            for pattern in patterns[:2]:
                share = int(pattern.get("share", 0) * 100)
                pdf.bullet_point(
                    f"{pattern.get('label', 'Pattern')} ({share}% | {pattern.get('count', 0)} videos)"
                )
                pdf.body_text(pattern.get("description", ""))
                examples = pattern.get("examples", [])
                if examples:
                    pdf.body_text("Examples: " + "; ".join(examples[:2]))
                if pdf.get_y() > pdf.h - 55:
                    pdf.add_page()

        channel_signatures = transcript_insights.get("channel_signatures", [])
        if channel_signatures:
            pdf.section_title("Channel Content Signatures / \u9891\u9053\u5185\u5bb9\u6307\u7eb9")
            for channel in channel_signatures[:4]:
                pdf.bullet_point(
                    f"{channel.get('channel', 'Unknown')} ({channel.get('videos', 0)} videos | avg {channel.get('avg_views', 0):,} views)"
                )
                pdf.body_text(channel.get("summary", ""))
                if pdf.get_y() > pdf.h - 55:
                    pdf.add_page()

        strategy_recommendations = transcript_insights.get("strategy_recommendations", [])
        if strategy_recommendations:
            pdf.section_title("Transcript-Grounded Strategy Moves / \u57fa\u4e8e\u5b57\u5e55\u7684\u7b56\u7565")
            for rec in strategy_recommendations[:4]:
                pdf.bullet_point(f"{rec.get('title', '')}: {rec.get('recommendation', '')}")
                pdf.body_text(
                    f"Evidence: {rec.get('evidence', '')} | Confidence: {rec.get('confidence', '')}"
                )
                if pdf.get_y() > pdf.h - 55:
                    pdf.add_page()

        script_templates = transcript_insights.get("script_templates", [])
        if script_templates:
            pdf.section_title("Reusable Script Templates / \u53ef\u590d\u7528\u811a\u672c\u6a21\u677f")
            for template in script_templates[:3]:
                pdf.bullet_point(template.get("name", "Template"))
                pdf.body_text(template.get("why_it_works", ""))
                pdf.body_text("Evidence: " + template.get("evidence", ""))
                for step in template.get("steps", [])[:5]:
                    pdf.body_text(f"- {step}")
                examples = template.get("example_titles", [])
                if examples:
                    pdf.body_text("Example Titles: " + " | ".join(examples[:2]))
                if pdf.get_y() > pdf.h - 60:
                    pdf.add_page()
    else:
        pdf.section_title("Transcript Intelligence / \u5b57\u5e55\u6d1e\u5bdf")
        pdf.body_text(
            "No transcript data collected for this run. Enable transcript fetching or reuse a saved transcript archive to unlock content-structure analysis."
        )

    if pdf.get_y() > pdf.h - 90:
        pdf.add_page()

    pdf.section_title("Content Strategy Map / \u5185\u5bb9\u7b56\u7565\u5730\u56fe")

    if content_strategy:
        painpoint = content_strategy.get("painpoint_hypothesis", {})
        if painpoint:
            pdf.section_title("Core Painpoint Diagnosis / \u6838\u5fc3\u75db\u70b9\u8bca\u65ad")
            pdf.bullet_point(f"Primary: {painpoint.get('primary', '')}")
            for item in painpoint.get("secondary", []):
                pdf.body_text(f"- {item}")
            pdf.body_text(f"Content Goal: {painpoint.get('content_goal', '')}")

        pdf.section_title("Title Formulas / \u6807\u9898\u516c\u5f0f")
        for formula in content_strategy.get("title_formulas", []):
            pdf.bullet_point(formula)
        pdf.ln(3)

        pdf.section_title("Optimal Duration / \u6700\u4f73\u65f6\u957f")
        pdf.body_text(content_strategy.get("optimal_duration", ""))

        pdf.section_title("Publishing Schedule / \u53d1\u5e03\u8282\u594f")
        pdf.body_text(content_strategy.get("publish_schedule", ""))

        pdf.section_title("Thumbnail Tips / \u7f29\u7565\u56fe\u5efa\u8bae")
        for tip in content_strategy.get("thumbnail_tips", []):
            pdf.bullet_point(tip)

        cold_start = content_strategy.get("cold_start_plan", {})
        if cold_start:
            pdf.ln(3)
            pdf.section_title("Cold Start Weekly Plan / \u51b7\u542f\u52a8\u5468\u8ba1\u5212")
            weekly_plan = cold_start.get("weekly_plan", [])
            for item in weekly_plan[:8]:
                pdf.bullet_point(
                    f"W{item.get('week', 0)}-{item.get('order', 0)} | "
                    f"{item.get('topic', '')[:50]} | {item.get('target_duration', '')}"
                )

            pdf.section_title("Experiment Matrix / \u6d4b\u8bd5\u77e9\u9635")
            for exp in cold_start.get("experiment_matrix", [])[:6]:
                pdf.body_text(
                    f"{exp.get('test_id', '')}: {exp.get('keyword', '')} | "
                    f"{exp.get('format', '')} | {exp.get('hook', '')}"
                )

    if "title_wordcloud" in chart_paths:
        pdf.add_page()
        pdf.section_title("Title Keywords / \u6807\u9898\u5173\u952e\u8bcd")
        pdf.safe_add_image(chart_paths["title_wordcloud"])

    if "publish_heatmap" in chart_paths:
        pdf.section_title("Publish Heatmap / \u53d1\u5e03\u65f6\u95f4\u70ed\u529b\u56fe")
        pdf.safe_add_image(chart_paths["publish_heatmap"])

    # ── 第五章：暴涨频道速报 ────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("5. Rising Channels / \u66b4\u6da8\u9891\u9053\u901f\u62a5")

    if rising_channels_df is not None and not rising_channels_df.empty:
        rising = rising_channels_df.head(5)
        for _, ch in rising.iterrows():
            emoji = ch.get("status_emoji", "")
            status = ch.get("status", "")
            ratio = ch.get("growth_ratio", 1.0)
            pdf.bullet_point(
                f'{emoji} {ch.get("title", "N/A")} — '
                f'Growth: {ratio}x | Subs: {ch.get("subscriber_count", 0):,} | '
                f'Status: {status}'
            )
    else:
        pdf.body_text("No rising channels detected in this niche scan.")

    if "growth_trend" in chart_paths:
        pdf.safe_add_image(chart_paths["growth_trend"])

    if evolution_insights:
        pdf.section_title("Channel Evolution Snapshot / \u9891\u9053\u7eb5\u5411\u6f14\u5316")
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
    pdf.chapter_title("6. Audience Pain Points / \u89c2\u4f17\u75db\u70b9\u6d1e\u5bdf")

    if comment_keywords:
        pdf.section_title("Hot Topics from Comments / \u8bc4\u8bba\u9ad8\u9891\u8bcd")
        top_words = list(comment_keywords.keys())[:20]
        for i in range(0, len(top_words), 4):
            line = " | ".join(top_words[i:i+4])
            pdf.body_text(line)
    else:
        pdf.body_text("No comment data collected. Re-run analysis with comment fetching enabled.")

    if "comment_wordcloud" in chart_paths:
        pdf.safe_add_image(chart_paths["comment_wordcloud"])

    # ── 第七章：阶段目标与盈利规划 ──────────────────────────
    pdf.add_page()
    pdf.chapter_title("7. Growth Plan & Monetization / \u9636\u6bb5\u76ee\u6807\u4e0e\u76c8\u5229")

    if milestone_plan:
        pdf.section_title(f"Timeline: {milestone_plan.get('estimated_timeline', '')}")
        pdf.ln(3)

        for ms in milestone_plan.get("milestones", []):
            pdf.section_title(ms["phase"])
            pdf.body_text(f"Target: {ms['target']} | Duration: {ms['duration']}")
            for action in ms.get("actions", []):
                pdf.bullet_point(action)
            pdf.body_text(f"KPI: {ms.get('kpi', '')}")
            pdf.ln(3)

            if pdf.get_y() > pdf.h - 60:
                pdf.add_page()

    if monetization:
        pdf.add_page()
        pdf.section_title("Revenue Projection / \u6536\u5165\u9884\u4f30")

        adsense = monetization.get("adsense", {})
        pdf.add_kv_row("AdSense (Low)", f"${adsense.get('low', 0):.0f}/mo")
        pdf.add_kv_row("AdSense (Mid)", f"${adsense.get('mid', 0):.0f}/mo")
        pdf.add_kv_row("AdSense (High)", f"${adsense.get('high', 0):.0f}/mo")
        pdf.ln(3)

        pdf.section_title("Knowledge Products / \u77e5\u8bc6\u4ed8\u8d39\u4ea7\u54c1")
        for p in monetization.get("knowledge_products", []):
            pdf.add_kv_row(
                p["name"],
                f"${p['price']} x {p['monthly_sales']:.0f}/mo = ${p['monthly_revenue']:.0f}/mo",
            )
        pdf.ln(3)

        mem = monetization.get("membership", {})
        pdf.add_kv_row("Membership", f"${mem.get('monthly_revenue', 0):.0f}/mo ({mem.get('members', 0)} members)")
        aff = monetization.get("affiliate", {})
        pdf.add_kv_row("Affiliate", f"${aff.get('monthly_revenue', 0):.0f}/mo")
        pdf.ln(5)

        total = monetization.get("total_estimated", {})
        pdf._set_font_safe("B", 12)
        pdf.set_text_color(34, 139, 34)
        pdf.cell(0, 10, f"Total Estimated Monthly Revenue: ${total.get('low',0):.0f} ~ ${total.get('high',0):.0f}",
                 new_x="LMARGIN", new_y="NEXT")

    # ── 第八章：执行建议 ────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("8. Action Checklist / \u6267\u884c\u5efa\u8bae\u6e05\u5355")

    checklist = [
        "[\u2009] Complete YouTube channel branding (avatar, banner, about section)",
        "[\u2009] Set up free lead magnet (PDF/mind map) and email collection tool",
        "[\u2009] Produce first 5 videos based on top-performing content themes above",
        "[\u2009] Optimize video titles using the title formulas in Chapter 4",
        "[\u2009] Create thumbnails following the tips in Chapter 4",
        "[\u2009] Set up Shorts workflow: repurpose long-form videos into 60s clips",
        "[\u2009] Join 3-5 relevant online communities and contribute value (not spam)",
        "[\u2009] Schedule videos at optimal publish times (see Chapter 4)",
        "[\u2009] After 15 videos: review analytics, double down on best-performing topics",
        "[\u2009] At 500 subs: prepare knowledge product (mini course outline)",
        "[\u2009] At 1000 subs: apply for YouTube Partner Program",
        "[\u2009] At 1000 subs: launch first paid product ($29-$99)",
    ]

    for item in checklist:
        pdf.bullet_point(item)

    # 输出
    return bytes(pdf.output())
