# --- Updated Master Scanner Logic ---
# (Inside your run_master_scan function)

# 1. Define the MA Status
m20 = df['Close'].rolling(20).mean().iloc[-1]
m50 = df['Close'].rolling(50).mean().iloc[-1]
m200 = df['Close'].rolling(200).mean().iloc[-1]

# 2. Recommendation Logic
if cp > m20 > m50 > m200:
    recommendation = "🟢 STRONG BUY"  # Perfect Alignment
elif cp > m50 > m200:
    recommendation = "🟡 HOLD / WATCH" # Trend healthy, but short-term pull-back
elif cp < m200:
    recommendation = "🔴 AVOID / SELL" # Long-term downtrend
else:
    recommendation = "⚪ NEUTRAL"

# 3. Add to the dataframe
all_data.append({
    "Ticker": t, 
    "Price": round(cp, 2),
    "Recommendation": recommendation,
    "MA_Trend": trend,
    "Score": int(score)
})
