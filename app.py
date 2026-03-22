import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import requests
import io
from datetime import datetime

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Nifty Sniper Elite v14.0", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. CSS COLOR INJECTION (Green/Red/Amber) ---
def highlight_reco(val):
    color = '#2ecc71' if 'BUY' in val else '#e74c3c' if 'SELL' in val else '#f1c40f'
    return f'background-color: {color}; color: black; font-weight: bold'

# --- 3. LIVE NIFTY 500 CONSTITUENT FETCH ---
@st.cache_data(ttl=86400)
def get_live_nifty_500():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        response = requests.get(url, headers=headers)
        df_n500 = pd.read_csv(io.StringIO(response.text))
        symbols = [s + ".NS" for s in df_n500['Symbol'].tolist()]
        sectors = dict(zip(df_n500['Symbol'] + ".NS", df_n500['Industry']))
        return symbols, sectors
    except:
        core = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ADANIPOWER.NS"]
        return core, {s: "Core Market" for s in core}

# --- 4. THE UNSHRUNK MATH ENGINE ---
def calculate_metrics(df, ticker):
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, level=1, axis=1)
            else:
                df.columns = df.columns.get_level_values(0)

        df.columns = [str(c).capitalize() for c in df.columns]
        c, h, l, v = df['Close'].values.flatten(), df['High'].values.flatten(), df['Low'].values.flatten(), df['Volume'].values.flatten()
        
        if len(c) < 200: return None

        # Technical Indicators
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        # ADX Calculation
        plus_dm = np.where((pd.Series(h).diff() > pd.Series(l).diff(periods=-1)), np.clip(pd.Series(h).diff(), 0, None), 0)
        minus_dm = np.where((pd.Series(l).diff(periods=-1) > pd.Series(h).diff()), np.clip(pd.Series(l).diff(periods=-1), 0, None), 0)
        tr_smooth = tr.rolling(14).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / tr_smooth)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / tr_smooth)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(14).mean().iloc[-1]
        
        # Momentum & Volatility
        z_score = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        p_chg = (c[-1] - c[-2]) / c[-2]
        
        # Scoring Logic
        miro = 2 + (5 if vol_surge > 2.0 else 0) + (3 if p_chg > 0.01 else 0)
        
        # FINAL RECOMMENDATION LOGIC
        reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_surge > 2.2 else "🛑 STRONG SELL" if p_chg < -0.02 and vol_surge > 2.2 else "🪃 REVERSION BUY" if z_score < -2.2 else "💤 NEUTRAL"

        return {
            "cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": round(adx, 1), 
            "z": round(z_score, 2), "vol": round(vol_surge, 2), "atr": atr, "reco": reco, "miro": miro
        }
    except: return None

# --- 5. INTERFACE & SIDEBAR ---
st.sidebar.subheader("🏦 Institutional Pulse")
st.sidebar.table(pd.DataFrame({
    "Metric": ["Date", "India VIX", "FII Net (Cr)"], 
    "Value": ["Mar 22, 2026", "22.81", "-5,518.39"]
}))

v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)
scan_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)

if st.sidebar.button("🚀 INITIALIZE GLOBAL 500 SCAN"):
    symbols, sectors = get_live_nifty_500()
    all_data = []
    prog = st.progress(0, text="Deep Scanning Nifty 500...")
    
    for i, t in enumerate(symbols[:scan_depth]):
        prog.progress((i + 1) / len(symbols[:scan_depth]))
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            m = calculate_metrics(raw, t)
            if m:
                all_data.append({
                    "Ticker": t, "Sector": sectors.get(t, "Misc"), "Price": round(m['cp'], 2), 
                    "Recommendation": m['reco'], "Miro_Score": m['miro'], "Z-Score": m['z'], 
                    "ADX Strength": m['adx'], "Vol_Surge": m['vol'], "MA 20": round(m['m20'], 2),
                    "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2)
                })
        except: continue
    
    if all_data: st.session_state['v14_res'] = pd.DataFrame(all_data)

# --- 6. TABS & STYLING ---
if 'v14_res' in st.session_state:
    df = st.session_state['v14_res']
    
    # Risk Calculation
    sl_mult = 3.0 if 22.81 > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "💎 Weekly Sniper", "🧬 Filing Audit", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # MIRO FLOW
        st.subheader("🎯 Miro Momentum (Visualized)")
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge"]].sort_values("Miro_Score", ascending=False).style.applymap(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)

    with tabs[1]: # TREND
        st.subheader("📈 Trend & ADX (Visualized)")
        # RESTORED RECOMMENDATION COLUMN HERE
        st.dataframe(df[["Ticker", "Price", "Recommendation", "ADX Strength", "MA 20", "MA 200"]].style.applymap(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)
        
    with tabs[2]: # REVERSION
        st.subheader("🪃 Mean Reversion (Visualized)")
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Z-Score"]].sort_values("Z-Score").style.applymap(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)

    with tabs[3]: # WEEKLY INSTITUTIONAL
        st.subheader("💎 Weekly Institutional Flow (Visualized)")
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Vol_Surge", "Sector"]].sort_values("Vol_Surge", ascending=False).style.applymap(highlight_reco, subset=['Recommendation']), hide_index=True, use_container_width=True)

    with tabs[4]: # FILING AUDIT
        t_f = st.selectbox("Select Asset for Audit", df['Ticker'].tolist())
        if st.button("🔍 Run Audit"):
            if client:
                prompt = f"Today is March 22, 2026. Audit Regulation 30 filings for {t_f} in 2026. Focus on Q3 FY26 earnings and March 2026 expansion plans."
                with st.spinner("Analyzing..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[5]: # INTELLIGENCE
        t_i = st.selectbox("Select Asset for Debate", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"Perform a 4-agent debate for {t_i} on March 22, 2026. Agents: BULL, BEAR, QUANT, and RISK MANAGER. Include VIX 22.81 context."
                with st.spinner("Debating..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[6]: # RISK LAB
        st.subheader("🛡️ Risk & Execution")
        st.dataframe(df[["Ticker", "Price", "Stop_Loss", "Qty", "ATR"]], hide_index=True, use_container_width=True)

else:
    st.info("Scanner Ready. Click 'INITIALIZE GLOBAL 500 SCAN' to begin.")
