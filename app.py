import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG & AI AGENTS ---
st.set_page_config(page_title="Nifty Hedge Fund Master v7.2", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()

# --- AI AGENT: NEWS SENTIMENT + COUNCIL ---
def summon_council(ticker, row, vix):
    if not ai_active: return "⚠️ AI Engine Offline. Check Secrets."
    
    # 2026 Fail-Safe: Try 2.5 Flash, then 3.0 Flash as backup
    models_to_try = ['gemini-2.5-flash', 'gemini-3-flash-preview']
    
    try:
        stock = yf.Ticker(ticker)
        news = stock.news[:5] 
        headlines = [n['title'] for n in news] if news else ["No recent news found."]
    except: headlines = ["News retrieval failed."]

    context = f"Ticker: {ticker} | Price: {row['Price']} | VIX: {vix} | Headlines: {headlines}"
    prompt = f"Perform a 3-agent debate (Bull, Bear, Risk Manager) for {ticker}. Analyze sentiment of: {headlines}. Data: {context}"

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            if model_name == models_to_try[-1]: # If last model also fails
                return f"Council is in recess: {e}"
            continue

# --- 2. HEDGE FUND MATH ENGINE ---

def calculate_metrics(df):
    try:
        c = df['Close'].values.flatten()
        h = df['High'].values.flatten()
        l = df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        m20 = np.mean(c[-20:]); m50 = np.mean(c[-50:]); m200 = np.mean(c[-200:])
        
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        
        return {
            "cp": c[-1], "m20": m20, "m50": m50, "m200": m200, 
            "adx": adx, "z": round(z, 2), "vol_surge": round(vol_surge, 2), "atr": atr.iloc[-1]
        }
    except: return None

# --- 3. DATA ENGINE ---

@st.cache_data(ttl=3600)
def fetch_institutional_flow():
    return pd.DataFrame({
        "Metric": ["FII Net (Cr)", "DII Net (Cr)", "Market Bias"],
        "Value": ["-7,558.20", "+3,864.00", "⚠️ BEARISH PRESSURE"]
    })

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "360ONE.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text=f"Scanning {limit} Assets...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 50: continue
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            
            m = calculate_metrics(raw)
            if not m: continue

            miro = 0
            if m['vol_surge'] > 1.8: miro += 5
            if m['adx'] > 25: miro += 3
            
            p_change = (m['cp'] - raw['Close'].iloc[-2]) / raw['Close'].iloc[-2]
            if p_change > 0.01 and m['vol_surge'] > 2.0: reco = "🔥 AGGRESSIVE BUY"
            elif m['z'] < -2.0: reco = "🪃 MEAN REVERSION"
            else: reco = "💤 NEUTRAL"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2),
                "Recommendation": reco, "Miro_Score": miro, "Z-Score": m['z'], 
                "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}",
                "Vol_Surge": m['vol_surge'], "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2),
                "ATR": round(m['atr'], 2)
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Hedge Fund Master v7.2")

st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(fetch_institutional_flow())
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)
v_vix = st.sidebar.number_input("India VIX", value=21.84)

if st.sidebar.button("🚀 EXECUTE MASTER SCAN"):
    st.session_state['v72_results'] = run_master_scan(v_depth)

if 'v72_results' in st.session_state:
    df = st.session_state['v72_results']
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Analysis", "🪃 Mean Reversion", "🧬 Intel & Correlation", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.subheader("Miro Score Leaderboard")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Recommendation', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
    
    with tabs[1]:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'ADX Strength', 'MA 20', 'MA 50', 'MA 200', 'Sector']], use_container_width=True)

    with tabs[2]:
        st.subheader("Statistical Mean Reversion (Z-Score)")
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Recommendation', 'Z-Score', 'Sector']], use_container_width=True)

    with tabs[3]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Correlation Matrix")
            selected = st.multiselect("Select Tickers", df['Ticker'].tolist(), default=df['Ticker'].tolist()[:4])
            if len(selected) > 1:
                c_data = yf.download(selected, period="6mo", progress=False)['Close']
                if isinstance(c_data.columns, pd.MultiIndex): c_data.columns = c_data.columns.get_level_values(1)
                st.dataframe(c_data.pct_change().corr(), use_container_width=True)
        with col2:
            st.subheader("🧠 News Sentiment Lab")
            target = st.selectbox("Audit Ticker", df['Ticker'].tolist())
            if st.button("⚖️ Summon Council"):
                with st.spinner("Council analyzing news..."):
                    st.markdown(summon_council(target, df[df['Ticker'] == target].iloc[0], v_vix))

    with tabs[4]:
        st.subheader("Risk Lab")
        st.dataframe(df[['Ticker', 'Price', 'ATR', 'Sector']], use_container_width=True)
else:
    st.info("System Ready. Scan depth defaulted to 500.")
