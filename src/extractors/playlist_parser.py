thonimport logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils.helpers import fetch_url, parse_number

logger = logging.getLogger("extractors.playlist")

def _extract_playlist_name(soup: BeautifulSoup) -> Optional[str]:
    heading = soup.select_one("h1, .playlist-title, .media-heading")
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)
    return None

def extract_playlist(
    url: str,
    config: Optional[Dict[str, Any]] = None,
    max_videos: int = 100,
) -> List[Dict[str, Any]]:
    """
    Extract videos from a playlist page.

    Outputs a list of video records tagged with `playlistName`.
    """
    cfg = config or {}
    http_cfg = cfg.get("http", {})
    scraper_cfg = cfg.get("scraper", {})

    max_videos = int(scraper_cfg.get("max_videos_per_playlist", max_videos))

    html = fetch_url(
        url,
        headers=http_cfg.get("headers"),
        proxies=http_cfg.get("proxy"),
        timeout=http_cfg.get("timeout", 15),
        max_retries=http_cfg.get("max_retries", 3),
    )
    soup = BeautifulSoup(html, "lxml")
    playlist_name = _extract_playlist_name(soup) or "Rumble Playlist"

    records: List[Dict[str, Any]] = []

    # Attempt to find any video cards inside the playlist container.
    playlist_container = soup.select_one(
        ".playlist-items, .video-list, .items-list"
    ) or soup

    for card in playlist_container.select("a[href*='/v']"):
        href = card.get("href")
        if not href:
            continue

        video_url = urljoin(url, href)
        title = card.get("title") or card.get_text(strip=True) or video_url

        # We might be able to pick up channel info from sibling elements.
        channel_name = None
        channel_link = None
        parent = card.parent
        if parent:
            channel_link = parent.select_one("a[href*='/c/'], a[href*='/user/']")
        if channel_link and channel_link.get_text(strip=True):
            channel_name = channel_link.get_text(strip=True)
        channel_url = (
            urljoin(url, channel_link["href"])
            if channel_link and channel_link.get("href")
            else None
        )

        views_span = card.select_one(".views, .video-item--views")
        views_text = views_span.get_text(strip=True) if views_span else None
        views = parse_number(views_text) if views_text else None

        record: Dict[str, Any] = {
            "videoTitle": title,
            "videoUrl": video_url,
            "channelName": channel_name,
            "channelUrl": channel_url,
            "views": views,
            "likes": None,
            "comments": None,
            "revenue": None,
            "uploadDate": None,
            "description": None,
            "playlistName": playlist_name,
            "searchKeyword": None,
            "trendingCategory": None,
        }
        records.append(record)
        if len(records) >= max_videos:
            break

    logger.info(
        "Extracted %s playlist records from %s (%s)",
        len(records),
        playlist_name,
        url,
    )
    return records