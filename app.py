import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import requests
import io

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper Elite v16.3", layout="wide")

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
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        response = requests.get(url, headers=headers)
        df_n500 = pd.read_csv(io.StringIO(response.text))
        symbols = [s + ".NS" for s in df_n500['Symbol'].tolist()]
        sectors = dict(zip(df_n500['Symbol'] + ".NS", df_n500['Industry']))
        return symbols, sectors
    except:
        core = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
        return core, {s: "Core" for s in core}

# --- 3. THE BATCH MATH ENGINE ---
def process_batch_data(raw_data, symbols, sectors):
    all_results = []
    for t in symbols:
        try:
            # Surgical extraction from MultiIndex
            df = raw_data.xs(t, level=1, axis=1).copy()
            df.columns = [str(c).capitalize() for c in df.columns]
            df = df.dropna()
            
            if len(df) < 200: continue
            
            c, h, l, v = df['Close'].values, df['High'].values, df['Low'].values, df['Volume'].values
            m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
            
            # ADX Calculation
            tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            z = (c[-1] - m20) / np.std(c[-20:])
            vol_s = v[-1] / np.mean(v[-20:])
            p_chg = (c[-1] - c[-2]) / c[-2]
            
            miro = 2 + (5 if vol_s > 2.0 else 0) + (3 if p_chg > 0.01 else 0)
            reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_s > 2.2 else "🛑 STRONG SELL" if p_chg < -0.02 and vol_s > 2.2 else "🪃 REVERSION BUY" if z < -2.2 else "💤 NEUTRAL"
            
            all_results.append({
                "Ticker": t, "Sector": sectors.get(t, "Misc"), "Price": round(c[-1], 2),
                "Recommendation": reco, "Miro_Score": miro, "Z-Score": round(z, 2),
                "MA 50": round(m50, 2), "MA 200": round(m200, 2), "Vol_Surge": round(vol_s, 2), "ATR": round(atr, 2)
            })
        except: continue
    return pd.DataFrame(all_results)

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v16.3")
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)

if st.sidebar.button("🚀 EXECUTE BATCH SCAN"):
    symbols, sectors = get_live_nifty_500()
    target_symbols = symbols[:scan_depth]
    
    with st.spinner(f"Requesting Institutional Data for {len(target_symbols)} stocks..."):
        # THE BIG FIX: ONE REQUEST FOR ALL TICKERS
        raw = yf.download(target_symbols, period="2y", interval="1d", group_by='column', auto_adjust=True, progress=False)
        st.session_state['v163_res'] = process_batch_data(raw, target_symbols, sectors)

if 'v163_res' in st.session_state:
    df = st.session_state['v163_res']
    
    # Side Heatmap
    breadth = (len(df[df['MA 200'] < df['Price']]) / len(df)) * 100
    st.sidebar.subheader("🌡️ Market Heatmap")
    if breadth > 60: st.sidebar.success(f"🔥 BULLISH ({round(breadth,1)}%)")
    elif breadth < 40: st.sidebar.error(f"❄️ BEARISH ({round(breadth,1)}%)")
    else: st.sidebar.warning(f"⚖️ NEUTRAL ({round(breadth,1)}%)")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & MA 50", "🪃 Reversion"])
    
    with tabs[0]:
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge"]].sort_values("Miro_Score", ascending=False).style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
    with tabs[1]:
        st.dataframe(df[["Ticker", "Price", "Recommendation", "MA 50", "MA 200"]].style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
    with tabs[2]:
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Z-Score"]].sort_values("Z-Score").style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
else:
    st.info("Click 'EXECUTE BATCH SCAN' to pull all 500 stocks at once.")
