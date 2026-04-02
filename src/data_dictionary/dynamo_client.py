from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from .models import DataElement

TABLE_NAME = os.environ.get("TABLE_NAME", "DataDictionary-prod")
PROPOSALS_TABLE_NAME = os.environ.get("PROPOSALS_TABLE_NAME", "DataDictionaryProposals-prod")
CONTEXT_INDEX = "context-index"

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
_table = _dynamodb.Table(TABLE_NAME)
_proposals_table = _dynamodb.Table(PROPOSALS_TABLE_NAME)


def get_data_element(data_element: str) -> Optional[Dict[str, Any]]:
    response = _table.get_item(Key={"dataElement": data_element})
    return response.get("Item")


def put_data_element(element: DataElement) -> Dict[str, Any]:
    existing = get_data_element(element.dataElement)
    existing_created_at = existing.get("createdAt") if existing else None
    item = element.with_timestamps(existing_created_at=existing_created_at).to_dynamo_item()
    _table.put_item(Item=item)
    return item


def search_data_elements(query: str) -> List[Dict[str, Any]]:
    query_lower = query.lower()
    filter_expr = Attr("dataElement").contains(query) | Attr("meaning").contains(query)
    if query != query_lower:
        filter_expr = (
            filter_expr
            | Attr("dataElement").contains(query_lower)
            | Attr("meaning").contains(query_lower)
        )

    items = []
    kwargs: Dict[str, Any] = {"FilterExpression": filter_expr}
    while True:
        response = _table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def list_data_elements(
    context: Optional[str] = None,
    limit: int = 50,
    last_evaluated_key: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if context:
        kwargs: Dict[str, Any] = {
            "IndexName": CONTEXT_INDEX,
            "KeyConditionExpression": Key("context").eq(context),
            "Limit": limit,
        }
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = _table.query(**kwargs)
    else:
        kwargs = {"Limit": limit}
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = _table.scan(**kwargs)

    return {
        "items": response.get("Items", []),
        "next_key": response.get("LastEvaluatedKey"),
        "count": response.get("Count", 0),
    }


def get_elements_by_context(context: str) -> List[Dict[str, Any]]:
    items = []
    kwargs: Dict[str, Any] = {
        "IndexName": CONTEXT_INDEX,
        "KeyConditionExpression": Key("context").eq(context),
    }
    while True:
        response = _table.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


# ---------------------------------------------------------------------------
# Proposal storage — cross-invocation persistence for propose/commit workflow
# ---------------------------------------------------------------------------

def save_proposal(proposal_id: str, data: Dict[str, Any], ttl_seconds: int = 3600) -> None:
    _proposals_table.put_item(Item={
        "proposal_id": proposal_id,
        "_expires_at": int(time.time()) + ttl_seconds,
        **data,
    })


def get_proposal_data(proposal_id: str) -> Optional[Dict[str, Any]]:
    response = _proposals_table.get_item(Key={"proposal_id": proposal_id})
    item = response.get("Item")
    if not item:
        return None
    return {k: v for k, v in item.items() if k not in ("proposal_id", "_expires_at")}
