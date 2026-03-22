import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. SYSTEM CONFIG & 2026 PULSE ---
st.set_page_config(page_title="Nifty Sniper Elite v10.0", layout="wide")

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
    panic_stocks = len(df[df['Z-Score'] < -2.2])
    breadth = (above_200 / total) * 100
    panic_pct = (panic_stocks / total) * 100
    
    if breadth > 60: return "🔥 BULL REGIME", "Focus on Miro Breakouts", "success"
    elif breadth < 40 and panic_pct > 15: return "😱 PANIC REGIME", "Focus on Mean Reversion", "error"
    elif breadth < 40: return "❄️ BEAR REGIME", "Capital Preservation / Defensive", "warning"
    else: return "⚖️ NEUTRAL", "Selective Sector Rotation", "info"

# --- 3. THE "UNSHRUNK" MATH ENGINE ---
def calculate_metrics(df, ticker):
    try:
        # 2026 MultiIndex Flattening
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, level=1, axis=1) if ticker in df.columns.get_level_values(1) else df.columns.get_level_values(0)

        df.columns = [str(c).capitalize() for c in df.columns]
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        if len(c) < 200: return None

        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        # ADX Calculation
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        p_chg = (c[-1] - c[-2]) / c[-2]
        
        # Miro Score & Recommendation
        miro = 2
        if vol_surge > 2.0: miro += 5
        if p_chg > 0.01: miro += 3
        reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_surge > 2.2 else "🪃 REVERSION" if z < -2.2 else "💤 NEUTRAL"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": round(adx, 1), 
                "z": round(z, 2), "vol": round(vol_surge, 2), "atr": atr.iloc[-1], "reco": reco, "miro": miro}
    except: return None

# --- 4. THE SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ESCORTS.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Deep Market Audit...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            m = calculate_metrics(raw, t)
            if m:
                all_data.append({
                    "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2), 
                    "Recommendation": m['reco'], "Miro_Score": m['miro'], "Z-Score": m['z'], 
                    "ADX Strength": m['adx'], "Vol_Surge": m['vol'], 
                    "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), 
                    "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2)
                })
        except: continue
    return pd.DataFrame(all_data)

# --- 5. INTERFACE ---
# Sidebar: Official March 22, 2026 Pulse
st.sidebar.subheader("🏦 2026 Institutional Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["India VIX", "FII Bias"], "Value": ["22.80", "🔴 SELLING (-₹7,558 Cr)"]}))
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(500)
    if not res.empty: st.session_state['v10_res'] = res

if 'v10_res' in st.session_state:
    df = st.session_state['v10_res']
    regime, advice, color = get_market_regime(df)
    st.sidebar.markdown(f"### 🌡️ Market Weather: {regime}")
    getattr(st.sidebar, color)(f"Strategy: {advice}")

    # Risk Math
    sl_mult = 3.0 if 22.80 > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # Miro Flow
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge", "Sector"]].sort_values("Miro_Score", ascending=False), hide_index=True, use_container_width=True)
    
    with tabs[1]: # Trend & ADX
        st.dataframe(df[["Ticker", "Price", "Recommendation", "ADX Strength", "MA 20", "MA 50", "MA 200"]], hide_index=True, use_container_width=True)
        
    with tabs[3]: # Earnings Front-Runner
        st.subheader("🧬 2026 Filing Audit")
        t_e = st.selectbox("Select Asset", df['Ticker'].tolist(), key="e_box")
        if st.button("🔍 Run Audit"):
            prompt = f"Today is March 22, 2026. Search and analyze Reg 30 filings for {t_e} from Jan-Mar 2026. For BIOCON, focus on the ₹4,150 Cr QIP (Jan 15), US FDA gSaxenda approval (Feb 24), and Q3 Net Profit of ₹144 Cr (up 475%)."
            with st.spinner("Auditing 2026 Filings..."):
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[4]: # Intelligence Lab
        st.subheader("🧠 2026 Strategic & Technical Council")
        t_i = st.selectbox("Select Asset", df['Ticker'].tolist(), key="i_box")
        if st.button("⚖️ Summon Council"):
            prompt = f"""
            Today is March 22, 2026. Price: {df[df['Ticker']==t_i]['Price'].values[0]}. 
            Debate {t_i} using 4 Agents:
            - BULL: Focus on 2026 catalysts (QIP deleveraging, GLP-1 rollout).
            - BEAR: Focus on FII exit (-₹7.5k Cr) and pricing pressure.
            - TECHNICAL: Analyze the horizontal box (₹360-₹392) and MA 200 test.
            - RISK: Focus on 22.80 VIX and March 31 integration deadline.
            """
            with st.spinner("Council debating..."):
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[5]: # Risk Lab
        st.dataframe(df[["Ticker", "Price", "Stop_Loss", "Qty", "ATR"]], hide_index=True, use_container_width=True)
else:
    st.info("Scanner Ready.")
