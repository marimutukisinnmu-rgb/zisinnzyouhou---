#!/usr/bin/env python3
"""JMA earthquake monitor -> data.json -> git commit/push."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# JMA high-frequency earthquake/volcano Atom feed.
FEED_URL = "https://www.data.jma.go.jp/developer/xml/feed/eqvol.xml"
POLL_SECONDS = 61
HISTORY_LIMIT = 30
ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data.json"


def text(node: ET.Element | None, default: str = "") -> str:
    return (node.text or "").strip() if node is not None else default


def find_text(root: ET.Element, paths: list[str]) -> str:
    for path in paths:
        node = root.find(path)
        value = text(node)
        if value:
            return value
    return ""


def fetch(url: str) -> bytes:
    """Fetch bytes with retries so a transient connection failure does not kill monitoring."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "zisinnzyouhou---/1.0",
                    "Accept": "application/xml,text/xml,*/*;q=0.1",
                    "Connection": "close",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {last_error}")


def get_feed_links() -> list[str]:
    """Return earthquake product URLs from Atom <link href="..."> elements."""
    root = ET.fromstring(fetch(FEED_URL))
    links: list[str] = []

    for entry in root.findall(".//{*}entry"):
        title = text(entry.find("{*}title"))
        if title != "震源・震度に関する情報":
            continue

        # Use the Atom link href as the product URL.
        for link in entry.findall("{*}link"):
            if link.attrib.get("type") == "application/xml":
                href = link.attrib.get("href", "").strip()
                if href:
                    links.append(href)
                    break

    return links


def parse_report(xml_bytes: bytes) -> dict | None:
    root = ET.fromstring(xml_bytes)

    info_type = find_text(root, [".//{*}Head/{*}InfoType"])
    if info_type and "地震" not in info_type:
        return None

    report_id = find_text(root, [
        ".//{*}Head/{*}EventID",
        ".//{*}Head/{*}Serial",
    ])
    origin_time = find_text(root, [
        ".//{*}Body/{*}Earthquake/{*}OriginTime",
    ])
    region = find_text(root, [
        ".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}Name",
        ".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}NameFromReference",
    ])
    magnitude = find_text(root, [
        ".//{*}Body/{*}Earthquake/{*}Magnitude",
    ])

    depth = ""
    coord = root.find(".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}Coordinate")
    if coord is None:
        coord = root.find(".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}{*}Coordinate")
    if coord is not None:
        raw = text(coord)
        # Typical JMA format: +36.1+140.1-50000/
        for part in raw.split("/"):
            part = part.strip()
            if not part:
                continue
            last_number = ""
            current = ""
            for ch in part:
                if ch.isdigit() or (ch == "-" and not current):
                    current += ch
                else:
                    if current.lstrip("-").isdigit():
                        last_number = current
                    current = ""
            if current.lstrip("-").isdigit():
                last_number = current
            if last_number and last_number.lstrip("-").isdigit():
                meters = abs(int(last_number))
                if meters >= 100:
                    depth = f"{meters // 1000} km"
                    break

    max_intensity = find_text(root, [
        ".//{*}Body/{*}Intensity/{*}Observation/{*}MaxInt",
        ".//{*}Body/{*}Intensity/{*}Observation/{*}MaxInt/{*}MaxInt",
    ])

    tsunami = find_text(root, [
        ".//{*}Body/{*}Comments/{*}ForecastComment/{*}Text",
        ".//{*}Body/{*}Comments/{*}WarningComment/{*}Text",
    ])
    if "津波" not in tsunami:
        tsunami = "情報確認中"

    if not report_id and not origin_time:
        return None

    return {
        "id": report_id or origin_time,
        "time": origin_time,
        "region": region or "未確認",
        "max_intensity": max_intensity or "未確認",
        "magnitude": magnitude or "未確認",
        "depth": depth or "未確認",
        "tsunami": tsunami,
    }


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"updated_at": None, "earthquakes": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"updated_at": None, "earthquakes": []}


def save_data(data: dict) -> None:
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )


def publish() -> None:
    add = git("add", "data.json")
    if add.returncode != 0:
        raise RuntimeError(add.stderr.strip() or "git add failed")

    commit = git("commit", "-m", "Update earthquake information")
    if commit.returncode != 0:
        if "nothing to commit" in (commit.stdout + commit.stderr).lower():
            return
        raise RuntimeError(commit.stderr.strip() or "git commit failed")

    push = git("push", "origin", "main")
    if push.returncode != 0:
        raise RuntimeError(push.stderr.strip() or "git push failed")


def main() -> None:
    print("JMA earthquake monitor started.")
    print(f"Feed: {FEED_URL}")
    print(f"Polling: every {POLL_SECONDS}s")

    while True:
        try:
            links = get_feed_links()
            current = load_data()
            known = {item.get("id") for item in current.get("earthquakes", [])}
            new_items: list[dict] = []

            for link in links:
                try:
                    item = parse_report(fetch(link))
                except Exception as exc:
                    print(f"parse failed: {exc}")
                    continue
                if item and item["id"] not in known:
                    new_items.append(item)
                    known.add(item["id"])

            if new_items:
                earthquakes = new_items + current.get("earthquakes", [])
                current["earthquakes"] = earthquakes[:HISTORY_LIMIT]
                current["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                save_data(current)
                print(f"New earthquake reports: {len(new_items)}")
                publish()
                print("Committed and pushed.")

        except Exception as exc:
            # Keep monitoring after transient network/Git errors.
            print(f"monitor error: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
