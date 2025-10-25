# FILE: shared/callback_types.py

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Type

"""
This module defines a structured way to handle callback data using classes.
Each class represents a specific type of callback action, encapsulating the logic
for creating and parsing its corresponding callback string.

This approach prevents "magic strings" and makes the code more maintainable and less error-prone.

Prefixes are kept short to respect Telegram's 64-byte limit for callback data.
"""

# A registry to hold all callback classes for easy lookup
CALLBACK_REGISTRY: dict[str, Type[CallbackData]] = {}

class CallbackData(ABC):
    """Abstract base class for all callback data types."""
    PREFIX: str

    def __init_subclass__(cls, **kwargs):
        """This special method automatically registers any subclass into our registry."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'PREFIX'):
            if cls.PREFIX in CALLBACK_REGISTRY:
                raise ValueError(f"Duplicate PREFIX '{cls.PREFIX}' found for class {cls.__name__}")
            CALLBACK_REGISTRY[cls.PREFIX] = cls

    @classmethod
    @abstractmethod
    def from_string(cls, data: str) -> Optional[CallbackData]:
        """Parses a callback string and returns an instance of the class if it matches."""
        raise NotImplementedError

    @abstractmethod
    def to_string(self) -> str:
        """Converts the instance to its string representation for callback data."""
        raise NotImplementedError

def parse_callback_data(data: str) -> Optional[CallbackData]:
    """
    A factory function that takes a raw callback string and returns the appropriate
    CallbackData object by looking up the prefix in the registry.
    """
    if not data or ':' not in data:
        return None
        
    prefix = data.split(':', 1)[0]
    cls = CALLBACK_REGISTRY.get(prefix)
    if cls:
        return cls.from_string(data)
    return None


# --- Define your specific callback types below ---

class SendReceipt(CallbackData):
    """Callback for a customer wanting to send a receipt for an invoice."""
    PREFIX = "sr"

    def __init__(self, invoice_id: int):
        self.invoice_id = invoice_id

    @classmethod
    def from_string(cls, data: str) -> Optional[SendReceipt]:
        parts = data.split(':')
        if len(parts) == 2 and parts[0] == cls.PREFIX:
            try:
                return cls(invoice_id=int(parts[1]))
            except (ValueError, TypeError):
                return None
        return None

    def to_string(self) -> str:
        return f"{self.PREFIX}:{self.invoice_id}"


class StartManualInvoice(CallbackData):
    """Callback for an admin to start creating a manual invoice for a user."""
    PREFIX = "smi" # Start Manual Invoice

    def __init__(self, customer_id: int, username: str):
        self.customer_id = customer_id
        self.username = username
    
    @classmethod
    def from_string(cls, data: str) -> Optional[StartManualInvoice]:
        parts = data.split(':', 2)
        if len(parts) == 3 and parts[0] == cls.PREFIX:
            try:
                return cls(customer_id=int(parts[1]), username=parts[2])
            except (ValueError, TypeError):
                return None
        return None

    def to_string(self) -> str:
        return f"{self.PREFIX}:{self.customer_id}:{self.username}"