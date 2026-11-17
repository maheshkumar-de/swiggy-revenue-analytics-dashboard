
import streamlit as st
import pandas as pd
import altair as alt
from snowflake.snowpark.context import get_active_session

# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Swiggy | Restaurant Analytics",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 2. SWIGGY-INSPIRED DESIGN
# ============================================================

SWIGGY_ORANGE = "#FF5200"
LIGHT_ORANGE = "#FFF0E8"
BACKGROUND = "#FFFAF7"

st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {BACKGROUND};
        }}

        [data-testid="stSidebar"] {{
            background-color: {LIGHT_ORANGE};
        }}

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            color: {SWIGGY_ORANGE};
        }}

        .main-title {{
            color: {SWIGGY_ORANGE};
            font-size: 34px;
            font-weight: 800;
            margin-bottom: 0;
        }}

        .sub-title {{
            color: #444444;
            font-size: 19px;
            margin-top: 0;
        }}

        .section-title {{
            color: #292929;
            font-size: 22px;
            font-weight: 700;
            margin-top: 15px;
        }}

        .kpi-card {{
            background-color: white;
            padding: 18px;
            border-radius: 12px;
            border-left: 5px solid {SWIGGY_ORANGE};
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            min-height: 105px;
        }}

        .kpi-label {{
            color: #666666;
            font-size: 14px;
            font-weight: 600;
        }}

        .kpi-value {{
            color: #222222;
            font-size: 25px;
            font-weight: 800;
            margin-top: 8px;
        }}

        .insight-card {{
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #FFE0D1;
            margin-bottom: 10px;
        }}

        div[data-testid="stMetric"] {{
            background-color: white;
            padding: 14px;
            border-radius: 10px;
            border-left: 4px solid {SWIGGY_ORANGE};
        }}

        .stButton button {{
            background-color: {SWIGGY_ORANGE};
            color: white;
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# 3. CONNECT TO SNOWFLAKE
# ============================================================

session = get_active_session()


def run_query(query):
    """
    Execute a Snowflake SQL query and return a Pandas DataFrame.
    """
    return session.sql(query).to_pandas()


# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================

def format_currency(value):
    """Format values as Indian Rupees."""
    if pd.isna(value):
        value = 0

    return f"₹{value:,.2f}"


def format_number(value):
    """Format numeric values with commas."""
    if pd.isna(value):
        value = 0

    return f"{value:,.0f}"


def show_kpi_card(label, value):
    """Display a styled KPI card."""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def find_column(dataframe, possible_names):
    """Find a column using a list of possible column names."""
    for name in possible_names:
        if name in dataframe.columns:
            return name

    return None


# ============================================================
# 5. LOAD SNOWFLAKE VIEWS
# ============================================================

YEARLY_QUERY = """
SELECT *
FROM SANDBOX.CONSUMPTION_SCH.VW_YEARLY_REVENUE_KPIS
ORDER BY YEAR
"""

MONTHLY_QUERY = """
SELECT *
FROM SANDBOX.CONSUMPTION_SCH.VW_MONTHLY_REVENUE_KPIS
ORDER BY YEAR, MONTH
"""

RESTAURANT_QUERY = """
SELECT *
FROM SANDBOX.CONSUMPTION_SCH.VW_MONTHLY_REVENUE_BY_RESTAURANT
"""

try:
    yearly_df = run_query(YEARLY_QUERY)
    monthly_df = run_query(MONTHLY_QUERY)
    restaurant_df = run_query(RESTAURANT_QUERY)

except Exception as error:
    st.error(f"Unable to load dashboard data: {error}")
    st.stop()


# Normalize column names
yearly_df.columns = yearly_df.columns.str.upper()
monthly_df.columns = monthly_df.columns.str.upper()
restaurant_df.columns = restaurant_df.columns.str.upper()


# ============================================================
# 6. DASHBOARD HEADER WITH SWIGGY LOGO
# ============================================================

logo_col, title_col, info_col = st.columns([1, 5, 2])

with logo_col:
    try:
        st.image(
            "https://cdn.simpleicons.org/swiggy/FF5200",
            width=75
        )
    except Exception:
        st.markdown("## 🍽️")

with title_col:
    st.markdown(
        """
        <div class="main-title">SWIGGY</div>
        <div class="sub-title">Restaurant Business Analytics</div>
        """,
        unsafe_allow_html=True
    )

with info_col:
    st.markdown(
        f"""
        <div style="
            background-color:{LIGHT_ORANGE};
            padding:15px;
            border-radius:10px;
            text-align:center;
            color:{SWIGGY_ORANGE};
            font-weight:bold;">
            BUSINESS INTELLIGENCE
        </div>
        """,
        unsafe_allow_html=True
    )

st.caption(
    "Restaurant Revenue | Monthly Trends | Restaurant Performance"
)

st.divider()


# ============================================================
# 7. CHECK DATA AVAILABILITY
# ============================================================

if yearly_df.empty:
    st.warning(
        "No yearly KPI data is available. "
        "Please check your Snowflake KPI view."
    )
    st.stop()

required_year_columns = [
    "YEAR",
    "TOTAL_REVENUE",
    "TOTAL_ORDERS"
]

missing_columns = [
    column
    for column in required_year_columns
    if column not in yearly_df.columns
]

if missing_columns:
    st.error(
        f"Missing columns in yearly KPI view: {missing_columns}"
    )
    st.stop()


# ============================================================
# 8. SIDEBAR FILTERS
# ============================================================

st.sidebar.markdown(
    """
    <h2 style="color:#FF5200;">🍽️ Swiggy Analytics</h2>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("### Dashboard Filters")
st.sidebar.caption("Customize your business analysis")

available_years = sorted(
    yearly_df["YEAR"].dropna().astype(int).unique().tolist()
)

if not available_years:
    st.warning("No valid year is available in the KPI data.")
    st.stop()

selected_year = st.sidebar.selectbox(
    "Select Year",
    available_years,
    index=len(available_years) - 1
)

selected_month = None

if not monthly_df.empty and "MONTH" in monthly_df.columns:
    year_month_data = monthly_df[
        monthly_df["YEAR"] == selected_year
    ].copy()

    available_months = sorted(
        year_month_data["MONTH"].dropna().astype(int).unique().tolist()
    )

    month_options = ["All Months"] + available_months

    selected_month = st.sidebar.selectbox(
        "Select Month",
        month_options
    )

st.sidebar.divider()

st.sidebar.markdown("### Data Sources")
st.sidebar.caption("Snowflake Consumption Schema")
st.sidebar.caption("Yearly Revenue KPI")
st.sidebar.caption("Monthly Revenue KPI")
st.sidebar.caption("Restaurant Revenue KPI")


# ============================================================
# 9. OVERALL BUSINESS KPIs
# ============================================================

st.markdown(
    '<div class="section-title">Overall Business Performance</div>',
    unsafe_allow_html=True
)

total_revenue = yearly_df["TOTAL_REVENUE"].sum()
total_orders = yearly_df["TOTAL_ORDERS"].sum()

if "MAX_ORDER_VALUE" in yearly_df.columns:
    max_order_value = yearly_df["MAX_ORDER_VALUE"].max()
else:
    max_order_value = 0

if total_orders > 0:
    overall_average_order = total_revenue / total_orders
else:
    overall_average_order = 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    show_kpi_card(
        "Total Revenue",
        format_currency(total_revenue)
    )

with kpi2:
    show_kpi_card(
        "Total Orders",
        format_number(total_orders)
    )

with kpi3:
    show_kpi_card(
        "Average Revenue / Order",
        format_currency(overall_average_order)
    )

with kpi4:
    show_kpi_card(
        "Maximum Order Value",
        format_currency(max_order_value)
    )


# ============================================================
# 10. SELECTED YEAR PERFORMANCE
# ============================================================

st.divider()

st.markdown(
    f'<div class="section-title">{selected_year} Performance</div>',
    unsafe_allow_html=True
)

selected_year_df = yearly_df[
    yearly_df["YEAR"].astype(int) == selected_year
]

if selected_year_df.empty:
    st.warning("No KPI data found for the selected year.")
    st.stop()

year_row = selected_year_df.iloc[0]

year_revenue = year_row["TOTAL_REVENUE"]
year_orders = year_row["TOTAL_ORDERS"]

year_avg_order = year_row.get(
    "AVG_REVENUE_PER_ORDER",
    year_revenue / year_orders if year_orders else 0
)

year_avg_item = year_row.get(
    "AVG_REVENUE_PER_ITEM",
    0
)

year_max_order = year_row.get(
    "MAX_ORDER_VALUE",
    0
)

# Previous year comparison
previous_year_df = yearly_df[
    yearly_df["YEAR"].astype(int) == selected_year - 1
]

previous_year_revenue = None

if not previous_year_df.empty:
    previous_year_revenue = previous_year_df.iloc[0]["TOTAL_REVENUE"]

    if previous_year_revenue != 0:
        revenue_change = (
            (year_revenue - previous_year_revenue)
            / previous_year_revenue
        ) * 100
    else:
        revenue_change = None
else:
    revenue_change = None

y1, y2, y3, y4, y5 = st.columns(5)

with y1:
    show_kpi_card(
        "Year Revenue",
        format_currency(year_revenue)
    )

with y2:
    show_kpi_card(
        "Year Orders",
        format_number(year_orders)
    )

with y3:
    show_kpi_card(
        "Avg Revenue / Order",
        format_currency(year_avg_order)
    )

with y4:
    show_kpi_card(
        "Avg Revenue / Item",
        format_currency(year_avg_item)
    )

with y5:
    show_kpi_card(
        "Max Order Value",
        format_currency(year_max_order)
    )

if revenue_change is not None:
    if revenue_change > 0:
        st.success(
            f"Revenue increased by {revenue_change:.2f}% "
            f"compared with {selected_year - 1}."
        )
    elif revenue_change < 0:
        st.warning(
            f"Revenue decreased by {abs(revenue_change):.2f}% "
            f"compared with {selected_year - 1}."
        )
    else:
        st.info("Revenue is unchanged compared with the previous year.")
else:
    st.info("Previous-year revenue comparison is not available.")


# ============================================================
# 11. MONTHLY REVENUE ANALYSIS
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">Monthly Revenue Analysis</div>',
    unsafe_allow_html=True
)

if monthly_df.empty:
    st.info("No monthly revenue data is available.")

else:
    monthly_year_df = monthly_df[
        monthly_df["YEAR"].astype(int) == selected_year
    ].copy()

    if selected_month != "All Months" and selected_month is not None:
        monthly_year_df = monthly_year_df[
            monthly_year_df["MONTH"].astype(int) == int(selected_month)
        ]

    if monthly_year_df.empty:
        st.info("No monthly data is available for this selection.")

    else:
        monthly_year_df["MONTH"] = (
            monthly_year_df["MONTH"].astype(int)
        )

        monthly_year_df = monthly_year_df.sort_values("MONTH")

        month_names = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December"
        }

        monthly_year_df["MONTH_NAME"] = (
            monthly_year_df["MONTH"].map(month_names)
        )

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### Monthly Revenue")

            revenue_chart = alt.Chart(
                monthly_year_df
            ).mark_bar(
                color=SWIGGY_ORANGE,
                cornerRadiusTopLeft=5,
                cornerRadiusTopRight=5
            ).encode(
                x=alt.X(
                    "MONTH_NAME:N",
                    sort=list(month_names.values()),
                    title="Month"
                ),
                y=alt.Y(
                    "TOTAL_REVENUE:Q",
                    title="Revenue"
                ),
                tooltip=[
                    "MONTH_NAME",
                    alt.Tooltip(
                        "TOTAL_REVENUE:Q",
                        format=",.2f"
                    )
                ]
            ).properties(
                height=350
            )

            st.altair_chart(
                revenue_chart,
                use_container_width=True
            )

        with chart_col2:
            st.markdown("#### Revenue Trend")

            trend_chart = alt.Chart(
                monthly_year_df
            ).mark_line(
                color=SWIGGY_ORANGE,
                point=True,
                strokeWidth=3
            ).encode(
                x=alt.X(
                    "MONTH_NAME:N",
                    sort=list(month_names.values()),
                    title="Month"
                ),
                y=alt.Y(
                    "TOTAL_REVENUE:Q",
                    title="Revenue"
                ),
                tooltip=[
                    "MONTH_NAME",
                    alt.Tooltip(
                        "TOTAL_REVENUE:Q",
                        format=",.2f"
                    )
                ]
            ).properties(
                height=350
            )

            st.altair_chart(
                trend_chart,
                use_container_width=True
            )

        st.markdown("#### Monthly Revenue Details")

        display_monthly_df = monthly_year_df.copy()

        columns_to_show = [
            column
            for column in [
                "YEAR",
                "MONTH",
                "MONTH_NAME",
                "TOTAL_REVENUE",
                "TOTAL_ORDERS",
                "AVG_REVENUE_PER_ORDER"
            ]
            if column in display_monthly_df.columns
        ]

        st.dataframe(
            display_monthly_df[columns_to_show],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 12. TOP 10 RESTAURANTS
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">Restaurant Performance</div>',
    unsafe_allow_html=True
)

if restaurant_df.empty:
    st.info("No restaurant performance data is available.")

else:
    restaurant_year_col = find_column(
        restaurant_df,
        ["YEAR"]
    )

    restaurant_month_col = find_column(
        restaurant_df,
        ["MONTH"]
    )

    restaurant_name_col = find_column(
        restaurant_df,
        [
            "RESTAURANT_NAME",
            "RESTAURANT",
            "NAME"
        ]
    )

    restaurant_revenue_col = find_column(
        restaurant_df,
        [
            "TOTAL_REVENUE",
            "REVENUE",
            "TOTAL_AMOUNT"
        ]
    )

    restaurant_orders_col = find_column(
        restaurant_df,
        [
            "TOTAL_ORDERS",
            "ORDER_COUNT",
            "ORDERS"
        ]
    )

    if (
        restaurant_year_col is None
        or restaurant_name_col is None
        or restaurant_revenue_col is None
    ):
        st.warning(
            "The restaurant view does not contain the expected "
            "year, restaurant name, or revenue columns. "
            "Please check the view column names."
        )

        st.dataframe(
            restaurant_df.head(20),
            use_container_width=True
        )

    else:
        restaurant_filtered_df = restaurant_df[
            restaurant_df[restaurant_year_col].astype(int) == selected_year
        ].copy()

        if (
            selected_month != "All Months"
            and selected_month is not None
            and restaurant_month_col is not None
        ):
            restaurant_filtered_df = restaurant_filtered_df[
                restaurant_filtered_df[
                    restaurant_month_col
                ].astype(int) == int(selected_month)
            ]

        if restaurant_filtered_df.empty:
            st.info(
                "No restaurant data is available for the selected "
                "year and month."
            )

        else:
            restaurant_filtered_df = (
                restaurant_filtered_df.sort_values(
                    restaurant_revenue_col,
                    ascending=False
                ).head(10)
            )

            left_col, right_col = st.columns([3, 2])

            with left_col:
                st.markdown("#### Top 10 Restaurants by Revenue")

                restaurant_chart = alt.Chart(
                    restaurant_filtered_df
                ).mark_bar(
                    color=SWIGGY_ORANGE,
                    cornerRadiusEnd=5
                ).encode(
                    x=alt.X(
                        f"{restaurant_revenue_col}:Q",
                        title="Revenue"
                    ),
                    y=alt.Y(
                        f"{restaurant_name_col}:N",
                        sort="-x",
                        title="Restaurant"
                    ),
                    tooltip=[
                        restaurant_name_col,
                        alt.Tooltip(
                            f"{restaurant_revenue_col}:Q",
                            format=",.2f"
                        )
                    ]
                ).properties(
                    height=380
                )

                st.altair_chart(
                    restaurant_chart,
                    use_container_width=True
                )

            with right_col:
                st.markdown("#### Restaurant Revenue Details")

                display_columns = [
                    restaurant_name_col,
                    restaurant_revenue_col
                ]

                if restaurant_orders_col is not None:
                    display_columns.append(
                        restaurant_orders_col
                    )

                st.dataframe(
                    restaurant_filtered_df[display_columns],
                    use_container_width=True,
                    hide_index=True
                )


# ============================================================
# 13. AUTOMATIC BUSINESS INSIGHTS
# ============================================================

st.divider()

st.markdown(
    '<div class="section-title">Business Insights</div>',
    unsafe_allow_html=True
)

insight_col1, insight_col2 = st.columns(2)

with insight_col1:
    st.markdown(
        '<div class="insight-card">📊 <b>Revenue Insight</b></div>',
        unsafe_allow_html=True
    )

    st.write(
        f"Total revenue for {selected_year} is "
        f"**{format_currency(year_revenue)}**."
    )

    st.markdown(
        '<div class="insight-card">🛒 <b>Order Insight</b></div>',
        unsafe_allow_html=True
    )

    st.write(
        f"The total number of orders in {selected_year} is "
        f"**{format_number(year_orders)}**."
    )

with insight_col2:
    st.markdown(
        '<div class="insight-card">💰 <b>Average Order Insight</b></div>',
        unsafe_allow_html=True
    )

    st.write(
        f"Average revenue per order is "
        f"**{format_currency(year_avg_order)}**."
    )

    st.markdown(
        '<div class="insight-card">🏆 <b>Best Month Insight</b></div>',
        unsafe_allow_html=True
    )

    if not monthly_df.empty:
        insight_month_df = monthly_df[
            monthly_df["YEAR"].astype(int) == selected_year
        ].copy()

        if not insight_month_df.empty:
            best_month_row = insight_month_df.loc[
                insight_month_df["TOTAL_REVENUE"].idxmax()
            ]

            best_month_number = int(best_month_row["MONTH"])

            best_month_name = month_names.get(
                best_month_number,
                str(best_month_number)
            )

            best_month_revenue = best_month_row["TOTAL_REVENUE"]

            st.write(
                f"**{best_month_name}** had the highest monthly revenue "
                f"at **{format_currency(best_month_revenue)}**."
            )
        else:
            st.write("Monthly insight is not available.")
    else:
        st.write("Monthly insight is not available.")


# ============================================================
# 14. PRODUCT CATALOG
# ============================================================

st.divider()

with st.expander("🛍️ View Product Catalog", expanded=False):

    st.markdown("### Product Catalog")

    try:
        catalog_query = """
            SELECT *
            FROM PROD_DB.PROD_SCH_RAW.PRODUCTS
            ORDER BY PRODUCT_ID
            LIMIT 500
        """

        catalog_df = run_query(catalog_query)
        catalog_df.columns = catalog_df.columns.str.upper()

        if catalog_df.empty:
            st.info("No product records are available.")

        else:
            st.success(
                f"Loaded {len(catalog_df)} product records."
            )

            search_text = st.text_input(
                "Search products",
                placeholder="Enter a product name or keyword"
            )

            if search_text:
                searchable_columns = [
                    column
                    for column in catalog_df.columns
                    if catalog_df[column].dtype == "object"
                ]

                if searchable_columns:
                    search_mask = catalog_df[
                        searchable_columns
                    ].apply(
                        lambda column: column.astype(str).str.contains(
                            search_text,
                            case=False,
                            na=False
                        )
                    ).any(axis=1)

                    catalog_df = catalog_df[search_mask]

            st.dataframe(
                catalog_df,
                use_container_width=True,
                hide_index=True
            )

    except Exception as error:
        st.error(
            f"Product catalog could not be loaded: {error}"
        )


# ============================================================
# 15. FOOTER
# ============================================================

st.divider()

st.markdown(
    f"""
    <div style="
        text-align:center;
        color:#777777;
        padding:15px;
        font-size:13px;">
        <b style="color:{SWIGGY_ORANGE};">
            SWIGGY RESTAURANT ANALYTICS
        </b>
        <br>
        Powered by Snowflake and Streamlit
        <br>
        Revenue | Orders | Restaurant Performance
    </div>
    """,
    unsafe_allow_html=True
)
