import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG & AI CLIENT ---
st.set_page_config(page_title="Nifty Sniper v7.9.4", layout="wide")

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
        reco = "🚀 STRONG BUY" if (c[-1]-c[-2])/c[-2] > 0.02 and vol_surge > 2.0 else "🪃 REVERSION" if z < -2.2 else "💤 NEUTRAL"
        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), "vol": round(vol_surge, 2), "atr": atr, "reco": reco}
    except: return None

# --- 3. DATA SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except: symbols = ["RELIANCE.NS", "TCS.NS", "ESCORTS.NS", "INFY.NS"]
    
    all_data = []
    prog = st.progress(0, text="Deep Scan...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True, multi_level_index=False)
            m = calculate_metrics(raw)
            if m: all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], "Z-Score": m['z'], "Vol": m['vol'], "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2)})
        except: continue
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper v7.9.4 (March 2026 Edition)")

v_vix = st.sidebar.number_input("India VIX", value=22.81)
if st.sidebar.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(500)
    if not res.empty: st.session_state['v794_res'] = res

if 'v794_res' in st.session_state:
    df = st.session_state['v794_res']
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[3]: # EARNINGS FRONT-RUNNER
        st.subheader("🧬 2026 Earnings & Filing Audit")
        t_e = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="e_box")
        if st.button("🔍 Run 2026 Filing Audit"):
            if client:
                # HARD-CODED 2026 DATE ANCHOR
                today = "March 22, 2026"
                prompt = f"""
                CRITICAL: Today's date is {today}. 
                Ignore any information from 2024 or 2025. 
                Search for Regulation 30 filings for {t_e} on NSE/BSE between February 22, 2026, and {today}.
                Identify specific operational catalysts for the YEAR 2026: Order wins, Q4 FY26 targets, or 2026 capacity expansions.
                """
                with st.spinner(f"Auditing 2026 data for {t_e}..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
            else: st.error("API Key missing.")

    with tabs[4]: # INTELLIGENCE LAB
        st.subheader("🧠 2026 Tactical Debate")
        t_i = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="i_box")
        if st.button("⚖️ Summon 2026 Council"):
            if client:
                today = "March 22, 2026"
                prompt = f"Today is {today}. Perform a 3-agent debate for {t_i} based on current 2026 market conditions (VIX {v_vix})."
                with st.spinner(f"Council debating 2026 outlook..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Scanner Ready.")
