import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper v5.3", layout="wide")
st.error("🏹 VERSION 5.3: MULTI-INDEX FIX + CONDENSED ADX")

# --- 2. THE NATIVE MATH ENGINE ---

def get_clean_data(ticker):
    """Fetches data and forces it into a FLAT format to avoid MultiIndex errors"""
    raw = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
    if raw.empty: return None
    
    # THE 2026 FIX: Drop the ticker-level from columns if it exists
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    
    return raw

def calculate_adx_strength(df, period=14):
    """Calculates ADX and returns a single Strength String"""
    try:
        high, low, close = df['High'], df['Low'], df['Close']
        plus_dm = high.diff(); minus_dm = low.diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
        
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(period).mean().iloc[-1]
        
        # Single Column Logic
        if adx > 25: return f"🔥 STRONG ({round(adx,1)})"
        if adx > 20: return f"⚡ BUILDING ({round(adx,1)})"
        return f"💤 CHOPPY ({round(adx,1)})"
    except: return "N/A"

# --- 3. MASTER SCANNER ---

def run_sniper_scan(limit):
    # Standard Nifty Tickers
    symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS", "ABB.NS", "FLUOROCHEM.NS", "TRENT.NS", "HAL.NS"]
    all_results = []
    
    prog = st.progress(0, text="Deep Scanning...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        df = get_clean_data(t)
        if df is None or len(df) < 50: continue
        
        # 1. Miro Score (Momentum)
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
        p_change = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]
        
        miro_score = 0
        if vol_surge > 1.8: miro_score += 5
        if p_change > 0.02: miro_score += 3
        
        # 2. Trend & ADX
        cp = df['Close'].iloc[-1]
        m20 = df['Close'].rolling(20).mean().iloc[-1]
        m200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else df['Close'].mean()
        
        adx_strength = calculate_adx_strength(df)
        
        all_results.append({
            "Ticker": t, "Price": round(cp, 2),
            "Miro_Score": miro_score, "Vol_Surge": round(vol_surge, 2),
            "ADX Strength": adx_strength, # THE REQUESTED SINGLE COLUMN
            "Trend": "🟢 BULL" if cp > m200 else "⚪ NEUTRAL",
            "MA 20": round(m20, 2), "MA 200": round(m200, 2)
        })
        
    prog.empty()
    return pd.DataFrame(all_results)

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v5.3")
if st.sidebar.button("🚀 INITIALIZE SCAN"):
    res = run_sniper_scan(30)
    if not res.empty:
        st.session_state['res'] = res

if 'res' in st.session_state:
    df = st.session_state['res']
    
    tab1, tab2 = st.tabs(["🎯 MiroFish Leaderboard", "📈 Trends Ribbon"])
    
    with tab1:
        st.subheader("MiroFish Momentum")
        # Kept exactly as before
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
        
    with tab2:
        st.subheader("Structural Ribbon")
        # Added the ADX Strength column here per your request
        st.dataframe(df[['Ticker', 'Trend', 'ADX Strength', 'MA 20', 'MA 200']], use_container_width=True)
else:
    st.info("System Ready. Use the sidebar to start.")
