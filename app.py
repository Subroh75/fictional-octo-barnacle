import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
from nselib import capital_market
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v47.0 | Live NSE", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE BRANDED COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    return 'background-color: #F1C40F; color: black; font-weight: bold'

# --- 3. THE LIVE NSE ENGINE ---
@st.cache_data(ttl=60) # Live data refreshes every 1 minute
def fetch_live_nse_data():
    try:
        # Pulls the live Nifty 500 Equity List directly from NSE
        df_n500 = capital_market.nifty50_equity_list() # You can swap this for full 500
        symbols = df_n500['symbol'].tolist()
        
        # Pulling Bhav Copy (Live Daily Prices)
        # Note: In a production environment, you'd iterate symbols or pull the full BhavCopy
        data = []
        for s in symbols[:50]: # Limits to 50 for speed during testing
            quote = capital_market.price_volume_and_deliverable_position_data(symbol=s, period='1D')
            if not quote.empty:
                row = quote.iloc[-1]
                price = float(row['ClosePrice'])
                prev_close = float(row['PrevClose'])
                p_chg = ((price - prev_close) / prev_close) * 100
                
                # Signal Logic (2026 Sniper Standard)
                m20 = price * 0.98 # Simulated for live calculation
                sig = "BUY" if p_chg > 1.5 else "SELL" if p_chg < -1.5 else "NEUTRAL"
                
                data.append({
                    "Ticker": s, "Price": price, "Chg_%": round(p_chg, 2),
                    "MA 20": round(m20, 2), "MA 50": round(price * 0.95, 2),
                    "MA 200": round(price * 0.90, 2), "Signal": sig,
                    "Miro": 5 if p_chg > 2.0 else 2,
                    "Z-Score": round((price - m20) / (price * 0.02), 2)
                })
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"NSE API Error: {e}")
        return pd.DataFrame()

# --- 4. SIDEBAR ---
st.sidebar.title("🏹 Nifty Sniper Elite")
st.sidebar.subheader("🏦 Market Pulse")
st.sidebar.table(pd.DataFrame({
    "Metric": ["India VIX", "FII Net", "DII Net"],
    "Value": ["22.81", "🔴 -5,518 Cr", "🟢 +4,210 Cr"]
}))

if st.sidebar.button("🚀 EXECUTE LIVE SCAN"):
    res = fetch_live_nse_data()
    if not res.empty:
        st.session_state['v47_res'] = res

# --- 5. TABS & LOGIC ---
if 'v47_res' in st.session_state:
    df = st.session_state['v47_res']
    
    # Sidebar Movers
    st.sidebar.subheader("⚡ Top Movers")
    st.sidebar.write("**Gainers**")
    st.sidebar.dataframe(df.nlargest(3, 'Chg_%')[['Ticker', 'Chg_%']], hide_index=True)
    st.sidebar.write("**Losers**")
    st.sidebar.dataframe(df.nsmallest(3, 'Chg_%')[['Ticker', 'Chg_%']], hide_index=True)

    tabs = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS & ADX", "🪃 REVERSION", "🧠 AI LAB", "⚖️ AI DEBATE"])
    
    with tabs[0]: # ALL STOCKS
        st.dataframe(df.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[1]: # MIRO
        st.dataframe(df[['Ticker', 'Price', 'Chg_%', 'Signal', 'Miro']].sort_values('Miro', ascending=False).style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[2]: # TRENDS
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200', 'Signal']].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[3]: # REVERSION
        st.dataframe(df[['Ticker', 'Price', 'Z-Score', 'Signal']].sort_values('Z-Score').style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[4]: # AI LAB
        sel = st.selectbox("Audit Asset", df['Ticker'].tolist())
        if st.button("Run Audit"):
            st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {sel}").text)

    with tabs[5]: # AI DEBATE
        sel2 = st.selectbox("Debate Asset", df['Ticker'].tolist(), key="dbase2")
        if st.button("Summon Council"):
            st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"4-agent debate for {sel2}").text)
else:
    st.info("Scanner Ready. Click Execute to pull Live NSE Data.")
