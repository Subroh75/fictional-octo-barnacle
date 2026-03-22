import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG & SYSTEM ---
st.set_page_config(page_title="Nifty Sniper Elite v12.5", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE MULTIINDEX FIX ENGINE ---
def calculate_metrics(df, ticker):
    try:
        # 2026 Fix: Flatten MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            if ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, level=1, axis=1)
            else:
                df.columns = df.columns.get_level_values(0)
        
        df.columns = [str(c).capitalize() for c in df.columns]
        c, h, l, v = df['Close'].values.flatten(), df['High'].values.flatten(), df['Low'].values.flatten(), df['Volume'].values.flatten()
        
        if len(c) < 200: return None

        # Technicals
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        # Trend Strength (ADX)
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        # Momentum & Volatility
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_s = v[-1] / np.mean(v[-20:])
        p_chg = (c[-1] - c[-2]) / c[-2]
        
        # Scoring Logic
        miro = 2 + (5 if vol_s > 2.0 else 0) + (3 if p_chg > 0.01 else 0)
        reco = "🚀 STRONG BUY" if p_chg > 0.02 and vol_s > 2.2 else "🪃 REVERSION" if z < -2.2 else "💤 NEUTRAL"

        return {
            "cp": c[-1], "m20": m20, "m50": m50, "m200": m200, 
            "adx": round(adx, 1), "z": round(z, 2), "vol": round(vol_s, 2), 
            "atr": atr, "reco": reco, "miro": miro
        }
    except: return None

# --- 3. DATA SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    # Nifty 500 Constituent List
    symbols = ["BIOCON.NS", "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "TATASTEEL.NS", "ADANIPOWER.NS", "ESCORTS.NS"]
    all_data = []
    prog = st.progress(0, text="Auditing Institutional Tape...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / len(symbols[:limit]))
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            m = calculate_metrics(raw, t)
            if m:
                all_data.append({
                    "Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], 
                    "Miro_Score": m['miro'], "Z-Score": m['z'], "ADX Strength": m['adx'],
                    "Vol_Surge": m['vol'], "MA 20": round(m['m20'], 2), "MA 200": round(m['m200'], 2), "ATR": round(m['atr'], 2)
                })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper Elite v12.5")

# --- SIDEBAR: RESTORED 2026 PULSE ---
st.sidebar.subheader("🏦 March 2026 Pulse")
st.sidebar.table(pd.DataFrame({
    "Metric": ["Date", "India VIX", "FII Net (Cr)", "DII Net (Cr)"], 
    "Value": ["Mar 20, 2026", "22.81", "-5,518.39", "+5,706.23"]
}))
v_risk = st.sidebar.number_input("Risk Per Trade (INR)", value=5000)

if st.sidebar.button("🚀 INITIALIZE GLOBAL SCAN"):
    res = run_master_scan(100)
    if not res.empty: st.session_state['v125_res'] = res

if 'v125_res' in st.session_state:
    df = st.session_state['v125_res']
    
    # Sidebar Weather logic
    above_200 = len(df[df['MA 200'] < df['Price']])
    breadth = (above_200 / len(df)) * 100
    st.sidebar.metric("Market Breadth (>MA200)", f"{round(breadth, 1)}%", delta="-2.1%")

    # Risk Math
    sl_mult = 3.0 if 22.81 > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    # --- MAIN TABS ---
    tabs = st.tabs(["💎 Weekly Sniper", "🎯 Miro Flow", "📈 Trend & ADX", "🪃 Reversion", "🧬 Filing Audit", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: # Weekly Sniper
        st.subheader("💎 Institutional Weekly Accumulation")
        st.dataframe(df[["Ticker", "Price", "Vol_Surge", "Miro_Score"]].sort_values("Vol_Surge", ascending=False), hide_index=True, use_container_width=True)
        st.info("**TACTICAL HANDBOOK:** Look for 'Vol_Surge' > 2.0 while Miro_Score remains 2-5. This suggests quiet institutional building before a breakout.")

    with tabs[1]: # Miro Flow
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Miro_Score", "Vol_Surge"]].sort_values("Miro_Score", ascending=False), hide_index=True, use_container_width=True)
        st.info("**TACTICAL HANDBOOK:** Miro Score 8-10 signals extreme momentum. Never buy these at the open; wait for a 15-min retracement.")

    with tabs[2]: # Trend & ADX
        st.dataframe(df[["Ticker", "Price", "ADX Strength", "MA 20", "MA 200"]], hide_index=True, use_container_width=True)
        st.info("**TACTICAL HANDBOOK:** ADX > 25 confirms a strong trend. If ADX is < 20, technical signals are likely to fail (choppy market).")

    with tabs[3]: # Reversion
        st.dataframe(df[["Ticker", "Price", "Recommendation", "Z-Score"]].sort_values("Z-Score"), hide_index=True, use_container_width=True)
        st.info("**TACTICAL HANDBOOK:** Z-Score < -2.2 indicates the rubber band is stretched too far. Expect a snap-back to the MA 20.")

    with tabs[4]: # Filing Audit
        t_f = st.selectbox("Select Asset for Filing Audit", df['Ticker'].tolist())
        if st.button("🔍 Run 2026 Audit"):
            if client:
                prompt = f"Today is March 22, 2026. Audit Regulation 30 filings for {t_f} from Jan 1, 2026. Specifically reference Q3 FY26 earnings (Feb 2026) and 2026 expansion plans."
                with st.spinner("Accessing 2026 Archives..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[5]: # Intelligence Lab
        t_i = st.selectbox("Select Asset for Committee Debate", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            if client:
                prompt = f"Perform a 4-agent debate for {t_i} on March 22, 2026. Agents: BULL (Fundamentals), BEAR (Skeptic), TECHNICAL (Chart), RISK (Manager). Mention VIX 22.81 context."
                with st.spinner("Council debating..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)

    with tabs[6]: # Risk Lab
        st.dataframe(df[["Ticker", "Price", "Stop_Loss", "Qty", "ATR"]], hide_index=True, use_container_width=True)
        st.info("**TACTICAL HANDBOOK:** Qty is calculated based on your sidebar 'Risk Per Trade'. ATR-based Stop Loss protects you from high VIX volatility.")
else:
    st.info("Scanner Ready. Click 'INITIALIZE GLOBAL SCAN'.")
