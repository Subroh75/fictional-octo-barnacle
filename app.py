import numpy as np
# Patch for NumPy 2.0 compatibility with Backtesting.py
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
    except:
        return False

ai_active = initialize_ai()
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. AI MODULES ---
def ai_filter_logic(query, df):
    if not ai_active: return df
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"Pandas query for: '{query}'. Columns: {list(df.columns)}. Return ONLY code string."
    try:
        resp = model.generate_content(prompt)
        return df.query(resp.text.strip().replace('`', '').replace('python', ''))
    except: return df

def summon_council(ticker, row, vix):
    if not ai_active: return "AI Engine Offline."
    model = genai.GenerativeModel('gemini-2.5-flash')
    now = datetime.now().strftime("%A, %b %d, %Y")
    prompt = f"Date: {now} | Ticker: {ticker} | Score: {row['Score']} | VIX: {vix}. Bull vs Bear debate + Risk Verdict."
    try: return model.generate_content(prompt).text
    except Exception as e: return f"Error: {e}"

# --- 3. BACKTESTING ENGINE ---
class MiroFishStrategy(Strategy):
    def init(self):
        self.sma200 = self.I(lambda x: pd.Series(x).rolling(200).mean(), self.data.Close)
    def next(self):
        if self.data.Close > self.sma200 and not self.position: self.buy()
        elif self.data.Close < self.sma200 and self.position: self.position.close()

def run_backtest(ticker):
    try:
        hist = yf.download(ticker, period="2y", progress=False)
        if hist.empty: return 0, 0
        bt = Backtest(hist, MiroFishStrategy, cash=100000, commission=.002)
        stats = bt.run()
        return round(stats['Win Rate [%]'], 2), round(stats['Return [%]'], 2)
    except: return 0, 0

# --- 4. THE DATA ENGINE (FIXED FOR MA DISPLAY) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit, vix):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["360ONE.NS", "3MINDIA.NS", "ABB.NS", "ATHERENERG.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Fetching Multi-Level Data...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            
            # CRITICAL FIX: Flatten MultiIndex columns (yfinance 2026 fix)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Calculations
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

# --- 5. UI ---
st.sidebar.title("🏹 Nifty Sniper AI")
vix_val = st.sidebar.number_input("India VIX", value=21.84)
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START AI SCAN"):
    res = run_full_scan(depth, vix_val)
    if not res.empty:
        sl_m = 3.0 if vix_val > 20 else 2.0
        res['Stop_Loss'] = res['Price'] - (sl_m * res['ATR'])
        res['Qty'] = (risk_amt / (res['Price'] - res['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = res

if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    st.subheader("💬 AI Natural Language Screener")
    ai_q = st.text_input("Example: 'Score > 7 and Dist_MA20 < 5'")
    if ai_q: df = ai_filter_logic(ai_q, df)

    tabs = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Inst. Flow", "🧠 Risk Lab", "🧬 Intelligence Lab"])
    
    with tabs[0]: st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    with tabs[1]:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'MA20', 'MA50', 'MA200', 'Dist_MA20', 'Trend']], use_container_width=True)
    with tabs[2]: st.dataframe(df[['Ticker', 'Action', 'Vol_Surge']], use_container_width=True)
    with tabs[3]: st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
    with tabs[4]:
        target = st.selectbox("Select Stock", df['Ticker'].tolist())
        row = df[df['Ticker'] == target].iloc[0]
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⚖️ Summon Council Debate"): st.markdown(summon_council(target, row, vix_val))
        with c2:
            if st.button("📊 Run 2Y Backtest"):
                wr, ret = run_backtest(target)
                st.metric("Win Rate", f"{wr}%", delta=f"{ret}% Return")
else:
    st.info("System Ready. Click 'START AI SCAN'.")
