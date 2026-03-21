import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG & AI CLIENT ---
st.set_page_config(page_title="Nifty Sniper v7.6", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. TOOL A: EARNINGS FRONT-RUNNER (Fundamental Scraper) ---
def run_earnings_audit(ticker):
    if not client: return "⚠️ AI Engine Offline."
    prompt = f"""
    Act as an Equity Research Analyst. Search for recent India exchange filings (Regulation 30) for {ticker} from the last 30 days.
    Specifically look for: Capacity expansion, new order wins, debt reduction, or management changes.
    Provide:
    1. **Earnings Momentum Score** (-10 to 10).
    2. **Key Catalyst:** Summary of the most important filing found.
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text
    except Exception as e: return f"Audit failed: {e}"

# --- 3. TOOL B: INTELLIGENCE LAB (Tactical Debate) ---
def summon_council(ticker, row, vix):
    if not client: return "⚠️ AI Engine Offline."
    context = f"Ticker: {ticker} | Price: {row['Price']} | VIX: {vix} | ADX: {row['ADX Strength']} | Miro: {row['Miro_Score']}"
    prompt = f"""
    You are a Hedge Fund Committee. Perform a 3-agent debate for {ticker}:
    1. **The Bull:** Momentum and volume thesis.
    2. **The Bear:** Institutional traps and macro risks.
    3. **The Risk Manager:** Stop-loss and position sizing.
    Data: {context}
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text
    except Exception as e: return f"Council in recess: {e}"

# --- 4. MARKET WEATHER STATION (REGIME) ---
def get_market_regime(df):
    total = len(df)
    above_200 = len(df[df['Above_200'] == True])
    panic_stocks = len(df[df['Z-Score'] < -2.0])
    breadth_pct = (above_200 / total) * 100
    panic_pct = (panic_stocks / total) * 100
    
    if breadth_pct > 60: return "🔥 BULL REGIME", "Focus on Miro Score", "success"
    elif breadth_pct < 40 and panic_pct > 15: return "😱 PANIC REGIME", "Focus on Mean Reversion", "error"
    elif breadth_pct < 40: return "❄️ BEAR REGIME", "Cash is King", "warning"
    else: return "⚖️ MILD/NEUTRAL", "Selective Sector Rotation", "info"

# --- 5. DATA ENGINE ---
def calculate_metrics(df):
    try:
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": adx, "z": round(z, 2), "vol_surge": round(vol_surge, 2), "atr": atr.iloc[-1], "above_200": c[-1] > m200}
    except: return None

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    n500 = pd.read_csv(url)
    symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    all_data = []
    prog = st.progress(0, text=f"Deep Audit: {limit} Stocks...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            m = calculate_metrics(raw)
            if m: all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Miro_Score": 10 if m['vol_surge'] > 2 else 2, "Z-Score": m['z'], "Vol_Surge": m['vol_surge'], "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}", "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2), "Above_200": m['above_200']})
        except: continue
    return pd.DataFrame(all_data)

# --- 6. INTERFACE ---
st.title("🏹 Nifty Hedge Fund Master v7.6")

v_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)
v_vix = st.sidebar.number_input("India VIX", value=22.50)
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GLOBAL AUDIT"):
    st.session_state['v76_results'] = run_master_scan(v_depth)

if 'v76_results' in st.session_state:
    df = st.session_state['v76_results']
    regime_name, advice, color = get_market_regime(df)
    st.sidebar.markdown(f"### Weather: {regime_name}")
    getattr(st.sidebar, color)(f"Strategy: {advice}")

    # Risk Logic
    sl_mult = 3.0 if v_vix > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Analysis", "🪃 Mean Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.subheader("Miro Leaderboard")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
    with tabs[1]:
        st.subheader("Structural Trend")
        st.dataframe(df[['Ticker', 'Price', 'ADX Strength', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
    with tabs[2]:
        st.subheader("Mean Reversion")
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Z-Score']], use_container_width=True)
    with tabs[3]:
        st.subheader("🧬 Earnings Front-Runner (Fundamental Audit)")
        target_e = st.selectbox("Select Asset for Filing Scan", df['Ticker'].tolist())
        if st.button("🔍 Run Filing Audit"):
            with st.spinner("Searching Reg 30 Filings..."): st.markdown(run_earnings_audit(target_e))
    with tabs[4]:
        st.subheader("🧠 Intelligence Lab (Tactical Debate)")
        target_i = st.selectbox("Select Asset for Committee Debate", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            with st.spinner("Agents Debating..."): st.markdown(summon_council(target_i, df[df['Ticker'] == target_i].iloc[0], v_vix))
    with tabs[5]:
        st.subheader("Risk Desk")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'ATR']], use_container_width=True)
else:
    st.info("System Ready. Depth: 500.")
