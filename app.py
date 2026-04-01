import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v26.0 | GID Bridge", layout="wide")

# YOUR MASTER KEYS
SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224"  # <--- YOUR TAB ID IS USED HERE

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

# --- 2. DATA BRIDGE (THE GID USAGE) ---
@st.cache_data(ttl=300)
def fetch_from_gid():
    # THE GID IS USED IN THIS URL STRING TO FETCH THE SPECIFIC TAB
    export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    
    try:
        response = requests.get(export_url, headers={'User-Agent': 'Mozilla/5.0'})
        # skiprows=6 targets the headers in Row 7 (STOCK, PRICE, etc.)
        df = pd.read_csv(io.StringIO(response.text), skiprows=6)
        
        # Cleanup: Remove spaces from column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Miro Score Calculation
        df['Miro_Score'] = 0
        if 'CHANGE %' in df.columns:
            # Your sheet has arrows in 'CHANGE %' and numbers in the next column
            change_num_col = df.columns[list(df.columns).index('CHANGE %') + 1]
            df['Num_Change'] = pd.to_numeric(df[change_num_col], errors='coerce')
            df['Miro_Score'] += df['Num_Change'].apply(lambda x: 5 if x > 1.5 else 0)
        
        return df
    except Exception as e:
        st.error(f"Sync Error: {e}")
        return pd.DataFrame()

# --- 3. THE COMMAND CENTER ---
st.sidebar.title("🏹 Nifty Sniper v26.0")

if st.sidebar.button("🚀 SYNC TAB: 1600033224"):
    data = fetch_from_gid()
    if not data.empty:
        st.session_state['miro_v26'] = data
        st.sidebar.success("Tab Synced Successfully!")

if 'miro_v26' in st.session_state:
    df = st.session_state['miro_v26']
    
    t1, t2 = st.tabs(["🎯 Miro Flow", "🧠 Intelligence Lab"])
    
    with t1:
        # Display Core Columns
        display_cols = [c for c in ['STOCK', 'PRICE', 'CHANGE %', 'SMA Rating', 'Miro_Score'] if c in df.columns]
        
        if 'SMA Rating' in df.columns:
            st.dataframe(
                df[display_cols].sort_values("Miro_Score", ascending=False).style.map(highlight_reco, subset=['SMA Rating']),
                use_container_width=True, hide_index=True
            )
        else:
            st.dataframe(df[display_cols].sort_values("Miro_Score", ascending=False), use_container_width=True)

    with t2:
        ticker = st.selectbox("Select Ticker", df['STOCK'].tolist() if 'STOCK' in df.columns else [])
        if st.button("⚖️ Summon Council") and ticker:
            if client:
                rating = df[df['STOCK']==ticker]['SMA Rating'].values[0] if 'SMA Rating' in df.columns else "N/A"
                prompt = f"Perform a strategic 4-agent debate for {ticker}. SMA Rating: {rating}."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("System Ready. Click the sidebar button to pull data from GID 1600033224.")
