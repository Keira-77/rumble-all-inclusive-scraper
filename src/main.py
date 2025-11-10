thonimport argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from utils.helpers import (
    configure_logging,
    export_records,
    flatten,
    get_project_root,
    load_json,
)

# Ensure local `src` modules (extractors, utils) are importable when running as a script.
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from extractors.video_parser import extract_video
from extractors.channel_parser import extract_channel
from extractors.playlist_parser import extract_playlist
from extractors.search_parser import extract_search

def load_config(root: Path, config_arg: str = None) -> Dict[str, Any]:
    """
    Load configuration JSON.

    If `config_arg` is supplied, that path is used (relative to root if not absolute).
    Otherwise we fall back to `src/config/settings.example.json` if present.
    """
    logger = logging.getLogger("main.load_config")
    config_path: Path

    if config_arg:
        config_path = Path(config_arg)
        if not config_path.is_absolute():
            config_path = root / config_arg
    else:
        config_path = root / "src" / "config" / "settings.example.json"

    if not config_path.exists():
        logger.warning(
            "Config file %s not found; using built-in defaults.", config_path
        )
        # Minimal defaults
        return {
            "http": {"timeout": 15, "max_retries": 3},
            "scraper": {
                "max_videos_per_channel": 50,
                "max_videos_per_playlist": 100,
                "max_results_per_search": 50,
            },
            "output": {"format": "json", "path": "data/sample_output.json"},
        }

    logger.info("Loading config from %s", config_path)
    return load_json(config_path)

def resolve_path(root: Path, path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = root / path_str
    return path

def run() -> None:
    configure_logging()
    logger = logging.getLogger("main")

    parser = argparse.ArgumentParser(
        description="Rumble All-Inclusive Scraper - videos, channels, playlists and search."
    )
    parser.add_argument(
        "--inputs",
        type=str,
        help="Path to input JSON describing URLs to scrape.",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration JSON (defaults to src/config/settings.example.json).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (overrides config).",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv", "html"],
        help="Export format (overrides config).",
    )

    args = parser.parse_args()
    root = get_project_root()

    config = load_config(root, args.config)
    output_cfg = config.get("output", {})

    # Resolve inputs
    if args.inputs:
        inputs_path = resolve_path(root, args.inputs)
    else:
        inputs_path = root / "data" / "inputs.sample.json"

    if not inputs_path.exists():
        raise FileNotFoundError(
            f"Input file {inputs_path} does not exist. "
            "Provide one via --inputs or create data/inputs.sample.json."
        )

    logger.info("Loading inputs from %s", inputs_path)
    inputs_data = load_json(inputs_path)
    if not isinstance(inputs_data, list):
        raise ValueError("Input JSON must be a list of objects.")

    # Resolve output
    if args.output:
        output_path = resolve_path(root, args.output)
    else:
        output_path = resolve_path(
            root, output_cfg.get("path", "data/sample_output.json")
        )

    export_format = (args.format or output_cfg.get("format") or "json").lower()

    all_batches: List[List[Dict[str, Any]]] = []

    for item in inputs_data:
        if not isinstance(item, dict):
            logger.warning("Skipping non-object item in input: %r", item)
            continue

        url = item.get("url")
        scrape_type = (item.get("type") or "").lower()
        search_keyword = item.get("searchKeyword")
        playlist_name = item.get("playlistName")
        trending_category = item.get("trendingCategory")

        if not url or not scrape_type:
            logger.warning("Skipping item missing url/type: %r", item)
            continue

        logger.info("Processing %s: %s", scrape_type, url)

        try:
            if scrape_type == "video":
                batch = extract_video(
                    url=url,
                    config=config,
                    search_keyword=search_keyword,
                    playlist_name=playlist_name,
                    trending_category=trending_category,
                )
            elif scrape_type == "channel":
                max_videos = int(
                    config.get("scraper", {}).get("max_videos_per_channel", 50)
                )
                batch = extract_channel(
                    url=url,
                    config=config,
                    max_videos=max_videos,
                )
            elif scrape_type == "playlist":
                max_videos = int(
                    config.get("scraper", {}).get("max_videos_per_playlist", 100)
                )
                batch = extract_playlist(
                    url=url,
                    config=config,
                    max_videos=max_videos,
                )
                # Tag playlistName if provided manually
                if playlist_name:
                    for rec in batch:
                        rec["playlistName"] = rec.get("playlistName") or playlist_name
            elif scrape_type in ("search", "trending"):
                max_results = int(
                    config.get("scraper", {}).get("max_results_per_search", 50)
                )
                batch = extract_search(
                    url=url,
                    config=config,
                    search_keyword=search_keyword,
                    max_results=max_results,
                )
                if scrape_type == "trending":
                    for rec in batch:
                        rec["trendingCategory"] = (
                            rec.get("trendingCategory") or trending_category or "Trending"
                        )
            else:
                logger.warning("Unknown type '%s' in item %r; skipping.", scrape_type, item)
                continue

            all_batches.append(batch)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process %s (%s): %s", scrape_type, url, exc)

    all_records = flatten(all_batches)
    logger.info("Collected %s total records.", len(all_records))

    export_records(all_records, output_path=output_path, export_format=export_format)
    logger.info("Done. Output written to %s", output_path)

if __name__ == "__main__":
    run()