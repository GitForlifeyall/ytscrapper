import math
import re
import asyncio
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable
import yt_dlp

def normalize_channel_input(input_str: str, content_type: str = "shorts") -> str:
    """Normalize handle, username, or URL to YouTube channel URL with proper tab (/shorts, /videos)."""
    s = input_str.strip()
    if not s:
        return ""

    # Do not turn a direct video URL into the malformed
    # ``/shorts/<id>/shorts`` form.  scrape_channel resolves it to the
    # uploader's channel before listing channel content.
    if is_youtube_video_url(s):
        return s
    
    target_tab = "shorts" if content_type == "shorts" else ("videos" if content_type == "videos" else "")

    # Clean existing tab if present
    for tab in ["/videos", "/shorts", "/streams", "/featured", "/playlists"]:
        if s.endswith(tab):
            s = s[:-len(tab)]
            break

    # If starts with http(s)
    if s.startswith("http://") or s.startswith("https://"):
        if target_tab:
            return f"{s.rstrip('/')}/{target_tab}"
        return s
    
    # If starts with @
    if s.startswith("@"):
        if target_tab:
            return f"https://www.youtube.com/{s}/{target_tab}"
        return f"https://www.youtube.com/{s}"
    
    # Channel ID (UC...)
    if s.startswith("UC") and len(s) == 24:
        if target_tab:
            return f"https://www.youtube.com/channel/{s}/{target_tab}"
        return f"https://www.youtube.com/channel/{s}"
    
    # Plain username / handle
    clean_handle = s.lstrip("@")
    if target_tab:
        return f"https://www.youtube.com/@{clean_handle}/{target_tab}"
    return f"https://www.youtube.com/@{clean_handle}"


def is_youtube_video_url(input_str: str) -> bool:
    """Return True for YouTube watch, Shorts, and youtu.be video URLs."""
    try:
        parsed = urlparse(input_str.strip())
    except ValueError:
        return False

    host = parsed.netloc.lower().split(":", 1)[0]
    if host in {"youtu.be", "www.youtu.be"}:
        return bool(parsed.path.strip("/"))
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        return False
    return parsed.path.startswith("/shorts/") or bool(parse_qs(parsed.query).get("v"))

def extract_channel_display_name(raw_input: str, info_dict: Optional[Dict[str, Any]] = None) -> str:
    if info_dict and info_dict.get("uploader"):
        return info_dict.get("uploader")
    if info_dict and info_dict.get("channel"):
        return info_dict.get("channel")
    if info_dict and info_dict.get("title"):
        return info_dict.get("title")
    cleaned = raw_input.strip()
    cleaned = re.sub(r"https?://(www\.)?youtube\.com/(@|c/|channel/)?", "", cleaned)
    for tab in ["/videos", "/shorts", "/streams", "/playlists"]:
        cleaned = cleaned.replace(tab, "")
    cleaned = cleaned.replace("/", "")
    return cleaned if cleaned else raw_input

class YouTubeScraper:
    def __init__(self, max_threads: int = 5):
        self.executor = ThreadPoolExecutor(max_workers=max_threads)

    def _get_channel_videos_flat(self, channel_url: str, max_videos: Optional[int] = None) -> Dict[str, Any]:
        """Fast flat extraction of channel videos list."""
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        if max_videos and max_videos > 0:
            ydl_opts['playlistend'] = max_videos

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            return info or {}

    def _resolve_video_to_channel(self, video_url: str) -> str:
        """Resolve a single YouTube video/Short URL to its channel URL."""
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False) or {}

        channel_url = info.get('channel_url') or info.get('uploader_url')
        if channel_url:
            return normalize_channel_input(channel_url, content_type="shorts")

        channel_id = info.get('channel_id')
        if channel_id:
            return normalize_channel_input(channel_id, content_type="shorts")

        uploader_id = info.get('uploader_id')
        if uploader_id and str(uploader_id).startswith('@'):
            return normalize_channel_input(str(uploader_id), content_type="shorts")

        raise ValueError(f"Could not determine the channel for video URL: {video_url}")

    def _fetch_single_video_details(self, video_id: str) -> Dict[str, Any]:
        """Fetch detailed stats (comment count, exact view count) for a single video."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {
                    'comment_count': info.get('comment_count') or 0,
                    'view_count': info.get('view_count') or 0,
                    'like_count': info.get('like_count') or 0,
                    'duration': info.get('duration') or 0,
                    'upload_date': info.get('upload_date') or '',
                }
            except Exception:
                return {'comment_count': 0, 'view_count': 0, 'like_count': 0, 'duration': 0, 'upload_date': ''}

    def scrape_channel(
        self,
        raw_channel: str,
        content_type: str = "shorts",
        max_videos_limit: Optional[int] = None,
        fetch_comments: bool = False,
        min_views: int = 0,
        progress_cb: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Any]:
        """Scrape all/capped Shorts (or videos) for a single channel."""
        # A direct Shorts URL identifies one video, not a channel. Resolve its
        # uploader first so the normal channel listing/ranking flow can run.
        source_url = raw_channel.strip()
        if is_youtube_video_url(source_url):
            normalized_url = self._resolve_video_to_channel(source_url)
        else:
            normalized_url = normalize_channel_input(source_url, content_type=content_type)
        type_label = "Shorts" if content_type == "shorts" else "Videos"
        
        if progress_cb:
            progress_cb(f"Fetching {type_label} list for {raw_channel}...", 10, 100)

        info = self._get_channel_videos_flat(normalized_url, max_videos=max_videos_limit)
        
        channel_title = extract_channel_display_name(raw_channel, info)
        entries = info.get('entries') or []
        
        valid_entries = []
        for e in entries:
            if not e:
                continue
            video_id = e.get('id') or e.get('url')
            if not video_id:
                continue
            
            # Extract video ID
            if "youtube.com" in video_id or "youtu.be" in video_id:
                m = re.search(r"(?:v=|be/|shorts/)([\w-]{11})", video_id)
                video_id = m.group(1) if m else video_id

            view_count = e.get('view_count') or 0
            comment_count = e.get('comment_count') or 0
            
            # Format clean Shorts URL if content_type is shorts
            if content_type == "shorts":
                item_url = f"https://www.youtube.com/shorts/{video_id}"
            else:
                item_url = f"https://www.youtube.com/watch?v={video_id}"

            valid_entries.append({
                'id': video_id,
                'title': e.get('title') or f"Short {video_id}",
                'url': item_url,
                'view_count': int(view_count) if str(view_count).isdigit() else 0,
                'comment_count': int(comment_count) if str(comment_count).isdigit() else 0,
                'duration': e.get('duration') or 0,
                'is_short': (content_type == "shorts"),
                'channel': channel_title,
                'thumbnails': e.get('thumbnails') or [],
                'thumbnail': e.get('thumbnail') or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if len(video_id) == 11 else ""),
                'upload_date': e.get('upload_date') or e.get('timestamp') or "",
            })

        total_scanned = len(valid_entries)
        if min_views > 0:
            valid_entries = [v for v in valid_entries if v['view_count'] >= min_views]
        total_found = len(valid_entries)
        if progress_cb:
            if min_views > 0:
                progress_cb(
                    f"Scanned {total_scanned} {type_label.lower()}; {total_found} meet the minimum {min_views:,} views...",
                    40, 100
                )
            else:
                progress_cb(f"Found {total_found} {type_label.lower()} for {channel_title}. Processing metadata...", 40, 100)

        # Optional comment enrichment
        if fetch_comments and total_found > 0:
            needs_comment_fetch = any(v['comment_count'] == 0 for v in valid_entries[:5])
            if needs_comment_fetch:
                max_enrich = min(total_found, 100)
                if progress_cb:
                    progress_cb(f"Fetching detailed comment counts for top {max_enrich} candidates...", 60, 100)
                
                def _enrich(item):
                    details = self._fetch_single_video_details(item['id'])
                    if details['comment_count']:
                        item['comment_count'] = details['comment_count']
                    if details['view_count'] and not item['view_count']:
                        item['view_count'] = details['view_count']
                    return item

                with ThreadPoolExecutor(max_workers=8) as pool:
                    valid_entries[:max_enrich] = list(pool.map(_enrich, valid_entries[:max_enrich]))

        if progress_cb:
            progress_cb(f"Completed extraction for {channel_title} ({total_found} {type_label.lower()}).", 100, 100)

        return {
            'channel_name': channel_title,
            'channel_url': normalized_url,
            'content_type': content_type,
            'total_videos': total_found,
            'total_videos_scanned': total_scanned,
            'min_views': min_views,
            'videos': valid_entries
        }

    def filter_top_x_percent(
        self,
        videos: List[Dict[str, Any]],
        percentage: float,
        metric: str = "views",  # "views", "comments", "combined"
        min_videos: int = 1
    ) -> List[Dict[str, Any]]:
        """Calculate top X% of videos/shorts based on selected metric."""
        if not videos:
            return []
        
        for v in videos:
            views = v.get('view_count', 0) or 0
            comments = v.get('comment_count', 0) or 0
            if metric == "comments":
                v['score'] = comments
            elif metric == "combined":
                v['score'] = views + (comments * 15)
            else:
                v['score'] = views

        # Sort descending by score
        sorted_videos = sorted(videos, key=lambda x: x.get('score', 0), reverse=True)
        
        # Calculate number of items to keep
        total_count = len(sorted_videos)
        pct = max(0.1, min(100.0, float(percentage)))
        count_to_keep = math.ceil((pct / 100.0) * total_count)
        count_to_keep = max(min_videos, min(count_to_keep, total_count))

        top_videos = sorted_videos[:count_to_keep]
        for idx, item in enumerate(top_videos, 1):
            item['rank'] = idx
            item['percentile_pct'] = round((idx / total_count) * 100, 1)

        return top_videos

    async def scrape_multiple_channels_async(
        self,
        channels: List[str],
        content_type: str = "shorts",
        top_percentage: float = 10.0,
        metric: str = "views",
        max_videos_per_channel: Optional[int] = None,
        fetch_comments: bool = False,
        min_views: int = 0,
        status_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Scrape multiple channels asynchronously and collect top X% shorts/videos."""
        results_by_channel = []
        all_top_urls = []
        all_top_videos = []
        total_scraped_videos = 0
        total_scanned_videos = 0

        clean_channels = [c.strip() for c in channels if c.strip()]
        total_channels = len(clean_channels)
        type_label = "Shorts" if content_type == "shorts" else "Videos"

        for idx, channel in enumerate(clean_channels):
            if status_callback:
                await status_callback({
                    'type': 'progress',
                    'channel': channel,
                    'channel_index': idx + 1,
                    'total_channels': total_channels,
                    'message': f"[{idx+1}/{total_channels}] Scraping {type_label} for {channel}...",
                    'progress_pct': int(((idx) / total_channels) * 100)
                })

            loop = asyncio.get_event_loop()
            try:
                channel_data = await loop.run_in_executor(
                    self.executor,
                    self.scrape_channel,
                    channel,
                    content_type,
                    max_videos_per_channel,
                    fetch_comments,
                    min_views
                )
                
                videos = channel_data.get('videos', [])
                total_scraped_videos += len(videos)
                total_scanned_videos += channel_data.get('total_videos_scanned', len(videos))
                
                # Filter top X%
                top_vids = self.filter_top_x_percent(videos, top_percentage, metric=metric)
                
                channel_result = {
                    'channel_name': channel_data.get('channel_name', channel),
                    'channel_url': channel_data.get('channel_url'),
                    'content_type': content_type,
                    'total_videos_found': len(videos),
                    'top_count': len(top_vids),
                    'min_views': min_views,
                    'percentage_used': top_percentage,
                    'metric': metric,
                    'top_videos': top_vids
                }
                results_by_channel.append(channel_result)
                
                for v in top_vids:
                    all_top_urls.append(v['url'])
                    all_top_videos.append(v)

                if status_callback:
                    await status_callback({
                        'type': 'channel_done',
                        'channel': channel_data.get('channel_name', channel),
                        'channel_index': idx + 1,
                        'total_channels': total_channels,
                        'videos_found': len(videos),
                        'top_extracted': len(top_vids),
                        'message': f"✓ Extracted top {len(top_vids)} ({top_percentage}%) of {len(videos)} {type_label.lower()} from {channel_data.get('channel_name', channel)}",
                        'progress_pct': int(((idx + 1) / total_channels) * 100)
                    })

            except Exception as e:
                if status_callback:
                    await status_callback({
                        'type': 'error',
                        'channel': channel,
                        'message': f"Error scraping {channel}: {str(e)}",
                        'channel_index': idx + 1,
                        'total_channels': total_channels,
                        'progress_pct': int(((idx + 1) / total_channels) * 100)
                    })

        txt_content = "\n".join(all_top_urls)

        return {
            'channels_processed': len(results_by_channel),
            'total_channels': total_channels,
            'content_type': content_type,
            'total_videos_scraped': total_scraped_videos,
            'total_videos_scanned': total_scanned_videos,
            'total_top_videos': len(all_top_videos),
            'percentage': top_percentage,
            'metric': metric,
            'min_views': min_views,
            'urls_list': all_top_urls,
            'txt_dump': txt_content,
            'all_top_videos': all_top_videos,
            'channel_results': results_by_channel
        }

scraper_instance = YouTubeScraper()
