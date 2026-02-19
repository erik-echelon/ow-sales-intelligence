"""
Research Document Viewer Component for OpenWorks Prospect Intelligence UI

Implements rendering of research documents with markdown formatting and
URGENT/ACTION flag highlighting.

Epic 5 (OWRKS-5.06)
Spec: §2.6 (Research Document Display Invariants), Appendix D
"""

import re
from typing import Dict, Optional, Tuple

import streamlit as st


def highlight_urgent_flags(doc: str) -> str:
    """
    Highlight URGENT flags with red emoji.

    Converts "**URGENT:**" to "🚨 **URGENT:**"

    Args:
        doc: Research document text

    Returns:
        Document with highlighted URGENT flags

    Spec: §2.6 Research Document Display Invariants
    """
    # Replace **URGENT:** with emoji version
    highlighted = re.sub(
        r'\*\*URGENT:\*\*',
        '🚨 **URGENT:**',
        doc
    )

    return highlighted


def highlight_action_flags(doc: str) -> str:
    """
    Highlight ACTION flags with green emoji.

    Converts "**ACTION:**" to "✅ **ACTION:**"

    Args:
        doc: Research document text

    Returns:
        Document with highlighted ACTION flags

    Spec: §2.6 Research Document Display Invariants
    """
    # Replace **ACTION:** with emoji version
    highlighted = re.sub(
        r'\*\*ACTION:\*\*',
        '✅ **ACTION:**',
        doc
    )

    return highlighted


def count_urgent_flags(doc: str) -> int:
    """
    Count URGENT flags in document.

    Matches the scoring pipeline's counting method: case-sensitive count of "URGENT".

    Args:
        doc: Research document text

    Returns:
        Count of URGENT flags

    Spec: §2.6 Flag counts match
    """
    # Use same counting method as scoring pipeline (src/scoring/document_signals.py)
    return doc.count("URGENT")


def count_action_flags(doc: str) -> int:
    """
    Count ACTION flags in document.

    Matches the scoring pipeline's counting method: case-sensitive count of "ACTION".

    Args:
        doc: Research document text

    Returns:
        Count of ACTION flags

    Spec: §2.6 Flag counts match
    """
    # Use same counting method as scoring pipeline (src/scoring/document_signals.py)
    return doc.count("ACTION")


def validate_flag_counts(doc: str, displayed_urgent: int, displayed_action: int) -> None:
    """
    Validate that flag counts match actual flags in document.

    Args:
        doc: Research document text
        displayed_urgent: Displayed urgent flag count
        displayed_action: Displayed action flag count

    Raises:
        AssertionError: If counts don't match

    Spec: §2.6 Flag counts match
    """
    actual_urgent = doc.count('URGENT')
    actual_action = doc.count('ACTION')

    assert actual_urgent == displayed_urgent, (
        f"URGENT count mismatch: doc has {actual_urgent}, displayed {displayed_urgent}"
    )

    assert actual_action == displayed_action, (
        f"ACTION count mismatch: doc has {actual_action}, displayed {displayed_action}"
    )


def format_research_document(doc: str) -> str:
    """
    Format research document with all highlighting applied.

    Applies:
    - URGENT flag highlighting (🚨)
    - ACTION flag highlighting (✅)
    - Preserves markdown formatting
    - Preserves source citations

    Args:
        doc: Raw research document text

    Returns:
        Formatted document ready for display

    Spec: §2.6 Research Document Display Invariants, Appendix D
    """
    formatted = doc

    # Apply URGENT highlighting
    formatted = highlight_urgent_flags(formatted)

    # Apply ACTION highlighting
    formatted = highlight_action_flags(formatted)

    return formatted


def get_document_summary(doc: str) -> Dict[str, any]:
    """
    Get summary statistics from research document.

    Args:
        doc: Research document text

    Returns:
        Dictionary with summary statistics:
        - word_count: Number of words
        - urgent_flags: Count of URGENT flags
        - action_flags: Count of ACTION flags
        - has_content: Whether document has meaningful content

    Spec: §1.2 Research Document Files
    """
    # Count words
    words = doc.split()
    word_count = len(words)

    # Count flags
    urgent_flags = count_urgent_flags(doc)
    action_flags = count_action_flags(doc)

    # Check if has content
    has_content = word_count > 0

    return {
        'word_count': word_count,
        'urgent_flags': urgent_flags,
        'action_flags': action_flags,
        'has_content': has_content
    }


def truncate_document(doc: str, max_words: int = 5000) -> Tuple[str, bool]:
    """
    Truncate document if it exceeds maximum word count.

    Args:
        doc: Research document text
        max_words: Maximum word count before truncation

    Returns:
        Tuple of (truncated_doc, was_truncated)

    Spec: §6.2 Edge Cases - Research document > 5,000 words
    """
    words = doc.split()

    if len(words) <= max_words:
        return doc, False

    # Truncate to max_words
    truncated_words = words[:max_words]
    truncated_doc = ' '.join(truncated_words) + '\n\n...\n\n*(Document truncated for display. Full content available.)*'

    return truncated_doc, True


def extract_company_name(doc_data: Dict) -> str:
    """
    Extract company name from research document data.

    Args:
        doc_data: Research document dictionary

    Returns:
        Company name or "Unknown Company" if missing

    Spec: §1.2 Research Document Files
    """
    return doc_data.get('company_name', 'Unknown Company')


def render_research_document(
    research_doc: str,
    company_name: str,
    show_summary: bool = True,
    max_words: int = 5000
) -> None:
    """
    Render research document in Streamlit with formatting.

    Displays:
    - Company name header
    - Document summary (optional)
    - Formatted research content with markdown
    - URGENT/ACTION flags highlighted
    - Truncation notice if applicable

    Args:
        research_doc: Research document text
        company_name: Name of the company
        show_summary: Whether to show document summary stats
        max_words: Maximum words before truncation

    Spec: §2.6 Research Document Display Invariants, Appendix D
    """
    st.subheader(f"📄 Intelligence Report: {company_name}")

    # Get document summary
    summary = get_document_summary(research_doc)

    # Show summary if requested
    if show_summary:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Word Count", f"{summary['word_count']:,}")
        with col2:
            st.metric("🚨 Urgent Flags", summary['urgent_flags'])
        with col3:
            st.metric("✅ Action Flags", summary['action_flags'])

        st.markdown("---")

    # Truncate if needed
    display_doc, was_truncated = truncate_document(research_doc, max_words)

    if was_truncated:
        st.warning(
            f"⚠️ Document truncated to {max_words:,} words for display. "
            f"Original length: {summary['word_count']:,} words."
        )

    # Format document
    formatted_doc = format_research_document(display_doc)

    # Render with markdown
    st.markdown(formatted_doc)


def render_research_summary_card(
    company_id: str,
    company_name: str,
    has_research: bool,
    urgent_flags: int = 0,
    action_flags: int = 0
) -> None:
    """
    Render compact research summary card.

    Useful for list views where full document is too large.

    Args:
        company_id: Company ID
        company_name: Company name
        has_research: Whether company has research document
        urgent_flags: Count of urgent flags in document
        action_flags: Count of action flags in document

    Spec: Page 1 requirements - Research indicators in table
    """
    if not has_research:
        st.info(f"No research available for {company_name}")
        return

    st.markdown(f"**{company_name}**")

    col1, col2 = st.columns(2)

    with col1:
        if urgent_flags > 0:
            st.markdown(f"🚨 **{urgent_flags} Urgent** finding(s)")

    with col2:
        if action_flags > 0:
            st.markdown(f"✅ **{action_flags} Action** item(s)")

    st.markdown(f"[View Full Report](#) *(Navigate to Company Detail page)*")


def check_research_document_validity(doc_data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Check if research document data is valid.

    Args:
        doc_data: Research document dictionary

    Returns:
        Tuple of (is_valid, error_message)

    Spec: §1.2 Research Document Files
    """
    # Check required fields
    if 'research_document' not in doc_data:
        return False, "Missing 'research_document' field"

    if 'status' not in doc_data:
        return False, "Missing 'status' field"

    # Check status
    if doc_data['status'] != 'completed':
        return False, f"Status is '{doc_data['status']}', expected 'completed'"

    # Check minimum length
    doc_text = doc_data['research_document']
    if len(doc_text) < 500:
        return False, f"Document too short: {len(doc_text)} chars (minimum 500)"

    # Check document_stats if present
    if 'document_stats' in doc_data:
        stats = doc_data['document_stats']
        if 'word_count' in stats and stats['word_count'] < 100:
            return False, f"Word count too low: {stats['word_count']} (minimum 100)"

    return True, None
