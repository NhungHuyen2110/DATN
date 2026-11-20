"""Shared HTTP parameter constraints without importing a business router."""

from typing import Annotated
from fastapi import Path, Query

OrderID = Annotated[int, Path(ge=1, le=2147483647)]
Page = Annotated[int, Query(ge=1, le=2147483647)]
PageSize = Annotated[int, Query(ge=1, le=100)]
