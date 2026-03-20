import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

st.set_page_config(page_title="Nifty Sniper Elite v5.2", layout="wide")

# --- 1. THE MATH DESK (NO LIBRARIES) ---

def calculate_vpt_native(close, volume):
    """Calculates Volume Price Trend (VPT)"""
    pct_change = close.pct_change()
    vpt = (pct_change * volume).cumsum()
    return vpt.iloc[-1], vpt.iloc[-2]

def calculate_volatility_atr(high, low, close, period=14):
    """Calculates Average True Range (ATR) for Volatility"""
    tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return round(atr, 2)

# --- 2. MASTER DATA SCANNER ---

@st.cache_data(ttl=3600)
def run_full_scan(limit):
    symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS", "ABB.NS", "FLUOROCHEM.NS"] # Expanded in app
    all_data = []
    
    for t in symbols[:limit]:
        try:
            df_raw = yf.download(t, period="1y", progress=False, auto_adjust=True)
            if df_raw.empty: continue
            
            # Flattening for 2026 Pandas
            c = df_raw['Close'].values.flatten()
            v = df_raw['Volume'].values.flatten()
            h = df_raw['High'].values.flatten()
            l = df_raw['Low'].values.flatten()
            
            s_close = pd.Series(c)
            s_vol = pd.Series(v)

            # --- VOLATILITY DESK ---
            atr = calculate_volatility_atr(pd.Series(h), pd.Series(l), s_close)
            volatility_pct = (atr / c[-1]) * 100

            # --- VOLUME FLOW (VPT) ---
            vpt_now, vpt_prev = calculate_vpt_native(s_close, s_vol)
            vpt_trend = "📈 ACCUMULATION" if vpt_now > vpt_prev else "📉 DISTRIBUTION"

            # --- MIRO SCORE RE-INTEGRATED ---
            vol_surge = v[-1] / np.mean(v[-20:])
            miro_score = 0
            if vol_surge > 2.0: miro_score += 5
            if vpt_now > vpt_prev: miro_score += 3
            if volatility_pct < 3.0: miro_score += 2 # Low vol breakout preference

            all_data.append({
                "Ticker": t, "Price": round(c[-1], 2),
                "Miro_Score": miro_score, "Vol_Surge": round(vol_surge, 2),
                "ATR (Vol)": atr, "Vol %": f"{round(volatility_pct, 1)}%",
                "Flow": vpt_trend, "Trend": "🟢 BULL" if c[-1] > np.mean(c[-200:]) else "⚪ NEUTRAL"
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 3. UI LAYOUT ---

st.sidebar.title("🏹 Nifty Sniper v5.2")
if st.sidebar.button("🚀 RUN FULL DIAGNOSTIC"):
    st.session_state['data'] = run_full_scan(20)

if 'data' in st.session_state:
    df = st.session_state['data']
    t1, t2, t3 = st.tabs(["📊 Inst. Flow (Volume)", "🛡️ Risk Lab (Volatility)", "🧬 Master Leaderboard"])
    
    with t1:
        st.subheader("Institutional Flow (VPT + Surge)")
        # This shows if big money is actually accumulating or just trading
        st.dataframe(df[['Ticker', 'Flow', 'Vol_Surge', 'Miro_Score']], use_container_width=True)
        
    with t2:
        st.subheader("Volatility & Risk Desk")
        # Shows ATR and how 'wild' the stock is moving
        st.dataframe(df[['Ticker', 'Price', 'ATR (Vol)', 'Vol %', 'Trend']], use_container_width=True)
        
    with t3:
        st.dataframe(df.sort_values("Miro_Score", ascending=False), use_container_width=True)
