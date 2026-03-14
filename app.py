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
                "MA50": round(m50, 2), "Dist_MA20_%": round(dist_m20, 2),
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

if st.sidebar.button("🚀 EXECUTE DUAL SCAN"):
    st.session_state['scan_results'] = run_master_scan(depth)

if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    
    # Calculate Dynamic Qty
    df['Stop_Loss'] = df['Price'] - (2 * df['ATR_Val'])
    df['Qty'] = (risk_per_trade / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    t1, t2, t3 = st.tabs(["🌍 Birds-Eye View", "📈 Trend Action (MA)", "🧠 Quant Genius Lab"])

    with t1:
        st.subheader("Interactive Sector Map")
        fig = px.treemap(df, path=['Sector', 'Ticker'], values=np.abs(df['RS_Score']),
                         color='RS_Score', color_continuous_scale='RdYlGn', height=700)
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("Moving Average Trend Alignment")
        [Image of a candlestick chart showing 20, 50, and 200-day moving averages in a clear bullish trend]
        cols_ma = ['Ticker', 'Price', 'MA_Action', 'Alert', 'Dist_MA20_%', 'MA20', 'MA50']
        st.dataframe(df[cols_ma].sort_values(["Alert", "MA_Action"], ascending=[True, False]), use_container_width=True)
        
        st.markdown("""
        ---
        ### 📈 The Trend Action Logic
        * **🟢 STRONG BUY:** Occurs when $Price > MA_{20} > MA_{50} > MA_{200}$. This signals a **stacked momentum** profile.
        * **🔥 BUY ZONE:** This highlights stocks that are in a Strong Buy trend but have pulled back close to the 20MA (within 0-3%).
        * **Dist_MA20:** This is the "Rubber Band" indicator. If it's too high (>10%), don't chase the stock; wait for it to cool down.
        """)

    with t3:
        st.subheader("Advanced Entry & Position Sizing")
        [Image of a volatility contraction pattern (VCP) showing diminishing price swings leading to a breakout]
        cols_gen = ['Ticker', 'RS_Score', 'Tightness', 'Stop_Loss', 'Qty']
        st.dataframe(df[cols_gen].sort_values("RS_Score", ascending=False), use_container_width=True)

        st.markdown(f"""
        ---
        ### 🧠 The Quant Genius Logic
        * **RS Score (Relative Strength):** Compares the stock's 1-month performance against the Nifty 50. Positive = Market Leader.
        * **Tightness (VCP):** Based on the ATR Ratio. **🎯 TIGHT** indicates that volatility is contracting—often the "calm before the storm."
        * **ATR Stop Loss:** Sets a stop loss based on $2 \times$ volatility, ensuring you aren't shaken out by normal daily price swings.
        * **Qty:** Tells you exactly how many shares to buy to risk exactly **₹{risk_per_trade}**.
        """)
