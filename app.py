import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG & SETUP ---
st.set_page_config(page_title="Alpha Master Terminal", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE UNIFIED DATA ENGINE ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        symbols, sector_map, nifty_perf = ["RELIANCE.NS", "TCS.NS"], {}, 0

    all_data = []
    prog = st.progress(0, text="Analyzing Market Structure...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            m20 = float(df['Close'].rolling(20).mean().iloc[-1])
            m50 = float(df['Close'].rolling(50).mean().iloc[-1])
            m200 = float(df['Close'].rolling(200).mean().iloc[-1])
            
            # MA Signal Logic
            if cp > m20 > m50 > m200: ma_action = "🟢 STRONG BUY"
            elif cp > m50 > m200: ma_action = "🟡 HOLD"
            elif cp < m200: ma_action = "🔴 AVOID"
            else: ma_action = "⚪ NEUTRAL"

            # Entry Alert Logic
            dist_m20 = ((cp - m20) / m20) * 100
            alert = "🔥 BUY ZONE" if (0 <= dist_m20 <= 3) and (ma_action == "🟢 STRONG BUY") else "Wait"

            # Quant Calculations
            stock_perf_1m = (cp / float(df['Close'].iloc[-21])) - 1
            rs_score = stock_perf_1m - nifty_perf
            
            # Volatility TR/ATR
            high_low = df['High'] - df['Low']
            high_cp = np.abs(df['High'] - df['Close'].shift(1))
            low_cp = np.abs(df['Low'] - df['Close'].shift(1))
            df['TR'] = np.maximum(high_low, np.maximum(high_cp, low_cp))
            df['ATR'] = df['TR'].rolling(14).mean()
            atr_ratio = df['ATR'].iloc[-1] / df['ATR'].rolling(50).mean().iloc[-1]
            
            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA_Action": ma_action, "Alert": alert, "MA20": round(m20, 2), 
                "MA50": round(m50, 2), "MA200": round(m200, 2),
                "Dist_MA20_%": round(dist_m20, 2),
                "RS_Score": round(rs_score * 100, 2), 
                "Tightness": "🎯 TIGHT" if atr_ratio < 0.9 else "🌊 LOOSE",
                "ATR_Val": float(df['ATR'].iloc[-1])
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI RENDER ---
st.sidebar.title("🏹 Alpha Master")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_per_trade = st.sidebar.number_input("Risk Amount (₹)", value=5000)

if st.sidebar.button("🚀 EXECUTE MASTER SCAN"):
    res = run_master_scan(depth)
    if not res.empty:
        st.session_state['scan_results'] = res
        st.rerun()

if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    
    # Calculate Dynamic Qty
    df['Stop_Loss'] = df['Price'] - (2 * df['ATR_Val'])
    df['Qty'] = (risk_per_trade / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    # Fixed Tabs Syntax
    t1, t2, t3 = st.tabs(["🌍 Birds-Eye View", "📈 Trend Action (MA)", "🧠 Quant Genius Lab"])

    with t1:
        st.subheader("Interactive Sector Map")
        fig = px.treemap(df, path=['Sector', 'Ticker'], values=np.abs(df['RS_Score']),
                         color='RS_Score', color_continuous_scale='RdYlGn', height=700)
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("Moving Average Trend Alignment")
        cols_ma = ['Ticker', 'Price', 'MA_Action', 'Alert', 'Dist_MA20_%', 'MA20', 'MA50']
        st.dataframe(df[cols_ma].sort_values(["Alert", "MA_Action"], ascending=[True, False]), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📖 The Trend Action Logic")
        st.markdown("* **🟢 STRONG BUY:** Price > MA20 > MA50 > MA200. This is the 'Perfect Alignment' for momentum.")
        st.markdown("* **🔥 BUY ZONE:** The 'Pullback Entry.' The stock is in an uptrend but has moved back within 0-3% of its 20-day average.")
        st.markdown("* **Dist_MA20_%:** Measures the 'stretch.' If >10%, the stock is overextended—do not chase.")

    with t3:
        st.subheader("Advanced Entry & Position Sizing")
        cols_gen = ['Ticker', 'RS_Score', 'Tightness', 'Stop_Loss', 'Qty']
        st.dataframe(df[cols_gen].sort_values("RS_Score", ascending=False), use_container_width=True)

        st.markdown("---")
        st.markdown("### 🧠 The Quant Genius Logic")
        st.markdown("* **RS Score:** Relative Strength against Nifty 50. Positive = Market Leader.")
        st.markdown("* **Tightness (VCP):** Measures volatility contraction. **🎯 TIGHT** setups precede explosive breakouts.")
        st.markdown("* **ATR Stop Loss:** A volatility-adjusted stop ($2 \\times ATR$). Filters 'daily noise' to prevent premature exits.")
        st.markdown(f"* **Qty:** Number of shares to buy to limit loss to **₹{risk_per_trade}**.")
else:
    st.info("Terminal Ready. Run the scan to populate the analysis.")
