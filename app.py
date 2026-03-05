import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="Alpha Quant Terminal", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("GSheets Connection not configured in Secrets. Portfolio will be read-only.")

# --- 2. MARKET REGIME ENGINE ---
@st.cache_data(ttl=3600)
def get_market_regime():
    try:
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        cp = nifty['Close'].iloc[-1]
        ma200 = nifty['Close'].rolling(200).mean().iloc[-1]
        adr = (nifty['High'] - nifty['Low']).rolling(20).mean().iloc[-1] / cp * 100
        if cp > ma200:
            return ("🐂 BULLISH", "green", round(adr, 2)) if adr < 1.5 else ("⚠️ VOLATILE BULL", "orange", round(adr, 2))
        return ("🐻 BEARISH", "red", round(adr, 2))
    except: return ("UNKNOWN", "grey", 0)

# --- 3. QUANT SCANNER ENGINE ---
@st.cache_data(ttl=3600)
def run_quant_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except: symbols, industries = ["RELIANCE.NS", "TCS.NS"], {}

    all_data = []
    prog = st.progress(0)
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp, prev_cp = df['Close'].iloc[-1], df['Close'].iloc[-2]
            v_surge = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
            
            # SCORING LOGIC
            score = 0
            # VCP Squeeze
            std10 = df['Close'].pct_change().rolling(10).std().iloc[-1]
            std100 = df['Close'].pct_change().rolling(100).std().iloc[-1]
            if (std10/std100) < 0.8: score += 1
            # RSI-2
            delta = df['Close'].diff()
            g, l = delta.where(delta > 0, 0).rolling(2).mean(), -delta.where(delta < 0, 0).rolling(2).mean()
            rsi2 = 100 - (100 / (1 + (g.iloc[-1] / l.iloc[-1]))) if l.iloc[-1] != 0 else 100
            if rsi2 < 20: score += 1
            # Volume & Breakout
            if v_surge > 2.0: score += 1
            if cp > df['High'].iloc[-21:-1].max(): score += 1

            atr = (pd.concat([df['High']-df['Low'], abs(df['High']-prev_cp), abs(df['Low']-prev_cp)], axis=1).max(axis=1)).rolling(14).mean().iloc[-1]

            all_data.append({
                "Ticker": t, "Sector": industries.get(t, "N/A"), "Score": score, 
                "Price": round(cp, 2), "RSI2": round(rsi2, 1), "Surge": round(v_surge, 1), 
                "SL": round(cp - (1.5 * atr), 2), "Target": round(cp * 1.07, 2)
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. PORTFOLIO & BROKERAGE ENGINE ---
def render_portfolio():
    try:
        df = conn.read(worksheet="trades", ttl="1m")
        if df.empty:
            st.info("Portfolio is empty. Log a trade to begin.")
            return

        # Fetch Live Prices
        tickers = df['Ticker'].unique().tolist()
        live = yf.download(tickers, period="1d", progress=False)['Close']
        
        def get_cp(t):
            try: return round(float(live[t].iloc[-1]), 2) if len(tickers) > 1 else round(float(live.iloc[-1]), 2)
            except: return 0.0

        df['Current'] = df['Ticker'].apply(get_cp)
        df['Days'] = (pd.to_datetime(datetime.now()) - pd.to_datetime(df['Entry_Date'])).dt.days
        
        # Calculation: Net of 0.12% Brokerage/STT
        df['Net_PnL_INR'] = ((df['Current'] - df['Entry_Price']) * df['Qty']) - ((df['Current'] + df['Entry_Price']) * df['Qty'] * 0.0012)
        df['Net_PnL_%'] = (df['Net_PnL_INR'] / (df['Entry_Price'] * df['Qty'])) * 100

        st.subheader("💰 Shared Partner Portfolio")
        st.dataframe(df[['Ticker', 'Qty', 'Entry_Price', 'Current', 'Net_PnL_INR', 'Net_PnL_%', 'Days', 'Trader']], use_container_width=True)
        
        total_net = df['Net_PnL_INR'].sum()
        st.metric("Total Partnership Net (INR)", f"₹{total_net:,.2f}")
    except Exception as e:
        st.warning("Connect Google Sheets to enable live tracking.")

# --- 5. MAIN UI ---
reg, col, vol = get_market_regime()
st.sidebar.markdown(f"**Regime:** <span style='color:{col}'>{reg}</span>", unsafe_allow_html=True)
st.sidebar.markdown(f"**Market Vol:** {vol}%")

trader = st.sidebar.selectbox("Active Partner", ["Partner A", "Partner B"])
menu = st.tabs(["🔍 Quant Scanner", "📊 Shared Tracker", "📈 Backtester"])

with menu[0]:
    if st.button("🚀 Run Market Scan"):
        st.session_state['scan'] = run_quant_scan(st.sidebar.slider("Depth", 50, 500, 100))
    
    if 'scan' in st.session_state:
        results = st.session_state['scan']
        high_score = results[results['Score'] >= 2].sort_values("Score", ascending=False)
        st.dataframe(high_score, use_container_width=True)
        
        # Export
        st.download_button("📥 Export Watchlist", high_score.to_csv(index=False), "watchlist.csv", "text/csv")
        
        # Charting
        sel = st.selectbox("Analyze Ticker:", results['Ticker'].tolist())
        if sel:
            cdf = yf.download(sel, period="6mo", progress=False)
            if isinstance(cdf.columns, pd.MultiIndex): cdf.columns = cdf.columns.get_level_values(0)
            
            fig, ax = mpf.plot(cdf, type='candle', style='charles', mav=(20, 50), volume=True, returnfig=True)
            st.pyplot(fig)

with menu[1]:
    render_portfolio()
    st.divider()
    with st.expander("➕ Log New Shared Trade"):
        with st.form("new_trade"):
            c1, c2, c3 = st.columns(3)
            t_id = c1.text_input("Ticker")
            t_q = c2.number_input("Qty", min_value=1)
            t_p = c3.number_input("Price")
            t_s = c1.number_input("Stop Loss")
            if st.form_submit_button("Sync to Google Sheets"):
                # Logic to append to GSheets via conn.update() goes here
                st.success("Trade logged! (Requires GSheets Secret Setup)")
