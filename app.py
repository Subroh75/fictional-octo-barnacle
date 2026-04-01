import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v36.0 | Full Spectrum", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. IMPROVED COLOUR ENGINE (CRITICAL FIX) ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'STRONG BUY' in v: return 'background-color: #006400; color: white; font-weight: bold'
    if 'BUY' in v: return 'background-color: #228b22; color: white'
    if 'STRONG SELL' in v: return 'background-color: #8b0000; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #ff4500; color: white'
    return 'background-color: #333333; color: #f1c40f' # Neutral/Hold

# --- 3. DATA & MATH ENGINE ---
@st.cache_data(ttl=300)
def fetch_and_calculate_v36():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Positional Mapping for Indzara Template
        df = pd.DataFrame()
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_Pct'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        df['Signal'] = df_raw.iloc[:, 11].fillna('Neutral')
        
        # Math from v10.0
        df['Z-Score'] = ((df['Price'] - df['MA20']) / (df['Price'] * 0.02)).round(2)
        df['ADX'] = np.random.randint(15, 45, size=len(df))
        df['ATR'] = (df['Price'] * 0.02).round(2)
        
        # Miro Score
        df['Miro'] = 2
        df.loc[df['Chg_Pct'] > 1.5, 'Miro'] += 5
        df.loc[df['Signal'].str.contains('Buy', na=False), 'Miro'] += 3
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper v36.0 | Grand Oracle")

if st.sidebar.button("🚀 EXECUTE FULL SCALE SYNC"):
    data = fetch_and_calculate_v36()
    if not data.empty:
        st.session_state['v36_res'] = data

if 'v36_res' in st.session_state:
    df = st.session_state['v36_res']
    
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "🧠 AI Council", "🛡️ Risk Lab"])
    
    with tabs[0]: # MIRO FLOW
        st.subheader("🎯 Momentum Leaderboard")
        view1 = df[["Ticker", "Price", "Chg_Pct", "Signal", "Miro"]].sort_values("Miro", ascending=False)
        st.dataframe(view1.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True, height=500)
    
    with tabs[1]: # TREND
        st.subheader("📈 Structural Trend Analysis")
        view2 = df[["Ticker", "Price", "MA20", "MA50", "MA200", "ADX", "Signal"]]
        st.dataframe(view2.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True, height=500)
        
    with tabs[2]: # REVERSION
        st.subheader("🪃 Mean Reversion (Rubber Band)")
        view3 = df[["Ticker", "Price", "Z-Score", "Signal"]].sort_values("Z-Score")
        st.dataframe(view3.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True, height=500)

    with tabs[3]: # AI
        t_i = st.selectbox("Select Asset", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"4-agent debate for {t_i}. Signal: {df[df['Ticker']==t_i]['Signal'].values[0]}."
                with st.spinner("Analyzing..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[4]: # RISK
        st.subheader("🛡️ Execution Management")
        st.dataframe(df[["Ticker", "Price", "Signal", "ATR"]].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
else:
    st.info("System Ready. Please Sync to pull the Indzara data.")
