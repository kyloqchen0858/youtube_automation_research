"""
Cold Start Executor — 冷启动可执行计划生成器

目标：把抽象策略转成可执行的 4 周冷启动计划。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

import pandas as pd

EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "to", "of", "in", "on", "for",
    "with", "and", "or", "but", "if", "then", "than", "that", "this", "these", "those", "it", "its", "you",
    "your", "yours", "we", "our", "they", "their", "i", "me", "my", "he", "she", "him", "her", "do", "does",
    "did", "can", "could", "should", "would", "how", "why", "what", "when", "where", "which", "who", "whom",
    "under", "into", "from", "about", "over", "after", "before", "internal", "today", "life", "wisdom", "ancient",
}

THEME_WHITELIST = {
    "procrastination", "discipline", "focus", "habit", "consistency", "execution", "anxiety", "mindset",
    "productivity", "stoic", "stoicism", "tao", "taoism", "wisdom", "philosophy", "self", "control",
    "motivation", "dopamine", "attention", "deep", "work", "workflow", "automation", "agent", "tutorial",
    "creator", "operators", "operator", "prompt", "prompts", "research", "system", "tool", "tools", "build",
}


@dataclass
class PlanItem:
    week: int
    order: int
    topic: str
    angle: str
    difficulty: str
    target_duration: str
    script_outline: str
    cta: str


def generate_executable_cold_start_plan(
    channels_data: dict,
    niche: str,
    user_keywords: list[str] | None = None,
    count: int = 12,
) -> dict:
    """
    生成冷启动可执行内容计划与测试矩阵。

    Returns:
        {
            "weekly_plan": [...],
            "experiment_matrix": [...],
            "setup_checklist": [...],
        }
    """
    keywords = _collect_seed_keywords(channels_data, user_keywords)
    if not keywords:
        keywords = _fallback_keywords(niche)

    topic_templates = [
        "{kw}：最值得先搭好的实战工作流",
        "别再低效使用 {kw}：一个可复制的执行版本",
        "7 天上手 {kw}：从混乱到稳定输出",
        "我把 {kw} 放进真实流程里测试，结果如何？",
        "你缺的不是时间，是系统：{kw} 拆解",
        "低门槛也能落地：{kw} 的最小可执行版本",
    ]

    angle_templates = [
        "痛点切入 + 真实案例 + 当日可执行动作",
        "反常识观点 + 3 步行动框架",
        "前后对比 + 模板拆解",
        "误区纠正 + 低门槛执行清单",
    ]

    cta_templates = [
        "评论区回复“workflow”，领取一页执行清单",
        "下一期投票选择你最想拆解的任务场景",
        "下载免费模板：流程图 / 提示词 / 操作清单",
    ]

    weekly_plan: list[dict] = []
    idx = 0
    for week in range(1, 5):
        for local_order in range(1, 4):
            if idx >= count:
                break
            kw = keywords[idx % len(keywords)]
            topic = topic_templates[idx % len(topic_templates)].format(kw=kw)
            angle = angle_templates[idx % len(angle_templates)]
            cta = cta_templates[idx % len(cta_templates)]

            difficulty = "easy" if idx < 4 else ("medium" if idx < 9 else "hard")
            target_duration = "5-8m" if difficulty == "easy" else ("8-12m" if difficulty == "medium" else "10-15m")

            script_outline = (
                "Hook 10s（指出具体任务或低效场景） -> "
                "Context 30s（为什么现在的方法低效） -> "
                "Workflow 3 steps（拆成可复制动作） -> "
                "Demo 60s（展示结果前后对比） -> "
                "CTA 15s"
            )

            item = PlanItem(
                week=week,
                order=local_order,
                topic=topic,
                angle=angle,
                difficulty=difficulty,
                target_duration=target_duration,
                script_outline=script_outline,
                cta=cta,
            )
            weekly_plan.append(_to_dict(item))
            idx += 1

    experiment_matrix = _build_experiment_matrix(keywords)

    setup_checklist = [
        f"确定频道一句话定位（围绕 {niche or '核心赛道'} 的明确承诺）",
        "准备统一缩略图模板（高对比底色 + 3-5 词标题）",
        "准备固定片头钩子句（10 秒内）",
        "建立选题看板：主题/标题/脚本/发布时间/结果",
        "设置每周复盘：CTR、平均观看时长、评论关键词",
    ]

    return {
        "weekly_plan": weekly_plan,
        "experiment_matrix": experiment_matrix,
        "setup_checklist": setup_checklist,
        "niche": niche,
    }


def _collect_seed_keywords(channels_data: dict, user_keywords: list[str] | None) -> list[str]:
    seeds: list[str] = []
    guided: list[str] = []

    if user_keywords:
        for kw in user_keywords:
            kw = (kw or "").strip()
            if kw and _is_meaningful_keyword(kw):
                guided.append(kw)

    if guided:
        seeds.extend(guided)
        seeds.extend(_guided_keyword_anchors(guided))

    for _, payload in channels_data.items():
        videos_df = payload.get("videos", pd.DataFrame())
        if videos_df.empty or "title" not in videos_df.columns:
            continue
        for title in videos_df["title"].head(8).tolist():
            for token in _simple_tokens(title):
                if _is_meaningful_keyword(token) and _is_theme_relevant_token(token):
                    seeds.append(token)

    deduped = []
    seen = set()
    for kw in seeds:
        low = kw.lower()
        if low in seen:
            continue
        seen.add(low)
        deduped.append(kw)

    return deduped[:20]


def _simple_tokens(text: str) -> Iterable[str]:
    clean = (
        text.replace("|", " ")
        .replace("-", " ")
        .replace(":", " ")
        .replace("/", " ")
        .replace("?", " ")
        .replace("!", " ")
        .replace("（", " ")
        .replace("）", " ")
        .replace("(", " ")
        .replace(")", " ")
    )
    return [t.strip() for t in clean.split() if t.strip()]


def _is_meaningful_keyword(token: str) -> bool:
    tok = (token or "").strip()
    if not tok:
        return False

    # 中文词保留长度 >=2
    if re.search(r"[\u4e00-\u9fff]", tok):
        return len(tok) >= 2

    # 英文词：纯字母、长度>=4、非停用词
    low = tok.lower()
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z\-']*", low):
        return False
    if len(low) < 4:
        return False
    if low in EN_STOPWORDS:
        return False
    return True


def _is_theme_relevant_token(token: str) -> bool:
    tok = token.lower().strip()

    if re.search(r"[\u4e00-\u9fff]", tok):
        return any(key in tok for key in ["拖延", "自律", "执行", "焦虑", "专注", "智慧", "道", "心法", "习惯", "工作流", "自动化", "教程", "工具", "创作", "复盘"]) 

    return any(key in tok for key in THEME_WHITELIST)


def _guided_keyword_anchors(guided_keywords: list[str]) -> list[str]:
    joined = " ".join(guided_keywords).lower()
    anchors = ["workflow", "playbook", "case study", "teardown"]

    if any(token in joined for token in ["ai", "agent", "automation", "prompt", "workflow"]):
        anchors.extend(["automation", "system design", "prompting", "operator workflow"])

    if any(token in joined for token in ["build", "public", "founder", "creator"]):
        anchors.extend(["build in public", "weekly recap", "behind the scenes"])

    if "procrast" in joined or "拖延" in "".join(guided_keywords):
        anchors.extend(["反拖延", "执行力", "习惯系统"])

    return anchors


def _fallback_keywords(niche: str) -> list[str]:
    niche_tokens = [token for token in _simple_tokens(niche or "") if _is_meaningful_keyword(token)]
    if niche_tokens:
        return niche_tokens[:8]
    return ["workflow", "automation", "tutorial", "creator", "research"]


def _build_experiment_matrix(keywords: list[str]) -> list[dict]:
    """
    生成格式 x 题材 x hook 的小步快跑测试矩阵。
    """
    formats = ["story", "how-to", "checklist"]
    hooks = [
        "你缺的不是工具，而是正确流程",
        "这个工作流今天就能复制",
        "90 秒讲清这 3 步怎么落地",
    ]

    matrix = []
    for idx, kw in enumerate(keywords[:6]):
        matrix.append(
            {
                "test_id": f"T{idx + 1}",
                "keyword": kw,
                "format": formats[idx % len(formats)],
                "hook": hooks[idx % len(hooks)],
                "success_metric": "CTR >= 5% and avg view duration >= 35%",
                "decision_rule": "连续 2 个视频达标则放大该组合，否则替换 hook",
            }
        )
    return matrix


def _to_dict(item: PlanItem) -> dict:
    return {
        "week": item.week,
        "order": item.order,
        "topic": item.topic,
        "angle": item.angle,
        "difficulty": item.difficulty,
        "target_duration": item.target_duration,
        "script_outline": item.script_outline,
        "cta": item.cta,
    }
