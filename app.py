import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v35.0 | Legacy Merger", layout="wide")

# Google Sheets Bridge Config
SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. COLOUR ENGINE (RE-ENHANCED) ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.lower()
    if 'strong buy' in v: return 'background-color: #006400; color: white; font-weight: bold'
    if 'buy' in v: return 'background-color: #228b22; color: white'
    if 'strong sell' in v: return 'background-color: #8b0000; color: white; font-weight: bold'
    if 'sell' in v: return 'background-color: #ff4500; color: white'
    return 'color: #f1c40f'

# --- 3. THE DATA & MATH ENGINE ---
@st.cache_data(ttl=300)
def fetch_and_calculate_legacy():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Base Data Mapping
        df = pd.DataFrame()
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_Pct'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        df['Signal'] = df_raw.iloc[:, 11].fillna('Neutral')
        
        # --- LEGACY MATH INTEGRATION ---
        # 1. Z-Score (Distance from MA20)
        df['Z-Score'] = ((df['Price'] - df['MA20']) / (df['Price'] * 0.02)).round(2) # Estimated StdDev
        
        # 2. ADX Strength Simulation (Placeholder until live data added)
        df['ADX Strength'] = np.random.randint(15, 45, size=len(df))
        
        # 3. ATR & Risk (Estimated at 2% of Price for SL logic)
        df['ATR'] = (df['Price'] * 0.02).round(2)
        
        # 4. Miro Score (v10.0 Logic)
        df['Miro_Score'] = 2
        df.loc[df['Chg_Pct'] > 1.5, 'Miro_Score'] += 5
        if 'Buy' in str(df['Signal']): df['Miro_Score'] += 3
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.sidebar.subheader("🏦 Institutional Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["India VIX", "FII Net"], "Value": ["22.81", "🔴 -5,518.40"]}))
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GLOBAL SYNC"):
    data = fetch_and_calculate_legacy()
    if not data.empty:
        st.session_state['v35_res'] = data

if 'v35_res' in st.session_state:
    df = st.session_state['v35_res']
    
    # Risk Math (Legacy v10.0)
    sl_mult = 3.0 if 22.81 > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # Miro Flow
        st.subheader("🎯 Miro Flow (Momentum Leaderboard)")
        st.dataframe(df[["Ticker", "Price", "Signal", "Miro_Score", "Chg_Pct"]].sort_values("Miro_Score", ascending=False).style.map(color_engine, subset=['Signal']), hide_index=True, use_container_width=True)
    
    with tabs[1]: # Trend & ADX
        st.subheader("📈 Structural Trend Analysis")
        st.dataframe(df[["Ticker", "Price", "Signal", "ADX Strength", "MA20", "MA50", "MA200"]], hide_index=True, use_container_width=True)
        
    with tabs[2]: # Reversion
        st.subheader("🪃 Statistical Mean Reversion (Z-Score)")
        st.dataframe(df[["Ticker", "Price", "Signal", "Z-Score"]].sort_values("Z-Score"), hide_index=True, use_container_width=True)

    with tabs[3]: # Intelligence Lab
        t_i = st.selectbox("Select Asset", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"4-agent debate for {t_i}. Price: {df[df['Ticker']==t_i]['Price'].values[0]}. Signal: {df[df['Ticker']==t_i]['Signal'].values[0]}."
                with st.spinner("Council debating..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[4]: # Risk Lab
        st.subheader("🛡️ Execution Management")
        st.dataframe(df[["Ticker", "Price", "Stop_Loss", "Qty", "ATR"]], hide_index=True, use_container_width=True)
else:
    st.info("Scanner Ready.")
