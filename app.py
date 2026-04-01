import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v24.1 | Miro Flow", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

def highlight_reco(val):
    if not isinstance(val, str): return ''
    if 'Strong Buy' in val: return 'background-color: #2ecc71; color: black; font-weight: bold'
    if 'Strong Sell' in val: return 'background-color: #e74c3c; color: white; font-weight: bold'
    return 'background-color: #f1c40f; color: black; font-weight: bold'

# --- 2. PRIVATE BRIDGE ENGINE ---
@st.cache_data(ttl=300)
def fetch_miro_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # skiprows=7 is the sweet spot for the SMA_Screener_v1.0 template
        df = pd.read_csv(io.StringIO(response.text), skiprows=7)
        
        # CLEANING STEP: Remove invisible spaces from headers
        df.columns = df.columns.str.strip()
        
        # Miro Score Logic
        df['Miro_Score'] = 2
        if 'CHANGE %' in df.columns:
            # Extract number even if ▲/▼ symbols are present
            df['Clean_Chg'] = df['CHANGE %'].astype(str).str.extract(r'([-+]?\d*\.\d+|\d+)').astype(float)
            df.loc[df['Clean_Chg'] > 1.5, 'Miro_Score'] += 5
        
        return df
    except Exception as e:
        st.error(f"Bridge Sync Failed: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v24.1")

if st.sidebar.button("🚀 SYNC MIRO FLOW"):
    data = fetch_miro_data()
    if not data.empty:
        st.session_state['miro_data'] = data

if 'miro_data' in st.session_state:
    df = st.session_state['miro_data']
    
    t1, t2 = st.tabs(["🎯 Miro Flow", "🧠 Intelligence Lab"])
    
    with t1:
        st.subheader("🎯 Miro Momentum Leaderboard")
        
        # Safety check for columns
        target_cols = ['STOCK', 'PRICE', 'CHANGE %', 'SMA Rating', 'Miro_Score']
        available_cols = [c for c in target_cols if c in df.columns]
        
        # Create a display dataframe
        display_df = df[available_cols].sort_values("Miro_Score", ascending=False)
        
        # APPLY STYLING ONLY IF 'SMA Rating' EXISTS
        if 'SMA Rating' in display_df.columns:
            st.dataframe(
                display_df.style.map(highlight_reco, subset=['SMA Rating']),
                use_container_width=True, hide_index=True
            )
        else:
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.warning("Note: 'SMA Rating' column not found for styling.")

    with t2:
        ticker = st.selectbox("Select Asset", df['STOCK'].tolist() if 'STOCK' in df.columns else [])
        if st.button("⚖️ Summon Council") and ticker:
            if client:
                # Get the rating safely
                rating = df[df['STOCK']==ticker]['SMA Rating'].values[0] if 'SMA Rating' in df.columns else "N/A"
                prompt = f"4-agent debate for {ticker}. SMA Status: {rating}. Current Date: April 1, 2026."
                with st.spinner("Consulting the Oracle..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Bridge Ready. Click 'Sync' to load your SMA Screener data.")
