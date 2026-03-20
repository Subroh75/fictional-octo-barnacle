import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- 1. SYSTEM SETTINGS ---
st.set_page_config(page_title="Nifty Sniper Stable", layout="wide")
st.error("🔄 SYSTEM RESTORED: Stable Build Active")

# --- 2. THE STABLE DATA ENGINE ---
def run_stable_scan(limit):
    # Fallback symbols if NSE link fails
    symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS", "3MINDIA.NS", "ABB.NS", "FLUOROCHEM.NS"]
    
    all_data = []
    prog = st.progress(0, text="Restoring Data Flow...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False, auto_adjust=True)
            if df.empty or len(df) < 50: continue
            
            # Standardizing Data (Fixing the MultiIndex/NaN issues)
            close_vals = df['Close'].values.flatten()
            vol_vals = df['Volume'].values.flatten()
            
            cp = float(close_vals[-1])
            prev_cp = float(close_vals[-2])
            
            # --- MIROFISH LOGIC (Volume & Momentum) ---
            avg_vol = np.mean(vol_vals[-20:])
            vol_surge = vol_vals[-1] / avg_vol if avg_vol > 0 else 0
            
            miro_score = 0
            if vol_surge > 1.8: miro_score += 5
            if cp > prev_cp: miro_score += 2
            
            # --- TREND LOGIC (Moving Averages) ---
            m20 = np.mean(close_vals[-20:])
            m200 = np.mean(close_vals[-200:]) if len(close_vals) >= 200 else np.mean(close_vals)
            dist_ma20 = ((cp - m20) / m20) * 100
            
            all_data.append({
                "Ticker": t,
                "Price": round(cp, 2),
                "Miro_Score": miro_score,
                "Vol_Surge": round(vol_surge, 2),
                "MA 20": round(m20, 2),
                "MA 200": round(m200, 2),
                "Dist_MA20 %": f"{round(dist_ma20, 2)}%",
                "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL"
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper Stable")
depth = st.sidebar.slider("Scan Depth", 5, 50, 20)

if st.sidebar.button("🚀 START SCAN"):
    # Clear old session data
    for key in st.session_state.keys():
        del st.session_state[key]
    
    res = run_stable_scan(depth)
    if not res.empty:
        st.session_state['stable_results'] = res

if 'stable_results' in st.session_state:
    df = st.session_state['stable_results']
    
    t1, t2 = st.tabs(["🎯 MiroFish Leaderboard", "📈 Trend Analysis"])
    
    with t1:
        st.subheader("MiroFish Momentum")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
        
    with t2:
        st.subheader("Structural Trends")
        st.dataframe(df[['Ticker', 'Trend', 'MA 20', 'MA 200', 'Dist_MA20 %']], use_container_width=True)
else:
    st.info("System Reset. Click 'START SCAN' to begin.")
