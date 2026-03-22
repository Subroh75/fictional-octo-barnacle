import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG & AI CLIENT ---
st.set_page_config(page_title="Nifty Sniper Elite v7.9.7", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE MARKET WEATHER STATION (Regime Logic) ---
def get_market_regime(df):
    if df.empty: return "📡 OFFLINE", "Initialize Scan", "info"
    total = len(df)
    above_200 = len(df[df['MA 200'] < df['Price']])
    panic_stocks = len(df[df['Z-Score'] < -2.0])
    breadth = (above_200 / total) * 100
    panic = (panic_stocks / total) * 100
    
    if breadth > 60: return "🔥 BULL REGIME", "Trust Breakouts (Miro Flow)", "success"
    elif breadth < 40 and panic > 15: return "😱 PANIC REGIME", "Trust Reversions (Deep Value)", "error"
    elif breadth < 40: return "❄️ BEAR REGIME", "Capital Preservation: Cash is King", "warning"
    else: return "⚖️ NEUTRAL", "Selective Trading: Sector Rotation", "info"

# --- 3. HEDGE FUND MATH ENGINE ---
def calculate_metrics(df, ticker):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, level=1, axis=1)
            else:
                df.columns = df.columns.get_level_values(0)

        df.columns = [str(c).capitalize() for c in df.columns]
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        if len(c) < 200: return None

        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        p_chg = (c[-1] - c[-2]) / c[-2]
        
        reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_surge > 2.2 else "🪃 REVERSION BUY" if z < -2.2 else "💤 NEUTRAL"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), 
                "vol": round(vol_surge, 2), "atr": atr, "reco": reco}
    except: return None

# --- 4. DATA SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ESCORTS.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Deep Market Audit...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            m = calculate_metrics(raw, t)
            if m:
                all_data.append({"Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2), 
                                   "Recommendation": m['reco'], "Z-Score": m['z'], "Vol_Surge": m['vol'], 
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2)})
        except: continue
    return pd.DataFrame(all_data)

# --- 5. INTERFACE ---
st.title("🏹 Nifty Sniper Elite v7.9.7")

# Sidebar: Institutional Context
st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["FII Net (Cr)", "DII Net (Cr)"], "Value": ["-5,518.39", "+5,706.23"]}))
v_vix = st.sidebar.number_input("India VIX", value=22.81)
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(500)
    if not res.empty: st.session_state['v797_res'] = res

if 'v797_res' in st.session_state:
    df = st.session_state['v797_res']
    
    # Sidebar Weather logic
    regime, advice, color = get_market_regime(df)
    st.sidebar.markdown(f"### 🌡️ Market Weather: {regime}")
    getattr(st.sidebar, color)(f"Strategy: {advice}")

    # Risk Calculation
    sl_mult = 3.0 if v_vix > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # Miro Flow
        st.subheader("Miro Flow (Momentum Leaderboard)")
        miro_cols = ["Ticker", "Price", "Recommendation", "Vol_Surge", "Sector"]
        st.dataframe(df[miro_cols].sort_values("Vol_Surge", ascending=False), hide_index=True, use_container_width=True)
    
    with tabs[1]: # Trend
        st.subheader("Structural Trend Analysis")
        trend_cols = ["Ticker", "Price", "MA 20", "MA 50", "MA 200"]
        st.dataframe(df[trend_cols], hide_index=True, use_container_width=True)
        
    with tabs[2]: # Reversion
        st.subheader("Statistical Mean Reversion")
        rev_cols = ["Ticker", "Price", "Recommendation", "Z-Score"]
        st.dataframe(df[rev_cols].sort_values("Z-Score"), hide_index=True, use_container_width=True)

    with tabs[3]: # Earnings Front-Runner
        st.subheader("🧬 2026 Earnings & Filing Audit")
        t_e = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="e_box")
        if st.button("🔍 Run 2026 Filing Audit"):
            if client:
                with st.spinner("Analyzing 2026 filings..."):
                    prompt = f"Today is {datetime.now().strftime('%B %d, %Y')}. Search Reg 30 filings for {t_e} from last 30 days. Identify 2026 operational catalysts."
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[4]: # Intelligence Lab
        st.subheader("🧠 2026 Tactical Debate")
        t_i = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="i_box")
        if st.button("⚖️ Summon 2026 Council"):
            if client:
                with st.spinner("Council debating 2026 outlook..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=f"3-agent 2026 Debate for {t_i}.").text)

    with tabs[5]: # Risk Lab
        st.subheader("Institutional Risk Management")
        risk_cols = ["Ticker", "Price", "Stop_Loss", "Qty", "ATR"]
        st.dataframe(df[risk_cols], hide_index=True, use_container_width=True)
else:
    st.info("Scanner Ready. Click 'EXECUTE GLOBAL SCAN' in the sidebar.")
