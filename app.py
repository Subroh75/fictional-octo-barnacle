import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
import os

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Nifty 500 Sniper AI", layout="wide")

# Connect to your Gemini API Key (ensure this is in your Streamlit Secrets)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Please add your GEMINI_API_KEY to Streamlit Secrets.")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. AI MODULE: THE NATURAL LANGUAGE SCREENER ---
def ai_filter_logic(query, df):
    """Translates English to Pandas Query"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    Convert this user request into a pandas query string: '{query}'
    Columns available: Ticker, Sector, Price, Score, Vol_Surge, ATR_Ratio, Trend, Action.
    Return ONLY the query string (e.g., Score > 8 and Vol_Surge > 1.5).
    """
    try:
        response = model.generate_content(prompt)
        clean_query = response.text.strip().replace('`', '')
        return df.query(clean_query)
    except Exception as e:
        st.warning(f"AI Screener Error: {e}")
        return df

# --- 3. DATA ENGINE (Your Existing Code) ---
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
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"]
        sector_map = {s: "Bluechip" for s in symbols}
        nifty_perf_1m = 0.02

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500 Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # VCP/Volatility
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            atr_ratio = atr / tr.rolling(50).mean().iloc[-1]
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol / avg_vol

            # Logic
            p_change = (cp - prev_cp) / prev_cp
            if p_change > 0 and vol_surge > 1.5: action = "🔥 AGGRESSIVE BUY"
            elif p_change > 0: action = "💎 ACCUMULATE"
            elif p_change < 0 and vol_surge > 1.5: action = "⚠️ PANIC SELL"
            else: action = "💤 HOLD/WAIT"

            # Scoring
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

# --- 4. SIDEBAR & THE SUPREME JUDGE ---
st.sidebar.title("🏹 Nifty 500 Sniper AI")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_val = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    scan_data = run_full_scan(depth)
    if not scan_data.empty:
        scan_data['Stop_Loss'] = scan_data['Price'] - (2 * scan_data['ATR_Val'])
        scan_data['Qty'] = (risk_val / (scan_data['Price'] - scan_data['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = scan_data

# AI CHAT IN SIDEBAR
if st.session_state['scan_results'] is not None:
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ Ask The Supreme Judge")
    user_ask = st.sidebar.text_input("Why is [Ticker] a buy?")
    if user_ask:
        model = genai.GenerativeModel('gemini-1.5-pro')
        # Context Injection to prevent hallucinations
        context = st.session_state['scan_results'].to_string()
        response = model.generate_content(f"You are the Nifty Sniper Judge. Use this data: {context}. Question: {user_ask}")
        st.sidebar.write(response.text)

# --- 5. MAIN INTERFACE ---
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    # NEW: AI SCREENER BAR
    st.subheader("💬 AI Natural Language Screener")
    ai_query = st.text_input("Try: 'Show me stocks with Score > 7 in the IT sector'", placeholder="Type here...")
    if ai_query:
        df = ai_filter_logic(ai_query, df)

    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Vol/Volume Lab", "🧠 Risk Lab", "👣 Inst. Flow"])

    with t1:
        st.subheader("High Confluence Picks")
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    
    # (Rest of your tabs t2, t3, t4, t5 remain the same as your code)
    # ... [Keep your existing tab logic here] ...

else:
    st.info("System Ready. Adjust settings in sidebar and click 'START SCAN'.")
