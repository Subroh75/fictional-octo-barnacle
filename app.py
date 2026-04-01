import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v32.0 | Expanded", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.lower()
    if 'strong buy' in v: return 'background-color: #006400; color: white; font-weight: bold'
    if 'buy' in v: return 'background-color: #228b22; color: white'
    if 'strong sell' in v: return 'background-color: #8b0000; color: white; font-weight: bold'
    if 'sell' in v: return 'background-color: #ff4500; color: white'
    return 'color: #f1c40f'

# --- 3. DATA BRIDGE (SMART COLUMN HUNTER) ---
@st.cache_data(ttl=300)
def fetch_expanded_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        raw_text = response.text
        full_df = pd.read_csv(io.StringIO(raw_text), header=None)
        
        # Find the row where the data actually starts
        h_idx = 0
        for i, row in full_df.iterrows():
            if any("STOCK" in str(v).upper() for v in row.values):
                h_idx = i
                break
        
        df = pd.read_csv(io.StringIO(raw_text), skiprows=h_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identify SMA Columns (SMA1, SMA 2, SMA 3, etc.)
        sma_cols = [c for c in df.columns if "SMA" in c.upper() and "SIGNAL" not in c.upper() and "RATING" not in c.upper()]
        
        # Ticker Cleanup
        df['TICKER'] = df['STOCK'].astype(str).str.split(':').str[-1] if 'STOCK' in df.columns else "N/A"
        
        # Numeric Change Calculation
        if 'CHANGE %' in df.columns:
            idx = list(df.columns).index('CHANGE %')
            # Look at the column to the right of the arrow
            df['CHG_VAL'] = pd.to_numeric(df.iloc[:, idx+1], errors='coerce')
        else:
            df['CHG_VAL'] = 0.0

        # Miro Score Logic
        df['MIRO'] = 0
        df.loc[df['CHG_VAL'] > 1.5, 'MIRO'] += 5
        if 'SMA Rating' in df.columns:
            df.loc[df['SMA Rating'].str.contains('Buy', na=False), 'MIRO'] += 5
            
        return df, sma_cols
    except Exception as e:
        st.error(f"Sync Failed: {e}")
        return pd.DataFrame(), []

# --- 4. UI INTERFACE ---
st.title("🏹 NIFTY SNIPER ORACLE v32.0")
st.markdown("---")

if st.sidebar.button("🚀 EXECUTE FULL SCALE SYNC"):
    data, sma_list = fetch_expanded_data()
    if not data.empty:
        st.session_state['v32_data'] = data
        st.session_state['v32_sma'] = sma_list

if 'v32_data' in st.session_state:
    df = st.session_state['v32_data']
    sma_cols = st.session_state['v32_sma']
    
    # 📈 TOP BAR METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Stocks", len(df))
    m2.metric("Top Mover", df.sort_values('CHG_VAL', ascending=False)['TICKER'].iloc[0])
    m3.metric("Market Sentiment", "BULLISH" if df['CHG_VAL'].mean() > 0 else "BEARISH")

    tabs = st.tabs(["🎯 Miro Momentum", "📈 Trend & MAs", "🧠 AI Strategy Lab"])
    
    with tabs[0]:
        st.subheader("🎯 High-Conviction Miro Flow")
        # Column selection for clean UI
        cols = ['TICKER', 'PRICE', 'CHG_VAL', 'SMA Rating', 'MIRO']
        avail = [c for c in cols if c in df.columns or c in ['TICKER', 'MIRO', 'CHG_VAL']]
        
        st.dataframe(
            df[avail].sort_values('MIRO', ascending=False).style.map(color_engine, subset=['SMA Rating'] if 'SMA Rating' in df.columns else []),
            use_container_width=True, height=600
        )

    with tabs[1]:
        st.subheader("📈 Moving Average & Trend Matrix")
        # We explicitly include the SMA columns we hunted for earlier
        trend_cols = ['TICKER', 'PRICE'] + sma_cols + (['SMA Rating'] if 'SMA Rating' in df.columns else [])
        st.dataframe(df[trend_cols], use_container_width=True, height=600)

    with tabs[2]:
        col_a, col_b = st.columns([1, 2])
        with col_a:
            t_f = st.selectbox("Select Asset", df['TICKER'].tolist())
            do_audit = st.button("🔍 Run Forensic Audit")
            do_debate = st.button("⚖️ Summon Council")
        
        with col_b:
            if do_audit and client:
                with st.spinner("AI Auditing..."):
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {t_f} trend.")
                    st.markdown(res.text)
            if do_debate and client:
                with st.spinner("Council debating..."):
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=f"4-agent debate for {t_f}.")
                    st.markdown(res.text)
else:
    st.info("System Offline. Click sidebar button to initialize Bridge.")
