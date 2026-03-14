import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpha Command Center", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE MASTER UNIFIED ENGINE ---
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
        symbols, sector_map, nifty_perf_1m = ["RELIANCE.NS", "TCS.NS"], {}, 0

    all_data = []
    prog = st.progress(0, text="Synchronizing Trend, Quant, & Institutional Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

            # --- CORE TECHNICALS ---
            cp = float(df['Close'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            open_p = float(df['Open'].iloc[-1])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]

            # --- LOGIC 1: TREND & MA ---
            if cp > m20 > m50 > m200: ma_action = "🟢 STRONG BUY"
            elif cp > m50 > m200: ma_action = "🟡 HOLD"
            else: ma_action = "🔴 AVOID"
            dist_m20 = ((cp - m20) / m20) * 100

            # --- LOGIC 2: QUANT GENIUS (RS & VCP) ---
            rs_score = ((cp / float(df['Close'].iloc[-21])) - 1) - nifty_perf_1m
            high_low = df['High'] - df['Low']
            df['TR'] = np.maximum(high_low, np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            df['ATR'] = df['TR'].rolling(14).mean()
            atr_ratio = df['ATR'].iloc[-1] / df['ATR'].rolling(50).mean().iloc[-1]

            # --- LOGIC 3: INSTITUTIONAL & GAPS ---
            body_size = abs(cp - open_p)
            avg_range = (df['High'] - df['Low']).rolling(10).mean().iloc[-1]
            is_acc = (vol > 1.5 * avg_vol and body_size < 0.3 * avg_range)
            gap_pct = ((open_p - prev_cp) / prev_cp) * 100

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "MA_Action": ma_action, "Dist_MA20_%": round(dist_m20, 2),
                "RS_Score": round(rs_score * 100, 2), "Tightness": "🎯 TIGHT" if atr_ratio < 0.9 else "🌊 LOOSE",
                "Footprint": "👣 ACCUMULATION" if is_acc else "Normal",
                "Gap_Signal": "🚀 PRO GAP" if (gap_pct > 1.0 and cp >= open_p) else "None",
                "Above_50MA": 1 if cp > m50 else 0, "ATR_Val": float(df['ATR'].iloc[-1]),
                "Vol_Ratio": round(vol/avg_vol, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI RENDER ---
st.sidebar.title("🏹 Alpha Master V5")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (₹)", value=5000)

if st.sidebar.button("🚀 EXECUTE FULL COMMAND SCAN"):
    st.session_state['scan_results'] = run_full_scan(depth)

if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    df['Stop_Loss'] = df['Price'] - (2 * df['ATR_Val'])
    df['Qty'] = (risk_amt / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🌍 Birds-Eye", "📈 Trend Action", "🧠 Quant Lab", "📉 Breadth", "👣 Inst. Flow", "🚀 Gap-Ups", "🔗 Correlation"])

    with tabs[0]:
        fig = px.treemap(df, path=['Sector', 'Ticker'], values=np.abs(df['RS_Score']), color='RS_Score', color_continuous_scale='RdYlGn', height=600)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.subheader("MA Trend Alignment")
        st.dataframe(df[['Ticker', 'Price', 'MA_Action', 'Dist_MA20_%']].sort_values("MA_Action"), use_container_width=True)
        st.markdown("### 📖 Logic: Look for 🟢 STRONG BUY with Dist_MA20 between 0-3%.")
        

    with tabs[2]:
        st.subheader("RS & Risk Management")
        st.dataframe(df[['Ticker', 'RS_Score', 'Tightness', 'Stop_Loss', 'Qty']].sort_values("RS_Score", ascending=False), use_container_width=True)
        st.markdown("### 📖 Logic: Focus on Positive RS Score + 🎯 TIGHT (VCP Pattern).")

    with tabs[3]:
        breadth = (df['Above_50MA'].sum() / len(df)) * 100
        st.metric("Market Breadth (>50MA)", f"{round(breadth, 1)}%")
        st.progress(breadth/100)
        st.markdown("### 📖 Logic: If Breadth > 80%, stop buying. If < 20%, start looking for long-term entries.")
        

    with tabs[4]:
        st.subheader("Institutional Footprint Tracking")
        st.dataframe(df[df['Footprint'] == "👣 ACCUMULATION"][['Ticker', 'Sector', 'Vol_Ratio']], use_container_width=True)
        st.markdown("### 📖 Logic: High Volume + Tight Price Range = Institutional Accumulation.")
        

    with tabs[5]:
        st.subheader("Opening Bell Gaps")
        st.dataframe(df[df['Gap_Signal'] == "🚀 PRO GAP"], use_container_width=True)
        st.markdown("### 📖 Logic: Gaps that don't fill in the first 30 mins signal extreme urgency.")

    with tabs[6]:
        st.subheader("Concentration Risk")
        st.bar_chart(df.groupby('Sector')['Ticker'].count())
        st.info("Ensure you are not over-exposed to a single sector.")

else:
    st.info("Run the Command Scan to populate all 7 modules.")
