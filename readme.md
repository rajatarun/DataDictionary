# DataDictionary MCP Server

DataDictionary is a Python-based MCP server that stores and retrieves API field definitions (`DataElement`) backed by DynamoDB, with AI-assisted draft generation through Amazon Bedrock and proposal/commit safety gates through MCP Observatory.

## What this repository provides

- **MCP tools for writes and reads** exposed by `FastMCP` in `src/data_dictionary/server.py`.
- **AI-assisted element generation** through Bedrock (`src/data_dictionary/bedrock_client.py`).
- **Proposal + commit verification flow** via MCP Observatory (`src/data_dictionary/observatory.py`).
- **Persistent storage** in DynamoDB (`src/data_dictionary/dynamo_client.py`).
- **Serverless deployment** with AWS SAM (`template.yaml`, `samconfig.toml`).

## Data model

A `DataElement` includes:

- `dataElement` (field name)
- `meaning`
- `context`
- `dataType` (`string | number | boolean | array | object`)
- `examples`
- `constraints`
- `relatedElements`
- `source`
- `status` (`active | deprecated`)
- timestamps (`createdAt`, `updatedAt`)

See `src/data_dictionary/models.py` for the canonical schema.

## MCP tools

### Write path (guarded)

1. `propose_data_element(prompt)`
   - Uses Bedrock to generate a structured `DataElement` from natural language.
   - Sends that candidate through Observatory proposal checks.
   - Returns `proposal_id` and `commit_token` when allowed.
2. `commit_data_element(proposal_id, commit_token)`
   - Re-hydrates proposal args.
   - Verifies token and payload integrity.
   - Persists item to DynamoDB.

### Read path (direct)

- `get_data_element(dataElement)`
- `search_data_elements(query)`
- `list_data_elements(context=None, limit=50, last_evaluated_key=None)`
- `get_elements_by_context(context)`

## Architecture at a glance

- **Lambda runtime:** Python 3.12
- **Entrypoint:** `data_dictionary.server.lambda_handler` via Mangum wrapping MCP ASGI app
- **DynamoDB table:** `DataDictionary-<Stage>`
  - PK: `dataElement`
  - GSI: `context-index` (`context` + `dataElement`)
- **Bedrock model:** configurable with `BEDROCK_MODEL_ID`
- **Commit safety:** HMAC-based token flow in MCP Observatory with in-memory proposal storage

## Prerequisites

- Python 3.12+
- AWS CLI configured
- AWS SAM CLI
- Access to:
  - DynamoDB
  - Bedrock model specified by `BEDROCK_MODEL_ID`

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For editable install using `pyproject.toml` metadata:

```bash
pip install -e .
```

## Key environment variables

- `TABLE_NAME` (default: `DataDictionary-prod`)
- `AWS_REGION` (default: `us-east-1`)
- `OBSERVATORY_SECRET_KEY` (**set in non-dev environments**)
- `BEDROCK_MODEL_ID` (default: `anthropic.claude-3-haiku-20240307-v1:0`)
- `STAGE`
- `AWS_ACCOUNT_ID`

## Build and deploy with SAM

Build:

```bash
sam build
```

Deploy to prod profile from `samconfig.toml`:

```bash
sam deploy --config-env prod
```

Deploy to dev:

```bash
sam deploy --config-env dev
```

The template exports:

- Function URL
- DynamoDB table name
- Lambda ARN

## Repository layout

```text
.
├── readme.md
├── decisions.md
├── template.yaml
├── samconfig.toml
├── pyproject.toml
├── requirements.txt
└── src
    ├── requirements.txt
    └── data_dictionary
        ├── server.py
        ├── models.py
        ├── dynamo_client.py
        ├── bedrock_client.py
        ├── observatory.py
        └── __init__.py
```

## Notes and operational caveats

- Proposal storage is currently **in-memory**, so pending proposals are not durable across cold starts or multiple Lambda instances.
- `search_data_elements` uses DynamoDB `scan` with filter expressions; this is simple but can become expensive at larger table sizes.
- Function URL is configured with `AuthType: NONE` in the SAM template; ensure upstream controls are in place if used in production.
