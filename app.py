import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai

# --- 1. CONFIG & AI INITIALIZATION ---
st.set_page_config(page_title="Nifty 500 Sniper AI", layout="wide")

def initialize_ai():
    try:
        # Pulls the secret from your Streamlit Dashboard TOML
        if "GEMINI_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            return True
        return False
    except:
        return False

ai_active = initialize_ai()

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None

# --- 2. AI POWER: THE HARDENED SCREENER ---
def ai_filter_logic(query, df):
    if not ai_active: return df
    # Using the current 2026 stable workhorse model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Convert this request: '{query}' into a SINGLE line of pandas query code.
    COLUMNS AVAILABLE: {list(df.columns)}
    RULES:
    - Return ONLY the query string.
    - No 'python' tags, no backticks, no extra text.
    - If filtering by string, use double quotes: Sector == "Information Technology".
    - Logic Example: Score > 5 and Vol_Surge > 1.2
    """
    try:
        response = model.generate_content(prompt)
        clean_query = response.text.strip().replace('`', '').replace('python', '')
        # Debugging: Uncomment the line below if the screener is still not responding
        # st.caption(f"🤖 AI Generated Query: {clean_query}") 
        return df.query(clean_query)
    except Exception as e:
        st.error(f"Screener Error: {e}")
        return df

# --- 3. DATA ENGINE (Nifty 500 Sniper Logic) ---
@st.cache_data(ttl=3600)
def run_full_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf_1m = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        # Fallback for connectivity issues
        symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "FLUOROCHEM.NS", "INFY.NS"]
        sector_map = {s: "Bluechip" for s in symbols}
        nifty_perf_1m = 0.02

    all_data = []
    prog = st.progress(0, text="🎯 Snipering Nifty 500 Data...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 100: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

            # Core Technicals
            cp = float(df['Close'].iloc[-1])
            m20, m50, m200 = df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(50).mean().iloc[-1], df['Close'].rolling(200).mean().iloc[-1]
            tr = np.maximum(df['High']-df['Low'], np.maximum(np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))))
            atr = tr.rolling(14).mean().iloc[-1]
            atr_ratio = atr / tr.rolling(50).mean().iloc[-1]
            vol_surge = float(df['Volume'].iloc[-1]) / df['Volume'].rolling(20).mean().iloc[-1]

            # MiroFish Logic
            p_change = (cp - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2])
            action = "🔥 AGGRESSIVE BUY" if (p_change > 0 and vol_surge > 1.5) else "💎 ACCUMULATE" if p_change > 0 else "💤 HOLD"
            
            score = 0
            if cp > m20 > m50: score += 2
            if atr_ratio < 0.9: score += 3
            if vol_surge > 1.8: score += 3

            all_data.append({
                "Ticker": t, "Sector": sector_map.get(t, "Misc"), "Price": round(cp, 2),
                "Score": score, "Vol_Surge": round(vol_surge, 2), "ATR_Ratio": round(atr_ratio, 2),
                "Trend": "🟢 STRONG" if cp > m20 > m50 > m200 else "⚪ NEUTRAL",
                "Action": action, "ATR_Val": round(atr, 2)
            })
        except: continue
    prog.empty()
    return pd.DataFrame(all_data)

# --- 4. SIDEBAR & THE SUPREME JUDGE ---
st.sidebar.title("🏹 Nifty Sniper AI")
st.sidebar.write(f"AI Status: {'✅ Online' if ai_active else '❌ Offline'}")
depth = st.sidebar.slider("Scan Depth", 50, 500, 100)
risk_val = st.sidebar.number_input("Risk Amount (INR)", value=5000)

if st.sidebar.button("🚀 START SCAN"):
    data = run_full_scan(depth)
    if not data.empty:
        # Pre-calculate Risk Metrics
        data['Stop_Loss'] = data['Price'] - (2 * data['ATR_Val'])
        data['Qty'] = (risk_val / (data['Price'] - data['Stop_Loss'])).replace([np.inf, -np.inf], 0).fillna(0).astype(int)
        st.session_state['scan_results'] = data

# SIDEBAR JUDGE CHAT (Targeted Context)
if st.session_state['scan_results'] is not None and ai_active:
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ The Supreme Judge")
    user_ask = st.sidebar.text_input("Ask about a stock (e.g. Why is SBIN a buy?)")
    if user_ask:
        with st.sidebar:
            with st.spinner("Judging..."):
                try:
                    all_t = st.session_state['scan_results']['Ticker'].tolist()
                    target = next((t for t in all_t if t.split('.')[0] in user_ask.upper()), None)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    if target:
                        context_df = st.session_state['scan_results'][st.session_state['scan_results']['Ticker'] == target]
                        context = context_df.to_string()
                    else:
                        context = st.session_state['scan_results'].sort_values("Score", ascending=False).head(10).to_string()
                    
                    prompt = f"Data Context: {context}. VIX: 21.42. MiroFish Logic: High score = Buy. Question: {user_ask}"
                    resp = model.generate_content(prompt)
                    st.write(resp.text)
                except Exception as e:
                    st.error(f"Judge Error: {e}")

# --- 5. MAIN INTERFACE ---
if st.session_state['scan_results'] is not None:
    df = st.session_state['scan_results']
    
    st.subheader("💬 AI Natural Language Screener")
    ai_q = st.text_input("Filter e.g. 'Score > 5 and Sector == \"BANKING\"'")
    if ai_q:
        with st.spinner("AI is filtering..."):
            df = ai_filter_logic(ai_q, df)

    t1, t2, t3, t4, t5 = st.tabs(["🎯 Leaderboard", "📈 Trends", "📊 Vol Lab", "🧠 Risk Lab", "👣 Inst. Flow"])
    
    with t1:
        st.subheader("High Confluence Picks")
        st.dataframe(df.sort_values("Score", ascending=False), use_container_width=True)
    with t2:
        st.subheader("Structural Trend Analysis")
        st.dataframe(df[['Ticker', 'Price', 'Trend', 'Sector']], use_container_width=True)
    with t3:
        st.subheader("Volatility & Volume Lab")
        st.dataframe(df[['Ticker', 'Vol_Surge', 'ATR_Ratio', 'Action']], use_container_width=True)
    with t4:
        st.subheader("Risk Management (Stop Loss/Qty)")
        st.dataframe(df[['Ticker', 'Price', 'Stop_Loss', 'Qty']], use_container_width=True)
    with t5:
        st.subheader("Institutional Footprint (Smart Money)")
        st.dataframe(df[df['Vol_Surge'] > 1.8][['Ticker', 'Vol_Surge', 'Action']], use_container_width=True)

else:
    st.info("System Ready. Click 'START SCAN' in the sidebar to begin.")
