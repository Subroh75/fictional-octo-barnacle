import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG & SYSTEM MEMORY ---
st.set_page_config(page_title="Nifty Sniper Elite v7.9", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            # 2026 New Client Syntax
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. LEDGER (SAVE) LOGIC ---
def save_to_ledger(ticker, strategy, price, content):
    if not content: return
    file_path = "sniper_ledger.csv"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[timestamp, ticker, strategy, price, content]], 
                             columns=["Timestamp", "Ticker", "Strategy", "Price", "Analysis"])
    if not os.path.isfile(file_path):
        new_entry.to_csv(file_path, index=False)
    else:
        new_entry.to_csv(file_path, mode='a', header=False, index=False)
    st.success(f"✅ Analysis for {ticker} saved to Ledger.")

# --- 3. THE WEATHER STATION (REGIME FILTER) ---
def get_market_regime(df):
    if df.empty: return "📡 WAITING", "Run Scan", "info"
    total = len(df)
    above_200 = len(df[df['MA 200'] < df['Price']])
    panic_stocks = len(df[df['Z-Score'] < -2.0])
    breadth = (above_200 / total) * 100
    panic = (panic_stocks / total) * 100
    
    if breadth > 60: return "🔥 BULL REGIME", "Trust Breakouts (Miro)", "success"
    elif breadth < 40 and panic > 15: return "😱 PANIC REGIME", "Trust Reversions (Deep Value)", "error"
    elif breadth < 40: return "❄️ BEAR REGIME", "Cash is King / Preservation", "warning"
    else: return "⚖️ NEUTRAL", "Selective: Sector Rotation", "info"

# --- 4. HEDGE FUND MATH ---
def calculate_metrics(df):
    try:
        # 2026 YFinance MultiIndex Flattening
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
        
        # Recommendations
        reco = "💤 NEUTRAL"
        if p_chg > 0.02 and vol_surge > 2.2: reco = "🚀 STRONG BUY"
        elif z < -2.2: reco = "🪃 STRONG REVERSION BUY"
        elif p_chg < -0.02 and vol_surge > 2.2: reco = "🛑 STRONG SELL"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "reco": reco}
    except: return None

# --- 5. THE SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS"]
    
    all_data = []
    prog = st.progress(0, text="Deep Scanning Nifty 500...")
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

# --- 6. INTERFACE ---

# Sidebar: Institutional Context (Live March 22, 2026 Data)
st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(pd.DataFrame({
    "Metric": ["FII Net (Cr)", "DII Net (Cr)", "India VIX"],
    "Value": ["-5,518.39", "+5,706.23", "22.81"]
}))

v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 INITIALIZE MASTER SCAN"):
    results = run_master_scan(500)
    if not results.empty:
        st.session_state['v79_res'] = results

if 'v79_res' in st.session_state:
    df = st.session_state['v79_res']
    
    # Sidebar Weather Details
    regime, advice, color = get_market_regime(df)
    st.sidebar.markdown(f"### 🌡️ Market Weather: {regime}")
    getattr(st.sidebar, color)(f"Strategy: {advice}")

    # Risk Calculation
    sl_mult = 3.0 if 22.81 > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # Miro
        st.dataframe(df.sort_values("Vol_Surge", ascending=False)[['Ticker', 'Price', 'Recommendation', 'Vol_Surge']], use_container_width=True)
    with tabs[1]: # Trend
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
    with tabs[2]: # Reversion
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Recommendation', 'Z-Score']], use_container_width=True)
    with tabs[3]: # Earnings
        st.subheader("🧬 Earnings Front-Runner (Filing Scan)")
        t_e = st.selectbox("Ticker for Filing Scan", df['Ticker'].tolist())
        if st.button("🔍 Run Fundamental Audit"):
            with st.spinner("AI searching Reg 30 filings..."):
                res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Search recent India Reg 30 filings for {t_e} (30d). Identify catalysts like expansion or order wins.").text
                st.session_state['last_audit'] = res
        if 'last_audit' in st.session_state:
            st.markdown(st.session_state['last_audit'])
            if st.button("💾 Save Audit to Ledger"): save_to_ledger(t_e, "Audit", df[df['Ticker']==t_e]['Price'].values[0], st.session_state['last_audit'])
    with tabs[4]: # Intelligence
        st.subheader("🧠 Intelligence Lab (Tactical Debate)")
        t_i = st.selectbox("Ticker for Debate", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            with st.spinner("Agents debating..."):
                res = client.models.generate_content(model="gemini-2.5-flash", contents=f"3-agent Debate for {t_i}. Provide Bull/Bear/Risk manager views.").text
                st.session_state['last_debate'] = res
        if 'last_debate' in st.session_state:
            st.markdown(st.session_state['last_debate'])
            if st.button("💾 Save Debate to Ledger"): save_to_ledger(t_i, "Debate", df[df['Ticker']==t_i]['Price'].values[0], st.session_state['last_debate'])
    with tabs[5]: # Risk & Ledger
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
        if os.path.exists("sniper_ledger.csv"):
            st.download_button("📥 Download Ledger", data=open("sniper_ledger.csv", "rb"), file_name="nifty_sniper_ledger.csv")
else:
    st.info("System Ready. Depth: 500. Weather Station offline until Scan.")
