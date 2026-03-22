import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime, timedelta

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper Elite v11.0", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE ADVANCED WEEKLY SNIPER ENGINE ---
def calculate_weekly_accumulation(df, ticker):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, level=1, axis=1) if ticker in df.columns.get_level_values(1) else df.columns.get_level_values(0)
        
        df.columns = [str(c).capitalize() for c in df.columns]
        c = df['Close'].values.flatten()
        v = df['Volume'].values.flatten()
        
        # 5-Day (Weekly) Window
        weekly_price_chg = (c[-1] - c[-5]) / c[-5]
        avg_vol = np.mean(v[-20:-5])
        curr_week_vol = np.mean(v[-5:])
        vol_ratio = curr_week_vol / avg_vol
        
        # Smart Money Accumulation Signal:
        # Price is stable/rising slightly while volume is expanding
        accumulation_score = 0
        if 0 < weekly_price_chg < 0.03: accumulation_score += 4 # Quiet absorption
        if vol_ratio > 1.5: accumulation_score += 6 # Institutional footprint
        
        status = "💎 ACCUMULATION" if accumulation_score >= 6 else "⚖️ CHURN" if vol_ratio > 1.2 else "💤 QUIET"
        
        return {"price": c[-1], "weekly_chg": round(weekly_price_chg * 100, 2), "vol_ratio": round(vol_ratio, 2), "status": status}
    except: return None

# --- 3. THE "UNSHRUNK" MATH ENGINE ---
def calculate_metrics(df, ticker):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, level=1, axis=1) if ticker in df.columns.get_level_values(1) else df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]
        c, h, l, v = df['Close'].values.flatten(), df['High'].values.flatten(), df['Low'].values.flatten(), df['Volume'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_s = v[-1] / np.mean(v[-20:])
        p_chg = (c[-1] - c[-2]) / c[-2]
        miro = 2 + (5 if vol_s > 2.0 else 0) + (3 if p_chg > 0.01 else 0)
        reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_s > 2.2 else "🪃 REVERSION" if z < -2.2 else "💤 NEUTRAL"
        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": round(adx, 1), "z": round(z, 2), "vol": round(vol_s, 2), "atr": atr, "reco": reco, "miro": miro}
    except: return None

# --- 4. THE SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    symbols = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ESCORTS.NS", "INFY.NS", "ADANIPOWER.NS", "TATASTEEL.NS"]
    all_data = []
    for t in symbols[:limit]:
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            m = calculate_metrics(raw, t)
            w = calculate_weekly_accumulation(raw, t)
            if m and w:
                all_data.append({
                    "Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], "Miro_Score": m['miro'], "Z-Score": m['z'], 
                    "ADX": m['adx'], "Vol_Surge": m['vol'], "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2),
                    "Weekly_Chg%": w['weekly_chg'], "Weekly_Vol_Ratio": w['vol_ratio'], "Weekly_Flow": w['status']
                })
        except: continue
    return pd.DataFrame(all_data)

# --- 5. INTERFACE ---
st.title("🏹 Nifty Sniper Elite v11.0")

if st.sidebar.button("🚀 EXECUTE 2026 AUDIT"):
    res = run_master_scan(100)
    if not res.empty: st.session_state['v11_res'] = res

if 'v11_res' in st.session_state:
    df = st.session_state['v11_res']
    tabs = st.tabs(["💎 Weekly Sniper", "🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧠 Intelligence", "🛡️ Risk Lab"])
    
    with tabs[0]: # WEEKLY SNIPER
        st.subheader("💎 Institutional Weekly Flow")
        st.dataframe(df[["Ticker", "Price", "Weekly_Chg%", "Weekly_Vol_Ratio", "Weekly_Flow"]].sort_values("Weekly_Vol_Ratio", ascending=False), hide_index=True, use_container_width=True)
        with st.expander("📘 HOW TO READ: The Weekly Sniper"):
            st.markdown("""
            **The Edge:** Institutions don't buy in a day; they buy over a week.
            - **💎 ACCUMULATION:** Price is steady or rising slightly (<3%), but volume is 1.5x higher than usual. This is 'Smart Money' quietly absorbing supply.
            - **⚖️ CHURN:** High volume with no price movement. Big money is exiting while retail is entering (or vice versa). Avoid until a breakout.
            - **Investment Signal:** Look for a 3-week streak of ACCUMULATION for a high-conviction positional trade.
            """)

    with tabs[1]: # MIRO FLOW
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge"]].sort_values("Miro_Score", ascending=False), hide_index=True, use_container_width=True)
        with st.expander("📘 HOW TO READ: Miro Flow"):
            st.markdown("""
            **The Edge:** Detects 'Momentum Bursts' caused by news or algorithmic buying.
            - **Miro Score (8-10):** Extreme conviction. The stock is being chased.
            - **Vol Surge > 2.2:** Confirms the move is real. Never trust a breakout on low volume.
            """)

    with tabs[3]: # REVERSION
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Z-Score"]].sort_values("Z-Score"), hide_index=True, use_container_width=True)
        with st.expander("📘 HOW TO READ: Mean Reversion"):
            st.markdown("""
            **The Edge:** Markets are like rubber bands; they snap back when stretched too far.
            - **Z-Score < -2.2:** The stock is 'statistically' oversold. Expect a 🪃 snap-back to the MA 20 within days.
            - **Z-Score > 2.2:** Danger zone. The stock is overheated. Trim positions.
            """)
else:
    st.info("Scanner Ready.")
