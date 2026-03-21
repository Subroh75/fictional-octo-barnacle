import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
import os
from datetime import datetime

# --- 1. CONFIG & AI CLIENT ---
st.set_page_config(page_title="Nifty Sniper v7.7.2", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE PRIVATE LEDGER ---
def save_to_ledger(ticker, strategy, price, content):
    file_path = "sniper_ledger.csv"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([[timestamp, ticker, strategy, price, content]], 
                             columns=["Timestamp", "Ticker", "Strategy", "Price", "Analysis"])
    if not os.path.isfile(file_path):
        new_entry.to_csv(file_path, index=False)
    else:
        new_entry.to_csv(file_path, mode='a', header=False, index=False)
    st.success(f"✅ Logged {ticker} to Private Ledger.")

# --- 3. AI AGENTS ---
def run_earnings_audit(ticker):
    if not client: return "⚠️ AI Offline."
    prompt = f"Equity Research: Search India Reg 30 filings for {ticker} (30d). Score Earnings Momentum (-10 to 10) & identify catalyst."
    try:
        return client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text
    except: return "Audit failed."

def summon_council(ticker, row, vix):
    if not client: return "⚠️ AI Offline."
    context = f"Ticker: {ticker} | Price: {row['Price']} | VIX: {vix} | ADX: {row['ADX Strength']} | Miro: {row['Miro_Score']}"
    prompt = f"Hedge Fund Committee Debate (Bull, Bear, Risk Manager) for {ticker}. Data: {context}"
    try:
        return client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text
    except: return "Council in recess."

# --- 4. HEDGE FUND MATH ENGINE ---
def calculate_metrics(df):
    try:
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = df['Volume'].iloc[-1] / df['Volume'].tail(20).mean()
        p_change = (c[-1] - c[-2]) / c[-2]
        
        # --- RESTORED: INSTITUTIONAL RECOMMENDATION LOGIC ---
        if p_change > 0.02 and vol_surge > 2.5: reco = "🚀 STRONG BUY (SURGE)"
        elif p_change > 0.01 and vol_surge > 1.8: reco = "🔥 AGGRESSIVE BUY"
        elif p_change < -0.02 and vol_surge > 2.5: reco = "🛑 STRONG SELL (EXIT)"
        elif p_change < -0.01 and vol_surge > 1.8: reco = "⚠️ INST. EXIT"
        elif p_change > 0 and vol_surge > 1.2: reco = "💎 ACCUMULATE"
        else: reco = "💤 NEUTRAL"

        # Mean Reversion Signal
        rev_sig = "💤 NEUTRAL"
        if z < -2.2: rev_sig = "🪃 STRONG REVERSION BUY"
        elif z < -1.8: rev_sig = "🪃 REVERSION BUY"
        elif z > 2.0: rev_sig = "⚠️ OVEREXTENDED"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "adx": adx, "z": round(z, 2), 
                "vol_surge": round(vol_surge, 2), "atr": atr, "rev_sig": rev_sig, "reco": reco}
    except: return None

# --- 5. DATA SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    n500 = pd.read_csv(url)
    symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    all_data = []
    prog = st.progress(0, text="Deep Audit: 500 Nifty Stocks...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            m = calculate_metrics(raw)
            if m:
                all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Miro_Score": 10 if m['vol_surge'] > 2 else 2, 
                                   "Recommendation": m['reco'], "Z-Score": m['z'], "Rev_Signal": m['rev_sig'], "Vol_Surge": m['vol_surge'], 
                                   "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}", 
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2), 
                                   "ATR": round(m['atr'], 2), "Above_200": m['cp'] > m['m200']})
        except: continue
    return pd.DataFrame(all_data)

# --- 6. INTERFACE ---
st.title("🏹 Nifty Sniper v7.7.2")
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)
v_vix = st.sidebar.number_input("India VIX", value=22.50)
v_risk = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 EXECUTE GLOBAL AUDIT"):
    st.session_state['v772_results'] = run_master_scan(v_depth)

if 'v772_results' in st.session_state:
    df = st.session_state['v772_results']
    
    # RISK LAB MATH
    sl_mult = 3.0 if v_vix > 20 else 2.0
    df['Stop_Loss'] = df['Price'] - (sl_mult * df['ATR'])
    df['Qty'] = (v_risk / (df['Price'] - df['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Analysis", "🪃 Mean Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.subheader("Miro Leaderboard (Momentum & Institutional Buying)")
        # RESTORED RECOMMENDATION COLUMN HERE
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Recommendation', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
    with tabs[1]:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'Recommendation', 'ADX Strength', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
    with tabs[2]:
        st.subheader("Mean Reversion Desk")
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Rev_Signal', 'Z-Score']], use_container_width=True)
    with tabs[3]:
        st.subheader("🧬 Earnings Front-Runner")
        t_e = st.selectbox("Ticker for Filing Audit", df['Ticker'].tolist())
        if st.button("🔍 Run Audit"):
            res = run_earnings_audit(t_e)
            st.markdown(res)
            if st.button("💾 Save Audit"): save_to_ledger(t_e, "Earnings Audit", df[df['Ticker']==t_e]['Price'].values[0], res)
    with tabs[4]:
        st.subheader("🧠 Intelligence Lab")
        t_i = st.selectbox("Ticker for Debate", df['Ticker'].tolist())
        if st.button("⚖️ Summon Council"):
            res = summon_council(t_i, df[df['Ticker'] == t_i].iloc[0], v_vix)
            st.markdown(res)
            if st.button("💾 Save Debate"): save_to_ledger(t_i, "Committee Debate", df[df['Ticker']==t_i]['Price'].values[0], res)
    with tabs[5]:
        st.subheader("Risk Lab & Ledger")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty', 'ATR']], use_container_width=True)
        if os.path.exists("sniper_ledger.csv"):
            st.download_button("📥 Download Private Ledger", data=open("sniper_ledger.csv", "rb"), file_name="nifty_sniper_ledger.csv")
