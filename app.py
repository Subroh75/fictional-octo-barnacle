import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v29.0 | Universal Bridge", layout="wide")

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

# --- 2. THE UNIVERSAL HEADER-SEEKER ---
@st.cache_data(ttl=300)
def fetch_universal_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        raw_text = response.text
        full_df = pd.read_csv(io.StringIO(raw_text), header=None)
        
        # We look for the row containing any major anchor keyword
        anchors = ['SYMBOL', 'STOCK', 'TICKER', 'NAME']
        header_idx = 0
        found = False
        for i, row in full_df.iterrows():
            if any(str(val).strip().upper() in anchors for val in row.values):
                header_idx = i
                found = True
                break
        
        # Load data from identified header row
        df = pd.read_csv(io.StringIO(raw_text), skiprows=header_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # UNIVERSAL MAPPING: Map SYMBOL or STOCK to a standard 'TICKER' column
        if 'SYMBOL' in df.columns:
            df['TICKER_FINAL'] = df['SYMBOL']
        elif 'STOCK' in df.columns:
            df['TICKER_FINAL'] = df['STOCK']
        else:
            # Fallback to the first column if no anchor found
            df['TICKER_FINAL'] = df.iloc[:, 0]

        # Miro Score Calculation
        df['MIRO_SCORE'] = 0
        # Check for 'Change (%)' as provided in your list
        if 'Change (%)' in df.columns:
            df['NUM_CHG'] = pd.to_numeric(df['Change (%)'].astype(str).str.replace('%',''), errors='coerce')
            df.loc[df['NUM_CHG'] > 1.5, 'MIRO_SCORE'] += 5
        elif 'CHANGE %' in df.columns:
            # Handle the "Arrow + Number" layout
            idx = list(df.columns).index('CHANGE %')
            num_col = df.columns[idx + 1]
            df['NUM_CHG'] = pd.to_numeric(df[num_col], errors='coerce')
            df.loc[df['NUM_CHG'] > 1.5, 'MIRO_SCORE'] += 5
            
        return df
    except Exception as e:
        st.error(f"Bridge Sync Failed: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v29.0")

if st.sidebar.button("🚀 SYNC UNIVERSAL BRIDGE"):
    data = fetch_universal_data()
    if not data.empty:
        st.session_state['v29_data'] = data
        st.sidebar.success("Found Headers & Synced!")

if 'v29_data' in st.session_state:
    df = st.session_state['v29_data']
    
    # Cleaning the Ticker names
    df['DISPLAY_TICKER'] = df['TICKER_FINAL'].astype(str).str.split(':').str[-1]
    
    t1, t2 = st.tabs(["🎯 Miro Flow", "🧠 AI Strategic Lab"])
    
    with t1:
        st.subheader("🎯 Miro Momentum Leaderboard")
        
        # Dynamically find columns based on your provided list
        pref_cols = ['DISPLAY_TICKER', 'Price', 'Change (%)', 'SMA Rating', 'MIRO_SCORE']
        actual_cols = [c for c in pref_cols if c in df.columns]
        
        # Fallback if specific names aren't found
        if not actual_cols:
            actual_cols = ['DISPLAY_TICKER', 'MIRO_SCORE'] + [c for c in df.columns if c not in ['TICKER_FINAL', 'DISPLAY_TICKER', 'MIRO_SCORE']][:3]

        st.dataframe(
            df[actual_cols].sort_values("MIRO_SCORE", ascending=False).style.map(
                highlight_reco, subset=['SMA Rating'] if 'SMA Rating' in df.columns else []
            ),
            use_container_width=True, hide_index=True
        )

    with t2:
        ticker = st.selectbox("Select Asset", df['DISPLAY_TICKER'].tolist())
        if st.button("⚖️ Summon Council") and ticker:
            if client:
                # Use whatever rating column is found (SMA Rating or SMA)
                rating_col = 'SMA Rating' if 'SMA Rating' in df.columns else 'SMA'
                rating = df[df['DISPLAY_TICKER']==ticker][rating_col].values[0] if rating_col in df.columns else "Neutral"
                prompt = f"Perform a 4-agent strategic debate for {ticker}. Rating: {rating}. Market: April 2026."
                with st.spinner(f"Analyzing {ticker}..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Bridge Ready. Click the sidebar button to auto-detect your spreadsheet headers.")
