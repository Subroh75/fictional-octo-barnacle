import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- VERSION 2.2 EMERGENCY OVERRIDE ---
st.set_page_config(page_title="EMERGENCY RESET")
st.error("🚨 VERSION 2.2: IF YOU SEE THIS, THE UPDATE WORKED")

st.sidebar.title("Emergency Control")
ticker = st.sidebar.text_input("Enter Ticker", value="ATHERENERG.NS")

if st.sidebar.button("RUN RAW DIAGNOSTIC"):
    st.write(f"Fetching data for {ticker}...")
    try:
        data = yf.download(ticker, period="1y", auto_adjust=True)
        
        # Flattening data manually
        df = pd.DataFrame()
        df['Price'] = data['Close'].values.flatten()
        df['MA20'] = pd.Series(df['Price']).rolling(20).mean()
        
        st.write("### Raw Data Output")
        st.dataframe(df.tail(10))
        
        if df['MA20'].isnull().all():
            st.warning("MA20 is returning all NaNs. Testing raw math...")
            st.write(f"Manual Mean of last 20: {np.mean(df['Price'][-20:])}")
            
    except Exception as e:
        st.error(f"Error: {e}")
