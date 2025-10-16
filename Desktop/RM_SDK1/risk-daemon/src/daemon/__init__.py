"""
Daemon module for Risk Manager.

Provides event bus and daemon initialization components.
"""

from .event_bus import EventBus

__all__ = ["EventBus"]
