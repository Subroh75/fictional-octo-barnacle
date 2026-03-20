import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG & AI AGENTS ---
st.set_page_config(page_title="Dual-Portfolio Master v6.1", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()

# --- AI AGENT: THE SUPREME COUNCIL ---
def summon_council(ticker, row, vix, strategy="Trend"):
    if not ai_active: 
        return "⚠️ AI Engine Offline. Check Streamlit Secrets."
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    now = datetime.now().strftime("%B %d, %Y")
    
    context = f"""
    Ticker: {ticker} | Price: {row['Price']} | Strategy: {strategy}
    Miro_Score: {row.get('Miro_Score', 'N/A')} | ADX: {row.get('ADX Strength', 'N/A')}
    Z-Score: {row.get('Z-Score', 'N/A')} | RSI: {row.get('RSI', 'N/A')}
    VIX: {vix} | Trend: {row['Trend']} | Vol_Surge: {row.get('Vol_Surge', 'N/A')}
    """
    
    prompt = f"""
    You are a Hedge Fund Committee debating a {strategy} trade.
    1. **The Bull:** Argue for entry based on the specific strategy metrics.
    2. **The Bear:** Look for traps, overextension, or macro headwinds (VIX: {vix}).
    3. **The Risk Manager:** Set a hard stop-loss and position size for this specific setup.
    
    Data: {context}
    """
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Council is in recess: {e}"

# --- 2. THE NATIVE MATH ENGINE ---

def calculate_metrics(df):
    """Calculates all indicators for both Portfolios A & B"""
    try:
        c = df['Close'].values.flatten()
        h = df['High'].values.flatten()
        l = df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        # --- Trend/Sniper Math ---
        m20 = np.mean(c[-20:])
        m200 = np.mean(c[-200:]) if len(c) >= 200 else np.mean(c)
        
        # ADX Calculation
        plus_dm = np.clip(pd.Series(h).diff(), 0, None)
        minus_dm = np.clip((-pd.Series(l).diff()), 0, None)
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(14).mean().iloc[-1]
        
        # --- Mean Reversion Math ---
        z_score = (c[-1] - m20) / np.std(c[-20:])
        
        # RSI Calculation
        delta = pd.Series(c).diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
        
        vol_surge = v[-1] / np.mean(v[-20:])
        
        return {
            "cp": c[-1], "m20": m20, "m200": m200, "adx": adx, 
            "z": round(z_score, 2), "rsi": round(rsi, 1), 
            "vol_surge": round(vol_surge, 2), "atr": atr.iloc[-1]
        }
    except: return None

# --- 3. MASTER DATA ENGINE ---

@st.cache_data(ttl=3600)
def run_master_portfolio_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "360ONE.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Analyzing Market for Trend & Reversion...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 50: continue
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            
            m = calculate_metrics(raw)
            if not m: continue

            # Miro Scoring (Trend-Focused)
            miro = 0
            if m['vol_surge'] > 1.8: miro += 5
            if m['adx'] > 25: miro += 3
            if m['cp'] > m['m20']: miro += 2

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2),
                "Miro_Score": miro, "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}",
                "Z-Score": m['z'], "RSI": m['rsi'], "Vol_Surge": m['vol_surge'], "ATR": round(m['atr'], 2),
                "MA 20": round(m['m20'], 2), "MA 200": round(m['m200'], 2),
                "Trend": "🟢 BULL" if m['cp'] > m['m200'] else "⚪ NEUTRAL"
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Dual-Portfolio Master v6.1")
st.sidebar.header("Global Risk Control")
v_vix = st.sidebar.number_input("India VIX", value=21.84)
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_amt = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 INITIALIZE DUAL SCAN"):
    res = run_master_portfolio_scan(v_depth)
    if not res.empty:
        # Portfolio A Risk (Trend Following)
        res['SL_Trend'] = res['Price'] - (2.5 * res['ATR'])
        # Portfolio B Risk (Mean Reversion - Tighter Stops)
        res['SL_Reversion'] = res['Price'] - (1.5 * res['ATR'])
        st.session_state['master_results'] = res

if 'master_results' in st.session_state:
    df = st.session_state['master_results']
    
    tabA, tabB, tabRisk, tabAI = st.tabs([
        "🎯 PORTFOLIO A: Sniper (Trend)", 
        "🪃 PORTFOLIO B: Reversion (Value)", 
        "🛡️ Advanced Risk Desk", 
        "🧬 Intelligence Lab"
    ])
    
    with tabA:
        st.subheader("High-Conviction Breakouts (Sniper Strategy)")
        # Criteria: ADX Strong + High Miro Score
        sniper_df = df[df['Miro_Score'] >= 5].sort_values("Miro_Score", ascending=False)
        st.dataframe(sniper_df[['Ticker', 'Price', 'Miro_Score', 'ADX Strength', 'Vol_Surge', 'Trend']], use_container_width=True)
        
    with tabB:
        st.subheader("Statistical Mean Reversion (Rubber Band Strategy)")
        # Criteria: Z-Score < -1.8 (Oversold) or RSI < 35
        reversion_df = df[(df['Z-Score'] < -1.8) | (df['RSI'] < 35)].sort_values("Z-Score")
        st.dataframe(reversion_df[['Ticker', 'Price', 'Z-Score', 'RSI', 'Trend', 'Sector']], use_container_width=True)
        
    with tabRisk:
        st.subheader("Cross-Portfolio Risk Management")
        if v_vix > 22: st.warning("⚠️ High VIX: Reduce Portfolio A (Trend) exposure by 40%.")
        st.dataframe(df[['Ticker', 'Price', 'SL_Trend', 'SL_Reversion', 'ATR']], use_container_width=True)
        
    with tabAI:
        st.subheader("🧬 Intelligence Lab (Council Debate)")
        target = st.selectbox("Select Asset for Audit", df['Ticker'].tolist())
        strat = st.radio("Select Strategy to Debate", ["Trend (Portfolio A)", "Mean Reversion (Portfolio B)"])
        if st.button("⚖️ Summon Council"):
            with st.spinner("Agents are debating..."):
                st.markdown(summon_council(target, df[df['Ticker'] == target].iloc[0], v_vix, strat))
else:
    st.info("System Ready. Click 'INITIALIZE DUAL SCAN' to begin.")
