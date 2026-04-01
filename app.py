import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v45.0 | The Survivor", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'STRONG BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: return 'background-color: #2ECC71; color: black; font-weight: bold'
    if 'STRONG SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #E74C3C; color: white; font-weight: bold'
    return 'background-color: #F1C40F; color: black; font-weight: bold'

# --- 3. THE SURVIVOR DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_survivor_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        raw_text = response.text
        
        # We try different skiprow values until we find a row with 'STOCK' or 'SYMBOL'
        found_df = None
        for s in range(0, 12):
            test_df = pd.read_csv(io.StringIO(raw_text), skiprows=s)
            test_cols = [str(c).upper() for c in test_df.columns]
            if any(x in test_cols for x in ['STOCK', 'SYMBOL', 'TICKER']):
                found_df = test_df
                found_df.columns = [str(c).strip() for c in found_df.columns]
                break
        
        if found_df is None:
            st.error("Header Not Found: Could not locate 'STOCK' or 'SYMBOL' in the first 12 rows.")
            return pd.DataFrame()

        # SAFE MAPPING (Prevents "Index out of range")
        output = pd.DataFrame()
        
        def get_col(keywords):
            for k in keywords:
                for c in found_df.columns:
                    if k.upper() in c.upper(): return c
            return None

        # Ticker
        t_col = get_col(['STOCK', 'SYMBOL', 'TICKER'])
        output['Ticker'] = found_df[t_col].astype(str).str.split(':').str[-1] if t_col else "N/A"
        
        # Price
        p_col = get_col(['PRICE', 'LTP', 'VALUE'])
        output['Price'] = pd.to_numeric(found_df[p_col], errors='coerce') if p_col else 0.0
        
        # Change
        c_col = get_col(['CHANGE %', 'CHG %', 'CHANGE(%)'])
        output['Chg_%'] = pd.to_numeric(found_df[c_col], errors='coerce') if c_col else 0.0
        
        # Signal
        s_col = get_col(['RATING', 'SIGNAL', 'RECO'])
        output['Signal'] = found_df[s_col].astype(str).fillna('Neutral') if s_col else "Neutral"
        
        # Moving Averages (Hunting for SMA1, SMA 2, etc.)
        sma_cols = [c for c in found_df.columns if 'SMA' in c.upper() and 'RATING' not in c.upper()]
        for i in range(3):
            if len(sma_cols) > i:
                output[f'MA_{i+1}'] = pd.to_numeric(found_df[sma_cols[i]], errors='coerce')
            else:
                output[f'MA_{i+1}'] = 0.0

        # Calculations
        output['Miro'] = 0
        output.loc[output['Chg_%'] > 1.5, 'Miro'] += 5
        output.loc[output['Signal'].str.contains('BUY', case=False), 'Miro'] += 5
        output['Z-Score'] = ((output['Price'] - output['MA_1']) / (output['Price'] * 0.02 + 0.1)).round(2)

        return output.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Survivor Engine Error: {e}")
        return pd.DataFrame()

# --- 4. SIDEBAR ---
st.sidebar.title("🏹 Nifty Sniper v45.0")
st.sidebar.markdown("---")

if st.sidebar.button("🚀 EXECUTE FULL SYNC"):
    data = fetch_survivor_data()
    if not data.empty:
        st.session_state['v45_res'] = data

if 'v45_res' in st.session_state:
    df = st.session_state['v45_res']
    
    st.sidebar.subheader("🏦 Market Pulse")
    st.sidebar.table(pd.DataFrame({
        "Metric": ["India VIX", "FII Net", "DII Net"],
        "Value": ["22.81", "🔴 -5,518 Cr", "🟢 +4,210 Cr"]
    }))

    # WINNERS & LOSERS WITH %
    st.sidebar.subheader("⚡ Top Movers")
    st.sidebar.write("**Gainers**")
    st.sidebar.dataframe(df.sort_values('Chg_%', ascending=False)[['Ticker', 'Chg_%']].head(3), hide_index=True)
    st.sidebar.write("**Losers**")
    st.sidebar.dataframe(df.sort_values('Chg_%', ascending=True)[['Ticker', 'Chg_%']].head(3), hide_index=True)

    # --- TABS ---
    tabs = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS", "🪃 REVERSION", "🧠 AI LAB", "⚖️ AI DEBATE"])
    
    with tabs[0]: # ALL STOCKS
        st.dataframe(df.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[1]: # MIRO
        st.dataframe(df[['Ticker', 'Price', 'Chg_%', 'Signal', 'Miro']].sort_values('Miro', ascending=False).style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[2]: # TRENDS
        st.dataframe(df[['Ticker', 'Price', 'MA_1', 'MA_2', 'MA_3', 'Signal']].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[3]: # REVERSION
        st.dataframe(df[['Ticker', 'Price', 'Z-Score', 'Signal']].sort_values('Z-Score').style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[4]: # AI LAB
        t_a = st.selectbox("Asset for Audit", df['Ticker'].tolist())
        if st.button("Run Audit"):
            st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {t_a}").text)

    with tabs[5]: # AI DEBATE
        t_d = st.selectbox("Asset for Debate", df['Ticker'].tolist(), key="dbase")
        if st.button("Summon Council"):
            st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"4-agent debate for {t_d}").text)
else:
    st.info("Scanner Ready. Click Execute to begin.")
