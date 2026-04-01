import numpy as np
if not hasattr(np, "bool8"):
    np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
from google import genai
from datetime import datetime, timedelta

# =========================
# 1. APP CONFIG
# =========================
st.set_page_config(page_title="Nifty Sniper Elite v11.0", layout="wide")

BRIDGE_URL = st.secrets.get("MARKET_BRIDGE_URL", "http://localhost:5055")
NIFTY500_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"


def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except Exception:
        return None


client = get_ai_client()


# =========================
# 2. MARKET REGIME LOGIC
# =========================
def get_market_regime(df: pd.DataFrame):
    if df.empty:
        return "📡 OFFLINE", "Initialize Scan", "info"

    total = len(df)
    above_200 = len(df[df["MA 200"] < df["Price"]])
    panic_stocks = len(df[df["Z-Score"] < -2.2])

    breadth = (above_200 / total) * 100 if total else 0
    panic_pct = (panic_stocks / total) * 100 if total else 0

    if breadth > 60:
        return "🔥 BULL REGIME", "Focus on Momentum / Breakouts", "success"
    elif breadth < 40 and panic_pct > 15:
        return "😱 PANIC REGIME", "Focus on Mean Reversion", "error"
    elif breadth < 40:
        return "❄️ BEAR REGIME", "Capital Preservation / Defensive", "warning"
    return "⚖️ NEUTRAL", "Selective Sector Rotation", "info"


# =========================
# 3. METRIC ENGINE
# =========================
def calculate_metrics(df: pd.DataFrame, ticker: str):
    try:
        if df is None or df.empty:
            return None

        df = df.copy()
        df.columns = [str(c).capitalize() for c in df.columns]

        required = {"Close", "High", "Low", "Volume"}
        if not required.issubset(df.columns):
            return None

        close = pd.to_numeric(df["Close"], errors="coerce")
        high = pd.to_numeric(df["High"], errors="coerce")
        low = pd.to_numeric(df["Low"], errors="coerce")
        volume = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)

        clean = pd.DataFrame({
            "Close": close,
            "High": high,
            "Low": low,
            "Volume": volume
        }).dropna()

        if len(clean) < 200:
            return None

        c = clean["Close"].values
        h = clean["High"].values
        l = clean["Low"].values
        v = clean["Volume"].values

        m20 = np.mean(c[-20:])
        m50 = np.mean(c[-50:])
        m200 = np.mean(c[-200:])

        prev_close = pd.Series(c).shift(1)
        tr = pd.concat([
            pd.Series(h - l),
            (pd.Series(h) - prev_close).abs(),
            (pd.Series(l) - prev_close).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(14).mean()
        atr_last = atr.iloc[-1]
        if pd.isna(atr_last) or atr_last <= 0:
            return None

        up_move = pd.Series(h).diff()
        down_move = -pd.Series(l).diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr)

        dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
        adx = dx.rolling(14).mean().iloc[-1]

        std20 = np.std(c[-20:])
        z = 0 if std20 == 0 else (c[-1] - m20) / std20

        avg_vol20 = np.mean(v[-20:])
        vol_surge = v[-1] / avg_vol20 if avg_vol20 > 0 else 0

        p_chg = (c[-1] - c[-2]) / c[-2] if c[-2] != 0 else 0

        miro = 2
        if vol_surge > 2.0:
            miro += 5
        if p_chg > 0.01:
            miro += 3

        reco = (
            "🚀 STRONG BUY" if p_chg > 0.02 and vol_surge > 2.2
            else "🪃 REVERSION" if z < -2.2
            else "💤 NEUTRAL"
        )

        return {
            "cp": float(c[-1]),
            "m20": float(m20),
            "m50": float(m50),
            "m200": float(m200),
            "adx": round(float(adx), 1) if pd.notna(adx) else 0.0,
            "z": round(float(z), 2),
            "vol": round(float(vol_surge), 2),
            "atr": float(atr_last),
            "reco": reco,
            "miro": int(miro)
        }

    except Exception:
        return None


# =========================
# 4. DATA HELPERS
# =========================
@st.cache_data(ttl=86400)
def get_nifty500_list():
    try:
        n500 = pd.read_csv(NIFTY500_CSV_URL)
        n500["Symbol"] = n500["Symbol"].astype(str).str.upper().str.strip()
        n500["Industry"] = n500["Industry"].astype(str).fillna("Misc")
        sector_map = dict(zip(n500["Symbol"], n500["Industry"]))
        return n500["Symbol"].tolist(), sector_map
    except Exception:
        symbols = ["BIOCON", "RELIANCE", "TCS", "HDFCBANK", "ESCORTS", "360ONE"]
        sector_map = {s: "Misc" for s in symbols}
        return symbols, sector_map


def fetch_batch_history(symbols, years=2):
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=365 * years)

    payload = {
        "symbols": symbols,
        "from": from_date.isoformat(),
        "to": to_date.isoformat()
    }

    response = requests.post(
        f"{BRIDGE_URL}/batch-history",
        json=payload,
        timeout=240
    )
    response.raise_for_status()
    return response.json()


def rows_to_dataframe(rows):
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume"
    }
    df = df.rename(columns=rename_map)

    needed = ["date", "Open", "High", "Low", "Close", "Volume"]
    for col in needed:
        if col not in df.columns:
            return pd.DataFrame()

    return df[needed]


# =========================
# 5. SCANNER
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def run_master_scan(limit):
    symbols, sector_map = get_nifty500_list()
    symbols = symbols[:limit]

    results_data = []

    batch_response = fetch_batch_history(symbols, years=2)
    results = batch_response.get("results", [])

    for item in results:
        if not item.get("ok"):
            continue

        symbol = item["symbol"]
        hist_df = rows_to_dataframe(item.get("rows", []))
        metrics = calculate_metrics(hist_df, symbol)

        if metrics:
            results_data.append({
                "Ticker": symbol,
                "Sector": sector_map.get(symbol, "Misc"),
                "Price": round(metrics["cp"], 2),
                "Recommendation": metrics["reco"],
                "Miro_Score": metrics["miro"],
                "Z-Score": metrics["z"],
                "ADX Strength": metrics["adx"],
                "Vol_Surge": metrics["vol"],
                "MA 20": round(metrics["m20"], 2),
                "MA 50": round(metrics["m50"], 2),
                "MA 200": round(metrics["m200"], 2),
                "ATR": round(metrics["atr"], 2)
            })

    return pd.DataFrame(results_data)


# =========================
# 6. UI
# =========================
st.title("🎯 Nifty Sniper Elite v11.0")
st.caption("Scanner powered by NSE/BSE bridge instead of Yahoo Finance")

st.sidebar.subheader("🏦 Market Pulse")
st.sidebar.caption("Static placeholders below unless you wire a live source")
st.sidebar.table(pd.DataFrame({
    "Metric": ["Date", "India VIX", "FII Net (Cr)"],
    "Value": [datetime.now().strftime("%b %d, %Y"), "N/A", "N/A"]
}))

scan_limit = st.sidebar.slider("Stocks to scan", min_value=25, max_value=500, value=200, step=25)
risk_per_trade = st.sidebar.number_input("Risk Per Trade (INR)", value=5000, step=500)

col1, col2 = st.columns([1, 3])
with col1:
    run_scan = st.button("🚀 EXECUTE GLOBAL SCAN", use_container_width=True)
with col2:
    st.write("")

if run_scan:
    progress_text = st.empty()
    progress_bar = st.progress(0)

    try:
        progress_text.info("Fetching market history from local bridge...")
        progress_bar.progress(25)

        result_df = run_master_scan(scan_limit)

        progress_bar.progress(100)
        progress_text.success(f"Scan completed. Stocks processed: {len(result_df)}")
        st.session_state["v11_res"] = result_df

    except Exception as e:
        progress_text.error(f"Scan failed: {e}")
        st.session_state["v11_res"] = pd.DataFrame()

if "v11_res" in st.session_state:
    df = st.session_state["v11_res"]

    if df.empty:
        st.warning("No results returned from the bridge. Check the Node service and symbol history methods.")
    else:
        regime, advice, color = get_market_regime(df)
        st.sidebar.markdown(f"### 🌡️ Market Weather: {regime}")
        getattr(st.sidebar, color)(f"Strategy: {advice}")

        # simple risk model
        assumed_vix = 20.0
        sl_mult = 3.0 if assumed_vix > 20 else 2.0

        df = df.copy()
        df["Stop_Loss"] = df["Price"] - (sl_mult * df["ATR"])
        risk_per_share = (df["Price"] - df["Stop_Loss"]).replace([np.inf, -np.inf], np.nan)
        df["Qty"] = (risk_per_trade / risk_per_share).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

        st.metric("Scanned Universe", len(df))

        tabs = st.tabs([
            "🎯 Miro Flow",
            "📈 Trend & ADX",
            "🪃 Reversion",
            "🧠 Intelligence Lab",
            "🛡️ Risk Lab"
        ])

        with tabs[0]:
            st.subheader("Miro Flow (Momentum Leaderboard)")
            out = df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge", "Sector"]]
            out = out.sort_values(["Miro_Score", "Vol_Surge"], ascending=[False, False])
            st.dataframe(out, hide_index=True, use_container_width=True)

        with tabs[1]:
            st.subheader("Structural Trend Analysis")
            out = df[["Ticker", "Price", "Recommendation", "ADX Strength", "MA 20", "MA 50", "MA 200", "Sector"]]
            out = out.sort_values("ADX Strength", ascending=False)
            st.dataframe(out, hide_index=True, use_container_width=True)

        with tabs[2]:
            st.subheader("Statistical Mean Reversion (Z-Score)")
            out = df[["Ticker", "Price", "Recommendation", "Z-Score", "Sector"]]
            out = out.sort_values("Z-Score", ascending=True)
            st.dataframe(out, hide_index=True, use_container_width=True)

        with tabs[3]:
            st.subheader("🧠 Tactical Debate")
            if client is None:
                st.info("Add GEMINI_API_KEY to Streamlit secrets to enable AI analysis.")
            else:
                t_i = st.selectbox("Select Asset", df["Ticker"].tolist(), key="i_box")
                if st.button("⚖️ Summon Council"):
                    price = df[df["Ticker"] == t_i]["Price"].values[0]
                    prompt = f"""
                    Analyze {t_i} for an Indian equities swing-trading scanner.

                    Current scanned price: {price}

                    Debate in 4 voices:
                    1. BULL - why this looks attractive
                    2. BEAR - why this may fail
                    3. TECHNICAL - chart/indicator interpretation
                    4. RISK - position sizing, stop loss, and trade management

                    End with:
                    - Verdict
                    - Best setup type
                    - 3 key risks
                    """
                    with st.spinner("Council debating..."):
                        try:
                            response = client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=prompt
                            )
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"AI analysis failed: {e}")

        with tabs[4]:
            st.subheader("Execution Management")
            out = df[["Ticker", "Price", "Stop_Loss", "Qty", "ATR", "Sector"]]
            out = out.sort_values("Qty", ascending=False)
            st.dataframe(out, hide_index=True, use_container_width=True)

else:
    st.info("Scanner Ready. Start the local Node bridge, then click EXECUTE GLOBAL SCAN.")
