import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import time
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Nifty 500 Swing Screener", layout="wide")

st.title("🏹 Nifty 500 Swing & Trend Dashboard")
st.markdown("Scanning for **Strong Buys (Bullish Stack)** and **Strong Sells (Bearish Stack)**.")

# --- SIDEBAR ---
st.sidebar.header("Trading Parameters")
risk_amt = st.sidebar.number_input("Risk per Trade (INR)", value=1000)
scan_num = st.sidebar.slider("Number of Stocks to Scan", 10, 500, 50)

@st.cache_data(ttl=3600)
def run_comprehensive_scan(limit):
    # Fetching the symbols
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]

    results = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(symbols[:limit]):
        progress.progress((i + 1) / limit)
        try:
            # Download 2 years of data for 200MA and 52W High/Low
            df = yf.download(ticker, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            
            # Flatten Multi-Index columns (2026 yfinance requirement)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # --- Price and Technicals ---
            cp = float(df['Close'].iloc[-1])
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma50 = df['Close'].rolling(50).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            
            # --- Volatility Calculations ---
            returns = df['Close'].pct_change().dropna()
            std_dev = returns.std()
            vol_d = std_dev               # Daily
            vol_w = std_dev * np.sqrt(5)   # Weekly
            vol_m = std_dev * np.sqrt(21)  # Monthly
            vol_y = std_dev * np.sqrt(252) # Yearly

            # --- Signal Logic ---
            signal = "Neutral"
            sl, qty = 0.0, 0
            
            # Strong Buy (Price > 20 > 50 > 200)
            if cp > ma20 > ma50 > ma200:
                signal = "Strong Buy"
                # ATR for Stop Loss
                tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().iloc[-1]
                sl = cp - (2 * atr)
                qty = int(risk_amt / (cp - sl)) if (cp - sl) > 0 else 0
            
            # Strong Sell (Price < 20 < 50 < 200)
            elif cp < ma20 < ma50 < ma200:
                signal = "Strong Sell"
                tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().iloc[-1]
                sl = cp + (2 * atr)
                qty = 0

            if signal != "Neutral":
                results.append({
                    "Ticker": ticker,
                    "Signal": signal,
                    "Price": round(cp, 2),
                    "Stop Loss": round(sl, 2),
                    "Qty": qty,
                    "Vol (Daily)": f"{vol_d:.2%}",
                    "Vol (Weekly)": f"{vol_w:.2%}",
                    "Vol (Monthly)": f"{vol_m:.2%}",
                    "Vol (Yearly)": f"{vol_y:.2%}",
                    "52W High": round(df['High'].max(), 2),
                    "52W Low": round(df['Low'].min(), 2)
                })
            time.sleep(0.1) # Be nice to Yahoo API
        except Exception as e:
            continue
            
    return pd.DataFrame(results)

# --- EXECUTION BUTTON ---
if st.button("🚀 Run Market Scan"):
    report = run_comprehensive_scan(scan_num)
    
    if not report.empty:
        # Separate Buys and Sells for clarity
        buys = report[report['Signal'] == "Strong Buy"]
        sells = report[report['Signal'] == "Strong Sell"]
        
        st.subheader("🟢 Strong Buy Candidates")
        st.dataframe(buys, use_container_width=True)
        
        st.subheader("🔴 Strong Sell Candidates")
        st.dataframe(sells, use_container_width=True)
        
        # --- CHARTING SECTION ---
        st.divider()
        ticker_list = report['Ticker'].tolist()
        selected_ticker = st.selectbox("Select Ticker for Detailed Analysis:", ticker_list)
        
        if selected_ticker:
            data_plot = yf.download(selected_ticker, period="1y", interval="1d", progress=False)
            if isinstance(data_plot.columns, pd.MultiIndex): data_plot.columns = data_plot.columns.get_level_values(0)
            
            # 
            fig, ax = mpf.plot(data_plot, type='candle', style='charles', mav=(20, 50, 200),
                               volume=True, returnfig=True, title=f"{selected_ticker} Analysis")
            st.pyplot(fig)
    else:
        st.info("No strong signals found in this batch. Try increasing the scan limit in the sidebar.")
