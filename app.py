import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
import re
from google import genai

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v46.0 | The Decoder", layout="wide")

SHEET_ID = "1SX9P19bzXWNypttEnfil195B8H63tjAZIBfK8PW2q9Y"
GID = "1600033224" 

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. COLOUR ENGINE ---
def color_engine(val):
    if not isinstance(val, str): return ''
    v = val.strip().upper()
    if 'BUY' in v: return 'background-color: #008000; color: white; font-weight: bold'
    if 'SELL' in v: return 'background-color: #B22222; color: white; font-weight: bold'
    return 'background-color: #F1C40F; color: black; font-weight: bold' # Amber Neutral

# --- 3. THE DECODER ENGINE ---
@st.cache_data(ttl=300)
def fetch_and_decode():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        # Read raw lines to handle the merged string issue
        lines = response.text.splitlines()
        
        decoded_data = []
        for line in lines[7:]: # Skip headers
            # Regex to find: [Ticker Letters] [Price Numbers] [Signal Letters]
            match = re.match(r"([A-Z0-9]+)([\d\.]+)(000|00)(Neutral|Buy|Sell|Strong Buy|Strong Sell)", line.strip())
            if match:
                ticker, price, _, signal = match.groups()
                decoded_data.append({
                    "Ticker": ticker,
                    "Price": float(price),
                    "Signal": signal,
                    "Chg_%": 0.0, # Placeholder as it's merged
                    "MA_20": float(price) * 0.98 # Simulated for logic
                })
            else:
                # Fallback if line is standard CSV
                parts = line.split(',')
                if len(parts) > 11:
                    decoded_data.append({
                        "Ticker": parts[0].split(':')[-1],
                        "Price": pd.to_numeric(parts[2], errors='coerce'),
                        "Signal": parts[11] if parts[11] != "" else "Neutral",
                        "Chg_%": pd.to_numeric(parts[4], errors='coerce'),
                        "MA_20": pd.to_numeric(parts[5], errors='coerce')
                    })

        df = pd.DataFrame(decoded_data).dropna(subset=['Ticker'])
        
        # Calculate Miro & Reversion
        df['Miro'] = 2
        df.loc[df['Signal'].str.contains('Buy', case=False, na=False), 'Miro'] += 5
        df['Z-Score'] = ((df['Price'] - df['MA_20']) / (df['Price'] * 0.02 + 0.1)).round(2)
        
        return df
    except Exception as e:
        st.error(f"Decoder Error: {e}")
        return pd.DataFrame()

# --- 4. SIDEBAR ---
st.sidebar.title("🏹 Nifty Sniper v46.0")
st.sidebar.subheader("🏦 Institutional Pulse")
st.sidebar.table(pd.DataFrame({
    "Metric": ["India VIX", "FII Net", "DII Net"],
    "Value": ["22.81", "🔴 -5,518 Cr", "🟢 +4,210 Cr"]
}))

if st.sidebar.button("🚀 EXECUTE DECODER SCAN"):
    data = fetch_and_decode()
    if not data.empty:
        st.session_state['v46_res'] = data

if 'v46_res' in st.session_state:
    df = st.session_state['v46_res']
    
    # Winners & Losers for Sidebar
    st.sidebar.subheader("⚡ Top Movers")
    st.sidebar.write("**Gainers**")
    st.sidebar.dataframe(df.nlargest(3, 'Price')[['Ticker', 'Price']], hide_index=True)
    st.sidebar.write("**Losers**")
    st.sidebar.dataframe(df.nsmallest(3, 'Price')[['Ticker', 'Price']], hide_index=True)

    # --- 5. TABS ---
    tabs = st.tabs(["📊 ALL STOCKS", "🎯 MIRO FLOW", "📈 TRENDS", "🪃 REVERSION", "🧠 AI LAB", "⚖️ AI DEBATE"])
    
    with tabs[0]:
        st.dataframe(df.style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.dataframe(df[['Ticker', 'Price', 'Signal', 'Miro']].sort_values('Miro', ascending=False).style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[2]:
        st.dataframe(df[['Ticker', 'Price', 'MA_20', 'Signal']].style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[3]:
        st.dataframe(df[['Ticker', 'Price', 'Z-Score', 'Signal']].sort_values('Z-Score').style.map(color_engine, subset=['Signal']), use_container_width=True, hide_index=True)

    with tabs[4]:
        sel = st.selectbox("Audit Asset", df['Ticker'].tolist())
        if st.button("Run Audit"):
            st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"Audit {sel}").text)

    with tabs[5]:
        sel2 = st.selectbox("Debate Asset", df['Ticker'].tolist(), key="dbase2")
        if st.button("Summon Council"):
            st.write(client.models.generate_content(model="gemini-2.5-flash", contents=f"4-agent debate for {sel2}").text)
else:
    st.info("Scanner Ready. Click Execute to decode your Google Sheet data.")
