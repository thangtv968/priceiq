"""PriceIQ CLI — one scan: scrape competitors → match catalog → analyze → report/alert.

    python run.py                 # scan using config.json
    python run.py --no-telegram   # skip alerts
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from priceiq import analyze, matching, sources, storage  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def notify_telegram(config: dict, text: str) -> bool:
    tg = config.get("telegram") or {}
    token, chat = tg.get("bot_token"), tg.get("chat_id")
    if not (token and chat):
        return False
    import requests
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[:4000]}, timeout=20).raise_for_status()
        return True
    except Exception as err:
        print(f"[telegram] failed: {err}", file=sys.stderr)
        return False


def run_scan(config: dict) -> list:
    all_listings: list = []
    for comp in config.get("competitors", []):
        try:
            got = sources.scrape_competitor(comp)
            print(f"✓ {comp['name']}: {len(got)} listing")
            all_listings.extend(got)
        except Exception as err:
            print(f"✗ {comp.get('name', '?')}: {err}", file=sys.stderr)

    my = config.get("my_catalog", [])
    match_map = matching.match_catalog(
        my, all_listings,
        model_name=config.get("embedding_model", matching.DEFAULT_MODEL),
        threshold=config.get("match_threshold", 0.55),
    )
    reports = analyze.analyze(my, match_map)

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [[ts, r.sku, comp, name, price]
            for r in reports for comp, name, price, _score in r.matches]
    storage.append_history(rows)
    storage.save_snapshot({"ts": ts, "reports": [r.__dict__ for r in reports]})
    return reports


def main() -> None:
    ap = argparse.ArgumentParser(description="PriceIQ — competitor price scan.")
    ap.add_argument("-c", "--config", default="config.json")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        print(f"Config not found: {args.config} (copy config.example.json -> config.json).", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    reports = run_scan(config)
    print("\n" + analyze.format_report(reports))

    alerts = [r for r in reports if r.map_violation]
    if alerts and not args.no_telegram:
        msg = "🚨 PriceIQ — cảnh báo phá giá sàn (MAP):\n" + "\n".join(
            f"- {r.name}: " + "; ".join(f"{c} bán {pr}" for c, n, pr in r.map_details)
            for r in alerts)
        if notify_telegram(config, msg):
            print("[telegram] alert sent")


if __name__ == "__main__":
    main()
