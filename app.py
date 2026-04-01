import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v44.0 | The Hunter", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE DYNAMIC COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'STRONG BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: return 'background-color: #2ECC71; color: black; font-weight: bold'
    if 'STRONG SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #E74C3C; color: white; font-weight: bold'
    return 'background-color: #F1C40F; color: black; font-weight: bold' # Amber Neutral

# --- 3. THE SMART HEADER HUNTER ---
@st.cache_data(ttl=300)
def fetch_and_hunt_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # Read the raw CSV
        raw_df = pd.read_csv(io.StringIO(response.text), header=None)
        
        # FIND THE HEADER ROW (Search for 'STOCK' or 'SYMBOL')
        h_idx = 0
        for i, row in raw_df.iterrows():
            if any(str(v).strip().upper() in ['STOCK', 'SYMBOL', 'TICKER'] for v in row.values):
                h_idx = i
                break
        
        # Load with detected header
        df = pd.read_csv(io.StringIO(response.text), skiprows=h_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # DYNAMIC MAPPING (The Hunter)
        output = pd.DataFrame()
        
        # 1. Hunt for Ticker
        t_col = [c for c in df.columns if any(x in c.upper() for x in ['STOCK', 'SYMBOL', 'TICKER'])][0]
        output['Ticker'] = df[t_col].astype(str).str.split(':').str[-1]
        
        # 2. Hunt for Price
        p_col = [c for c in df.columns if 'PRICE' in c.upper() or 'LTP' in c.upper()][0]
        output['Price'] = pd.to_numeric(df[p_col], errors='coerce')
        
        # 3. Hunt for Change (Numeric)
        # We look for the column containing '%' or 'CHANGE' that is NOT the arrow column
        c_cols = [c for c in df.columns if ('CHANGE' in c.upper() or '%' in c) and 'UNNAMED' not in c.upper()]
        if len(c_cols) > 1:
            output['Chg_%'] = pd.to_numeric(df[c_cols[1]], errors='coerce') # Usually the 2nd change col is numeric
        else:
            output['Chg_%'] = pd.to_numeric(df[c_cols[0]], errors='coerce')

        # 4. Hunt for SMAs
        sma_cols = [c for c in df.columns if 'SMA' in c.upper() and 'RATING' not in c.upper()]
        for i, s_col in enumerate(sma_cols[:3]):
            output[f'MA_{i+1}'] = pd.to_numeric(df[s_col], errors='coerce')

        # 5. Hunt for Signal
        sig_col = [c for c in df.columns if 'RATING' in c.upper() or 'SIGNAL' in c.upper()][0]
        output['Signal'] = df[sig_col].astype(str).str.strip().replace('nan', 'Neutral')
        
        # Post-process logic
        output['Miro'] = 0
        output.loc[output['Chg_%'] > 1.5, 'Miro'] += 5
        output.loc[output['Signal'].str.contains('BUY', case=False), 'Miro'] += 5
        output['Z-Score'] = ((output['Price'] - output.iloc[:, 3]) / (output['Price'] * 0.02 + 0.1)).round(2)

        return output.dropna(subset=['Ticker']), df.columns.tolist()
    except Exception as e:
        st.error(f"Hunter Failed: {e}")
        return pd.DataFrame(), []

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v44.0")

if st.sidebar.button("🚀 EXECUTE SYSTEM SCAN"):
    data, raw_cols = fetch_and_hunt_data()
    if not data.empty:
        st.session_state['v44_res'] = data
        st.session_state['v44_cols'] = raw_cols

if 'v44_res' in st.session_state:
    df = st.session_state['v44_res']
    
    # Sidebar Metrics
    st.sidebar.subheader("🏦 Market Pulse")
    st.sidebar.info("VIX: 22.81 | FII: -5,518 Cr")
    
    # Winners/Losers with proper percent display
    st.sidebar.subheader("⚡ Top Gainers")
    st.sidebar.table(df.sort_values('Chg_%', ascending=False)[['Ticker', 'Chg_%']].head(3))
    st.sidebar.subheader("📉 Top Losers")
    st.sidebar.table(df.sort_values('Chg_%', ascending=True)[['Ticker', 'Chg_%']].head(3))

    # --- 5. TABS ---
    t1, t2, t3, t4, t5, t6 = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS", "🪃 REVERSION", "🧠 AI LAB", "⚖️ AI DEBATE"])
    
    with t1:
        st.dataframe(df.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t2:
        st.dataframe(df[['Ticker', 'Price', 'Chg_%', 'Signal', 'Miro']].sort_values('Miro', ascending=False).style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t3:
        # Dynamic MA display
        ma_disp = [c for c in df.columns if 'MA_' in c]
        st.dataframe(df[['Ticker', 'Price'] + ma_disp + ['Signal']].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t4:
        st.dataframe(df[['Ticker', 'Price', 'Z-Score', 'Signal']].sort_values('Z-Score').style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t5:
        st.subheader("🧠 Forensic Lab")
        sel = st.selectbox("Ticker", df['Ticker'].tolist())
        if st.button("Run Audit"):
            st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {sel}").text)

    with t6:
        st.subheader("⚖️ Strategic Debate")
        sel2 = st.selectbox("Ticker", df['Ticker'].tolist(), key="db2")
        if st.button("Summon Council"):
            st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=f"4-agent debate for {sel2}").text)
else:
    st.info("System Ready. Please Sync.")
