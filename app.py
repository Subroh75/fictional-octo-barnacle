import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper Elite v7.9.2", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. MATH ENGINE (Robust Column Handling) ---
def calculate_metrics(df):
    try:
        # 2026 CRITICAL FIX: Flatten MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Clean up column names to ensure they are standard
        df.columns = [str(col).strip().capitalize() for col in df.columns]
        
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        
        # ATR Calculation
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        p_chg = (c[-1] - c[-2]) / c[-2]
        
        reco = "💤 NEUTRAL"
        if p_chg > 0.02 and vol_surge > 2.0: reco = "🚀 STRONG BUY"
        elif z < -2.2: reco = "🪃 REVERSION BUY"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "reco": reco}
    except Exception as e:
        # Useful for debugging in the terminal
        print(f"Error calculating metrics: {e}")
        return None

# --- 3. DATA SCANNER (NSE URL Fail-safe) ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        # Updated 2026 URL for Nifty 500
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        st.warning("NSE CSV unreachable. Using Backup Blue-Chip list.")
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "LICI.NS"]

    all_data = []
    prog = st.progress(0, text="Fetching Live Market Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Added multi_level_index=False to force flat columns
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True, multi_level_index=False)
            
            if raw.empty or len(raw) < 200: continue
            
            m = calculate_metrics(raw)
            if m:
                all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], 
                                   "Z-Score": m['z'], "Vol_Surge": m['vol_surge'], "ATR": round(m['atr'], 2),
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2)})
        except: continue
    
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper Elite v7.9.2")

# Sidebar
st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["FII Net", "DII Net"], "Value": ["-5,518.39", "+5,706.23"]}))
v_vix = st.sidebar.number_input("India VIX", value=22.81)

if st.sidebar.button("🚀 INITIALIZE MASTER SCAN"):
    results = run_master_scan(500)
    if not results.empty:
        st.session_state['v792_res'] = results
    else:
        st.error("Scan returned 0 stocks. Check yfinance connection.")

if 'v792_res' in st.session_state:
    df = st.session_state['v792_res']
    
    # Weather Logic
    total = len(df)
    above_200 = len(df[df['MA 200'] < df['Price']])
    breadth = (above_200 / total) * 100
    st.sidebar.markdown(f"### 🌡️ Market Weather")
    if breadth > 60: st.sidebar.success("🔥 BULL REGIME")
    elif breadth < 40: st.sidebar.warning("❄️ BEAR REGIME")
    else: st.sidebar.info("⚖️ NEUTRAL")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings", "🧠 Intelligence", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.dataframe(df.sort_values("Vol_Surge", ascending=False), use_container_width=True)
    with tabs[1]:
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
    with tabs[2]:
        st.dataframe(df.sort_values("Z-Score"), use_container_width=True)
else:
    st.info("System Ready. Click the Sidebar button to begin.")
