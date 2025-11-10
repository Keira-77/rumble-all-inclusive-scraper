thonimport logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils.helpers import fetch_url, parse_number

logger = logging.getLogger("extractors.channel")

def _extract_channel_name(soup: BeautifulSoup) -> Optional[str]:
    heading = soup.select_one("h1, .channel-header-title, .media-heading")
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)
    return None

def _extract_video_cards(soup: BeautifulSoup) -> List[Any]:
    """
    Rumble uses a few different layouts. Here we try to grab any
    anchor element that looks like a video card (contains `/v`).
    """
    cards = []
    for a in soup.select("a[href*='/v']"):
        cards.append(a)
    return cards

def extract_channel(
    url: str, config: Optional[Dict[str, Any]] = None, max_videos: int = 50
) -> List[Dict[str, Any]]:
    """
    Extract videos listed on a channel page.

    Since the main output schema is video-centric, this returns
    a list of video records enriched with channel details.
    """
    cfg = config or {}
    http_cfg = cfg.get("http", {})
    scraper_cfg = cfg.get("scraper", {})

    max_videos = int(scraper_cfg.get("max_videos_per_channel", max_videos))

    html = fetch_url(
        url,
        headers=http_cfg.get("headers"),
        proxies=http_cfg.get("proxy"),
        timeout=http_cfg.get("timeout", 15),
        max_retries=http_cfg.get("max_retries", 3),
    )

    soup = BeautifulSoup(html, "lxml")
    channel_name = _extract_channel_name(soup) or "Unknown channel"

    records: List[Dict[str, Any]] = []
    cards = _extract_video_cards(soup)
    logger.info("Found %s potential video cards on channel page", len(cards))

    for card in cards:
        href = card.get("href")
        if not href:
            continue

        video_url = urljoin(url, href)
        title = card.get("title") or card.get_text(strip=True) or video_url

        views_span = card.select_one(".views, .video-item--views")
        views_text = views_span.get_text(strip=True) if views_span else None
        views = parse_number(views_text) if views_text else None

        record: Dict[str, Any] = {
            "videoTitle": title,
            "videoUrl": video_url,
            "channelName": channel_name,
            "channelUrl": url,
            "views": views,
            "likes": None,
            "comments": None,
            "revenue": None,
            "uploadDate": None,
            "description": None,
            "playlistName": None,
            "searchKeyword": None,
            "trendingCategory": None,
        }
        records.append(record)
        if len(records) >= max_videos:
            break

    logger.info(
        "Extracted %s records from channel %s (%s)", len(records), channel_name, url
    )
    return records