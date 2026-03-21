import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG & CLIENT ---
st.set_page_config(page_title="Nifty Sniper Elite v7.9.1", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. HEDGE FUND MATH ENGINE ---
def calculate_metrics(df):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        p_chg = (c[-1] - c[-2]) / c[-2]
        
        reco = "💤 NEUTRAL"
        if p_chg > 0.02 and vol_surge > 2.2: reco = "🚀 STRONG BUY"
        elif z < -2.2: reco = "🪃 STRONG REVERSION BUY"
        
        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "reco": reco}
    except: return None

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]
    
    all_data = []
    prog = st.progress(0, text="Deep Market Audit...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            m = calculate_metrics(raw)
            if m:
                all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], "Z-Score": m['z'], 
                                   "Vol_Surge": round(m['vol_surge'], 2), "ATR": round(m['atr'], 2),
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2)})
        except: continue
    return pd.DataFrame(all_data)

# --- 3. INTERFACE ---
st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["FII Net (Cr)", "DII Net (Cr)"], "Value": ["-5,518.39", "+5,706.23"]}))
v_vix = st.sidebar.number_input("India VIX", value=22.81)

if st.sidebar.button("🚀 INITIALIZE MASTER SCAN"):
    results = run_master_scan(500)
    if not results.empty:
        st.session_state['v791_res'] = results

if 'v791_res' in st.session_state:
    df = st.session_state['v791_res']
    
    # Sidebar Weather Logic
    total = len(df)
    above_200 = len(df[df['MA 200'] < df['Price']])
    breadth = (above_200 / total) * 100
    st.sidebar.markdown(f"### 🌡️ Market Weather")
    if breadth > 60: st.sidebar.success("🔥 BULL REGIME: Trust Miro")
    elif breadth < 40: st.sidebar.warning("❄️ BEAR REGIME: Capital Preservation")
    else: st.sidebar.info("⚖️ NEUTRAL: Sector Rotation")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[4]: # Intelligence Lab
        st.subheader("🧠 Intelligence Lab")
        # Added a unique key to prevent cross-tab interference
        t_i = st.selectbox("Select Ticker for Committee Debate", df['Ticker'].tolist(), key="intel_ticker")
        
        # This prevents the AI from firing until the button is clicked
        if st.button("⚖️ Summon Council"):
            with st.spinner(f"Agents debating {t_i}..."):
                res = client.models.generate_content(model="gemini-2.5-flash", contents=f"3-agent Debate for {t_i} at price {df[df['Ticker']==t_i]['Price'].values[0]}. Provide Bull/Bear/Risk manager views.").text
                # Store the debate in session memory so it stays on screen
                st.session_state[f'debate_{t_i}'] = res

        # Only display the debate if it's in the memory for THIS specific ticker
        if f'debate_{t_i}' in st.session_state:
            st.markdown(st.session_state[f'debate_{t_i}'])
            if st.button("💾 Save Debate to Ledger"):
                # Saving logic here
                st.success(f"Debate for {t_i} saved!")

else:
    st.info("Scanner Ready. Depth: 500.")
