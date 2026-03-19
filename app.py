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
        # Looks for the TOML secret you saved in Streamlit Cloud
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except:
        return False

ai_active = initialize_ai()

# Initialize session state for the scan results
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. AI MODULE: THE SCREENER ---
def ai_filter_logic(query, df):
    if not ai_active: return df
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Convert this request into a pandas query string: '{query}'
    Columns: Ticker, Sector, Price, Score, Vol_Surge, ATR_Ratio, Trend, Action.
    Return ONLY the query string (e.g., Score > 8 and Sector == 'IT').
    """
    try:
        response = model.generate_content(prompt)
        clean_query = response.text.strip().replace('`', '')
        return df.query(clean_query)
    except:
        return df

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
        sector_map = {s: "Bluechip" for s in symbols}
        nifty_perf_1m = 0.02

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500 Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

            # Technical Stats
            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # Volatility (VCP)
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            atr_ratio = atr / tr.rolling(50).mean().iloc[-1]
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol / avg_vol

            # Scoring Logic
            p_change = (cp - prev_cp) / prev_cp
            if p_change > 0 and vol_surge > 1.5: action = "🔥 AGGRESSIVE BUY"
            elif p_change > 0: action = "💎 ACCUMULATE"
            elif p_change < 0 and vol_surge > 1.5: action = "⚠️ PANIC SELL"
            else: action = "💤 HOLD/WAIT"

            score = 0
            if cp > m20 > m50: score += 2  
            if ((cp / float(df['Close'].iloc[-21])) - 1) - nifty_perf_1m > 0: score += 2 
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

# --- 4. SIDEBAR & THE JUDGE ---
st.sidebar.title("🏹 Nifty Sniper AI")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_val = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    scan_data = run_full_scan(depth)
    if not scan_data.empty:
        scan_data['Stop_Loss'] = scan_data['Price'] - (2 * scan_data['ATR_Val'])
        scan_data['Qty'] = (risk_val / (scan_data['Price'] - scan_data['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = scan_data

# Sidebar Judge Chat
if st.session_state['scan_results'] is not None and ai_active:
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ The Supreme Judge")
    user_ask = st.sidebar.text_input("Ask about a stock (e.g. Why is SBIN a buy?)")
    if user_ask:
        with st.sidebar:
            with st.spinner("Judging..."):
                model = genai.GenerativeModel('gemini-1.5-pro')
                context = st.session_state['scan_results'].head(20).to_string()
                resp = model.generate_content(f"Use this data: {context}. MiroFish Logic: High score means Trend + Vol surge. Question: {user_ask}")
                st.write(resp.text)

# --- 5. MAIN INTERFACE ---
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    # AI SCREENER
    st.subheader("💬 AI Natural Language Screener")
    ai_query = st.text_input("Type e.g. 'Show me High Score stocks in Banking'", placeholder="Search with AI...")
    if ai_query:
        df = ai_filter_logic(ai_query, df)

    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Vol Lab", "🧠 Risk Lab", "👣 Inst. Flow"])

    with t1:
        st.subheader("High Confluence Picks")
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)

    with t2:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'Trend', 'Sector']], use_container_width=True)

    with t3:
        st.subheader("Volatility & Volume Patterns")
        st.dataframe(df[['Ticker', 'Vol_Surge', 'ATR_Ratio', 'Action']], use_container_width=True)

    with t4:
        st.subheader("Risk Management (INR)")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)

    with t5:
        st.subheader("Institutional Footprint")
        st.dataframe(df[df['Vol_Surge'] > 1.8][['Ticker', 'Vol_Surge', 'Action']], use_container_width=True)

else:
    if not ai_active:
        st.error("🔑 AI Features Disabled. Add 'GEMINI_API_KEY' to Streamlit Secrets.")
    st.info("System Ready. Adjust settings in sidebar and click 'START SCAN'.")
