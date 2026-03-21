import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG & AI CLIENT ---
st.set_page_config(page_title="Nifty Sniper v7.9.3", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. HEDGE FUND MATH ENGINE ---
def calculate_metrics(df):
    try:
        # 2026 yfinance MultiIndex Flattening
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        
        # ATR & ADX
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        
        reco = "💤 NEUTRAL"
        if (c[-1]-c[-2])/c[-2] > 0.02 and vol_surge > 2.0: reco = "🚀 STRONG BUY"
        elif z < -2.2: reco = "🪃 REVERSION BUY"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": adx, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "reco": reco}
    except: return None

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "SBIN.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Deep Market Audit...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True, multi_level_index=False)
            m = calculate_metrics(raw)
            if m:
                all_data.append({"Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2), 
                                   "Recommendation": m['reco'], "Z-Score": m['z'], "Vol_Surge": m['vol_surge'], 
                                   "ADX": round(m['adx'], 1), "MA 20": round(m['m20'], 2), 
                                   "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2)})
        except: continue
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper v7.9.3")

# Sidebar
st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(pd.DataFrame({"Metric": ["FII Net", "DII Net"], "Value": ["-5,518.39", "+5,706.23"]}))
v_vix = st.sidebar.number_input("India VIX", value=22.81)
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(500)
    if not res.empty: st.session_state['v793_res'] = res

if 'v793_res' in st.session_state:
    df = st.session_state['v793_res']
    
    # Sidebar Weather
    above_200 = len(df[df['MA 200'] < df['Price']])
    breadth = (above_200 / len(df)) * 100
    st.sidebar.markdown(f"### 🌡️ Market Weather")
    if breadth > 60: st.sidebar.success("🔥 BULL REGIME")
    elif breadth < 40: st.sidebar.warning("❄️ BEAR REGIME")
    else: st.sidebar.info("⚖️ NEUTRAL")

    # Risk Calculation
    sl_mult = 3.0 if v_vix > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.dataframe(df.sort_values("Vol_Surge", ascending=False)[['Ticker', 'Price', 'Recommendation', 'Vol_Surge', 'Sector']], use_container_width=True)
    with tabs[1]:
        st.dataframe(df[['Ticker', 'Price', 'ADX', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
    with tabs[2]:
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Recommendation', 'Z-Score']], use_container_width=True)
    
    with tabs[3]: # EARNINGS FRONT-RUNNER
        st.subheader("🧬 Earnings Front-Runner (Filing Scan)")
        t_e = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="e_box")
        if st.button("🔍 Run Fundamental Audit"):
            if client:
                with st.spinner(f"Analyzing Reg 30 filings for {t_e}..."):
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Search recent India Reg 30 filings for {t_e} from last 30 days. Identify catalysts like expansion or order wins.").text
                    st.markdown(res)
            else: st.error("API Key missing.")

    with tabs[4]: # INTELLIGENCE LAB
        st.subheader("🧠 Intelligence Lab (Tactical Debate)")
        t_i = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="i_box")
        if st.button("⚖️ Summon Council"):
            if client:
                with st.spinner(f"Agents debating {t_i}..."):
                    res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Hedge Fund Debate for {t_i}. Provide 3 agents: Bull, Bear, and Risk Manager viewpoints.").text
                    st.markdown(res)
            else: st.error("API Key missing.")

    with tabs[5]: # RISK LAB
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'ATR']], use_container_width=True)
else:
    st.info("Scanner Ready. Click 'EXECUTE GLOBAL SCAN' in the sidebar.")
