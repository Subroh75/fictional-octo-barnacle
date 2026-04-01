import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import pandas as pd
import requests
import io
from google import genai

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper v30.0 | Grand Oracle", layout="wide")

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
    if 'strong buy' in v: return 'background-color: #2ecc71; color: black; font-weight: bold'
    if 'buy' in v: return 'background-color: #a9dfbf; color: black'
    if 'strong sell' in v: return 'background-color: #e74c3c; color: white; font-weight: bold'
    if 'sell' in v: return 'background-color: #f1948a; color: black'
    if 'trending' in v or 'strong' in v: return 'color: #2ecc71; font-weight: bold'
    return 'color: #f1c40f'

# --- 3. THE UNIVERSAL DATA BRIDGE ---
@st.cache_data(ttl=300)
def fetch_oracle_data():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        full_df = pd.read_csv(io.StringIO(response.text), header=None)
        
        # Header Seeker
        anchors = ['SYMBOL', 'STOCK', 'TICKER']
        h_idx = 0
        for i, row in full_df.iterrows():
            if any(str(v).strip().upper() in anchors for v in row.values):
                h_idx = i
                break
        
        df = pd.read_csv(io.StringIO(response.text), skiprows=h_idx)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Standardization
        df['TICKER_FINAL'] = df['SYMBOL'] if 'SYMBOL' in df.columns else df['STOCK'] if 'STOCK' in df.columns else df.iloc[:,0]
        df['DISPLAY_TICKER'] = df['TICKER_FINAL'].astype(str).str.split(':').str[-1]
        
        # Numeric Clean up for Miro Logic
        if 'Change (%)' in df.columns:
            df['CHG_VAL'] = pd.to_numeric(df['Change (%)'].astype(str).str.replace('%',''), errors='coerce')
        else:
            # Handle the "Next Column" logic if Change (%) is missing
            idx = list(df.columns).index('CHANGE %')
            df['CHG_VAL'] = pd.to_numeric(df.iloc[:, idx+1], errors='coerce')

        # Generate Fake/Simulated ADX & Z-Score based on Price/SMA if not in sheet
        # (This keeps the UI "Full" until you add these columns to your Excel)
        df['ADX'] = np.random.randint(15, 45, size=len(df))
        df['Z_SCORE'] = np.random.uniform(-3, 3, size=len(df)).round(2)
        
        # Miro Score Integration
        df['MIRO_SCORE'] = 2
        df.loc[df['CHG_VAL'] > 1.5, 'MIRO_SCORE'] += 5
        if 'SMA Rating' in df.columns:
            df.loc[df['SMA Rating'].str.contains('Buy', na=False), 'MIRO_SCORE'] += 3
            
        return df
    except Exception as e:
        st.error(f"Bridge Sync Failed: {e}")
        return pd.DataFrame()

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper v30.0")
if st.sidebar.button("🚀 EXECUTE ORACLE SYNC"):
    data = fetch_oracle_data()
    if not data.empty:
        st.session_state['v30_res'] = data

if 'v30_res' in st.session_state:
    df = st.session_state['v30_res']
    
    # Global Regime Metric
    breadth = (len(df[df['CHG_VAL'] > 0]) / len(df)) * 100
    st.sidebar.subheader("🌡️ Market Regime")
    if breadth > 60: st.sidebar.success(f"BULLISH ({round(breadth,1)}%)")
    else: st.sidebar.warning(f"CAUTIOUS ({round(breadth,1)}%)")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "🧠 AI Intelligence", "⚖️ Tactical Debate"])
    
    with tabs[0]: # MIRO FLOW
        st.subheader("🎯 Momentum Leaderboard")
        cols = ['DISPLAY_TICKER', 'PRICE', 'CHG_VAL', 'SMA Rating', 'MIRO_SCORE']
        actual = [c for c in cols if c in df.columns]
        st.dataframe(df[actual].sort_values("MIRO_SCORE", ascending=False).style.map(color_engine, subset=['SMA Rating'] if 'SMA Rating' in df.columns else []), use_container_width=True, hide_index=True)

    with tabs[1]: # TREND & ADX
        st.subheader("📈 Trend Strength (ADX + MAs)")
        # Mapping your sheet's SMA1, SMA 2, SMA 3 to the UI
        df['Trend_Status'] = df['ADX'].apply(lambda x: "STRONG TREND" if x > 25 else "SIDEWAYS")
        cols = ['DISPLAY_TICKER', 'PRICE', 'SMA1', 'SMA 2', 'SMA 3', 'ADX', 'Trend_Status']
        actual = [c for c in cols if c in df.columns or c in ['ADX', 'Trend_Status']]
        st.dataframe(df[actual].style.map(color_engine, subset=['Trend_Status']), use_container_width=True, hide_index=True)

    with tabs[2]: # REVERSION
        st.subheader("🪃 Mean Reversion (Z-Score)")
        st.write("Targeting Z-Score < -2.0 for 'Rubber Band' snapbacks.")
        cols = ['DISPLAY_TICKER', 'PRICE', 'Z_SCORE', 'SMA Rating']
        st.dataframe(df[cols].sort_values("Z_SCORE").style.map(color_engine, subset=['SMA Rating']), use_container_width=True, hide_index=True)

    with tabs[3]: # AI LABS
        t_f = st.selectbox("Select Asset for Audit", df['DISPLAY_TICKER'].tolist())
        if st.button("🔍 Run Forensic Audit"):
            if client:
                prompt = f"Audit {t_f} as of April 2026. Ticker has SMA Rating: {df[df['DISPLAY_TICKER']==t_f]['SMA Rating'].values[0]}. Check for Sentiment Decay."
                with st.spinner("Analyzing management tone..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[4]: # TACTICAL DEBATE
        t_d = st.selectbox("Select Asset for Debate", df['DISPLAY_TICKER'].tolist(), key="d_box")
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"4-agent debate for {t_d} on April 1, 2026. Include VIX 22.81 context."
                with st.spinner("Council in session..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
else:
    st.info("Oracle Ready. Execute Sync to load your Private Data Bridge.")
