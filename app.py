import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# --- 1. CONFIG & AI INITIALIZATION ---
st.set_page_config(page_title="Nifty 500 Sniper AI", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except:
        return False

ai_active = initialize_ai()

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. AI MODULE: THE SCREENER ---
def ai_filter_logic(query, df):
    if not ai_active: return df
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"Convert this to a pandas query: '{query}'. Columns: Ticker, Sector, Price, Score, Vol_Surge, ATR_Ratio. Return ONLY the code."
    try:
        response = model.generate_content(prompt)
        return df.query(response.text.strip().replace('`', ''))
    except: return df

# --- 3. DATA ENGINE (Nifty 500 Logic) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "FLUOROCHEM.NS"]
        sector_map = {s: "Misc" for s in symbols}; nifty_perf_1m = 0.02

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500 Data...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            atr_ratio = atr / tr.rolling(50).mean().iloc[-1]
            vol_surge = float(df['Volume'].iloc[-1]) / df['Volume'].rolling(20).mean().iloc[-1]

            # Logic
            p_change = (cp - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])
            action = "🔥 AGGRESSIVE BUY" if (p_change > 0 and vol_surge > 1.5) else "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"
            
            score = 0
            if cp > m20 > m50: score += 2
            if atr_ratio < 0.9: score += 3
            if vol_surge > 1.8: score += 3

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Vol_Surge": round(vol_surge, 2), "ATR_Ratio": round(atr_ratio, 2),
                "Trend": "🟢 STRONG" if cp > m20 > m50 > m200 else "⚪ NEUTRAL",
                "Action": action, "ATR_Val": round(atr, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. SIDEBAR & THE SLIM-CONTEXT JUDGE ---
st.sidebar.title("🏹 Nifty Sniper AI")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_val = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    data = run_full_scan(depth)
    if not data.empty:
        data['Stop_Loss'] = data['Price'] - (2 * data['ATR_Val'])
        data['Qty'] = (risk_val / (data['Price'] - data['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = data

if st.session_state['scan_results'] is not None and ai_active:
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ The Supreme Judge")
    user_ask = st.sidebar.text_input("Ask about a stock (e.g. Why is Fluorochem a buy?)")
    if user_ask:
        with st.sidebar:
            with st.spinner("Analyzing..."):
                try:
                    all_t = st.session_state['scan_results']['Ticker'].tolist()
                    target = next((t for t in all_t if t.split('.')[0] in user_ask.upper()), None)
                   model = genai.GenerativeModel('gemini-2.5-pro')
                    # Targeted Context to prevent API Crashes
                    context = st.session_state['scan_results'][st.session_state['scan_results']['Ticker'] == target].to_string() if target else st.session_state['scan_results'].head(10).to_string()
                    resp = model.generate_content(f"Data: {context}. VIX: 21.42. Question: {user_ask}")
                    st.write(resp.text)
                except Exception as e: st.error(f"Error: {e}")

# --- 5. MAIN INTERFACE ---
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    st.subheader("💬 AI Natural Language Screener")
    ai_q = st.text_input("Search (e.g. 'Score > 5 and Sector == \"Chemicals\"')")
    if ai_q: df = ai_filter_logic(ai_q, df)

    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Vol Lab", "🧠 Risk Lab", "👣 Inst. Flow"])
    with t1: st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    with t2: st.dataframe(df[['Ticker', 'Price', 'Trend', 'Sector']], use_container_width=True)
    with t3: st.dataframe(df[['Ticker', 'Vol_Surge', 'ATR_Ratio', 'Action']], use_container_width=True)
    with t4: st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
    with t5: st.dataframe(df[df['Vol_Surge'] > 1.8][['Ticker', 'Vol_Surge', 'Action']], use_container_width=True)
else:
    st.info("Ready. Adjust settings and click 'START SCAN'.")
