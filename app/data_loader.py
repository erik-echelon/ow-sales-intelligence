"""
Data Loading Module for OpenWorks Prospect Intelligence UI

Centralized data loading with schema validation, caching, and environment
variable support.

Epic 5 (OWRKS-5.02)
Spec: §1.1-1.7 (Preconditions), §4.3 (Caching)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import yaml

from app.exceptions import DataLoadError, SchemaValidationError

logger = logging.getLogger(__name__)

# Cache TTL: 300 seconds (5 minutes)
CACHE_TTL = 300


def get_data_dir() -> Path:
    """
    Get data directory from environment variable or default.

    Returns:
        Path to data directory

    Spec: §1.4 Environment Variables
    """
    data_dir_str = os.getenv('OPENWORKS_DATA_DIR', './data')
    data_dir = Path(data_dir_str)

    if not data_dir.exists():
        raise DataLoadError(
            f"Data directory not found: {data_dir}. "
            f"Set OPENWORKS_DATA_DIR environment variable or ensure ./data exists."
        )

    return data_dir


@st.cache_data(ttl=CACHE_TTL)
def load_exclusions_config() -> Dict[str, Any]:
    """
    Load exclusions.yaml configuration for industry filtering.

    Returns:
        Dictionary with exclusions configuration

    Raises:
        DataLoadError: If file not found or invalid YAML
    """
    data_dir = get_data_dir()
    file_path = data_dir / "config" / "exclusions.yaml"

    if not file_path.exists():
        # Exclusions are optional - return empty config if not found
        logger.info("exclusions.yaml not found - no industry exclusions will be applied")
        return {}

    try:
        with open(file_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise DataLoadError(f"Invalid YAML in {file_path}: {e}")
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    logger.info(f"Loaded exclusions config from {file_path}")
    return config or {}


def _get_excluded_naics_codes() -> List[str]:
    """
    Get list of NAICS codes to exclude based on exclusions config.

    Returns:
        List of 8-digit NAICS codes to exclude
    """
    try:
        config = load_exclusions_config()
    except Exception as e:
        logger.warning(f"Failed to load exclusions config: {e}. No exclusions will be applied.")
        return []

    excluded_codes = []

    # Public education exclusions
    if config.get('public_education', {}).get('enabled', False):
        public_ed_codes = config['public_education'].get('naics_codes', [])
        excluded_codes.extend(public_ed_codes)
        logger.info(f"Excluding {len(public_ed_codes)} public education NAICS codes: {public_ed_codes}")

    # Future: Add other exclusion categories here
    # Example:
    # if config.get('government_facilities', {}).get('enabled', False):
    #     gov_codes = config['government_facilities'].get('naics_codes', [])
    #     excluded_codes.extend(gov_codes)

    return excluded_codes


def validate_schema(df: pd.DataFrame, required_columns: List[str], file_name: str) -> None:
    """
    Validate that DataFrame contains all required columns.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        file_name: File name for error message

    Raises:
        SchemaValidationError: If required columns are missing

    Spec: §1.7 Schema Requirements
    """
    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        raise SchemaValidationError(
            f"{file_name} missing required columns: {sorted(missing_columns)}. "
            f"Found columns: {sorted(df.columns)}"
        )


@st.cache_data(ttl=CACHE_TTL)
def load_companies() -> pd.DataFrame:
    """
    Load companies.csv with schema validation.

    Returns:
        DataFrame with company data

    Raises:
        DataLoadError: If file not found
        SchemaValidationError: If required columns missing

    Spec: §1.1 Required Files
    """
    data_dir = get_data_dir()
    file_path = data_dir / "processed" / "companies.csv"

    if not file_path.exists():
        raise DataLoadError(
            f"Required file not found: {file_path}\n"
            f"Run Epic 1 pipeline to generate companies.csv"
        )

    try:
        df = pd.read_csv(file_path, dtype=str)
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    # Validate schema (Spec: §1.1)
    # Note: 'source' comes from scored_companies.csv (Epic 4), not companies.csv (Epic 1)
    # Note: Epic 1 v4 outputs use 'building_count_estimate' instead of 'building_count'
    required_columns = [
        'company_id', 'name', 'primary_naics',
        'hq_latitude', 'hq_longitude'
    ]
    validate_schema(df, required_columns, "companies.csv")

    # Normalize building_count column name for backward compatibility
    if 'building_count_estimate' in df.columns and 'building_count' not in df.columns:
        df['building_count'] = df['building_count_estimate']

    logger.info(f"Loaded {len(df)} companies from {file_path}")
    return df


@st.cache_data(ttl=CACHE_TTL)
def load_buildings() -> pd.DataFrame:
    """
    Load buildings from golden_buildings.csv (Epic 2 output) which includes both
    DataAxle and HubSpot buildings with source and served status.

    Falls back to buildings.csv (Epic 1 output) if golden_buildings.csv not found.

    Returns:
        DataFrame with building data

    Raises:
        DataLoadError: If file not found
        SchemaValidationError: If required columns missing

    Spec: §1.1 Required Files, Epic 2 golden buildings
    """
    data_dir = get_data_dir()

    # Try golden_buildings.csv first (Epic 2 output with source/served info)
    golden_path = data_dir / "processed" / "golden_buildings.csv"
    file_path = data_dir / "processed" / "buildings.csv"

    if golden_path.exists():
        # Use golden buildings which includes HubSpot (served) buildings
        try:
            df = pd.read_csv(golden_path, dtype={'company_id': str, 'building_id': str})
            logger.info(f"Loaded {len(df)} buildings from golden_buildings.csv (includes served buildings)")
            file_path = golden_path  # For error messages
        except Exception as e:
            raise DataLoadError(f"Failed to read {golden_path}: {e}")
    elif file_path.exists():
        # Fallback to buildings.csv (Epic 1 output, no served buildings)
        logger.warning("golden_buildings.csv not found, using buildings.csv (no served buildings)")
        try:
            df = pd.read_csv(file_path, dtype={'company_id': str, 'building_id': str})
        except Exception as e:
            raise DataLoadError(f"Failed to read {file_path}: {e}")
    else:
        raise DataLoadError(
            f"Required file not found: {file_path}\n"
            f"Run Epic 2 pipeline to generate golden_buildings.csv"
        )

    # Validate schema (Spec: §1.1)
    required_columns = [
        'building_id', 'company_id',
        'latitude', 'longitude'
    ]
    validate_schema(df, required_columns, "buildings")

    # Add missing columns if not present (for backwards compatibility)
    if 'source' not in df.columns:
        # Fallback for buildings.csv without source
        logger.warning("No source column, defaulting all buildings to dataaxle (unserved)")
        df['source'] = 'dataaxle'

    # Fill any null sources
    df['source'] = df['source'].fillna('dataaxle')

    # Add is_served column based on source
    if 'is_served' not in df.columns:
        # Derive is_served from source: manual/hubspot = served, dataaxle = not served
        df['is_served'] = df['source'].apply(
            lambda x: x.lower() in ['manual', 'hubspot'] if pd.notna(x) else False
        )
        logger.info(f"Derived is_served: {df['is_served'].sum()} served, {(~df['is_served']).sum()} unserved")

    if 'square_footage' not in df.columns:
        # Use square_footage_code if available, otherwise set to None
        if 'square_footage_code' in df.columns:
            df['square_footage'] = df['square_footage_code']
        else:
            df['square_footage'] = None

    # Filter out buildings for companies that don't exist in companies.csv
    # This makes the UI resilient to upstream data issues
    initial_count = len(df)
    df = _filter_orphaned_buildings(df)
    filtered_count = initial_count - len(df)

    if filtered_count > 0:
        logger.warning(
            f"Filtered {filtered_count} buildings from buildings.csv for companies that don't exist in companies.csv. "
            f"This indicates an upstream data issue - check Epic 1 and Epic 2 pipelines."
        )

    logger.info(f"Loaded {len(df)} buildings from {file_path}")
    return df


@st.cache_data(ttl=CACHE_TTL)
def load_scored_companies() -> pd.DataFrame:
    """
    Load scored_companies_final.csv (or fallback to scored_companies.csv) with schema validation.

    Filters out any company_ids that don't exist in companies.csv to ensure
    join integrity for the UI (resilient to upstream data issues).

    Returns:
        DataFrame with scored company data

    Raises:
        DataLoadError: If file not found
        SchemaValidationError: If required columns missing

    Spec: §1.1 Required Files
    """
    data_dir = get_data_dir()

    # Try to load scored_companies_final.csv first (new dual-path scoring)
    final_path = data_dir / "scoring" / "scored_companies_final.csv"
    file_path = data_dir / "scoring" / "scored_companies.csv"

    if final_path.exists():
        file_path = final_path
    elif not file_path.exists():
        raise DataLoadError(
            f"Required file not found: {file_path} or {final_path}\n"
            f"Run Epic 4 scoring pipeline to generate scored_companies.csv"
        )

    try:
        # Read with company_id as string to preserve leading zeros and ensure join integrity
        df = pd.read_csv(file_path, dtype={'company_id': str})
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    # Validate schema (Spec: §1.1)
    # Support both old and new scoring formats
    # Old format: standard_score, augmented_score, segment_rank, etc.
    # New format: final_score, naics_attractiveness_score, company_opportunity_score, rank, scoring_path

    # Core columns that should exist in both formats
    core_required = ['company_id', 'company_name', 'primary_naics']

    # Check if this is the new dual-path scoring format
    is_new_format = 'final_score' in df.columns and 'scoring_path' in df.columns

    if is_new_format:
        # New dual-path scoring columns
        required_columns = core_required + [
            'final_score', 'naics_attractiveness_score', 'company_opportunity_score',
            'scoring_path', 'is_customer'
        ]
    else:
        # Old scoring columns
        required_columns = core_required + [
            'source', 'channel_id', 'standard_score', 'augmented_score',
            'augmented_confidence', 'segment_rank', 'icp_fit_score',
            'urgent_flags', 'action_flags', 'has_research_doc'
        ]

    validate_schema(df, required_columns, file_path.name)

    # Filter out company_ids that don't exist in companies.csv
    # This makes the UI resilient to upstream data issues
    initial_count = len(df)
    df = _filter_orphaned_companies(df)
    filtered_count = initial_count - len(df)

    if filtered_count > 0:
        logger.warning(
            f"Filtered {filtered_count} companies from scored_companies.csv that don't exist in companies.csv. "
            f"This indicates an upstream data issue - check Epic 1 and Epic 4 pipelines."
        )

    # Apply industry exclusions (e.g., public education)
    initial_count = len(df)
    df = _apply_industry_exclusions(df)
    excluded_count = initial_count - len(df)

    if excluded_count > 0:
        logger.info(
            f"Excluded {excluded_count} companies based on industry exclusions config "
            f"({len(df)} companies remaining)"
        )

    # Always re-rank within segments to ensure contiguous ranks
    # This is needed for both filtered data and new scoring format (which uses global ranks)
    df = _rerank_within_segments(df)

    # Merge building_count from companies.csv (needed for UI display)
    df = _merge_building_count(df)

    logger.info(f"Loaded {len(df)} scored companies from {file_path}")
    return df


def _merge_building_count(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge building_count from companies.csv into scored companies DataFrame.

    Args:
        scored_df: Scored companies DataFrame

    Returns:
        DataFrame with building_count column added
    """
    # Load companies.csv to get building_count
    data_dir = get_data_dir()
    companies_path = data_dir / "processed" / "companies.csv"

    if not companies_path.exists():
        logger.warning("companies.csv not found - cannot add building_count")
        scored_df['building_count'] = None
        return scored_df

    try:
        companies_df = pd.read_csv(companies_path, dtype={'company_id': str})
    except Exception as e:
        logger.warning(f"Failed to read companies.csv for building_count: {e}")
        scored_df['building_count'] = None
        return scored_df

    if 'building_count' not in companies_df.columns:
        logger.warning("companies.csv missing building_count column")
        scored_df['building_count'] = None
        return scored_df

    # Merge building_count
    scored_df = scored_df.merge(
        companies_df[['company_id', 'building_count']],
        on='company_id',
        how='left'
    )

    # Fill any missing values with 0
    scored_df['building_count'] = scored_df['building_count'].fillna(0).astype(int)

    return scored_df


def _rerank_within_segments(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Re-rank companies within each NAICS segment to ensure contiguous segment_rank values.

    After filtering out orphaned companies, segment ranks may have gaps (e.g., [1, 2, 3, 7, 11, ...]).
    This function re-assigns ranks to be contiguous (e.g., [1, 2, 3, 4, 5, ...]) within each segment,
    preserving the original score-based ordering.

    Args:
        scored_df: Scored companies DataFrame (after filtering)

    Returns:
        DataFrame with re-ranked segment_rank values (contiguous within each segment)
    """
    if len(scored_df) == 0:
        return scored_df

    # Use new format columns if available, otherwise old format
    score_col = 'final_score' if 'final_score' in scored_df.columns else 'augmented_score'
    rank_col = 'rank' if 'rank' in scored_df.columns else 'segment_rank'

    # Sort by primary_naics, score (descending), and original rank (ascending)
    # This ensures we preserve the original score-based ranking within each segment
    # Using rank as a tie-breaker ensures stable sorting when scores are equal
    scored_df = scored_df.sort_values(
        ['primary_naics', score_col, rank_col],
        ascending=[True, False, True]
    ).copy()

    # Re-assign rank within each NAICS group
    def assign_contiguous_rank(group):
        """Assign contiguous ranks 1, 2, 3, ... within a group."""
        group = group.copy()
        group[rank_col] = range(1, len(group) + 1)
        return group

    scored_df = scored_df.groupby('primary_naics', group_keys=False).apply(assign_contiguous_rank, include_groups=True)

    # Sort the DataFrame by NAICS and rank to ensure row order matches rank order
    # This is critical for UI validation which expects ranks to match score order in the DataFrame
    scored_df = scored_df.sort_values(['primary_naics', rank_col], ascending=[True, True]).reset_index(drop=True)

    logger.info(
        f"Re-ranked {len(scored_df)} companies across {scored_df['primary_naics'].nunique()} segments "
        f"to ensure contiguous segment_rank values"
    )

    return scored_df


def _filter_orphaned_buildings(buildings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter buildings to only include those for companies that exist in companies.csv.

    Args:
        buildings_df: Buildings DataFrame

    Returns:
        Filtered DataFrame with only buildings for valid company_ids
    """
    # Load companies.csv to get valid company_ids
    data_dir = get_data_dir()
    companies_path = data_dir / "processed" / "companies.csv"

    if not companies_path.exists():
        # If companies.csv doesn't exist, return buildings_df as-is
        # The main data loader will catch this later
        return buildings_df

    try:
        companies_df = pd.read_csv(companies_path, dtype=str)
    except Exception as e:
        logger.warning(f"Failed to read companies.csv for filtering buildings: {e}")
        return buildings_df

    if 'company_id' not in companies_df.columns:
        logger.warning("companies.csv missing company_id column - cannot filter buildings")
        return buildings_df

    # Get valid company_ids (already strings from load_companies)
    valid_ids = set(companies_df['company_id'])
    building_company_ids = buildings_df['company_id']

    # Identify orphaned buildings
    orphaned_mask = ~building_company_ids.isin(valid_ids)
    orphaned_count = orphaned_mask.sum()

    if orphaned_count > 0:
        orphaned_company_sample = buildings_df[orphaned_mask]['company_id'].unique()[:5].tolist()
        logger.warning(
            f"Found {orphaned_count} buildings for {len(buildings_df[orphaned_mask]['company_id'].unique())} "
            f"company_ids not in companies.csv. Sample company_ids: {orphaned_company_sample}"
        )

        # Filter to only buildings for valid companies
        filtered_df = buildings_df[~orphaned_mask].copy()
        return filtered_df

    return buildings_df


def _apply_industry_exclusions(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter out companies based on industry exclusions configuration.

    Applies exclusions defined in data/config/exclusions.yaml based on primary_naics codes.
    This allows filtering out unwanted industries (e.g., public education) from the UI
    without rerunning the entire data pipeline.

    Args:
        scored_df: Scored companies DataFrame

    Returns:
        Filtered DataFrame with excluded industries removed
    """
    if len(scored_df) == 0:
        return scored_df

    # Get list of NAICS codes to exclude (as strings from YAML)
    excluded_codes_str = _get_excluded_naics_codes()

    if not excluded_codes_str:
        # No exclusions configured
        return scored_df

    # Convert excluded codes to integers for comparison
    # (primary_naics column is stored as int64 in the CSV)
    excluded_codes = [int(code) for code in excluded_codes_str]

    # Filter out companies with excluded NAICS codes
    initial_count = len(scored_df)
    mask = ~scored_df['primary_naics'].isin(excluded_codes)
    filtered_df = scored_df[mask].copy()

    excluded_count = initial_count - len(filtered_df)
    if excluded_count > 0:
        # Log sample of excluded companies for debugging
        excluded_sample = scored_df[~mask][['company_name', 'primary_naics']].head(5)
        logger.debug(
            f"Excluded {excluded_count} companies with NAICS codes {excluded_codes}. "
            f"Sample: {excluded_sample.to_dict('records')}"
        )

    return filtered_df


def _filter_orphaned_companies(scored_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter scored companies to only include those that exist in companies.csv.

    Args:
        scored_df: Scored companies DataFrame

    Returns:
        Filtered DataFrame with only valid company_ids
    """
    # Load companies.csv to get valid company_ids
    data_dir = get_data_dir()
    companies_path = data_dir / "processed" / "companies.csv"

    if not companies_path.exists():
        # If companies.csv doesn't exist, return scored_df as-is
        # The main data loader will catch this later
        return scored_df

    try:
        companies_df = pd.read_csv(companies_path, dtype=str)
    except Exception as e:
        logger.warning(f"Failed to read companies.csv for filtering: {e}")
        return scored_df

    if 'company_id' not in companies_df.columns:
        logger.warning("companies.csv missing company_id column - cannot filter")
        return scored_df

    # Get valid company_ids (already strings from load_companies)
    valid_ids = set(companies_df['company_id'])
    scored_ids = scored_df['company_id']

    # Identify orphaned companies
    orphaned_mask = ~scored_ids.isin(valid_ids)
    orphaned_count = orphaned_mask.sum()

    if orphaned_count > 0:
        orphaned_sample = scored_df[orphaned_mask]['company_id'].head(10).tolist()
        logger.warning(
            f"Found {orphaned_count} company_ids in scored_companies.csv not in companies.csv. "
            f"Sample: {orphaned_sample[:5]}"
        )

        # Filter to only valid companies
        filtered_df = scored_df[~orphaned_mask].copy()
        return filtered_df

    return scored_df


@st.cache_data(ttl=CACHE_TTL)
def load_penetration_by_company() -> pd.DataFrame:
    """
    Load penetration_by_company.csv with schema validation.

    Returns:
        DataFrame with penetration data

    Raises:
        DataLoadError: If file not found
        SchemaValidationError: If required columns missing

    Spec: §1.1 Required Files
    """
    data_dir = get_data_dir()
    file_path = data_dir / "processed" / "penetration_by_company.csv"

    if not file_path.exists():
        raise DataLoadError(
            f"Required file not found: {file_path}\n"
            f"Run Epic 2 pipeline to generate penetration_by_company.csv"
        )

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    # Validate schema (Spec: §1.1)
    required_columns = [
        'company_id', 'served_buildings', 'total_buildings_estimate', 'penetration_rate'
    ]
    validate_schema(df, required_columns, "penetration_by_company.csv")

    logger.info(f"Loaded {len(df)} penetration records from {file_path}")
    return df


@st.cache_data(ttl=CACHE_TTL)
def load_contact_summary() -> pd.DataFrame:
    """
    Load contact_summary.csv with schema validation.

    Returns:
        DataFrame with contact data

    Raises:
        DataLoadError: If file not found
        SchemaValidationError: If required columns missing

    Spec: §1.1 Required Files
    """
    data_dir = get_data_dir()
    file_path = data_dir / "processed" / "contact_summary.csv"

    if not file_path.exists():
        raise DataLoadError(
            f"Required file not found: {file_path}\n"
            f"Run Epic 2 pipeline to generate contact_summary.csv"
        )

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    # Validate schema (Spec: §1.1)
    # Note: contact_summary.csv contains aggregated contact data at company level
    required_columns = [
        'company_id', 'contact_count', 'last_contact_date',
        'contact_names', 'contact_emails'
    ]
    validate_schema(df, required_columns, "contact_summary.csv")

    logger.info(f"Loaded {len(df)} contacts from {file_path}")
    return df


@st.cache_data(ttl=CACHE_TTL)
def load_research_enrichment() -> Dict[str, Any]:
    """
    Load research_enrichment.json.

    Returns:
        Dictionary with research enrichment data

    Raises:
        DataLoadError: If file not found or invalid JSON

    Spec: §1.1 Required Files
    """
    data_dir = get_data_dir()
    file_path = data_dir / "research" / "research_enrichment.json"

    if not file_path.exists():
        raise DataLoadError(
            f"Required file not found: {file_path}\n"
            f"Run Epic 3 research pipeline to generate research_enrichment.json"
        )

    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise DataLoadError(f"Invalid JSON in {file_path}: {e}")
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    # Validate structure
    if 'metadata' not in data or 'companies' not in data:
        raise DataLoadError(
            f"Invalid research_enrichment.json structure. "
            f"Expected 'metadata' and 'companies' keys."
        )

    logger.info(f"Loaded research enrichment for {len(data['companies'])} companies")
    return data


def load_research_document(company_id: str) -> Optional[Dict[str, Any]]:
    """
    Load individual research document for a company.

    Args:
        company_id: Company ID to load research for

    Returns:
        Research document dict, or None if not found

    Spec: §1.2 Research Document Files
    """
    data_dir = get_data_dir()
    file_path = data_dir / "research" / "research_documents" / f"{company_id}.json"

    if not file_path.exists():
        logger.debug(f"Research document not found for company {company_id}")
        return None

    try:
        with open(file_path) as f:
            doc = json.load(f)
        return doc
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in research document {company_id}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to read research document {company_id}: {e}")
        return None


@st.cache_data(ttl=CACHE_TTL)
def load_channels_config() -> Dict[str, Any]:
    """
    Load channels.yaml configuration.

    Returns:
        Dictionary with channels configuration

    Raises:
        DataLoadError: If file not found or invalid YAML

    Spec: §1.1 Required Files
    """
    data_dir = get_data_dir()
    file_path = data_dir / "config" / "channels.yaml"

    if not file_path.exists():
        raise DataLoadError(
            f"Required file not found: {file_path}\n"
            f"Ensure channels.yaml exists in data/config/"
        )

    try:
        with open(file_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise DataLoadError(f"Invalid YAML in {file_path}: {e}")
    except Exception as e:
        raise DataLoadError(f"Failed to read {file_path}: {e}")

    if 'channels' not in config:
        raise DataLoadError(
            f"Invalid channels.yaml structure. Expected 'channels' key."
        )

    logger.info(f"Loaded {len(config['channels'])} channel definitions")
    return config


@st.cache_data(ttl=CACHE_TTL)
def load_company_research_data() -> Optional[pd.DataFrame]:
    """
    Load company_icp_scores_with_research.csv (Epic 4c output with web research).

    Returns:
        DataFrame with company research data including reasoning, hot_lead_signals,
        concerns, timing, and research_summary, or None if file doesn't exist

    Spec: Epic 4c - Company ICP Scoring with Web Research
    """
    data_dir = get_data_dir()
    file_path = data_dir / "scoring" / "company_icp_scores_with_research.csv"

    if not file_path.exists():
        logger.info("company_icp_scores_with_research.csv not found (Epic 4c not complete) - graceful degradation")
        return None

    try:
        df = pd.read_csv(file_path, dtype={'company_id': str})

        # Validate expected columns
        expected_columns = [
            'company_id', 'company_name', 'had_web_research', 'icp_fit_score',
            'confidence', 'reasoning', 'recommendation'
        ]

        missing = set(expected_columns) - set(df.columns)
        if missing:
            logger.warning(f"company_icp_scores_with_research.csv missing columns: {missing}")

        logger.info(f"Loaded research data for {len(df)} companies from {file_path}")
        return df
    except Exception as e:
        logger.warning(f"Failed to load company_icp_scores_with_research.csv: {e}. Continuing without detailed research data.")
        return None


@st.cache_data(ttl=CACHE_TTL)
def load_churn_predictions() -> Optional[pd.DataFrame]:
    """
    Load churn_predictions.csv (optional - Epic 6 output).

    Returns:
        DataFrame with churn predictions, or None if file doesn't exist

    Spec: §1.3 Churn Predictions (Epic 6 Output) - graceful degradation
    """
    data_dir = get_data_dir()
    file_path = data_dir / "scoring" / "churn_predictions.csv"

    if not file_path.exists():
        logger.info("churn_predictions.csv not found (Epic 6 not complete) - graceful degradation")
        return None

    try:
        df = pd.read_csv(file_path)

        # Validate schema if file exists
        required_columns = [
            'company_id', 'churn_probability', 'risk_tier', 'prediction_date'
        ]
        validate_schema(df, required_columns, "churn_predictions.csv")

        logger.info(f"Loaded {len(df)} churn predictions from {file_path}")
        return df
    except Exception as e:
        logger.warning(f"Failed to load churn_predictions.csv: {e}. Continuing without churn data.")
        return None


def clear_cache():
    """
    Clear all cached data loaders.

    Useful for "Refresh Data" button functionality.

    Spec: §4.3 Caching
    """
    st.cache_data.clear()
    logger.info("Cleared all data loader caches")
