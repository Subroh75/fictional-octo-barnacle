import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import plotly.express as px
import time

st.set_page_config(page_title="Alpha Ignition", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("⚡ Momentum Controls")
risk_amt = st.sidebar.number_input("Risk (INR)", value=1000)
scan_num = st.sidebar.slider("Scan Depth", 10, 500, 100)

@st.cache_data(ttl=3600)
def fetch_data(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        industries = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols, industries = ["RELIANCE.NS", "TCS.NS"], {}

    results = []
    prog = st.progress(0)
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", interval="1d", progress=False)
            if df.empty or len(df) < 50: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp, prev_cp = float(df['Close'].iloc[-1]), float(df['Close'].iloc[-2])
            ma20, ma50, ma200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            
            # RSI
            delta = df['Close'].diff()
            gain, loss = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1]))) if loss.iloc[-1] != 0 else 100
            
            # Momentum / NR7
            df['Range'] = df['High'] - df['Low']
            nr7 = df['Range'].iloc[-1] == df['Range'].iloc[-7:].min()
            h20, l20 = df['High'].iloc[-21:-1].max(), df['Low'].iloc[-21:-1].min()
            v_surge = df['Volume'].iloc[-1] / df['Volume'].iloc[-21:-1].mean()
            
            # Signal Engine
            sig = "Neutral"
            if cp > h20 and v_surge > 1.5: sig = "🚀 IGNITION" if nr7 else "⚡ BURST"
            elif cp > ma20 > ma50 > ma200: sig = "📈 TREND UP"
            elif cp < l20 and v_surge > 1.5: sig = "📉 BREAKDOWN"
            elif cp < ma20 < ma50 < ma200: sig = "🔻 STRONG SELL"

            atr = (pd.concat([df['High']-df['Low'], abs(df['High']-prev_cp), abs(df['Low']-prev_cp)], axis=1).max(axis=1)).rolling(14).mean().iloc[-1]
            sl = cp + (1.5 * atr) if "SELL" in sig or "BREAKDOWN" in sig else cp - (1.5 * atr)

            results.append({"Ticker": t, "Sector": industries.get(t, "N/A"), "Price": round(cp, 2), "RSI": round(rsi, 2), "Signal": sig, "Surge": round(v_surge, 1), "SL": round(sl, 2), "52W_H": round(df['High'].max(), 2)})
            time.sleep(0.01)
        except: continue
    return pd.DataFrame(results)

st.title("🏹 Alpha Ignition Suite")
if st.button("🔍 Run Global Scan"):
    st.session_state['res'] = fetch_data(scan_num)

if 'res' in st.session_state:
    res = st.session_state['res']
    t1, t2, t3 = st.tabs(["🚀 Long", "📉 Short", "📊 Sectors"])
    with t1:
        st.dataframe(res[res['Signal'].str.contains("IGNITION|BURST|UP", na=False)], use_container_width=True)
    with t2:
        st.dataframe(res[res['Signal'].str.contains("BREAKDOWN|SELL", na=False)], use_container_width=True)
    with t3:
        if not res.empty: st.plotly_chart(px.histogram(res[res['Signal'] != "Neutral"], x="Sector", color="Signal"), use_container_width=True)

    st.divider()
    sel = st.selectbox("Chart:", res['Ticker'].tolist())
    if sel:
        cdf = yf.download(sel, period="6mo", progress=False)
        if isinstance(cdf.columns, pd.MultiIndex): cdf.columns = cdf.columns.get_level_values(0)
        fig, ax = mpf.plot(cdf, type='candle', style='charles', mav=(20, 50), volume=True, returnfig=True)
        st.pyplot(fig)
