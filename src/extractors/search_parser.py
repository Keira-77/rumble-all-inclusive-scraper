thonimport logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils.helpers import fetch_url, parse_number

logger = logging.getLogger("extractors.search")

def extract_search(
    url: str,
    config: Optional[Dict[str, Any]] = None,
    search_keyword: Optional[str] = None,
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """
    Extract search results or trending/editor-pick style listings from Rumble.

    Returns a list of video-centric records tagged with `searchKeyword`
    and possibly `trendingCategory`.
    """
    cfg = config or {}
    http_cfg = cfg.get("http", {})
    scraper_cfg = cfg.get("scraper", {})

    max_results = int(scraper_cfg.get("max_results_per_search", max_results))

    html = fetch_url(
        url,
        headers=http_cfg.get("headers"),
        proxies=http_cfg.get("proxy"),
        timeout=http_cfg.get("timeout", 15),
        max_retries=http_cfg.get("max_retries", 3),
    )
    soup = BeautifulSoup(html, "lxml")

    records: List[Dict[str, Any]] = []

    # Rumble search often uses cards or list items with anchor tags to the videos.
    for card in soup.select("a[href*='/v']"):
        href = card.get("href")
        if not href:
            continue

        video_url = urljoin(url, href)
        title = card.get("title") or card.get_text(strip=True) or video_url

        wrapper = card.parent
        while wrapper and wrapper.name not in ("article", "li", "div"):
            wrapper = wrapper.parent

        channel_name = None
        channel_url = None
        if wrapper:
            ch_link = wrapper.select_one("a[href*='/c/'], a[href*='/user/']")
            if ch_link:
                if ch_link.get_text(strip=True):
                    channel_name = ch_link.get_text(strip=True)
                if ch_link.get("href"):
                    channel_url = urljoin(url, ch_link["href"])

        views_text = None
        if wrapper:
            views_span = wrapper.select_one(".views, .video-item--views")
            if views_span:
                views_text = views_span.get_text(strip=True)
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
            "playlistName": None,
            "searchKeyword": search_keyword,
            "trendingCategory": None,
        }
        records.append(record)
        if len(records) >= max_results:
            break

    logger.info(
        "Extracted %s search records for keyword '%s' from %s",
        len(records),
        search_keyword,
        url,
    )
    return records