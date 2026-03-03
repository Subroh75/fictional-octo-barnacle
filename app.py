import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
import time
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Nifty 500 Alpha Suite", layout="wide")

# --- SIDEBAR SETTINGS ---
st.sidebar.title("🛠️ Control Panel")
risk_amt = st.sidebar.number_input("Risk per Trade (INR)", value=1000)
scan_num = st.sidebar.slider("Scan Depth (Nifty 500)", 10, 500, 100)
st.sidebar.divider()
st.sidebar.info("Power Breakout = Trend Confluence + 20-Day High + Volume Surge")

# --- DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_market_data(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]
        industries = {}

    all_data = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(symbols[:limit]):
        progress.progress((i + 1) / limit)
        try:
            df = yf.download(ticker, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            # Technicals
            cp = float(df['Close'].iloc[-1])
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma50 = df['Close'].rolling(50).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            
            # Breakout Logic
            recent_high_20 = df['High'].iloc[-21:-1].max()
            avg_vol = df['Volume'].iloc[-21:-1].mean()
            curr_vol = df['Volume'].iloc[-1]
            is_breakout = cp > recent_high_20 and curr_vol > (avg_vol * 1.5)
            
            # 52-Week Metrics
            high_52w = df['High'].max()
            dist_52w = ((high_52w - cp) / high_52w) * 100

            # Trend Signal
            signal = "Neutral"
            if cp > ma20 > ma50 > ma200: signal = "Strong Buy"
            elif cp < ma20 < ma50 < ma200: signal = "Strong Sell"

            # ATR for SL
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]

            all_data.append({
                "Ticker": ticker,
                "Industry": industries.get(ticker, "N/A"),
                "Price": round(cp, 2),
                "Signal": signal,
                "Is Breakout": is_breakout,
                "Vol Surge": round(curr_vol/avg_vol, 2),
                "Stop Loss": round(cp - (2*atr), 2) if signal != "Strong Sell" else round(cp + (2*atr), 2),
                "52W High": round(high_52w, 2),
                "Dist to 52W High %": round(dist_52w, 2),
                "ATR": round(atr, 2)
            })
            time.sleep(0.05)
        except: continue
    return pd.DataFrame(all_data)

# --- APP LAYOUT ---
st.title("📈 Nifty 500 Alpha Swing Suite")

if st.button("🔄 Execute Market Scan"):
    results = fetch_market_data(scan_num)
    st.session_state['results'] = results

if 'results' in st.session_state:
    data = st.session_state['results']

    # --- TOP METRICS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Stocks Scanned", len(data))
    col2.metric("Strong Buy Trends", len(data[data['Signal'] == "Strong Buy"]))
    col3.metric("Breakouts Found", len(data[data['Is Breakout'] == True]))

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["🚀 Trend Confluence", "⚡ Breakout Scanner", "📊 Sector Distribution"])

    with tab1:
        st.subheader("Structural Trend Following")
        trend_data = data[data['Signal'] != "Neutral"].copy()
        if not trend_data.empty:
            trend_data['Qty'] = (risk_amt / abs(trend_data['Price'] - trend_data['Stop Loss'])).fillna(0).astype(int)
            st.dataframe(trend_data[["Ticker", "Industry", "Signal", "Price", "Stop Loss", "Qty", "Dist to 52W High %"]], use_container_width=True)
        else:
            st.write("No trend signals found.")

    with tab2:
        st.subheader("Momentum Breakouts")
        breakout_data = data[data['Is Breakout'] == True].copy()
        if not breakout_data.empty:
            breakout_data['Type'] = breakout_data['Signal'].apply(lambda x: "🔥 POWER" if x == "Strong Buy" else "Standard")
            st.dataframe(breakout_data[["Ticker", "Type", "Price", "Vol Surge", "52W High", "Dist to 52W High %"]], use_container_width=True)
        else:
            st.write("No breakouts found.")

    with tab3:
        st.subheader("Industry Strength Analysis")
        # Filter for only bullish signals
        bullish_data = data[data['Signal'] == "Strong Buy"]
        if not bullish_data.empty:
            sector_counts = bullish_data['Industry'].value_counts().reset_index()
            sector_counts.columns = ['Industry', 'Count']
            
            fig_sector = px.pie(sector_counts, values='Count', names='Industry', 
                               title="Sectors Dominating Strong Buy Trends",
                               hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_sector, use_container_width=True)
            
            st.caption("A high concentration in a single sector suggests 'Sector Rotation'—where institutions are pouring money into one industry.")
        else:
            st.write("Not enough data to generate sector distribution.")

    # --- SHARED CHARTING ---
    st.divider()
    st.subheader("🔍 Technical Chart Deep Dive")
    selected = st.selectbox("Select Ticker to Chart:", data['Ticker'].tolist())
    
    if selected:
        c_df = yf.download(selected, period="1y", interval="1d", progress=False)
        if isinstance(c_df.columns, pd.MultiIndex): c_df.columns = c_df.columns.get_level_values(0)
        
        fig, ax = mpf.plot(c_df, type='candle', style='charles', mav=(20, 50, 200),
                           volume=True, returnfig=True, title=f"\n{selected} Swing Setup")
        st.pyplot(fig)
else:
    st.info("Click 'Execute Market Scan' to begin your analysis.")
