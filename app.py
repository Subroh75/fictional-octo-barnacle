import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG & AI CLIENT ---
st.set_page_config(page_title="Nifty Hedge Fund Master v7.5.1", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            # Using new 2026 google-genai SDK
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. AI ENGINE: FRONT-RUNNER & COUNCIL ---
def summon_council(ticker, row, vix):
    if not client: return "⚠️ AI Engine Offline. Check Secrets."
    
    # AI performs a 'Search' for latest filings and news
    prompt = f"""
    You are a Hedge Fund Committee Audit for {ticker}.
    1. Search for recent India exchange filings (Reg 30) or news from the last 30 days.
    2. Look for keywords: 'Capacity Expansion', 'Order Book', 'Debt reduction', 'Market share'.
    3. Give an 'Earnings Momentum' score (-10 to 10).
    4. Debate the trade: Bull (Momentum), Bear (Institutional Trap), Risk Manager (Stop-Loss).
    Context: Price {row['Price']}, VIX {vix}, ADX {row['ADX Strength']}, Miro {row['Miro_Score']}.
    """
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"Council is in recess: {e}"

# --- 3. MARKET WEATHER STATION (REGIME) ---
def get_market_regime(df):
    total = len(df)
    above_200 = len(df[df['Above_200'] == True])
    panic_stocks = len(df[df['Z-Score'] < -2.0])
    
    breadth_pct = (above_200 / total) * 100
    panic_pct = (panic_stocks / total) * 100
    
    if breadth_pct > 60:
        return "🔥 BULL REGIME", "Focus on Miro Score (Breakouts)", "success"
    elif breadth_pct < 40 and panic_pct > 15:
        return "😱 PANIC REGIME", "Focus on Mean Reversion (Deep Value)", "error"
    elif breadth_pct < 40:
        return "❄️ BEAR REGIME", "Capital Preservation: Cash is King", "warning"
    else:
        return "⚖️ MILD/NEUTRAL", "Selective Trading: Sector Rotation", "info"

# --- 4. HEDGE FUND MATH ENGINE ---
def calculate_metrics(df):
    try:
        c = df['Close'].values.flatten()
        h = df['High'].values.flatten()
        l = df['Low'].values.flatten()
        
        m20 = np.mean(c[-20:]); m50 = np.mean(c[-50:]); m200 = np.mean(c[-200:])
        
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        
        return {
            "cp": c[-1], "m20": m20, "m50": m50, "m200": m200, 
            "adx": adx, "z": round(z, 2), "vol_surge": round(vol_surge, 2), 
            "atr": atr.iloc[-1], "above_200": c[-1] > m200
        }
    except: return None

# --- 5. DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_institutional_flow():
    # NSE Data as of March 20, 2026
    return pd.DataFrame({
        "Metric": ["FII Net (Cr)", "DII Net (Cr)", "Sentiment"],
        "Value": ["-5,518.39", "+5,706.23", "⚖️ Tug of War"]
    })

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text=f"Analyzing {limit} Stocks...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 200: continue
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            
            m = calculate_metrics(raw)
            if not m: continue

            miro = 0
            if m['vol_surge'] > 1.8: miro += 5
            if m['adx'] > 25: miro += 3
            
            p_change = (m['cp'] - raw['Close'].iloc[-2]) / raw['Close'].iloc[-2]
            if p_change > 0.01 and m['vol_surge'] > 2.0: reco = "🔥 AGGRESSIVE BUY"
            elif m['z'] < -2.0: reco = "🪃 MEAN REVERSION"
            elif p_change > 0 and m['vol_surge'] > 1.2: reco = "💎 ACCUMULATE"
            else: reco = "💤 NEUTRAL"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2),
                "Recommendation": reco, "Miro_Score": miro, "Z-Score": m['z'], 
                "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}",
                "Vol_Surge": m['vol_surge'], "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2),
                "ATR": round(m['atr'], 2), "Above_200": m['above_200']
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 6. INTERFACE ---
st.title("🏹 Nifty Hedge Fund Master v7.5.1")

# Sidebar: Institutional Pulse + Regime
st.sidebar.subheader("🏦 Institutional Pulse")
st.sidebar.table(fetch_institutional_flow())
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)
v_vix = st.sidebar.number_input("India VIX", value=22.80)
v_risk = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE MASTER SCAN"):
    st.session_state['v751_results'] = run_master_scan(v_depth)

if 'v751_results' in st.session_state:
    df = st.session_state['v751_results']
    
    # APPLY MARKET REGIME
    regime_name, advice, color = get_market_regime(df)
    st.sidebar.markdown(f"### Weather: {regime_name}")
    getattr(st.sidebar, color)(f"Strategy: {advice}")

    # Calculate Risk Data
    sl_mult = 3.0 if v_vix > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Analysis", "🪃 Mean Reversion", "🧬 Earnings Front-Runner", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.subheader("Miro Leaderboard (Momentum)")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Recommendation', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
    
    with tabs[1]:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'ADX Strength', 'MA 20', 'MA 50', 'MA 200', 'Sector']], use_container_width=True)

    with tabs[2]:
        st.subheader("Mean Reversion (Z-Score)")
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Recommendation', 'Z-Score', 'Sector']], use_container_width=True)

    with tabs[3]:
        st.subheader("🧠 Intelligence Lab (Front-Runner Audit)")
        target = st.selectbox("Select Asset for Deep Audit", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council Debate"):
            with st.spinner(f"AI scanning filings and debating {target}..."):
                st.markdown(summon_council(target, df[df['Ticker'] == target].iloc[0], v_vix))

    with tabs[4]:
        st.subheader("Hedge Fund Risk Desk")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'ATR']], use_container_width=True)
else:
    st.info("System Ready. Depth set to 500.")
