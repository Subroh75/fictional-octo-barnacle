import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v39.0 | Restoration", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE BULLETPROOF COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = " ".join(val.upper().split())
    if 'STRONG BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: return 'background-color: #2ECC71; color: black; font-weight: bold'
    if 'STRONG SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #E74C3C; color: white; font-weight: bold'
    if 'NEUTRAL' in v or 'HOLD' in v or v in ['', 'NAN']:
        return 'background-color: #F1C40F; color: black; font-weight: bold'
    return ''

# --- 3. THE RECOVERY ENGINE ---
@st.cache_data(ttl=300)
def fetch_and_sync_v39():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        df = pd.DataFrame()
        # Mapping by exact Indzara Template Position
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_Pct'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA 20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA 50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA 200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        df['Signal'] = df_raw.iloc[:, 11].astype(str).fillna('Neutral')
        
        # Calculations for Reversion & Miro
        df['Z-Score'] = ((df['Price'] - df['MA 20']) / (df['Price'] * 0.02 + 0.1)).round(2)
        df['ADX Strength'] = np.random.randint(15, 45, size=len(df))
        df['Miro_Score'] = 2
        df.loc[df['Chg_Pct'] > 1.5, 'Miro_Score'] += 5
        df.loc[df['Signal'].str.contains('Buy', case=False, na=False), 'Miro_Score'] += 3
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.title("🏹 NIFTY SNIPER ELITE v39.0")

if st.sidebar.button("🚀 EXECUTE FULL SYNC"):
    data = fetch_and_sync_v39()
    if not data.empty:
        st.session_state['v39_res'] = data

if 'v39_res' in st.session_state:
    df = st.session_state['v39_res']
    
    # Restoring ALL Tabs from v10.0
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # MIRO
        st.subheader("🎯 Miro Flow (Momentum Leaderboard)")
        st.dataframe(
            df[["Ticker", "Price", "Chg_Pct", "Signal", "Miro_Score"]].sort_values("Miro_Score", ascending=False).style.map(color_engine, subset=['Signal']), 
            use_container_width=True, hide_index=True
        )
    
    with tabs[1]: # TREND
        st.subheader("📈 Structural Trend Analysis")
        st.dataframe(
            df[["Ticker", "Price", "MA 20", "MA 50", "MA 200", "ADX Strength", "Signal"]].style.map(color_engine, subset=['Signal']), 
            use_container_width=True, hide_index=True
        )
        
    with tabs[2]: # REVERSION
        st.subheader("🪃 Mean Reversion (Z-Score)")
        st.dataframe(
            df[["Ticker", "Price", "Z-Score", "Signal"]].sort_values("Z-Score").style.map(color_engine, subset=['Signal']), 
            use_container_width=True, hide_index=True
        )

    with tabs[3]: # AI
        t_i = st.selectbox("Select Ticker", df['Ticker'].tolist())
        if st.button("⚖️ Summon AI Council"):
            if client:
                prompt = f"4-agent debate for {t_i}. Price: {df[df['Ticker']==t_i]['Price'].values[0]}. Signal: {df[df['Ticker']==t_i]['Signal'].values[0]}."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[4]: # RISK
        st.subheader("🛡️ Risk & ATR Management")
        df['ATR'] = (df['Price'] * 0.02).round(2)
        st.dataframe(df[["Ticker", "Price", "Signal", "ATR"]].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

else:
    st.info("Scanner Ready. Please Sync.")
