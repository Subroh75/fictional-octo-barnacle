import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v33.0 | Deep Scanner", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. COLOUR CODING ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.lower()
    if 'strong buy' in v: return 'background-color: #006400; color: white; font-weight: bold'
    if 'buy' in v: return 'background-color: #228b22; color: white'
    if 'strong sell' in v: return 'background-color: #8b0000; color: white; font-weight: bold'
    if 'sell' in v: return 'background-color: #ff4500; color: white'
    return 'color: #f1c40f'

# --- 3. THE DEEP SCAN ENGINE ---
@st.cache_data(ttl=300)
def fetch_deep_scan():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # We read the raw file to find the "STOCK" anchor
        raw_df = pd.read_csv(io.StringIO(response.text), header=None)
        
        h_idx = 0
        for i, row in raw_df.iterrows():
            if any("STOCK" in str(v).upper() for v in row.values):
                h_idx = i
                break
        
        # Read data with the correct header row
        df = pd.read_csv(io.StringIO(response.text), skiprows=h_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- FIXING THE "NA" BY POSITION ---
        # 1. Find Ticker
        stock_col = [c for c in df.columns if "STOCK" in c.upper()][0]
        df['TICKER'] = df[stock_col].astype(str).str.split(':').str[-1]
        
        # 2. Find Price
        price_col = [c for c in df.columns if "PRICE" in c.upper()][0]
        df['LTP'] = pd.to_numeric(df[price_col], errors='coerce')
        
        # 3. Find Change % (It is usually 2 columns to the right of PRICE in this template)
        p_idx = list(df.columns).index(price_col)
        df['CHG_NUM'] = pd.to_numeric(df.iloc[:, p_idx + 2], errors='coerce')
        
        # 4. Find SMA Ratings & Signals
        # We hunt for any column that contains 'Rating' or 'Signal'
        rating_col = [c for c in df.columns if "RATING" in c.upper()][0]
        df['SIGNAL'] = df[rating_col]
        
        # 5. Hunt for the 3 SMA numeric values (SMA1, SMA 2, SMA 3)
        # In the Indzara template, these are usually columns 5, 6, and 7
        df['MA20'] = pd.to_numeric(df.iloc[:, p_idx + 3], errors='coerce')
        df['MA50'] = pd.to_numeric(df.iloc[:, p_idx + 4], errors='coerce')
        df['MA200'] = pd.to_numeric(df.iloc[:, p_idx + 5], errors='coerce')
        
        # Miro Score Logic
        df['MIRO'] = 0
        df['MIRO'] += df['CHG_NUM'].apply(lambda x: 5 if x > 1.5 else 0)
        df.loc[df['SIGNAL'].str.contains('Buy', na=False), 'MIRO'] += 5
        
        return df
    except Exception as e:
        st.error(f"Deep Scan Error: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper v33.0 | Deep Scan")

if st.sidebar.button("🚀 EXECUTE DEEP SYNC"):
    data = fetch_deep_scan()
    if not data.empty:
        st.session_state['v33_res'] = data

if 'v33_res' in st.session_state:
    df = st.session_state['v33_res']
    
    # Dashboard Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Universe", len(df))
    c2.metric("Mean Change", f"{round(df['CHG_NUM'].mean(), 2)}%")
    c3.metric("Strongest", df.sort_values('MIRO', ascending=False)['TICKER'].iloc[0])

    t1, t2, t3 = st.tabs(["🎯 Miro Flow", "📈 Trend Matrix", "⚖️ AI Council"])
    
    with t1:
        # MOMENTUM VIEW
        view = df[['TICKER', 'LTP', 'CHG_NUM', 'SIGNAL', 'MIRO']].copy()
        view.columns = ['Ticker', 'Price', 'Change %', 'Signal', 'Miro']
        st.dataframe(view.sort_values('Miro', ascending=False).style.map(color_engine, subset=['Signal']), use_container_width=True, height=500)

    with tabs[1]:
        # TREND VIEW
        trend = df[['TICKER', 'LTP', 'MA20', 'MA50', 'MA200', 'SIGNAL']].copy()
        st.dataframe(trend, use_container_width=True, height=500)

    with tabs[2]:
        ticker = st.selectbox("Select Asset", df['TICKER'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"Perform a strategic 4-agent debate for {ticker}. Current Signal: {df[df['TICKER']==ticker]['SIGNAL'].values[0]}."
                st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("System Ready. Please Sync to pull the Indzara template data.")
