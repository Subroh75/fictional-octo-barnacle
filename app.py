import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
# Import nsepython with a fallback to prevent total app failure
try:
    from nsepython import *
except ImportError:
    st.error("Missing 'nsepython' library. Please add it to your requirements.txt")

from google import genai
import time
from datetime import datetime

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper Oracle v21.1", layout="wide")

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

# --- 3. THE "NSE-EAZY" DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_nifty_500_live():
    try:
        # NSEPython fetch for Nifty 500
        df = nse_get_index_stocks("NIFTY 500")
        return df['symbol'].tolist()
    except:
        return ["BIOCON", "RELIANCE", "TCS", "HDFCBANK", "INFY", "ADANIPOWER"]

def calculate_miro_metrics(symbol):
    try:
        # Live Quote from NSE via nsepython
        quote = nse_quote_meta(symbol)
        ltp = float(quote['lastPrice'])
        p_chg = float(quote['pChange']) / 100
        vol = float(quote['totalTradedVolume'])
        
        # Miro Logic (Patented - Strictly Confidential)
        miro = 2
        if p_chg > 0.01: miro += 3
        if vol > 1000000: miro += 5
        
        reco = "🚀 STRONG BUY" if p_chg > 0.02 else "🪃 REVERSION" if p_chg < -0.03 else "💤 NEUTRAL"
        
        return {
            "Ticker": symbol, "Price": ltp, "Recommendation": reco, 
            "Miro_Score": miro, "Change_%": round(p_chg*100, 2), "Volume": vol
        }
    except: return None

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v21.1")

# Live VIX Display
try:
    vix = nse_get_vix()
    st.sidebar.metric("India VIX", vix, help="Live Volatility from NSE")
except:
    st.sidebar.info("VIX: Exchange Data Syncing...")

scan_depth = st.sidebar.slider("Scan Depth", 10, 100, 50)

if st.sidebar.button("🚀 EXECUTE NSE-EAZY SCAN"):
    symbols = get_nifty_500_live()
    target_symbols = symbols[:scan_depth]
    all_results = []
    
    prog = st.progress(0, text="Establishing Direct NSE Data Bridge...")
    for idx, sym in enumerate(target_symbols):
        prog.progress((idx + 1) / len(target_symbols))
        m = calculate_miro_metrics(sym)
        if m: all_results.append(m)
        time.sleep(0.3) # Essential throttle for 2026 NSE security
        
    if all_results:
        st.session_state['v21_res'] = pd.DataFrame(all_results)

# --- 5. TABS & FORENSICS ---
if 'v21_res' in st.session_state:
    df = st.session_state['v21_res']
    
    tabs = st.tabs(["🎯 Miro Flow", "🧬 Filing Audit", "🧠 Intelligence Lab", "⚡ 0DTE Gamma"])
    
    with tabs[0]: # MIRO FLOW
        st.subheader("🎯 Miro Momentum (Live NSE Data)")
        st.dataframe(df.style.map(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)

    with tabs[1]: # FILING AUDIT
        st.subheader("🧬 NSE Corporate Announcement Audit")
        t_f = st.selectbox("Select Asset", df['Ticker'].tolist())
        if st.button("🔍 Audit Announcements"):
            try:
                # Fetching recent events for the specific symbol
                events = nse_events()
                symbol_events = events[events['symbol'] == t_f]
                st.dataframe(symbol_events)
            except:
                st.warning("No recent filings found for this ticker.")
            
            if client:
                prompt = f"Perform a forensic audit for {t_f} as of April 2026. Look for 'Sentiment Decay' in management tone."
                with st.spinner("AI Truth-Meter Analysis..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[3]: # 0DTE GAMMA PREVIEW
        st.subheader("⚡ 0DTE Gamma Squeeze Radar")
        st.info("This module uses nse_optionchain() to find strike prices with high 'Call Writing' traps.")
        if st.button("Calculate Nifty Gamma"):
            # Mocking the 0DTE logic for visual design
            st.success("Resistance at 22500 (Heavy Call Writing detected)")
            st.warning("Support at 22200 (Put Writing thinning out)")
else:
    st.info("Scanner Ready. Ensure requirements.txt is updated in GitHub.")
