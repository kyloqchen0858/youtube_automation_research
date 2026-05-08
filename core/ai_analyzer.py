"""
AI Deep Analyzer — 使用 DeepSeek API 对 YouTube 数据做深度分析
输出具体、可执行、有实操价值的结论，而不是笼统的建议
"""

import logging
import os
import time
from typing import Any, Mapping, Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

DEFAULT_PROFILE = {
    "language": "英文",
    "topic": "AI workflow tutorials for creators and operators",
    "differentiation": "用真实工作流和可复制步骤讲清工具价值",
    "target_audience": "独立创作者、运营者、小团队负责人",
    "channel_style": "不露脸教程频道，以录屏、旁白和结果演示为主",
    "title_language": "英文",
}


def _merge_profile(profile: Mapping[str, Any] | None) -> dict[str, str]:
    merged = dict(DEFAULT_PROFILE)
    if profile:
        for key, value in profile.items():
            if value is None:
                continue
            text = str(value).strip()
            if text:
                merged[key] = text
    return merged


class AIAnalyzer:
    """使用 DeepSeek 做深度内容分析"""

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        profile: Mapping[str, Any] | None = None,
    ):
        self.api_key = api_key
        self.model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.profile = _merge_profile(profile)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _profile_block(self) -> str:
        profile = self.profile
        return (
            f"- 频道语言：{profile['language']}\n"
            f"- 主题：{profile['topic']}\n"
            f"- 差异化：{profile['differentiation']}\n"
            f"- 目标受众：{profile['target_audience']}\n"
            f"- 频道形式：{profile['channel_style']}\n"
            f"- 标题语言要求：{profile['title_language']}"
        )

    def _call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096, temperature: float = 0.3) -> str:
        """调用 DeepSeek API，带重试"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "thinking": {"type": "disabled"},
        }

        for attempt in range(3):
            try:
                resp = requests.post(
                    DEEPSEEK_API_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0]["message"]
                return message.get("content") or message.get("reasoning_content", "")
            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"DeepSeek API error: {e}")
                    raise
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise
        return ""

    def validate_key(self) -> bool:
        """验证 API key 是否有效"""
        try:
            result = self._call("You are a test.", "Say OK.", max_tokens=10)
            return len(result) > 0
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════
    # 核心分析方法
    # ═══════════════════════════════════════════════════════════

    def analyze_top3_channels(self, channels_data: dict, videos_df: pd.DataFrame) -> str:
        """分析最值得关注的 3 个频道及具体原因"""
        system = f"""你是一位资深 YouTube 频道增长策略专家。
    用户当前频道画像：
    {self._profile_block()}

你的任务是：从给定的竞品频道数据中，挑出最值得关注的 3 个频道，并详细说明原因。
原因必须具体到：内容结构、选题策略、标题套路、增长模式、可以借鉴的具体做法。
不要笼统的建议，要具体到「这个频道的XX视频用了XX手法，播放量是均值的XX倍，说明XX策略有效」。
用中文回答。"""

        # 构建频道摘要
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

            channel_summaries.append(
                f"""频道: {info.get('title', 'Unknown')}
  订阅: {info.get('subscriber_count', 0):,}
  平均播放: {avg_views:,} | 最高播放: {max_views:,}
  增长倍率: {growth.get('growth_ratio', 0)}x ({growth.get('status', '')})
  平均时长: {avg_dur}分钟
  TOP 5 视频:
{top5}"""
            )

        user = f"""以下是 {len(channels_data)} 个竞品频道的详细数据。
请从中选出最值得我关注学习的 3 个频道，对每个频道给出具体的分析：

1. 为什么值得关注（具体数据支撑，不要泛泛而谈）
2. 它的内容策略是什么（从标题和播放量差异中推断）
3. 它的增长模式（是稳定出量还是偶尔爆发）
4. 我可以借鉴的具体做法（至少3条，要可执行）
5. 它和我的频道画像的关联度

频道数据：
{'='*60}
{chr(10).join(channel_summaries)}
"""
        return self._call(system, user, max_tokens=4096)

    def analyze_top10_videos(self, videos_df: pd.DataFrame, transcripts: dict) -> str:
        """分析最值得研究的 10 个视频及具体原因"""
        system = f"""你是一位资深 YouTube 内容策略专家。
    用户当前频道画像：
    {self._profile_block()}

你的任务是：从播放量和参与率数据中，挑出最值得深入研究的 10 个视频。

选择标准不是简单的播放量排名，而是综合考虑：
- 播放量与所在频道均值的对比（超出均值越多，说明选题越成功）
- 参与率（高参与 = 内容引发共鸣）
- 标题结构（数字型、反常识型、情感型等，哪种效果最好）
- 与用户频道主题的关联度（优先选与频道画像高度一致的内容）

对每个视频给出：
1. 为什么值得研究（数据支撑）
2. 标题的套路分析
3. 如果有字幕内容，分析内容结构（开头hook、展开方式、结尾CTA）
4. 我可以做的类似选题（结合用户频道画像重新切入）

用中文回答。"""

        # 取播放量 TOP 30 + 参与率 TOP 20（去重后让 AI 选 10）
        if videos_df.empty:
            return "无视频数据"

        top_views = videos_df.nlargest(30, "view_count")
        top_eng = videos_df[videos_df["view_count"] >= 5000].nlargest(20, "engagement_rate")
        candidates = pd.concat([top_views, top_eng]).drop_duplicates(subset="video_id")

        video_entries = []
        for _, v in candidates.iterrows():
            vid_id = v["video_id"]
            transcript_text = transcripts.get(vid_id, "")
            # 截取前 500 字的字幕
            transcript_preview = transcript_text[:500] + "..." if len(transcript_text) > 500 else transcript_text

            video_entries.append(
                f"""视频: {v['title']}
  频道: {v.get('channel_title', '')}
  播放量: {v['view_count']:,} | 点赞: {v['like_count']:,} | 评论: {v['comment_count']:,}
  参与率: {v.get('engagement_rate', 0):.2%}
  时长: {v.get('duration_minutes', 0):.1f}分钟
  字幕摘要: {transcript_preview if transcript_preview else '（无字幕）'}"""
            )

        user = f"""以下是 {len(candidates)} 个候选视频的数据（含字幕摘要）。
请从中选出最值得我深入研究的 10 个视频，按推荐优先级排序。

{chr(10).join(video_entries)}
"""
        return self._call(system, user, max_tokens=6000)

    def analyze_transcripts_deep(self, transcripts: dict, video_info: dict) -> str:
        """深度分析视频字幕内容，提取内容结构和叙事模式"""
        system = f"""你是一位资深的 YouTube 视频内容架构师。
    用户当前频道画像：
    {self._profile_block()}

你的任务是：深度分析这些热门视频的字幕文本，提取出可复制的内容模式。

分析要点：
1. 开场 Hook 模式（前30秒是怎么抓人的）
2. 内容结构（总分总、列表型、故事型、问题-方案型）
3. 核心论点和论据类型（引经据典、个人故事、科学研究、历史案例）
4. 情感操控节奏（什么时候制造焦虑，什么时候给出希望）
5. 结尾 CTA 模式
6. 总结出 3-5 种可复制的视频脚本模板

给出具体的模板示例，而不是泛泛而谈。用中文回答。"""

        transcript_entries = []
        for vid_id, text in transcripts.items():
            if not text or len(text) < 100:
                continue
            info = video_info.get(vid_id, {})
            # 取前 1500 字（足够分析结构）
            preview = text[:1500]
            transcript_entries.append(
                f"""--- 视频: {info.get('title', vid_id)} ---
频道: {info.get('channel_title', '')} | 播放量: {info.get('view_count', 0):,}
字幕内容:
{preview}
"""
            )

        if not transcript_entries:
            return "没有足够的字幕数据进行分析"

        # 最多送 8 个字幕给 AI（控制 token）
        user = f"""以下是 {min(len(transcript_entries), 8)} 个高播放视频的字幕内容。
请深度分析它们的内容模式，提取可复制的框架。

{chr(10).join(transcript_entries[:8])}
"""
        return self._call(system, user, max_tokens=5000)

    def analyze_comments_deep(self, comments: list, video_info: dict) -> str:
        """深度分析评论，提取观众真实痛点而非无用关键词"""
        system = f"""你是一位用户洞察专家。
    用户当前频道画像：
    {self._profile_block()}

你的任务是：从这些视频评论中提取观众的真实需求和痛点。

不要做词频统计！"amen"、"god"、"love this" 这些无内容的附和评论没有分析价值。
只关注有实质内容的评论，分析：
1. 观众正在经历什么困境（具体到场景：被裁员、不知道职业方向、人际关系困境等）
2. 观众最渴望什么（具体需求：如何应对焦虑、如何做选择、如何面对失败等）
3. 哪些评论提到了具体的转变（"以前我XXX，看了这个视频后我XXX"——这说明内容真正解决了问题）
4. 有没有观众主动提到东方哲学/中国文化的（说明这个切入点有市场）
5. 基于这些痛点，建议 5 个具体的视频选题（要精确到标题）

用中文回答。"""

        # 过滤有内容的评论（长度 > 50 字符，排除纯附和）
        meaningful = [c for c in comments if len(c.get("text", "")) > 50]
        # 按点赞数排序，高赞 = 代表性强
        meaningful.sort(key=lambda x: x.get("like_count", 0), reverse=True)

        comment_entries = []
        for c in meaningful[:60]:  # 取前 60 条有内容评论
            vid_id = c.get("video_id", "")
            info = video_info.get(vid_id, {})
            comment_entries.append(
                f'[{c["like_count"]} likes | video: {info.get("title", "")[:40]}] {c["text"][:300]}'
            )

        if not comment_entries:
            return "没有足够有实质内容的评论数据"

        user = f"""以下是 {len(comment_entries)} 条高赞有实质内容的观众评论。
请深度分析观众的真实需求和痛点。

{chr(10).join(comment_entries)}
"""
        return self._call(system, user, max_tokens=4000)

    def generate_action_plan(
        self,
        top3_analysis: str,
        top10_analysis: str,
        transcript_analysis: str,
        comment_analysis: str,
        channels_data: dict,
    ) -> str:
        """基于所有深度分析，生成具体的行动方案"""
        system = f"""你是一位资深 YouTube 增长教练，专门帮助新频道制定 0 到 1 的增长策略。
    用户当前频道画像：
    {self._profile_block()}

你的任务是输出一份可以直接执行的行动方案，不要任何空话套话。每个建议都要具体到可以直接执行。
用中文回答。"""

        user = f"""以下是基于数据分析得出的四份深度洞察报告：

═══ 最值得关注的3个频道分析 ═══
{top3_analysis[:2000]}

═══ 最值得研究的10个视频分析 ═══
{top10_analysis[:2000]}

═══ 视频内容结构分析 ═══
{transcript_analysis[:2000]}

═══ 观众痛点分析 ═══
{comment_analysis[:2000]}

请基于以上所有分析，输出：

1. 【前10个视频选题】精确到标题（按用户频道要求的语言），每个标题说明为什么选这个题（30字以内）
2. 【视频脚本模板】给出1个完整的示例脚本大纲（包含开场hook、几个要点、结尾CTA），以最适合用户频道画像的格式
3. 【第1个月行动表】精确到每周要做什么（4周计划）
4. 【差异化定位声明】一句话总结频道定位，要让人一听就知道你和 Daily Stoic 等频道有什么不同
"""
        return self._call(system, user, max_tokens=5000)
