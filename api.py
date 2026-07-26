"""PriceIQ REST API (FastAPI).

    uvicorn api:app --host 0.0.0.0 --port 8000

Endpoints
  GET  /health   liveness probe
  GET  /report   latest persisted scan (snapshot on disk) — fast
  GET  /alerts   only products currently violating MAP (below floor price)
  POST /scan     run a fresh scan now (scrape → AI match → analyze), persist + return

The heavy /scan path reuses run.py's pipeline so the API and CLI never drift.
"""
from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException

import run as engine
from priceiq import storage

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_HERE, "config.json")
EXAMPLE_CONFIG = os.path.join(_HERE, "config.example.json")

app = FastAPI(
    title="PriceIQ API",
    version="0.1.0",
    description="Competitor price intelligence — scrape → AI product match → pricing analysis.",
)


def _config() -> dict:
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_CONFIG
    return engine.load_config(path)


def _summary(reports: list[dict]) -> dict:
    return {
        "products": len(reports),
        "matched": sum(1 for r in reports if r.get("matches")),
        "listings_matched": sum(len(r.get("matches", [])) for r in reports),
        "map_alerts": sum(1 for r in reports if r.get("map_violation")),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "priceiq", "version": app.version}


@app.get("/report")
def report() -> dict:
    """Return the latest persisted scan without re-scraping (fast)."""
    snap = storage.load_snapshot()
    if not snap:
        raise HTTPException(404, "No scan yet — call POST /scan first.")
    reports = snap.get("reports", [])
    return {"scanned_at": snap.get("ts"), "summary": _summary(reports), "reports": reports}


@app.get("/alerts")
def alerts() -> dict:
    """Return only products whose competitors are selling below the MAP floor."""
    snap = storage.load_snapshot()
    if not snap:
        raise HTTPException(404, "No scan yet — call POST /scan first.")
    violating = [r for r in snap.get("reports", []) if r.get("map_violation")]
    return {"scanned_at": snap.get("ts"), "count": len(violating), "alerts": violating}


@app.post("/scan")
def scan() -> dict:
    """Run a full scan now. Slow (live scrape + embeddings); persists results."""
    try:
        reports = engine.run_scan(_config())
    except Exception as err:  # surface scrape/model failures as 502
        raise HTTPException(502, f"scan failed: {err}") from err
    payload = [asdict(r) for r in reports]
    return {"summary": _summary(payload), "reports": payload}
