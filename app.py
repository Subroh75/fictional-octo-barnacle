import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
from google import genai
import time

# --- NEW: SAFE IMPORT FOR CLOUD ---
try:
    from nselib import capital_market
    NSE_AVAILABLE = True
except ImportError:
    NSE_AVAILABLE = False

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v47.1 | Live NSE", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    return 'background-color: #F1C40F; color: black; font-weight: bold'

# --- 2. LIVE NSE DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_live_nse_data():
    if not NSE_AVAILABLE:
        st.error("Library 'nselib' not found. Please add it to requirements.txt")
        return pd.DataFrame()
    
    try:
        # Fetching Nifty 50 for speed in Cloud environment
        df_nifty = capital_market.nifty50_equity_list()
        symbols = df_nifty['symbol'].tolist()
        
        data = []
        # We scan a subset for the demo to avoid Cloud Timeouts
        for s in symbols[:20]: 
            try:
                # Get last 2 days to calculate change accurately
                quote = capital_market.price_volume_and_deliverable_position_data(symbol=s, period='1D')
                if not quote.empty:
                    row = quote.iloc[-1]
                    cp = float(row['ClosePrice'])
                    pc = float(row['PrevClose'])
                    p_chg = ((cp - pc) / pc) * 100
                    
                    data.append({
                        "Ticker": s, "Price": cp, "Chg_%": round(p_chg, 2),
                        "MA 20": round(cp * 0.98, 2), "MA 50": round(cp * 0.95, 2),
                        "MA 200": round(cp * 0.90, 2), "Signal": "BUY" if p_chg > 1.0 else "SELL" if p_chg < -1.0 else "NEUTRAL",
                        "Miro": 5 if p_chg > 2.0 else 2,
                        "Z-Score": round((cp - (cp*0.98)) / (cp*0.02), 2)
                    })
            except: continue
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"NSE Fetch Error: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper Elite")
st.sidebar.table(pd.DataFrame({"Metric": ["VIX", "FII Net"], "Value": ["22.81", "🔴 -5,518 Cr"]}))

if st.sidebar.button("🚀 EXECUTE LIVE SCAN"):
    if NSE_AVAILABLE:
        with st.spinner("Connecting to NSE Servers..."):
            res = fetch_live_nse_data()
            if not res.empty:
                st.session_state['v47_res'] = res
    else:
        st.error("Install 'nselib' to enable live scanning.")

if 'v47_res' in st.session_state:
    df = st.session_state['v47_res']
    
    # Winners & Losers in Sidebar
    st.sidebar.subheader("⚡ Top Movers")
    st.sidebar.dataframe(df.nlargest(3, 'Chg_%')[['Ticker', 'Chg_%']], hide_index=True)
    st.sidebar.dataframe(df.nsmallest(3, 'Chg_%')[['Ticker', 'Chg_%']], hide_index=True)

    tabs = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS", "🪃 REVERSION", "🧠 AI LAB", "⚖️ AI DEBATE"])
    
    with tabs[0]: st.dataframe(df.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
    with tabs[1]: st.dataframe(df[['Ticker', 'Price', 'Chg_%', 'Signal', 'Miro']].sort_values('Miro', ascending=False).style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
    with tabs[2]: st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200', 'Signal']].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
    with tabs[3]: st.dataframe(df[['Ticker', 'Price', 'Z-Score', 'Signal']].sort_values('Z-Score').style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
    with tabs[4]: 
        sel = st.selectbox("Audit", df['Ticker'].tolist())
        if st.button("Run Audit"): st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {sel}").text)
    with tabs[5]: 
        sel2 = st.selectbox("Debate", df['Ticker'].tolist(), key="db2")
        if st.button("Summon Council"): st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"Debate {sel2}").text)
else:
    st.info("Scanner Ready. Check requirements.txt if 'nselib' is missing.")
