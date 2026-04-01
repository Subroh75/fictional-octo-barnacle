import numpy as np
if not hasattr(np, "bool8"):
    np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime, timedelta
from anthropic import Anthropic

# =========================
# 1. APP CONFIG
# =========================
st.set_page_config(
    page_title="Nifty Sniper Elite v12.0",
    layout="wide",
    initial_sidebar_state="expanded"
)

NIFTY500_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

def get_anthropic_client():
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return Anthropic(api_key=key)
    except Exception:
        pass
    return None

# =========================
# 2. YAHOO FINANCE — DIRECT HTTP (no npm, no bridge)
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_candles_yf(ticker_ns: str) -> pd.DataFrame:
    """Fetch 2y daily OHLCV from Yahoo Finance v8 API directly."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_ns}?interval=1d&range=2y"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NiftySniper/1.0)"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data.get("chart", {}).get("result", [{}])[0]
        timestamps = result.get("timestamp", [])
        q = result.get("indicators", {}).get("quote", [{}])[0]
        if not timestamps:
            return pd.DataFrame()
        df = pd.DataFrame({
            "date":   pd.to_datetime(timestamps, unit="s"),
            "Open":   q.get("open", []),
            "High":   q.get("high", []),
            "Low":    q.get("low", []),
            "Close":  q.get("close", []),
            "Volume": q.get("volume", []),
        }).dropna(subset=["Close"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_pulse() -> dict:
    """Fetch NIFTY50, Bank Nifty, VIX, USD/INR from Yahoo Finance."""
    symbols = {"^NSEI": "nifty50", "^NSEBANK": "banknifty", "^INDIAVIX": "vix", "USDINR=X": "usdinr"}
    result = {}
    for sym, key in symbols.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            result[key] = round(closes[-1], 2) if closes else 0
            result[f"{key}_prev"] = round(closes[-2], 2) if len(closes) >= 2 else 0
        except Exception:
            result[key] = 0
            result[f"{key}_prev"] = 0
    return result

# =========================
# 3. NIFTY 500 SYMBOLS
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
        fallback = ["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","BHARTIARTL",
                    "SBIN","KOTAKBANK","HINDUNILVR","AXISBANK","LT","MARUTI"]
        return fallback, {s: "Misc" for s in fallback}

# =========================
# 4. METRIC ENGINE
# =========================
def calculate_metrics(df: pd.DataFrame, ticker: str) -> dict | None:
    try:
        if df is None or df.empty or len(df) < 50:
            return None
        c = df["Close"].values.astype(float)
        h = df["High"].values.astype(float)
        l = df["Low"].values.astype(float)
        v = df["Volume"].values.astype(float)

        n = len(c)
        m20  = float(np.mean(c[-20:]))
        m50  = float(np.mean(c[-min(50, n):]))
        m200 = float(np.mean(c[-min(200, n):]))

        # ATR
        prev_c = np.roll(c, 1); prev_c[0] = c[0]
        tr = np.maximum(h-l, np.maximum(np.abs(h-prev_c), np.abs(l-prev_c)))
        atr = float(np.mean(tr[-14:])) if n >= 14 else float(np.mean(tr))

        # ADX
        adx = 0.0
        if n >= 28:
            up   = np.diff(h); down = -np.diff(l)
            pdm  = np.where((up > down) & (up > 0), up, 0.0)
            mdm  = np.where((down > up) & (down > 0), down, 0.0)
            tr14 = np.convolve(tr[1:], np.ones(14)/14, mode='valid')
            pdi  = 100 * np.convolve(pdm, np.ones(14)/14, mode='valid') / (tr14 + 1e-9)
            mdi  = 100 * np.convolve(mdm, np.ones(14)/14, mode='valid') / (tr14 + 1e-9)
            dxv  = np.abs(pdi - mdi) / (pdi + mdi + 1e-9) * 100
            adx  = float(np.mean(dxv[-14:])) if len(dxv) >= 14 else float(np.mean(dxv))

        # Z-Score
        std20 = float(np.std(c[-20:]))
        z     = float((c[-1] - m20) / std20) if std20 > 0 else 0.0

        # Volume surge
        avg_v20 = float(np.mean(v[-20:])) if n >= 20 else float(np.mean(v))
        vol_surge = float(v[-1] / avg_v20) if avg_v20 > 0 else 1.0

        # Price change
        p_chg = float((c[-1] - c[-2]) / c[-2]) if c[-2] != 0 else 0.0

        # Miro Score (0-10)
        miro = 0.0
        if vol_surge >= 5:   miro += 5
        elif vol_surge >= 4: miro += 4
        elif vol_surge >= 3: miro += 3
        elif vol_surge >= 2.5: miro += 2.5
        elif vol_surge >= 2:   miro += 2
        elif vol_surge >= 1.5: miro += 1
        abs_pct = abs(p_chg)
        if abs_pct >= 0.05:   miro += 5
        elif abs_pct >= 0.04: miro += 4
        elif abs_pct >= 0.03: miro += 3
        elif abs_pct >= 0.02: miro += 2
        elif abs_pct >= 0.01: miro += 1
        if p_chg < -0.01: miro = max(0, miro - 2)
        if p_chg < -0.03: miro = max(0, miro - 2)
        miro = min(10, round(miro, 1))

        # IBS — Internal Bar Strength (Kakushadze §mean reversion)
        ibs = float((c[-1] - l[-1]) / (h[-1] - l[-1])) if (h[-1] - l[-1]) > 0 else 0.5

        # Donchian Channel (20-day)
        donch_up   = float(np.max(h[-20:])) if n >= 20 else float(np.max(h))
        donch_down = float(np.min(l[-20:])) if n >= 20 else float(np.min(l))
        donch_pos  = (c[-1] - donch_down) / (donch_up - donch_down + 1e-9)

        # HP Filter — Hodrick-Prescott (λ=1400 for daily data)
        hp_trend = hp_filter(c, lam=1400)
        hp_signal = "ABOVE TREND" if c[-1] > hp_trend[-1] else "BELOW TREND"
        hp_slope  = float(hp_trend[-1] - hp_trend[-5]) if len(hp_trend) >= 5 else 0.0

        # Recommendation
        if z <= -2.5 or (ibs < 0.15 and vol_surge > 1.5):
            reco = "🪃 STRONG REVERSION BUY"
        elif p_chg > 0.02 and vol_surge > 2.2 and c[-1] > m20:
            reco = "🚀 STRONG BUY"
        elif p_chg > 0.01 and vol_surge > 1.8:
            reco = "📈 BUY"
        elif z >= 2.5 or (ibs > 0.85 and vol_surge > 1.5):
            reco = "🔻 STRONG REVERSION SELL"
        elif p_chg < -0.02 and vol_surge > 2.2:
            reco = "📉 SELL"
        else:
            reco = "💤 NEUTRAL"

        return {
            "cp": round(float(c[-1]), 2),
            "m20": round(m20, 2), "m50": round(m50, 2), "m200": round(m200, 2),
            "adx": round(adx, 1), "z": round(z, 2),
            "vol": round(vol_surge, 2), "atr": round(atr, 2),
            "reco": reco, "miro": miro,
            "ibs": round(ibs, 3),
            "donch_up": round(donch_up, 2), "donch_down": round(donch_down, 2),
            "donch_pos": round(donch_pos, 3),
            "hp_signal": hp_signal, "hp_slope": round(hp_slope, 4),
            "p_chg": round(p_chg * 100, 2),
        }
    except Exception:
        return None

# =========================
# 5. HP FILTER (Kakushadze §trend smoothing)
# =========================
def hp_filter(series: np.ndarray, lam: float = 1400) -> np.ndarray:
    """Hodrick-Prescott filter. Returns smoothed trend S*(t).
    Minimises: Σ[S(t)-S*(t)]² + λ·Σ[S*(t+1)-2S*(t)+S*(t-1)]²
    """
    n = len(series)
    if n < 5:
        return series.copy()
    from scipy.sparse import diags, eye
    from scipy.sparse.linalg import spsolve
    try:
        I = eye(n, format="csc")
        ones = np.ones(n - 2)
        D = diags([ones, -2*ones, ones], [0, 1, 2], shape=(n-2, n), format="csc")
        trend = spsolve((I + lam * D.T @ D), series)
        return trend
    except Exception:
        # Fallback: simple moving average
        return pd.Series(series).rolling(20, min_periods=1).mean().values

# =========================
# 6. MARKET REGIME
# =========================
def get_market_regime(df: pd.DataFrame):
    if df.empty:
        return "📡 OFFLINE", "Run a scan first", "info"
    total = len(df)
    above_200 = len(df[df["MA 200"] < df["Price"]])
    panic = len(df[df["Z-Score"] < -2.2])
    breadth  = (above_200 / total * 100) if total else 0
    panic_pct = (panic / total * 100) if total else 0
    if breadth > 60:
        return "🔥 BULL REGIME", "Momentum + Breakouts", "success"
    elif breadth < 40 and panic_pct > 15:
        return "😱 PANIC REGIME", "Mean Reversion entries", "error"
    elif breadth < 40:
        return "❄️ BEAR REGIME", "Capital Preservation", "warning"
    return "⚖️ NEUTRAL", "Selective Sector Rotation", "info"

# =========================
# 7. SCANNER
# =========================
@st.cache_data(ttl=1800, show_spinner=False)
def run_master_scan(symbols: tuple, sector_map: dict) -> pd.DataFrame:
    rows = []
    prog = st.progress(0, text="Scanning…")
    total = len(symbols)
    for i, sym in enumerate(symbols):
        prog.progress((i+1)/total, text=f"Scanning {sym} ({i+1}/{total})")
        ticker = sym + ".NS"
        df = fetch_candles_yf(ticker)
        m = calculate_metrics(df, sym)
        if m:
            rows.append({
                "Ticker":      sym,
                "Sector":      sector_map.get(sym, "Misc"),
                "Price":       m["cp"],
                "Recommendation": m["reco"],
                "Miro_Score":  m["miro"],
                "Z-Score":     m["z"],
                "ADX":         m["adx"],
                "Vol_Surge":   m["vol"],
                "MA 20":       m["m20"],
                "MA 50":       m["m50"],
                "MA 200":      m["m200"],
                "ATR":         m["atr"],
                "IBS":         m["ibs"],
                "Donch_Pos":   m["donch_pos"],
                "Donch_Up":    m["donch_up"],
                "Donch_Down":  m["donch_down"],
                "HP_Signal":   m["hp_signal"],
                "HP_Slope":    m["hp_slope"],
                "CHG%":        m["p_chg"],
            })
        time.sleep(0.05)  # polite rate limiting
    prog.empty()
    return pd.DataFrame(rows)

# =========================
# 8. TRADINGAGENTS PIPELINE (Claude multi-agent)
# =========================
AGENT_SYSTEM = """You are part of NiftySniper's institutional trading council.
Market context: Indian NSE equities. All prices in INR.
Be specific, concise, and actionable. Format clearly with markdown."""

def run_agent(client: Anthropic, role: str, prompt: str, context: str = "") -> str:
    """Run a single agent and return its analysis."""
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    with client.messages.stream(
        model="claude-opus-4-5-20251101",
        max_tokens=600,
        system=AGENT_SYSTEM + f"\n\nYour role: {role}",
        messages=[{"role": "user", "content": full_prompt}]
    ) as stream:
        return stream.get_final_text()

def build_stock_context(ticker: str, row: pd.Series, pulse: dict) -> str:
    return f"""
STOCK: {ticker}.NS
Price: ₹{row['Price']} | CHG: {row['CHG%']}% | Sector: {row['Sector']}
MA20: ₹{row['MA 20']} | MA50: ₹{row['MA 50']} | MA200: ₹{row['MA 200']}
ADX: {row['ADX']} | Z-Score: {row['Z-Score']} | Vol Surge: {row['Vol_Surge']}x
ATR: ₹{row['ATR']} | Miro: {row['Miro_Score']}/10
IBS: {row['IBS']} | Donchian Position: {row['Donch_Pos']:.0%} | HP Trend: {row['HP_Signal']}
NIFTY50: {pulse.get('nifty50', 'N/A')} | VIX: {pulse.get('vix', 'N/A')} | USD/INR: {pulse.get('usdinr', 'N/A')}
""".strip()

def run_trading_council(client: Anthropic, ticker: str, row: pd.Series,
                        pulse: dict, placeholder) -> None:
    """Run the full 5-agent TradingAgents pipeline with live streaming to UI."""
    ctx = build_stock_context(ticker, row, pulse)
    output = ""

    agents = [
        ("📊 TECHNICAL ANALYST", "Senior Technical Analyst for NSE equities",
         f"Analyse {ticker} technically. Cover: MA alignment, ADX trend strength, Z-score mean reversion, IBS reading ({row['IBS']:.3f}), Donchian channel position ({row['Donch_Pos']:.0%}), HP Filter signal ({row['HP_Signal']}). Give key support/resistance levels. Max 150 words."),

        ("🟢 BULL RESEARCHER", "Bullish equity researcher",
         f"Make the strongest bullish case for {ticker}. Use the technical data and sector context. Give 3 specific bull catalysts and a 4-week price target. Max 120 words."),

        ("🔴 BEAR RESEARCHER", "Bearish equity researcher",
         f"Make the strongest bearish case for {ticker}. Challenge the bull case. Give 3 specific downside risks and a worst-case scenario. Max 120 words."),

        ("⚖️ TRADER DECISION", "Senior Trader making the final call",
         f"Review the bull/bear debate for {ticker}. Give a clear BUY/SELL/HOLD decision with conviction score (1-10), exact entry zone, stop loss, and 4-week target. Max 100 words."),

        ("🛡️ RISK MANAGER", "Risk Manager and Portfolio Protector",
         f"For {ticker}: Given VIX={pulse.get('vix', 20)}, validate the trade. Recommend position size as % of portfolio, confirm or tighten the stop loss, and state max loss tolerance. Final verdict: APPROVED/REJECTED. Max 80 words."),
    ]

    prev_output = ""
    for title, role, prompt in agents:
        output += f"\n\n## {title}\n"
        placeholder.markdown(output + "▊")
        response = run_agent(client, role, prompt, ctx + "\n\n" + prev_output)
        output += response
        prev_output += f"\n\n{title}:\n{response}"
        placeholder.markdown(output)
        time.sleep(0.2)

    placeholder.markdown(output)

# =========================
# 9. PAIRS TRADING (Kakushadze §3.8)
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def compute_pairs(sym_a: str, sym_b: str) -> dict | None:
    """Compute demeaned return: R̃_A = R_A - ½(R_A + R_B)"""
    df_a = fetch_candles_yf(sym_a + ".NS")
    df_b = fetch_candles_yf(sym_b + ".NS")
    if df_a.empty or df_b.empty:
        return None
    # align on common dates
    df_a = df_a.set_index("date")["Close"]
    df_b = df_b.set_index("date")["Close"]
    common = df_a.index.intersection(df_b.index)
    if len(common) < 30:
        return None
    ra = df_a[common].pct_change().dropna()
    rb = df_b[common].pct_change().dropna()
    r_tilde_a = ra - 0.5 * (ra + rb)
    r_tilde_b = rb - 0.5 * (ra + rb)
    corr = float(ra.corr(rb))
    last_tilde_a = float(r_tilde_a.iloc[-1])
    signal = "SHORT A / BUY B" if last_tilde_a > 0 else "BUY A / SHORT B"
    return {
        "correlation": round(corr, 3),
        "r_tilde_a": round(last_tilde_a * 100, 4),
        "r_tilde_b": round(float(r_tilde_b.iloc[-1]) * 100, 4),
        "signal": signal,
        "strength": round(abs(last_tilde_a) * 100, 4),
    }

# =========================
# 10. KNN PREDICTION (Kakushadze §3.17)
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def knn_predict(ticker: str, k: int = 5, lookback: int = 5) -> dict | None:
    """k-Nearest Neighbours prediction using price/volume feature vectors.
    Distance: D(t,t')² = Σ(X̃_a(t) - X̃_a(t'))²
    Predicted return Y(t) = mean of k nearest historical outcomes.
    """
    df = fetch_candles_yf(ticker + ".NS")
    if df.empty or len(df) < lookback + k + 10:
        return None
    closes  = df["Close"].values.astype(float)
    volumes = df["Volume"].values.astype(float)
    # Normalise features
    c_norm = (closes - closes.mean()) / (closes.std() + 1e-9)
    v_norm = (volumes - volumes.mean()) / (volumes.std() + 1e-9)
    # Build feature vectors of length `lookback`
    X, Y = [], []
    for i in range(lookback, len(closes) - 1):
        feat = np.concatenate([c_norm[i-lookback:i], v_norm[i-lookback:i]])
        X.append(feat)
        Y.append((closes[i+1] - closes[i]) / closes[i])
    X, Y = np.array(X), np.array(Y)
    # Current vector
    curr = np.concatenate([c_norm[-lookback:], v_norm[-lookback:]])
    # Euclidean distances
    dists = np.sqrt(np.sum((X - curr) ** 2, axis=1))
    nn_idx = np.argsort(dists)[:k]
    predicted_return = float(np.mean(Y[nn_idx]))
    confidence = 1.0 - float(np.std(Y[nn_idx])) / (abs(predicted_return) + 1e-9)
    signal = "BUY" if predicted_return > 0.002 else "SELL" if predicted_return < -0.002 else "HOLD"
    return {
        "predicted_return_pct": round(predicted_return * 100, 4),
        "signal": signal,
        "confidence": round(min(max(confidence, 0), 1), 3),
        "k_used": k,
        "avg_dist": round(float(np.mean(dists[nn_idx])), 4),
    }

# =========================
# 11. MAIN UI
# =========================
# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0a0a0a; }
.strategy-card {
    background: #111; border: 1px solid #ff6600; border-radius:4px;
    padding: 10px 14px; margin-bottom: 8px; cursor: pointer;
}
.metric-card {
    background: #0d0d0d; border: 1px solid #1a1a1a;
    padding: 12px; border-radius: 4px; text-align: center;
}
.regime-bull  { color: #00ff41; font-weight: 700; }
.regime-bear  { color: #ff2222; font-weight: 700; }
.regime-panic { color: #ff8800; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Nifty Sniper Elite v12.0")
st.caption("Multi-agent AI · Direct Yahoo Finance · HP Filter · IBS · Donchian · KNN · Pairs Trading")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ STRATEGY MODE")
    strategy = st.radio(
        "Select Strategy",
        options=["📈 HP Filter Trend", "🎯 IBS Mean Reversion",
                 "📦 Donchian Breakout", "🤖 KNN ML Predict",
                 "⚖️ Pairs Trading"],
        label_visibility="collapsed"
    )
    strategy_key = strategy.split()[1].lower()  # hp, ibs, donchian, knn, pairs

    st.markdown("---")
    st.markdown("### 🏦 SCAN UNIVERSE")
    scan_limit = st.slider("Stocks to scan", 25, 500, 100, 25)
    risk_per_trade = st.number_input("Risk Per Trade (₹)", value=5000, step=500)

    st.markdown("---")
    st.markdown("### 🌡️ MARKET PULSE")
    if st.button("Refresh Pulse", use_container_width=True):
        st.cache_data.clear()
    pulse_data = fetch_market_pulse()
    nifty_chg = pulse_data.get("nifty50", 0) - pulse_data.get("nifty50_prev", 0)
    nifty_pct = (nifty_chg / pulse_data.get("nifty50_prev", 1) * 100) if pulse_data.get("nifty50_prev") else 0
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("NIFTY 50", f"{pulse_data.get('nifty50', 'N/A'):,.0f}", f"{nifty_pct:+.2f}%")
        st.metric("VIX", f"{pulse_data.get('vix', 'N/A'):.2f}")
    with col_b:
        st.metric("BANK NIFTY", f"{pulse_data.get('banknifty', 'N/A'):,.0f}")
        st.metric("USD/INR", f"{pulse_data.get('usdinr', 'N/A'):.2f}")

    st.markdown("---")
    # Strategy descriptions
    st.markdown("##### 📖 Strategy Guide")
    guides = {
        "hp":       "**HP Filter** (λ=1400): Isolates trend from noise. Crossovers on S*(t) beat raw price signals.",
        "ibs":      "**IBS**: (Close-Low)/(High-Low). IBS<0.2=BUY near low. IBS>0.8=SHORT near high.",
        "donchian": "**Donchian**: 20-day B_up/B_down. Price at channel top=breakout BUY. Bottom=SHORT.",
        "knn":      "**KNN** (k=5): Finds 5 historical price/vol twins. Predicts next-day return via Euclidean distance.",
        "pairs":    "**Pairs**: R̃_A = R_A - ½(R_A+R_B). Short 'rich' stock, buy 'cheap' stock.",
    }
    st.info(guides.get(strategy_key, ""))
    st.markdown("---")
    st.markdown("<small>⚠️ Not SEBI registered · Not buy/sell advice</small>", unsafe_allow_html=True)

# ── SCAN TRIGGER ─────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 5])
with col1:
    run_scan = st.button("🚀 EXECUTE SCAN", use_container_width=True, type="primary")
with col2:
    clear_cache = st.button("🔄 Clear Cache", use_container_width=True)
if clear_cache:
    st.cache_data.clear()
    st.rerun()

if run_scan:
    symbols_list, sector_map = get_nifty500_list()
    symbols_list = symbols_list[:scan_limit]
    with st.spinner("Fetching live NSE data from Yahoo Finance..."):
        result_df = run_master_scan(tuple(symbols_list), sector_map)
    if not result_df.empty:
        st.session_state["scan_df"] = result_df
        st.session_state["pulse"] = pulse_data
        st.success(f"✅ Scan complete — {len(result_df)} stocks analysed")
    else:
        st.error("No results. Check your internet connection.")

# ── RESULTS ───────────────────────────────────────────────────────────────────
if "scan_df" in st.session_state:
    df    = st.session_state["scan_df"].copy()
    pulse = st.session_state.get("pulse", {})

    # Regime banner
    regime, advice, color = get_market_regime(df)
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    with col_r1: st.metric("🌡️ Market Regime", regime)
    with col_r2: st.metric("📌 Strategy Advice", advice)
    with col_r3: st.metric("📊 Stocks Scanned", len(df))
    with col_r4:
        strong_buys = len(df[df["Recommendation"].str.contains("STRONG BUY", na=False)])
        st.metric("🚀 Strong Signals", strong_buys)

    # Stop loss + position sizing
    assumed_vix = float(pulse.get("vix", 20) or 20)
    sl_mult = 3.0 if assumed_vix > 25 else 2.5 if assumed_vix > 20 else 2.0
    df["Stop_Loss"] = (df["Price"] - sl_mult * df["ATR"]).round(2)
    df["Risk/Share"] = (df["Price"] - df["Stop_Loss"]).clip(lower=0.01)
    df["Qty"]       = (risk_per_trade / df["Risk/Share"]).astype(int)

    st.markdown("---")

    # ── TABS ────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "⚡ Miro Flow",
        "📈 HP Filter",
        "🎯 IBS Reversion",
        "📦 Donchian",
        "📉 Trend & ADX",
        "📊 Z-Score",
        "🤖 KNN Predict",
        "⚖️ Pairs Trading",
        "🧠 AI Council",
        "🛡️ Risk Lab",
    ])

    # ─ TAB 0: MIRO ─────────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("⚡ Miro Flow — Institutional Hot Money Detector")
        st.caption("Miro Score 0-10 | Score ≥8 = strong institutional flow | Vol Surge = today vs 20-day avg")
        out = df[["Ticker","Sector","Price","CHG%","Miro_Score","Vol_Surge","Recommendation"]].sort_values("Miro_Score", ascending=False)
        st.dataframe(out, hide_index=True, use_container_width=True)

    # ─ TAB 1: HP FILTER ────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("📈 Hodrick-Prescott Filter — Trend vs Noise (Kakushadze §trend)")
        st.caption("λ=1400 for daily data | ABOVE TREND = bullish momentum on smoothed price S*(t)")
        hp_df = df[["Ticker","Sector","Price","CHG%","HP_Signal","HP_Slope","MA 50","MA 200","ADX"]].copy()
        hp_df = hp_df.sort_values("HP_Slope", ascending=False)
        hp_df["HP_Slope"] = hp_df["HP_Slope"].apply(lambda x: f"+{x:.4f}" if x >= 0 else f"{x:.4f}")
        def hp_highlight(row):
            if row["HP_Signal"] == "ABOVE TREND":
                return ["background-color: #001a00"] * len(row)
            return ["background-color: #1a0000"] * len(row)
        st.dataframe(hp_df.style.apply(hp_highlight, axis=1), hide_index=True, use_container_width=True)

    # ─ TAB 2: IBS ──────────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("🎯 Internal Bar Strength — Mean Reversion (Kakushadze §IBS)")
        st.caption("IBS = (Close - Low) / (High - Low) | <0.2 = near daily LOW → BUY | >0.8 = near daily HIGH → SHORT")
        ibs_df = df[["Ticker","Sector","Price","CHG%","IBS","Z-Score","Vol_Surge","ATR"]].copy()
        ibs_df = ibs_df.sort_values("IBS")
        ibs_df["IBS Signal"] = ibs_df["IBS"].apply(
            lambda x: "🟢 BUY (near low)" if x < 0.2 else "🔴 SHORT (near high)" if x > 0.8 else "⚪ NEUTRAL"
        )
        st.dataframe(ibs_df, hide_index=True, use_container_width=True)
        col_buy, col_short = st.columns(2)
        with col_buy:
            st.metric("IBS < 0.2 (Buy Setups)", len(ibs_df[ibs_df["IBS"] < 0.2]))
        with col_short:
            st.metric("IBS > 0.8 (Short Setups)", len(ibs_df[ibs_df["IBS"] > 0.8]))

    # ─ TAB 3: DONCHIAN ─────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("📦 Donchian Channel Breakouts (Kakushadze §support/resistance)")
        st.caption("B_up = 20-day high | B_down = 20-day low | Position 0=bottom, 1=top of channel")
        don_df = df[["Ticker","Sector","Price","CHG%","Donch_Pos","Donch_Up","Donch_Down","Vol_Surge","ATR"]].copy()
        don_df = don_df.sort_values("Donch_Pos", ascending=False)
        don_df["Channel %"] = (don_df["Donch_Pos"] * 100).round(1).astype(str) + "%"
        don_df["Breakout Signal"] = don_df["Donch_Pos"].apply(
            lambda x: "🚀 UPPER BREAKOUT" if x > 0.95 else
                      "🔻 LOWER BREAKDOWN" if x < 0.05 else
                      "📈 UPPER ZONE" if x > 0.75 else
                      "📉 LOWER ZONE" if x < 0.25 else "↔️ MID CHANNEL"
        )
        st.dataframe(don_df[["Ticker","Sector","Price","CHG%","Channel %","Donch_Up","Donch_Down","Breakout Signal","Vol_Surge"]], hide_index=True, use_container_width=True)

    # ─ TAB 4: TREND & ADX ──────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("📉 Structural Trend & ADX Strength")
        st.caption("Golden Cross = Price > MA50 > MA200 | ADX > 25 = strong trend confirmed")
        trend_df = df[["Ticker","Sector","Price","CHG%","ADX","MA 20","MA 50","MA 200","HP_Signal"]].copy()
        trend_df["Alignment"] = trend_df.apply(
            lambda r: "🟡 GOLDEN" if r["Price"] > r["MA 50"] > r["MA 200"]
            else "💀 DEATH" if r["Price"] < r["MA 50"] < r["MA 200"]
            else "↗️ PARTIAL", axis=1
        )
        trend_df = trend_df.sort_values("ADX", ascending=False)
        st.dataframe(trend_df, hide_index=True, use_container_width=True)

    # ─ TAB 5: Z-SCORE ──────────────────────────────────────────────────────
    with tabs[5]:
        st.subheader("📊 Statistical Mean Reversion — Z-Score")
        st.caption("Z < -2.5 = extreme oversold SNAP-BACK BUY | Z > +2.5 = extreme overbought SELL")
        z_df = df[["Ticker","Sector","Price","CHG%","Z-Score","IBS","Vol_Surge","MA 20"]].copy()
        z_df = z_df.sort_values("Z-Score")
        z_df["Z Signal"] = z_df["Z-Score"].apply(
            lambda z: "🚀 STRONG BUY" if z <= -2.5 else
                      "📈 OVERSOLD" if z <= -1.5 else
                      "🔻 STRONG SELL" if z >= 2.5 else
                      "📉 OVERBOUGHT" if z >= 1.5 else "NEUTRAL"
        )
        st.dataframe(z_df, hide_index=True, use_container_width=True)

    # ─ TAB 6: KNN ──────────────────────────────────────────────────────────
    with tabs[6]:
        st.subheader("🤖 KNN Machine Learning Prediction (Kakushadze §3.17)")
        st.caption(f"k=5 nearest historical price/volume twins | Euclidean distance | Predicts next-day return")
        knn_ticker = st.selectbox("Select stock for KNN analysis", df["Ticker"].tolist(), key="knn_sel")
        if st.button("🤖 Run KNN Prediction", key="knn_btn"):
            with st.spinner(f"Finding 5 nearest historical twins for {knn_ticker}..."):
                result = knn_predict(knn_ticker)
            if result:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Predicted Return", f"{result['predicted_return_pct']:+.3f}%")
                c2.metric("Signal", result["signal"])
                c3.metric("Confidence", f"{result['confidence']:.0%}")
                c4.metric("Avg Distance", f"{result['avg_dist']:.4f}")
                direction = "📈" if result["predicted_return_pct"] > 0 else "📉"
                st.info(f"{direction} KNN predicts {result['signal']} for **{knn_ticker}** with {result['confidence']:.0%} confidence based on {result['k_used']} nearest historical patterns.")
            else:
                st.warning("Insufficient data for KNN prediction. Need at least 60 trading days.")

    # ─ TAB 7: PAIRS TRADING ────────────────────────────────────────────────
    with tabs[7]:
        st.subheader("⚖️ Pairs Trading — Cross-Sectional (Kakushadze §3.8)")
        st.caption("R̃_A = R_A - ½(R_A+R_B) | Positive R̃_A = A is 'rich', SHORT A / BUY B")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            sym_a = st.selectbox("Stock A", df["Ticker"].tolist(), key="pair_a")
        with col_p2:
            sym_b = st.selectbox("Stock B", df["Ticker"].tolist(), index=1, key="pair_b")
        if st.button("⚖️ Analyse Pair", key="pairs_btn"):
            if sym_a == sym_b:
                st.error("Select two different stocks")
            else:
                with st.spinner(f"Computing pair {sym_a} / {sym_b}..."):
                    pair = compute_pairs(sym_a, sym_b)
                if pair:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Correlation", f"{pair['correlation']:.3f}")
                    c2.metric("R̃_A (demeaned)", f"{pair['r_tilde_a']:+.4f}%")
                    c3.metric("Signal", pair["signal"])
                    if pair["correlation"] < 0.5:
                        st.warning(f"⚠️ Low correlation ({pair['correlation']:.2f}) — pairs trade may be unreliable. Look for pairs with correlation > 0.7")
                    else:
                        st.success(f"✅ **{pair['signal']}** | Strength: {pair['strength']:.4f}% | Correlation: {pair['correlation']:.3f}")
                    st.info("""**How to trade this:**
- The stock with **positive R̃** is trading 'rich' vs its peer → SHORT it
- The stock with **negative R̃** is trading 'cheap' → BUY it
- Close both legs when returns converge (typically 1-5 days)
- Use equal INR value in both legs for market neutrality""")
                else:
                    st.error("Could not fetch data for one or both symbols")

    # ─ TAB 8: AI COUNCIL ───────────────────────────────────────────────────
    with tabs[8]:
        st.subheader("🧠 AI Investment Council — Multi-Agent TradingAgents Pipeline")
        st.caption("5 specialized Claude agents debate each stock: Technical → Bull → Bear → Trader → Risk Manager")
        client = get_anthropic_client()
        if client is None:
            st.warning("Add `ANTHROPIC_API_KEY` to Streamlit secrets (.streamlit/secrets.toml) to enable the AI Council.")
            st.code("""# .streamlit/secrets.toml
ANTHROPIC_API_KEY = "sk-ant-..."
""", language="toml")
        else:
            council_ticker = st.selectbox("Select stock for council analysis",
                                          df["Ticker"].tolist(), key="council_sel")
            row_data = df[df["Ticker"] == council_ticker].iloc[0]
            # Show quick stats
            with st.expander("📊 Quick Stats", expanded=True):
                cs1, cs2, cs3, cs4, cs5 = st.columns(5)
                cs1.metric("Price", f"₹{row_data['Price']:,.2f}", f"{row_data['CHG%']:+.2f}%")
                cs2.metric("Miro Score", f"{row_data['Miro_Score']}/10")
                cs3.metric("Z-Score", f"{row_data['Z-Score']:.2f}")
                cs4.metric("IBS", f"{row_data['IBS']:.3f}")
                cs5.metric("HP Trend", row_data["HP_Signal"])

            if st.button("🏛️ SUMMON COUNCIL", key="council_btn", use_container_width=True, type="primary"):
                result_area = st.empty()
                result_area.info("Council assembling...")
                run_trading_council(client, council_ticker, row_data, pulse, result_area)

    # ─ TAB 9: RISK LAB ─────────────────────────────────────────────────────
    with tabs[9]:
        st.subheader("🛡️ Risk Lab — Position Sizing & Stop Loss Engine")
        st.caption(f"Stop = Price - {sl_mult}× ATR | Qty = ₹{risk_per_trade:,} / Risk-per-Share | VIX = {assumed_vix:.1f}")
        risk_df = df[["Ticker","Sector","Price","Stop_Loss","Risk/Share","Qty","ATR","Vol_Surge","Recommendation"]].copy()
        risk_df = risk_df.sort_values("Qty", ascending=False)
        risk_df["Risk%"] = ((risk_df["Price"] - risk_df["Stop_Loss"]) / risk_df["Price"] * 100).round(2)
        st.dataframe(risk_df, hide_index=True, use_container_width=True)
        total_trades = len(risk_df[risk_df["Qty"] > 0])
        st.info(f"**{total_trades} tradeable** | SL multiplier: {sl_mult}× ATR | Max loss/trade: ₹{risk_per_trade:,}")

else:
    # ── WELCOME SCREEN ────────────────────────────────────────────────────
    st.markdown("""
    ### Welcome to Nifty Sniper Elite v12.0

    **What's new in v12.0:**
    - ✅ Direct Yahoo Finance — no local bridge required, deploys anywhere
    - ✅ HP Filter (Hodrick-Prescott, λ=1400) for trend smoothing
    - ✅ IBS (Internal Bar Strength) mean reversion signals
    - ✅ Donchian Channel 20-day breakout detection
    - ✅ KNN ML prediction (k=5 nearest historical twins)
    - ✅ Pairs Trading with demeaned return R̃ calculation
    - ✅ 5-agent Claude AI Council (Technical → Bull → Bear → Trader → Risk Manager)
    - ✅ Full Nifty 500 universe from live NSE archives

    **To get started:** Set the scan limit in the sidebar and click **🚀 EXECUTE SCAN**

    > ⚠️ *NiftySniper is NOT registered with SEBI. This is an institutional-grade scanner to assist in your trading journey. All signals are not buy/sell recommendations.*
    """)
