
import streamlit as st
import pandas as pd
import plotly.express as px

from src.allocation import allocate_water, optimize_fair_allocation
from src.uncertainty import simulate_rainfall_scenarios


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Mettur Water Allocation DSS",
    page_icon="💧",
    layout="wide"
)

# Consistent, restrained visual theme
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = ["#287D8E", "#16324F", "#7CA6B8", "#C49A55", "#6B8E7D"]

st.markdown("""
<style>
    .stApp { background-color: #F5F7FA; color: #1F2937; }
    .block-container { padding-top: 3rem; padding-bottom: 3rem; max-width: 1500px; }
    h1 { color: #16324F !important; font-weight: 750 !important; letter-spacing: -0.4px; }
    h2, h3 { color: #214761 !important; font-weight: 650 !important; }
    [data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #DCE5ED;
        border-left: 4px solid #287D8E; border-radius: 10px;
        padding: 15px 17px; box-shadow: 0 2px 8px rgba(22,50,79,.05);
        min-width: 0;
    }
    [data-testid="stMetricValue"] { color: #16324F; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #526579; }
    [data-testid="stSidebar"] { background: #EDF2F7; border-right: 1px solid #DCE5ED; }
    [data-testid="stDataFrame"] { border: 1px solid #DCE5ED; border-radius: 8px; }
    [data-testid="stExpander"] { background: #FFFFFF; border: 1px solid #DCE5ED; border-radius: 9px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: 1px solid #DCE5ED; }
    .stTabs [data-baseweb="tab"] { padding: 11px 16px; font-weight: 600; }
    hr { border-color: #DCE5ED; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="padding: 8px 0 16px 0;">
  <div style="color:#287D8E;font-size:12px;font-weight:700;letter-spacing:2px;">
    WATER RESOURCE MANAGEMENT · DECISION SUPPORT
  </div>
  <h1 style="margin:8px 0 4px;color:#16324F;font-size:34px;">
    💧 Dynamic Water Reservoir Allocation
  </h1>
  <p style="color:#64748B;font-size:15px;margin:0;">
    Data-driven analysis and fair water distribution planning for Mettur Reservoir, Tamil Nadu
  </p>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# LOAD REAL RESERVOIR DATA
# --------------------------------------------------

@st.cache_data
def load_data():
    data = pd.read_csv("data/reservoir_daily.csv")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    data = data[data["reservoir_slug"] == "mettur"].copy()
    data = data.dropna(subset=["date", "storage_mcft"])
    data = data.sort_values("date").reset_index(drop=True)

    if data.empty:
        raise ValueError("No Mettur records were found in the dataset.")

    data["storage_percentage"] = (
        data["storage_mcft"] / data["capacity_mcft"] * 100
    )

    data["outflow_mcft_day"] = (
        data["outflow_cusecs"] * 86400 / 1_000_000
    )

    return data


try:
    df = load_data()
except Exception as error:
    st.error(f"Unable to load the reservoir dataset: {error}")
    st.stop()


latest = df.iloc[-1]
latest_date = latest["date"]
latest_storage = float(latest["storage_mcft"])
capacity = float(latest["capacity_mcft"])


st.info(
    f"Historical observations: {df['date'].min():%d %b %Y} – "
    f"{latest_date:%d %b %Y}. "
    "Allocation demands and scenario multipliers are illustrative "
    "planning assumptions, not official demand estimates or forecasts."
)


overview_tab, allocation_tab, history_tab, simulation_tab = st.tabs([
    "Overview", "Allocation", "Historical Analysis", "Simulation"
])

with overview_tab:
    # --------------------------------------------------
    # OVERVIEW
    # --------------------------------------------------

    st.subheader("1. Mettur Reservoir Overview")

    k1, k2, k3, k4 = st.columns(4)

    k1.metric("Latest Recorded Storage", f"{latest_storage:,.0f} MCFT")
    k2.metric("Reservoir Capacity", f"{capacity:,.0f} MCFT")
    k3.metric(
        "Storage Level",
        f"{latest['storage_percentage']:.1f}%"
    )

    if pd.notna(latest["outflow_mcft_day"]):
        k4.metric(
            "Latest Recorded Outflow",
            f"{latest['outflow_mcft_day']:,.2f} MCFT/day"
        )
    else:
        k4.metric("Latest Recorded Outflow", "Unavailable")


    if latest_storage > capacity:
        st.warning(
            "The latest recorded storage exceeds the capacity value "
            "in the dataset. The observation has not been altered."
        )


    # --------------------------------------------------
    # HISTORICAL CHARTS
    # --------------------------------------------------

    st.subheader("2. Historical Reservoir Trends")

    tab_storage, tab_flow, tab_records = st.tabs(
        ["Storage", "Inflow & Outflow", "Data Records"]
    )

    with tab_storage:
        storage_chart = px.line(
            df,
            x="date",
            y="storage_mcft",
            title="Mettur Reservoir Storage Over Time",
            labels={
                "date": "Date",
                "storage_mcft": "Storage (MCFT)"
            }
        )
        storage_chart.update_layout(hovermode="x unified")
        st.plotly_chart(storage_chart, width="stretch")

        percentage_chart = px.line(
            df,
            x="date",
            y="storage_percentage",
            title="Recorded Storage as a Percentage of Listed Capacity",
            labels={
                "date": "Date",
                "storage_percentage": "Storage (% of capacity)"
            }
        )
        percentage_chart.add_hline(
            y=100,
            line_dash="dash",
            annotation_text="Listed capacity"
        )
        st.plotly_chart(percentage_chart, width="stretch")

    with tab_flow:
        flow_df = df[["date", "inflow_cusecs", "outflow_cusecs"]].copy()
        flow_df = flow_df.melt(
            id_vars="date",
            value_vars=["inflow_cusecs", "outflow_cusecs"],
            var_name="Flow Type",
            value_name="Flow (cusecs)"
        )
        flow_df["Flow Type"] = flow_df["Flow Type"].map({
            "inflow_cusecs": "Inflow",
            "outflow_cusecs": "Outflow"
        })

        flow_chart = px.line(
            flow_df,
            x="date",
            y="Flow (cusecs)",
            color="Flow Type",
            title="Recorded Daily Flow Rates",
            labels={"date": "Date"}
        )
        st.plotly_chart(flow_chart, width="stretch")

        st.caption(
            "Flow values are recorded in cusecs. Missing values are left "
            "missing rather than treated as zero."
        )

    with tab_records:
        st.write(f"Number of available Mettur records: {len(df):,}")
        st.dataframe(df, hide_index=True, width="stretch")


with allocation_tab:
    # --------------------------------------------------
    # DAILY ALLOCATION COMPARISON
    # --------------------------------------------------

    st.divider()
    st.subheader("3. Daily Water Allocation Comparison")

    st.write(
        "Compare the existing priority-based allocation method with a "
        "maximin fairness model. The budget is based on a selected "
        "historical outflow observation, not a forecast of future supply."
    )

    valid_flow_dates = df.loc[
        df["outflow_mcft_day"].notna(), "date"
    ].sort_values()

    if valid_flow_dates.empty:
        st.warning("No recorded outflow values are available for simulation.")
        st.stop()

    with st.sidebar:
        st.header("Daily Allocation Settings")

        selected_date = st.selectbox(
            "Choose a historical observation date",
            options=valid_flow_dates.tolist(),
            index=len(valid_flow_dates) - 1,
            format_func=lambda date: pd.Timestamp(date).strftime("%d %b %Y")
        )

        selected_row = df.loc[df["date"] == selected_date].iloc[-1]
        daily_budget = float(selected_row["outflow_mcft_day"])

        st.markdown("**Selected Outflow Budget**")
        st.markdown(
            f"<div style='background:#FFFFFF;border:1px solid #DCE5ED;"
            f"border-left:4px solid #287D8E;border-radius:10px;padding:12px 14px;'>"
            f"<div style='font-size:27px;font-weight:750;color:#16324F;"
            f"white-space:normal;overflow-wrap:anywhere;'>{daily_budget:,.2f}</div>"
            f"<div style='font-size:12px;color:#64748B;'>MCFT/day</div></div>",
            unsafe_allow_html=True
        )

        daily_reserve = st.number_input(
            "Protected part of daily budget (MCFT)",
            min_value=0.0,
            max_value=float(daily_budget),
            value=0.0,
            step=1.0,
            help="Illustrative reserve deducted from this daily budget."
        )

        st.caption("Daily demand assumptions — MCFT/day")

        domestic_daily = st.number_input(
            "Domestic demand",
            min_value=0.0,
            value=30.0,
            step=5.0
        )

        agriculture_daily = st.number_input(
            "Agriculture demand",
            min_value=0.0,
            value=60.0,
            step=5.0
        )

        industry_daily = st.number_input(
            "Industry demand",
            min_value=0.0,
            value=20.0,
            step=5.0
        )


    demands = {
        "domestic_demand": domestic_daily,
        "agriculture_demand": agriculture_daily,
        "industry_demand": industry_daily
    }

    sector_names = ["Domestic", "Agriculture", "Industry"]
    demand_values = [
        domestic_daily,
        agriculture_daily,
        industry_daily
    ]

    baseline = allocate_water(
        available_water=daily_budget,
        reserve_water=daily_reserve,
        **demands
    )

    fair = optimize_fair_allocation(
        available_water=daily_budget,
        reserve_water=daily_reserve,
        **demands
    )


    def get_baseline_value(result, possible_keys):
        """Support the allocation function's existing TMC or MCFT labels."""
        for key in possible_keys:
            if key in result:
                return float(result[key])
        raise KeyError(
            f"Expected one of these allocation result keys: {possible_keys}. "
            f"Available keys: {list(result.keys())}"
        )


    baseline_allocations = [
        get_baseline_value(
            baseline,
            ["Domestic Allocation (MCFT)", "Domestic Allocation (TMC)"]
        ),
        get_baseline_value(
            baseline,
            ["Agriculture Allocation (MCFT)", "Agriculture Allocation (TMC)"]
        ),
        get_baseline_value(
            baseline,
            ["Industry Allocation (MCFT)", "Industry Allocation (TMC)"]
        )
    ]

    fair_allocations = [
        fair["Domestic"],
        fair["Agriculture"],
        fair["Industry"]
    ]


    def build_allocation_table(allocations, demands_list, method):
        result_df = pd.DataFrame({
            "Sector": sector_names,
            "Demand (MCFT/day)": demands_list,
            "Allocated (MCFT/day)": allocations
        })

        result_df["Unmet Demand (MCFT/day)"] = (
            result_df["Demand (MCFT/day)"]
            - result_df["Allocated (MCFT/day)"]
        ).clip(lower=0)

        result_df["Demand Satisfied (%)"] = result_df.apply(
            lambda row: (
                100 * row["Allocated (MCFT/day)"]
                / row["Demand (MCFT/day)"]
                if row["Demand (MCFT/day)"] > 0
                else 100.0
            ),
            axis=1
        )

        result_df["Method"] = method
        return result_df


    baseline_table = build_allocation_table(
        baseline_allocations, demand_values, "Priority-based"
    )

    fair_table = build_allocation_table(
        fair_allocations, demand_values, "Maximin fair"
    )

    comparison = pd.concat(
        [baseline_table, fair_table],
        ignore_index=True
    )

    total_demand = sum(demand_values)
    usable_daily_budget = max(0.0, daily_budget - daily_reserve)

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Daily Demand", f"{total_demand:,.2f} MCFT/day")
    c2.metric("Usable Daily Budget", f"{usable_daily_budget:,.2f} MCFT/day")

    baseline_total = sum(baseline_allocations)
    c3.metric("Priority-Based Allocation", f"{baseline_total:,.2f} MCFT/day")

    st.markdown("#### Priority-based allocation")
    st.dataframe(baseline_table, hide_index=True, width="stretch")

    st.markdown("#### Maximin fair allocation")
    st.dataframe(fair_table, hide_index=True, width="stretch")

    chart_data = comparison.melt(
        id_vars=["Sector", "Method"],
        value_vars=["Demand (MCFT/day)", "Allocated (MCFT/day)"],
        var_name="Measure",
        value_name="Water (MCFT/day)"
    )

    comparison_chart = px.bar(
        chart_data,
        x="Sector",
        y="Water (MCFT/day)",
        color="Measure",
        barmode="group",
        facet_col="Method",
        title="Demand vs Allocation by Method"
    )
    st.plotly_chart(comparison_chart, width="stretch")

    if total_demand > usable_daily_budget:
        st.warning(
            "Shortage under the selected assumptions: total demand exceeds "
            "the usable daily budget. Compare sector satisfaction to understand "
            "how the two methods distribute the shortage."
        )
    else:
        st.success(
            "The usable daily budget is sufficient to meet all entered demands."
        )

    st.caption(
        "Priority-based allocation follows the existing priority rules. "
        "Maximin allocation seeks to maximize the lowest sector demand-"
        "satisfaction percentage. Neither method represents an official "
        "water-release decision."
    )


with simulation_tab:
    # --------------------------------------------------
    # STORAGE-BASED UNCERTAINTY SCENARIOS
    # --------------------------------------------------

    st.divider()
    st.subheader("4. Uncertain Inflow: Drought, Normal and Wet Scenarios")

    st.write(
        "This separate planning exercise starts from recorded reservoir "
        "storage and adds an assumed inflow. It does not forecast rainfall "
        "or model releases, evaporation or all reservoir operations."
    )

    with st.expander("Configure illustrative storage scenarios", expanded=True):
        sc1, sc2, sc3 = st.columns(3)

        with sc1:
            scenario_reserve_pct = st.slider(
                "Protected reserve (% of listed capacity)",
                min_value=0,
                max_value=80,
                value=20,
                step=5
            )

        with sc2:
            expected_inflow = st.number_input(
                "Assumed inflow (MCFT per planning period)",
                min_value=0.0,
                value=1000.0,
                step=100.0
            )

        with sc3:
            st.write("Scenario multipliers")
            st.write("Drought: 0.4×")
            st.write("Normal: 1.0×")
            st.write("Wet: 1.6×")

    scenario_reserve = capacity * scenario_reserve_pct / 100

    scenario_results = simulate_rainfall_scenarios(
        current_storage_mcft=latest_storage,
        capacity_mcft=capacity,
        reserve_water_mcft=scenario_reserve,
        expected_inflow_mcft=expected_inflow
    )

    scenario_df = pd.DataFrame(scenario_results)

    st.caption(
        f"Starting storage: {latest_storage:,.2f} MCFT, based on the latest "
        f"available observation dated {latest_date:%d %b %Y}. "
        f"Protected reserve: {scenario_reserve:,.2f} MCFT."
    )

    scenario_chart = px.bar(
        scenario_df,
        x="Scenario",
        y="Usable Storage (MCFT)",
        color="Scenario",
        title="Usable Storage Under Illustrative Inflow Scenarios",
        text_auto=".2f"
    )
    st.plotly_chart(scenario_chart, width="stretch")

    st.dataframe(scenario_df, hide_index=True, width="stretch")


    # --------------------------------------------------
    # OPTIONAL FAIR ALLOCATION UNDER EACH STORAGE SCENARIO
    # --------------------------------------------------

    st.markdown("#### Fair allocation under storage scenarios")

    st.write(
        "Enter separate illustrative demands for this planning period. "
        "These values are in MCFT, not MCFT/day."
    )

    scd1, scd2, scd3 = st.columns(3)

    with scd1:
        domestic_period = st.number_input(
            "Domestic demand (MCFT)",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            key="domestic_period"
        )

    with scd2:
        agriculture_period = st.number_input(
            "Agriculture demand (MCFT)",
            min_value=0.0,
            value=2000.0,
            step=100.0,
            key="agriculture_period"
        )

    with scd3:
        industry_period = st.number_input(
            "Industry demand (MCFT)",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            key="industry_period"
        )

    period_demands = {
        "domestic_demand": domestic_period,
        "agriculture_demand": agriculture_period,
        "industry_demand": industry_period
    }

    scenario_allocations = []

    for _, scenario_row in scenario_df.iterrows():
        allocation = optimize_fair_allocation(
            available_water=float(scenario_row["Usable Storage (MCFT)"]),
            reserve_water=0,
            **period_demands
        )

        for sector in sector_names:
            demand = period_demands[
                f"{sector.lower()}_demand"
            ]

            allocated = allocation[sector]

            scenario_allocations.append({
                "Scenario": scenario_row["Scenario"],
                "Sector": sector,
                "Demand (MCFT)": demand,
                "Allocated (MCFT)": allocated,
                "Unmet Demand (MCFT)": max(0.0, demand - allocated),
                "Demand Satisfied (%)": (
                    100 * allocated / demand if demand > 0 else 100.0
                ),
                "Minimum Satisfaction (%)": allocation[
                    "Minimum Satisfaction (%)"
                ]
            })

    scenario_allocation_df = pd.DataFrame(scenario_allocations)

    st.dataframe(
        scenario_allocation_df,
        hide_index=True,
        width="stretch"
    )

    scenario_allocation_chart = px.bar(
        scenario_allocation_df,
        x="Sector",
        y="Allocated (MCFT)",
        color="Scenario",
        barmode="group",
        title="Fair Allocation Across Inflow Scenarios"
    )
    st.plotly_chart(scenario_allocation_chart, width="stretch")


with history_tab:
    # --------------------------------------------------
    # PROJECT LIMITATIONS
    # --------------------------------------------------

    with st.expander("Data, assumptions and model limitations"):
        st.markdown("""
        - **Historical data:** Mettur records loaded from
          `data/reservoir_daily.csv`. Missing dates are not filled with
          invented observations.
        - **Daily allocation:** uses a selected historical outflow rate as
          a one-day supply budget. The sector demands and protected daily
          reserve are user-defined assumptions.
        - **Storage scenarios:** use assumed inflow multipliers of 0.4, 1.0
          and 1.6. These are stress-test scenarios, not rainfall forecasts.
        - **Fairness model:** maximizes the minimum sector demand-satisfaction
          ratio. It does not determine real-world legal or policy priorities.
        - **Not yet included:** a validated rainfall forecasting model,
          a complete multi-period reservoir water balance, evaporation,
          planned releases, verified sector demand data and operational rules.
        """)


with history_tab:
    # ============================================================
    # HISTORICAL EVALUATION + DYNAMIC SIMULATION
    # ============================================================

    st.header("Historical Allocation Evaluation")
    st.caption(
        "570 recorded Mettur observations. Sector demands are illustrative "
        "assumptions: Domestic 30, Agriculture 60, Industry 20 MCFT/day."
    )


    sector_demands = {
        "Domestic": 30.0,
        "Agriculture": 60.0,
        "Industry": 20.0
    }

    # Historical evaluation using recorded daily outflow
    # Load the dataset independently of notebook variables.
    # The dashboard uses df, which already contains the Mettur records.
    historical_data = df.copy()
    historical_data["date"] = pd.to_datetime(historical_data["date"], errors="coerce")
    historical_data["observed_outflow_mcft_day"] = (
        pd.to_numeric(historical_data["outflow_cusecs"], errors="coerce")
        * 86400 / 1_000_000
    )
    historical_data = historical_data.dropna(
        subset=["observed_outflow_mcft_day"]
    )

    evaluation_rows = []

    for _, row in historical_data.iterrows():
        budget = max(0.0, row["observed_outflow_mcft_day"])

        baseline = allocate_water(
            available_water=budget,
            reserve_water=0,
            domestic_demand=30,
            agriculture_demand=60,
            industry_demand=20
        )

        fair = optimize_fair_allocation(
            available_water=budget,
            reserve_water=0,
            domestic_demand=30,
            agriculture_demand=60,
            industry_demand=20
        )

        item = {"Date": row["date"]}

        for sector, demand in sector_demands.items():
            base_alloc = baseline[f"{sector} Allocation (MCFT)"]
            fair_alloc = fair[sector]

            item[f"Baseline {sector} Satisfaction (%)"] = (
                100 * base_alloc / demand
            )
            item[f"Fair {sector} Satisfaction (%)"] = (
                100 * fair_alloc / demand
            )

        item["Baseline Minimum Satisfaction (%)"] = min(
            item[f"Baseline {s} Satisfaction (%)"]
            for s in sector_demands
        )
        item["Fair Minimum Satisfaction (%)"] = fair[
            "Minimum Satisfaction (%)"
        ]
        item["Baseline Industry Zero"] = (
            baseline["Industry Allocation (MCFT)"] <= 1e-8
        )
        item["Fair Industry Zero"] = fair["Industry"] <= 1e-8

        evaluation_rows.append(item)

    dashboard_evaluation = pd.DataFrame(evaluation_rows)

    evaluation_summary = pd.DataFrame({
        "Metric": [
            "Domestic average satisfaction (%)",
            "Agriculture average satisfaction (%)",
            "Industry average satisfaction (%)",
            "Average minimum sector satisfaction (%)",
            "Days industry received zero water"
        ],
        "Priority Baseline": [
            dashboard_evaluation["Baseline Domestic Satisfaction (%)"].mean(),
            dashboard_evaluation["Baseline Agriculture Satisfaction (%)"].mean(),
            dashboard_evaluation["Baseline Industry Satisfaction (%)"].mean(),
            dashboard_evaluation["Baseline Minimum Satisfaction (%)"].mean(),
            dashboard_evaluation["Baseline Industry Zero"].sum()
        ],
        "Maximin Fair": [
            dashboard_evaluation["Fair Domestic Satisfaction (%)"].mean(),
            dashboard_evaluation["Fair Agriculture Satisfaction (%)"].mean(),
            dashboard_evaluation["Fair Industry Satisfaction (%)"].mean(),
            dashboard_evaluation["Fair Minimum Satisfaction (%)"].mean(),
            dashboard_evaluation["Fair Industry Zero"].sum()
        ]
    })

    st.dataframe(
        evaluation_summary.round(2),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Historical comparison uses recorded outflow as the daily allocation "
        "budget. It evaluates allocation policies, not actual sector deliveries."
    )

with simulation_tab:
    # ------------------------------------------------------------
    # DATA-DERIVED 30-DAY SCENARIOS AND RESERVE SENSITIVITY
    # ------------------------------------------------------------

    st.header("Dynamic 30-Day Reservoir Simulation")
    st.caption(
        "Historical inflow percentiles are used as constant-inflow stress tests, "
        "not as rainfall forecasts. Missing daily inflow observations are not "
        "treated as zero."
    )

    capacity = float(df["capacity_mcft"].max())
    latest_row = df.sort_values("date").iloc[-1]
    starting_storage = float(latest_row["storage_mcft"])

    daily_inflow_series = (
        df.assign(
            date=pd.to_datetime(df["date"], errors="coerce"),
            inflow_mcft_day=(
                pd.to_numeric(df["inflow_cusecs"], errors="coerce")
                * 86400 / 1_000_000
            )
        )
        .set_index("date")["inflow_mcft_day"]
        .sort_index()
        .resample("D")
        .mean()
    )

    rolling_30_day = daily_inflow_series.rolling(
        30, min_periods=30
    ).sum().dropna()

    if rolling_30_day.empty:
        st.error("There are no complete rolling 30-day inflow windows.")
    else:
        scenario_totals = {
            "Drought (10th percentile)": rolling_30_day.quantile(0.10),
            "Normal (50th percentile)": rolling_30_day.quantile(0.50),
            "Wet (90th percentile)": rolling_30_day.quantile(0.90)
        }

        scenario_table = pd.DataFrame([
            {
                "Scenario": name,
                "Historical 30-Day Inflow (MCFT)": total,
                "Average Daily Inflow (MCFT/day)": total / 30
            }
            for name, total in scenario_totals.items()
        ])

        st.subheader("Historical Inflow-Based Scenarios")
        st.dataframe(
            scenario_table.round(2),
            use_container_width=True,
            hide_index=True
        )

        reserve_choice = st.selectbox(
            "Protected reserve for the displayed simulation",
            [10, 20],
            index=1,
            format_func=lambda x: f"{x}% of reservoir capacity"
        )

        simulation_rows = []

        for reserve_pct in [10, 20]:
            reserve = capacity * reserve_pct / 100

            for scenario, total_inflow in scenario_totals.items():
                daily_inflow = total_inflow / 30

                for method in ["Priority Baseline", "Maximin Fair"]:
                    storage = starting_storage

                    for day in range(1, 31):
                        storage_before_release = storage + daily_inflow
                        overflow = max(0.0, storage_before_release - capacity)
                        available = min(capacity, storage_before_release)

                        if method == "Priority Baseline":
                            allocation = allocate_water(
                                available_water=available,
                                reserve_water=reserve,
                                domestic_demand=30,
                                agriculture_demand=60,
                                industry_demand=20
                            )
                            domestic = allocation["Domestic Allocation (MCFT)"]
                            agriculture = allocation["Agriculture Allocation (MCFT)"]
                            industry = allocation["Industry Allocation (MCFT)"]
                        else:
                            allocation = optimize_fair_allocation(
                                available_water=available,
                                reserve_water=reserve,
                                domestic_demand=30,
                                agriculture_demand=60,
                                industry_demand=20
                            )
                            domestic = allocation["Domestic"]
                            agriculture = allocation["Agriculture"]
                            industry = allocation["Industry"]

                        release = domestic + agriculture + industry
                        ending_storage = max(0.0, available - release)

                        simulation_rows.append({
                            "Reserve (%)": reserve_pct,
                            "Scenario": scenario,
                            "Method": method,
                            "Day": day,
                            "Domestic Satisfaction (%)": 100 * domestic / 30,
                            "Agriculture Satisfaction (%)": 100 * agriculture / 60,
                            "Industry Satisfaction (%)": 100 * industry / 20,
                            "Total Release (MCFT)": release,
                            "Ending Storage (MCFT)": ending_storage,
                            "Overflow (MCFT)": overflow
                        })

                        storage = ending_storage

        dashboard_simulation = pd.DataFrame(simulation_rows)

        selected_simulation = dashboard_simulation[
            dashboard_simulation["Reserve (%)"] == reserve_choice
        ]

        st.subheader("Storage Trajectory")
        storage_chart = px.line(
            selected_simulation,
            x="Day",
            y="Ending Storage (MCFT)",
            color="Method",
            line_dash="Scenario",
            title=f"30-Day Storage Projection — {reserve_choice}% Reserve"
        )
        storage_chart.add_hline(
            y=capacity * reserve_choice / 100,
            line_dash="dash",
            annotation_text="Protected reserve"
        )
        st.plotly_chart(storage_chart, use_container_width=True)

        st.subheader("Average Sector Demand Satisfaction")
        satisfaction_summary = selected_simulation.groupby(
            ["Scenario", "Method"]
        ).agg(
            Domestic=("Domestic Satisfaction (%)", "mean"),
            Agriculture=("Agriculture Satisfaction (%)", "mean"),
            Industry=("Industry Satisfaction (%)", "mean"),
            Final_Storage=("Ending Storage (MCFT)", "last")
        ).reset_index()

        st.dataframe(
            satisfaction_summary.round(2),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Reserve Sensitivity")
        reserve_summary = dashboard_simulation.groupby(
            ["Reserve (%)", "Scenario", "Method"]
        ).agg(
            Domestic=("Domestic Satisfaction (%)", "mean"),
            Agriculture=("Agriculture Satisfaction (%)", "mean"),
            Industry=("Industry Satisfaction (%)", "mean"),
            Final_Storage=("Ending Storage (MCFT)", "last")
        ).reset_index()

        st.dataframe(
            reserve_summary.round(2),
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "The simulation assumes constant average daily inflow within each "
            "scenario and fixed illustrative daily demands. It does not model "
            "evaporation, forecast rainfall, or operational rules beyond the "
            "protected reserve and reservoir capacity."
        )
