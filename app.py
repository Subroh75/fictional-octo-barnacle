import numpy as np
# CRITICAL FIX: Patch for Backtesting.py / NumPy 2.0 compatibility
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from backtesting import Backtest, Strategy

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

# --- 2. THE COUNCIL OF EXPERTS (MULTI-AGENT DEBATE) ---
def summon_council(ticker, row, vix):
    if not ai_active: return "AI Engine Offline."
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    context = f"Ticker: {ticker}, Score: {row['Score']}, Vol_Surge: {row['Vol_Surge']}, Trend: {row['Trend']}"
    
    prompt = f"""
    Act as a Hedge Fund Committee for {ticker}.
    DATA: {context} | VIX: {vix} (High Volatility)
    
    1. BULL AGENT: Arguments for a long position.
    2. BEAR AGENT: Arguments for a 'Bull Trap' or downside risk.
    3. RISK MANAGER: Final 'GO' or 'NO-GO' verdict based on ₹5,000 risk per trade.
    """
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        return f"Council error: {e}"

# --- 3. BACKTESTING ENGINE ---
class MiroFishBacktest(Strategy):
    def init(self):
        # We use a 200 SMA as the core "MiroFish" filter
        self.sma200 = self.I(lambda x: pd.Series(x).rolling(200).mean(), self.data.Close)

    def next(self):
        if self.data.Close > self.sma200 and not self.position:
            self.buy()
        elif self.data.Close < self.sma200 and self.position:
            self.position.close()

def run_historical_check(ticker):
    try:
        hist = yf.download(ticker, period="2y", progress=False)
        if hist.empty: return 0, 0
        bt = Backtest(hist, MiroFishBacktest, cash=100000, commission=.002)
        stats = bt.run()
        return round(stats['Win Rate [%]'], 2), round(stats['Return [%]'], 2)
    except:
        return 0, 0

# --- 4. DATA ENGINE (VIX-ADAPTIVE & INSTITUTIONAL FLOW) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit, vix):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "FLUOROCHEM.NS"]
        sector_map = {s: "Bluechip" for s in symbols}

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
            m20, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            vol_surge = float(df['Volume'].iloc[-1]) / df['Volume'].rolling(20).mean().iloc[-1]

            # Smart Flow (Institutional Delivery Mock)
            smart_flow = vol_surge * (np.random.randint(45, 80) / 100)

            # Restored Aggressive Signal Logic
            p_change = (cp - prev_cp) / prev_cp
            score = 0
            if cp > m20: score += 2
            if cp > m200: score += 3
            if vol_surge > 1.8: score += 5

            if p_change > 0 and vol_surge > 1.8: action = "🔥 AGGRESSIVE BUY"
            elif p_change < 0 and vol_surge > 1.8: action = "⚠️ PANIC SELL"
            elif p_change > 0: action = "💎 ACCUMULATE"
            else: action = "💤 HOLD"

            # VIX High Volatility Overlay
            if vix > 20 and score < 8:
                action = f"🛡️ {action} (VIX Alert)"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Smart_Flow": round(smart_flow, 2), "Vol_Surge": round(vol_surge, 2),
                "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL",
                "Action": action, "ATR": round(atr, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 5. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper AI")
vix_val = st.sidebar.number_input("India VIX Today", value=21.84)
st.sidebar.info(f"Market Mode: {'🛡️ CONSERVATIVE' if vix_val > 20 else '🚀 AGGRESSIVE'}")

depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START AI SCAN"):
    results = run_full_scan(depth, vix_val)
    if not results.empty:
        sl_mult = 3.0 if vix_val > 20 else 2.0
        results['Stop_Loss'] = results['Price'] - (sl_mult * results['ATR'])
        results['Qty'] = (risk_amt / (results['Price'] - results['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = results

if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Inst. Flow", "🧠 Risk Lab", "🧬 Intelligence Lab"])
    
    with t1: st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    with t2: st.dataframe(df[['Ticker', 'Trend', 'Sector']], use_container_width=True)
    with t3:
        st.subheader("Smart Flow (Volume Surge * Delivery)")
        st.dataframe(df.sort_values("Smart_Flow", ascending=False)[['Ticker', 'Action', 'Smart_Flow', 'Vol_Surge']], use_container_width=True)
    with t4: st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
    with t5:
        st.subheader("🧬 Intelligence Lab")
        target = st.selectbox("Select Stock", df['Ticker'].tolist())
        row_data = df[df['Ticker'] == target].iloc[0]
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⚖️ Summon Council Debate"):
                st.markdown(summon_council(target, row_data, vix_val))
        with c2:
            if st.button("📊 Run 2Y Backtest"):
                wr, ret = run_historical_check(target)
                st.metric("Win Rate", f"{wr}%", delta=f"{ret}% Return")
else:
    st.info("System Ready. Click 'START AI SCAN' to begin.")
