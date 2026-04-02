from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DataElement(BaseModel):
    dataElement: str = Field(
        description="The exact API field key name (e.g. customerId, orderTotal)"
    )
    meaning: str = Field(
        description=(
            "Precise, unambiguous definition an AI agent can rely on without hallucination. "
            "Should include what the field represents, its purpose, and any important semantics."
        )
    )
    context: str = Field(
        description="The API or service this field belongs to (e.g. OrdersAPI, CustomerService)"
    )
    dataType: Literal["string", "number", "boolean", "array", "object"] = Field(
        description="The data type of the field"
    )
    examples: List[str] = Field(
        default_factory=list,
        description="2-3 concrete example values demonstrating the field's content",
    )
    constraints: str = Field(
        default="",
        description="Format, validation, and immutability rules (e.g. UUID v4, immutable, max 255 chars)",
    )
    relatedElements: List[str] = Field(
        default_factory=list,
        description="Names of related API field keys that are semantically connected",
    )
    source: str = Field(
        default="",
        description="API name and version where this field originates (e.g. Orders API v2.1)",
    )
    createdAt: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of when this entry was first created",
    )
    updatedAt: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of when this entry was last updated",
    )
    status: Literal["active", "deprecated"] = Field(
        default="active",
        description="Lifecycle status of this data element",
    )

    def with_timestamps(self, existing_created_at: Optional[str] = None) -> "DataElement":
        now = datetime.now(timezone.utc).isoformat()
        return self.model_copy(
            update={
                "createdAt": existing_created_at or now,
                "updatedAt": now,
            }
        )

    def to_dynamo_item(self) -> dict:
        item = self.model_dump()
        item["examples"] = item.get("examples") or []
        item["relatedElements"] = item.get("relatedElements") or []
        return {k: v for k, v in item.items() if v is not None and v != ""}
