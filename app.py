import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from backtesting import Backtest, Strategy
from datetime import datetime

# --- 1. CONFIG & AI INITIALIZATION ---
st.set_page_config(page_title="Nifty Sniper Institutional AI", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. AI TOOLS ---
def ai_filter_logic(query, df):
    if not ai_active: return df
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"Convert to pandas query: '{query}'. Columns: {list(df.columns)}. Return ONLY code."
    try:
        resp = model.generate_content(prompt)
        return df.query(resp.text.strip().replace('`', '').replace('python', ''))
    except: return df

def summon_judge(ticker, row, vix):
    if not ai_active: return "AI Offline."
    model = genai.GenerativeModel('gemini-2.5-flash')
    now = datetime.now().strftime("%Y-%m-%d")
    prompt = f"Date: {now} | Ticker: {ticker} | Score: {row['Score']} | VIX: {vix}. Technical verdict?"
    try: return model.generate_content(prompt).text
    except: return "Judge busy."

# --- 3. DATA ENGINE (FIXED FOR MA & MULTI-INDEX) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit, vix):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "3MINDIA.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Calculating Structural Trends...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # 1. Download and immediately fix index
            raw_df = yf.download(t, period="1y", progress=False)
            if raw_df.empty: continue
            
            # 2. FORCE SINGLE INDEX (The Fix for NaN MAs)
            df = pd.DataFrame(index=raw_df.index)
            df['Close'] = raw_df['Close'].values.flatten()
            df['High'] = raw_df['High'].values.flatten()
            df['Low'] = raw_df['Low'].values.flatten()
            df['Volume'] = raw_df['Volume'].values.flatten()

            # 3. Trend Calculations on Clean Data
            cp = float(df['Close'].iloc[-1])
            m20 = df['Close'].rolling(20).mean().iloc[-1]
            m50 = df['Close'].rolling(50).mean().iloc[-1]
            m200 = df['Close'].rolling(200).mean().iloc[-1]
            dist_ma20 = ((cp - m20) / m20) * 100
            
            vol_surge = float(df['Volume'].iloc[-1]) / df['Volume'].rolling(20).mean().iloc[-1]
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]

            score = 0
            if cp > m20 > m50: score += 2
            if cp > m200: score += 3
            if vol_surge > 1.8: score += 5

            p_change = (cp - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])
            action = "🔥 AGGRESSIVE BUY" if (p_change > 0 and vol_surge > 1.8) else "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA20": round(m20, 2), "MA50": round(m50, 2), "MA200": round(m200, 2),
                "Dist_MA20": round(dist_ma20, 2), "Score": score, "Vol_Surge": round(vol_surge, 2),
                "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL",
                "Action": action, "ATR": round(atr, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper AI")
v_vix = st.sidebar.number_input("India VIX", value=21.84)
v_depth = st.sidebar.slider("Depth", 50, 500, 100)
v_risk = st.sidebar.number_input("Risk (INR)", value=5000)

if st.sidebar.button("🚀 START AI SCAN"):
    res = run_full_scan(v_depth, v_vix)
    if not res.empty:
        sl_m = 3.0 if v_vix > 20 else 2.0
        res['Stop_Loss'] = res['Price'] - (sl_m * res['ATR'])
        res['Qty'] = (v_risk / (res['Price'] - res['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = res

if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    # Judge & Screener Integrated
    st.subheader("💬 AI Natural Language Screener")
    ai_q = st.text_input("Filter: 'Score > 8 and Dist_MA20 < 2'")
    if ai_q: df = ai_filter_logic(ai_q, df)

    t1, t2, t3, t4 = st.tabs(["🎯 Leaderboard", "📈 Trends", "🧠 Risk Lab", "🧬 Intelligence Lab"])
    
    with t1: st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    with t2:
        st.subheader("MA Trends & Distance")
        st.dataframe(df[['Ticker', 'Price', 'MA20', 'MA50', 'MA200', 'Dist_MA20', 'Trend']], use_container_width=True)
    with t3: st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'Action']], use_container_width=True)
    with t4:
        st.subheader("🧬 Supreme Judge")
        tgt = st.selectbox("Select Stock", df['Ticker'].tolist())
        if st.button("⚖️ Analyze"):
            st.write(summon_judge(tgt, df[df['Ticker'] == tgt].iloc[0], v_vix))
else:
    st.info("System Ready. Click 'START AI SCAN'.")
