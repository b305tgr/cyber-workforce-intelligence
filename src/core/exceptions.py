class CyberWorkforceException(Exception):
    """Base exception for the application."""


class ValidationException(CyberWorkforceException):
    """Raised when validation fails."""


class DuplicateRecordException(CyberWorkforceException):
    """Raised when a duplicate record is detected."""


class DatabaseException(CyberWorkforceException):
    """Raised for database-related errors."""


class ImportException(CyberWorkforceException):
    """Raised during import failures."""