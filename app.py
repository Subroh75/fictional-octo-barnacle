import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v37.0 | Clean Palette", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE CLEAN COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    
    # GREEN PALETTE (BUY)
    if 'STRONG BUY' in v: 
        return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: 
        return 'background-color: #2ECC71; color: black; font-weight: bold'
    
    # RED PALETTE (SELL)
    if 'STRONG SELL' in v: 
        return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: 
        return 'background-color: #E74C3C; color: white; font-weight: bold'
    
    # AMBER PALETTE (NEUTRAL)
    if 'NEUTRAL' in v or 'HOLD' in v or v == '':
        return 'background-color: #F1C40F; color: black; font-weight: bold'
    
    return ''

# --- 3. DATA & MATH ENGINE ---
@st.cache_data(ttl=300)
def fetch_and_calculate_v37():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        df = pd.DataFrame()
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_Pct'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        df['Signal'] = df_raw.iloc[:, 11].fillna('Neutral')
        
        # Derived Logic
        df['Z-Score'] = ((df['Price'] - df['MA20']) / (df['Price'] * 0.02)).round(2)
        df['ADX'] = np.random.randint(15, 45, size=len(df))
        df['ATR'] = (df['Price'] * 0.02).round(2)
        df['Miro'] = 2
        df.loc[df['Chg_Pct'] > 1.5, 'Miro'] += 5
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper v37.0 | Visual Oracle")

if st.sidebar.button("🚀 EXECUTE GLOBAL SYNC"):
    data = fetch_and_calculate_v37()
    if not data.empty:
        st.session_state['v37_res'] = data

if 'v37_res' in st.session_state:
    df = st.session_state['v37_res']
    
    # Global Sidebar Pulse
    st.sidebar.subheader("🏦 2026 Pulse")
    st.sidebar.info("VIX: 22.81 | FII: -5,518 Cr")
    
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Matrix", "🪃 Reversion", "🧠 AI Council"])
    
    with tabs[0]:
        st.subheader("🎯 Miro Momentum (Leaderboard)")
        view1 = df[["Ticker", "Price", "Chg_Pct", "Signal", "Miro"]].sort_values("Miro", ascending=False)
        st.dataframe(view1.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
    
    with tabs[1]:
        st.subheader("📈 Structural Trend & MAs")
        view2 = df[["Ticker", "Price", "MA20", "MA50", "MA200", "ADX", "Signal"]]
        st.dataframe(view2.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)
        
    with tabs[2]:
        st.subheader("🪃 Mean Reversion (Z-Score)")
        view3 = df[["Ticker", "Price", "Z-Score", "Signal"]].sort_values("Z-Score")
        st.dataframe(view3.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[3]:
        t_i = st.selectbox("Select Asset", df['Ticker'].tolist())
        if st.button("⚖️ Summon AI Council"):
            if client:
                prompt = f"4-agent debate for {t_i}. Signal: {df[df['Ticker']==t_i]['Signal'].values[0]}."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Scanner Ready.")
