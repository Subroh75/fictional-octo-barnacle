import numpy as np
if not hasattr(np, 'bool8'): np.bool8 = np.bool_

import streamlit as st
import yfinance as yf
import pandas as pd
from google import genai
from datetime import datetime

# --- 1. CONFIG & AI AGENTS ---
st.set_page_config(page_title="Nifty Hedge Fund Master v7.3", layout="wide")

def get_ai_client():
    """Uses the new 2026 Google Gen AI SDK"""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        return None
    except: return None

client = get_ai_client()

def summon_council(ticker, row, vix):
    if not client: return "⚠️ AI Engine Offline. Check Secrets."
    
    # Using the 2026 Stable Workhorse: Gemini 2.5 Flash
    model_id = "gemini-2.5-flash"
    
    # We now use the AI to 'search' for news context rather than relying on broken YFinance links
    context = f"""
    Ticker: {ticker} | Price: {row['Price']} | VIX: {vix}
    Signal: {row['Recommendation']} | Miro_Score: {row['Miro_Score']}
    ADX: {row['ADX Strength']} | Z-Score: {row['Z-Score']}
    """
    
    prompt = f"""
    You are a Hedge Fund Committee. 
    1. Search for recent news regarding {ticker} in the Indian Market.
    2. Provide a Sentiment Score (-1.0 to 1.0).
    3. Perform a 3-agent debate (Bull, Bear, Risk Manager) on this asset.
    Data: {context}
    """
    try:
        # Utilizing the new SDK's generate_content method
        response = client.models.generate_content(
            model=model_id,
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Council is in recess: {e}. (Ensure you are using the new 'google-genai' library)"

# --- 2. HEDGE FUND MATH ENGINE ---

def calculate_metrics(df):
    try:
        c = df['Close'].values.flatten()
        h = df['High'].values.flatten()
        l = df['Low'].values.flatten()
        v = df['Volume'].values.flatten()
        
        m20 = np.mean(c[-20:]); m50 = np.mean(c[-50:]); m200 = np.mean(c[-200:])
        tr = pd.concat([pd.Series(h-l), abs(h-pd.Series(c).shift(1)), abs(l-pd.Series(c).shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        plus_di = 100 * (np.clip(pd.Series(h).diff(), 0, None).rolling(14).mean() / atr)
        minus_di = 100 * (np.clip((-pd.Series(l).diff()), 0, None).rolling(14).mean() / atr)
        adx = ((abs(plus_di - minus_di) / (plus_di + minus_di)) * 100).rolling(14).mean().iloc[-1]
        
        z = (c[-1] - m20) / np.std(c[-20:])
        vol_surge = v[-1] / np.mean(v[-20:])
        
        return {
            "cp": c[-1], "m20": m20, "m50": m50, "m200": m200, 
            "adx": adx, "z": round(z, 2), "vol_surge": round(vol_surge, 2), "atr": atr.iloc[-1]
        }
    except: return None

# --- 3. DATA ENGINE ---

@st.cache_data(ttl=3600)
def fetch_institutional_flow():
    return pd.DataFrame({
        "Metric": ["FII Net (Cr)", "DII Net (Cr)", "Market Bias"],
        "Value": ["-7,558.20", "+3,864.00", "⚠️ BEARISH PRESSURE"]
    })

@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
    except:
        symbols = ["RELIANCE.NS", "TCS.NS", "360ONE.NS"]
        sector_map = {s: "Misc" for s in symbols}

    all_data = []
    prog = st.progress(0, text=f"Deep Audit in progress...")
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            # Note: yfinance historical data still works, but news is restricted
            raw = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if raw.empty or len(raw) < 50: continue
            if isinstance(raw.columns, pd.MultiIndex): raw.columns = raw.columns.get_level_values(0)
            
            m = calculate_metrics(raw)
            if not m: continue

            miro = 0
            if m['vol_surge'] > 1.8: miro += 5
            if m['adx'] > 25: miro += 3
            
            p_change = (m['cp'] - raw['Close'].iloc[-2]) / raw['Close'].iloc[-2]
            if p_change > 0.01 and m['vol_surge'] > 2.0: reco = "🔥 AGGRESSIVE BUY"
            elif m['z'] < -2.0: reco = "🪃 MEAN REVERSION"
            else: reco = "💤 NEUTRAL"

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(m['cp'], 2),
                "Recommendation": reco, "Miro_Score": miro, "Z-Score": m['z'], 
                "ADX Strength": f"🔥 {round(m['adx'],1)}" if m['adx'] > 25 else f"💤 {round(m['adx'],1)}",
                "Vol_Surge": m['vol_surge'], "MA 20": round(m['m20'], 2), "MA 50": round(m['m50'], 2), "MA 200": round(m['m200'], 2),
                "ATR": round(m['atr'], 2)
            })
        except: continue
    return pd.DataFrame(all_data)

# --- 4. INTERFACE ---
st.title("🏹 Nifty Hedge Fund Master v7.3")

st.sidebar.subheader("🏦 Smart Money Pulse")
st.sidebar.table(fetch_institutional_flow())
v_depth = st.sidebar.slider("Scan Depth", 50, 500, 500)
v_vix = st.sidebar.number_input("India VIX", value=21.84)

if st.sidebar.button("🚀 EXECUTE MASTER SCAN"):
    st.session_state['v73_results'] = run_master_scan(v_depth)

if 'v73_results' in st.session_state:
    df = st.session_state['v73_results']
    tabs = st.tabs(["🎯 Miro Flow", "📈 Trend Analysis", "🪃 Mean Reversion", "🧬 Intel & Correlation", "🛡️ Risk Lab"])
    
    with tabs[0]:
        st.subheader("Miro Score Leaderboard")
        st.dataframe(df.sort_values("Miro_Score", ascending=False)[['Ticker', 'Price', 'Recommendation', 'Miro_Score', 'Vol_Surge']], use_container_width=True)
    
    with tabs[1]:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'ADX Strength', 'MA 20', 'MA 50', 'MA 200', 'Sector']], use_container_width=True)

    with tabs[2]:
        st.subheader("Statistical Mean Reversion (Z-Score)")
        st.dataframe(df.sort_values("Z-Score")[['Ticker', 'Price', 'Recommendation', 'Z-Score', 'Sector']], use_container_width=True)

    with tabs[3]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Correlation Matrix")
            selected = st.multiselect("Select Tickers", df['Ticker'].tolist(), default=df['Ticker'].tolist()[:4])
            if len(selected) > 1:
                c_data = yf.download(selected, period="6mo", progress=False)['Close']
                if isinstance(c_data.columns, pd.MultiIndex): c_data.columns = c_data.columns.get_level_values(1)
                st.dataframe(c_data.pct_change().corr(), use_container_width=True)
        with col2:
            st.subheader("🧠 News Sentiment Lab")
            target = st.selectbox("Audit Ticker", df['Ticker'].tolist())
            if st.button("⚖️ Summon Council"):
                with st.spinner("Council debating based on search context..."):
                    st.markdown(summon_council(target, df[df['Ticker'] == target].iloc[0], v_vix))

    with tabs[4]:
        st.subheader("Risk Lab")
        st.dataframe(df[['Ticker', 'Price', 'ATR', 'Sector']], use_container_width=True)
else:
    st.info("System Ready. Depth: 500.")
