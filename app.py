import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. CONFIG & APP STATE ---
st.set_page_config(page_title="Nifty 500 Sniper", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. DATA ENGINE ---
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
        # Fallback if NSE site is down
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

            # Technical Calcs
            cp = float(df['Close'].iloc[-1])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # Volatility
            high_low = df['High'] - df['Low']
            tr = np.maximum(high_low, np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            atr_50 = tr.rolling(50).mean().iloc[-1]
            atr_ratio = atr / atr_50
            
            # Volume
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]
            vol_surge = vol / avg_vol

            # Confluence Score
            score = 0
            if cp > m20 > m50: score += 2  
            if ((cp / float(df['Close'].iloc[-21])) - 1) - nifty_perf_1m > 0: score += 2 
            if atr_ratio < 0.9: score += 3  
            if vol_surge > 1.8: score += 3  

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Vol_Surge": round(vol_surge, 2), "ATR_Ratio": round(atr_ratio, 2),
                "Trend": "🟢 STRONG" if cp > m20 > m50 > m200 else "⚪ NEUTRAL",
                "ATR_Val": round(atr, 2)
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. SIDEBAR ---
st.sidebar.title("🏹 Nifty 500 Sniper")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    data = run_full_scan(depth)
    if not data.empty:
        st.session_state['scan_results'] = data
        st.rerun()

# --- 4. DISPLAY TABS ---
results = st.session_state['scan_results']

if results is not None and not results.empty:
    # Calculations
    results['Stop_Loss'] = results['Price'] - (2 * results['ATR_Val'])
    results['Qty'] = (risk_amt / (results['Price'] - results['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Vol/Volume", "🧠 Risk Lab", "👣 Inst. Flow"])

    with t1:
        st.subheader("High Confluence Leaderboard")
        top = results[results['Score'] >= 6].sort_values("Score", ascending=False)
        st.dataframe(top, use_container_width=True)
        st.markdown("---")
        st.markdown("### 🎯 Sniper Logic: Triple Confluence")
        st.write("We look for stocks where **Trend + Volume + Tightness** align. A score > 8 indicates a prime swing candidate.")

    with t2:
        st.subheader("Trend Alignment")
        st.dataframe(results[['Ticker', 'Price', 'Trend']], use_container_width=True)
        st.markdown("---")
        st.markdown("### 📈 Trend Action Logic")
        st.write("Stocks are flagged as **STRONG** when the Price is above the 20, 50, and 200-day Moving Averages.")
        

    with t3:
        st.subheader("Volume & Volatility")
        st.dataframe(results[['Ticker', 'Vol_Surge', 'ATR_Ratio']], use_container_width=True)
        st.markdown("---")
        st.markdown("### 📊 Volatility Contraction (VCP)")
        st.write("An **ATR Ratio < 0.90** signals that price is tightening (VCP). This often precedes a massive breakout.")
        

    with t4:
        st.subheader("Risk & Position Sizing")
        st.dataframe(results[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
        st.markdown("---")
        st.markdown(f"### 🧠 Risk Management (INR {risk_amt})")
        st.write("The Qty is calculated so you lose exactly your risk amount if the 2x ATR Stop Loss is hit.")

    with t5:
        st.subheader("Institutional Footprint")
        inst = results[results['Vol_Surge'] > 1.5].sort_values("Vol_Surge", ascending=False)
        st.dataframe(inst[['Ticker', 'Sector', 'Vol_Surge']], use_container_width=True)
        st.markdown("---")
        st.markdown("### 👣 Footprint Logic")
        st.write("Volume Surge > 1.8 indicates 'Institutional Footprints'—big players entering the stock.")
        

else:
    st.warning("No data found. Please click 'START SCAN' in the sidebar to begin.")
