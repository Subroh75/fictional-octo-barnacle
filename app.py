import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Nifty Sniper Elite v7.9.5", layout="wide")

def get_ai_client():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

# --- 2. THE DATA ENGINE (2026 FLATTENING) ---
def calculate_metrics(df, ticker):
    try:
        # Step 1: Force flatten if yfinance sends MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            # Extract the data for the specific ticker to remove the level
            if ticker in df.columns.get_level_values(1):
                df = df.xs(ticker, level=1, axis=1)
            else:
                df.columns = df.columns.get_level_values(0)

        # Step 2: Ensure Column names are standard
        df.columns = [str(c).capitalize() for c in df.columns]
        
        c = df['Close'].values.flatten()
        h, l = df['High'].values.flatten(), df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        if len(c) < 200: return None # Not enough history

        m20, m50, m200 = np.mean(c[-20:]), np.mean(c[-50:]), np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        
        reco = "🚀 STRONG BUY" if (c[-1]-c[-2])/c[-2] > 0.02 and vol_surge > 2.0 else "🪃 REVERSION" if z < -2.2 else "💤 NEUTRAL"

        return {"cp": c[-1], "m20": m20, "m50": m50, "m200": m200, "z": round(z, 2), 
                "vol": round(vol_surge, 2), "atr": atr, "reco": reco}
    except Exception as e:
        return None

# --- 3. THE SCANNER ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    # Fallback list if NSE CSV is down
    backup_symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS", "BHARTIARTL.NS", "LICI.NS", "ITC.NS", "HINDALCO.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "ADANIENT.NS", "ESCORTS.NS"]
    
    try:
        url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
    except:
        symbols = backup_symbols

    all_data = []
    prog = st.progress(0, text="Fetching Live 2026 Market Data...")
    
    # Scan a subset for speed/stability
    target_list = symbols[:limit]
    
    for i, t in enumerate(target_list):
        prog.progress((i + 1) / len(target_list))
        try:
            # multi_level_index=False is often ignored by yf, so we flatten in metrics
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty: continue
            
            m = calculate_metrics(raw, t)
            if m:
                all_data.append({"Ticker": t, "Price": round(m['cp'], 2), "Recommendation": m['reco'], 
                                   "Z-Score": m['z'], "Vol_Surge": m['vol'], "ATR": round(m['atr'], 2),
                                   "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2)})
        except: continue
    
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Sniper Elite v7.9.5")

if st.sidebar.button("🚀 EXECUTE GLOBAL SCAN"):
    res = run_master_scan(100) # Reduced to 100 for stability; increase to 500 later
    if not res.empty:
        st.session_state['v795_res'] = res
    else:
        st.error("No data found. Check yfinance connection or Ticker list.")

if 'v795_res' in st.session_state:
    df = st.session_state['v795_res']
    
    # SideBar Weather
    above_200 = len(df[df['MA 200'] < df['Price']])
    breadth = (above_200 / len(df)) * 100
    st.sidebar.markdown(f"### 🌡️ Market Weather")
    if breadth > 60: st.sidebar.success("🔥 BULL REGIME")
    elif breadth < 40: st.sidebar.warning("❄️ BEAR REGIME")
    else: st.sidebar.info("⚖️ NEUTRAL")

    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend", "🪃 Reversion", "🧬 Earnings Front-Runner", "🧠 Intelligence Lab", "🛡️ Risk Lab"])
    
    with tabs[0]: st.dataframe(df.sort_values("Vol_Surge", ascending=False), use_container_width=True)
    with tabs[1]: st.dataframe(df[['Ticker', 'Price', 'MA 20', 'MA 50', 'MA 200']], use_container_width=True)
    with tabs[2]: st.dataframe(df.sort_values("Z-Score"), use_container_width=True)
    
    with tabs[3]: # EARNINGS
        t_e = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="e_box")
        if st.button("🔍 Run Audit"):
            if client:
                with st.spinner("Searching 2026 Filings..."):
                    prompt = f"Today is {datetime.now().strftime('%B %d, %Y')}. Search Reg 30 filings for {t_e} from last 30 days. Identify 2026 catalysts."
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text)
            else: st.error("API Key missing.")

    with tabs[4]: # INTELLIGENCE
        t_i = st.selectbox("Select Ticker", df['Ticker'].tolist(), key="i_box")
        if st.button("⚖️ Summon Council"):
            if client:
                with st.spinner("Debating..."):
                    st.markdown(client.models.generate_content(model="gemini-2.5-flash", contents=f"3-agent 2026 Debate for {t_i}.").text)

    with tabs[5]: st.dataframe(df[['Ticker', 'Price', 'ATR']], use_container_width=True)
else:
    st.info("System Ready. Please click 'EXECUTE GLOBAL SCAN'.")
