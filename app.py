import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

# --- 1. CONFIG & SETUP ---
st.set_page_config(page_title="Alpha Master Terminal", layout="wide")

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()

# --- 2. THE UNIFIED DATA ENGINE ---
@st.cache_data(ttl=3600)
def run_master_scan(limit):
    url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
    try:
        n500 = pd.read_csv(url)
        symbols = [s + ".NS" for s in n500['Symbol'].tolist()]
        sector_map = dict(zip(n500['Symbol'] + ".NS", n500['Industry']))
        
        nifty = yf.download("^NSEI", period="1y", progress=False)
        if isinstance(nifty.columns, pd.MultiIndex): 
            nifty.columns = nifty.columns.get_level_values(0)
        nifty_perf = (float(nifty['Close'].iloc[-1]) / float(nifty['Close'].iloc[-21])) - 1
    except:
        symbols, sector_map, nifty_perf = ["RELIANCE.NS", "TCS.NS"], {}, 0

    all_data = []
    prog = st.progress(0, text="Analyzing Market Structure...")
    
    for i, t in enumerate(symbols[:limit]):
        prog.progress((i + 1) / limit)
        try:
            df = yf.download(t, period="1y", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.Multi
