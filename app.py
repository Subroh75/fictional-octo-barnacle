import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. SYSTEM SETTINGS ---
st.set_page_config(page_title="Nifty Sniper Dual-Engine v5.0", layout="wide")
st.error("🚀 VERSION 5.0: LIGHTWEIGHT ENGINE (No External TA Libraries)")

# --- 2. HEDGE FUND MATH DESK (NO LIBRARIES NEEDED) ---

def calculate_adx_lite(high, low, close, period=14):
    """Raw mathematical calculation of ADX, D+, D-"""
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
    atr = tr.rolling(period).mean()
    
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (abs(minus_dm).rolling(period).mean() / atr)
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    return round(adx.iloc[-1], 2), round(plus_di.iloc[-1], 2), round(minus_di.iloc[-1], 2)

def calculate_relative_strength(stock_close, nifty_close):
    """Calculates how much the stock is outperforming Nifty 50"""
    stock_ret = stock_close.pct_change(60).iloc[-1] # 3-month return
    nifty_ret = nifty_close.pct_change(60).iloc[-1]
    rs_score = (stock_ret - nifty_ret) * 100
    return round(rs_score, 2)

# --- 3. THE DATA ENGINE ---
def run_sniper_scan(limit):
    # Fetch Nifty 50 for RS Calculation
    nifty = yf.download("^NSEI", period="1y", progress=False, auto_adjust=True)
    nifty_close = nifty['Close']

    symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS", "3MINDIA.NS", "ABB.NS", "FLUOROCHEM.NS"]
    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False, auto_adjust=True)
            if df.empty or len(df) < 50: continue
            
            # Clean data
            c = df['Close'].values.flatten()
            h = df['High'].values.flatten()
            l = df['Low'].values.flatten()
            v = df['Volume'].values.flatten()
            
            s_close = pd.Series(c)
            
            # MiroFish Logic (Momentum)
            vol_surge = v[-1] / np.mean(v[-20:])
            miro_score = 0
            if vol_surge > 1.8: miro_score += 5
            if (c[-1] > c[-2]): miro_score += 2

            # MA Trend Desk
            m20 = np.mean(c[-20:])
            m200 = np.mean(c[-200:]) if len(c) >= 200 else np.mean(c)
            
            # ADX Desk (Strength)
            adx, d_plus, d_minus = calculate_adx_lite(pd.Series(h), pd.Series(l), s_close)
            
            # RS Desk (Alpha)
            rs_val = calculate_relative_strength(s_close, nifty_close)

            all_data.append({
                "Ticker": t, "Price": round(c[-1], 2),
                "Miro_Score": miro_score, "ADX": adx,
                "RS_Alpha": rs_val, "Trend": "🟢 BULL" if c[-1] > m200 else "⚪ NEUTRAL",
                "Vol_Surge": round(vol_surge, 2), "D+": d_plus
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. UI ---
st.sidebar.title("🏹 Alpha Sniper Elite")
depth = st.sidebar.slider("Scan Depth", 5, 100, 20)

if st.sidebar.button("🚀 INITIALIZE SCAN"):
    st.session_state['results'] = run_sniper_scan(depth)

if 'results' in st.session_state:
    df = st.session_state['results']
    t1, t2, t3 = st.tabs(["🎯 MiroFish Logic", "📈 Trend Structure", "🧬 Alpha Desk"])
    
    with t1:
        st.subheader("MiroFish Momentum")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
    with t2:
        st.subheader("Trend Speedometer")
        st.dataframe(df[['Ticker', 'Trend', 'ADX', 'D+']], use_container_width=True)
    with t3:
        st.subheader("Relative Strength Alpha")
        st.caption("Score > 0 means the stock is beating the Nifty 50 over the last 3 months.")
        st.dataframe(df.sort_values("RS_Alpha", ascending=False)[['Ticker', 'RS_Alpha', 'Price']], use_container_width=True)
