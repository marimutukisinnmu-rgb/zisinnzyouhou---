#!/usr/bin/env python3
"""JMA earthquake monitor -> data.json -> git commit/push.

Run this script continuously on the machine that should publish updates.
Git credentials/remotes are intentionally handled by Git itself; no token is stored here.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

FEED_URL = "https://www.data.jma.go.jp/developer/xml/feed/eqvol_l.xml"
POLL_SECONDS = 10
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
    req = urllib.request.Request(url, headers={"User-Agent": "zisinnzyouhou---/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


def get_feed_links() -> list[str]:
    root = ET.fromstring(fetch(FEED_URL))
    links: list[str] = []
    for entry in root.findall(".//{*}entry"):
        title = text(entry.find("{*}title"))
        link = entry.find("{*}link")
        href = link.attrib.get("href", "") if link is not None else ""
        # VXSE53 = earthquake hypocenter/intensity information.
        if "震源・震度" in title and href:
            links.append(href)
    return links


def parse_report(xml_bytes: bytes) -> dict | None:
    root = ET.fromstring(xml_bytes)

    # Reject non-earthquake reports if the feed ever returns an unexpected item.
    info_type = find_text(root, [".//{*}Head/{*}InfoType"])
    if info_type and "地震" not in info_type:
        return None

    report_id = find_text(root, [".//{*}Head/{*}EventID", ".//{*}Head/{*}Serial"])
    origin_time = find_text(root, [
        ".//{*}Body/{*}Earthquake/{*}OriginTime",
        ".//{*}Body/{*}Earthquake/{*}OriginTime",
    ])
    region = find_text(root, [
        ".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}Name",
        ".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}NameFromReference",
    ])
    magnitude = find_text(root, [
        ".//{*}Body/{*}Earthquake/{*}Magnitude",
    ])

    # JMA coordinates are typically text such as +36.1+140.1-50000/
    depth = ""
    coord = root.find(".//{*}Body/{*}Earthquake/{*}Hypocenter/{*}Area/{*}Coordinate")
    if coord is not None:
        raw = text(coord)
        parts = raw.split("/")
        if parts:
            last = parts[-1]
            if last.endswith("/"):
                last = last[:-1]
            # Find the depth-like negative number after longitude.
            nums = last.replace("+", " ").replace("-", " -").split()
            for item in reversed(nums):
                if item.lstrip("-").isdigit() and abs(int(item)) >= 100:
                    meters = abs(int(item))
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
        # Nothing to commit is harmless.
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

            # Newest feed entries are normally first. Parse only unseen reports.
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
