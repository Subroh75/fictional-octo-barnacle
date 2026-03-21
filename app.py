import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper v7.8.1", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE PRIVATE LEDGER ---
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
    st.success(f"✅ Saved {ticker} to Ledger!")

# --- 3. MATH ENGINE (Flattened for 2026 yfinance) ---
def calculate_metrics(df):
    try:
        # CRITICAL FIX: Ensure columns are flat (no MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        
        reco = "💤 NEUTRAL"
        if (c[-1]-c[-2])/c[-2] > 0.02 and vol_surge > 2.0: reco = "🚀 STRONG BUY"
        elif z < -2.2: reco = "🪃 STRONG REVERSION BUY"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "reco": reco}
    except Exception as e:
        return None

# --- 4. SCANNER (With NSE Website Fail-Safe) ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    # Try fetching from NSE, use backup list if it fails
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        st.warning("NSE List unreachable. Using Blue-Chip backup list.")
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS"]

    all_data = []
    prog = st.progress(0, text="Fetching Live Market Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Download with auto_adjust to keep columns clean
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty: continue
            
            m = calculate_metrics(raw)
            if m:
                all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], 
                                   "Z-Score": m['z'], "Vol_Surge": m['vol_surge'], "ATR": round(m['atr'], 2),
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2)})
        except: continue
    
    if not all_data:
        st.error("No data could be fetched. Check your internet or yfinance version.")
    return pd.DataFrame(all_data)

# --- 5. INTERFACE ---
st.title("🏹 Nifty Sniper v7.8.1")
v_vix = st.sidebar.number_input("India VIX", value=22.50)

if st.sidebar.button("🚀 INITIALIZE SCAN"):
    results = run_master_scan(500)
    if not results.empty:
        st.session_state['v781_results'] = results

if 'v781_results' in st.session_state:
    df = st.session_state['v781_results']
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings", "🧠 Intelligence", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.subheader("Miro Flow (Momentum)")
        st.dataframe(df.sort_values("Vol_Surge", ascending=False), use_container_width=True)
    
    with tabs[1]:
        st.subheader("Trend Ribbon")
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
        
    with tabs[2]:
        st.subheader("Mean Reversion (Z-Score)")
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Recommendation', 'Z-Score']], use_container_width=True)

    with tabs[4]: # Intelligence Lab
        st.subheader("🧠 Intelligence Lab")
        t_i = st.selectbox("Select Ticker", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                with st.spinner("Analyzing..."):
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Debate {t_i} at price {df[df['Ticker']==t_i]['Price'].values[0]}").text
                    st.session_state['current_debate'] = res
                    st.markdown(res)
            else: st.error("API Key missing.")
        
        if 'current_debate' in st.session_state:
            if st.button("💾 Save to Ledger"):
                save_to_ledger(t_i, "Debate", df[df['Ticker']==t_i]['Price'].values[0], st.session_state['current_debate'])
else:
    st.info("Scanner Ready. Click 'INITIALIZE SCAN' in sidebar.")
