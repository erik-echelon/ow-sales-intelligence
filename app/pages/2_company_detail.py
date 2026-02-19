"""
Page 2: Company Detail

Deep dive view for individual company with tabs for all data aspects.

Epic 5 (OWRKS-5.07)
Spec: Screen 2 (Company Detail)
"""

import json
import logging

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
# GET SELECTED COMPANY
# =============================================================================

company_id = get_selected_company_id()

if not company_id:
    st.warning(get_no_company_selected_message())
    st.stop()

# =============================================================================
# LOAD DATA
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
        st.metric("Company ID", info['Company ID'])
        st.metric("Name", info['Name'])

    with col2:
        st.metric("NAICS Code", info['NAICS'])
        st.metric("City", hq_info['city'])

    with col3:
        st.metric("State", hq_info['state'])
        st.metric("Coordinates", hq_info['coordinates'])

    st.markdown("---")

    # Company Size Metrics
    st.subheader("Company Size")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Building Count Estimate", hq_info['building_count_estimate'])

    with col2:
        st.metric("Employee Count", hq_info['employee_size'])

    with col3:
        st.metric("Sales Volume", hq_info['sales_volume'])

    # Calculate and display penetration
    st.markdown("---")
    st.subheader("Penetration Metrics")

    penetration_rate = calculate_penetration_rate(buildings)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Buildings", len(buildings))

    with col2:
        served_count = buildings['is_served'].sum()
        st.metric("Served Buildings", served_count)

    with col3:
        st.metric("Penetration Rate", f"{penetration_rate:.1f}%")

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
            st.metric("Total Contacts", int(contacts_count))

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
                        st.metric("Primary Contact", full_name)

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

    # Display three key scores in columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "NAICS Attractiveness Score",
            f"{breakdown['naics_score']:.1f}",
            help="Industry-level attractiveness score based on market size, profitability, churn health, and ticket health"
        )

    with col2:
        st.metric(
            "Company Opportunity Score",
            f"{breakdown['company_score']:.1f}",
            help="Company-level score based on fit, expansion potential, contact quality, and buying intent"
        )

    with col3:
        st.metric(
            "Final Score",
            f"{breakdown['final_score']:.1f}",
            help="Combined score (NAICS attractiveness weighted 40%, company opportunity 60%)"
        )

    st.markdown("---")

    # Display segment rank and NAICS
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Segment Rank", f"#{breakdown['segment_rank']}")

    with col2:
        st.metric("NAICS Code", breakdown['naics_code'])

    st.markdown("---")

    # Display scoring reason (explains what factors were used)
    st.subheader("Scoring Details")
    st.info(f"**Scoring Rationale:** {breakdown['scoring_reason']}")

    # Add explanation of scoring paths
    with st.expander("ℹ️ About Scoring Paths"):
        st.markdown("""
        **Customer Expansion** (5 factors):
        - Expansion Potential (30%): Based on penetration rate
        - Churn Health (25%): Based on churn risk model
        - Profitability (20%): Placeholder for future margin data
        - Ticket Health (15%): Based on support ticket severity
        - Revenue (10%): Based on current building count

        **Prospect** (4 factors):
        - Facility Portfolio (40%): Based on building count and size
        - Contact Quality (30%): Based on HubSpot/DataAxle contacts
        - Buying Intent (20%): Placeholder for future intent signals
        - NAICS Quality (10%): Based on industry vertical value

        **Note:** Missing data receives a neutral score of 50 to ensure low scores reflect actual poor performance, not missing data.
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
