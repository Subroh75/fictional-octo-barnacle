import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v27.0 | Arrow-Hunter", layout="wide")

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
    v = val.lower()
    if 'strong buy' in v: return 'background-color: #2ecc71; color: black; font-weight: bold'
    if 'strong sell' in v: return 'background-color: #e74c3c; color: white; font-weight: bold'
    return 'background-color: #f1c40f; color: black'

# --- 2. DATA BRIDGE (THE ARROW-HUNTER) ---
@st.cache_data(ttl=300)
def fetch_from_bridge():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # skiprows=6 aligns the headers correctly for SMA_Screener_v1.0
        df = pd.read_csv(io.StringIO(response.text), skiprows=6)
        
        # Cleanup: Remove spaces from column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # ARROW-HUNTER LOGIC: 
        # Column 'CHANGE %' is the arrow. The NEXT column is the actual percentage number.
        if 'CHANGE %' in df.columns:
            arrow_idx = list(df.columns).index('CHANGE %')
            # Column 4 in your sheet (unnamed) contains the actual numeric data
            num_chg_col = df.columns[arrow_idx + 1] 
            df['Real_Change'] = pd.to_numeric(df[num_chg_col], errors='coerce')
        
        # Miro Score Calculation
        df['Miro_Score'] = 0
        if 'Real_Change' in df.columns:
            df['Miro_Score'] += df['Real_Change'].apply(lambda x: 5 if x > 1.5 else 0)
        
        # Add score if SMA Rating is bullish
        if 'SMA Rating' in df.columns:
            df.loc[df['SMA Rating'].str.contains('Buy', na=False), 'Miro_Score'] += 3
            
        return df
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v27.0")

if st.sidebar.button("🚀 SYNC FROM GOOGLE BRIDGE"):
    data = fetch_from_bridge()
    if not data.empty:
        st.session_state['miro_v27'] = data
        st.sidebar.success("Institutional Data Synced.")

if 'miro_v27' in st.session_state:
    df = st.session_state['miro_v27']
    
    # Cleaning Ticker Names (Removing NSE: or NASDAQ: prefix for clarity)
    df['Clean_Ticker'] = df['STOCK'].str.split(':').str[-1]
    
    t1, t2 = st.tabs(["🎯 Miro Flow", "🧠 Intelligence Lab"])
    
    with t1:
        st.subheader("🎯 Miro Momentum Leaderboard")
        # Final display mapping
        display_map = {
            'Clean_Ticker': 'Ticker',
            'PRICE': 'Price',
            'CHANGE %': 'Dir',
            'Real_Change': 'Chg %',
            'SMA Rating': 'SMA Rating',
            'Miro_Score': 'Miro'
        }
        
        cols = [c for c in display_map.keys() if c in df.columns]
        final_df = df[cols].rename(columns=display_map)
        
        st.dataframe(
            final_df.sort_values("Miro", ascending=False).style.map(highlight_reco, subset=['SMA Rating']),
            use_container_width=True, hide_index=True
        )

    with t2:
        ticker = st.selectbox("Select Ticker", df['Clean_Ticker'].tolist() if 'Clean_Ticker' in df.columns else [])
        if st.button("⚖️ Summon Council"):
            if client:
                rating = df[df['Clean_Ticker']==ticker]['SMA Rating'].values[0]
                prompt = f"Perform a 4-agent strategic debate for {ticker}. SMA Rating: {rating}. Context: April 2026 Market."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Bridge Ready. Click the sidebar button to pull data from your SMA Screener.")
