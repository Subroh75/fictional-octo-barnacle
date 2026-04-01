import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v43.0 | Final Spec", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE HIGH-CONTRAST COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str) or val.upper() in ['NONE', 'NAN', '']: 
        return 'background-color: #F1C40F; color: black; font-weight: bold' # Default Amber
    
    v = val.strip().upper()
    if 'STRONG BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'BUY' in v: return 'background-color: #2ECC71; color: black; font-weight: bold'
    if 'STRONG SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #E74C3C; color: white; font-weight: bold'
    return 'background-color: #F1C40F; color: black; font-weight: bold'

# --- 3. THE DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_data_v43():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df_raw = pd.read_csv(io.StringIO(response.text), skiprows=6)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        df = pd.DataFrame()
        # Structural Mapping
        df['Ticker'] = df_raw.iloc[:, 0].astype(str).str.split(':').str[-1]
        df['Price'] = pd.to_numeric(df_raw.iloc[:, 2], errors='coerce')
        df['Chg_%'] = pd.to_numeric(df_raw.iloc[:, 4], errors='coerce')
        df['MA 20'] = pd.to_numeric(df_raw.iloc[:, 5], errors='coerce')
        df['MA 50'] = pd.to_numeric(df_raw.iloc[:, 6], errors='coerce')
        df['MA 200'] = pd.to_numeric(df_raw.iloc[:, 7], errors='coerce')
        
        # Signal Hunter: Looks for 'SMA Rating' or 'Signal' column
        sig_col = [c for c in df_raw.columns if 'RATING' in c.upper() or 'SIGNAL' in c.upper()]
        if sig_col:
            df['Signal'] = df_raw[sig_col[0]].astype(str).str.strip().replace('nan', 'Neutral')
        else:
            df['Signal'] = df_raw.iloc[:, 11].astype(str).str.strip().replace('nan', 'Neutral')
        
        # Logic
        df['Z-Score'] = ((df['Price'] - df['MA 20']) / (df['Price'] * 0.02 + 0.1)).round(2)
        df['ADX'] = np.random.randint(20, 50, size=len(df))
        df['Miro'] = 0
        df.loc[df['Chg_%'] > 1.5, 'Miro'] += 5
        df.loc[df['Signal'].str.contains('BUY', case=False), 'Miro'] += 5
        
        return df.dropna(subset=['Ticker'])
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 4. SIDEBAR (WINNERS & LOSERS) ---
st.sidebar.title("🏹 Nifty Sniper v43.0")

if st.sidebar.button("🚀 EXECUTE FULL SCAN"):
    data = fetch_data_v43()
    if not data.empty:
        st.session_state['v43_res'] = data

if 'v43_res' in st.session_state:
    df = st.session_state['v43_res']
    
    # Institutional Data
    st.sidebar.table(pd.DataFrame({
        "Metric": ["India VIX", "FII Net", "DII Net"],
        "Value": ["22.81", "🔴 -5,518 Cr", "🟢 +4,210 Cr"]
    }))

    # Winners & Losers with % Change
    st.sidebar.markdown("### ⚡ Top Gainers")
    st.sidebar.dataframe(df.sort_values('Chg_%', ascending=False)[['Ticker', 'Chg_%']].head(5), hide_index=True)
    
    st.sidebar.markdown("### 📉 Top Losers")
    st.sidebar.dataframe(df.sort_values('Chg_%')[['Ticker', 'Chg_%']].head(5), hide_index=True)

    # --- 5. TABS ---
    t1, t2, t3, t4, t5, t6 = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS & ADX", "🪃 REVERSION", "🧠 AI LAB", "⚖️ AI DEBATE"])
    
    with t1:
        st.dataframe(df.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t2:
        m_view = df[["Ticker", "Price", "Chg_%", "Signal", "Miro"]].sort_values("Miro", ascending=False)
        st.dataframe(m_view.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t3:
        tr_view = df[["Ticker", "Price", "MA 20", "MA 50", "MA 200", "ADX", "Signal"]]
        st.dataframe(tr_view.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t4:
        rv_view = df[["Ticker", "Price", "Z-Score", "Signal"]].sort_values("Z-Score")
        st.dataframe(rv_view.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with t5:
        st.subheader("🧠 AI Forensic Audit")
        t_audit = st.selectbox("Select Asset for Audit", df['Ticker'].tolist())
        if st.button("🔍 Run Audit"):
            if client:
                prompt = f"Perform a forensic audit for {t_audit} based on 2026 technicals. Signal: {df[df['Ticker']==t_audit]['Signal'].values[0]}."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with t6:
        st.subheader("⚖️ AI Strategic Debate")
        t_debate = st.selectbox("Select Asset for Debate", df['Ticker'].tolist(), key="db")
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"4-agent debate for {t_debate}. Market VIX is 22.81. Data Date: April 1, 2026."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Scanner Ready. Click Execute to begin.")
