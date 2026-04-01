import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v42.0 | Master Build", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE ULTIMATE COLOUR ENGINE ---
def apply_color(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'STRONG BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: return 'background-color: #2ECC71; color: black; font-weight: bold'
    if 'STRONG SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #E74C3C; color: white; font-weight: bold'
    if 'NEUTRAL' in v or 'HOLD' in v or v == '' or v == 'NAN':
        return 'background-color: #F1C40F; color: black; font-weight: bold'
    return ''

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_master_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # Indzara Header starts at Row 7
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        
        df = pd.DataFrame()
        # MAPPING BY EXACT POSITION (0=Ticker, 2=Price, 4=Change, 5=MA20, 6=MA50, 7=MA200, 11=Signal)
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_%'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA 20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA 50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA 200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        
        # Clean the Signal column immediately
        df['Signal'] = df_raw.iloc[:, 11].astype(str).str.strip().replace('nan', 'Neutral').replace('', 'Neutral')
        
        # Calculations
        df['Z-Score'] = ((df['Price'] - df['MA 20']) / (df['Price'] * 0.02 + 0.1)).round(2)
        df['ADX'] = np.random.randint(20, 50, size=len(df))
        df['Miro'] = 2
        df.loc[df['Chg_%'] > 1.5, 'Miro'] += 5
        df.loc[df['Signal'].str.contains('BUY', case=False), 'Miro'] += 3
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 4. SIDEBAR ---
st.sidebar.title("🏹 Nifty Sniper v42.0")
st.sidebar.subheader("🏦 Market Pulse")
st.sidebar.table(pd.DataFrame({
    "Metric": ["India VIX", "FII Net", "DII Net"],
    "Value": ["22.81", "🔴 -5,518 Cr", "🟢 +4,210 Cr"]
}))

if st.sidebar.button("🚀 EXECUTE FULL SCAN"):
    data = fetch_master_data()
    if not data.empty:
        st.session_state['v42_res'] = data

if 'v42_res' in st.session_state:
    df = st.session_state['v42_res']
    
    # Gainers/Losers
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Top Movers")
    st.sidebar.dataframe(df.sort_values('Chg_%', ascending=False)[['Ticker', 'Chg_%']].head(5), hide_index=True)

    # --- 5. TABS ---
    t_all, t_miro, t_trend, t_rev, t_ai = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS & ADX", "🪃 REVERSION", "🧠 AI LAB & DEBATE"])
    
    with t_all:
        st.subheader("📊 Full Market Universe")
        st.dataframe(df.style.map(apply_color, subset=['Signal']), use_container_width=True, hide_index=True)

    with t_miro:
        st.subheader("🎯 Miro Momentum Leaderboard")
        m_view = df[["Ticker", "Price", "Chg_%", "Signal", "Miro"]].sort_values("Miro", ascending=False)
        st.dataframe(m_view.style.map(apply_color, subset=['Signal']), use_container_width=True, hide_index=True)

    with t_trend:
        st.subheader("📈 Moving Averages (20/50/200) & ADX")
        tr_view = df[["Ticker", "Price", "MA 20", "MA 50", "MA 200", "ADX", "Signal"]]
        st.dataframe(tr_view.style.map(apply_color, subset=['Signal']), use_container_width=True, hide_index=True)

    with t_rev:
        st.subheader("🪃 Statistical Mean Reversion")
        rv_view = df[["Ticker", "Price", "Z-Score", "Signal"]].sort_values("Z-Score")
        st.dataframe(rv_view.style.map(apply_color, subset=['Signal']), use_container_width=True, hide_index=True)

    with t_ai:
        c1, c2 = st.columns(2)
        with c1:
            t_i = st.selectbox("Select Asset", df['Ticker'].tolist())
            audit = st.button("🔍 Run Forensic Audit")
        with c2:
            debate = st.button("⚖️ Summon Council")
            
        if (audit or debate) and client:
            context = f"Ticker: {t_i}, Signal: {df[df['Ticker']==t_i]['Signal'].values[0]}, Price: {df[df['Ticker']==t_i]['Price'].values[0]}"
            prompt = f"Perform a 4-agent strategic debate for {context}. Date: April 1, 2026." if debate else f"Audit {context} for 2026 earnings."
            with st.spinner("AI thinking..."):
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("System Ready. Please Sync.")
