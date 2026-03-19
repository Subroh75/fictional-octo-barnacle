import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG & AI ---
st.set_page_config(page_title="Nifty Sniper AI Institutional", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. THE ULTIMATE DATA ENGINE (2026 FIX) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "3MINDIA.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Deep-Scanning Market Structure...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # We fetch 2y to ensure the 200 SMA has enough data points
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 200: continue
            
            # --- THE 2026 FIX: BRUTE FORCE EXTRACTION ---
            # We bypass the headers entirely and pull the raw numpy values
            close_vals = raw['Close'].values.flatten()
            vol_vals = raw['Volume'].values.flatten()
            
            # Reconstruct a CLEAN, FLAT series for math
            s_close = pd.Series(close_vals)
            s_vol = pd.Series(vol_vals)
            
            cp = float(s_close.iloc[-1])
            m20 = float(s_close.tail(20).mean())
            m50 = float(s_close.tail(50).mean())
            m200 = float(s_close.tail(200).mean())
            
            # Distance from 20 MA
            dist_ma20 = ((cp - m20) / m20) * 100
            
            # Volume Surge
            avg_vol = float(s_vol.tail(20).mean())
            vol_surge = float(s_vol.iloc[-1]) / avg_vol if avg_vol != 0 else 0

            # Trend Score
            score = 0
            if cp > m20 > m50: score += 2
            if cp > m200: score += 3
            if vol_surge > 1.8: score += 5

            p_change = (cp - s_close.iloc[-2]) / s_close.iloc[-2]
            action = "🔥 AGGRESSIVE BUY" if (p_change > 0 and vol_surge > 1.8) else "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA 20": round(m20, 2), "MA 50": round(m50, 2), "MA 200": round(m200, 2),
                "MA20 Dist": f"{round(dist_ma20, 2)}%", "Score": score, 
                "Vol_Surge": round(vol_surge, 2), "Action": action,
                "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL"
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper AI")
v_vix = st.sidebar.number_input("India VIX", value=21.84)
v_depth = st.sidebar.slider("Depth", 50, 500, 100)
v_risk = st.sidebar.number_input("Risk (INR)", value=5000)

if st.sidebar.button("🚀 START AI SCAN"):
    # Force a cache clear to ensure fresh data mapping
    st.cache_data.clear()
    res = run_full_scan(v_depth)
    if not res.empty:
        st.session_state['scan_results'] = res

if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    t1, t2, t3 = st.tabs(["🎯 Leaderboard", "📈 Trend & MA Analysis", "🧠 Risk Lab"])
    
    with t1:
        st.subheader("Leaderboard")
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
        
    with t2:
        st.subheader("Structural Moving Averages")
        # EXPLICITLY SELECTING THE NEW COLUMNS
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200', 'MA20 Dist', 'Trend']], use_container_width=True)
        
    with t3:
        st.subheader("Risk & Action Lab")
        st.dataframe(df[['Ticker', 'Price', 'Action', 'Vol_Surge', 'Sector']], use_container_width=True)
else:
    st.info("System Ready. Click 'START AI SCAN' to begin.")
