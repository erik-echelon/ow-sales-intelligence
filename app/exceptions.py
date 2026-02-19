"""
Custom Exceptions for OpenWorks Prospect Intelligence UI

Epic 5 (OWRKS-5.02)
"""


class DataLoadError(Exception):
    """Raised when required data file cannot be loaded."""
    pass


class SchemaValidationError(Exception):
    """Raised when loaded data does not match required schema."""
    pass


class DataQualityError(Exception):
    """Raised when data quality gates fail (blocking gates only)."""
    pass
