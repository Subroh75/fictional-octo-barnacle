import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG & AI INITIALIZATION ---
st.set_page_config(page_title="Nifty Sniper Elite", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()

# --- 2. THE INTELLIGENCE MODULES ---

def ai_filter_logic(query, df):
    if not ai_active: return df
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"Convert to pandas query: '{query}'. Columns: {list(df.columns)}. Return ONLY code."
    try:
        resp = model.generate_content(prompt)
        return df.query(resp.text.strip().replace('`', '').replace('python', ''))
    except: return df

def summon_council(ticker, row, vix):
    if not ai_active: return "AI Engine Offline."
    model = genai.GenerativeModel('gemini-2.5-flash')
    now = datetime.now().strftime("%B %d, %Y")
    context = f"Ticker: {ticker}, Miro_Score: {row['Miro_Score']}, Trend: {row['Trend']}, Vol_Surge: {row['Vol_Surge']}"
    prompt = f"Date: {now} | Ticker: {ticker} | VIX: {vix}. Perform a Bull/Bear/Risk Manager debate for this Nifty 500 stock."
    try: return model.generate_content(prompt).text
    except: return "Council is currently in recess."

# --- 3. THE MASTER DATA ENGINE (NIFTY 500 DEPTH) ---

@st.cache_data(ttl=3600)
def run_master_scan(limit, vix):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="1y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 50: continue
            
            # RAW MATH BYPASS (Multi-Index Fix)
            c = raw['Close'].values.flatten()
            v = raw['Volume'].values.flatten()
            h = raw['High'].values.flatten()
            l = raw['Low'].values.flatten()
            
            # --- MIROFISH MOMENTUM ---
            avg_vol = np.mean(v[-20:])
            vol_surge = v[-1] / avg_vol if avg_vol > 0 else 0
            p_change = (c[-1] - c[-2]) / c[-2]
            
            miro_score = 0
            if vol_surge > 1.8: miro_score += 5
            if p_change > 0.02: miro_score += 3
            
            # --- TREND RIBBON ---
            m20 = np.mean(c[-20:])
            m50 = np.mean(c[-50:])
            m200 = np.mean(c[-200:]) if len(c) >= 200 else np.mean(c)
            dist_ma20 = ((c[-1] - m20) / m20) * 100
            
            # --- RISK DATA (ATR) ---
            tr = np.maximum(h-l, np.maximum(np.abs(h-pd.Series(c).shift(1)), np.abs(l-pd.Series(c).shift(1))))
            atr = tr.tail(14).mean()

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(c[-1], 2),
                "Miro_Score": miro_score, "Vol_Surge": round(vol_surge, 2),
                "MA 20": round(m20, 2), "MA 200": round(m200, 2), "Dist_MA20 %": round(dist_ma20, 2),
                "ATR": round(atr, 2), "Trend": "🟢 STRONG" if c[-1] > m200 else "⚪ NEUTRAL"
            })
        except: continue
            
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. THE INTERFACE ---

st.sidebar.title("🏹 Nifty Sniper Elite")
vix_val = st.sidebar.number_input("India VIX", value=21.84)
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 INITIALIZE MASTER SCAN"):
    st.cache_data.clear()
    res = run_master_scan(scan_depth, vix_val)
    if not res.empty:
        sl_mult = 3.0 if vix_val > 20 else 2.0
        res['Stop_Loss'] = res['Price'] - (sl_mult * res['ATR'])
        res['Qty'] = (risk_amt / (res['Price'] - res['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['master_results'] = res

if 'master_results' in st.session_state:
    df = st.session_state['master_results']
    
    # Natural Language Screener
    st.subheader("💬 AI Natural Language Screener")
    ai_q = st.text_input("Example: 'Miro_Score > 7 and Sector == \"Financial Services\"'")
    if ai_q: df = ai_filter_logic(ai_q, df)

    tabs = st.tabs(["🎯 Leaderboard", "📈 Trend Ribbon", "📊 Inst. Flow", "🧠 Risk Lab", "🧬 Intelligence Lab"])
    
    with tabs[0]:
        st.dataframe(df.sort_values("Miro_Score", ascending=False), use_container_width=True)
    with tabs[1]:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 200', 'Dist_MA20 %', 'Trend']], use_container_width=True)
    with tabs[2]:
        st.subheader("Volume & Surge Flow")
        st.dataframe(df[['Ticker', 'Vol_Surge', 'Miro_Score', 'Sector']], use_container_width=True)
    with tabs[3]:
        st.subheader("Hedge Fund Risk Desk")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
    with tabs[4]:
        st.subheader("🧬 Intelligence Lab (Supreme Council)")
        target = st.selectbox("Select Ticker for AI Audit", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council Debate"):
            st.markdown(summon_council(target, df[df['Ticker'] == target].iloc[0], vix_val))
else:
    st.info("System Online. Click 'INITIALIZE MASTER SCAN' in Sidebar.")
