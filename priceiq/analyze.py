"""Analysis + report: turn matches into a pricing position, a suggestion,
and a MAP-violation flag (a reseller selling below the brand's floor price).
Rule-based (no LLM) — deterministic and explainable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Optional


@dataclass
class ProductReport:
    sku: str
    name: str
    my_price: float
    currency: str
    matches: list = field(default_factory=list)   # (competitor, name, price, score)
    cheapest: Optional[float] = None
    median_price: Optional[float] = None
    position: str = "no-data"                      # cheapest | mid | expensive | no-data
    suggestion: str = ""
    map_price: Optional[float] = None
    map_violation: bool = False
    map_details: list = field(default_factory=list)  # (competitor, name, price)


def analyze(my_products: list, match_map: dict) -> list:
    reports: list = []
    for p in my_products:
        matches = match_map.get(p["sku"], [])
        cur = p.get("currency", "")
        my = float(p["my_price"])
        map_price = p.get("map_price")

        priced = [m for m in matches if m.listing.price is not None]
        comp_prices = [m.listing.price for m in priced]
        map_hits = ([m for m in priced if m.listing.price < map_price]
                    if map_price is not None else [])

        rep = ProductReport(
            sku=p["sku"], name=p["name"], my_price=my, currency=cur, map_price=map_price,
            matches=[(m.listing.competitor, m.listing.name, m.listing.price, round(m.score, 2))
                     for m in matches],
            map_violation=bool(map_hits),
            map_details=[(m.listing.competitor, m.listing.name, m.listing.price) for m in map_hits],
        )

        if not comp_prices:
            rep.position = "no-data"
            rep.suggestion = "Chưa khớp được trên nguồn nào — mở rộng nguồn hoặc chỉnh tên trong catalog."
            reports.append(rep)
            continue

        rep.cheapest = min(comp_prices)
        rep.median_price = median(comp_prices)
        if my <= rep.cheapest:
            rep.position = "cheapest"
            rep.suggestion = (f"Đang RẺ NHẤT ({my} ≤ {rep.cheapest}). "
                              f"Có thể nâng nhẹ về ~{rep.median_price:.2f} để tăng biên.")
        elif my <= rep.median_price:
            rep.position = "mid"
            rep.suggestion = f"Ở khoảng giữa (dưới trung vị {rep.median_price:.2f}) — vị thế ổn."
        else:
            rep.position = "expensive"
            rep.suggestion = (f"Đang ĐẮT ({my} > trung vị {rep.median_price:.2f}). "
                              f"Cân nhắc giảm về ~{rep.cheapest:.2f}–{rep.median_price:.2f}.")
        reports.append(rep)
    return reports


def format_report(reports: list) -> str:
    """Plain-text report (for CLI / Telegram)."""
    lines = ["=== PriceIQ — Báo cáo vị thế giá ===\n"]
    alerts = 0
    for r in reports:
        lines.append(f"• {r.name}  (giá của bạn: {r.my_price} {r.currency})")
        if r.position == "no-data":
            lines.append(f"    ⚠️ {r.suggestion}")
        else:
            lines.append(f"    Vị thế: {r.position} | rẻ nhất đối thủ: {r.cheapest} | trung vị: {r.median_price:.2f}")
            lines.append(f"    → {r.suggestion}")
            lines.append(f"    Khớp {len(r.matches)} listing: " +
                         ", ".join(f"{c}:{pr}({sc})" for c, n, pr, sc in r.matches[:4]))
        if r.map_violation:
            alerts += 1
            hits = "; ".join(f"{c} bán {pr}" for c, n, pr in r.map_details)
            lines.append(f"    🚨 PHÁ GIÁ SÀN (MAP {r.map_price}): {hits}")
        lines.append("")
    lines.append(f"Tổng: {len(reports)} sản phẩm, {alerts} cảnh báo phá giá sàn.")
    return "\n".join(lines)
