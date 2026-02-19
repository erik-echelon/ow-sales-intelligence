"""
Page 1: Ranked Companies

Displays all scored companies using the dual-path scoring methodology.
"""

import logging
import pandas as pd
import streamlit as st

from app.data_loader import (
    load_companies,
    load_penetration_by_company,
    load_scored_companies,
)
from app.ranked_companies_logic import (
    get_empty_state_message,
    get_filtered_count_message,
    set_selected_company,
    sort_by_score_within_segment,
    validate_rank_matches_score_order,
    validate_segment_rank_contiguity,
)
from app.quality_gates import check_entity_resolution_quality

logger = logging.getLogger(__name__)

# Page header
st.title("📊 Ranked Companies")

# =============================================================================
# SCORING METHODOLOGY
# =============================================================================

with st.expander("🎯 Scoring Methodology (Click to expand)"):
    st.markdown("""
Our dual-path scoring system evaluates companies using different methodologies based on their relationship status:

### **Two Scoring Paths**

#### **Path 1: Customer Expansion** (Existing Customers)
For current OpenWorks customers, we identify expansion opportunities:
- **Focus**: Additional locations within existing customer accounts
- **Scoring**: Emphasizes opportunity size and ease of expansion
- **Key Factors**:
  - Building count (more locations = higher score)
  - Current penetration rate (more room to grow = higher score)
  - Sales volume indicators

#### **Path 2: Prospect Acquisition** (New Customers)
For prospective new customers, we evaluate both industry and company attractiveness:

**Final Score = (NAICS Attractiveness × 40%) + (Company Opportunity × 60%)**

**NAICS Attractiveness Score** (0-100):
- **ICP Fit** (25%): Claude AI assessment of industry alignment with OpenWorks' ideal customer profile
- **Market Size** (15%): Nationwide market size in this industry
- **OW Revenue Concentration** (15%): OpenWorks' revenue concentration in this industry
- **OW Building Count** (20%): OpenWorks operational scale in this industry
- **Revenue per Building** (5%): OpenWorks revenue quality in this industry
- **Churn Health** (15%): Customer retention in this industry
- **Ticket Health** (5%): Support ticket quality/volume

**Company Opportunity Score** (0-100):
- **Building Count**: Number of locations (more locations = higher score)
- **Sales Volume**: Revenue indicators (scaled)
- **Employee Count**: Facility size indicators

### **Score Ranges**
- **90-100**: Exceptional opportunity - highest priority
- **80-89**: Strong opportunity - high priority
- **70-79**: Good opportunity - medium priority
- **60-69**: Fair opportunity - consider
- **<60**: Lower priority

Rankings are calculated within each NAICS industry segment to enable fair comparisons.
    """)

st.markdown("---")

# =============================================================================
# DATA LOADING
# =============================================================================

try:
    # Load scored companies
    scored_df = load_scored_companies()

    # Load raw company data to get building_count_estimate, growing_business_code, contacts_count
    companies_df = load_companies()

    # Merge raw fields from companies.csv into scored_df
    # Only merge the specific fields we need for display
    raw_fields = companies_df[['company_id', 'building_count_estimate', 'growing_business_code', 'contacts_count']].copy()

    # Remove duplicates to prevent merge from creating duplicate rows
    # (companies.csv has some duplicate company_ids which would multiply rows in the merge)
    raw_fields = raw_fields.drop_duplicates(subset=['company_id'], keep='first')

    scored_df = scored_df.merge(raw_fields, on='company_id', how='left')

    # Load penetration data for display
    try:
        penetration_df = load_penetration_by_company()
        penetration_map = dict(zip(
            penetration_df['company_id'].astype(str),
            penetration_df['penetration_rate']
        ))
    except Exception:
        # Penetration data is optional
        penetration_map = {}

except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# =============================================================================
# DATA QUALITY WARNINGS
# =============================================================================

# Check entity resolution orphan rate
from app.data_loader import get_data_dir
er_log_path = get_data_dir() / "processed" / "entity_resolution_log.csv"
orphan_rate, er_passed = check_entity_resolution_quality(er_log_path)

if not er_passed:
    st.warning(
        f"⚠️ **Data Quality Notice**: Entity resolution orphan rate is {orphan_rate:.1%} "
        f"(threshold: <10%). Some HubSpot records could not be matched to universe data. "
        f"Contact and penetration information may be incomplete."
    )

# =============================================================================
# VALIDATE RANKING INVARIANTS
# =============================================================================

try:
    # Validate segment rank contiguity
    validate_segment_rank_contiguity(scored_df)

    # Validate rank matches score order
    validate_rank_matches_score_order(scored_df)

except AssertionError as e:
    st.error(f"🚨 **Ranking Validation Error**: {e}")
    st.error("Please regenerate scored_companies.csv with correct rankings.")
    st.stop()

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================

# Check for NAICS filter from session state (navigation from NAICS Rankings page)
naics_from_rankings = None
if 'naics_filter_from_rankings' in st.session_state:
    naics_from_rankings = st.session_state['naics_filter_from_rankings']
    # Clear it after reading so it doesn't persist on subsequent page loads
    del st.session_state['naics_filter_from_rankings']

with st.sidebar:
    st.header("Filters")

    # Scoring Path filter
    scoring_paths = ['All'] + sorted(scored_df['scoring_path'].unique().tolist())
    selected_path = st.selectbox("Scoring Path", scoring_paths, index=0)

    # NAICS filter
    naics_options = ['All'] + sorted([str(x) for x in scored_df['naics_4digit'].unique() if pd.notna(x)])

    # If navigated from NAICS Rankings page, pre-select that NAICS code
    default_naics_index = 0
    if naics_from_rankings and naics_from_rankings in naics_options:
        default_naics_index = naics_options.index(naics_from_rankings)

    selected_naics = st.selectbox("NAICS Code", naics_options, index=default_naics_index, key="naics_selectbox")

    # Show info message after the selectbox if we auto-filtered
    if naics_from_rankings and naics_from_rankings in naics_options:
        st.info(f"🔍 Filtered to NAICS {naics_from_rankings} (from Industry Rankings)")

    # Customer status filter
    customer_options = ['All', 'Customers Only', 'Prospects Only']
    selected_customer = st.selectbox("Customer Status", customer_options, index=0)

    # State filter
    if 'state' in scored_df.columns:
        state_options = ['All'] + sorted([str(x) for x in scored_df['state'].unique() if pd.notna(x)])
        selected_state = st.selectbox("State", state_options, index=0)
    else:
        selected_state = 'All'

    # Score range filter
    st.markdown("---")
    st.markdown("**Score Range**")
    min_score, max_score = st.slider(
        "Final Score",
        min_value=0.0,
        max_value=100.0,
        value=(0.0, 100.0),
        step=1.0,
        key="score_filter"
    )

    # Reset button
    st.markdown("---")
    if st.button("🔄 Reset Filters", key="reset_filters"):
        # Clear only filter-related session state, not everything
        for key in list(st.session_state.keys()):
            if 'filter' in key:
                del st.session_state[key]
        st.rerun()

# =============================================================================
# APPLY FILTERS
# =============================================================================

filtered_df = scored_df.copy()

# Apply scoring path filter
if selected_path != 'All':
    filtered_df = filtered_df[filtered_df['scoring_path'] == selected_path]

# Apply NAICS filter
if selected_naics != 'All':
    filtered_df = filtered_df[filtered_df['naics_4digit'].astype(str) == selected_naics]

# Debug: Show filter status if navigated from NAICS Rankings
if naics_from_rankings:
    st.sidebar.markdown(f"**Debug:** Applied NAICS filter = `{selected_naics}`")
    st.sidebar.markdown(f"**Debug:** Companies after filter = `{len(filtered_df)}`")

# Apply customer status filter
if selected_customer == 'Customers Only':
    filtered_df = filtered_df[filtered_df['is_customer'] == True]
elif selected_customer == 'Prospects Only':
    filtered_df = filtered_df[filtered_df['is_customer'] == False]

# Apply state filter
if selected_state != 'All' and 'state' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['state'] == selected_state]

# Apply score range filter
filtered_df = filtered_df[
    (filtered_df['final_score'] >= min_score) &
    (filtered_df['final_score'] <= max_score)
]

# Sort by final score descending (highest scores first)
filtered_df = filtered_df.sort_values('final_score', ascending=False)

# =============================================================================
# DISPLAY COUNTS AND SUMMARY
# =============================================================================

total_count = len(scored_df)
filtered_count = len(filtered_df)

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Companies", f"{filtered_count:,} / {total_count:,}")

with col2:
    if filtered_count > 0:
        avg_score = filtered_df['final_score'].mean()
        st.metric("Avg Score", f"{avg_score:.1f}")
    else:
        st.metric("Avg Score", "—")

with col3:
    if filtered_count > 0:
        customer_count = filtered_df['is_customer'].sum()
        st.metric("Customers", f"{customer_count:,}")
    else:
        st.metric("Customers", "—")

with col4:
    if filtered_count > 0:
        prospect_count = (~filtered_df['is_customer']).sum()
        st.metric("Prospects", f"{prospect_count:,}")
    else:
        st.metric("Prospects", "—")

# Refresh button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🔄 Refresh", key="refresh_ranked"):
        from app.data_loader import clear_cache
        clear_cache()
        st.rerun()

# =============================================================================
# HANDLE EMPTY RESULTS
# =============================================================================

if len(filtered_df) == 0:
    st.warning(get_empty_state_message())
    st.stop()

# =============================================================================
# PREPARE DISPLAY DATAFRAME
# =============================================================================

display_df = filtered_df.copy()

# Add global rank based on current sort order (by final_score descending)
display_df = display_df.reset_index(drop=True)
display_df['Rank'] = range(1, len(display_df) + 1)

# Create display columns
display_df['Company'] = display_df['company_name']
display_df['Path'] = display_df['scoring_path']

# Score columns - keep as numeric for proper sorting
display_df['Final Score'] = display_df['final_score'].round(1)
display_df['NAICS Score'] = display_df['naics_attractiveness_score'].round(1)
display_df['Company Score'] = display_df['company_opportunity_score'].round(1)

# Company opportunity components
if 'location_employee_size' in display_df.columns:
    display_df['Employees'] = display_df['location_employee_size'].fillna(0).astype(int)
else:
    display_df['Employees'] = 0

if 'sales_volume' in display_df.columns:
    # Format sales volume in millions
    display_df['Revenue ($M)'] = display_df['sales_volume'].apply(
        lambda x: f"{x/1_000_000:.1f}" if pd.notna(x) and x > 0 else "—"
    )
else:
    display_df['Revenue ($M)'] = "—"

# Add location info
if 'city' in display_df.columns and 'state' in display_df.columns:
    display_df['Location'] = display_df.apply(
        lambda row: f"{row['city']}, {row['state']}" if pd.notna(row['city']) and pd.notna(row['state']) else "—",
        axis=1
    )
else:
    display_df['Location'] = "—"

# Add NAICS code
display_df['NAICS'] = display_df['naics_4digit'].apply(lambda x: str(int(x)) if pd.notna(x) else "—")

# Add customer indicator
display_df['Customer'] = display_df['is_customer'].apply(lambda x: "✅" if x else "")

# Add raw data columns instead of normalized scores
# Building count
if 'building_count_estimate' in display_df.columns:
    display_df['Buildings'] = display_df['building_count_estimate'].fillna(0).astype(int)
else:
    display_df['Buildings'] = 0

# ICP Fit Score (keep this as a score)
if 'icp_fit_score' in display_df.columns:
    display_df['ICP Fit'] = display_df['icp_fit_score'].apply(lambda x: f"{int(x)}" if pd.notna(x) else "—")
else:
    display_df['ICP Fit'] = "—"

# Growth indicator (use growing_business_code if available)
if 'growing_business_code' in display_df.columns:
    def format_growth(code):
        if pd.isna(code):
            return "—"
        code_str = str(code).strip().upper()
        mapping = {'G': '📈 High', '+': '↗️ Growing', 'C': '➡️ Stable', 'S': '➡️ Stable', '-': '📉 Declining'}
        return mapping.get(code_str, code_str)
    display_df['Growth'] = display_df['growing_business_code'].apply(format_growth)
else:
    display_df['Growth'] = "—"

# Contact count
if 'contacts_count' in display_df.columns:
    display_df['Contacts'] = pd.to_numeric(display_df['contacts_count'], errors='coerce').fillna(0).astype(int)
else:
    display_df['Contacts'] = 0

# NOTE: Growing Business Code and Digital Presence are no longer separate factors
# They are now captured within the ICP Fit Score assessment

# Note: Customer component columns (Expansion, Churn, Profit, Tickets) are excluded
# from the main table since only 18 out of 789 companies are actual customers.
# These components are still calculated and available in the CSV, and can be viewed
# on the Company Detail page.

# Select columns for display (prospect components only)
display_columns = [
    'company_id', 'Rank', 'Company', 'Path', 'NAICS', 'Final Score',
    'NAICS Score', 'Company Score', 'Employees', 'Revenue ($M)', 'Location', 'Customer',
    # Prospect components (shown for all companies) - Raw data instead of normalized scores
    'ICP Fit', 'Buildings', 'Growth', 'Contacts'
]

# Only include columns that exist in the dataframe
display_columns = [col for col in display_columns if col in display_df.columns]

result_df = display_df[display_columns].copy()

# =============================================================================
# DISPLAY TABLE WITH ROW SELECTION
# =============================================================================

st.markdown("---")
st.markdown("### 📋 Company Rankings")
st.markdown("Click on any row to select a company, then navigate to the Company Detail page to view full information.")

# Display companies table with row selection enabled
event = st.dataframe(
    result_df,
    use_container_width=True,
    height=600,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="ranked_companies_table",
    column_config={
        "company_id": None,  # Hide company_id column
        "Rank": st.column_config.NumberColumn(
            "Rank",
            help="Overall ranking by Final Score (1 = highest)",
            format="%d",
            width="small"
        ),
        "Company": st.column_config.TextColumn(
            "Company",
            help="Company name (click row to select)",
            width="medium"
        ),
        "Path": st.column_config.TextColumn(
            "Path",
            help="Scoring path: Customer Expansion or Prospect",
            width="small"
        ),
        "NAICS": st.column_config.TextColumn(
            "NAICS",
            help="4-digit NAICS industry code",
            width="small"
        ),
        "Final Score": st.column_config.NumberColumn(
            "Final Score",
            help="Overall opportunity score (0-100)",
            format="%.1f",
            width="small"
        ),
        "NAICS Score": st.column_config.NumberColumn(
            "NAICS Score",
            help="Industry attractiveness score (ICP fit, market size, profitability, health)",
            format="%.1f",
            width="small"
        ),
        "Company Score": st.column_config.NumberColumn(
            "Company Score",
            help="Company opportunity score (employees, revenue)",
            format="%.1f",
            width="small"
        ),
        "Employees": st.column_config.NumberColumn(
            "Employees",
            help="Employee count",
            format="%d",
            width="small"
        ),
        "Revenue ($M)": st.column_config.TextColumn(
            "Revenue ($M)",
            help="Annual revenue in millions",
            width="small"
        ),
        "Location": st.column_config.TextColumn(
            "Location",
            help="City, State",
            width="medium"
        ),
        "Customer": st.column_config.TextColumn(
            "Customer",
            help="✅ = Existing customer",
            width="small"
        ),
        # Prospect component data (raw data instead of normalized scores)
        "ICP Fit": st.column_config.TextColumn(
            "ICP Fit",
            help="ICP Fit Score (0-100) - Claude AI assessment of company-ICP alignment",
            width="small"
        ),
        "Buildings": st.column_config.NumberColumn(
            "Buildings",
            help="Number of building locations",
            format="%d",
            width="small"
        ),
        "Growth": st.column_config.TextColumn(
            "Growth",
            help="Growth indicator: 📈 High Growth, ↗️ Growing, ➡️ Stable, 📉 Declining",
            width="small"
        ),
        "Contacts": st.column_config.NumberColumn(
            "Contacts",
            help="Number of contacts available",
            format="%d",
            width="small"
        ),
    }
)

# Handle row selection
if event.selection.rows:
    selected_row_index = event.selection.rows[0]
    selected_company_id = result_df.iloc[selected_row_index]['company_id']
    selected_company_name = result_df.iloc[selected_row_index]['Company']

    # Set selected company in session state
    set_selected_company(selected_company_id)

    # Show confirmation message
    st.success(f"✅ Selected: **{selected_company_name}**")
    st.info("👉 Navigate to the **Company Detail** page using the sidebar to view full information.")

# =============================================================================
# FOOTER INFO
# =============================================================================

with st.expander("ℹ️ About This Page"):
    st.markdown("""
    **Ranked Companies** displays all scored prospects using our dual-path scoring methodology.

    **Features:**
    - Companies ranked by **Final Score** within each NAICS segment
    - **Two scoring paths**:
      - **Customer Expansion**: Existing customers evaluated for additional locations
      - **Prospect**: New prospects evaluated on industry + company attractiveness
    - **Filters**: Scoring path, NAICS code, customer status, state, score range
    - **Score Components**:
      - **NAICS Attr.**: Industry attractiveness (ICP fit, market size, profitability, health)
      - **Co. Opp.**: Company opportunity (building count, sales volume, employee size)

    **Columns:**
    - **Rank**: Overall ranking by final score (1 = highest score)
    - **Final Score**: Overall opportunity score (0-100)
    - **NAICS Score**: Industry attractiveness score
    - **Company Score**: Company opportunity score (aggregate of components below)
    - **Path**: Scoring methodology used (Customer Expansion or Prospect)
    - **Customer**: ✅ indicates existing OpenWorks customer

    **Additional Company Data** (displayed for all companies):
    - **ICP Fit**: Claude AI assessment of company-ICP alignment (0-100 score)
    - **Buildings**: Number of building locations
    - **Growth**: Growth indicator (📈 High Growth, ↗️ Growing, ➡️ Stable, 📉 Declining)
    - **Contacts**: Number of contacts available

    Note: These columns show raw data to provide context about company size and growth.

    **Note on Customer Components**: The 18 companies with Path = "Customer Expansion" use
    different scoring components (Expansion, Churn, Profitability, Tickets, Revenue). These
    are not displayed in the main table but can be viewed on the Company Detail page.

    **Note**: Some existing customers (✅) may appear in the "Prospect" path. This means they're being evaluated for new business opportunities using the prospect methodology, separate from any existing customer expansion tracking.

    **Data Quality:**
    - Rankings validated for contiguity and score order consistency
    - Entity resolution quality checked against <10% orphan rate threshold

    Select a company to view full intelligence details on the Company Detail page.
    """)
