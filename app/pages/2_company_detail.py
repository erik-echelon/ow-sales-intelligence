"""
Page 2: Company Detail

Deep dive view for individual company with tabs for all data aspects.

Epic 5 (OWRKS-5.07)
Spec: Screen 2 (Company Detail)
"""

import json
import logging
import sys
from pathlib import Path

# Add parent directory to path to allow 'app' module imports in Streamlit Cloud
_page_dir = Path(__file__).resolve().parent
_app_dir = _page_dir.parent
_project_root = _app_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import streamlit as st

from app.company_detail_logic import (
    calculate_penetration_rate,
    format_buildings_display,
    format_company_info,
    format_contacts_display,
    format_score_components,
    get_company_buildings,
    get_company_by_id,
    get_company_contacts,
    get_company_not_found_message,
    get_churn_prediction,
    get_no_company_selected_message,
    get_scored_company_by_id,
    get_selected_company_id,
    has_churn_data,
    metric_with_tooltip,
)
from app.components.research_viewer import render_research_document
from app.components.score_display import (
    format_score,
    render_score_badge,
    render_score_comparison,
)
from app.data_loader import (
    load_buildings,
    load_churn_predictions,
    load_companies,
    load_company_research_data,
    load_contact_summary,
    load_research_document,
    load_scored_companies,
)
from app.quality_gates import validate_scoring_weights
from pathlib import Path

logger = logging.getLogger(__name__)

# Page header
st.title("🏢 Company Detail")

# =============================================================================
# GET SELECTED COMPANY/COMPANIES
# =============================================================================

# Check if multiple companies are selected
selected_company_ids = st.session_state.get('selected_company_ids', [])
selected_company_names = st.session_state.get('selected_company_names', [])

# Fall back to single company selection for backward compatibility
if not selected_company_ids:
    company_id = get_selected_company_id()
    if not company_id:
        st.warning(get_no_company_selected_message())
        st.stop()
    selected_company_ids = [company_id]
    selected_company_names = [None]  # Will be filled in later

# Multi-company view mode
multi_company_mode = len(selected_company_ids) > 1

if multi_company_mode:
    st.info(f"**Viewing {len(selected_company_ids)} selected companies** - Use the tabs below to switch between companies")

# =============================================================================
# LOAD DATA (ONCE FOR ALL COMPANIES)
# =============================================================================

try:
    companies_df = load_companies()
    scored_df = load_scored_companies()
    buildings_df = load_buildings()
    contacts_df = load_contact_summary()
    churn_df = load_churn_predictions()  # May be None
    research_data_df = load_company_research_data()  # May be None - Epic 4c research with web data
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# =============================================================================
# HANDLE MULTI-COMPANY MODE
# =============================================================================

if multi_company_mode:
    st.markdown("---")
    st.markdown("### 📋 Select a Company to View")
    st.markdown("Click a company name below to view full details")

    # Create radio buttons for company selection
    selected_index = st.radio(
        "Select company:",
        range(len(selected_company_ids)),
        format_func=lambda i: f"{selected_company_names[i]} (ID: {selected_company_ids[i]})",
        key="multi_company_selector"
    )

    # Use the selected company
    company_id = selected_company_ids[selected_index]
else:
    # Single company mode
    company_id = selected_company_ids[0]

# =============================================================================
# GET COMPANY DATA
# =============================================================================

company = get_company_by_id(company_id, companies_df)
scored = get_scored_company_by_id(company_id, scored_df)

if company is None or scored is None:
    st.error(get_company_not_found_message(company_id))
    st.stop()

# Note: 'source' column no longer exists in new scoring format
# All data comes from DataAxle in the new dual-path scoring system

# Get related data
buildings = get_company_buildings(company_id, buildings_df)
contacts = get_company_contacts(company_id, contacts_df)

# =============================================================================
# BREADCRUMB NAVIGATION
# =============================================================================

# Display breadcrumb to show navigation context
st.markdown("Ranked Companies > **{company_name}**".format(company_name=company['name']))
st.markdown("---")

# =============================================================================
# COMPANY HEADER
# =============================================================================

st.markdown(f"## {company['name']}")
st.markdown("---")

# =============================================================================
# TABS
# =============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Company Info",
    "📊 Scoring",
    "🎯 ICP Research",
    "⚠️ Churn"
])

# =============================================================================
# TAB 1: COMPANY INFO (Consolidated: Info + HQ Info + Contacts)
# =============================================================================

with tab1:
    st.subheader("Company Information")

    info = format_company_info(company)

    # Get HQ info
    from app.company_detail_logic import format_hq_info
    company_with_sales = company.copy()
    if 'sales_volume' not in company_with_sales or pd.isna(company_with_sales.get('sales_volume')):
        company_with_sales['sales_volume'] = scored.get('sales_volume')
    hq_info = format_hq_info(company_with_sales)

    # Basic Company Details
    col1, col2, col3 = st.columns(3)

    with col1:
        metric_with_tooltip(
            "Company ID",
            info['Company ID'],
            "🆔 Unique identifier for this company in the DataAxle database. Use this ID to reference the company across all system reports and data exports."
        )
        metric_with_tooltip(
            "Name",
            info['Name'],
            "🏢 Official company name from DataAxle. This is the legal or primary business name used for identification."
        )

    with col2:
        metric_with_tooltip(
            "NAICS Code",
            info['NAICS'],
            "🏭 North American Industry Classification System code. This 8-digit code identifies the company's primary business activity. First 4 digits = industry group used for scoring. Visit NAICS Rankings page to explore industries."
        )
        metric_with_tooltip(
            "City",
            hq_info['city'],
            "📍 City location of company headquarters from DataAxle. This is the primary business address on file."
        )

    with col3:
        metric_with_tooltip(
            "State",
            hq_info['state'],
            "🗺️ State location of company headquarters. Use this for geographic filtering and territory assignment."
        )
        metric_with_tooltip(
            "Coordinates",
            hq_info['coordinates'],
            "🌐 Geographic coordinates (latitude, longitude) of headquarters location. Used for mapping, proximity analysis, and territory planning."
        )

    st.markdown("---")

    # Company Size Metrics
    st.subheader("Company Size")

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_with_tooltip(
            "Building Count Estimate",
            hq_info['building_count_estimate'],
            "🏗️ Estimated number of locations/buildings for this company from DataAxle. Multi-location companies (10+) score much higher in Company Score (20% weight). This is an estimate and may differ from actual building count discovered through research."
        )

    with col2:
        metric_with_tooltip(
            "Employee Count",
            hq_info['employee_size'],
            "👥 Total employee count from DataAxle. Larger companies = bigger facilities and higher Company Score (10% weight). Used as a proxy for company size and facility complexity. Example: 3,200 employees typically means large multi-building operations."
        )

    with col3:
        metric_with_tooltip(
            "Sales Volume",
            hq_info['sales_volume'],
            "💰 Annual revenue/sales volume from DataAxle. Higher revenue = higher Company Score (15% weight). Shows company's financial scale and ability to pay for facility services. Format: millions of dollars (e.g., $250M)."
        )

    # Calculate and display penetration
    st.markdown("---")
    st.subheader("Penetration Metrics")

    penetration_rate = calculate_penetration_rate(buildings)

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_with_tooltip(
            "Total Buildings",
            str(len(buildings)),
            "🏢 Total number of buildings/locations discovered for this company through research and entity resolution. This is the actual count from our building database, which may be more accurate than the DataAxle estimate above."
        )

    with col2:
        served_count = buildings['is_served'].sum()
        metric_with_tooltip(
            "Served Buildings",
            str(int(served_count)),
            "✅ Number of buildings currently served by OpenWorks (matched to HubSpot building records). These are active service locations where OpenWorks has existing contracts and relationships."
        )

    with col3:
        metric_with_tooltip(
            "Penetration Rate",
            f"{penetration_rate:.1f}%",
            "📊 Percentage of total buildings currently served by OpenWorks. Formula: (Served Buildings / Total Buildings) × 100. Higher penetration = less expansion opportunity. Lower penetration = more whitespace to capture within existing customer."
        )

    # Contacts section (from DataAxle data)
    st.markdown("---")
    st.subheader("Contacts")

    # Extract contact data from company record
    contacts_count_raw = company.get('contacts_count', 0)
    primary_contact_str = company.get('primary_contact')

    # Convert contacts_count to int if it's a string
    try:
        contacts_count = int(float(contacts_count_raw)) if pd.notna(contacts_count_raw) else 0
    except (ValueError, TypeError):
        contacts_count = 0

    if contacts_count > 0:
        col1, col2 = st.columns(2)

        with col1:
            metric_with_tooltip(
                "Total Contacts",
                str(int(contacts_count)),
                "📞 Number of contacts available in enriched database from DataAxle. Having contacts makes outreach easier and is worth 5% of Company Score. 75+ contacts = good coverage, 0 contacts = need to research decision makers."
            )

        # Parse and display primary contact if available
        if pd.notna(primary_contact_str):
            try:
                primary_contact = json.loads(primary_contact_str)

                with col2:
                    # Build contact name
                    first_name = primary_contact.get('first_name', '')
                    last_name = primary_contact.get('last_name', '')
                    full_name = f"{first_name} {last_name}".strip()

                    if full_name:
                        metric_with_tooltip(
                            "Primary Contact",
                            full_name,
                            "👤 Primary decision maker or key contact from DataAxle contact database. This is typically a facilities manager, operations director, or C-level executive. Use as starting point for outreach."
                        )

                # Display additional contact details
                st.markdown("**Primary Contact Details:**")

                contact_details = []

                # Job titles
                job_titles = primary_contact.get('job_titles', [])
                if job_titles:
                    contact_details.append(f"**Title:** {', '.join(job_titles)}")

                # Management level
                management_level = primary_contact.get('management_level', '')
                if management_level:
                    level_display = management_level.replace('_', ' ').title()
                    contact_details.append(f"**Level:** {level_display}")

                # Gender
                gender = primary_contact.get('gender', '')
                if gender:
                    contact_details.append(f"**Gender:** {gender}")

                if contact_details:
                    for detail in contact_details:
                        st.markdown(f"- {detail}")
                else:
                    st.info("Primary contact name available, but no additional details.")

            except (json.JSONDecodeError, TypeError) as e:
                st.info("Primary contact data available but could not be parsed.")
        else:
            st.info(f"{int(contacts_count)} contacts available from DataAxle, but primary contact details not provided.")
    else:
        st.info("No contact information available for this company.")

    # Note about HQ-only data
    st.markdown("---")
    st.info("""
    **Note:** Building count and employee count represent the company's overall size estimate from DataAxle data.
    Penetration metrics show the percentage of this company's buildings that are currently served by OpenWorks.
    """)

# =============================================================================
# TAB 2: SCORING
# =============================================================================

with tab2:
    st.subheader("Scoring Breakdown")

    from app.company_detail_logic import format_scoring_breakdown

    # Get scoring breakdown
    breakdown = format_scoring_breakdown(scored)

    # Display scoring path
    st.markdown(f"**Scoring Path:** {breakdown['scoring_path']}")
    st.markdown("---")

    # Display three key scores in columns with tooltips
    col1, col2, col3 = st.columns(3)

    with col1:
        metric_with_tooltip(
            "NAICS Attractiveness Score",
            f"{breakdown['naics_score']:.1f}",
            "🎯 Industry-level attractiveness (0-100). Weighted 40% in Final Score for Prospects. Based on: ICP Fit (25%), Market Size (15%), OW Revenue Concentration (15%), OW Building Count (20%), Revenue/Building (5%), Churn Health (15%), Ticket Health (5%). Same for all companies in this NAICS."
        )

    with col2:
        metric_with_tooltip(
            "Company Opportunity Score",
            f"{breakdown['company_score']:.1f}",
            "🏢 Company-specific opportunity (0-100). Weighted 60% in Final Score for Prospects. For Prospects: ICP Fit (50%), Buildings (20%), Revenue (15%), Employees (10%), Contacts (5%). For Customers: Expansion (40%), Churn (30%), Profitability (20%), Tickets (10%)."
        )

    with col3:
        metric_with_tooltip(
            "Final Score",
            f"{breakdown['final_score']:.1f}",
            "⭐ Overall opportunity score (0-100). For Prospects: (NAICS Score × 40%) + (Company Score × 60%). For Customers: Company Score only. 90-100=Elite, 80-89=Strong, 70-79=Good, 60-69=Fair, <60=Lower priority."
        )

    st.markdown("---")

    # Display segment rank and NAICS
    col1, col2 = st.columns(2)

    with col1:
        metric_with_tooltip(
            "Segment Rank",
            f"#{breakdown['segment_rank']}",
            "🏆 Rank within this company's NAICS segment (8-digit code). Rankings are per-segment to enable fair comparisons between companies in the same industry. #1 = highest Final Score in segment."
        )

    with col2:
        metric_with_tooltip(
            "NAICS Code",
            breakdown['naics_code'],
            "🏭 8-digit NAICS code for this company's primary business activity. First 4 digits determine the NAICS Attractiveness Score shared by all companies in that industry group."
        )

    st.markdown("---")

    # Component Scores Section
    st.subheader("Component Scores")

    scoring_path = breakdown['scoring_path']

    if scoring_path == "Prospect":
        st.markdown("**Company Opportunity Components** (for Prospects)")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            icp_score = scored.get('icp_fit_score')
            if pd.notna(icp_score):
                metric_with_tooltip(
                    "ICP Fit",
                    f"{int(icp_score)}",
                    "🤖 Company ICP Fit Score (0-100). Worth 50% of Company Score! Claude AI evaluates multi-location potential, facility type, operational fit, and similarity to successful customers. 70+=Strong fit, 40-69=Moderate, <40=Poor fit."
                )

        with col2:
            buildings_score = scored.get('buildings_score')
            if pd.notna(buildings_score):
                metric_with_tooltip(
                    "Buildings",
                    f"{buildings_score:.1f}",
                    "🏗️ Building count score (0-100). Worth 20% of Company Score. Log-scaled: 1 building=low score, 10+=high score, 100+=maximum. Multi-location companies are key targets for OpenWorks."
                )

        with col3:
            revenue_score = scored.get('revenue_score')
            if pd.notna(revenue_score):
                metric_with_tooltip(
                    "Revenue",
                    f"{revenue_score:.1f}",
                    "💰 Revenue score (0-100). Worth 15% of Company Score. Log-scaled based on annual revenue. Higher revenue = bigger facilities and more ability to pay for services. $100M+ = high scores."
                )

        with col4:
            growth_score = scored.get('growth_score')
            if pd.notna(growth_score):
                metric_with_tooltip(
                    "Employees",
                    f"{growth_score:.1f}",
                    "👥 Employee count score (0-100). Worth 10% of Company Score. Log-scaled proxy for company size. Larger companies = bigger facilities = higher scores. 1,000+ employees = high scores."
                )

        # Second row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            contact_score = scored.get('contact_score')
            if pd.notna(contact_score):
                metric_with_tooltip(
                    "Contacts",
                    f"{contact_score:.1f}",
                    "📞 Contact availability score (0-100). Worth 5% of Company Score. Having contacts = 75 points, no contacts = 25 points. Makes outreach easier and improves conversion odds."
                )

    else:  # Customer Expansion
        st.markdown("**Company Opportunity Components** (for Customer Expansion)")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            expansion_score = scored.get('expansion_score')
            if pd.notna(expansion_score):
                metric_with_tooltip(
                    "Expansion",
                    f"{expansion_score:.1f}",
                    "📈 Expansion opportunity score (0-100). Worth 40% of Company Score for customers. Based on unpenetrated buildings × revenue potential. Low penetration = high expansion score."
                )

        with col2:
            churn_score = scored.get('churn_score')
            if pd.notna(churn_score):
                metric_with_tooltip(
                    "Churn Health",
                    f"{churn_score:.1f}",
                    "🔄 Customer retention health (0-100). Worth 30% of Company Score for customers. Based on churn risk predictions. Higher score = lower churn risk = healthier account."
                )

        with col3:
            profitability_score = scored.get('profitability_score')
            if pd.notna(profitability_score):
                metric_with_tooltip(
                    "Profitability",
                    f"{profitability_score:.1f}",
                    "💵 Account profitability score (0-100). Worth 20% of Company Score for customers. Based on margin data. Higher margins = more profitable account = better expansion target."
                )

        with col4:
            tickets_score = scored.get('tickets_score')
            if pd.notna(tickets_score):
                metric_with_tooltip(
                    "Tickets",
                    f"{tickets_score:.1f}",
                    "🎫 Support ticket health (0-100). Worth 10% of Company Score for customers. Based on ticket volume and severity. Fewer/better tickets = higher score = healthier account."
                )

    st.markdown("---")

    # Display scoring reason (explains what factors were used)
    st.subheader("Scoring Rationale")
    st.info(f"{breakdown['scoring_reason']}")

    # Add explanation of scoring paths
    with st.expander("ℹ️ About Scoring Methodology"):
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
        | **Revenue per Building** | 5% | Avg monthly revenue/building vs median | \\$5,550/building = 92, \\$1,187/building = 29 |
        | **Churn Health** | 15% | Customer retention in industry | Low churn = 90+, high churn = <60 |
        | **Ticket Health** | 5% | Support ticket quality/volume | Few tickets = 55+, many tickets = 35 |

        **Formula**: NAICS Score = (ICP Fit × 25%) + (Market Size × 15%) + (OW Rev Conc × 15%) + (OW Buildings × 20%) + (Rev/Building × 5%) + (Churn × 15%) + (Tickets × 5%)

        ##### **Company Opportunity Score** (0-100, weighted 60%):
        Company-specific score evaluating the opportunity at this particular company.

        | Component | Weight | Description | Example |
        |-----------|--------|-------------|---------|
        | **ICP Fit** | 50% | Claude AI assessment of company-ICP alignment | 63 = Decent fit, 30 = Poor fit |
        | **Buildings** | 20% | Number of locations (log-scaled) | 11 locations = 50, 100+ locations = 100 |
        | **Revenue** | 15% | Annual revenue (log-scaled) | \\$250M = 100, \\$24M = 83 |
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

# =============================================================================
# TAB 3: ICP RESEARCH
# =============================================================================

with tab3:
    st.subheader("ICP Fit Assessment & Web Research")

    # Load detailed research data from company_icp_scores_with_research.csv
    research_record = None
    if research_data_df is not None:
        research_matches = research_data_df[research_data_df['company_id'] == company_id]
        if len(research_matches) > 0:
            research_record = research_matches.iloc[0]

    # =============================================================================
    # ICP FIT METRICS
    # =============================================================================

    st.markdown("### 🎯 ICP Fit Score")

    col1, col2, col3 = st.columns(3)

    with col1:
        icp_score = scored.get('icp_fit_score')
        if pd.notna(icp_score):
            st.metric("ICP Fit Score", f"{int(icp_score)}/100")
        else:
            st.metric("ICP Fit Score", "N/A")

    with col2:
        if research_record is not None and pd.notna(research_record.get('recommendation')):
            st.metric("Recommendation", research_record['recommendation'])
        elif pd.notna(scored.get('icp_recommendation')):
            st.metric("Recommendation", scored['icp_recommendation'])
        else:
            st.metric("Recommendation", "N/A")

    with col3:
        if research_record is not None and pd.notna(research_record.get('confidence')):
            st.metric("Confidence", research_record['confidence'])
        elif pd.notna(scored.get('icp_confidence')):
            st.metric("Confidence", scored['icp_confidence'])
        else:
            st.metric("Confidence", "N/A")

    st.markdown("---")

    # Display ICP reasoning
    st.markdown("### 📝 ICP Fit Reasoning")

    reasoning_text = None
    if research_record is not None and pd.notna(research_record.get('reasoning')):
        reasoning_text = research_record['reasoning']
    elif pd.notna(scored.get('icp_fit_reasoning')):
        reasoning_text = scored['icp_fit_reasoning']

    if reasoning_text:
        st.info(reasoning_text)
    else:
        st.info("No ICP reasoning available.")

    # =============================================================================
    # WEB RESEARCH FINDINGS
    # =============================================================================

    # Display web research data if available
    if research_record is not None and research_record.get('had_web_research', False):
        st.markdown("---")
        st.markdown("### 🔍 Web Research Findings")
        st.success("✅ Deep web research was performed for this company")

        # Hot Lead Signals
        if pd.notna(research_record.get('hot_lead_signals')):
            st.markdown("#### 🔥 Hot Lead Signals")
            try:
                signals = json.loads(research_record['hot_lead_signals'])
                if signals:
                    for signal in signals:
                        st.markdown(f"- {signal}")
                else:
                    st.info("No hot lead signals identified")
            except:
                st.markdown(research_record['hot_lead_signals'])

        # Concerns
        if pd.notna(research_record.get('concerns')):
            st.markdown("#### ⚠️ Concerns")
            try:
                concerns = json.loads(research_record['concerns'])
                if concerns:
                    for concern in concerns:
                        st.markdown(f"- {concern}")
                else:
                    st.info("No major concerns identified")
            except:
                st.markdown(research_record['concerns'])

        # Timing Assessment
        if pd.notna(research_record.get('timing')) and research_record['timing']:
            st.markdown("#### ⏰ Timing Assessment")
            st.info(research_record['timing'])

        # Research Summary (detailed JSON data)
        if pd.notna(research_record.get('research_summary')):
            st.markdown("---")
            with st.expander("📊 View Detailed Research Summary", expanded=False):
                try:
                    summary = json.loads(research_record['research_summary'])

                    # Display news findings
                    if 'news_findings' in summary:
                        st.markdown("#### 📰 News Findings")
                        news = summary['news_findings']
                        if news.get('found_recent_news'):
                            st.markdown(f"**Headline:** {news.get('headline', 'N/A')}")
                            st.markdown(f"**Date:** {news.get('date', 'N/A')}")
                            st.markdown(f"**Signal Type:** {news.get('signal_type', 'N/A')}")
                            st.markdown(f"**Summary:** {news.get('summary', 'N/A')}")
                        else:
                            st.info("No recent news found")
                        st.markdown("---")

                    # Display jobs findings
                    if 'jobs_findings' in summary:
                        st.markdown("#### 💼 Jobs/Hiring Findings")
                        jobs = summary['jobs_findings']
                        st.markdown(f"**Operations Roles Found:** {jobs.get('found_ops_roles', False)}")
                        st.markdown(f"**Hiring Scale:** {jobs.get('hiring_scale', 'N/A')}")
                        st.markdown(f"**Summary:** {jobs.get('summary', 'N/A')}")
                        if jobs.get('role_examples'):
                            st.markdown("**Example Roles:**")
                            for role in jobs['role_examples'][:5]:
                                st.markdown(f"- {role}")
                        st.markdown("---")

                    # Display corporate operations findings
                    if 'corporate_ops_findings' in summary:
                        st.markdown("#### 🏢 Corporate Operations Findings")
                        ops = summary['corporate_ops_findings']
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Has Vendor Portal:** {'✅' if ops.get('has_vendor_portal', False) else '❌'}")
                            st.markdown(f"**Has Facilities Dept:** {'✅' if ops.get('has_facilities_dept', False) else '❌'}")
                        with col2:
                            st.markdown(f"**Centralized Operations:** {'✅' if ops.get('centralized_operations', False) else '❌'}")
                            st.markdown(f"**Professionalism Level:** {ops.get('professionalism_level', 'N/A')}")
                        st.markdown(f"**Summary:** {ops.get('summary', 'N/A')}")

                except Exception as e:
                    st.warning(f"Could not parse research summary: {e}")
                    st.code(research_record['research_summary'])
    else:
        st.markdown("---")
        st.info("No web research was performed for this company. Web research is only conducted for companies meeting minimum thresholds (5+ locations, $10M+ revenue OR 100+ employees).")

# =============================================================================
# TAB 4: CHURN
# =============================================================================

with tab4:
    st.subheader("Churn Risk Prediction")

    if has_churn_data(company_id, churn_df):
        churn = get_churn_prediction(company_id, churn_df)

        if churn is not None:
            # Display churn metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                churn_prob = churn['churn_probability']
                st.metric("Churn Probability", f"{churn_prob:.1%}")

            with col2:
                risk_tier = churn['risk_tier']
                st.metric("Risk Tier", risk_tier)

            with col3:
                pred_date = churn.get('prediction_date', 'N/A')
                st.metric("Prediction Date", pred_date)

            # Risk tier color coding
            st.markdown("---")

            if risk_tier == 'High':
                st.error("🚨 **High Risk**: This customer is at high risk of churn. Immediate action recommended.")
            elif risk_tier == 'Medium':
                st.warning("⚠️ **Medium Risk**: Monitor this customer closely for signs of dissatisfaction.")
            elif risk_tier == 'Low':
                st.success("✅ **Low Risk**: This customer appears stable.")
            else:
                st.info(f"Risk Tier: {risk_tier}")
        else:
            st.info("Churn prediction data not available for this company.")
    else:
        st.info("Churn predictions not available (Epic 6 not complete or no prediction for this company).")

# =============================================================================
# BACK TO LIST BUTTON
# =============================================================================

st.markdown("---")

if st.button("← Back to Ranked Companies", key="back_to_ranked"):
    # Clear selected company
    if 'selected_company_id' in st.session_state:
        del st.session_state.selected_company_id
    st.info("Navigate to **Ranked Companies** page using the sidebar.")
