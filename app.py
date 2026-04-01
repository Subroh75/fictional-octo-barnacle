import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v38.0 | Bulletproof", layout="wide")

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
    # Clean the string: uppercase, remove extra spaces
    v = " ".join(val.upper().split())
    
    # Check for GREEN (BUY)
    if 'STRONG BUY' in v: 
        return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: 
        return 'background-color: #2ECC71; color: black; font-weight: bold'
    
    # Check for RED (SELL)
    if 'STRONG SELL' in v: 
        return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: 
        return 'background-color: #E74C3C; color: white; font-weight: bold'
    
    # Check for AMBER (NEUTRAL)
    if 'NEUTRAL' in v or 'HOLD' in v or v == '' or v == 'NAN':
        return 'background-color: #F1C40F; color: black; font-weight: bold'
    
    return ''

# --- 3. THE SMART DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_bulletproof_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # Read with a flexible header finder
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        df = pd.DataFrame()
        # Mapping by exact column position to ensure no "NA"
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_Pct'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        
        # Pull Signal from index 11 (SMA Rating column in Indzara)
        df['Signal'] = df_raw.iloc[:, 11].astype(str).fillna('Neutral')
        
        # Miro Logic
        df['Miro'] = 2
        df.loc[df['Chg_Pct'] > 1.5, 'Miro'] += 5
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Failed: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper v38.0 | Visual Fix")

if st.sidebar.button("🚀 EXECUTE SYNC"):
    data = fetch_bulletproof_data()
    if not data.empty:
        st.session_state['v38_res'] = data

if 'v38_res' in st.session_state:
    df = st.session_state['v38_res']
    
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Matrix", "🧠 AI Lab"])
    
    with tabs[0]:
        st.subheader("🎯 Momentum Flow")
        # Ensure 'Signal' is the column being styled
        st.dataframe(
            df[["Ticker", "Price", "Chg_Pct", "Signal", "Miro"]].sort_values("Miro", ascending=False).style.applymap(color_engine, subset=['Signal']), 
            use_container_width=True, hide_index=True
        )
    
    with tabs[1]:
        st.subheader("📈 Moving Average Matrix")
        st.dataframe(
            df[["Ticker", "Price", "MA20", "MA50", "MA200", "Signal"]].style.applymap(color_engine, subset=['Signal']), 
            use_container_width=True, hide_index=True
        )
        
    with tabs[2]:
        t_i = st.selectbox("Select Asset", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"Debate {t_i}. Signal is {df[df['Ticker']==t_i]['Signal'].values[0]}."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("System Ready. Please Sync.")
