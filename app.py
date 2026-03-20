import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- 1. CONFIG & AI AGENTS ---
st.set_page_config(page_title="Nifty Sniper Elite v5.1", layout="wide")

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
    if not ai_active: return "⚠️ AI Engine Offline. Check Secrets."
    model = genai.GenerativeModel('gemini-2.0-flash')
    now = datetime.now().strftime("%B %d, %Y")
    
    context = f"""
    Ticker: {ticker}
    Price: {row['Price']} | Signal: {row['Signal']}
    Miro_Score: {row['Miro_Score']} | ADX: {row['ADX']}
    Trend: {row['Trend']} | Vol_Surge: {row['Vol_Surge']}
    VIX: {vix}
    """
    
    prompt = f"""
    Date: {now}. You are a Hedge Fund Committee. 
    Perform a 3-agent debate on the following data:
    1. **The Bull:** Argues for the 'Aggressive Buy' case.
    2. **The Bear:** Looks for the 'Institutional Trap' or fakeout.
    3. **The Risk Manager:** Sets a hard stop-loss based on VIX {vix}.
    
    Data: {context}
    """
    try:
        resp = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"Council is currently unavailable: {e}"

# --- 2. NATIVE MATH ENGINE (ADX & TREND) ---

def calculate_adx_native(df, period=14):
    high, low, close = df['High'], df['Low'], df['Close']
    plus_dm = high.diff(); minus_dm = low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
    tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (pd.Series(plus_dm).rolling(period).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm).rolling(period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    return round(adx.iloc[-1], 1), round(plus_di.iloc[-1], 1), round(minus_di.iloc[-1], 1)

# --- 3. THE DATA SCANNER (NIFTY 500) ---

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
    prog = st.progress(0, text="Snipering Nifty 500 Depth...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="1y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 50: continue
            
            # Flattening
            df = pd.DataFrame(index=raw.index)
            df['Close'] = raw['Close'].values.flatten()
            df['High'] = raw['High'].values.flatten()
            df['Low'] = raw['Low'].values.flatten()
            df['Volume'] = raw['Volume'].values.flatten()

            cp = float(df['Close'].iloc[-1])
            
            # --- TREND DESK ---
            m20 = np.mean(df['Close'].values[-20:])
            m50 = np.mean(df['Close'].values[-50:])
            m200 = np.mean(df['Close'].values[-200:]) if len(df) >= 200 else np.mean(df['Close'].values)
            
            # --- ADX DESK ---
            adx, d_plus, d_minus = calculate_adx_native(df)

            # --- FLOW & MIRO DESK ---
            vol_surge = df['Volume'].iloc[-1] / np.mean(df['Volume'].values[-20:])
            p_change = (cp - df['Close'].iloc[-2]) / df['Close'].iloc[-2]
            
            miro_score = 0
            if vol_surge > 1.8: miro_score += 5
            if p_change > 0.02: miro_score += 3
            if adx > 25: miro_score += 2

            # Institutional Signal Logic
            if p_change > 0.01 and vol_surge > 2.0: signal = "🔥 AGGRESSIVE BUY"
            elif p_change < -0.01 and vol_surge > 2.0: signal = "⚠️ INST. EXIT"
            elif p_change > 0 and vol_surge > 1.2: signal = "💎 ACCUMULATE"
            else: signal = "💤 NEUTRAL"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Signal": signal, "Miro_Score": miro_score, "ADX": adx, 
                "D+": d_plus, "D-": d_minus, "Vol_Surge": round(vol_surge, 2),
                "MA 20": round(m20, 2), "MA 50": round(m50, 2), "MA 200": round(m200, 2),
                "Trend": "🟢 BULL" if cp > m200 else "⚪ NEUTRAL"
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.sidebar.title("🏹 Nifty Sniper Elite")
v_vix = st.sidebar.number_input("India VIX", value=21.84)
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 100)

if st.sidebar.button("🚀 INITIALIZE MASTER SCAN"):
    st.cache_data.clear()
    res = run_master_scan(v_depth)
    if not res.empty:
        st.session_state['master_results'] = res

if 'master_results' in st.session_state:
    df = st.session_state['master_results']
    
    tabs = st.tabs(["🎯 Miro & Flow", "📈 Trend Ribbon", "🧬 Alpha Desk", "🧬 Intelligence Lab"])
    
    with tabs[0]:
        st.subheader("Momentum & Institutional Flow")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Signal', 'Miro_Score', 'Vol_Surge', 'Price']], use_container_width=True)
    
    with tabs[1]:
        st.subheader("Structural Ribbon (20/50/200)")
        st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200', 'Trend']], use_container_width=True)
        
    with tabs[2]:
        st.subheader("ADX Trend Strength")
        st.dataframe(df.sort_values("ADX", ascending=False)[['Ticker', 'ADX', 'D+', 'D-', 'Signal']], use_container_width=True)
        
    with tabs[3]:
        st.subheader("🧬 Supreme Judge Council (AI Agents)")
        target = st.selectbox("Select Ticker for AI Audit", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council Debate"):
            with st.spinner(f"Agents are debating {target}..."):
                debate = summon_council(target, df[df['Ticker'] == target].iloc[0], v_vix)
                st.markdown(debate)
else:
    st.info("System Ready. Run Master Scan from Sidebar.")
