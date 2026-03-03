if 'data' in st.session_state:
    df_res = st.session_state['data']
    
    t1, t2, t3 = st.tabs(["⚡ Momentum (Long)", "📉 Breakdown (Short)", "📊 Sector Pulse"])

    with t1:
        st.subheader("High-Velocity Upside Bursts")
        # Filter and then sort on a separate line to avoid syntax nesting errors
        long_df = df_res[df_res['Signal'].str.contains("IGNITION|BURST|TREND UP", na=False)]
        long_df = long_df.sort_values(by="Vol Surge", ascending=False)
        st.dataframe(long_df, use_container_width=True)

    with t2:
        st.subheader("High-Velocity Downside Crashes")
        # Filter and then sort on a separate line
        short_df = df_res[df_res['Signal'].str.contains("BREAKDOWN|SELL", na=False)]
        if not short_df.empty:
            short_df = short_df.sort_values(by="Day %", ascending=True)
            st.dataframe(short_df, use_container_width=True)
        else:
            st.info("No strong bearish signals detected.")

    with t3:
        st.subheader("Sector Leadership")
        active_sectors = df_res[df_res['Signal'] != "Neutral"]
        if not active_sectors.empty:
            fig = px.histogram(active_sectors, x="Industry", color="Signal", title="Signals by Sector")
            st.plotly_chart(fig, use_container_width=True)
