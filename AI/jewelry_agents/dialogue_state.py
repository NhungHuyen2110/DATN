
"""Structured shopping state, independent of storage and retrieval."""

from dataclasses import dataclass, replace, asdict
from typing import Optional
from decimal import Decimal
import re


@dataclass(frozen=True)
class ShoppingState:

    category: Optional[str] = None
    material: Optional[str] = None
    gemstone: Optional[str] = None

    min_price: Optional[int | str] = None
    max_price: Optional[int | str] = None

    min_exclusive: bool = False
    max_exclusive: bool = False

    audience: Optional[str] = None
    style: Optional[str] = None

    price_preference: str = "neutral"
    top_k: int = 3

    def __post_init__(self):

        if type(self.top_k) is not int or not 1 <= self.top_k <= 10:
            raise ValueError("top_k must be 1..10")

        if self.price_preference not in {
            "neutral",
            "affordable",
            "lowest_price",
            "highest_price"
        }:
            raise ValueError("Invalid price preference")

        for field in ("min_price", "max_price"):
            value = getattr(self, field)

            if value is not None:
                if type(value) is not int and not (isinstance(value, str) and re.fullmatch(r'\d+(?:\.\d+)?', value)):
                    raise ValueError("Invalid budget")
                if Decimal(str(value)) < 0:
                    raise ValueError("Invalid budget")

        if (
            self.min_price is not None
            and self.max_price is not None
        ):
            if Decimal(str(self.min_price)) > Decimal(str(self.max_price)):
                raise ValueError("Invalid budget range")

            if (
                Decimal(str(self.min_price)) == Decimal(str(self.max_price))
                and (self.min_exclusive or self.max_exclusive)
            ):
                raise ValueError("Empty budget range")

    def to_dict(self):
        return asdict(self)


FIELDS = set(ShoppingState.__dataclass_fields__)


def update_state(state, updates=None, clear=None):
    """Apply validated changes without mutating the previous state."""

    if not isinstance(state, ShoppingState):
        raise TypeError("Expected ShoppingState")

    updates = dict(updates or {})
    clear = set(clear or ())

    if (set(updates) | clear) - FIELDS:
        raise ValueError("Unknown shopping state field")

    if set(updates) & clear:
        raise ValueError("Conflicting state operations")

    defaults = ShoppingState()

    changes = {
        field: getattr(defaults, field)
        for field in clear
    }

    if "min_price" in clear:
        changes["min_exclusive"] = False

    if "max_price" in clear:
        changes["max_exclusive"] = False

    if "min_price" in updates:
        changes["min_exclusive"] = False

    if "max_price" in updates:
        changes["max_exclusive"] = False

    changes.update(updates)

    return replace(state, **changes)


def reset_state(top_k=3):
    """Start a new shopping task without inheriting old constraints."""
    return ShoppingState(top_k=top_k)


@dataclass(frozen=True)
class StatePatch:
    """Omitted slots KEEP their values; UNKNOWN never clears a slot."""
    updates: dict
    clear: frozenset = frozenset()
    reset: bool = False
    unknown: frozenset = frozenset()

    def __post_init__(self):
        groups = (set(self.updates), set(self.clear), set(self.unknown))
        if set.union(*groups) - FIELDS or any(groups[i] & groups[j] for i in range(3) for j in range(i)):
            raise ValueError('Invalid or conflicting slot operations')

    def operations(self):
        operations = {field: ('SET' if field in self.updates else 'CLEAR' if field in self.clear
                             else 'UNKNOWN' if field in self.unknown else 'KEEP') for field in FIELDS}
        if self.reset:
            operations['task'] = 'RESET'
        return operations

    def apply(self, previous):
        base = reset_state() if self.reset else previous
        return update_state(base, self.updates, self.clear)


@dataclass(frozen=True)
class PendingClarification:
    """Server-owned goal; attempts bound repeated questions without losing slots."""
    goal: str
    attempts: int = 1
