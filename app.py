import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty 500 Sniper", layout="wide")

# Initialize session state for the scan results
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    # Fetching Nifty 500 directly from NSE source
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        
        # Benchmarking
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        # Fallback to a few tickers if NSE site fails
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

            # Core Stats
            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # Volatility (VCP)
            high_low = df['High'] - df['Low']
            tr = np.maximum(high_low, np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            atr_ratio = atr / tr.rolling(50).mean().iloc[-1]
            
            # Volume
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol / avg_vol

            # Buy/Sell/Hold Logic
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

# --- 3. SIDEBAR ---
st.sidebar.title("🏹 Nifty 500 Sniper")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_val = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    scan_data = run_full_scan(depth)
    if not scan_data.empty:
        # Pre-calculate Risk before saving to session
        scan_data['Stop_Loss'] = scan_data['Price'] - (2 * scan_data['ATR_Val'])
        scan_data['Qty'] = (risk_val / (scan_data['Price'] - scan_data['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = scan_data

# Sidebar Top 5 & Sector Heat (Only shows if data exists)
if st.session_state['scan_results'] is not None:
    res = st.session_state['scan_results']
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Top 5 Sniper Picks")
    top5 = res.sort_values("Score", ascending=False).head(5)
    for _, row in top5.iterrows():
        st.sidebar.metric(row['Ticker'], f"Score: {row['Score']}", f"₹{row['Price']}", delta_color="off")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏗️ Sector Heat")
    heat = res[res['Score'] >= 6]['Sector'].value_counts().head(3)
    for s, c in heat.items():
        st.sidebar.write(f"**{s}:** {c} Stocks")

# --- 4. MAIN TABS ---
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Vol/Volume Lab", "🧠 Risk Lab", "👣 Inst. Flow"])

    with t1:
        st.subheader("High Confluence Picks")
        st.dataframe(df[df['Score'] >= 6].sort_values("Score", ascending=False), use_container_width=True)
        st.markdown("### 🎯 Sniper Logic\nScore 8+ = **Golden Setup** (Trend + Volume + Tightness).")

    with t2:
        st.subheader("Trend Action")
        st.dataframe(df[['Ticker', 'Price', 'Trend', 'Sector']], use_container_width=True)
        

    with t3:
        st.subheader("Volume Action & VCP")
        st.dataframe(df[['Ticker', 'Action', 'Vol_Surge', 'ATR_Ratio']], use_container_width=True)
        st.markdown("### 📊 Logic Guide\n- **Aggressive Buy:** Price & Vol surging together.\n- **ATR Ratio < 0.9:** Price is 'coiling' for a move.")
        

    with t4:
        st.subheader("Risk Management")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
        st.info(f"Quantities based on ₹{risk_val} risk per trade.")

    with t5:
        st.subheader("Institutional Footprint")
        st.dataframe(df[df['Vol_Surge'] > 1.8][['Ticker', 'Vol_Surge', 'Action']], use_container_width=True)
        

else:
    st.info("System Ready. Adjust settings in sidebar and click 'START SCAN'.")
