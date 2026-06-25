from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"


class SourceType(str, Enum):
    MANUAL_RESEARCH = "manual_research"
    CSV_IMPORT = "csv_import"
    EXCEL_IMPORT = "excel_import"
    JSON_IMPORT = "json_import"
    API_IMPORT = "api_import"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"