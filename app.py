import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import requests
import io
import time
from datetime import datetime

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper Elite v20.0", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. VISUAL STYLING ENGINE ---
def highlight_reco(val):
    if not isinstance(val, str): return ''
    color = '#2ecc71' if 'BUY' in val else '#e74c3c' if 'SELL' in val else '#f1c40f'
    return f'background-color: {color}; color: black; font-weight: bold'

# --- 3. DATA ACQUISITION (Live Nifty 500) ---
@st.cache_data(ttl=86400)
def get_live_nifty_500():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        response = requests.get(url, headers=headers)
        df_n500 = pd.read_csv(io.StringIO(response.text))
        symbols = [s + ".NS" for s in df_n500['Symbol'].tolist()]
        sectors = dict(zip(df_n500['Symbol'] + ".NS", df_n500['Industry']))
        return symbols, sectors
    except:
        core = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ADANIPOWER.NS"]
        return core, {s: "Core Market" for s in core}

# --- 4. THE UNSHRUNK MATH ENGINE ---
def process_batch_data(raw_data, symbols, sectors):
    all_results = []
    for t in symbols:
        try:
            if t not in raw_data.columns.get_level_values(1): continue
            df = raw_data.xs(t, level=1, axis=1).copy().dropna()
            if len(df) < 200: continue
            
            df.columns = [str(c).capitalize() for c in df.columns]
            c, h, l, v = df['Close'].values, df['High'].values, df['Low'].values, df['Volume'].values
            
            # Indicators
            m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
            tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            z = (c[-1] - m20) / np.std(c[-20:])
            vol_s = v[-1] / np.mean(v[-20:])
            p_chg = (c[-1] - c[-2]) / c[-2]
            
            # Miro Logic (Patented - Confidential)
            miro = 2 + (5 if vol_s > 2.0 else 0) + (3 if p_chg > 0.01 else 0)
            
            # Recommendations
            reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_s > 2.2 else "🛑 STRONG SELL" if p_chg < -0.02 and vol_s > 2.2 else "🪃 REVERSION BUY" if z < -2.2 else "💤 NEUTRAL"
            
            all_results.append({
                "Ticker": t, "Sector": sectors.get(t, "Misc"), "Price": round(c[-1], 2),
                "Recommendation": reco, "Miro_Score": miro, "Z-Score": round(z, 2),
                "MA 50": round(m50, 2), "MA 200": round(m200, 2), "Vol_Surge": round(vol_s, 2), "ATR": round(atr, 2)
            })
        except: continue
    return pd.DataFrame(all_results)

# --- 5. INTERFACE & SIDEBAR ---
st.sidebar.title("🏹 Nifty Sniper v20.0")
st.sidebar.subheader("🏦 Mar 22, 2026 Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["India VIX", "FII Net"], "Value": ["22.81", "🔴 -5,518.40 Cr"]}))
v_risk = st.sidebar.number_input("Risk INR", value=5000)
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)

if st.sidebar.button("🚀 EXECUTE FULL MARKET AUDIT"):
    symbols, sectors = get_live_nifty_500()
    target_symbols = symbols[:scan_depth]
    all_final_data = []
    chunk_size = 50
    chunks = [target_symbols[i:i + chunk_size] for i in range(0, len(target_symbols), chunk_size)]
    
    prog = st.progress(0, text="Establishing Institutional Data Bridge...")
    for idx, chunk in enumerate(chunks):
        prog.progress((idx + 1) / len(chunks), text=f"Downloading Batch {idx+1}/{len(chunks)}...")
        raw = yf.download(chunk, period="2y", group_by='column', auto_adjust=True, progress=False)
        batch_results = process_batch_data(raw, chunk, sectors)
        all_final_data.append(batch_results)
        time.sleep(1)
        
    if all_final_data:
        st.session_state['v20_res'] = pd.concat(all_final_data)

# --- 6. TABS & FORENSICS ---
if 'v20_res' in st.session_state:
    df = st.session_state['v20_res']
    
    # Side Heatmap
    above_200 = len(df[df['MA 200'] < df['Price']])
    breadth = (above_200 / len(df)) * 100
    st.sidebar.subheader("🌡️ Market Heatmap")
    if breadth > 60: st.sidebar.success(f"🔥 BULLISH ({round(breadth,1)}%)")
    elif breadth < 40: st.sidebar.error(f"❄️ BEARISH ({round(breadth,1)}%)")
    else: st.sidebar.warning(f"⚖️ NEUTRAL ({round(breadth,1)}%)")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & MA 50", "🪃 Reversion", "💎 Weekly Sniper", "🧬 Filing Audit", "🧠 Intelligence Lab"])
    
    with tabs[0]: # Miro Flow
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge"]].sort_values("Miro_Score", ascending=False).style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
        with st.expander("📘 TACTICAL LOGIC"): st.write("Miro Logic: Combining institutional volume surges with price breakouts.")

    with tabs[1]: # Trend
        st.dataframe(df[["Ticker", "Price", "Recommendation", "MA 50", "MA 200"]].style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
        with st.expander("📘 TACTICAL LOGIC"): st.write("Golden Alignment: Buy when Price > MA 50 > MA 200.")

    with tabs[4]: # Filing Audit (FORENSIC TRUTH-METER)
        t_f = st.selectbox("Select Asset for Truth-Meter Audit", df['Ticker'].tolist())
        if st.button("🔍 Run Forensic Audit"):
            if client:
                prompt = f"Today is March 22, 2026. Perform a forensic linguistic audit for {t_f}. Look for 'Sentiment Decay' vs 'Stable Guidance' in recent filings."
                with st.spinner("Analyzing Management Tone..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[5]: # Intelligence Lab
        t_i = st.selectbox("Select Asset for 4-Agent Debate", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"Perform a 4-agent debate for {t_i} on March 22, 2026. Bull, Bear, Quant, and Risk agents."
                with st.spinner("Council Debating..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Scanner Ready. Click 'EXECUTE FULL MARKET AUDIT' to start.")
