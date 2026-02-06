import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# =========================
# Page config
# =========================
st.set_page_config(page_title="IDX Portfolio Rebalancing Simulator", layout="wide")
st.title("📈 IDX Close Price (1Y) + ⚖️ Rebalancing vs Buy & Hold Simulator")

# =========================
# User Input
# =========================
tickers_input = st.text_area(
    "Enter IDX tickers (2–5 tickers, one per line, without .JK)",
    value="BBCA\nBMRI\nBBRI",
    height=150
)

initial_equity = st.number_input("Initial Equity (IDR)", min_value=1_000_000, value=100_000_000, step=1_000_000)
rebalance_period = st.number_input("Rebalancing Period (trading days)", min_value=5, value=20, step=5)

tickers = [t.strip().upper() + ".JK" for t in tickers_input.splitlines() if t.strip()]
tickers_clean = [t.replace(".JK", "") for t in tickers]

# =========================
# Date range
# =========================
end_date = datetime.today()
start_date = end_date - timedelta(days=365)

# =========================
# Run
# =========================
if st.button("Run Simulation"):

    if not (2 <= len(tickers) <= 5):
        st.warning("Please input between 2 and 5 tickers.")
        st.stop()

    # =========================
    # Fetch Prices
    # =========================
    price_data = {}

    with st.spinner("Fetching data..."):
        for ticker in tickers:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)

            if df.empty:
                st.error(f"No data for {ticker}")
                st.stop()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            price_data[ticker.replace(".JK", "")] = df["Close"]

    prices_df = pd.concat(price_data.values(), axis=1)
    prices_df.columns = tickers_clean
    prices_df = prices_df.dropna()

    # =========================
    # Price Chart
    # =========================
    fig_price = go.Figure()
    for col in prices_df.columns:
        fig_price.add_trace(go.Scatter(
            x=prices_df.index,
            y=prices_df[col],
            mode="lines",
            name=col,
            hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%Y-%m-%d}<br>Price: IDR %{y:,.0f}<extra></extra>'
        ))

    fig_price.update_layout(
        title="Close Price – Last 1 Year",
        xaxis_title="Date",
        yaxis_title="Price (IDR)",
        hovermode="x unified",
        height=450
    )
    st.plotly_chart(fig_price, use_container_width=True)

    # =========================
    # Rebalancing Simulation
    # =========================
    n_assets = len(tickers_clean)
    target_weight = 1 / n_assets

    shares_reb = {}
    shares_hold = {}

    equity_reb_curves = {t: [] for t in tickers_clean}
    equity_hold_curves = {t: [] for t in tickers_clean}

    portfolio_reb_curve = []
    portfolio_hold_curve = []

    rebalance_log = []

    # Initial allocation
    for t in tickers_clean:
        alloc = initial_equity * target_weight
        shares_reb[t] = alloc / prices_df.iloc[0][t]
        shares_hold[t] = alloc / prices_df.iloc[0][t]

    for i, date in enumerate(prices_df.index):
        values_reb = {}
        values_hold = {}
        total_reb = 0
        total_hold = 0

        for t in tickers_clean:
            v_reb = shares_reb[t] * prices_df.iloc[i][t]
            v_hold = shares_hold[t] * prices_df.iloc[i][t]

            equity_reb_curves[t].append(v_reb)
            equity_hold_curves[t].append(v_hold)

            values_reb[t] = v_reb
            values_hold[t] = v_hold

            total_reb += v_reb
            total_hold += v_hold

        portfolio_reb_curve.append(total_reb)
        portfolio_hold_curve.append(total_hold)

        if i > 0 and i % rebalance_period == 0:
            target_value = total_reb * target_weight
            log_row = {"Date": date.strftime("%Y-%m-%d")}

            for t in tickers_clean:
                drift_pct = (values_reb[t] / target_value - 1) * 100
                transfer = target_value - values_reb[t]

                log_row[f"{t} Equity (Before)"] = values_reb[t]
                log_row[f"{t} Drift (%)"] = drift_pct
                log_row[f"{t} Transfer"] = transfer

                shares_reb[t] = target_value / prices_df.iloc[i][t]

            rebalance_log.append(log_row)

    equity_reb_df = pd.DataFrame(equity_reb_curves, index=prices_df.index)
    equity_reb_df["Portfolio"] = portfolio_reb_curve

    equity_hold_df = pd.DataFrame(equity_hold_curves, index=prices_df.index)
    equity_hold_df["Portfolio"] = portfolio_hold_curve

    # =========================
    # Equity Curve Comparison Plot
    # =========================
    fig_equity = go.Figure()

    fig_equity.add_trace(go.Scatter(
        x=equity_reb_df.index,
        y=equity_reb_df["Portfolio"],
        mode="lines",
        name="Portfolio (Rebalanced)",
        line=dict(width=3)
    ))

    fig_equity.add_trace(go.Scatter(
        x=equity_hold_df.index,
        y=equity_hold_df["Portfolio"],
        mode="lines",
        name="Portfolio (Buy & Hold)",
        line=dict(dash="dash")
    ))

    fig_equity.update_layout(
        title="📊 Portfolio Equity Curve: Rebalancing vs Buy & Hold",
        xaxis_title="Date",
        yaxis_title="Equity (IDR)",
        hovermode="x unified",
        height=550
    )
    st.plotly_chart(fig_equity, use_container_width=True)

    # =========================
    # Rebalancing History Table
    # =========================
    st.subheader("🔄 Rebalancing History")

    if rebalance_log:
        rebalance_df = pd.DataFrame(rebalance_log)
        rebalance_display = rebalance_df.copy()

        money_cols = [c for c in rebalance_display.columns if "Equity" in c or "Transfer" in c]
        pct_cols = [c for c in rebalance_display.columns if "Drift" in c]

        for col in money_cols:
            rebalance_display[col] = rebalance_display[col].map(lambda x: f"{x:,.0f}")

        for col in pct_cols:
            rebalance_display[col] = rebalance_display[col].map(lambda x: f"{x:.2f}%")

        st.dataframe(rebalance_display, use_container_width=True)
    else:
        st.info("No rebalancing events occurred.")

    # =========================
    # Summary Table (Rebalancing)
    # =========================
    st.subheader("📋 Summary (With Rebalancing)")

    summary_reb_rows = []
    for t in tickers_clean:
        start_price = prices_df[t].iloc[0]
        end_price = prices_df[t].iloc[-1]
        price_growth_pct = (end_price / start_price - 1) * 100

        final_equity = equity_reb_df[t].iloc[-1]
        initial_alloc = initial_equity * target_weight
        equity_growth_pct = (final_equity / initial_alloc - 1) * 100

        summary_reb_rows.append({
            "Ticker": t,
            "Price Growth (1Y %)": price_growth_pct,
            "Final Equity (IDR)": final_equity,
            "Equity Growth (%)": equity_growth_pct
        })

    portfolio_reb_growth_pct = (equity_reb_df["Portfolio"].iloc[-1] / initial_equity - 1) * 100

    summary_reb_df = pd.DataFrame(summary_reb_rows)
    portfolio_reb_row = pd.DataFrame([{
        "Ticker": "PORTFOLIO (Rebalanced)",
        "Price Growth (1Y %)": None,
        "Final Equity (IDR)": equity_reb_df["Portfolio"].iloc[-1],
        "Equity Growth (%)": portfolio_reb_growth_pct
    }])

    summary_reb_df = pd.concat([summary_reb_df, portfolio_reb_row], ignore_index=True)

    summary_reb_display = summary_reb_df.copy()
    summary_reb_display["Final Equity (IDR)"] = summary_reb_display["Final Equity (IDR)"].map(lambda x: f"{x:,.0f}")
    summary_reb_display["Price Growth (1Y %)"] = summary_reb_display["Price Growth (1Y %)"].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
    summary_reb_display["Equity Growth (%)"] = summary_reb_display["Equity Growth (%)"].map(lambda x: f"{x:.2f}%")

    st.dataframe(summary_reb_display, use_container_width=True)

    # =========================
    # Buy & Hold Summary
    # =========================
    st.subheader("🧱 Buy & Hold (No Rebalancing) Summary")

    summary_hold_rows = []
    for t in tickers_clean:
        start_price = prices_df[t].iloc[0]
        end_price = prices_df[t].iloc[-1]
        price_growth_pct = (end_price / start_price - 1) * 100

        final_equity = equity_hold_df[t].iloc[-1]
        initial_alloc = initial_equity * target_weight
        equity_growth_pct = (final_equity / initial_alloc - 1) * 100

        summary_hold_rows.append({
            "Ticker": t,
            "Price Growth (1Y %)": price_growth_pct,
            "Final Equity (IDR)": final_equity,
            "Equity Growth (%)": equity_growth_pct
        })

    portfolio_hold_growth_pct = (equity_hold_df["Portfolio"].iloc[-1] / initial_equity - 1) * 100

    summary_hold_df = pd.DataFrame(summary_hold_rows)
    portfolio_hold_row = pd.DataFrame([{
        "Ticker": "PORTFOLIO (Buy & Hold)",
        "Price Growth (1Y %)": None,
        "Final Equity (IDR)": equity_hold_df["Portfolio"].iloc[-1],
        "Equity Growth (%)": portfolio_hold_growth_pct
    }])

    summary_hold_df = pd.concat([summary_hold_df, portfolio_hold_row], ignore_index=True)

    summary_hold_display = summary_hold_df.copy()
    summary_hold_display["Final Equity (IDR)"] = summary_hold_display["Final Equity (IDR)"].map(lambda x: f"{x:,.0f}")
    summary_hold_display["Price Growth (1Y %)"] = summary_hold_display["Price Growth (1Y %)"].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
    summary_hold_display["Equity Growth (%)"] = summary_hold_display["Equity Growth (%)"].map(lambda x: f"{x:.2f}%")

    st.dataframe(summary_hold_display, use_container_width=True)

    st.success("Simulation completed: Rebalancing vs Buy & Hold comparison ready.")
