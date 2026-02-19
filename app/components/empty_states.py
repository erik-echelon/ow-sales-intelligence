"""
Empty States Component for OpenWorks Prospect Intelligence UI

Implements standardized empty state and error handling across all pages.

Epic 5 (OWRKS-5.11)
Spec: §5.5 (Silent Failures), Navigation & Error Handling
"""

import streamlit as st

# Standard messages per spec §5.5
STANDARD_MESSAGES = {
    'empty_companies': "No companies match the current filters. Try adjusting your selection.",
    'no_buildings': "No buildings found for this company.",
    'no_contacts': "No contact history available.",
    'no_research': "Research not available for this company.",
    'churn_pending': "Churn predictions pending.",
    'no_valid_coordinates': "No buildings with valid coordinates match current filters.",
    'no_company_selected': "No company selected. Please select a company from the **Ranked Companies** page and click 'View Company Detail'.",
}


def get_empty_companies_message() -> str:
    """
    Get standard message for no companies matching filters.

    Returns:
        Standard empty companies message

    Spec: §5.5 Standard empty state messages
    """
    return STANDARD_MESSAGES['empty_companies']


def get_no_buildings_message() -> str:
    """
    Get standard message for no buildings.

    Returns:
        Standard no buildings message

    Spec: §5.5 Standard empty state messages
    """
    return STANDARD_MESSAGES['no_buildings']


def get_no_contacts_message() -> str:
    """
    Get standard message for no contacts.

    Returns:
        Standard no contacts message

    Spec: §5.5 Standard empty state messages
    """
    return STANDARD_MESSAGES['no_contacts']


def get_no_research_message() -> str:
    """
    Get standard message for no research.

    Returns:
        Standard no research message

    Spec: §5.5 Standard empty state messages
    """
    return STANDARD_MESSAGES['no_research']


def get_churn_pending_message() -> str:
    """
    Get standard message for pending churn predictions.

    Returns:
        Standard churn pending message

    Spec: §5.5 Standard empty state messages
    """
    return STANDARD_MESSAGES['churn_pending']


def get_no_valid_coordinates_message() -> str:
    """
    Get standard message for no valid coordinates.

    Returns:
        Standard no valid coordinates message

    Spec: §5.5 Standard empty state messages
    """
    return STANDARD_MESSAGES['no_valid_coordinates']


def get_no_company_selected_message() -> str:
    """
    Get standard message when no company is selected.

    Returns:
        Standard no company selected message

    Spec: Navigation requirement - Company Detail empty state
    """
    return STANDARD_MESSAGES['no_company_selected']


def get_company_not_found_message(company_id: str) -> str:
    """
    Get message when company ID is not found.

    Args:
        company_id: Company ID that wasn't found

    Returns:
        Error message with company ID

    Spec: Error handling requirement
    """
    return f"Company ID '{company_id}' not found in data. The company may have been removed or the ID is invalid."


def render_empty_table(message: str) -> None:
    """
    Render standardized empty table state.

    Args:
        message: Message to display to user

    Spec: §5.5 Empty table never renders without explanation
    """
    st.warning(message)


def render_error(title: str, details: str) -> None:
    """
    Render standardized error state.

    Args:
        title: Error title
        details: Error details/explanation

    Spec: Error handling - user-friendly error display
    """
    st.error(f"**{title}**")
    st.error(details)


def render_info(message: str) -> None:
    """
    Render standardized info state.

    Args:
        message: Info message to display

    Spec: Informational messages
    """
    st.info(message)


def handle_missing_data_error(data_type: str, file_path: str = None) -> None:
    """
    Handle and display missing data file errors.

    Args:
        data_type: Type of data that's missing (e.g., "companies", "buildings")
        file_path: Optional file path that's missing

    Spec: §5.5 Missing input artifact handling
    """
    if file_path:
        render_error(
            "Data File Missing",
            f"Required {data_type} data file not found: {file_path}. "
            f"Please ensure all upstream Epic outputs are available."
        )
    else:
        render_error(
            "Data Missing",
            f"Required {data_type} data could not be loaded. "
            f"Please ensure all upstream Epic outputs are available."
        )


def handle_invalid_json_error(file_path: str, error_details: str = None) -> None:
    """
    Handle corrupt/invalid JSON file errors.

    Args:
        file_path: Path to corrupt JSON file
        error_details: Optional error details

    Spec: §5.5 Corrupt research JSON handling
    """
    error_msg = f"Invalid JSON in file: {file_path}"
    if error_details:
        error_msg += f"\n\nDetails: {error_details}"

    render_error("Corrupt Data File", error_msg)


def handle_schema_validation_error(data_type: str, missing_columns: list) -> None:
    """
    Handle schema validation errors.

    Args:
        data_type: Type of data with schema issues
        missing_columns: List of missing column names

    Spec: §5.5 Invalid/corrupt CSV handling
    """
    columns_str = ", ".join(missing_columns)
    render_error(
        "Data Schema Error",
        f"{data_type} data is missing required columns: {columns_str}. "
        f"Please check that upstream Epics have completed successfully."
    )


def render_navigation_link(page_name: str, link_text: str = None) -> None:
    """
    Render a navigation hint to user.

    Args:
        page_name: Name of page to navigate to
        link_text: Optional custom link text

    Spec: Navigation guidance
    """
    if link_text is None:
        link_text = f"Navigate to **{page_name}** using the sidebar."

    st.info(link_text)
