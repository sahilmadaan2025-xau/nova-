"""
Early-Stage Budget Impact Estimation Tool
Team Pulse Pioneers | NN GBS Hackathon 2026 | Problem Statement #19

This is a working prototype that estimates the change in healthcare
system spending (budget impact) if a new drug is introduced, for
either Type 2 Diabetes or Obesity.

Reference values used as starting points (editable in the app):
  - UK adult population: ~54.5 million (ONS, approx.)
  - Type 2 Diabetes prevalence: ~9% of UK adults (Diabetes UK, ~5.3-6M people)
  - Obesity prevalence: ~30% of UK adults (NHS Health Survey for England 2024)
These are illustrative reference figures for the prototype demo, not
Novo Nordisk internal data. Replace with sourced figures (NICE, WHO GHO,
IHME GBD, World Bank) as your team finalises the model.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Budget Impact Estimator", layout="wide")

st.title("Early-Stage Budget Impact Estimation Tool")
st.caption("Team Pulse Pioneers  |  NN GBS Hackathon 2026  |  Problem Statement #19")

DISEASE_DEFAULTS = {
    "Type 2 Diabetes": {
        "prevalence_pct": 9.0,
        "eligible_pct": 40.0,
        "comparators": [
            {"name": "Metformin / generic oral therapy", "cost_month": 8, "current_share_pct": 55},
            {"name": "Older injectable (e.g. basal insulin)", "cost_month": 45, "current_share_pct": 30},
            {"name": "Other branded oral therapy", "cost_month": 70, "current_share_pct": 15},
        ],
        "new_drug_cost_month": 220,
        "admin_cost_month": 5,
        "monitoring_cost_month": 10,
        "offset_cost_month": 15,
    },
    "Obesity": {
        "prevalence_pct": 30.0,
        "eligible_pct": 25.0,
        "comparators": [
            {"name": "Lifestyle / diet program (no drug)", "cost_month": 5, "current_share_pct": 70},
            {"name": "Older weight-management drug", "cost_month": 60, "current_share_pct": 30},
        ],
        "new_drug_cost_month": 300,
        "admin_cost_month": 8,
        "monitoring_cost_month": 12,
        "offset_cost_month": 25,
    },
}

COUNTRY_POPULATION = {
    "UK": 54_500_000,
    "Germany": 68_000_000,
    "France": 53_000_000,
    "US": 258_000_000,
    "Custom": None,
}

# ---------------- Sidebar Inputs ----------------
st.sidebar.header("1. Population")

disease = st.sidebar.selectbox("Disease area", list(DISEASE_DEFAULTS.keys()))
defaults = DISEASE_DEFAULTS[disease]

country = st.sidebar.selectbox("Country / geography", list(COUNTRY_POPULATION.keys()))
if country == "Custom":
    total_adult_population = st.sidebar.number_input(
        "Total adult population", min_value=1_000_000, value=50_000_000, step=1_000_000
    )
else:
    total_adult_population = COUNTRY_POPULATION[country]
    st.sidebar.write(f"Adult population used: **{total_adult_population:,}**")

prevalence_pct = st.sidebar.slider(
    "Prevalence (% of adults with condition)", 0.0, 60.0, defaults["prevalence_pct"], 0.5
)
eligible_pct = st.sidebar.slider(
    "Eligible for new drug (% of prevalent population)", 0.0, 100.0, defaults["eligible_pct"], 1.0
)
incident_growth_pct = st.sidebar.slider(
    "Annual new (incident) patient growth (% per year)", 0.0, 15.0, 2.0, 0.5,
    help="New patients diagnosed each year, added to the eligible pool (open-cohort)."
)
discontinuation_pct = st.sidebar.slider(
    "Annual discontinuation / attrition (% per year)", 0.0, 15.0, 3.0, 0.5,
    help="Patients leaving treatment each year (death, switch away, discontinuation)."
)

st.sidebar.header("2. Treatment Mix & Uptake")
st.sidebar.write("Current comparators in the market:")
comparator_df = pd.DataFrame(defaults["comparators"])
comparator_df = st.sidebar.data_editor(
    comparator_df, num_rows="dynamic", key="comparators",
    column_config={
        "name": "Comparator",
        "cost_month": st.column_config.NumberColumn("Cost/month (local currency)"),
        "current_share_pct": st.column_config.NumberColumn("Current share (%)"),
    },
)

new_drug_cost_month = st.sidebar.number_input(
    "New drug cost per patient per month", min_value=0, value=defaults["new_drug_cost_month"], step=5
)

st.sidebar.write("Uptake of new drug over time (% of eligible population):")
uptake_y1 = st.sidebar.slider("Year 1 uptake (%)", 0, 100, 10)
uptake_y3 = st.sidebar.slider("Year 3 uptake (%)", 0, 100, 25)
uptake_y5 = st.sidebar.slider("Year 5 uptake (%)", 0, 100, 40)

st.sidebar.header("3. Additional Costs")
admin_cost_month = st.sidebar.number_input(
    "Administration cost / month (new drug)", min_value=0, value=defaults["admin_cost_month"]
)
monitoring_cost_month = st.sidebar.number_input(
    "Monitoring cost / month (new drug)", min_value=0, value=defaults["monitoring_cost_month"]
)
offset_cost_month = st.sidebar.number_input(
    "Cost offset / month (avoided complications, hospitalisations, etc.)",
    min_value=0, value=defaults["offset_cost_month"],
    help="Savings from things the new drug prevents (e.g. avoided hospital visits)."
)

st.sidebar.header("4. Sensitivity Scenario")
scenario = st.sidebar.radio("Scenario", ["Low", "Base", "High"], index=1)
scenario_multiplier = {"Low": 0.8, "Base": 1.0, "High": 1.2}[scenario]

# ---------------- Calculations ----------------

def interpolate_uptake(y1, y3, y5):
    """Simple interpolation to build a 5-year uptake curve from 3 anchor points."""
    years = [1, 2, 3, 4, 5]
    y2 = y1 + (y3 - y1) / 2
    y4 = y3 + (y5 - y3) / 2
    values = [y1, y2, y3, y4, y5]
    return dict(zip(years, values))


uptake_curve = interpolate_uptake(uptake_y1, uptake_y3, uptake_y5)

current_weighted_cost = 0.0
total_current_share = comparator_df["current_share_pct"].sum() if len(comparator_df) else 0
if total_current_share > 0:
    for _, row in comparator_df.iterrows():
        current_weighted_cost += row["cost_month"] * (row["current_share_pct"] / total_current_share)

prevalent_population_y0 = total_adult_population * (prevalence_pct / 100)
eligible_population_y0 = prevalent_population_y0 * (eligible_pct / 100)

rows = []
eligible_population = eligible_population_y0
for year in range(1, 6):
    eligible_population = eligible_population * (1 + incident_growth_pct / 100) * (1 - discontinuation_pct / 100)
    uptake_pct = uptake_curve[year]

    patients_on_new_drug = eligible_population * (uptake_pct / 100)
    patients_on_old_mix = eligible_population - patients_on_new_drug

    new_drug_monthly_cost_per_patient = (
        new_drug_cost_month + admin_cost_month + monitoring_cost_month - offset_cost_month
    ) * scenario_multiplier

    cost_with_new_drug = (
        patients_on_new_drug * new_drug_monthly_cost_per_patient
        + patients_on_old_mix * current_weighted_cost
    ) * 12

    cost_without_new_drug = eligible_population * current_weighted_cost * 12

    budget_impact = cost_with_new_drug - cost_without_new_drug

    rows.append({
        "Year": year,
        "Eligible patients": round(eligible_population),
        "Patients on new drug": round(patients_on_new_drug),
        "Uptake %": round(uptake_pct, 1),
        "Annual cost WITHOUT new drug": round(cost_without_new_drug),
        "Annual cost WITH new drug": round(cost_with_new_drug),
        "Annual budget impact": round(budget_impact),
    })

results_df = pd.DataFrame(rows)
results_df["Cumulative budget impact"] = results_df["Annual budget impact"].cumsum()

# ---------------- Output ----------------
st.subheader(f"Results — {disease} in {country} ({scenario} scenario)")

col1, col2, col3 = st.columns(3)
col1.metric("Eligible population (Year 1)", f"{rows[0]['Eligible patients']:,}")
col2.metric("Year 1 budget impact", f"{rows[0]['Annual budget impact']:,}")
col3.metric("5-year cumulative impact", f"{results_df['Cumulative budget impact'].iloc[-1]:,}")

st.dataframe(results_df, use_container_width=True)

fig = go.Figure()
fig.add_trace(go.Bar(x=results_df["Year"], y=results_df["Annual budget impact"], name="Annual budget impact"))
fig.add_trace(go.Scatter(x=results_df["Year"], y=results_df["Cumulative budget impact"],
                          name="Cumulative budget impact", mode="lines+markers", yaxis="y"))
fig.update_layout(
    title="Budget Impact Over 5 Years",
    xaxis_title="Year",
    yaxis_title="Budget Impact (local currency)",
    legend=dict(orientation="h", y=-0.2),
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Assumptions, data sources & limitations"):
    st.markdown("""
    **Method reference:** ISPOR Good Practices for Budget Impact Analysis; structure inspired by the
    YHEC example Shiny budget impact model.

    **Data sources for real figures (to replace defaults above):**
    - Epidemiology: Orphanet/Orphadata, IHME GHDx (Global Burden of Disease), WHO Global Health Observatory
    - Population denominators: World Bank, UN Population Data, Eurostat, national statistics offices
    - Costs & pricing: Published HTA reports — NICE (UK), HAS (France), IQWiG/G-BA (Germany), PBAC (Australia), CADTH (Canada)

    **Current prototype defaults (for demo purposes only, not Novo Nordisk internal data):**
    - UK adult population ≈ 54.5 million
    - Type 2 Diabetes prevalence ≈ 9% of adults (Diabetes UK)
    - Obesity prevalence ≈ 30% of adults (NHS Health Survey for England 2024)

    **Known limitations of this prototype:**
    - Uptake curve is a simple interpolation between 3 user-set points, not a full diffusion model
    - Subgroup/comorbidity-level breakdown not yet implemented (planned next iteration)
    - Cost offsets are entered as a flat monthly value rather than event-based (e.g. per hospitalisation avoided)
    """)
