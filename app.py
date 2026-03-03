import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
import time

st.set_page_config(page_title="Nifty 500 Momentum Suite", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("⚡ Momentum Controls")
risk_amt = st.sidebar.number_input("Risk per Trade (INR)", value=1000)
scan_num = st.sidebar.slider("Scan Depth", 10, 500, 100)
chase_limit = st.sidebar.slider("Max Day % Change (Avoid Chasing)", 1.0, 10.0, 5.0)

@st.cache_data(ttl=3600)
def fetch_momentum_data(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS"]
        industries = {}

    all_data = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(symbols[:limit]):
        progress.progress((i + 1) / limit)
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 50: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            # --- Technicals ---
            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            day_change = ((cp - prev_cp) / prev_cp) * 100
            
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma50 = df['Close'].rolling(50).mean().iloc[-1]
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            
            # --- Momentum & NR7 Logic ---
            df['Range'] = df['High'] - df['Low']
            is_nr7 = df['Range'].iloc[-1] == df['Range'].iloc[-7:].min()
            
            recent_high_20 = df['High'].iloc[-21:-1].max()
            avg_vol = df['Volume'].iloc[-21:-1].mean()
            curr_vol = df['Volume'].iloc[-1]
            
            # --- 52W & Volatility ---
            high_52w = df['High'].max()
            dist_52w = ((high_52w - cp) / high_52w) * 100
            vol_y = df['Close'].pct_change().std() * np.sqrt(252)

            # --- Signal Classification ---
            status = "Neutral"
            if cp > recent_high_20 and curr_vol > (avg_vol * 2):
                status = "⚡ MOMENTUM BURST"
                if is_nr7: status = "🚀 EXPLOSIVE IGNITION"
            elif cp > ma20 > ma50 > ma200:
                status = "📈 TRENDING UP"

            # Position Sizing (ATR)
            tr = pd.concat([df['High']-df['Low'], abs(df['High']-prev_cp), abs(df['Low']-prev_cp)], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            sl = cp - (1.5 * atr) # Tighter SL for momentum
            qty = int(risk_amt / (cp - sl)) if (cp - sl) > 0 else 0

            all_data.append({
                "Ticker": ticker,
                "Industry": industries.get(ticker, "N/A"),
                "Price": round(cp, 2),
                "Day %": round(day_change, 2),
                "Signal": status,
                "Action": "⚠️ TOO LATE" if day_change > chase_limit else "✅ BUY ZONE",
                "Vol Surge": round(curr_vol/avg_vol, 1),
                "Dist 52W High %": round(dist_52w, 2),
                "Stop Loss": round(sl, 2),
                "Qty": qty,
                "Vol Yearly": f"{vol_y:.2%}"
            })
            time.sleep(0.05)
        except: continue
    return pd.DataFrame(all_data)

# --- APP LAYOUT ---
st.title("🏹 Nifty 500 Alpha Ignition Dashboard")

if st.button("🔍 Scan for Momentum"):
    st.session_state['data'] = fetch_momentum_data(scan_num)

if 'data' in st.session_state:
    df_res = st.session_state['data']
    
    t1, t2, t3 = st.tabs(["⚡ Ignition Scanner", "🛡️ Trend Watch", "📊 Sector Pulse"])

    with t1:
        st.subheader("High-Velocity Momentum Plays")
        # Filter for Bursts/Ignition
        ign_df = df_res[df_res['Signal'].str.contains("MOMENTUM|EXPLOSIVE", na=False)].copy()
        st.dataframe(ign_df.sort_values(by="Vol Surge", ascending=False), use_container_width=True)

    with t2:
        st.subheader("Steady Trend Pullbacks")
        trend_df = df_res[df_res['Signal'] == "📈 TRENDING UP"].copy()
        st.dataframe(trend_df, use_container_width=True)

    with t3:
        st.subheader("Sector Leadership")
        top_sectors = df_res[df_res['Signal'] != "Neutral"]['Industry'].value_counts().reset_index()
        fig = px.bar(top_sectors, x='Industry', y='count', color='count', title="Sectors with Strongest Momentum")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    selected = st.selectbox("Analyze Setup:", df_res['Ticker'].tolist())
    if selected:
        c_df = yf.download(selected, period="6mo", interval="1d", progress=False)
        if isinstance(c_df.columns, pd.MultiIndex): c_df.columns = c_df.columns.get_level_values(0)
        # Add 7-day Range for visual NR7 check
        
        fig, ax = mpf.plot(c_df, type='candle', style='charles', mav=(20, 50), volume=True, returnfig=True, title=f"{selected} Momentum Check")
        st.pyplot(fig)
