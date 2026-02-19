"""
Quality Gates Module for OpenWorks Prospect Intelligence UI

Implements blocking and non-blocking quality gates that run at startup.

Epic 5 (OWRKS-5.02)
Spec: §2.3 (Entity Resolution), §2.4 (Weight Validation), §4.5 (Data Quality Gates)
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from app.exceptions import DataQualityError

logger = logging.getLogger(__name__)

def validate_critical_field_completeness(scored_df: pd.DataFrame) -> None:
    """
    Validate that critical fields are ≥99% complete.

    Supports both old and new scoring formats:
    - Old: segment_rank, standard_score, augmented_score, icp_fit_score
    - New: rank, final_score, naics_attractiveness_score, company_opportunity_score

    Args:
        scored_df: Scored companies DataFrame

    Raises:
        DataQualityError: If any critical field is <99% complete

    Spec: §4.5 Data Quality Gates - BLOCKING
    """
    # Detect which format we're using
    is_new_format = 'final_score' in scored_df.columns and 'scoring_path' in scored_df.columns

    # Core fields that should exist in both formats
    critical_fields = ['company_id', 'company_name']

    # Add format-specific critical fields
    if is_new_format:
        critical_fields.extend([
            'rank',  # Replaces segment_rank
            'final_score',  # Replaces augmented_score
            'naics_attractiveness_score',
            'company_opportunity_score'
        ])
    else:
        critical_fields.extend([
            'segment_rank',
            'standard_score',
            'augmented_score',
            'icp_fit_score'
        ])

    for field in critical_fields:
        if field not in scored_df.columns:
            raise DataQualityError(
                f"BLOCKING: Critical field '{field}' missing from scored_companies.csv"
            )

        completeness = scored_df[field].notna().mean()

        if completeness < 0.99:
            raise DataQualityError(
                f"BLOCKING: Critical field '{field}' is only {completeness:.1%} complete. "
                f"Required: ≥99%. Fix upstream data before launching UI."
            )

    logger.info("✓ Critical field completeness validation passed (all ≥99%)")


def validate_no_duplicates(scored_df: pd.DataFrame, buildings_df: pd.DataFrame) -> None:
    """
    Validate no duplicate company_id or building_id values.

    Args:
        scored_df: Scored companies DataFrame
        buildings_df: Buildings DataFrame

    Raises:
        DataQualityError: If duplicates found

    Spec: §5.6 Duplicate Records - BLOCKING
    """
    # Check company_id duplicates
    if not scored_df['company_id'].is_unique:
        dupes = scored_df[scored_df['company_id'].duplicated(keep=False)]
        sample = dupes['company_id'].head(5).tolist()
        raise DataQualityError(
            f"BLOCKING: {len(dupes)} duplicate company_ids in scored_companies.csv. "
            f"Sample duplicates: {sample}"
        )

    # Check building_id duplicates
    if not buildings_df['building_id'].is_unique:
        dupes = buildings_df[buildings_df['building_id'].duplicated(keep=False)]
        sample = dupes['building_id'].head(5).tolist()
        raise DataQualityError(
            f"BLOCKING: {len(dupes)} duplicate building_ids in buildings.csv. "
            f"Sample duplicates: {sample}"
        )

    logger.info("✓ Duplicate validation passed (all IDs unique)")


def validate_join_integrity(
    scored_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    buildings_df: pd.DataFrame
) -> None:
    """
    Validate 100% join integrity across tables.

    Args:
        scored_df: Scored companies DataFrame
        companies_df: Companies DataFrame
        buildings_df: Buildings DataFrame

    Raises:
        DataQualityError: If any company_id in scores/buildings not in companies

    Spec: §5.2 Incorrect Joins - BLOCKING
    """
    # Check scored → companies (IDs already strings from data loaders)
    scored_ids = set(scored_df['company_id'])
    company_ids = set(companies_df['company_id'])

    missing_from_companies = scored_ids - company_ids
    if missing_from_companies:
        sample = list(missing_from_companies)[:5]
        raise DataQualityError(
            f"BLOCKING: {len(missing_from_companies)} company_ids in scored_companies.csv "
            f"not found in companies.csv. Sample: {sample}"
        )

    # Check buildings → companies (IDs already strings from data loaders)
    building_company_ids = set(buildings_df['company_id'])
    missing_building_companies = building_company_ids - company_ids
    if missing_building_companies:
        sample = list(missing_building_companies)[:5]
        raise DataQualityError(
            f"BLOCKING: {len(missing_building_companies)} company_ids in buildings.csv "
            f"not found in companies.csv. Sample: {sample}"
        )

    logger.info("✓ Join integrity validation passed (100% matched)")


def check_entity_resolution_quality(er_log_path: Path) -> Tuple[float, bool]:
    """
    Check entity resolution orphan rate (<10% threshold).

    Args:
        er_log_path: Path to entity_resolution_log.csv

    Returns:
        Tuple of (orphan_rate, passed)

    Spec: §2.3 Entity Resolution UI Checks - NON-BLOCKING BANNER
    """
    if not er_log_path.exists():
        logger.warning("Entity resolution log not found. Skipping quality check.")
        return 0.0, True

    try:
        er_log = pd.read_csv(er_log_path)

        if 'match_type' not in er_log.columns:
            logger.warning("Entity resolution log missing 'match_type' column")
            return 0.0, True

        orphan_rate = (er_log['match_type'] == 'unmatched').mean()
        passed = bool(orphan_rate < 0.10)

        if not passed:
            orphan_count = (er_log['match_type'] == 'unmatched').sum()
            logger.warning(
                f"Entity resolution orphan rate is {orphan_rate:.1%} "
                f"(threshold: <10%). {orphan_count} HubSpot records unmatched."
            )
        else:
            logger.info(f"✓ Entity resolution quality check passed (orphan rate: {orphan_rate:.1%})")

        return orphan_rate, passed

    except Exception as e:
        logger.warning(f"Failed to check entity resolution quality: {e}")
        return 0.0, True


def validate_scoring_weights(diagnostics_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that scoring weights sum to 1.0.

    Args:
        diagnostics_path: Path to scoring_diagnostics.json

    Returns:
        Tuple of (valid, error_message)

    Spec: §2.4 Weight Normalization Validation - NON-BLOCKING (hides chart)
    """
    if not diagnostics_path.exists():
        return False, "Scoring diagnostics file not found"

    try:
        with open(diagnostics_path) as f:
            diagnostics = json.load(f)

        weight_sum = diagnostics.get('weight_validation', {}).get('sum')

        if weight_sum is None:
            return False, "Weight validation not found in diagnostics"

        # Tolerance for floating point comparison
        if abs(weight_sum - 1.0) > 0.001:
            return False, f"Scoring weights sum to {weight_sum}, not 1.0"

        logger.info(f"✓ Scoring weights validation passed (sum={weight_sum})")
        return True, None

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in diagnostics: {e}"
    except Exception as e:
        return False, f"Failed to validate weights: {e}"


def check_coordinate_coverage(buildings_df: pd.DataFrame) -> Tuple[float, bool]:
    """
    Check that ≥80% of buildings have valid coordinates.

    Args:
        buildings_df: Buildings DataFrame

    Returns:
        Tuple of (coverage_rate, passed)

    Spec: §2.1.2 Geo-coordinate Validity - NON-BLOCKING WARNING
    """
    total = len(buildings_df)

    # Count buildings with both lat and lon
    has_coords = buildings_df['latitude'].notna() & buildings_df['longitude'].notna()
    count_with_coords = has_coords.sum()

    coverage_rate = count_with_coords / total if total > 0 else 0.0
    passed = bool(coverage_rate >= 0.80)

    if not passed:
        logger.warning(
            f"Coordinate coverage is {coverage_rate:.1%} "
            f"(threshold: ≥80%). {total - count_with_coords} buildings missing coordinates."
        )
    else:
        logger.info(f"✓ Coordinate coverage check passed ({coverage_rate:.1%})")

    return coverage_rate, passed


def check_research_coverage(scored_df: pd.DataFrame) -> Tuple[float, bool]:
    """
    Check that ≥70% of companies have research documents.

    Args:
        scored_df: Scored companies DataFrame

    Returns:
        Tuple of (coverage_rate, passed)

    Spec: §4.5 Data Quality Gates - NON-BLOCKING WARNING
    """
    if 'has_research_doc' not in scored_df.columns:
        logger.warning("scored_companies.csv missing 'has_research_doc' column")
        return 0.0, False

    total = len(scored_df)
    with_research = scored_df['has_research_doc'].sum()

    coverage_rate = with_research / total if total > 0 else 0.0
    passed = bool(coverage_rate >= 0.70)

    if not passed:
        logger.warning(
            f"Research coverage is {coverage_rate:.1%} "
            f"(threshold: ≥70%). {total - with_research} companies without research."
        )
    else:
        logger.info(f"✓ Research coverage check passed ({coverage_rate:.1%})")

    return coverage_rate, passed


def run_startup_validation(
    scored_df: pd.DataFrame,
    companies_df: pd.DataFrame,
    buildings_df: pd.DataFrame,
    data_dir: Path
) -> dict:
    """
    Run all quality gates at application startup.

    Runs blocking gates first (fail fast), then non-blocking gates.

    Args:
        scored_df: Scored companies DataFrame
        companies_df: Companies DataFrame
        buildings_df: Buildings DataFrame
        data_dir: Path to data directory

    Returns:
        Dictionary with validation results

    Raises:
        DataQualityError: If any blocking gate fails

    Spec: §4.5 Data Quality Gates
    """
    logger.info("Running startup validation...")

    results = {
        'blocking_gates': {},
        'non_blocking_gates': {}
    }

    # =========================================================================
    # BLOCKING GATES (fail fast)
    # =========================================================================

    try:
        # Gate 1: Critical field completeness ≥99%
        validate_critical_field_completeness(scored_df)
        results['blocking_gates']['critical_field_completeness'] = 'PASS'
    except DataQualityError as e:
        results['blocking_gates']['critical_field_completeness'] = f'FAIL: {e}'
        raise

    try:
        # Gate 2: No duplicates
        validate_no_duplicates(scored_df, buildings_df)
        results['blocking_gates']['no_duplicates'] = 'PASS'
    except DataQualityError as e:
        results['blocking_gates']['no_duplicates'] = f'FAIL: {e}'
        raise

    try:
        # Gate 3: 100% join integrity
        validate_join_integrity(scored_df, companies_df, buildings_df)
        results['blocking_gates']['join_integrity'] = 'PASS'
    except DataQualityError as e:
        results['blocking_gates']['join_integrity'] = f'FAIL: {e}'
        raise

    # =========================================================================
    # NON-BLOCKING GATES (log warnings, continue)
    # =========================================================================

    # Gate 4: Entity resolution orphan rate <10% (displays banner if fails)
    er_log_path = data_dir / "processed" / "entity_resolution_log.csv"
    orphan_rate, er_passed = check_entity_resolution_quality(er_log_path)
    results['non_blocking_gates']['entity_resolution'] = {
        'orphan_rate': orphan_rate,
        'passed': er_passed
    }

    # Gate 5: Scoring weights sum to 1.0 (hides chart if fails)
    diagnostics_path = data_dir / "scoring" / "scoring_diagnostics.json"
    weights_valid, weight_error = validate_scoring_weights(diagnostics_path)
    results['non_blocking_gates']['scoring_weights'] = {
        'valid': weights_valid,
        'error': weight_error
    }

    # Gate 6: Coordinate coverage ≥80% (log warning if fails)
    coord_coverage, coord_passed = check_coordinate_coverage(buildings_df)
    results['non_blocking_gates']['coordinate_coverage'] = {
        'coverage': coord_coverage,
        'passed': coord_passed
    }

    # Gate 7: Research coverage ≥70% (log warning if fails)
    research_coverage, research_passed = check_research_coverage(scored_df)
    results['non_blocking_gates']['research_coverage'] = {
        'coverage': research_coverage,
        'passed': research_passed
    }

    logger.info("✓ All blocking gates passed")
    return results
