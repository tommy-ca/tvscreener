class ExtensionError(Exception):
    """Base error for tvscreener extensions."""

    pass


class ForexScreenerError(ExtensionError):
    """Base exception for ForexOpportunityScreener."""

    pass


class InvalidPairError(ForexScreenerError):
    """Raised when forex pair symbol is invalid."""

    pass


class FilterConfigurationError(ForexScreenerError):
    """Raised when filter configuration is invalid."""

    pass


class RateLimitError(ForexScreenerError):
    """Raised when API rate limit is exceeded."""

    pass
