import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
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
def summon_council(ticker, row):
    if not ai_active: return "AI Offline."
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    technical_context = f"Ticker: {ticker}, Price: {row['Price']}, Score: {row['Score']}, Vol_Surge: {row['Vol_Surge']}, Action: {row['Action']}"
    
    prompt = f"""
    Perform a Council Debate for {ticker}.
    DATA: {technical_context}
    VIX: 21.84 (High Volatility)
    
    1. BULL AGENT: Find momentum reasons to buy.
    2. BEAR AGENT: Identify red flags or 'Bull Traps'.
    3. RISK MANAGER: Weigh both and give a 'GO' or 'NO-GO' verdict based on ₹5000 risk.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Council Error: {e}"

# --- 3. BACKTESTING ENGINE ---
class MiroFishBacktest(Strategy):
    def init(self):
        self.sma200 = self.I(lambda x: pd.Series(x).rolling(200).mean(), self.data.Close)
    def next(self):
        if self.data.Close > self.sma200:
            if not self.position:
                self.buy()
        elif self.data.Close < self.sma200:
            if self.position:
                self.position.close()

def run_historical_check(ticker):
    try:
        data = yf.download(ticker, period="2y", progress=False)
        if data.empty: return 0, 0
        bt = Backtest(data, MiroFishBacktest, cash=100_000, commission=.002)
        stats = bt.run()
        return round(stats['Win Rate [%]'], 2), round(stats['Return [%]'], 2)
    except:
        return 0, 0

# --- 4. DATA ENGINE (MODIFIED WITH VIX GUARDRAILS) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit, vix_val):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "FLUOROCHEM.NS"]
        sector_map = {s: "Bluechip" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500...")
    
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

            # VIX ADAPTIVE LOGIC
            p_change = (cp - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])
            
            # Smart Money (Volume * Delivery Mock - for full version connect to NSE API)
            delivery_mock = np.random.randint(40, 75) # Replace with real scraping if needed
            smart_flow = vol_surge * (delivery_mock / 100)

            score = 0
            if cp > m20 > m50: score += 2
            if atr_ratio < 0.9: score += 3
            if vol_surge > 1.8: score += 3
            
            # VIX Guardrail Adjustment
            action = "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"
            if vix_val > 20 and score < 9: action = "⚠️ VIX CAUTION"
            elif p_change > 0 and vol_surge > 1.5: action = "🔥 AGGRESSIVE BUY"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Vol_Surge": round(vol_surge, 2), "Smart_Flow": round(smart_flow, 2),
                "ATR_Ratio": round(atr_ratio, 2), "Trend": "🟢 STRONG" if cp > m200 else "⚪ NEUTRAL",
                "Action": action, "ATR_Val": round(atr, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 5. UI & SIDEBAR ---
st.sidebar.title("🏹 Nifty Sniper AI")
current_vix = st.sidebar.number_input("India VIX", value=21.84)
vix_mode = "🛡️ CONSERVATIVE" if current_vix > 20 else "🚀 AGGRESSIVE"
st.sidebar.info(f"Mode: {vix_mode}")

depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_val = st.sidebar.number_input("Risk (INR)", value=5000)

if st.sidebar.button("🚀 START AI SCAN"):
    data = run_full_scan(depth, current_vix)
    if not data.empty:
        sl_mult = 3.0 if current_vix > 20 else 2.0
        data['Stop_Loss'] = data['Price'] - (sl_mult * data['ATR_Val'])
        data['Qty'] = (risk_val / (data['Price'] - data['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = data

# --- 6. MAIN DASHBOARD ---
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Inst. Flow", "🧠 Risk Lab", "🧬 Intelligence Lab"])
    
    with t1:
        st.subheader("Leaderboard")
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)

    with t2:
        st.subheader("Trend Action")
        st.dataframe(df[['Ticker', 'Price', 'Trend', 'Sector']], use_container_width=True)

    with t3:
        st.subheader("Institutional Flow (Volume * Delivery)")
        st.dataframe(df.sort_values("Smart_Flow", ascending=False)[['Ticker', 'Smart_Flow', 'Vol_Surge', 'Action']], use_container_width=True)

    with t4:
        st.subheader("Risk Lab")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)

    with t5:
        st.subheader("🧬 Intelligence Lab")
        target_stock = st.selectbox("Select Stock for Deep Analysis", df['Ticker'].tolist())
        row = df[df['Ticker'] == target_stock].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚖️ Summon Council Debate"):
                st.markdown(summon_council(target_stock, row))
        with col2:
            if st.button("📊 Run 2Y Backtest"):
                win_rate, returns = run_historical_check(target_stock)
                st.metric("Historical Win Rate", f"{win_rate}%", delta=f"{returns}% Return")
else:
    st.info("System Ready. Click 'START AI SCAN'.")
