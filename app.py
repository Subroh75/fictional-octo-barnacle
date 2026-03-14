import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Alpha Command Center V6", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE MASTER ENGINE ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        symbols, sector_map, nifty_perf_1m = ["RELIANCE.NS"], {}, 0

    all_data = []
    prog = st.progress(0, text="Calculating Confluence Scores...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            # Technicals
            cp = float(df['Close'].iloc[-1])
            open_p = float(df['Open'].iloc[-1])
            prev_cp = float(df['Close'].iloc[-2])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            vol, avg_vol = float(df['Volume'].iloc[-1]), df['Volume'].rolling(20).mean().iloc[-1]

            # 1. Trend Score (Max 3)
            trend_score = 0
            if cp > m20: trend_score += 1
            if m20 > m50: trend_score += 1
            if m50 > m200: trend_score += 1

            # 2. Quant Score (Max 3)
            quant_score = 0
            rs_val = ((cp / float(df['Close'].iloc[-21])) - 1) - nifty_perf_1m
            if rs_val > 0: quant_score += 1
            
            high_low = df['High'] - df['Low']
            df['TR'] = np.maximum(high_low, np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            df['ATR'] = df['TR'].rolling(14).mean()
            atr_ratio = df['ATR'].iloc[-1] / df['ATR'].rolling(50).mean().iloc[-1]
            if atr_ratio < 0.9: quant_score += 2 # VCP is weighted higher

            # 3. Institutional Score (Max 4)
            inst_score = 0
            body_size = abs(cp - open_p)
            avg_range = (df['High'] - df['Low']).rolling(10).mean().iloc[-1]
            if vol > 1.5 * avg_vol and body_size < 0.3 * avg_range: inst_score += 2
            if (open_p - prev_cp)/prev_cp > 0.01 and cp >= open_p: inst_score += 2

            total_score = trend_score + quant_score + inst_score

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": total_score, "MA_Action": "🟢 STRONG" if trend_score == 3 else "🟡 WEAK",
                "RS_Score": round(rs_val * 100, 2), "Tightness": "🎯 TIGHT" if atr_ratio < 0.9 else "🌊 LOOSE",
                "Footprint": "👣 ACCUM" if inst_score >= 2 else "Normal",
                "Above_50MA": 1 if cp > m50 else 0, "ATR_Val": float(df['ATR'].iloc[-1])
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 3. UI ---
st.sidebar.title("🏹 Alpha Master V6")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Amount (₹)", value=5000)

if st.sidebar.button("🚀 EXECUTE CONFLUENCE SCAN"):
    st.session_state['scan_results'] = run_full_scan(depth)

if not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    df['Stop_Loss'] = df['Price'] - (2 * df['ATR_Val'])
    df['Qty'] = (risk_amt / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🌍 Birds-Eye", "📈 Trend Action", "🧠 Quant & Confluence", "📉 Breadth", "👣 Inst. Flow", "🚀 Gap-Ups", "🔗 Correlation"])

    with tabs[2]:
        st.subheader("The Confluence Leaderboard")
        st.write("Ranking stocks by Trend + Quant + Institutional alignment.")
        # Highlight Top Scores
        st.dataframe(df[['Ticker', 'Score', 'RS_Score', 'Tightness', 'Footprint', 'Qty']].sort_values("Score", ascending=False), use_container_width=True)
        
        st.markdown("""
        ---
        ### 📖 Scoring Guide
        * **Score 8-10:** 🔥 **Triple Confluence.** Institutional buying in a tight VCP pattern within a strong uptrend.
        * **Score 5-7:** ✅ **High Probability.** Good trend and momentum, missing either tightness or high-volume footprint.
        * **Score < 4:** ⚠️ **Speculative.** Lacks structural support.
        """)
        

    # ... (Keep other tab content same as V5)
    with tabs[1]:
        st.dataframe(df[['Ticker', 'Price', 'MA_Action', 'Score']].sort_values("Score", ascending=False), use_container_width=True)
        
    
    with tabs[3]:
        breadth = (df['Above_50MA'].sum() / len(df)) * 100
        st.metric("Market Breadth (>50MA)", f"{round(breadth, 1)}%")
        

else:
    st.info("Run scan to calculate Confluence Scores.")
