import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import time
from datetime import datetime

# Page Config
st.set_page_config(page_title="Nifty 500 Trend Screener", layout="wide")

# --- APP HEADER ---
st.title("🚀 Nifty 500 Professional Trend Screener")
st.markdown("""
This app scans the Nifty 500 for **Trend Confluence**: Price > 20MA > 50MA > 200MA.
It uses **ATR** to calculate the ideal Stop Loss and Quantity for your risk.
""")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Configuration")
risk_input = st.sidebar.number_input("Risk Per Trade (INR)", value=1000, step=100)
scan_limit = st.sidebar.slider("Number of stocks to scan", 10, 500, 50)

# --- CORE LOGIC (CACHED) ---
@st.cache_data(ttl=3600) # Cache data for 1 hour
def get_nifty_500_data(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500_df = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500_df['Symbol'].tolist()]
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"] # Fallback
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(symbols[:limit]):
        status_text.text(f"Scanning {ticker} ({i+1}/{limit})...")
        progress_bar.progress((i + 1) / limit)
        
        try:
            df = yf.download(ticker, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            
            # Handle Multi-Index
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
            ma50 = float(df['Close'].rolling(50).mean().iloc[-1])
            ma200 = float(df['Close'].rolling(200).mean().iloc[-1])
            
            # ATR for Stop Loss
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])

            # Signal Check
            if cp > ma20 > ma50 > ma200:
                sl = cp - (2 * atr)
                qty = int(risk_input / (cp - sl)) if (cp - sl) > 0 else 0
                results.append({
                    "Ticker": ticker,
                    "Price": round(cp, 2),
                    "Stop Loss": round(sl, 2),
                    "Qty": qty,
                    "ATR": round(atr, 2)
                })
            time.sleep(0.1) # Small delay for API stability
        except: continue
            
    status_text.text("✅ Scan Complete!")
    return pd.DataFrame(results)

# --- MAIN INTERFACE ---
if st.button("▶️ Start Market Scan"):
    report = get_nifty_500_data(scan_limit)
    
    if not report.empty:
        st.subheader("🔥 Strong Buy Candidates")
        st.dataframe(report, use_container_width=True)
        
        # Download Option
        csv = report.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Results as CSV", data=csv, file_name="nifty_signals.csv", mime="text/csv")
        
        # Charting
        st.divider()
        st.subheader("📊 Visual Chart Confirmation")
        selected_stock = st.selectbox("Select a stock to visualize:", report['Ticker'].tolist())
        
        if selected_stock:
            chart_data = yf.download(selected_stock, period="1y", interval="1d", progress=False)
            if isinstance(chart_data.columns, pd.MultiIndex): chart_data.columns = chart_data.columns.get_level_values(0)
            
            fig, ax = mpf.plot(
                chart_data, type='candle', style='charles', 
                mav=(20, 50, 200), volume=True, returnfig=True,
                figratio=(12, 6), title=f"{selected_stock} Trend Analysis"
                # ... [Keep your imports and session setup from the previous app code] ...

@st.cache_data(ttl=3600)
def run_swing_screener(limit):
    # ... [Keep the symbol loading logic] ...
    
    for i, ticker in enumerate(symbols[:limit]):
        try:
            # We fetch 2 years to get a solid 200MA and 52W High/Low context
            df = yf.download(ticker, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            ma20, ma50, ma200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # --- VOLATILITY PARAMETERS ---
            daily_returns = df['Close'].pct_change().dropna()
            vol_d = daily_returns.std()
            vol_y = vol_d * np.sqrt(252) # Annualized Volatility

            # --- SWING SIGNAL LOGIC ---
            signal = "Neutral"
            if cp > ma20 > ma50 > ma200:
                # If price is within 2% of the 20MA or 50MA, it's a "Pullback Buy" (High Quality Swing)
                proximity_20 = abs(cp - ma20) / ma20
                signal = "Strong Buy (Pullback)" if proximity_20 < 0.02 else "Strong Buy (Extended)"
            
            elif cp < ma20 < ma50 < ma200:
                signal = "Strong Sell"

            if signal != "Neutral":
                results.append({
                    "Ticker": ticker,
                    "Signal": signal,
                    "Price": round(cp, 2),
                    "52W High": round(df['High'].max(), 2),
                    "52W Low": round(df['Low'].min(), 2),
                    "Vol (Yearly)": f"{vol_y:.2%}",
                    "Dist from 52W High": f"{((df['High'].max() - cp) / df['High'].max()):.2%}",
                    "MA 50 Support": round(ma50, 2)
                })
            # ... [Rest of the loop] ...
            )
            st.pyplot(fig)
    else:
        st.warning("No Strong Buy signals found. Try increasing the scan limit!")
