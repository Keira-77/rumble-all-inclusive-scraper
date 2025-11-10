thonimport csv
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger once."""
    if logging.getLogger().handlers:
        # Already configured
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def get_project_root() -> Path:
    """
    Returns the project root folder (the folder that contains `src` and `data`).

    Assumes this file is located at `<root>/src/utils/helpers.py`.
    """
    return Path(__file__).resolve().parents[2]

def fetch_url(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    proxies: Optional[Dict[str, str]] = None,
    timeout: int = 15,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> str:
    """Fetch a URL with basic retry logic and logging."""
    logger = logging.getLogger("helpers.fetch_url")

    session = requests.Session()
    final_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    if headers:
        final_headers.update(headers)

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Requesting %s (attempt %s)", url, attempt)
            response = session.get(
                url,
                headers=final_headers,
                proxies=proxies,
                timeout=timeout,
            )
            response.raise_for_status()
            logger.info("Fetched %s (%s)", url, response.status_code)
            return response.text
        except requests.RequestException as exc:
            logger.warning(
                "Attempt %s/%s failed for %s: %s",
                attempt,
                max_retries,
                url,
                exc,
            )
            if attempt == max_retries:
                logger.error("Failed to fetch %s after %s attempts", url, max_retries)
                raise
            sleep_for = backoff_factor ** (attempt - 1)
            time.sleep(sleep_for)

    # Should never reach here
    raise RuntimeError("Unexpected fetch_url failure")

def parse_number(text: Optional[str]) -> Optional[int]:
    """
    Parse numbers like:
    - '1,234'
    - '2.5K'
    - '3M views'
    Returns None if parsing fails.
    """
    if not text:
        return None

    raw = text.strip().replace(",", "").lower()
    if not raw:
        return None

    multiplier = 1
    if raw.endswith("k"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 1_000_000
        raw = raw[:-1]

    digits = []
    dot_seen = False
    for ch in raw:
        if ch.isdigit():
            digits.append(ch)
        elif ch == "." and not dot_seen:
            digits.append(ch)
            dot_seen = True
        elif ch in " ":
            continue
        else:
            # Stop when we hit something unexpected
            break

    if not digits:
        return None

    try:
        value = float("".join(digits))
        return int(value * multiplier)
    except ValueError:
        return None

def ensure_path(path: Path) -> Path:
    """Ensure parent folder exists for given file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def export_records(
    records: List[Dict[str, Any]],
    output_path: Path,
    export_format: str = "json",
) -> None:
    """
    Export scraped records to JSON, CSV, or HTML.
    """
    logger = logging.getLogger("helpers.export_records")
    export_format = export_format.lower()
    output_path = ensure_path(output_path)

    if export_format == "json":
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        logger.info("Exported %s records to JSON at %s", len(records), output_path)
    elif export_format == "csv":
        export_to_csv(records, output_path)
        logger.info("Exported %s records to CSV at %s", len(records), output_path)
    elif export_format == "html":
        export_to_html(records, output_path)
        logger.info("Exported %s records to HTML at %s", len(records), output_path)
    else:
        raise ValueError(f"Unsupported export format: {export_format}")

def export_to_csv(records: List[Dict[str, Any]], output_path: Path) -> None:
    if not records:
        output_path.write_text("", encoding="utf-8")
        return

    # Union of keys across all records
    fieldnames: List[str] = sorted(
        {key for row in records for key in row.keys()}
    )

    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)

def export_to_html(records: List[Dict[str, Any]], output_path: Path) -> None:
    if not records:
        output_path.write_text("<html><body><p>No data.</p></body></html>", encoding="utf-8")
        return

    fieldnames: List[str] = sorted(
        {key for row in records for key in row.keys()}
    )

    lines: List[str] = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'>",
        "<title>Rumble Scraper Output</title>",
        "<style>",
        "table {border-collapse: collapse; width: 100%;}",
        "th, td {border: 1px solid #ccc; padding: 4px 8px; font-size: 14px;}",
        "th {background: #f5f5f5; text-align: left;}",
        "</style>",
        "</head>",
        "<body>",
        "<table>",
        "<thead>",
        "<tr>",
    ]
    for field in fieldnames:
        lines.append(f"<th>{field}</th>")
    lines.extend(["</tr>", "</thead>", "<tbody>"])

    for row in records:
        lines.append("<tr>")
        for field in fieldnames:
            value = row.get(field, "")
            value_str = "" if value is None else str(value)
            lines.append(f"<td>{value_str}</td>")
        lines.append("</tr>")

    lines.extend(["</tbody>", "</table>", "</body>", "</html>"])
    output_path.write_text("\n".join(lines), encoding="utf-8")

def load_json(path: Path) -> Any:
    """Load JSON file and return parsed value."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def flatten(list_of_lists: Iterable[Iterable[Any]]) -> List[Any]:
    """Flatten a list of iterables into a simple list."""
    flattened: List[Any] = []
    for it in list_of_lists:
        flattened.extend(list(it))
    return flattened