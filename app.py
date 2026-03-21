import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper v7.8", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. PERSISTENT SAVING LOGIC ---
def save_to_ledger(ticker, strategy, price, content):
    if not content or content == "":
        st.error("Nothing to save! Run the analysis first.")
        return
    
    file_path = "sniper_ledger.csv"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[timestamp, ticker, strategy, price, content]], 
                             columns=["Timestamp", "Ticker", "Strategy", "Price", "Analysis"])
    
    if not os.path.isfile(file_path):
        new_entry.to_csv(file_path, index=False)
    else:
        new_entry.to_csv(file_path, mode='a', header=False, index=False)
    st.success(f"✅ Saved {ticker} to Ledger!")

# --- 3. MATH ENGINE (ATR, ADX, Z-Score) ---
def calculate_metrics(df):
    try:
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        
        reco = "💤 NEUTRAL"
        if (c[-1]-c[-2])/c[-2] > 0.02 and vol_surge > 2.5: reco = "🚀 STRONG BUY"
        elif z < -2.2: reco = "🪃 STRONG REVERSION BUY"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": adx, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "reco": reco}
    except: return None

# --- 4. SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    n500 = pd.read_csv(url)
    symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    all_data = []
    prog = st.progress(0, text="Deep Scanning 500 Stocks...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            m = calculate_metrics(raw)
            if m:
                all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], 
                                   "Z-Score": m['z'], "Vol_Surge": m['vol_surge'], "ATR": round(m['atr'], 2),
                                   "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}", 
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2)})
        except: continue
    return pd.DataFrame(all_data)

# --- 5. INTERFACE ---
st.title("🏹 Nifty Sniper v7.8")
v_vix = st.sidebar.number_input("India VIX", value=22.50)

if st.sidebar.button("🚀 INITIALIZE GLOBAL AUDIT"):
    st.session_state['v78_results'] = run_master_scan(500)

if 'v78_results' in st.session_state:
    df = st.session_state['v78_results']
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Analysis", "🪃 Mean Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[3]: # Earnings Front-Runner
        st.subheader("🧬 Earnings Front-Runner")
        t_e = st.selectbox("Ticker for Filing Audit", df['Ticker'].tolist(), key="audit_select")
        if st.button("🔍 Run Audit"):
            with st.spinner("Searching..."):
                st.session_state['last_audit'] = client.models.generate_content(model="gemini-2.5-flash", contents=f"Search India Reg 30 filings for {t_e} (30d). Score Earnings Momentum (-10 to 10).").text
        
        if 'last_audit' in st.session_state:
            st.markdown(st.session_state['last_audit'])
            if st.button("💾 Save Audit to Ledger"):
                save_to_ledger(t_e, "Earnings Audit", df[df['Ticker']==t_e]['Price'].values[0], st.session_state['last_audit'])

    with tabs[4]: # Intelligence Lab
        st.subheader("🧠 Intelligence Lab")
        t_i = st.selectbox("Ticker for Debate", df['Ticker'].tolist(), key="debate_select")
        if st.button("⚖️ Summon Council"):
            with st.spinner("Debating..."):
                st.session_state['last_debate'] = client.models.generate_content(model="gemini-2.5-flash", contents=f"Hedge Fund Debate for {t_i}. Price: {df[df['Ticker']==t_i]['Price'].values[0]}").text
        
        if 'last_debate' in st.session_state:
            st.markdown(st.session_state['last_debate'])
            if st.button("💾 Save Debate to Ledger"):
                save_to_ledger(t_i, "Committee Debate", df[df['Ticker']==t_i]['Price'].values[0], st.session_state['last_debate'])

    with tabs[5]: # Risk & Ledger
        st.subheader("Risk Lab & Ledger")
        st.dataframe(df[['Ticker', 'Price', 'Recommendation', 'ATR']], use_container_width=True)
        if os.path.exists("sniper_ledger.csv"):
            st.download_button("📥 Download Private Ledger", data=open("sniper_ledger.csv", "rb"), file_name="nifty_sniper_ledger.csv")
