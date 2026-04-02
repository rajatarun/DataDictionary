from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from .models import DataElement

TABLE_NAME = os.environ.get("TABLE_NAME", "DataDictionary-prod")
CONTEXT_INDEX = "context-index"


def _get_table():
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return dynamodb.Table(TABLE_NAME)


def get_data_element(data_element: str) -> Optional[Dict[str, Any]]:
    table = _get_table()
    response = table.get_item(Key={"dataElement": data_element})
    return response.get("Item")


def put_data_element(element: DataElement) -> Dict[str, Any]:
    table = _get_table()
    existing = get_data_element(element.dataElement)
    existing_created_at = existing.get("createdAt") if existing else None
    item = element.with_timestamps(existing_created_at=existing_created_at).to_dynamo_item()
    table.put_item(Item=item)
    return item


def search_data_elements(query: str) -> List[Dict[str, Any]]:
    table = _get_table()
    query_lower = query.lower()
    filter_expr = Attr("dataElement").contains(query) | Attr("meaning").contains(query)
    # Also try case-insensitive approach for lower-case query
    if query != query_lower:
        filter_expr = (
            filter_expr
            | Attr("dataElement").contains(query_lower)
            | Attr("meaning").contains(query_lower)
        )

    items = []
    kwargs: Dict[str, Any] = {"FilterExpression": filter_expr}
    while True:
        response = table.scan(**kwargs)
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
    table = _get_table()

    if context:
        kwargs: Dict[str, Any] = {
            "IndexName": CONTEXT_INDEX,
            "KeyConditionExpression": Key("context").eq(context),
            "Limit": limit,
        }
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = table.query(**kwargs)
    else:
        kwargs = {"Limit": limit}
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = table.scan(**kwargs)

    return {
        "items": response.get("Items", []),
        "next_key": response.get("LastEvaluatedKey"),
        "count": response.get("Count", 0),
    }


def get_elements_by_context(context: str) -> List[Dict[str, Any]]:
    table = _get_table()
    items = []
    kwargs: Dict[str, Any] = {
        "IndexName": CONTEXT_INDEX,
        "KeyConditionExpression": Key("context").eq(context),
    }
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items
