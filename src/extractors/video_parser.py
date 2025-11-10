thonimport logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils.helpers import fetch_url, parse_number

logger = logging.getLogger("extractors.video")

def _get_meta_content(soup: BeautifulSoup, key: str) -> Optional[str]:
    meta = soup.find("meta", attrs={"property": key}) or soup.find(
        "meta", attrs={"name": key}
    )
    if meta and meta.get("content"):
        return meta["content"].strip()
    return None

def _get_first_text(soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
    for selector in selectors:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return None

def parse_video_html(
    soup: BeautifulSoup,
    url: str,
    search_keyword: Optional[str] = None,
    playlist_name: Optional[str] = None,
    trending_category: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse a single Rumble video page into a structured record."""
    title = (
        _get_meta_content(soup, "og:title")
        or _get_first_text(soup, ["h1", ".video-title", ".video-item--title"])
        or ""
    )

    description = (
        _get_meta_content(soup, "og:description")
        or _get_first_text(soup, [".video-description", ".description", "p.lead"])
    )

    channel_name = _get_first_text(
        soup,
        [
            "a[href*='/c/']",
            ".media-heading a",
            ".channel-name",
            "a[href*='/user/']",
        ],
    )

    channel_url = None
    channel_link = soup.select_one(
        "a[href*='/c/'], .media-heading a[href*='/'], a.channel-name"
    )
    if channel_link and channel_link.get("href"):
        channel_url = urljoin(url, channel_link["href"])

    # Views, likes, comments and revenue are rendered in various ways on Rumble;
    # we try a few common patterns and fall back gracefully.
    views_text = _get_first_text(
        soup, [".media-heading .views", ".rmp-view-count", "span.views"]
    )
    likes_text = _get_first_text(
        soup,
        [
            ".rmp-like-count",
            ".vote-up .count",
            ".rmp-vote-up .count",
            ".video-engagement .likes",
        ],
    )
    comments_text = _get_first_text(
        soup, [".rmp-comment-count", ".comment-count", ".video-comments-count"]
    )
    revenue_text = _get_first_text(
        soup,
        [
            ".video-revenue",
            ".rmp-revenue",
            ".earnings",
        ],
    )

    views = parse_number(views_text) if views_text else None
    likes = parse_number(likes_text) if likes_text else None
    comments = parse_number(comments_text) if comments_text else None

    upload_date = (
        _get_meta_content(soup, "article:published_time")
        or _get_meta_content(soup, "og:video:release_date")
        or _get_meta_content(soup, "date")
    )

    record: Dict[str, Any] = {
        "videoTitle": title,
        "videoUrl": url,
        "channelName": channel_name,
        "channelUrl": channel_url,
        "views": views,
        "likes": likes,
        "comments": comments,
        "revenue": revenue_text,
        "uploadDate": upload_date,
        "description": description,
        "playlistName": playlist_name,
        "searchKeyword": search_keyword,
        "trendingCategory": trending_category,
    }
    return record

def extract_video(
    url: str,
    config: Optional[Dict[str, Any]] = None,
    search_keyword: Optional[str] = None,
    playlist_name: Optional[str] = None,
    trending_category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Extract a single video given its URL.

    Returns a list with exactly one record, for consistency with other extractors.
    """
    cfg = config or {}
    http_cfg = cfg.get("http", {})

    html = fetch_url(
        url,
        headers=http_cfg.get("headers"),
        proxies=http_cfg.get("proxy"),
        timeout=http_cfg.get("timeout", 15),
        max_retries=http_cfg.get("max_retries", 3),
    )

    soup = BeautifulSoup(html, "lxml")
    record = parse_video_html(
        soup,
        url=url,
        search_keyword=search_keyword,
        playlist_name=playlist_name,
        trending_category=trending_category,
    )
    logger.info("Parsed video '%s' (%s)", record.get("videoTitle"), url)
    return [record]