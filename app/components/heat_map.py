"""
Heat Map Component for OpenWorks Prospect Intelligence UI

Implements rendering of US heat map with served/unserved building markers
and coordinate validation.

Epic 5 (OWRKS-5.10)
Spec: §2.1.2 (Geo-coordinate Validity), §4.1 (Performance Gates)
"""

from typing import Dict, Optional, Tuple

import folium
import pandas as pd


def validate_coordinates(latitude: any, longitude: any) -> Tuple[bool, Optional[str]]:
    """
    Validate that coordinates are non-null and within valid ranges.

    Args:
        latitude: Latitude value
        longitude: Longitude value

    Returns:
        Tuple of (is_valid, reason_if_invalid)

    Spec: §2.1.2 Geo-coordinate Validity
    """
    # Check for missing coordinates
    if pd.isna(latitude) or pd.isna(longitude):
        return False, "Coordinates missing"

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (ValueError, TypeError):
        return False, "Coordinates not numeric"

    # Check if in valid range
    if not (-90 <= lat <= 90):
        return False, f"Latitude out of range: {lat}"

    if not (-180 <= lon <= 180):
        return False, f"Longitude out of range: {lon}"

    return True, None


def filter_valid_coordinates(
    buildings_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filter buildings to only those with valid coordinates.

    Args:
        buildings_df: Buildings dataframe

    Returns:
        Tuple of (valid_buildings_df, excluded_buildings_df)

    Spec: §2.1.2 Geo-coordinate Validity, coordinate exclusion logging
    """
    valid_mask = buildings_df.apply(
        lambda row: validate_coordinates(row['latitude'], row['longitude'])[0],
        axis=1
    )

    valid_buildings = buildings_df[valid_mask].copy()
    excluded_buildings = buildings_df[~valid_mask].copy()

    return valid_buildings, excluded_buildings


def get_exclusion_summary(excluded_df: pd.DataFrame) -> Dict:
    """
    Get summary statistics for excluded buildings by source.

    Args:
        excluded_df: Excluded buildings dataframe

    Returns:
        Dictionary with exclusion statistics segmented by source

    Spec: Coordinate exclusion logging with source segmentation
    """
    if len(excluded_df) == 0:
        return {
            'total': 0,
            'by_source': {
                'dataaxle': 0,
                'manual': 0
            }
        }

    by_source = excluded_df.groupby('source').size().to_dict()

    return {
        'total': len(excluded_df),
        'by_source': {
            'dataaxle': by_source.get('dataaxle', 0),
            'manual': by_source.get('manual', 0)
        }
    }


def get_marker_color(
    is_customer: bool = False,
    has_research: bool = False,
    score: float = 0,
    color_mode: str = 'customer_status'
) -> str:
    """
    Get marker color based on selected color mode.

    Args:
        is_customer: Whether company is a customer
        has_research: Whether company has research document
        score: Final score (0-100)
        color_mode: 'customer_status', 'research_status', or 'score_tier'

    Returns:
        Color string for marker

    Epic 5: Updated heat map with multiple color modes
    """
    if color_mode == 'customer_status':
        # Green for customers, red for prospects
        return 'green' if is_customer else 'red'

    elif color_mode == 'research_status':
        # Blue for has research, gray for no research
        return 'blue' if has_research else 'gray'

    elif color_mode == 'score_tier':
        # Green (80+), yellow (60-79), orange (40-59), red (<40)
        if score >= 80:
            return 'green'
        elif score >= 60:
            return 'gold'  # Folium uses 'gold' for yellow
        elif score >= 40:
            return 'orange'
        else:
            return 'red'

    # Default fallback
    return 'blue'


def format_tooltip(
    company_name: str,
    city: str,
    state: str,
    source: str
) -> str:
    """
    Format tooltip text for building marker.

    Args:
        company_name: Company name
        city: City
        state: State
        source: Source (dataaxle or manual)

    Returns:
        Formatted HTML tooltip

    Spec: Tooltips show company name, city, state, source
    """
    # Format source with badge
    source_display = '🔵 DataAxle' if source == 'dataaxle' else '🟢 Manual'

    return f"""
    <b>{company_name}</b><br>
    {city}, {state}<br>
    {source_display}
    """


def get_map_center() -> Dict:
    """
    Get map center coordinates for continental US.

    Returns:
        Dictionary with lat, lon, zoom

    Spec: Center map on continental US (lat=39.8, lon=-98.6, zoom=4)
    """
    return {
        'lat': 39.8,
        'lon': -98.6,
        'zoom': 4
    }


def create_base_map() -> folium.Map:
    """
    Create base Folium map centered on continental US.

    Returns:
        Folium Map object

    Spec: Center map requirement
    """
    center = get_map_center()

    m = folium.Map(
        location=[center['lat'], center['lon']],
        zoom_start=center['zoom'],
        tiles='OpenStreetMap'
    )

    return m


def filter_by_served_status(
    buildings_df: pd.DataFrame,
    served_filter: str
) -> pd.DataFrame:
    """
    Filter buildings by served status.

    Args:
        buildings_df: Buildings dataframe
        served_filter: 'all', 'served', or 'unserved'

    Returns:
        Filtered dataframe

    Spec: Served status filter requirement
    """
    if served_filter == 'all':
        return buildings_df.copy()

    if served_filter == 'served':
        return buildings_df[buildings_df['is_served'] == True].copy()

    if served_filter == 'unserved':
        return buildings_df[buildings_df['is_served'] == False].copy()

    return buildings_df.copy()


def filter_by_source(buildings_df: pd.DataFrame, source_filter: str) -> pd.DataFrame:
    """
    Filter buildings by source.

    Args:
        buildings_df: Buildings dataframe
        source_filter: 'all', 'dataaxle', or 'manual'

    Returns:
        Filtered dataframe

    Spec: Source filter requirement
    """
    if source_filter == 'all':
        return buildings_df.copy()

    return buildings_df[buildings_df['source'] == source_filter].copy()


def create_us_heat_map(
    companies_df: pd.DataFrame,
    color_mode: str = 'customer_status'
) -> Tuple[folium.Map, Dict]:
    """
    Create US heat map with HQ location markers for companies.

    Args:
        companies_df: Companies dataframe with HQ coordinates (scored_companies_final.csv)
        color_mode: 'customer_status', 'research_status', or 'score_tier'

    Returns:
        Tuple of (folium_map, statistics_dict)

    Epic 5: Updated to show HQ locations only with multiple color modes
    """
    # Rename columns to match expected names for validation
    # scored_companies_final.csv uses different column names
    companies_df = companies_df.copy()

    # Ensure we have required coordinate columns
    if 'hq_latitude' in companies_df.columns and 'hq_longitude' in companies_df.columns:
        companies_df['latitude'] = companies_df['hq_latitude']
        companies_df['longitude'] = companies_df['hq_longitude']

    # Filter to valid coordinates
    valid_companies, excluded_companies = filter_valid_coordinates(companies_df)

    # Get exclusion summary (note: scored companies don't have 'source' field)
    # Count total exclusions
    exclusion_count = len(excluded_companies)

    # Create base map
    m = create_base_map()

    # Add markers for each valid company HQ
    for _, company in valid_companies.iterrows():
        # Get company attributes for coloring
        is_customer = company.get('is_customer', False)
        has_research = company.get('has_research_doc', False)
        score = company.get('final_score', 0)

        # Get marker color based on mode
        color = get_marker_color(
            is_customer=is_customer,
            has_research=has_research,
            score=score,
            color_mode=color_mode
        )

        # Format tooltip
        company_name = company.get('company_name', 'Unknown')
        city = company.get('city', 'Unknown')
        state = company.get('state', 'Unknown')

        tooltip_text = f"""
        <b>{company_name}</b><br>
        {city}, {state}<br>
        Score: {score:.1f}<br>
        {'✅ Customer' if is_customer else '❌ Prospect'}<br>
        {'📄 Has Research' if has_research else ''}
        """

        # Add marker
        folium.CircleMarker(
            location=[company['latitude'], company['longitude']],
            radius=5,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            popup=tooltip_text,
            tooltip=tooltip_text
        ).add_to(m)

    # Compile statistics
    stats = {
        'total_companies': len(companies_df),
        'valid_companies': len(valid_companies),
        'excluded_companies': exclusion_count,
        'customers': int(valid_companies['is_customer'].sum()) if 'is_customer' in valid_companies.columns else 0,
        'prospects': len(valid_companies) - int(valid_companies['is_customer'].sum()) if 'is_customer' in valid_companies.columns else len(valid_companies)
    }

    return m, stats


def format_exclusion_warning(stats: Dict) -> Optional[str]:
    """
    Format exclusion warning message.

    Args:
        stats: Statistics dictionary from create_us_heat_map

    Returns:
        Formatted warning message or None if no exclusions

    Spec: Display exclusion warning with source counts
    """
    if stats['excluded_buildings'] == 0:
        return None

    dataaxle_count = stats['exclusion_by_source']['dataaxle']
    manual_count = stats['exclusion_by_source']['manual']

    return (
        f"⚠️ {stats['excluded_buildings']} buildings excluded from map "
        f"(missing or invalid coordinates): "
        f"DataAxle: {dataaxle_count}, Manual: {manual_count}"
    )
