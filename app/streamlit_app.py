#!/usr/bin/env python3
"""
OpenWorks Prospect Intelligence - Streamlit UI Entry Point

Epic 5 main application that provides interactive visualization of the
complete prospect intelligence pipeline output.

Usage:
    streamlit run app/streamlit_app.py
"""

import logging
from pathlib import Path

import streamlit as st

from app.data_loader import (
    get_data_dir,
    load_buildings,
    load_companies,
    load_scored_companies,
)
from app.exceptions import DataLoadError, DataQualityError, SchemaValidationError
from app.quality_gates import run_startup_validation

logger = logging.getLogger(__name__)

# Configure page
st.set_page_config(
    page_title="OpenWorks Prospect Intelligence",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for filter persistence across pages
# Spec requirement: §2.1.3 Filter State Consistency
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

# ============================================================================
# DATA LOADING & QUALITY GATE VALIDATION (Spec: §1.1-1.7, §4.5)
# ============================================================================

def run_data_validation():
    """
    Load data and run quality gates at application startup.

    Stores results in session state to avoid re-running on page navigation.
    Displays blocking errors or non-blocking warnings as appropriate.

    Spec: §4.5 Data Quality Gates
    """
    if 'validation_complete' not in st.session_state:
        st.session_state.validation_complete = False

    if st.session_state.validation_complete:
        return  # Already validated this session

    try:
        # Load required data files (Spec: §1.1)
        with st.spinner("Loading data files..."):
            scored_df = load_scored_companies()
            companies_df = load_companies()
            buildings_df = load_buildings()
            data_dir = get_data_dir()

        # Run all quality gates (blocking + non-blocking)
        with st.spinner("Running quality gates..."):
            validation_results = run_startup_validation(
                scored_df, companies_df, buildings_df, data_dir
            )

        # Store validation results in session state
        st.session_state.validation_results = validation_results
        st.session_state.validation_complete = True

        # Display non-blocking warnings if any gates failed
        non_blocking = validation_results.get('non_blocking_gates', {})

        # Entity resolution orphan rate ≥10% (Spec: §2.3)
        er_result = non_blocking.get('entity_resolution', {})
        if not er_result.get('passed', True):
            orphan_rate = er_result.get('orphan_rate', 0)
            st.warning(
                f"⚠️ **Entity Resolution Warning**: {orphan_rate:.1%} of HubSpot records "
                f"could not be matched (threshold: <10%). Review entity_resolution_log.csv "
                f"to improve matching rules."
            )

        # Coordinate coverage <80% (Spec: §2.1.2)
        coord_result = non_blocking.get('coordinate_coverage', {})
        if not coord_result.get('passed', True):
            coverage = coord_result.get('coverage', 0)
            st.warning(
                f"⚠️ **Coordinate Coverage Warning**: Only {coverage:.1%} of buildings have "
                f"valid coordinates (threshold: ≥80%). Heat map may be incomplete."
            )

        # Research coverage check removed - no longer using deep research (Google Deep Research deprecated)

        logger.info("✓ Data loading and validation complete")

    except DataQualityError as e:
        # BLOCKING error - halt application
        st.error(f"🚨 **BLOCKING DATA QUALITY ERROR**\n\n{e}")
        st.error(
            "**The application cannot start due to critical data quality issues.** "
            "Please fix the upstream data and regenerate artifacts before launching the UI."
        )
        st.stop()  # Halt execution

    except (DataLoadError, SchemaValidationError) as e:
        # BLOCKING error - required file missing or invalid
        st.error(f"🚨 **DATA LOADING ERROR**\n\n{e}")
        st.error(
            "**Required data files are missing or invalid.** "
            "Ensure all Epics 1-4 have been run successfully and output files exist."
        )
        st.stop()  # Halt execution

    except Exception as e:
        # Unexpected error
        st.error(f"🚨 **UNEXPECTED ERROR**\n\n{e}")
        logger.exception("Unexpected error during data validation")
        st.stop()  # Halt execution

# Run validation (only executes once per session)
run_data_validation()

# Main landing page
st.title("🏢 OpenWorks Prospect Intelligence Demo")

st.markdown("""
## Welcome to the Prospect Intelligence Platform

This application provides interactive access to scored and prioritized prospects
from the complete data pipeline (Epics 1-5).

### Available Views

Use the sidebar navigation to access:

0. **NAICS Rankings** - View industry-level attractiveness scores with AI-generated ICP fit justifications, market size data, and profitability metrics for each industry vertical
1. **Ranked Companies** - Browse scored companies with dual-path scoring (Customer Expansion vs New Prospect) including filters and sortable columns
2. **Company Detail** - Deep dive into individual company intelligence with complete scoring breakdown, HQ information, and firmographic data

### Quick Start

1. Start with **NAICS Rankings** to identify the most attractive industry verticals based on ICP fit, market size, profitability, and customer health metrics
2. Navigate to **Ranked Companies** to see prospects ranked by final score - filter by NAICS code, scoring path, or other criteria
3. Click any company row to view detailed scoring breakdown on the **Company Detail** page
4. Use filters in the sidebar to narrow down by NAICS, channel, source, or scoring path

### Current Status

- ✅ **AI-driven NAICS ICP scoring**: Claude AI evaluates each industry's fit with OpenWorks' ideal customer profile with detailed justifications
- ✅ **Company-level web research**: Automated research for qualified prospects (5+ locations, $10M+ revenue) identifying growth signals and outsourcing likelihood
- ✅ **Dual-path scoring**: Customer Expansion and New Prospect scoring paths with different factor weightings
- ✅ **NAICS-first approach**: Industry attractiveness scores guide company-level prioritization
- ✅ **Entity resolution**: LLM-based matching between DataAxle prospects (6,288 companies) and HubSpot customers (1,272 matched)
- ✅ **Comprehensive data integration**: Market size (nationwide DataAxle counts), customer health metrics (churn + support tickets), and profitability data

---

**Data Sources:** Epic 1 (Data Collection), Epic 2 (Entity Resolution),
Epic 3 (Research), Epic 4 (Scoring), Epic 5 (UI Updates)
""")

# Display current filter state (for debugging/validation)
if st.checkbox("Show active filters (debug)"):
    st.json({
        "naics_filter": st.session_state.naics_filter,
        "source_filter": st.session_state.source_filter,
        "channel_filter": st.session_state.channel_filter,
        "research_filter": st.session_state.research_filter,
        "served_filter": st.session_state.served_filter,
    })
