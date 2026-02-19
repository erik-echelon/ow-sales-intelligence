"""
Filter State Management Component for OpenWorks Prospect Intelligence UI

Implements reusable filter components that maintain state across page navigation
using Streamlit session_state.

Epic 5 (OWRKS-5.03)
Spec: §2.1.3 (Filter State Consistency)
"""

from typing import List, Optional

import pandas as pd
import streamlit as st


def init_filter_state():
    """
    Initialize all filter defaults in session state.

    Only sets defaults if keys don't already exist, preserving user selections
    across page navigation.

    Spec: §2.1.3 Filter State Consistency
    """
    if 'naics_filter' not in st.session_state:
        st.session_state.naics_filter = 'all'

    if 'source_filter' not in st.session_state:
        st.session_state.source_filter = 'all'

    if 'channel_filter' not in st.session_state:
        st.session_state.channel_filter = 'all'

    if 'research_filter' not in st.session_state:
        st.session_state.research_filter = 'all'

    if 'served_filter' not in st.session_state:
        st.session_state.served_filter = 'all'


def get_unique_naics(df: pd.DataFrame) -> List[str]:
    """
    Extract unique NAICS codes from dataframe.

    Args:
        df: DataFrame with 'primary_naics' column

    Returns:
        Sorted list of unique NAICS codes
    """
    if 'primary_naics' not in df.columns:
        return []

    naics_codes = df['primary_naics'].dropna().unique().tolist()
    return sorted(naics_codes)


def get_unique_channels(df: pd.DataFrame) -> List[str]:
    """
    Extract unique channels from dataframe.

    Args:
        df: DataFrame with 'channel_id' column

    Returns:
        Sorted list of unique channel IDs
    """
    if 'channel_id' not in df.columns:
        return []

    channels = df['channel_id'].dropna().unique().tolist()
    return sorted(channels)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply active filters to DataFrame based on session state.

    Supports filtering by:
    - NAICS code (single or list)
    - Source (dataaxle/manual/all)
    - Channel ID
    - Research status (has_research/no_research/all)
    - Served status (served/unserved/all) - for buildings only

    Args:
        df: DataFrame to filter

    Returns:
        Filtered DataFrame

    Spec: §2.1.3 Filter State Consistency
    """
    filtered_df = df.copy()

    # NAICS filter
    if 'primary_naics' in filtered_df.columns:
        naics_filter = st.session_state.get('naics_filter', 'all')
        if naics_filter != 'all':
            if isinstance(naics_filter, list):
                # Multiple NAICS codes selected
                filtered_df = filtered_df[filtered_df['primary_naics'].isin(naics_filter)]
            else:
                # Single NAICS code selected
                filtered_df = filtered_df[filtered_df['primary_naics'] == naics_filter]

    # Source filter
    if 'source' in filtered_df.columns:
        source_filter = st.session_state.get('source_filter', 'all')
        if source_filter != 'all':
            filtered_df = filtered_df[filtered_df['source'] == source_filter]

    # Channel filter
    if 'channel_id' in filtered_df.columns:
        channel_filter = st.session_state.get('channel_filter', 'all')
        if channel_filter != 'all':
            filtered_df = filtered_df[filtered_df['channel_id'] == channel_filter]

    # Research filter
    if 'has_research_doc' in filtered_df.columns:
        research_filter = st.session_state.get('research_filter', 'all')
        if research_filter == 'has_research':
            filtered_df = filtered_df[filtered_df['has_research_doc'] == True]
        elif research_filter == 'no_research':
            filtered_df = filtered_df[filtered_df['has_research_doc'] == False]

    # Served filter (for buildings dataframe)
    if 'is_served' in filtered_df.columns:
        served_filter = st.session_state.get('served_filter', 'all')
        if served_filter == 'served':
            filtered_df = filtered_df[filtered_df['is_served'] == True]
        elif served_filter == 'unserved':
            filtered_df = filtered_df[filtered_df['is_served'] == False]

    return filtered_df


def reset_filters():
    """
    Reset all filters to default ('all') state.

    Spec: §2.1.3 Filter State Consistency
    """
    st.session_state.naics_filter = 'all'
    st.session_state.source_filter = 'all'
    st.session_state.channel_filter = 'all'
    st.session_state.research_filter = 'all'
    st.session_state.served_filter = 'all'


def render_naics_filter(df: pd.DataFrame, key: str = "naics_filter_widget"):
    """
    Render NAICS code multiselect filter.

    Args:
        df: DataFrame with 'primary_naics' column
        key: Unique key for the widget

    Spec: §2.1.3 Filter State Consistency
    """
    naics_codes = get_unique_naics(df)

    if not naics_codes:
        st.warning("No NAICS codes available for filtering")
        return

    st.subheader("NAICS Filter")

    # "All" option
    all_selected = st.checkbox("All NAICS", value=(st.session_state.naics_filter == 'all'), key=f"{key}_all")

    if all_selected:
        st.session_state.naics_filter = 'all'
    else:
        # Multiselect for specific NAICS codes
        default_value = []
        if st.session_state.naics_filter != 'all':
            if isinstance(st.session_state.naics_filter, list):
                default_value = st.session_state.naics_filter
            else:
                default_value = [st.session_state.naics_filter]

        selected_naics = st.multiselect(
            "Select NAICS codes",
            options=naics_codes,
            default=default_value,
            key=key
        )

        if selected_naics:
            st.session_state.naics_filter = selected_naics if len(selected_naics) > 1 else selected_naics[0]
        else:
            st.session_state.naics_filter = 'all'


def render_channel_filter(df: pd.DataFrame, key: str = "channel_filter_widget"):
    """
    Render channel dropdown filter.

    Args:
        df: DataFrame with 'channel_id' column
        key: Unique key for the widget

    Spec: §2.1.3 Filter State Consistency
    """
    channels = get_unique_channels(df)

    if not channels:
        st.warning("No channels available for filtering")
        return

    st.subheader("Channel Filter")

    options = ['all'] + channels
    current_value = st.session_state.get('channel_filter', 'all')

    if current_value not in options:
        current_value = 'all'

    index = options.index(current_value)

    selected_channel = st.selectbox(
        "Select channel",
        options=options,
        index=index,
        key=key
    )

    st.session_state.channel_filter = selected_channel


def render_source_filter(key: str = "source_filter_widget"):
    """
    Render source radio filter: All / 🔵 DataAxle / 🟢 Manual.

    Args:
        key: Unique key for the widget

    Spec: §2.1.3 Filter State Consistency
    """
    st.subheader("Source Filter")

    options = {
        'all': 'All',
        'dataaxle': '🔵 DataAxle',
        'manual': '🟢 Manual'
    }

    current_value = st.session_state.get('source_filter', 'all')

    # Radio buttons
    selected = st.radio(
        "Filter by source",
        options=list(options.keys()),
        format_func=lambda x: options[x],
        index=list(options.keys()).index(current_value),
        key=key
    )

    st.session_state.source_filter = selected


def render_research_filter(key: str = "research_filter_widget"):
    """
    Render research status radio filter: All / Has Research / No Research.

    Args:
        key: Unique key for the widget

    Spec: §2.1.3 Filter State Consistency
    """
    st.subheader("Research Status Filter")

    options = {
        'all': 'All',
        'has_research': 'Has Research',
        'no_research': 'No Research'
    }

    current_value = st.session_state.get('research_filter', 'all')

    selected = st.radio(
        "Filter by research status",
        options=list(options.keys()),
        format_func=lambda x: options[x],
        index=list(options.keys()).index(current_value),
        key=key
    )

    st.session_state.research_filter = selected


def render_served_filter(key: str = "served_filter_widget"):
    """
    Render served status radio filter: All / Served / Unserved.

    Args:
        key: Unique key for the widget

    Spec: §2.1.3 Filter State Consistency
    """
    st.subheader("Served Status Filter")

    options = {
        'all': 'All',
        'served': 'Served',
        'unserved': 'Unserved'
    }

    current_value = st.session_state.get('served_filter', 'all')

    selected = st.radio(
        "Filter by served status",
        options=list(options.keys()),
        format_func=lambda x: options[x],
        index=list(options.keys()).index(current_value),
        key=key
    )

    st.session_state.served_filter = selected


def render_filter_summary() -> str:
    """
    Render a summary of currently active filters.

    Returns:
        String summary of active filters

    Spec: §2.1.3 Filter State Consistency
    """
    active_filters = []

    naics_filter = st.session_state.get('naics_filter', 'all')
    if naics_filter != 'all':
        if isinstance(naics_filter, list):
            active_filters.append(f"NAICS: {', '.join(naics_filter)}")
        else:
            active_filters.append(f"NAICS: {naics_filter}")

    source_filter = st.session_state.get('source_filter', 'all')
    if source_filter != 'all':
        active_filters.append(f"Source: {source_filter}")

    channel_filter = st.session_state.get('channel_filter', 'all')
    if channel_filter != 'all':
        active_filters.append(f"Channel: {channel_filter}")

    research_filter = st.session_state.get('research_filter', 'all')
    if research_filter != 'all':
        active_filters.append(f"Research: {research_filter}")

    served_filter = st.session_state.get('served_filter', 'all')
    if served_filter != 'all':
        active_filters.append(f"Served: {served_filter}")

    if active_filters:
        return "Active filters: " + " | ".join(active_filters)
    else:
        return "No active filters"


def render_reset_button(key: str = "reset_filters_button"):
    """
    Render reset filters button.

    Args:
        key: Unique key for the widget

    Spec: §2.1.3 Filter State Consistency
    """
    if st.button("🔄 Reset Filters", key=key):
        reset_filters()
        st.rerun()
