import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. SETUP ---
st.set_page_config(page_title="Alpha Genius Terminal", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE GENIUS ENGINE ---
@st.cache_data(ttl=3600)
def run_genius_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        # Fetch Nifty for Relative Strength calculation
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf = (nifty['Close'].iloc[-1] / nifty['Close'].iloc[-21]) - 1
    except:
        symbols, sector_map, nifty_perf = ["RELIANCE.NS"], {}, 0

    all_data = []
    prog = st.progress(0, text="Running Quant Lab Analysis...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            # --- LOGIC 1: RELATIVE STRENGTH (RS) ---
            stock_perf_1m = (df['Close'].iloc[-1] / df['Close'].iloc[-21]) - 1
            rs_score = stock_perf_1m - nifty_perf
            
            # --- LOGIC 2: VCP DETECTION (ATR CONTRACTION) ---
            df['TR'] = np.maximum(df['High'] - df['Low'], 
                       np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                       abs(df['Low'] - df['Close'].shift(1))))
            df['ATR'] = df['TR'].rolling(14).mean()
            atr_ratio = df['ATR'].iloc[-1] / df['ATR'].rolling(50).mean().iloc[-1]
            vcp_signal = "🎯 TIGHT" if atr_ratio < 0.9 else "🌊 LOOSE"

            # --- LOGIC 3: ATR-BASED RISK (STOP LOSS) ---
            cp = float(df['Close'].iloc[-1])
            atr_val = df['ATR'].iloc[-1]
            suggested_sl = cp - (2 * atr_val)
            risk_per_share = cp - suggested_sl

            # --- LOGIC 4: MEAN REVERSION (OVEREXTENDED CHECK) ---
            m20 = df['Close'].rolling(20).mean().iloc[-1]
            dist_ma20 = ((cp - m20) / m20) * 100
            
            status = "NORMAL"
            if dist_ma20 > 12: status = "⚠️ OVEREXTENDED"
            elif dist_ma20 < -5 and cp > df['Close'].rolling(200).mean().iloc[-1]: status = "💎 DIP BUY"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "RS vs Nifty": round(rs_score * 100, 2), "Volatility": vcp_signal,
                "Status": status, "Stop Loss": round(suggested_sl, 2),
                "Position Size ($1k Risk)": int(1000 / risk_per_share) if risk_per_share > 0 else 0,
                "Action": "BUY" if rs_score > 0 and vcp_signal == "🎯 TIGHT" and status != "⚠️ OVEREXTENDED" else "WAIT"
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI ---
st.sidebar.title("🛠️ Genius Controls")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
capital_risk = st.sidebar.number_input("Risk per trade (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GENIUS SCAN"):
    st.session_state['scan_results'] = run_genius_scan(depth)

if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    t1, t2 = st.tabs(["📊 Market Heatmap", "🧠 Quant Genius Lab"])

    with t1:
        fig = px.treemap(df, path=['Sector', 'Ticker'], values=np.abs(df['RS vs Nifty']),
                         color='RS vs Nifty', color_continuous_scale='RdYlGn', height=700)
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("Advanced Decision Matrix")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Relative Strength Leaders", len(df[df['RS vs Nifty'] > 0]))
        col2.metric("VCP Tight Setups", len(df[df['Volatility'] == "🎯 TIGHT"]))
        col3.metric("Overextended (Avoid)", len(df[df['Status'] == "⚠️ OVEREXTENDED"]))

        # Styling the dataframe
        def color_status(val):
            color = 'red' if val == "⚠️ OVEREXTENDED" else 'green' if val == "💎 DIP BUY" else 'white'
            return f'color: {color}'

        st.dataframe(df.style.applymap(color_status, subset=['Status']), use_container_width=True)

        st.markdown("""
        ### 💡 How to read this Lab:
        * **RS vs Nifty:** Positive means the stock is leading the market.
        * **Volatility (🎯 TIGHT):** This is the VCP logic. It means the stock is "coiling" for a move.
        * **Stop Loss:** Calculated as $Price - (2 \times ATR)$. This is the most logical place to exit.
        * **Position Size:** If you want to risk exactly **₹{0}**, buy this many shares.
        """.format(capital_risk))
        
        [Image of a volatility contraction pattern (VCP) showing diminishing price swings leading to a breakout]
else:
    st.info("Run the Genius Scan to unlock advanced quantitative analytics.")
