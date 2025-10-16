"""
Custom exceptions for SDK adapter layer.

These exceptions wrap SDK-specific errors to provide a clean interface
for the Risk Manager Daemon.
"""


class SDKAdapterError(Exception):
    """Base exception for SDK adapter errors."""
    pass


class ConnectionError(SDKAdapterError):
    """Failed to connect or authenticate with broker."""
    pass


class QueryError(SDKAdapterError):
    """Failed to query positions, orders, or account data."""
    pass


class OrderError(SDKAdapterError):
    """Failed to place, modify, or cancel order."""
    pass


class PriceError(SDKAdapterError):
    """Failed to get current market price."""
    pass


class InstrumentError(SDKAdapterError):
    """Instrument not found or invalid."""
    pass
