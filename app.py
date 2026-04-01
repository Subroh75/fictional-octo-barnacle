import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v24.0 | Miro Flow", layout="wide")

# Your verified Sheet ID and Tab GID
SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# Professional Styling for Recommendations
def highlight_reco(val):
    if not isinstance(val, str): return ''
    if 'Strong Buy' in val: return 'background-color: #2ecc71; color: black; font-weight: bold'
    if 'Strong Sell' in val: return 'background-color: #e74c3c; color: white; font-weight: bold'
    return 'background-color: #f1c40f; color: black; font-weight: bold'

# --- 2. PRIVATE BRIDGE ENGINE ---
@st.cache_data(ttl=300)
def fetch_miro_data():
    # Direct CSV Export link to bypass "Publish to Web" restrictions
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    
    try:
        # Browser-mimic headers to ensure Google allows the connection
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Based on SMA_Screener_v1.0, the actual data starts at Row 8 (skiprows=7)
        df = pd.read_csv(io.StringIO(response.text), skiprows=7)
        
        # Clean column names to remove spaces/symbols
        df.columns = df.columns.str.strip()
        
        # Miro Score Logic (Patented by User)
        # We look at 'CHANGE %' and 'SMA Rating' from your sheet
        df['Miro_Score'] = 2
        # If 'CHANGE %' has the ▲ symbol, we clean it first
        if 'CHANGE %' in df.columns:
            df['Clean_Chg'] = df['CHANGE %'].astype(str).str.extract(r'(\d+\.?\d*)').astype(float)
            df.loc[df['Clean_Chg'] > 1.5, 'Miro_Score'] += 5
        
        return df
    except Exception as e:
        st.error(f"Bridge Sync Failed: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v24.0")
st.sidebar.info("Connected to SMA_Screener_v1.0")

if st.sidebar.button("🚀 SYNC MIRO FLOW"):
    with st.spinner("Connecting to Private Google Bridge..."):
        data = fetch_miro_data()
        if not data.empty:
            st.session_state['miro_data'] = data
            st.sidebar.success("Institutional Data Synced.")

# --- 4. DASHBOARD TABS ---
if 'miro_data' in st.session_state:
    df = st.session_state['miro_data']
    
    t1, t2, t3 = st.tabs(["🎯 Miro Flow", "📉 SMA Analysis", "🧠 Intelligence Lab"])
    
    with t1:
        st.subheader("🎯 Miro Momentum Leaderboard")
        # Filtering for relevant columns from your spreadsheet
        display_cols = ['STOCK', 'PRICE', 'CHANGE %', 'SMA Rating', 'Miro_Score']
        # Intersect with existing columns to avoid errors
        cols = [c for c in display_cols if c in df.columns]
        
        st.dataframe(
            df[cols].sort_values("Miro_Score", ascending=False).style.map(highlight_reco, subset=['SMA Rating']),
            use_container_width=True, hide_index=True
        )

    with t2:
        st.subheader("📈 Simple Moving Average (SMA) Breakdown")
        sma_cols = ['STOCK', 'PRICE', 'SMA1', 'SMA 2', 'SMA 3', 'SMA Rating']
        cols_sma = [c for c in sma_cols if c in df.columns]
        st.dataframe(df[cols_sma], use_container_width=True, hide_index=True)

    with t3:
        st.subheader("🧠 4-Agent Strategy Debate")
        ticker = st.selectbox("Select Asset", df['STOCK'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                rating = df[df['STOCK']==ticker]['SMA Rating'].values[0]
                prompt = f"Perform a 4-agent strategic debate for {ticker}. Current SMA Rating: {rating}. Date: April 1, 2026."
                with st.spinner("Analyzing Market Sentiment..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Bridge Ready. Click the sidebar button to establish the Nifty 500 connection.")
