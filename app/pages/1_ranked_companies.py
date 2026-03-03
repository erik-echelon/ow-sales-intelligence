"""
Page 1: Ranked Companies

Displays all scored companies using the dual-path scoring methodology.
"""

import logging
import pandas as pd
import streamlit as st

from app.data_loader import (
    get_data_dir,
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
from app.naics_rankings_logic import get_naics_description
from app.quality_gates import check_entity_resolution_quality

logger = logging.getLogger(__name__)

# Page header
st.title("📊 Ranked Companies")

# =============================================================================
# SCORING METHODOLOGY
# =============================================================================

with st.expander("🎯 Scoring Methodology (Click to expand)", expanded=False):
    st.markdown("""
Our dual-path scoring system evaluates companies using different methodologies based on their relationship status:

### **Two Scoring Paths**

---

#### **Path 1: Prospect Acquisition** (New Customers - Most Companies)
For prospective new customers, we combine industry attractiveness with company-specific opportunity:

**Final Score = (NAICS Attractiveness × 40%) + (Company Opportunity × 60%)**

##### **NAICS Attractiveness Score** (0-100, weighted 40%):
Industry-level score based on how attractive each NAICS industry is for OpenWorks. Calculated once per NAICS code.

| Component | Weight | Description | Example |
|-----------|--------|-------------|---------|
| **ICP Fit** | 25% | Claude AI assessment of industry-ICP alignment | Schools (92) = Perfect fit, Hospitals (68) = Moderate fit |
| **Market Size** | 15% | Nationwide market size (log-scaled) | 230K locations = 100, 3.6K locations = 71 |
| **OW Revenue Concentration** | 15% | % of OpenWorks revenue from this industry | 13% revenue = 100, <1% revenue = 37 |
| **OW Building Count** | 20% | Buildings OpenWorks serves in this industry | 164 buildings = 100, 11 buildings = 63 |
| **Revenue per Building** | 5% | Avg monthly revenue/building vs median | $5,550/building = 92, $1,187/building = 29 |
| **Churn Health** | 15% | Customer retention in industry | Low churn = 90+, high churn = <60 |
| **Ticket Health** | 5% | Support ticket quality/volume | Few tickets = 55+, many tickets = 35 |

**Formula**: NAICS Score = (ICP Fit × 25%) + (Market Size × 15%) + (OW Rev Conc × 15%) + (OW Buildings × 20%) + (Rev/Building × 5%) + (Churn × 15%) + (Tickets × 5%)

##### **Company Opportunity Score** (0-100, weighted 60%):
Company-specific score evaluating the opportunity at this particular company.

| Component | Weight | Description | Example |
|-----------|--------|-------------|---------|
| **ICP Fit** | 50% | Claude AI assessment of company-ICP alignment | 63 = Decent fit, 30 = Poor fit |
| **Buildings** | 20% | Number of locations (log-scaled) | 11 locations = 50, 100+ locations = 100 |
| **Revenue** | 15% | Annual revenue (log-scaled) | $250M = 100, $24M = 83 |
| **Employees** | 10% | Employee count as growth proxy (log-scaled) | 3,200 employees = 100, 75 employees = 100 |
| **Contacts** | 5% | Contact availability | Has contacts = 75, No contacts = 25 |

**Formula**: Company Score = (ICP Fit × 50%) + (Buildings × 20%) + (Revenue × 15%) + (Employees × 10%) + (Contacts × 5%)

**Note**: Missing data receives neutral score of 50, so low scores reflect actual small companies, not missing data.

---

#### **Path 2: Customer Expansion** (Existing Customers)
For current OpenWorks customers, we focus on expansion potential within the existing account:

**Company Opportunity Score** components (Customer path doesn't use NAICS scores):

| Component | Weight | Description |
|-----------|--------|-------------|
| **Expansion Opportunity** | 40% | Unpenetrated buildings × revenue potential |
| **Churn Risk** | 30% | Customer retention likelihood (inverse of risk) |
| **Profitability** | 20% | Current account profitability |
| **Support Tickets** | 10% | Support quality (fewer = better) |

---

### **Final Score Interpretation**
- **90-100**: 🟢 Elite tier - Exceptional opportunity, highest priority
- **80-89**: 🟢 Strong opportunity - High priority for expansion
- **70-79**: 🟡 Good opportunity - Medium priority
- **60-69**: 🟡 Fair opportunity - Consider with caution
- **<60**: 🔴 Lower priority - Proceed carefully

### **Key Insights**
- **ICP Fit is dominant**: At company level (50% of Company Score) and industry level (25% of NAICS Score)
- **Multi-location companies score higher**: Buildings are 20% of Company Score
- **Proven success matters**: Industries where OpenWorks already succeeds (high revenue concentration, many buildings) score higher
- **Rankings are per-segment**: Companies ranked within their NAICS industry for fair comparison
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

    # Load HubSpot data to determine presence
    try:
        # Load HubSpot companies
        hubspot_path = get_data_dir() / "raw" / "hubspot_companies.csv"
        hubspot_df = pd.read_csv(hubspot_path)

        # Extract domains from HubSpot (clean them)
        hubspot_domains = set()
        for domain in hubspot_df['domain'].dropna():
            # Clean domain: remove http://, https://, www., trailing slashes
            domain_clean = str(domain).lower().strip()
            domain_clean = domain_clean.replace('http://', '').replace('https://', '')
            domain_clean = domain_clean.replace('www.', '').rstrip('/')
            if domain_clean:
                hubspot_domains.add(domain_clean)

        # Extract domains from companies.csv (match on website field)
        # Clean company websites similarly
        def clean_domain(url):
            if pd.isna(url):
                return None
            url_clean = str(url).lower().strip()
            url_clean = url_clean.replace('http://', '').replace('https://', '')
            url_clean = url_clean.replace('www.', '').rstrip('/')
            # Extract just the domain part (remove path)
            if '/' in url_clean:
                url_clean = url_clean.split('/')[0]
            return url_clean if url_clean else None

        # Check if website field exists
        if 'website' not in companies_df.columns:
            scored_df['in_hubspot'] = False
        else:
            companies_df['domain_clean'] = companies_df['website'].apply(clean_domain)

            # Create mapping of company_id to whether it's in HubSpot
            company_domain_map = dict(zip(
                companies_df['company_id'].astype(str),
                companies_df['domain_clean'].apply(lambda d: d in hubspot_domains if d else False)
            ))

            scored_df['in_hubspot'] = scored_df['company_id'].astype(str).map(company_domain_map).fillna(False)
    except Exception as e:
        # If we can't load HubSpot data, assume no matches
        st.error(f"Error loading HubSpot data: {e}")
        scored_df['in_hubspot'] = False

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

    # Customer Status filter (renamed from Scoring Path)
    scoring_paths = ['All'] + sorted(scored_df['scoring_path'].unique().tolist())
    selected_path = st.selectbox("Customer Status", scoring_paths, index=0)

    # NAICS filter
    naics_codes = sorted([str(x) for x in scored_df['naics_4digit'].unique() if pd.notna(x)])
    naics_options = ['All'] + naics_codes

    # Create mapping of NAICS codes to descriptions for display
    naics_display_map = {code: f"{code} - {get_naics_description(code)}" for code in naics_codes}
    naics_display_map['All'] = 'All'

    # If navigated from NAICS Rankings page, pre-select that NAICS code
    default_naics_index = 0
    if naics_from_rankings and naics_from_rankings in naics_options:
        default_naics_index = naics_options.index(naics_from_rankings)

    selected_naics = st.selectbox(
        "NAICS Code",
        naics_options,
        index=default_naics_index,
        format_func=lambda x: naics_display_map[x],
        key="naics_selectbox"
    )

    # Show info message after the selectbox if we auto-filtered
    if naics_from_rankings and naics_from_rankings in naics_options:
        st.info(f"🔍 Filtered to NAICS {naics_from_rankings} (from Industry Rankings)")

    # HubSpot Status filter (replaces Customer Status)
    hubspot_options = ['All', 'In HubSpot', 'Not in HubSpot']
    selected_hubspot = st.selectbox("HubSpot Status", hubspot_options, index=0)

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

# Apply customer status filter (scoring path)
if selected_path != 'All':
    filtered_df = filtered_df[filtered_df['scoring_path'] == selected_path]

# Apply NAICS filter
if selected_naics != 'All':
    filtered_df = filtered_df[filtered_df['naics_4digit'].astype(str) == selected_naics]

# Debug: Show filter status if navigated from NAICS Rankings
if naics_from_rankings:
    st.sidebar.markdown(f"**Debug:** Applied NAICS filter = `{selected_naics}`")
    st.sidebar.markdown(f"**Debug:** Companies after filter = `{len(filtered_df)}`")

# Apply HubSpot status filter
if selected_hubspot == 'In HubSpot':
    filtered_df = filtered_df[filtered_df['in_hubspot'] == True]
elif selected_hubspot == 'Not in HubSpot':
    filtered_df = filtered_df[filtered_df['in_hubspot'] == False]

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

# Add HubSpot indicator
display_df['In HubSpot'] = display_df['in_hubspot'].apply(lambda x: "✅" if x else "")

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
    'NAICS Score', 'Company Score', 'Employees', 'Revenue ($M)', 'Location', 'Customer', 'In HubSpot',
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
            help="🏆 Position in filtered results, sorted by Final Score descending (1 = highest). Changes based on active filters.",
            format="%d",
            width="small"
        ),
        "Company": st.column_config.TextColumn(
            "Company",
            help="🏢 Company name from DataAxle database. Click any row to select this company and view full details on the Company Detail page.",
            width="medium"
        ),
        "Path": st.column_config.TextColumn(
            "Path",
            help="🛤️ Customer Status / Scoring methodology: 'Prospect' (new customer - scored on industry + company attractiveness) or 'Customer Expansion' (existing customer - scored on expansion opportunity). ~97% are Prospects.",
            width="small"
        ),
        "NAICS": st.column_config.TextColumn(
            "NAICS",
            help="🏭 4-digit NAICS industry code. All companies in same NAICS have same NAICS Score. Visit NAICS Rankings page to explore industries.",
            width="small"
        ),
        "Final Score": st.column_config.NumberColumn(
            "Final Score",
            help="⭐ Overall opportunity score (0-100). For Prospects: (NAICS Score × 40%) + (Company Score × 60%). Higher = better opportunity. 90-100=Elite, 80-89=Strong, 70-79=Good, 60-69=Fair, <60=Lower priority.",
            format="%.1f",
            width="small"
        ),
        "NAICS Score": st.column_config.NumberColumn(
            "NAICS Score",
            help="🎯 Industry attractiveness (0-100). Based on: ICP Fit (25%), Market Size (15%), OW Revenue Concentration (15%), OW Building Count (20%), Revenue/Building (5%), Churn Health (15%), Ticket Health (5%). Same for all companies in this NAICS.",
            format="%.1f",
            width="small"
        ),
        "Company Score": st.column_config.NumberColumn(
            "Company Score",
            help="🏢 Company-specific opportunity (0-100). Based on: ICP Fit (50%), Buildings (20%), Revenue (15%), Employees (10%), Contacts (5%). Varies by company size and characteristics.",
            format="%.1f",
            width="small"
        ),
        "Employees": st.column_config.NumberColumn(
            "Employees",
            help="👥 Employee count at this location from DataAxle. Larger = bigger facilities, higher Company Score (10% weight). Example: 3,200 employees = likely large facility complex.",
            format="%d",
            width="small"
        ),
        "Revenue ($M)": st.column_config.TextColumn(
            "Revenue ($M)",
            help="💰 Annual revenue in millions from DataAxle. Higher revenue = higher Company Score (15% weight). Blank if not available. Example: 250.0 = $250M annual revenue.",
            width="small"
        ),
        "Location": st.column_config.TextColumn(
            "Location",
            help="📍 Primary location (City, State) from DataAxle. Use State filter in sidebar to focus on specific regions.",
            width="medium"
        ),
        "Customer": st.column_config.TextColumn(
            "Customer",
            help="✅ Existing OpenWorks customer indicator. ✅ = Currently active customer (matched via HubSpot entity resolution). Blank = Prospect. Some customers scored as 'Prospect' path for new business opportunities.",
            width="small"
        ),
        "In HubSpot": st.column_config.TextColumn(
            "In HubSpot",
            help="📋 HubSpot presence indicator. ✅ = Company has a record in HubSpot (known to OpenWorks, may have buildings/contacts). Blank = Not in HubSpot yet (completely unknown). Companies can be in HubSpot but still be prospects (not yet customers).",
            width="small"
        ),
        # Prospect component data (raw data instead of normalized scores)
        "ICP Fit": st.column_config.TextColumn(
            "ICP Fit",
            help="🤖 Company ICP Fit Score (0-100) from Claude AI. Evaluates multi-location potential, facility type, operational fit, and similarity to successful customers. Worth 50% of Company Score! 70+=Strong fit, 40-69=Moderate, <40=Poor fit.",
            width="small"
        ),
        "Buildings": st.column_config.NumberColumn(
            "Buildings",
            help="🏗️ Number of building locations from DataAxle. Multi-location companies score much higher (20% of Company Score). 10+=Excellent, 5-9=Good, 3-4=Fair, 1-2=Limited opportunity.",
            format="%d",
            width="small"
        ),
        "Growth": st.column_config.TextColumn(
            "Growth",
            help="📈 Growth indicator from DataAxle: 📈 High Growth (rapid expansion), ↗️ Growing (steady growth), ➡️ Stable (flat growth), 📉 Declining (contracting). Growing companies = better long-term prospects.",
            width="small"
        ),
        "Contacts": st.column_config.NumberColumn(
            "Contacts",
            help="📞 Number of contacts available in our enriched database (worth 5% of Company Score). 75=We have contacts, 0=No contacts yet. Having contacts makes outreach easier.",
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

with st.expander("ℹ️ About This Page - Complete Column Reference", expanded=False):
    st.markdown("""
    **Ranked Companies** displays all scored prospects using our dual-path scoring methodology.

    ---

    ### **Table Columns Explained**

    Every column in the rankings table is explained below with examples:

    | Column | Description | Example Values | Notes |
    |--------|-------------|----------------|-------|
    | **Rank** | Position in filtered results, sorted by Final Score descending | 1, 2, 3... | Changes based on filters applied |
    | **Company** | Company name from DataAxle | "Monterey Mushrooms, LLC" | Click row to select for detail view |
    | **Path** | Customer status / Scoring methodology | "Prospect" or "Customer Expansion" | Most companies are Prospects (~97%) |
    | **NAICS** | 4-digit NAICS industry code | "1114", "6214" | Use NAICS Rankings page to understand industries |
    | **Final Score** | Overall opportunity score (0-100) | 93.8, 52.4, 45.3 | **Main sorting metric** - higher = better opportunity |
    | **NAICS Score** | Industry attractiveness (0-100) | 93.8 (Schools), 25.8 (Agriculture) | Same for all companies in same 4-digit NAICS |
    | **Company Score** | Company-specific opportunity (0-100) | 70.2, 54.3, 47.1 | Varies by company size, buildings, revenue, ICP fit |
    | **Employees** | Employee count at this location | 3200, 526, 75 | From DataAxle - indicates facility size |
    | **Revenue ($M)** | Annual revenue in millions | 250.0, 24.3, 29.1 | From DataAxle - blank if not available |
    | **Location** | City, State | "Watsonville, CA" | Primary location from DataAxle |
    | **Customer** | Existing OpenWorks customer indicator | ✅ or blank | ✅ = Currently active customer |
    | **In HubSpot** | HubSpot presence indicator | ✅ or blank | ✅ = Known to OpenWorks (in HubSpot), blank = Unknown prospect |
    | **ICP Fit** | Company ICP Fit Score (0-100) | 63, 42, 30 | Claude AI assessment of company-ICP alignment |
    | **Buildings** | Number of building locations | 11, 5, 3 | Multi-location companies score higher |
    | **Growth** | Growth indicator from DataAxle | 📈 High, ↗️ Growing, ➡️ Stable, 📉 Declining | Based on DataAxle's growing_business_code |
    | **Contacts** | Number of contacts available | 75, 0 | From contact enrichment - 75 means we have contacts |

    ---

    ### **Scoring Paths**

    #### **Prospect Path** (Most Companies):
    - **Final Score** = (NAICS Score × 40%) + (Company Score × 60%)
    - **NAICS Score**: Industry attractiveness (ICP fit, market size, OpenWorks performance, customer health)
    - **Company Score**: Company opportunity (ICP fit 50%, buildings 20%, revenue 15%, employees 10%, contacts 5%)

    #### **Customer Expansion Path** (~18 companies):
    - **Final Score** = Company Score only (no NAICS score used)
    - **Company Score**: Expansion opportunity, churn risk, profitability, support tickets
    - These customers are evaluated for additional locations within existing accounts

    ---

    ### **How to Use This Page**

    1. **Filter** using sidebar controls:
       - **Customer Status**: Focus on Prospects or Customer Expansion opportunities
       - **NAICS Code**: Filter to specific industries (use dropdown with descriptions)
       - **HubSpot Status**: Filter by whether company is in HubSpot (known to OpenWorks) or not
       - **State**: Geographic filtering
       - **Score Range**: Focus on high-scoring opportunities (e.g., 80-100)

    2. **Sort** by clicking column headers or use default sort (Final Score descending)

    3. **Select** a company by clicking its row, then navigate to **Company Detail** page for:
       - Full ICP Fit reasoning and recommendation
       - Complete scoring breakdown with all components
       - Company research and intelligence (if available)
       - Contact information

    ---

    ### **Understanding Scores**

    **Final Score Ranges:**
    - **90-100**: 🟢 Elite tier - Exceptional opportunity (top ~5% of prospects)
    - **80-89**: 🟢 Strong opportunity - High priority (top ~10% of prospects)
    - **70-79**: 🟡 Good opportunity - Medium priority (top ~20% of prospects)
    - **60-69**: 🟡 Fair opportunity - Consider with caution
    - **<60**: 🔴 Lower priority - Proceed carefully

    **What Makes a High Score?**
    - Strong industry (schools, hospitals, warehousing = high NAICS scores)
    - Multi-location company (11+ buildings = big boost)
    - Large revenue and employee count
    - High ICP Fit (AI says company matches OpenWorks' ideal customer)
    - Available contacts

    **What Makes a Low Score?**
    - Weak industry fit (agriculture, single-location businesses = low NAICS scores)
    - Few buildings (1-2 locations)
    - Small revenue or employee count
    - Low ICP Fit (AI identifies misalignment)
    - No contact data

    ---

    ### **Data Sources**

    - **Company Data**: DataAxle (buildings, revenue, employees, location, NAICS, growth)
    - **Customer Status**: HubSpot (entity resolution matches DataAxle ↔ HubSpot)
    - **ICP Fit Scores**: Claude AI (analyzes company characteristics against ideal customer profile)
    - **NAICS Scores**: Calculated from OpenWorks operational data (revenue, buildings, churn, tickets) + market size + AI assessment
    - **Contacts**: Enriched contact database

    ---

    ### **Data Quality Notes**

    - **Rankings**: Validated for contiguity and score order consistency per NAICS segment
    - **Entity Resolution**: Quality checked against <10% orphan rate threshold
    - **Missing Data**: Receives neutral score (50) so low scores reflect actual small companies, not missing data
    - **Customer Flag**: Some customers (✅) appear in "Prospect" path because they're being evaluated for new business opportunities separate from existing accounts

    ---

    ### **Pro Tips**

    💡 **Start with high scores**: Filter to Final Score 80-100 to see elite opportunities

    💡 **Use NAICS filter**: Click "🔍 View Companies" on NAICS Rankings page to auto-filter to an industry

    💡 **Check ICP Fit**: Companies with ICP Fit >70 have strong alignment even if Final Score is moderate

    💡 **Multi-location matters**: Buildings column is key - 10+ locations = significant opportunity

    💡 **Combine filters**: Try "Prospect" path + "80-100" score + your target state for laser-focused prospecting

    ---

    **Questions?** Expand the "🎯 Scoring Methodology" section at the top for detailed scoring formulas and component breakdowns.
    """)
