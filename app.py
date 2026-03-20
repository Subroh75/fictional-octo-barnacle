import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG & AI AGENTS ---
st.set_page_config(page_title="Nifty Sniper Elite v6.2", layout="wide")

def initialize_ai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except: return False

ai_active = initialize_ai()

# --- AI AGENT: THE SUPREME COUNCIL ---
def summon_council(ticker, row, vix):
    if not ai_active: 
        return "⚠️ AI Engine Offline. Check Streamlit Secrets."
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    now = datetime.now().strftime("%B %d, %Y")
    
    context = f"""
    Ticker: {ticker} | Price: {row['Price']} 
    Miro_Score: {row['Miro_Score']} | Vol_Surge: {row['Vol_Surge']}
    ADX Strength: {row['ADX Strength']} | Trend Status: {row['Trend Status']}
    VIX: {vix} | Sector: {row['Sector']}
    """
    
    prompt = f"""
    You are a Hedge Fund Committee. Perform a 3-agent debate:
    1. **The Bull:** Argue for the 'Miro Momentum' case.
    2. **The Bear:** Look for overextension or high VIX ({vix}) traps.
    3. **The Risk Manager:** Set a hard stop-loss and position size.
    
    Data: {context}
    """
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Council is in recess: {e}"

# --- 2. NATIVE MATH ENGINE ---

def calculate_adx_native(df, period=14):
    """Calculates ADX and returns a single Strength String"""
    try:
        if len(df) < 30: return "CHOPPY (NaN)", 0
        
        high, low, close = df['High'], df['Low'], df['Close']
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        
        tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(period).mean().iloc[-1]
        
        if pd.isna(adx): return "CHOPPY (NaN)", 0
        
        label = f"💤 WEAK ({round(adx,1)})"
        if adx > 20: label = f"⚡ BUILDING ({round(adx,1)})"
        if adx > 25: label = f"🔥 STRONG ({round(adx,1)})"
        
        return label, adx
    except: return "CHOPPY (NaN)", 0

# --- 3. MASTER DATA ENGINE ---

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "ATHERENERG.NS", "360ONE.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text="Snipering Nifty 500 Market Depth...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 50: continue
            
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            
            c = raw['Close'].values.flatten()
            v = raw['Volume'].values.flatten()
            cp = float(c[-1])

            # Trend Status (Back-end calculation only)
            m200 = np.mean(c[-200:]) if len(c) >= 200 else np.mean(c)
            
            # ADX Logic
            adx_label, adx_val = calculate_adx_native(raw)
            
            # Miro Score Logic
            vol_surge = v[-1] / np.mean(v[-20:])
            p_change = (cp - c[-2]) / c[-2]
            
            miro_score = 0
            if vol_surge > 1.8: miro_score += 5
            if p_change > 0.02: miro_score += 3
            if adx_val > 25: miro_score += 2

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Miro_Score": miro_score, "Vol_Surge": round(vol_surge, 2),
                "ADX Strength": adx_label, "ADX_Val": adx_val,
                "Trend Status": "🟢 BULL" if cp > m200 else "⚪ NEUTRAL",
                "ATR": round(pd.concat([raw['High']-raw['Low'], abs(raw['High']-raw['Close'].shift(1))], axis=1).max(axis=1).tail(14).mean(), 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper Elite v6.2")
st.sidebar.header("Global Controls")
v_vix = st.sidebar.number_input("India VIX", value=21.84)
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 INITIALIZE MASTER SCAN"):
    st.cache_data.clear()
    res = run_master_scan(v_depth)
    if not res.empty:
        sl_mult = 3.0 if v_vix > 20 else 2.0
        res['Stop_Loss'] = res['Price'] - (sl_mult * res['ATR'])
        res['Qty'] = (v_risk / (res['Price'] - res['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['v62_results'] = res

if 'v62_results' in st.session_state:
    df = st.session_state['v62_results']
    
    tabs = st.tabs(["🎯 Miro Score Leaderboard", "🔥 ADX Trend Tracker", "🛡️ Risk Lab", "🧬 Intelligence Lab"])
    
    with tabs[0]:
        st.subheader("Miro Score: Volume & Momentum")
        # Focused only on Miro metrics
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Miro_Score', 'Vol_Surge', 'Sector']], use_container_width=True)
    
    with tabs[1]:
        st.subheader("ADX Momentum Tracker")
        # Replaced MA 20/50/200 with pure ADX Score and Trend Status
        st.dataframe(df.sort_values("ADX_Val", ascending=False)[['Ticker', 'Price', 'ADX Strength', 'Trend Status', 'Sector']], use_container_width=True)
        
    with tabs[2]:
        st.subheader("Hedge Fund Risk Desk")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'ATR']], use_container_width=True)
        
    with tabs[3]:
        st.subheader("🧬 Intelligence Lab (AI Agents)")
        target = st.selectbox("Select Ticker for Audit", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council Debate"):
            with st.spinner(f"Agents are debating {target}..."):
                st.markdown(summon_council(target, df[df['Ticker'] == target].iloc[0], v_vix))
else:
    st.info("System Ready. Click 'INITIALIZE MASTER SCAN' in sidebar.")
