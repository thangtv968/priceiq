"""PriceIQ — competitor price intelligence dashboard.

    streamlit run app.py

Reads the latest scan snapshot + price history written by run.py and turns it
into a decision surface: pricing position, MAP-violation alerts, and a
run-a-fresh-scan button. The scan itself is delegated to run.py in a
subprocess so the (Playwright) scraper runs in a clean process.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import altair as alt
import pandas as pd
import streamlit as st

from priceiq import storage

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_HERE, "config.json")
EXAMPLE_CONFIG = os.path.join(_HERE, "config.example.json")

st.set_page_config(page_title="PriceIQ — Price Intelligence", page_icon="💹", layout="wide")

# --- light styling: tighten metric cards + badge colors -------------------
st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1200px;}
      div[data-testid="stMetric"] {
          background: #f8f9fe; border: 1px solid #e8eafc;
          border-radius: 12px; padding: 14px 18px;
      }
      .pill {display:inline-block; padding:2px 12px; border-radius:999px;
             font-size:0.80rem; font-weight:600;}
      .pill-cheap {background:#e7f7ee; color:#0a7d43;}
      .pill-mid   {background:#eef1fb; color:#3b46b3;}
      .pill-exp   {background:#fdeceb; color:#c0392b;}
      .pill-none  {background:#f0f0f2; color:#6b7280;}
      .muted {color:#6b7280; font-size:0.86rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

_POSITION_PILL = {
    "cheapest": ("pill-cheap", "RẺ NHẤT"),
    "mid": ("pill-mid", "TẦM GIỮA"),
    "expensive": ("pill-exp", "ĐANG ĐẮT"),
    "no-data": ("pill-none", "CHƯA KHỚP"),
}


def load_config() -> dict:
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_CONFIG
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=3)
def load_snapshot() -> dict:
    return storage.load_snapshot()


@st.cache_data(ttl=3)
def history_df() -> pd.DataFrame:
    hist = storage.load_history()
    if not hist:
        return pd.DataFrame()
    df = pd.DataFrame(hist)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    return df.dropna(subset=["timestamp", "price"])


def run_scan_subprocess(with_telegram: bool) -> tuple[int, str]:
    """Run one scan via run.py in a clean subprocess; return (code, tail-of-output)."""
    cmd = [sys.executable, os.path.join(_HERE, "run.py")]
    if not with_telegram:
        cmd.append("--no-telegram")
    proc = subprocess.run(cmd, cwd=_HERE, capture_output=True, text=True, encoding="utf-8")
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out[-3000:]


def pill(position: str) -> str:
    cls, label = _POSITION_PILL.get(position, _POSITION_PILL["no-data"])
    return f'<span class="pill {cls}">{label}</span>'


# ==========================================================================
config = load_config()
snap = load_snapshot()
reports = snap.get("reports", [])
scanned_at = snap.get("ts", "—")

# --- sidebar --------------------------------------------------------------
with st.sidebar:
    st.markdown("### 💹 PriceIQ")
    st.caption("AI competitor price intelligence")
    st.divider()

    telegram_on = bool((config.get("telegram") or {}).get("bot_token"))
    st.write("**Chạy quét mới**")
    send_alert = st.toggle("Gửi cảnh báo Telegram", value=telegram_on, disabled=not telegram_on,
                           help="Bật/tắt gửi alert khi phát hiện phá giá sàn.")
    if st.button("▶️  Quét đối thủ ngay", type="primary", width="stretch"):
        with st.spinner("Đang scrape + AI khớp sản phẩm… (Playwright + embeddings)"):
            code, tail = run_scan_subprocess(with_telegram=send_alert)
        if code == 0:
            st.success("Quét xong!")
            st.cache_data.clear()
        else:
            st.error(f"Quét lỗi (exit {code}).")
        with st.expander("Log lần quét"):
            st.code(tail or "(no output)")
        st.rerun()

    st.divider()
    st.write("**Cấu hình**")
    st.markdown(
        f"- Model khớp: `{config.get('embedding_model', 'all-MiniLM-L6-v2')}`\n"
        f"- Ngưỡng khớp: `{config.get('match_threshold', 0.5)}`\n"
        f"- Nguồn đối thủ: **{len(config.get('competitors', []))}**\n"
        f"- Telegram: {'✅ bật' if telegram_on else '⚪ tắt'}"
    )
    with st.expander("Nguồn đang theo dõi"):
        for c in config.get("competitors", []):
            st.markdown(f"- **{c['name']}** · `{c['type']}`")

# --- header ---------------------------------------------------------------
st.title("💹 PriceIQ — Competitor Price Intelligence")
_store = config.get("store_name", "")
st.caption((f"🏪 **{_store}** · " if _store else "")
           + "Scrape giá đối thủ → AI khớp sản phẩm khác tên/SKU → phát hiện phá giá sàn (MAP) & đề xuất chỉnh giá.")

if not reports:
    st.info("Chưa có dữ liệu quét. Bấm **▶️ Quét đối thủ ngay** ở thanh bên để chạy lần đầu.")
    st.stop()

# --- KPI row --------------------------------------------------------------
n_products = len(reports)
n_matched = sum(1 for r in reports if r.get("matches"))
n_listings = sum(len(r.get("matches", [])) for r in reports)
n_alerts = sum(1 for r in reports if r.get("map_violation"))

k1, k2, k3, k4 = st.columns(4)
k1.metric("Sản phẩm theo dõi", n_products)
k2.metric("Khớp được đối thủ", f"{n_matched}/{n_products}")
k3.metric("Listing đối thủ khớp", n_listings)
k4.metric("🚨 Cảnh báo phá giá", n_alerts, delta=None,
          delta_color="inverse")
st.caption(f"Lần quét gần nhất: `{scanned_at}` · Nguồn: {len(config.get('competitors', []))} site")

# --- MAP alert banner -----------------------------------------------------
alert_reports = [r for r in reports if r.get("map_violation")]
if alert_reports:
    lines = []
    for r in alert_reports:
        who = "; ".join(f"**{c}** bán {pr} {r.get('currency','')}" for c, n, pr in r.get("map_details", []))
        lines.append(f"- **{r['name']}** (sàn MAP {r.get('map_price')}): {who}")
    st.error("### 🚨 Phá giá sàn (MAP) đang diễn ra\n" + "\n".join(lines))

st.divider()

tab_overview, tab_compare, tab_history, tab_matches = st.tabs(
    ["📊 Tổng quan", "📈 So sánh giá", "🕒 Lịch sử", "🔎 Chi tiết khớp"]
)

# --- tab: overview --------------------------------------------------------
with tab_overview:
    for r in reports:
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(f"#### {r['name']}  {pill(r.get('position','no-data'))}", unsafe_allow_html=True)
            cur = r.get("currency", "")
            bits = [f"Giá của bạn: **{r['my_price']} {cur}**"]
            if r.get("cheapest") is not None:
                bits.append(f"Rẻ nhất đối thủ: **{r['cheapest']} {cur}**")
            if r.get("median_price") is not None:
                bits.append(f"Trung vị: **{r['median_price']:.2f} {cur}**")
            st.markdown(" · ".join(bits))
            st.markdown(f"<span class='muted'>💡 {r.get('suggestion','')}</span>", unsafe_allow_html=True)
        with c2:
            if r.get("map_violation"):
                st.error(f"🚨 Phá giá sàn (MAP {r.get('map_price')})")
            elif r.get("position") == "cheapest":
                st.success("Bạn đang rẻ nhất thị trường")
            elif r.get("position") == "expensive":
                st.warning("Bạn đang đắt hơn trung vị")
            elif r.get("position") == "no-data":
                st.info("Chưa khớp — cân nhắc chỉnh tên/nguồn")
            else:
                st.info("Vị thế giá ổn")
        st.divider()

# --- tab: price comparison ------------------------------------------------
with tab_compare:
    rows = []
    for r in reports:
        cur = r.get("currency", "")
        label = f"{r['name']} ({cur})"
        rows.append({"product": label, "who": "Bạn", "price": r["my_price"], "kind": "you"})
        for comp, name, price, score in r.get("matches", []):
            if price is not None:
                rows.append({"product": label, "who": comp, "price": price, "kind": "competitor"})
    if not rows:
        st.info("Chưa có giá để so sánh.")
    else:
        cdf = pd.DataFrame(rows)
        for label in cdf["product"].unique():
            sub = cdf[cdf["product"] == label]
            st.markdown(f"**{label}**")
            chart = (
                alt.Chart(sub)
                .mark_bar()
                .encode(
                    x=alt.X("price:Q", title="Giá", scale=alt.Scale(zero=True)),
                    y=alt.Y("who:N", title=None, sort="-x"),
                    color=alt.Color("kind:N",
                                    scale=alt.Scale(domain=["you", "competitor"],
                                                    range=["#4f46e5", "#c7ccf5"]),
                                    legend=None),
                    tooltip=["who", "price"],
                )
                .properties(height=28 * len(sub) + 20)
            )
            st.altair_chart(chart, width="stretch")
            st.divider()

# --- tab: history ---------------------------------------------------------
with tab_history:
    hdf = history_df()
    if hdf.empty or hdf["timestamp"].nunique() < 2:
        st.info("Cần ≥2 lần quét để vẽ xu hướng giá theo thời gian. "
                "Bấm **▶️ Quét đối thủ ngay** vài lần để tích lũy lịch sử.")
        if not hdf.empty:
            st.dataframe(hdf.sort_values("timestamp", ascending=False), width="stretch", hide_index=True)
    else:
        listings = sorted(hdf["listing"].unique())
        pick = st.multiselect("Chọn listing để xem xu hướng", listings, default=listings[:5])
        sub = hdf[hdf["listing"].isin(pick)]
        line = (
            alt.Chart(sub)
            .mark_line(point=True)
            .encode(
                x=alt.X("timestamp:T", title="Thời gian"),
                y=alt.Y("price:Q", title="Giá", scale=alt.Scale(zero=False)),
                color=alt.Color("listing:N", title="Listing"),
                tooltip=["timestamp", "competitor", "listing", "price"],
            )
            .properties(height=380)
        )
        st.altair_chart(line, width="stretch")

# --- tab: match detail ----------------------------------------------------
with tab_matches:
    st.caption("AI khớp sản phẩm của bạn với listing đối thủ theo *ngữ nghĩa* (điểm cosine 0–1).")
    for r in reports:
        with st.expander(f"{r['name']} — {len(r.get('matches', []))} listing khớp"):
            if not r.get("matches"):
                st.write("Chưa khớp listing nào.")
                continue
            mdf = pd.DataFrame(
                [{"Đối thủ": c, "Listing": n, "Giá": pr, "Độ khớp": sc}
                 for c, n, pr, sc in r["matches"]]
            )
            st.dataframe(
                mdf, width="stretch", hide_index=True,
                column_config={
                    "Độ khớp": st.column_config.ProgressColumn(
                        "Độ khớp (AI)", min_value=0.0, max_value=1.0, format="%.2f"),
                    "Giá": st.column_config.NumberColumn(format="%.2f"),
                },
            )
