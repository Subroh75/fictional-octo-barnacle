import streamlit as st
import pandas as pd
import numpy as np
from statsmodels.tsa.filters.hp_filter import hpfilter
from sklearn.neighbors import NearestNeighbors

def render_quant_sidebar(df, current_price):
    """
    Implements '151 Trading Strategies' Quant Layers into the Nifty Sniper Sidebar.
    Expects a DataFrame 'df' with ['close', 'high', 'low', 'volume'] columns.
    """
    st.sidebar.markdown("# 🎯 Quant Strategy Lab")
    st.sidebar.info("These tools provide a mathematical 'overlay' to validate your manual setups. Use them to filter out noise and confirm high-probability zones.")
    st.sidebar.markdown("---")

    # --- 1. HP FILTER (TREND REFINER) ---
    st.sidebar.subheader("📡 Trend Refiner (HP)")
    hp_expander = st.sidebar.expander("Logic: How it works")
    hp_expander.write("""
        **The Math:** It separates the 'Trend' from high-frequency 'Noise' by minimizing price curvature.
        **The Goal:** To ignore 1-minute 'fake-outs' and only trade when the core institutional trend is in your favor.
    """)
    
    if st.sidebar.checkbox("Enable HP Noise Filter", value=True):
        # Lambda 12800 is a standard quantitative setting for intraday data
        # It provides a 'smooth' line that resists minor price stutters
        cycle, trend = hpfilter(df['close'], lamb=12800)
        latest_trend = trend.iloc[-1]
        
        if current_price > latest_trend:
            st.sidebar.success(f"HP STATUS: BULLISH\n(Price is above the core trend)")
        else:
            st.sidebar.error(f"HP STATUS: BEARISH\n(Price is below the core trend)")

    # --- 2. IBS (MEAN REVERSION) ---
    st.sidebar.subheader("🔄 Mean Reversion (IBS)")
    ibs_expander = st.sidebar.expander("Logic: How it works")
    ibs_expander.write("""
        **The Math:** (Current - Daily Low) / (Daily High - Daily Low).
        **The Goal:** To see how 'stretched' the price is. 
        - **0.0 to 0.2:** Oversold 'Snipe' zone (Expect a bounce).
        - **0.8 to 1.0:** Overbought zone (Expect a cooldown).
    """)
    
    day_high = df['high'].max()
    day_low = df['low'].min()
    
    # Calculate IBS (Internal Bar Strength)
    if day_high != day_low:
        ibs = (current_price - day_low) / (day_high - day_low)
    else:
        ibs = 0.5
        
    st.sidebar.write(f"**Current IBS Score: {ibs:.2f}**")
    st.sidebar.progress(float(np.clip(ibs, 0.0, 1.0)))
    
    if ibs < 0.2:
        st.sidebar.warning("⚠️ SNIPE ALERT: Price is at extreme daily lows. Potential Reversal.")
    elif ibs > 0.8:
        st.sidebar.warning("⚠️ CAUTION: Price is at extreme daily highs. Avoid chasing.")

    # --- 3. KNN (HISTORICAL PATTERN MATCHING) ---
    st.sidebar.subheader("🧠 Intelligence Lab (KNN)")
    knn_expander = st.sidebar.expander("Logic: How it works")
    knn_expander.write("""
        **The Math:** K-Nearest Neighbors (Euclidean Distance).
        **The Goal:** It scans the last 1,000 bars of history to find the 3 times the market moved exactly like it is moving right now.
        **The Result:** It tells you if the 'Historical Twins' resulted in a move Up or Down.
    """)
    
    if len(df) > 60:
        # We look at the last 5 bars of price and volume as a 'pattern'
        lookback = 5
        current_pattern = df[['close', 'volume']].tail(lookback).values.flatten().reshape(1, -1)
        
        # Prepare historical patterns to search through
        history_features = []
        history_outcomes = []
        
        # We stop 5 bars early to see what the 'outcome' was after the pattern
        for i in range(len(df) - (lookback + 5)):
            pattern = df[['close', 'volume']].iloc[i : i + lookback].values.flatten()
            # Did the price go up or down 5 bars later?
            outcome = 1 if df['close'].iloc[i + lookback + 5] > df['close'].iloc[i + lookback] else 0
            history_features.append(pattern)
            history_outcomes.append(outcome)
        
        # Fit KNN
        model = NearestNeighbors(n_neighbors=3, metric='euclidean')
        model.fit(history_features)
        
        distances, indices = model.kneighbors(current_pattern)
        
        # Calculate how many of the 3 matches went 'Up'
        up_moves = sum([history_outcomes[idx] for idx in indices[0]])
        
        if up_moves >= 2:
            st.sidebar.write("✅ **History says: UP (Probable)**")
        else:
            st.sidebar.write("❌ **History says: DOWN (Probable)**")
        st.sidebar.caption(f"Pattern Confidence: {int((up_moves/3)*100)}%")

    # --- 4. THE GATEKEEPER (COST PROTECTOR) ---
    st.sidebar.subheader("🛡️ The Gatekeeper")
    gate_expander = st.sidebar.expander("Logic: How it works")
    gate_expander.write("""
        **The Math:** (Projected Profit %) - (Total Transaction Costs %).
        **The Goal:** To prevent 'Ghost Profits.' If the move isn't big enough to cover your taxes and brokerage, the trade is mathematically a loss before you even start.
    """)
    
    target_move = st.sidebar.slider("Expected Move (%)", 0.1, 2.0, 0.5)
    
    # Approximate costs for Indian Market (Brokerage + STT + Slippage + GST)
    fixed_costs = 0.15 
    net_return = target_move - fixed_costs
    
    if net_return <= 0:
        st.sidebar.error(f"🛑 TRADE BLOCKED\nNet Return: {net_return:.2f}%")
        st.sidebar.caption("Move is too small to cover execution costs.")
    else:
        st.sidebar.success(f"🟢 TRADE APPROVED\nNet Return: +{net_return:.2f}%")
