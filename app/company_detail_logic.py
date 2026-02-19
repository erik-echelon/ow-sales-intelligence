"""
Business Logic for Company Detail Page

Contains testable functions for retrieving and formatting company detail data.

Epic 5 (OWRKS-5.07)
Spec: Screen 2 (Company Detail)
"""

from typing import Dict, Optional

import pandas as pd
import streamlit as st


def get_selected_company_id() -> Optional[str]:
    """
    Get selected company ID from session state.

    Returns:
        Company ID or None if not set

    Spec: Page 2 requirements - Use selected_company_id from session
    """
    return st.session_state.get('selected_company_id')


def get_company_by_id(company_id: str, companies_df: pd.DataFrame) -> Optional[pd.Series]:
    """
    Get company data by ID.

    Args:
        company_id: Company ID to retrieve
        companies_df: Companies dataframe

    Returns:
        Company data as Series or None if not found
    """
    matches = companies_df[companies_df['company_id'].astype(str) == str(company_id)]

    if len(matches) == 0:
        return None

    return matches.iloc[0]


def get_scored_company_by_id(company_id: str, scored_df: pd.DataFrame) -> Optional[pd.Series]:
    """
    Get scored company data by ID.

    Args:
        company_id: Company ID to retrieve
        scored_df: Scored companies dataframe

    Returns:
        Scored company data as Series or None if not found
    """
    matches = scored_df[scored_df['company_id'].astype(str) == str(company_id)]

    if len(matches) == 0:
        return None

    return matches.iloc[0]


def get_company_buildings(company_id: str, buildings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get all buildings for a company.

    Args:
        company_id: Company ID
        buildings_df: Buildings dataframe

    Returns:
        Filtered buildings dataframe
    """
    # Normalize company_id to handle zero-padding inconsistencies
    # Both '7526346' and '007526346' should match
    company_id_str = str(company_id).lstrip('0') or '0'  # Keep '0' if all zeros

    # Filter buildings where company_id matches (after removing leading zeros from both sides)
    mask = buildings_df['company_id'].astype(str).str.lstrip('0').fillna('0') == company_id_str
    return buildings_df[mask].copy()


def get_company_contacts(company_id: str, contacts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get all contacts for a company.

    Args:
        company_id: Company ID
        contacts_df: Contacts dataframe

    Returns:
        Filtered contacts dataframe
    """
    return contacts_df[contacts_df['company_id'].astype(str) == str(company_id)].copy()


def format_company_info(company_data: pd.Series) -> Dict[str, str]:
    """
    Format company info for display.

    Args:
        company_data: Company data series

    Returns:
        Dictionary of formatted info fields

    Spec: Info tab requirements
    """
    info = {
        'Company ID': str(company_data.get('company_id', 'N/A')),
        'Name': str(company_data.get('name', 'N/A')),
        'NAICS': str(company_data.get('primary_naics', 'N/A')),
        'Buildings': str(int(company_data.get('building_count', 0)))
    }

    # Add HQ coordinates if available
    try:
        lat = company_data.get('hq_latitude')
        lon = company_data.get('hq_longitude')
        if pd.notna(lat) and pd.notna(lon):
            # Convert to float (they may be strings from CSV)
            lat_float = float(lat)
            lon_float = float(lon)
            info['HQ Location'] = f"{lat_float:.4f}, {lon_float:.4f}"
    except (ValueError, TypeError):
        # If conversion fails, skip HQ location
        pass

    return info


def calculate_penetration_rate(buildings_df: pd.DataFrame) -> float:
    """
    Calculate penetration rate for company's buildings.

    Args:
        buildings_df: Buildings dataframe for company

    Returns:
        Penetration rate as percentage (0-100)

    Spec: Penetration display requirements
    """
    if len(buildings_df) == 0:
        return 0.0

    served_count = buildings_df['is_served'].sum()
    total_count = len(buildings_df)

    return (served_count / total_count) * 100.0


def has_churn_data(company_id: str, churn_df: Optional[pd.DataFrame]) -> bool:
    """
    Check if company has churn prediction data.

    Args:
        company_id: Company ID
        churn_df: Churn predictions dataframe (may be None)

    Returns:
        True if churn data exists for company

    Spec: Churn tab requirements - Optional Epic 6 data
    """
    if churn_df is None:
        return False

    matches = churn_df[churn_df['company_id'].astype(str) == str(company_id)]
    return len(matches) > 0


def get_churn_prediction(company_id: str, churn_df: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    """
    Get churn prediction for company.

    Args:
        company_id: Company ID
        churn_df: Churn predictions dataframe (may be None)

    Returns:
        Churn prediction data or None
    """
    if churn_df is None:
        return None

    matches = churn_df[churn_df['company_id'].astype(str) == str(company_id)]

    if len(matches) == 0:
        return None

    return matches.iloc[0]


def format_score_components(scored_data: pd.Series) -> Dict[str, float]:
    """
    Format score components for display.

    Converts 0-1 scale scores to 0-100 scale for display.

    Args:
        scored_data: Scored company data

    Returns:
        Dictionary of component names to scores (0-100 scale)

    Spec: Scoring tab requirements - Component breakdown
    """
    components = {}

    # ICP Fit Score (0-1 to 0-100)
    if 'icp_fit_score' in scored_data and pd.notna(scored_data['icp_fit_score']):
        components['ICP Fit Score'] = scored_data['icp_fit_score'] * 100

    # Expansion Potential (0-1 to 0-100)
    if 'expansion_potential' in scored_data and pd.notna(scored_data['expansion_potential']):
        components['Expansion Potential'] = scored_data['expansion_potential'] * 100

    # Decision Maker Clarity (0-1 to 0-100)
    if 'decision_maker_clarity' in scored_data and pd.notna(scored_data['decision_maker_clarity']):
        components['Decision Maker Clarity'] = scored_data['decision_maker_clarity'] * 100

    # Hygiene Relevance (0-1 to 0-100)
    if 'hygiene_relevance' in scored_data and pd.notna(scored_data['hygiene_relevance']):
        components['Hygiene Relevance'] = scored_data['hygiene_relevance'] * 100

    # Revenue Potential (0-1 to 0-100)
    if 'revenue_potential' in scored_data and pd.notna(scored_data['revenue_potential']):
        components['Revenue Potential'] = scored_data['revenue_potential'] * 100

    # Buyer Intent (0-1 to 0-100)
    if 'buyer_intent' in scored_data and pd.notna(scored_data['buyer_intent']):
        components['Buyer Intent'] = scored_data['buyer_intent'] * 100

    # Geographic Fit (0-1 to 0-100)
    if 'geographic_fit' in scored_data and pd.notna(scored_data['geographic_fit']):
        components['Geographic Fit'] = scored_data['geographic_fit'] * 100

    return components


def format_buildings_display(buildings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Format buildings dataframe for display.

    Args:
        buildings_df: Buildings dataframe

    Returns:
        Formatted dataframe for display

    Spec: Buildings tab requirements
    """
    display_df = buildings_df.copy()

    # Format served status
    display_df['Status'] = display_df['is_served'].apply(
        lambda x: '✅ Served' if x else '❌ Unserved'
    )

    # Format square footage
    display_df['Square Feet'] = display_df['square_footage'].apply(
        lambda x: f"{int(x):,}" if pd.notna(x) else 'N/A'
    )

    # Select columns for display
    display_columns = ['City', 'State', 'Status', 'Square Feet']

    # Rename columns if needed
    if 'city' in display_df.columns:
        display_df['City'] = display_df['city']
    if 'state' in display_df.columns:
        display_df['State'] = display_df['state']

    return display_df[display_columns]


def format_contacts_display(contacts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Format contacts dataframe for display.

    Note: contact_summary.csv contains aggregated contact data at company level,
    not individual contact records.

    Args:
        contacts_df: Contacts dataframe (aggregated by company)

    Returns:
        Formatted dataframe for display

    Spec: Contacts tab requirements
    """
    if len(contacts_df) == 0:
        return pd.DataFrame()

    display_df = contacts_df.copy()

    # Format aggregated contact data for display
    display_df['Contact Count'] = display_df['contact_count'].fillna(0).astype(int)
    display_df['Contact Names'] = display_df['contact_names'].fillna('N/A')
    display_df['Contact Emails'] = display_df['contact_emails'].fillna('N/A')
    display_df['Last Contact'] = display_df['last_contact_date'].fillna('N/A')

    # Select columns for display
    display_columns = ['Contact Count', 'Contact Names', 'Contact Emails', 'Last Contact']

    return display_df[display_columns]


def get_no_company_selected_message() -> str:
    """
    Get message to display when no company is selected.

    Returns:
        Message string
    """
    return (
        "No company selected. Please select a company from the **Ranked Companies** page "
        "and click 'View Company Detail'."
    )


def get_company_not_found_message(company_id: str) -> str:
    """
    Get message to display when company ID not found.

    Args:
        company_id: Company ID that wasn't found

    Returns:
        Error message string
    """
    return f"Company ID '{company_id}' not found in data. The company may have been removed or the ID is invalid."


def format_scoring_breakdown(scored_data: pd.Series) -> Dict[str, any]:
    """
    Format scoring breakdown for display in Tab 2.

    Args:
        scored_data: Scored company data from scored_companies_final.csv

    Returns:
        Dictionary with scoring breakdown components

    Epic 5 Task 3: New scoring tab
    """
    breakdown = {}

    # Scoring path (Customer Expansion vs Prospect)
    breakdown['scoring_path'] = scored_data.get('scoring_path', 'Prospect')

    # NAICS attractiveness score (segment-level)
    breakdown['naics_score'] = scored_data.get('naics_attractiveness_score', 0)

    # Company opportunity score (company-level)
    breakdown['company_score'] = scored_data.get('company_opportunity_score', 0)

    # Final score (combined)
    breakdown['final_score'] = scored_data.get('final_score', 0)

    # Scoring reason (explains what factors were used)
    breakdown['scoring_reason'] = scored_data.get('scoring_reason', 'N/A')

    # Segment rank
    breakdown['segment_rank'] = scored_data.get('rank', 'N/A')

    # NAICS code
    breakdown['naics_code'] = scored_data.get('primary_naics', 'N/A')

    return breakdown


def format_hq_info(company_data: pd.Series) -> Dict[str, str]:
    """
    Format HQ information for display in Tab 4 (replaces Buildings tab).

    Args:
        company_data: Company data series

    Returns:
        Dictionary of formatted HQ info fields

    Epic 5 Task 3: New HQ Info tab
    """
    hq_info = {}

    # HQ address components
    hq_info['city'] = str(company_data.get('city', 'N/A'))
    hq_info['state'] = str(company_data.get('state', 'N/A'))

    # HQ coordinates
    try:
        lat = company_data.get('hq_latitude')
        lon = company_data.get('hq_longitude')
        if pd.notna(lat) and pd.notna(lon):
            lat_float = float(lat)
            lon_float = float(lon)
            hq_info['coordinates'] = f"{lat_float:.4f}, {lon_float:.4f}"
        else:
            hq_info['coordinates'] = 'N/A'
    except (ValueError, TypeError):
        hq_info['coordinates'] = 'N/A'

    # Building count estimate (from building_count_estimate or building_count field)
    building_count = company_data.get('building_count_estimate', company_data.get('building_count', 0))
    hq_info['building_count_estimate'] = str(int(building_count)) if pd.notna(building_count) else 'N/A'

    # Employee count (try location_employee_size first, then employees field)
    employee_size = company_data.get('location_employee_size')
    if pd.isna(employee_size):
        employee_size = company_data.get('employees')

    if pd.notna(employee_size):
        try:
            hq_info['employee_size'] = str(int(float(employee_size)))
        except (ValueError, TypeError):
            hq_info['employee_size'] = 'N/A'
    else:
        hq_info['employee_size'] = 'N/A'

    # Sales volume (revenue) - try multiple fields
    sales_volume = company_data.get('sales_volume')
    if pd.isna(sales_volume):
        # Fall back to corporate_sales_revenue if available
        sales_volume = company_data.get('corporate_sales_revenue')
    if pd.isna(sales_volume):
        # Fall back to revenue field
        sales_volume = company_data.get('revenue')

    if pd.notna(sales_volume):
        # Format as currency if numeric
        try:
            sales_float = float(sales_volume)
            hq_info['sales_volume'] = f"${sales_float:,.0f}"
        except (ValueError, TypeError):
            hq_info['sales_volume'] = str(sales_volume)
    else:
        hq_info['sales_volume'] = 'N/A'

    return hq_info
