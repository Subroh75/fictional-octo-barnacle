import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import requests
import io
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper Elite v16.5", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

def highlight_reco(val):
    if not isinstance(val, str): return ''
    color = '#2ecc71' if 'BUY' in val else '#e74c3c' if 'SELL' in val else '#f1c40f'
    return f'background-color: {color}; color: black; font-weight: bold'

# --- 2. LIVE NIFTY 500 FETCH ---
@st.cache_data(ttl=86400)
def get_live_nifty_500():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        response = requests.get(url, headers=headers, timeout=10)
        df_n500 = pd.read_csv(io.StringIO(response.text))
        symbols = [s + ".NS" for s in df_n500['Symbol'].tolist()]
        sectors = dict(zip(df_n500['Symbol'] + ".NS", df_n500['Industry']))
        return symbols, sectors
    except:
        # Emergency Core Watchlist
        core = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATASTEEL.NS", "ADANIPOWER.NS"]
        return core, {s: "Core Market" for s in core}

# --- 3. THE CHUNKED MATH ENGINE ---
def process_batch(raw_data, symbols, sectors):
    batch_results = []
    for t in symbols:
        try:
            if t not in raw_data.columns.get_level_values(1): continue
            df = raw_data.xs(t, level=1, axis=1).copy().dropna()
            if len(df) < 100: continue
            
            df.columns = [str(c).capitalize() for c in df.columns]
            c, h, l, v = df['Close'].values, df['High'].values, df['Low'].values, df['Volume'].values
            
            m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
            tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            z = (c[-1] - m20) / np.std(c[-20:])
            vol_s = v[-1] / np.mean(v[-20:])
            p_chg = (c[-1] - c[-2]) / c[-2]
            
            miro = 2 + (5 if vol_s > 2.0 else 0) + (3 if p_chg > 0.01 else 0)
            reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_s > 2.2 else "🛑 STRONG SELL" if p_chg < -0.02 and vol_s > 2.2 else "🪃 REVERSION BUY" if z < -2.2 else "💤 NEUTRAL"
            
            batch_results.append({
                "Ticker": t, "Sector": sectors.get(t, "Misc"), "Price": round(c[-1], 2),
                "Recommendation": reco, "Miro_Score": miro, "Z-Score": round(z, 2),
                "MA 50": round(m50, 2), "MA 200": round(m200, 2), "Vol_Surge": round(vol_s, 2), "ATR": round(atr, 2)
            })
        except: continue
    return batch_results

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v16.5")
st.sidebar.info("System optimized for April 2026 Batch Audits.")
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)

if st.sidebar.button("🚀 EXECUTE FULL 500 AUDIT"):
    symbols, sectors = get_live_nifty_500()
    target_symbols = symbols[:scan_depth]
    all_final_data = []
    
    # CHUNKING LOGIC: Process 50 stocks at a time to bypass Yahoo rate limits
    chunk_size = 50
    chunks = [target_symbols[i:i + chunk_size] for i in range(0, len(target_symbols), chunk_size)]
    
    prog = st.progress(0, text="Initializing Institutional Data Bridge...")
    for idx, chunk in enumerate(chunks):
        prog.progress((idx + 1) / len(chunks), text=f"Downloading Batch {idx+1}/{len(chunks)}...")
        try:
            raw = yf.download(chunk, period="1y", group_by='column', auto_adjust=True, progress=False, threads=True)
            batch_data = process_batch(raw, chunk, sectors)
            all_final_data.extend(batch_data)
            time.sleep(1) # Small pause to stay under the radar
        except: continue
        
    if all_final_data:
        st.session_state['v165_res'] = pd.DataFrame(all_final_data)

if 'v165_res' in st.session_state:
    df = st.session_state['v165_res']
    
    # Side Heatmap
    breadth = (len(df[df['MA 200'] < df['Price']]) / len(df)) * 100
    st.sidebar.subheader("🌡️ Market Heatmap")
    if breadth > 60: st.sidebar.success(f"🔥 BULLISH ({round(breadth,1)}%)")
    elif breadth < 40: st.sidebar.error(f"❄️ BEARISH ({round(breadth,1)}%)")
    else: st.sidebar.warning(f"⚖️ NEUTRAL ({round(breadth,1)}%)")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & MA 50", "🪃 Reversion", "💎 Weekly Sniper", "🧬 Filing Audit", "🧠 Intelligence Lab"])
    
    with tabs[0]:
        st.subheader("🎯 Miro Momentum Leaderboard")
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge"]].sort_values("Miro_Score", ascending=False).style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
        with st.expander("📘 TACTICAL LOGIC"): st.write("Miro Score (8-10): Institutional volume alignment with price action.")

    with tabs[1]:
        st.subheader("📈 Structural Trend Analysis")
        st.dataframe(df[["Ticker", "Price", "Recommendation", "MA 50", "MA 200"]].style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)

    with tabs[4]: # FILING AUDIT
        t_f = st.selectbox("Select Asset", df['Ticker'].tolist(), key="f_box")
        if st.button("🔍 Run Forensic Audit"):
            if client:
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {t_f} for Sentiment Decay in April 2026.").text)

    with tabs[5]: # INTELLIGENCE
        t_i = st.selectbox("Select Asset", df['Ticker'].tolist(), key="i_box")
        if st.button("⚖️ Summon Council"):
            if client:
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=f"4-agent debate for {t_i} on April 1, 2026.").text)
else:
    st.info("Scanner Ready. Execute Audit to see all 500 stocks.")
