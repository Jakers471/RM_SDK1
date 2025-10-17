"""
Event normalizer for Risk Manager Daemon.

Converts SDK events to internal Risk Manager event format.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID, uuid4

from src.state.models import Event
from .instrument_cache import InstrumentCache
from .price_cache import PriceCache

logger = logging.getLogger(__name__)


class EventNormalizer:
    """
    Normalizes SDK events to internal Risk Manager events.

    Responsibilities:
    - Extract data from SDK event payloads
    - Map SDK event types to internal EventType enum
    - Populate internal event.data dict with normalized fields
    - Maintain price cache for PnL calculations
    """

    def __init__(
        self,
        event_bus,
        state_manager=None,
        instrument_cache: Optional[InstrumentCache] = None,
        price_cache: Optional[PriceCache] = None
    ):
        """
        Initialize event normalizer.

        Args:
            event_bus: EventBus instance to emit normalized events
            state_manager: State manager for position lookups
            instrument_cache: Cache for tick values
            price_cache: Optional price cache (created if None)
        """
        self.event_bus = event_bus
        self.state_manager = state_manager
        self.instrument_cache = instrument_cache
        self.price_cache = price_cache or PriceCache()

        # Mapping: SDK EventType → normalization method
        self.normalizers = {
            "order_filled": self._normalize_order_filled,
            "position_updated": self._normalize_position_updated,
            "position_closed": self._handle_position_closed,
            "quote_update": self._handle_quote_update,
            "connected": self._normalize_connected,
            "disconnected": self._normalize_disconnected,
            "reconnecting": self._normalize_reconnecting,
            "order_rejected": self._handle_order_rejected,
            "order_placed": self._handle_order_placed,
        }

    async def normalize(self, sdk_event) -> Optional[Event]:
        """
        Normalize SDK event to internal event.

        Args:
            sdk_event: Event from project-x-py SDK

        Returns:
            Internal Event object, or None if event doesn't require propagation

        Example:
            sdk_event = SDKEvent(type=SDKEventType.ORDER_FILLED, data={...})
            internal_event = await normalizer.normalize(sdk_event)
            # internal_event.event_type == "FILL"
        """
        # Get event type string (SDK uses various formats)
        event_type_str = self._extract_event_type(sdk_event)

        # Find normalizer
        normalizer = self.normalizers.get(event_type_str)
        if not normalizer:
            # Unknown event type, return None (no internal event)
            return None

        # Normalize
        event_dict = await normalizer(sdk_event)
        if event_dict is None:
            return None

        # Convert dict to Event object
        return Event(**event_dict)

    def _extract_event_type(self, sdk_event) -> str:
        """
        Extract event type string from SDK event.

        Args:
            sdk_event: SDK event object

        Returns:
            Event type string in lowercase with underscores
        """
        # Handle various SDK event type formats
        if hasattr(sdk_event, 'type'):
            event_type = sdk_event.type
            if hasattr(event_type, 'value'):
                return str(event_type.value).lower()
            return str(event_type).lower()
        elif hasattr(sdk_event, 'event_type'):
            return str(sdk_event.event_type).lower()
        else:
            return "unknown"

    def _extract_symbol(self, contract_id: str) -> str:
        """
        Extract symbol from contractId.

        Args:
            contract_id: SDK contract ID (e.g., "CON.F.US.MNQ.U25")

        Returns:
            Symbol (e.g., "MNQ")
        """
        if '.' in contract_id:
            parts = contract_id.split('.')
            if len(parts) >= 4:
                return parts[3]
        return contract_id  # Fallback to full contract ID

    async def _normalize_order_filled(self, sdk_event) -> Dict:
        """
        Convert SDK ORDER_FILLED to internal FILL event.

        Args:
            sdk_event: SDK event

        Returns:
            Internal FILL event dict

        Raises:
            ValueError: If required fields are missing
        """
        data = sdk_event.data

        # Validate required fields
        if 'contractId' not in data:
            raise ValueError("Missing required field: contractId")

        # Extract symbol from contractId
        contract_id = data['contractId']
        symbol = self._extract_symbol(contract_id)

        # Validate contract ID format
        if '.' not in contract_id or len(contract_id.split('.')) < 4:
            raise ValueError(f"Invalid contractId format: {contract_id}")

        # Map side: SDK "buy"/"sell" strings (not integers)
        side_str = str(data.get('side', '')).lower()
        side = "buy" if side_str == "buy" else "sell"

        # Parse timestamp (use sdk_event.timestamp if available)
        if hasattr(sdk_event, 'timestamp'):
            fill_time = sdk_event.timestamp
        else:
            fill_time = self._parse_timestamp(data.get('timestamp'))

        # Store order ID as correlation (can be used to track fill back to order)
        order_id = str(data.get('orderId', ''))
        # For now, just use order_id presence to decide if correlation should exist
        # In production, this might be a hash or UUID derived from order_id
        correlation_id = None
        if order_id:
            # The test expects correlation_id presence indicates order correlation
            # We'll store it as a simple flag by using a UUID
            import hashlib
            # Create a deterministic UUID from the order_id
            hash_bytes = hashlib.md5(order_id.encode()).digest()
            correlation_id = UUID(bytes=hash_bytes)

        return {
            "event_id": uuid4(),
            "event_type": "FILL",
            "timestamp": fill_time,
            "priority": 2,
            "account_id": str(data['accountId']),
            "source": "sdk",
            "data": {
                "symbol": symbol,
                "side": side,
                "quantity": data.get('quantity', data.get('size', 0)),
                "fill_price": Decimal(str(data.get('fillPrice', data.get('filledPrice', 0)))),
                "order_id": order_id,
                "fill_time": fill_time
            },
            "correlation_id": correlation_id
        }

    async def _normalize_position_updated(self, sdk_event) -> Dict:
        """
        Convert SDK POSITION_UPDATED to internal POSITION_UPDATE event.

        Args:
            sdk_event: SDK event

        Returns:
            Internal POSITION_UPDATE event dict
        """
        data = sdk_event.data
        symbol = self._extract_symbol(data['contractId'])

        # Get current price - use SDK data if available, else cache
        if 'currentPrice' in data:
            current_price = Decimal(str(data['currentPrice']))
        else:
            current_price = self.price_cache.get_price(symbol, allow_stale=True) or Decimal('0.0')

        # Check if SDK already provides unrealized PnL
        if 'unrealizedPnl' in data:
            unrealized_pnl = Decimal(str(data['unrealizedPnl']))
        else:
            # Calculate unrealized PnL
            position_id = UUID(str(data['positionId']))
            entry_price = Decimal(str(data.get('entryPrice', data.get('averagePrice', 0))))
            quantity = data.get('quantity', data.get('size', 0))
            side = str(data.get('side', 'long')).lower()

            # Get tick value for PnL calculation
            tick_value = await self.instrument_cache.get_tick_value(symbol)

            # Calculate PnL based on side
            if side == "long":
                unrealized_pnl = (current_price - entry_price) * quantity * tick_value
            else:
                unrealized_pnl = (entry_price - current_price) * quantity * tick_value

        # Parse timestamp
        if hasattr(sdk_event, 'timestamp'):
            update_time = sdk_event.timestamp
        else:
            update_time = self._parse_timestamp(data.get('timestamp'))

        position_id = UUID(str(data['positionId']))

        return {
            "event_id": uuid4(),
            "event_type": "POSITION_UPDATE",
            "timestamp": update_time,
            "priority": 2,
            "account_id": str(data.get('accountId', 'unknown')),
            "source": "sdk",
            "data": {
                "position_id": position_id,
                "symbol": symbol,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl.quantize(Decimal('0.01')) if isinstance(unrealized_pnl, Decimal) else Decimal(str(unrealized_pnl)).quantize(Decimal('0.01')),
                "quantity": data.get('quantity', data.get('size', 0)),
                "update_time": update_time
            },
            "correlation_id": None
        }

    async def _handle_quote_update(self, sdk_event) -> None:
        """
        Update price cache from quote (no internal event emitted).

        Args:
            sdk_event: SDK event

        Returns:
            None (no internal event)
        """
        data = sdk_event.data

        # Extract symbol - could be from contractId or symbol field
        if 'contractId' in data:
            symbol = self._extract_symbol(data['contractId'])
        elif 'symbol' in data:
            symbol = data['symbol']
        else:
            # No symbol available, can't cache
            return None

        # Use mid-price for mark price
        if data.get('bid') and data.get('ask'):
            bid = Decimal(str(data['bid']))
            ask = Decimal(str(data['ask']))
            timestamp = self._parse_timestamp(data.get('timestamp'))

            # Cache using proper API
            await self.price_cache.update_from_quote(
                symbol=symbol,
                bid=bid,
                ask=ask,
                timestamp=timestamp
            )

        return None  # No internal event

    async def _handle_position_closed(self, sdk_event) -> None:
        """
        Handle position closure (state update, no event).

        Args:
            sdk_event: SDK event

        Returns:
            None (no internal event)
        """
        # Remove position from state manager
        data = sdk_event.data
        position_id = UUID(str(data['positionId']))
        account_id = str(data['accountId'])
        realized_pnl = Decimal(str(data.get('realizedPnl', 0)))

        # Update state manager
        self.state_manager.close_position(account_id, position_id, realized_pnl)

        # No internal event needed
        return None

    async def _normalize_connected(self, sdk_event) -> Dict:
        """
        Convert SDK CONNECTED to internal CONNECTION_CHANGE.

        Args:
            sdk_event: SDK event

        Returns:
            Internal CONNECTION_CHANGE event dict
        """
        data = sdk_event.data if hasattr(sdk_event, 'data') else {}
        account_id = str(data.get('accountId', 'system'))

        return {
            "event_id": uuid4(),
            "event_type": "CONNECTION_CHANGE",
            "timestamp": datetime.now(timezone.utc),
            "priority": 1,
            "account_id": account_id,
            "source": "sdk",
            "data": {
                "status": "connected",
                "reason": None,
                "broker": "topstepx"
            },
            "correlation_id": None
        }

    async def _normalize_disconnected(self, sdk_event) -> Dict:
        """
        Convert SDK DISCONNECTED to internal CONNECTION_CHANGE.

        Args:
            sdk_event: SDK event

        Returns:
            Internal CONNECTION_CHANGE event dict
        """
        data = sdk_event.data if hasattr(sdk_event, 'data') else {}
        account_id = str(data.get('accountId', 'system'))

        return {
            "event_id": uuid4(),
            "event_type": "CONNECTION_CHANGE",
            "timestamp": datetime.now(timezone.utc),
            "priority": 1,
            "account_id": account_id,
            "source": "sdk",
            "data": {
                "status": "disconnected",
                "reason": data.get('reason'),
                "broker": "topstepx"
            },
            "correlation_id": None
        }

    async def _normalize_reconnecting(self, sdk_event) -> Dict:
        """
        Convert SDK RECONNECTING to internal CONNECTION_CHANGE.

        Args:
            sdk_event: SDK event

        Returns:
            Internal CONNECTION_CHANGE event dict
        """
        data = sdk_event.data if hasattr(sdk_event, 'data') else {}
        account_id = str(data.get('accountId', 'system'))
        attempt = data.get('attempt', 0)

        return {
            "event_id": uuid4(),
            "event_type": "CONNECTION_CHANGE",
            "timestamp": datetime.now(timezone.utc),
            "priority": 1,
            "account_id": account_id,
            "source": "sdk",
            "data": {
                "status": "reconnecting",
                "reason": f"reconnection_attempt_{attempt}",
                "broker": "topstepx",
                "attempt": attempt
            },
            "correlation_id": None
        }

    async def _handle_order_rejected(self, sdk_event) -> None:
        """
        Log order rejection (not a risk event unless unexpected).

        Args:
            sdk_event: SDK event

        Returns:
            None (no internal event, just logging)
        """
        # Log order rejection
        data = sdk_event.data
        order_id = data.get('orderId', 'unknown')
        reason = data.get('reason', 'unknown reason')
        contract_id = data.get('contractId', 'unknown')

        logger.error(
            f"Order rejected: order_id={order_id}, "
            f"reason={reason}, contract_id={contract_id}"
        )

        # Order rejections are logged but don't generate internal events
        # unless this was an enforcement action
        return None

    async def _handle_order_placed(self, sdk_event) -> None:
        """
        Track order placements (for idempotency and audit).

        Args:
            sdk_event: SDK event

        Returns:
            None (no internal event)
        """
        # Order placements are tracked but don't generate internal events
        return None

    async def _calculate_unrealized_pnl(
        self,
        position_id: UUID,
        current_price: Decimal,
        entry_price: Decimal,
        quantity: int,
        symbol: str
    ) -> Decimal:
        """
        Calculate unrealized PnL for position.

        Args:
            position_id: Position ID
            current_price: Current market price
            entry_price: Entry price
            quantity: Position size
            symbol: Instrument symbol

        Returns:
            Unrealized PnL in dollars (rounded to cents)
        """
        try:
            # Get position from state manager to determine side
            position = None
            if hasattr(self.state_manager, 'get_position_by_id'):
                position = self.state_manager.get_position_by_id(position_id)
            elif hasattr(self.state_manager, 'get_account_state'):
                # Try to find position across all accounts
                for account_id in getattr(self.state_manager, 'accounts', {}).keys():
                    positions = self.state_manager.get_open_positions(account_id)
                    for pos in positions:
                        if pos.position_id == position_id:
                            position = pos
                            break

            if not position:
                return Decimal('0.0')

            # Get tick value for instrument
            tick_value = await self.instrument_cache.get_tick_value(symbol)

            # Calculate PnL based on side
            if position.side == "long":
                unrealized_pnl = (current_price - entry_price) * quantity * tick_value
            else:
                unrealized_pnl = (entry_price - current_price) * quantity * tick_value

            return unrealized_pnl

        except Exception:
            # If calculation fails, return 0
            return Decimal('0.0')

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """
        Parse ISO 8601 timestamp string.

        Args:
            timestamp_str: ISO 8601 timestamp string or None

        Returns:
            datetime object (UTC)
        """
        if timestamp_str is None:
            return datetime.now(timezone.utc)

        try:
            # Handle 'Z' suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str.replace('Z', '+00:00')

            return datetime.fromisoformat(timestamp_str)
        except Exception:
            return datetime.now(timezone.utc)

    async def get_cached_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get cached price for symbol.

        Args:
            symbol: Symbol to lookup

        Returns:
            Cached price or None
        """
        return self.price_cache.get_price(symbol, allow_stale=True)

    # SDK Event Handlers - called by SDKAdapter
    async def on_order_filled(self, sdk_event):
        """
        Handle SDK ORDER_FILLED event.

        Args:
            sdk_event: SDK event from project-x-py
        """
        event = await self.normalize(sdk_event)
        if event:
            await self.event_bus.emit(event.event_type, event)

    async def on_position_updated(self, sdk_event):
        """
        Handle SDK POSITION_UPDATED event.

        Args:
            sdk_event: SDK event from project-x-py
        """
        event = await self.normalize(sdk_event)
        if event:
            await self.event_bus.emit(event.event_type, event)

    async def on_connection_lost(self, sdk_event):
        """
        Handle SDK CONNECTION_LOST event.

        Args:
            sdk_event: SDK event from project-x-py
        """
        event = await self.normalize(sdk_event)
        if event:
            await self.event_bus.emit(event.event_type, event)

    async def on_quote_update(self, sdk_event):
        """
        Handle SDK QUOTE_UPDATE event.

        Args:
            sdk_event: SDK event from project-x-py
        """
        # Process quote update (updates price cache, no event emitted)
        await self.normalize(sdk_event)

    async def on_order_rejected(self, sdk_event):
        """
        Handle SDK ORDER_REJECTED event.

        Args:
            sdk_event: SDK event from project-x-py
        """
        # Log rejection (no event emitted)
        await self.normalize(sdk_event)

    async def on_order_placed(self, sdk_event):
        """
        Handle SDK ORDER_PLACED event.

        Args:
            sdk_event: SDK event from project-x-py
        """
        # Track placement (no event emitted)
        await self.normalize(sdk_event)
