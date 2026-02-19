"""
Business Logic for Ranked Companies Page

Contains testable functions for ranking, sorting, formatting, and validation.

Epic 5 (OWRKS-5.05)
Spec: §2.3 (Entity Resolution), §2.5 (Ranking Invariants)
"""

from typing import Dict, Optional

import pandas as pd
import streamlit as st


def validate_segment_rank_contiguity(df: pd.DataFrame) -> None:
    """
    Validate that segment ranks are contiguous (no gaps) within each NAICS segment.

    Args:
        df: DataFrame with 'primary_naics' and 'segment_rank' or 'rank' columns

    Raises:
        AssertionError: If ranks are not contiguous within any segment

    Spec: §2.5 Ranking Invariants - Contiguous ranks
    """
    # Use 'rank' if available (new format), otherwise 'segment_rank' (old format)
    rank_col = 'rank' if 'rank' in df.columns else 'segment_rank'

    if rank_col not in df.columns:
        # Skip validation if neither column exists
        return

    for naics in df['primary_naics'].unique():
        segment_df = df[df['primary_naics'] == naics]
        ranks = sorted(segment_df[rank_col].unique())
        expected_ranks = list(range(1, len(ranks) + 1))

        assert ranks == expected_ranks, (
            f"NAICS {naics}: Ranks {ranks} are not contiguous. Expected {expected_ranks}"
        )


def validate_rank_matches_score_order(df: pd.DataFrame) -> None:
    """
    Validate that ranks match score order within each segment.

    Higher score should have lower rank number.

    Args:
        df: DataFrame with 'primary_naics', score column, and rank column

    Raises:
        AssertionError: If ranks don't match score order

    Spec: §2.5 Ranking Invariants - Rank matches score order
    """
    # Use new format columns if available, otherwise old format
    score_col = 'final_score' if 'final_score' in df.columns else 'augmented_score'
    rank_col = 'rank' if 'rank' in df.columns else 'segment_rank'

    if score_col not in df.columns or rank_col not in df.columns:
        # Skip validation if required columns don't exist
        return

    for naics in df['primary_naics'].unique():
        segment_df = df[df['primary_naics'] == naics].copy()

        # Sort by score descending, using rank as tie-breaker for stable sorting
        # This ensures companies with identical scores maintain consistent rank order
        segment_df = segment_df.sort_values([score_col, rank_col], ascending=[False, True])

        # Expected ranks should be 1, 2, 3, ...
        expected_ranks = list(range(1, len(segment_df) + 1))
        actual_ranks = segment_df[rank_col].tolist()

        assert actual_ranks == expected_ranks, (
            f"NAICS {naics}: Ranks {actual_ranks} don't match score order. Expected {expected_ranks}"
        )


def sort_by_score_within_segment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort companies by score descending within each NAICS segment.

    Args:
        df: DataFrame with 'primary_naics' and score column

    Returns:
        Sorted DataFrame

    Spec: §2.5 Ranking Invariants
    """
    # Use new format score column if available, otherwise old format
    score_col = 'final_score' if 'final_score' in df.columns else 'augmented_score'

    # Sort by NAICS first, then by score descending within each NAICS
    sorted_df = df.sort_values(
        ['primary_naics', score_col],
        ascending=[True, False]
    ).copy()

    return sorted_df


def get_source_badge(source: str) -> str:
    """
    Get source badge emoji/text for display.

    Args:
        source: Source value ('dataaxle' or 'manual')

    Returns:
        Badge string (e.g., "🔵 DataAxle")

    Spec: Page requirements - Source badge per row
    """
    if source == 'dataaxle':
        return "🔵 DataAxle"
    elif source == 'manual':
        return "🟢 Manual"
    else:
        return source


def format_urgent_flags(count: int) -> str:
    """
    Format urgent flags display.

    Args:
        count: Number of urgent flags

    Returns:
        Formatted string (e.g., "🚨 2") or empty if 0

    Spec: Page requirements - 🚨 icon with count when > 0
    """
    if count > 0:
        return f"🚨 {count}"
    return "—"


def format_action_flags(count: int) -> str:
    """
    Format action flags display.

    Args:
        count: Number of action flags

    Returns:
        Formatted string (e.g., "✅ 3") or empty if 0

    Spec: Page requirements - ✅ icon with count when > 0
    """
    if count > 0:
        return f"✅ {count}"
    return "—"


def format_research_indicator(has_research: bool) -> str:
    """
    Format research document indicator.

    Args:
        has_research: Whether company has research document

    Returns:
        📄 icon if True, empty otherwise

    Spec: Page requirements - 📄 if has_research_doc=true
    """
    if has_research:
        return "📄"
    return "—"


def format_penetration_rate(company_id: str, penetration_map: Dict[str, float]) -> str:
    """
    Format penetration rate display.

    Args:
        company_id: Company ID
        penetration_map: Dictionary mapping company_id to penetration_rate

    Returns:
        Formatted percentage string or "N/A"
    """
    rate = penetration_map.get(company_id)
    if rate is not None:
        return f"{rate:.1f}%"
    return "—"


def format_building_count(count: Optional[int]) -> str:
    """
    Format building count display.

    Args:
        count: Number of buildings

    Returns:
        Formatted count string or "—" if None
    """
    if count is not None:
        return str(int(count))
    return "—"


def get_filtered_count_message(filtered_count: int, total_count: int) -> str:
    """
    Get message showing filtered vs total count.

    Args:
        filtered_count: Number of companies after filtering
        total_count: Total number of companies

    Returns:
        Message string (e.g., "Showing 10 of 50 companies")

    Spec: Page requirements - Display total and filtered count
    """
    if filtered_count == total_count:
        return f"Showing {total_count} companies"
    else:
        return f"Showing {filtered_count} of {total_count} companies"


def prepare_display_dataframe(
    df: pd.DataFrame,
    penetration_map: Dict[str, float]
) -> pd.DataFrame:
    """
    Prepare dataframe for display with formatted columns.

    Args:
        df: Scored companies dataframe (already sorted by score)
        penetration_map: Dictionary mapping company_id to penetration_rate

    Returns:
        DataFrame formatted for display with global and segment ranks
    """
    display_df = df.copy()

    # Add global rank based on current sort order (by augmented_score descending)
    # This gives the overall ranking across all segments
    display_df['Global Rank'] = range(1, len(display_df) + 1)

    # Add display columns
    display_df['Segment Rank'] = display_df['segment_rank'] if 'segment_rank' in display_df.columns else display_df['rank']
    display_df['Company'] = display_df['company_name']
    display_df['Channel'] = display_df['channel_id'] if 'channel_id' in display_df.columns else 'N/A'

    # Add Scoring Path column (Epic 5 requirement)
    display_df['Scoring Path'] = display_df['scoring_path'] if 'scoring_path' in display_df.columns else 'Prospect'

    # Use final_score if available, fallback to augmented_score
    score_col = 'final_score' if 'final_score' in display_df.columns else 'augmented_score'
    display_df['Score'] = display_df[score_col].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")

    # Flags and indicators (may not exist in new schema)
    if 'urgent_flags' in display_df.columns:
        display_df['🚨'] = display_df['urgent_flags'].apply(format_urgent_flags)
    else:
        display_df['🚨'] = "—"

    if 'action_flags' in display_df.columns:
        display_df['✅'] = display_df['action_flags'].apply(format_action_flags)
    else:
        display_df['✅'] = "—"

    if 'has_research_doc' in display_df.columns:
        display_df['📄'] = display_df['has_research_doc'].apply(format_research_indicator)
    else:
        display_df['📄'] = "—"

    display_df['Penetration'] = display_df['company_id'].apply(
        lambda cid: format_penetration_rate(cid, penetration_map)
    )

    # Keep Buildings as numeric for proper sorting
    building_col = 'building_count' if 'building_count' in display_df.columns else 'location_employee_size'
    if building_col in display_df.columns:
        display_df['Buildings'] = display_df[building_col].fillna(0).astype(int)
    else:
        display_df['Buildings'] = 0

    if 'source' in display_df.columns:
        display_df['Source'] = display_df['source'].apply(get_source_badge)
    else:
        display_df['Source'] = "🔵 DataAxle"

    # Select and order columns for display
    # Include company_id as hidden column for row selection mapping
    display_columns = [
        'company_id', 'Global Rank', 'Segment Rank', 'Company', 'Scoring Path', 'Channel', 'Score', '🚨', '✅', '📄',
        'Penetration', 'Buildings', 'Source'
    ]

    # Sort by final score descending by default
    result_df = display_df[display_columns].copy()
    result_df = result_df.sort_values('Score', ascending=False)

    return result_df


def handle_empty_results(df: pd.DataFrame) -> str:
    """
    Get message for empty filter results.

    Args:
        df: Filtered dataframe

    Returns:
        Empty state message

    Spec: Page requirements - Handle empty filtered results
    """
    if len(df) == 0:
        return "No companies match the current filters. Try adjusting your selection."
    return ""


def get_empty_state_message() -> str:
    """
    Get standard empty state message.

    Returns:
        Empty state message string
    """
    return "No companies match the current filters. Try adjusting your selection."


def set_selected_company(company_id: str) -> None:
    """
    Set selected company ID in session state for navigation to detail page.

    Args:
        company_id: Company ID to select

    Spec: Page requirements - Make company name clickable
    """
    st.session_state.selected_company_id = company_id
