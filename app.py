import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper Institutional AI", layout="wide")

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

# --- 2. DATA ENGINE (THE AGGRESSIVE FIX) ---
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
    prog = st.progress(0, text="Fetching Clean Market Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Fetch 2 years to ensure MA200 has enough data
            raw = yf.download(t, period="2y", progress=False)
            if raw.empty or len(raw) < 200: continue
            
            # --- THE FIX: MANUALLY EXTRACTING ARRAYS ---
            # This ignores all MultiIndex/Header issues by going straight to the numbers
            close_prices = raw['Close'].values.flatten()
            high_prices = raw['High'].values.flatten()
            low_prices = raw['Low'].values.flatten()
            volumes = raw['Volume'].values.flatten()

            # Create a clean temporary Series for calculations
            s_close = pd.Series(close_prices)
            
            cp = float(s_close.iloc[-1])
            m20 = float(s_close.tail(20).mean())
            m50 = float(s_close.tail(50).mean())
            m200 = float(s_close.tail(200).mean())
            
            dist_ma20 = ((cp - m20) / m20) * 100
            
            # Volume Surge
            avg_vol = float(pd.Series(volumes).tail(20).mean())
            vol_surge = float(volumes[-1]) / avg_vol if avg_vol != 0 else 0

            # ATR Calculation
            df_temp = pd.DataFrame({'H': high_prices, 'L': low_prices, 'C': close_prices})
            df_temp['tr'] = np.maximum(df_temp['H']-df_temp['L'], 
                             np.maximum(np.abs(df_temp['H']-df_temp['C'].shift(1)), 
                                        np.abs(df_temp['L']-df_temp['C'].shift(1))))
            atr = float(df_temp['tr'].tail(14).mean())

            score = 0
            if cp > m20 > m50: score += 2
            if cp > m200: score += 3
            if vol_surge > 1.8: score += 5

            p_change = (cp - s_close.iloc[-2]) / s_close.iloc[-2]
            action = "🔥 AGGRESSIVE BUY" if (p_change > 0 and vol_surge > 1.8) else "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA20": round(m20, 2), "MA50": round(m50, 2), "MA200": round(m200, 2),
                "Dist_MA20": f"{round(dist_ma20, 2)}%", "Score": score, 
                "Vol_Surge": round(vol_surge, 2), "Action": action, "ATR": round(atr, 2),
                "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL"
            })
        except Exception as e:
            continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI ---
st.sidebar.title("🏹 Nifty Sniper AI")
v_vix = st.sidebar.number_input("India VIX", value=21.84)
v_depth = st.sidebar.slider("Depth", 50, 500, 100)
v_risk = st.sidebar.number_input("Risk (INR)", value=5000)

if st.sidebar.button("🚀 START AI SCAN"):
    res = run_full_scan(v_depth)
    if not res.empty:
        sl_m = 3.0 if v_vix > 20 else 2.0
        res['Stop_Loss'] = res['Price'] - (sl_m * res['ATR'])
        res['Qty'] = (v_risk / (res['Price'] - res['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = res

if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    t1, t2, t3 = st.tabs(["🎯 Leaderboard", "📈 Trends & MAs", "🧠 Risk Lab"])
    
    with t1: st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    with t2:
        st.subheader("Structural Trend Analysis")
        # Explicitly showing the new MA columns
        st.dataframe(df[['Ticker', 'Price', 'MA20', 'MA50', 'MA200', 'Dist_MA20', 'Trend']], use_container_width=True)
    with t3:
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'Action']], use_container_width=True)
else:
    st.info("System Ready. Click 'START AI SCAN'.")
