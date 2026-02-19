"""
Score Display Component for OpenWorks Prospect Intelligence UI

Implements reusable components for displaying scores with proper formatting
and null handling.

Epic 5 (OWRKS-5.04)
Spec: §2.2 (Score Display Invariants)
"""

import numpy as np
import pandas as pd
import streamlit as st
from typing import Any, Optional


# Null display map for all nullable fields (Spec: §2.1.1)
NULL_DISPLAY_MAP = {
    'employees': 'N/A',
    'revenue': 'N/A',
    'square_footage': 'Unknown',
    'contact_notes': '(No notes)',
    'churn_probability': 'Not predicted',
    'augmented_score': 'Pending',
}


def is_null(value: Any) -> bool:
    """
    Check if a value is null (None, NaN, or empty string).

    Args:
        value: Value to check

    Returns:
        True if value is null, False otherwise
    """
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == '':
        return True
    return False


def format_score(value: Any, max_val: float = 100.0) -> str:
    """
    Format a score value with null handling.

    Args:
        value: Score value (0-max_val)
        max_val: Maximum score value (default: 100.0)

    Returns:
        Formatted string (e.g., "78.5") or "N/A" if null

    Spec: §2.2 Score Display Invariants
    """
    if is_null(value):
        return "N/A"

    try:
        # Convert to float
        score = float(value)

        # Use appropriate precision based on scale
        # For 0-1 scale (e.g., ICP fit score), use 2 decimal places
        # For 0-100 scale, use 1 decimal place
        if max_val <= 1.0:
            return f"{score:.2f}"
        else:
            return f"{score:.1f}"
    except (ValueError, TypeError):
        return "N/A"


def format_percentage(value: Any) -> str:
    """
    Format a percentage value with null handling.

    Args:
        value: Percentage value (0-100)

    Returns:
        Formatted string (e.g., "75.5%") or "N/A" if null

    Spec: §2.2 Score Display Invariants
    """
    if is_null(value):
        return "N/A"

    try:
        percentage = float(value)
        return f"{percentage:.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_confidence(value: Any) -> str:
    """
    Format a confidence value (0-1) as percentage.

    Converts 0-1 scale to 0-100% display.

    Args:
        value: Confidence value (0-1)

    Returns:
        Formatted string (e.g., "85%") or "N/A" if null

    Spec: §2.2 Score Display Invariants
    """
    if is_null(value):
        return "N/A"

    try:
        confidence = float(value)
        percentage = confidence * 100
        # Round to nearest integer for confidence display
        return f"{int(round(percentage))}%"
    except (ValueError, TypeError):
        return "N/A"


def get_score_color(score: Any) -> str:
    """
    Get color code for score badge.

    Args:
        score: Score value (0-100)

    Returns:
        Color string: "green" (≥70), "yellow" (≥40), "red" (<40), or "gray" (null)

    Spec: §2.2 Score Display Invariants
    """
    if is_null(score):
        return "gray"

    try:
        score_val = float(score)
        if score_val >= 70:
            return "green"
        elif score_val >= 40:
            return "yellow"
        else:
            return "red"
    except (ValueError, TypeError):
        return "gray"


def format_nullable_field(value: Any, field_name: str) -> str:
    """
    Format a nullable field using NULL_DISPLAY_MAP.

    Args:
        value: Field value
        field_name: Name of the field

    Returns:
        Formatted string or appropriate null placeholder

    Spec: §2.1.1 Null handling requirements
    """
    # Check for empty string specifically for contact_notes
    if field_name == 'contact_notes' and isinstance(value, str) and value.strip() == '':
        return NULL_DISPLAY_MAP.get(field_name, 'N/A')

    if is_null(value):
        return NULL_DISPLAY_MAP.get(field_name, 'N/A')

    # Return value as string
    return str(value)


def render_score_badge(score: Any, label: str, key: Optional[str] = None) -> None:
    """
    Render a colored score badge.

    Colors based on score:
    - Green: score ≥ 70
    - Yellow: 40 ≤ score < 70
    - Red: score < 40
    - Gray: null/invalid

    Args:
        score: Score value (0-100)
        label: Label for the badge
        key: Optional unique key for the component

    Spec: §2.2 Score Display Invariants
    """
    color = get_score_color(score)
    formatted_score = format_score(score)

    # Color mapping for Streamlit
    color_map = {
        'green': '🟢',
        'yellow': '🟡',
        'red': '🔴',
        'gray': '⚪'
    }

    icon = color_map.get(color, '⚪')

    # Display badge
    st.markdown(f"{icon} **{label}:** {formatted_score}")


def render_score_comparison(
    standard: Any,
    augmented: Any,
    label_standard: str = "Standard Score",
    label_augmented: str = "Augmented Score",
    key: Optional[str] = None
) -> None:
    """
    Render side-by-side score comparison.

    Args:
        standard: Standard score value
        augmented: Augmented score value
        label_standard: Label for standard score
        label_augmented: Label for augmented score
        key: Optional unique key for the component

    Spec: §2.2 Score Display Invariants
    """
    col1, col2 = st.columns(2)

    with col1:
        st.metric(label_standard, format_score(standard))

    with col2:
        # Calculate delta if both scores are valid
        delta = None
        if not is_null(standard) and not is_null(augmented):
            try:
                delta_val = float(augmented) - float(standard)
                delta = f"{delta_val:+.1f}"
            except (ValueError, TypeError):
                pass

        st.metric(label_augmented, format_score(augmented), delta=delta)


def format_score_with_confidence(score: Any, confidence: Any) -> str:
    """
    Format score with confidence indicator.

    Args:
        score: Score value
        confidence: Confidence value (0-1)

    Returns:
        Formatted string like "85.5 (90% confidence)"
    """
    score_str = format_score(score)
    confidence_str = format_confidence(confidence)

    if score_str == "N/A":
        return "N/A"

    if confidence_str == "N/A":
        return score_str

    return f"{score_str} ({confidence_str} confidence)"


def render_score_breakdown(
    component_scores: dict,
    title: str = "Score Components",
    key: Optional[str] = None
) -> None:
    """
    Render a breakdown of score components.

    Args:
        component_scores: Dictionary of component names to scores
        title: Title for the breakdown section
        key: Optional unique key for the component

    Spec: §2.2 Score Display Invariants
    """
    st.subheader(title)

    for component_name, score in component_scores.items():
        color = get_score_color(score)
        formatted_score = format_score(score)

        # Display component with color badge
        color_map = {
            'green': '🟢',
            'yellow': '🟡',
            'red': '🔴',
            'gray': '⚪'
        }
        icon = color_map.get(color, '⚪')

        # Format component name nicely
        display_name = component_name.replace('_', ' ').title()

        st.markdown(f"{icon} **{display_name}:** {formatted_score}")


def format_icp_fit_score(score: Any, basis: str = None) -> str:
    """
    Format ICP fit score with basis indicator.

    Args:
        score: ICP fit score (0-1)
        basis: ICP fit basis (calculated/no_data/partial)

    Returns:
        Formatted string like "0.85 (calculated)" or "N/A (no data)"
    """
    if is_null(score):
        if basis == 'no_data':
            return "N/A (no data)"
        elif basis == 'partial':
            return "N/A (partial data)"
        else:
            return "N/A"

    try:
        score_val = float(score)
        score_str = f"{score_val:.2f}"

        if basis:
            basis_display = basis.replace('_', ' ').title()
            return f"{score_str} ({basis_display})"
        else:
            return score_str
    except (ValueError, TypeError):
        return "N/A"


def format_large_number(value: Any, field_name: str = None) -> str:
    """
    Format large numbers with thousand separators.

    Args:
        value: Numeric value
        field_name: Optional field name for null handling

    Returns:
        Formatted string like "1,500" or null placeholder
    """
    if is_null(value):
        if field_name:
            return NULL_DISPLAY_MAP.get(field_name, 'N/A')
        return "N/A"

    try:
        num = float(value)
        # Format with thousand separators, no decimal places for large numbers
        if num == int(num):
            return f"{int(num):,}"
        else:
            return f"{num:,.1f}"
    except (ValueError, TypeError):
        if field_name:
            return NULL_DISPLAY_MAP.get(field_name, 'N/A')
        return "N/A"
