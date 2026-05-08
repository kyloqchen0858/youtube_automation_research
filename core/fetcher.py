"""
YouTube Data Fetcher — 数据抓取模块
使用 YouTube Data API v3 + youtube-transcript-api
核心优化：用 playlistItems.list（1单位）替代 search.list（100单位），节省 99% API 配额
"""

import re
import time
import logging
import html
import json
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def _parse_iso8601_duration(duration_str: str) -> int:
    """将 YouTube ISO 8601 时长（PT1H2M3S）转换为秒数"""
    if not duration_str:
        return 0
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration_str)
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def _call_with_backoff(request, max_retries: int = 5):
    """带指数退避的 API 调用，处理限流和网络错误"""
    for attempt in range(max_retries):
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in (403, 429):
                wait = 2 ** attempt
                logger.warning(f"API 限流，等待 {wait}s 后重试 (第 {attempt+1} 次)")
                time.sleep(wait)
            elif e.resp.status == 404:
                logger.warning(f"资源不存在: {e}")
                return None
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"网络错误: {e}，等待 {wait}s 后重试")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("API 调用超过最大重试次数")


class YouTubeFetcher:
    """YouTube 数据抓取器"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.youtube = build("youtube", "v3", developerKey=api_key)

    def validate_api_key(self) -> bool:
        """验证 API Key 是否有效"""
        try:
            req = self.youtube.channels().list(part="id", id="UC_x5XG1OV2P6uZZ5FSM9Ttw", maxResults=1)
            resp = _call_with_backoff(req)
            return resp is not None
        except Exception:
            return False

    # ── 频道发现 ──────────────────────────────────────────────

    def search_channels(self, keyword: str, max_results: int = 10) -> list[dict]:
        """
        用关键词搜索频道（search.list，100单位/次，慎用）
        返回：[{channel_id, title, description, subscriber_count, video_count, thumbnail}]
        """
        req = self.youtube.search().list(
            part="snippet",
            q=keyword,
            type="channel",
            maxResults=min(max_results, 50),
            order="relevance",
        )
        resp = _call_with_backoff(req)
        if not resp:
            return []

        channel_ids = [item["snippet"]["channelId"] for item in resp.get("items", [])]
        if not channel_ids:
            return []

        return self._get_channels_info(channel_ids)

    def search_videos(self, keyword: str, max_results: int = 20, published_after: str = None) -> list[dict]:
        """
        用关键词搜索视频（search.list，100单位/次）
        published_after: ISO 格式日期字符串，如 '2026-01-20T00:00:00Z'
        """
        params = dict(
            part="snippet",
            q=keyword,
            type="video",
            maxResults=min(max_results, 50),
            order="viewCount",
        )
        if published_after:
            params["publishedAfter"] = published_after

        req = self.youtube.search().list(**params)
        resp = _call_with_backoff(req)
        if not resp:
            return []

        video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]
        channel_ids = list({item["snippet"]["channelId"] for item in resp.get("items", [])})

        return channel_ids, video_ids

    def _get_channels_info(self, channel_ids: list[str]) -> list[dict]:
        """批量获取频道详情（channels.list，1单位/请求）"""
        results = []
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i : i + 50]
            req = self.youtube.channels().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            )
            resp = _call_with_backoff(req)
            if not resp:
                continue

            for item in resp.get("items", []):
                stats = item.get("statistics", {})
                results.append(
                    {
                        "channel_id": item["id"],
                        "title": item["snippet"]["title"],
                        "description": item["snippet"].get("description", ""),
                        "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                        "subscriber_count": int(stats.get("subscriberCount", 0)),
                        "video_count": int(stats.get("videoCount", 0)),
                        "view_count": int(stats.get("viewCount", 0)),
                        "created_at": item["snippet"].get("publishedAt", ""),
                        "uploads_playlist_id": item.get("contentDetails", {})
                        .get("relatedPlaylists", {})
                        .get("uploads", ""),
                    }
                )
        return results

    def get_channel_info(self, channel_id: str) -> Optional[dict]:
        """获取单个频道信息"""
        results = self._get_channels_info([channel_id])
        return results[0] if results else None

    # ── 视频数据 ──────────────────────────────────────────────

    def get_channel_videos(self, channel_id: str, max_videos: int = 50, progress_callback=None) -> pd.DataFrame:
        """
        获取频道全部视频（playlistItems + videos.list，配额友好）
        1) channels.list 获取 uploads playlist ID (1单位)
        2) playlistItems.list 分页获取视频 ID (1单位/页, 每页50条)
        3) videos.list 批量获取详情 (1单位/50个视频)
        """
        # Step 1: 获取 uploads playlist ID
        ch_info = self.get_channel_info(channel_id)
        if not ch_info or not ch_info.get("uploads_playlist_id"):
            return pd.DataFrame()

        playlist_id = ch_info["uploads_playlist_id"]

        # Step 2: 获取视频 ID 列表
        video_ids = []
        next_page = None
        while len(video_ids) < max_videos:
            req = self.youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=min(50, max_videos - len(video_ids)),
                pageToken=next_page,
            )
            resp = _call_with_backoff(req)
            if not resp:
                break

            for item in resp.get("items", []):
                video_ids.append(item["contentDetails"]["videoId"])

            next_page = resp.get("nextPageToken")
            if not next_page:
                break

        if not video_ids:
            return pd.DataFrame()

        # Step 3: 批量获取视频详情
        videos = []
        total_batches = (len(video_ids) + 49) // 50
        for batch_idx, i in enumerate(range(0, len(video_ids), 50)):
            batch = video_ids[i : i + 50]
            req = self.youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            )
            resp = _call_with_backoff(req)
            if not resp:
                continue

            for item in resp.get("items", []):
                stats = item.get("statistics", {})
                snippet = item["snippet"]
                videos.append(
                    {
                        "video_id": item["id"],
                        "title": snippet["title"],
                        "description": snippet.get("description", "")[:500],
                        "published_at": snippet["publishedAt"],
                        "channel_id": snippet["channelId"],
                        "channel_title": snippet["channelTitle"],
                        "duration_seconds": _parse_iso8601_duration(
                            item.get("contentDetails", {}).get("duration", "")
                        ),
                        "view_count": int(stats.get("viewCount", 0)),
                        "like_count": int(stats.get("likeCount", 0)),
                        "comment_count": int(stats.get("commentCount", 0)),
                        "thumbnail": snippet["thumbnails"].get("medium", {}).get("url", ""),
                    }
                )

            if progress_callback:
                progress_callback((batch_idx + 1) / total_batches)

        df = pd.DataFrame(videos)
        if not df.empty:
            df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
            df["duration_minutes"] = df["duration_seconds"] / 60
        return df

    # ── 评论 ──────────────────────────────────────────────────

    def get_video_comments(self, video_id: str, max_comments: int = 100) -> list[dict]:
        """
        获取视频热门评论（commentThreads.list，1单位/页）
        按相关性排序以获取高赞评论
        """
        comments = []
        next_page = None

        while len(comments) < max_comments:
            try:
                req = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=min(20, max_comments - len(comments)),
                    order="relevance",
                    textFormat="plainText",
                    pageToken=next_page,
                )
                resp = _call_with_backoff(req)
                if not resp:
                    break

                for item in resp.get("items", []):
                    c = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append(
                        {
                            "video_id": video_id,
                            "author": c["authorDisplayName"],
                            "text": c["textDisplay"],
                            "like_count": c["likeCount"],
                            "published_at": c["publishedAt"],
                        }
                    )

                next_page = resp.get("nextPageToken")
                if not next_page:
                    break

            except HttpError as e:
                if "commentsDisabled" in str(e) or e.resp.status == 403:
                    logger.info(f"视频 {video_id} 评论已关闭")
                    break
                raise

        return comments

    # ── 字幕 ──────────────────────────────────────────────────

    @staticmethod
    def _clean_caption_text(text: str) -> str:
        cleaned = html.unescape(text or "")
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _vtt_to_text(vtt_text: str) -> str:
        chunks = []
        for block in re.split(r"\r?\n\r?\n", vtt_text or ""):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            text_lines = [
                line for line in lines
                if "-->" not in line
                and not line.startswith("WEBVTT")
                and not line.startswith("Kind:")
                and not line.startswith("Language:")
                and not line.isdigit()
            ]
            if text_lines:
                chunks.append(YouTubeFetcher._clean_caption_text(text_lines[-1]))

        deduped = []
        for chunk in chunks:
            if chunk and (not deduped or deduped[-1] != chunk):
                deduped.append(chunk)
        return " ".join(deduped).strip()

    @staticmethod
    def _json3_to_text(raw_text: str) -> str:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return ""

        segments = []
        for event in payload.get("events", []):
            segs = event.get("segs") or []
            text = "".join(seg.get("utf8", "") for seg in segs)
            text = YouTubeFetcher._clean_caption_text(text)
            if text and (not segments or segments[-1] != text):
                segments.append(text)
        return " ".join(segments).strip()

    @staticmethod
    def _download_caption_url(downloader, url: str) -> str:
        with downloader.urlopen(url) as response:
            return response.read().decode("utf-8", errors="ignore")

    @staticmethod
    def _is_rate_limited_caption_error(exc: Exception) -> bool:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in (403, 429):
            return True

        message = str(exc).lower()
        return "429" in message or "too many requests" in message or "http error 403" in message

    @staticmethod
    def _extract_caption_from_yt_dlp(video_id: str, languages: list[str]) -> Optional[str]:
        try:
            from yt_dlp import YoutubeDL
        except Exception as exc:
            logger.debug(f"yt-dlp unavailable for transcript fallback {video_id}: {exc}")
            return None

        try:
            with YoutubeDL(
                {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "socket_timeout": 5,
                    "retries": 0,
                    "extractor_retries": 0,
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": languages,
                    "subtitlesformat": "vtt/json3/best",
                }
            ) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

                caption_sources = [
                    info.get("requested_subtitles") or {},
                    info.get("subtitles") or {},
                    info.get("automatic_captions") or {},
                ]

                language_candidates = []
                for lang in languages:
                    if lang not in language_candidates:
                        language_candidates.append(lang)
                    base_lang = lang.split("-")[0]
                    if base_lang and base_lang not in language_candidates:
                        language_candidates.append(base_lang)

                for source in caption_sources:
                    if not source:
                        continue
                    for lang in language_candidates:
                        entries = source.get(lang)
                        if not entries:
                            entries = next(
                                (value for key, value in source.items() if key.startswith(f"{lang}-") or key == lang),
                                None,
                            )
                        if not entries:
                            continue

                        if isinstance(entries, dict):
                            entries = [entries]

                        preferred = sorted(
                            entries,
                            key=lambda item: 0 if item.get("ext") == "vtt" else (1 if item.get("ext") == "json3" else 2),
                        )
                        for entry in preferred:
                            url = entry.get("url")
                            if not url:
                                continue
                            try:
                                raw_text = YouTubeFetcher._download_caption_url(ydl, url)
                            except Exception as exc:
                                logger.debug(f"caption URL fetch failed for {video_id}: {exc}")
                                if YouTubeFetcher._is_rate_limited_caption_error(exc):
                                    return None
                                continue

                            ext = (entry.get("ext") or "").lower()
                            if ext == "json3":
                                parsed = YouTubeFetcher._json3_to_text(raw_text)
                            else:
                                parsed = YouTubeFetcher._vtt_to_text(raw_text)
                            if len(parsed) > 80:
                                return parsed
        except Exception as exc:
            logger.debug(f"yt-dlp transcript fallback failed for {video_id}: {exc}")
            return None

        return None

    @staticmethod
    def get_video_transcript(video_id: str, languages: list[str] = None) -> Optional[str]:
        """
        获取视频字幕文本（零 API 配额，使用 youtube-transcript-api）
        优先中文，fallback 英文
        """
        if languages is None:
            languages = ["zh-Hans", "zh-CN", "zh", "en", "en-US"]

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            ytt_api = YouTubeTranscriptApi()
            transcript = ytt_api.fetch(video_id, languages=languages)
            full_text = " ".join(snippet.text for snippet in transcript)
            return full_text
        except Exception as e:
            logger.debug(f"youtube-transcript-api 字幕获取失败 {video_id}: {e}")

        fallback = YouTubeFetcher._extract_caption_from_yt_dlp(video_id, languages)
        if fallback:
            return fallback

        return None
