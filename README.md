# OpenWorks Sales Intelligence - Streamlit UI

This repository contains the Streamlit UI for the OpenWorks Prospect Intelligence platform.

## Structure

```
.
├── app/
│   ├── streamlit_app.py          # Main entry point
│   ├── data_loader.py             # Data loading with caching
│   ├── quality_gates.py           # Data validation
│   ├── exceptions.py              # Custom exceptions
│   ├── pages/                     # Multi-page app pages
│   │   ├── 0_naics_rankings.py
│   │   ├── 1_ranked_companies.py
│   │   └── 2_company_detail.py
│   └── components/                # Reusable UI components
│       ├── filters.py
│       ├── score_display.py
│       └── heat_map.py
├── data/
│   ├── processed/                 # Epic 1, 2 outputs
│   │   ├── companies.csv          # Required
│   │   ├── buildings.csv          # Required
│   │   └── golden_buildings.csv   # Optional (enhanced buildings)
│   ├── scoring/                   # Epic 4 outputs
│   │   ├── scored_companies_final.csv  # Required
│   │   └── naics_icp_fit_scores.csv    # Required for NAICS Rankings
│   └── config/                    # Configuration files
│       ├── exclusions.yaml
│       └── channels.yaml
└── pyproject.toml                 # Python dependencies

```

## Running Locally

```bash
# Install dependencies (using uv - recommended)
uv pip install -e .

# Or using pip
pip install -e .

# Run the app
streamlit run app/streamlit_app.py
```

## Deploying to Streamlit Cloud

1. Push this repository to GitHub
2. Go to https://share.streamlit.io/
3. Connect your GitHub account
4. Select this repository
5. Set main file path: `app/streamlit_app.py`
6. Deploy!

## Environment Variables

Optional environment variables:

- `OPENWORKS_DATA_DIR`: Path to data directory (default: `./data`)

## Data Requirements

### Required Files (Streamlit will not start without these):

- `data/processed/companies.csv` - Company master list (Epic 1 output)
- `data/processed/buildings.csv` - Building locations (Epic 1 output)
- `data/scoring/scored_companies_final.csv` - Scored companies (Epic 4 output)

### Optional Files (graceful degradation):

- `data/processed/golden_buildings.csv` - Enhanced buildings with HubSpot data
- `data/scoring/naics_icp_fit_scores.csv` - NAICS industry scores
- `data/scoring/company_icp_scores_with_research.csv` - Company research data
- `data/config/exclusions.yaml` - Industry exclusion rules

## Updating Data

To update the data displayed in the app:

1. Re-run the relevant Epic pipelines in the main repository
2. Copy updated CSV files to this repository's `data/` directory
3. Either restart the Streamlit app or use the "Refresh Data" button in the UI

## Architecture

This is a read-only visualization layer. All data processing happens in the main `sales-intelligence-platform` repository:

- Epic 1: Data Collection (companies.csv, buildings.csv)
- Epic 2: Entity Resolution (golden_buildings.csv)
- Epic 3: Research (research documents)
- Epic 4: Scoring (scored_companies_final.csv)
- Epic 5: UI (this repository)
