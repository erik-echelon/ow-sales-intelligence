"""
NAICS Industry Rankings Page

Shows aggregated industry-level attractiveness scores, allowing users to identify
the most attractive verticals before drilling down to specific companies.

Epic 5 - New Page 1 per PRD v4.1
"""

import sys
from pathlib import Path

# Add parent directory to path to allow 'app' module imports in Streamlit Cloud
_page_dir = Path(__file__).resolve().parent
_app_dir = _page_dir.parent
_project_root = _app_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from app.data_loader import load_scored_companies
from app.exceptions import DataLoadError
from app.naics_rankings_logic import display_naics_rankings

# Configure page
st.set_page_config(
    page_title="NAICS Rankings - OpenWorks",
    page_icon="📊",
    layout="wide"
)

def main():
    """Main page logic."""
    try:
        # Load scored companies data
        scored_df = load_scored_companies()

        # Display rankings
        display_naics_rankings(scored_df)

    except DataLoadError as e:
        st.error(f"❌ **Data Loading Error**: {e}")
        st.info(
            "Please ensure the scoring pipeline has completed and "
            "`scored_companies_final.csv` exists in `data/scoring/`."
        )
    except Exception as e:
        st.error(f"❌ **Unexpected Error**: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
