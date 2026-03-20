import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper Dual-Engine", layout="wide")
st.error("🚀 DUAL-ENGINE ACTIVE: [MiroFish Sniper] + [MA Trend Ribbon]")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()

# --- 2. DATA ENGINE (SEPARATED LOGIC) ---
def run_dual_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS"]

    all_data = []
    prog = st.progress(0, text="Engaging Dual-Engine Analysis...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df_raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if df_raw.empty or len(df_raw) < 200: continue
            
            # Flatten 
            df = pd.DataFrame(index=df_raw.index)
            df['Close'] = df_raw['Close'].values.flatten()
            df['High'] = df_raw['High'].values.flatten()
            df['Low'] = df_raw['Low'].values.flatten()
            df['Volume'] = df_raw['Volume'].values.flatten()

            # --- ENGINE A: MIROFISH (Momentum & Volatility) ---
            cp = float(df['Close'].iloc[-1])
            vol_surge = float(df['Volume'].iloc[-1]) / df['Volume'].rolling(20).mean().iloc[-1]
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            
            miro_score = 0
            if vol_surge > 1.8: miro_score += 5
            if (cp - df['Close'].iloc[-2]) / df['Close'].iloc[-2] > 0.02: miro_score += 3
            if vol_surge > 3.0: miro_score += 2 # Super Surge

            # --- ENGINE B: MA TREND RIBBON (Structure) ---
            m20 = df['Close'].rolling(20).mean().iloc[-1]
            m50 = df['Close'].rolling(50).mean().iloc[-1]
            m200 = df['Close'].rolling(200).mean().iloc[-1]
            
            trend_state = "🔴 BEARISH"
            if cp > m200: trend_state = "🟡 NEUTRAL (Above 200)"
            if cp > m50 > m200: trend_state = "🔵 RECOVERING"
            if cp > m20 > m50 > m200: trend_state = "🟢 FULL BULL"

            # --- ENGINE C: ADX (Strength) ---
            adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
            adx_val = adx_df['ADX_14'].iloc[-1]

            all_data.append({
                "Ticker": t,
                "Price": round(cp, 2),
                # MiroFish Data
                "Miro_Score": miro_score,
                "Vol_Surge": round(vol_surge, 2),
                # Trend Data
                "Trend": trend_state,
                "ADX": round(adx_val, 1),
                "MA 20": round(m20, 2),
                "MA 50": round(m50, 2),
                "MA 200": round(m200, 2),
                "ATR": round(atr, 2)
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Dual Sniper")
depth = st.sidebar.slider("Scan Depth", 10, 500, 50)

if st.sidebar.button("🚀 INITIALIZE DUAL SCAN"):
    st.cache_data.clear()
    res = run_dual_scan(depth)
    if not res.empty:
        st.session_state['dual_results'] = res

if 'dual_results' in st.session_state:
    df = st.session_state['dual_results']
    
    # SEPARATED DASHBOARD
    t1, t2, t3 = st.tabs(["🔥 MiroFish Hunter", "📈 MA Trend Ribbon", "🧠 Strategic Sync"])
    
    with t1:
        st.subheader("MiroFish Momentum Leaderboard")
        st.caption("Focus: Volume Surges and Short-term Explosiveness")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
        
    with t2:
        st.subheader("Structural Trend Ribbon")
        st.caption("Focus: 20/50/200 MA Alignment and Trend Strength (ADX)")
        st.dataframe(df[['Ticker', 'Trend', 'ADX', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
        
    with t3:
        st.subheader("Strategic Synchronization")
        # Logic to find where both agree
        high_confluence = df[(df['Miro_Score'] >= 8) & (df['Trend'] == "🟢 FULL BULL")]
        if not high_confluence.empty:
            st.success(f"Found {len(high_confluence)} Stocks with 'Full Confluence' (Momentum + Trend)")
            st.dataframe(high_confluence[['Ticker', 'Price', 'Miro_Score', 'Trend', 'ADX']], use_container_width=True)
        else:
            st.warning("No stocks currently meet both MiroFish and Full Bull Trend criteria.")

else:
    st.info("Dual Engine Ready. Run scan to see results.")
