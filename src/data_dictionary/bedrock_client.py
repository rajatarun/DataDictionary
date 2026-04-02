from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import boto3

from .models import DataElement

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
)

SYSTEM_PROMPT = """You are a DataDictionary expert. Given a description of an API field, \
return ONLY a valid JSON object with these exact fields (no markdown, no explanation):

- dataElement (string): the exact API field key name in camelCase or snake_case as described
- meaning (string): precise, unambiguous definition an AI agent can rely on without hallucination; \
include what the field represents, its purpose, lifecycle, and important semantics
- context (string): the API or service this field belongs to (e.g. OrdersAPI, CustomerService)
- dataType (string): one of exactly: string, number, boolean, array, object
- examples (array of strings): 2-3 concrete example values that illustrate real data
- constraints (string): format, validation, and immutability rules \
(e.g. "UUID v4, immutable after creation, max 36 characters")
- relatedElements (array of strings): names of semantically connected API field keys
- source (string): API name and version where this field originates (e.g. "Orders API v2.1")
- status (string): exactly "active"

Return ONLY the raw JSON object. No code blocks, no markdown, no explanation."""


def _get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    # Strip markdown code fences if model ignores instructions
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


async def generate_data_element(prompt: str) -> DataElement:
    client = _get_bedrock_client()

    response = client.converse(
        modelId=BEDROCK_MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {
                "role": "user",
                "content": [{"text": f"Generate a DataDictionary entry for: {prompt}"}],
            }
        ],
        inferenceConfig={
            "maxTokens": 1024,
            "temperature": 0.1,
        },
    )

    output_text = response["output"]["message"]["content"][0]["text"]
    raw = _extract_json(output_text)
    return DataElement.model_validate(raw)
