# Architecture Decision Records (ADR)

This document captures high-level architectural decisions for the DataDictionary repository.

---

## ADR-001: Build an MCP-native DataDictionary service

- **Status:** Accepted
- **Date:** 2026-04-23

### Context
The service must expose a machine-friendly interface for AI agents to read and write field definitions while preserving strict schema semantics.

### Decision
Implement the service as an MCP server using `FastMCP`, with tool-based operations for both write and read workflows.

### Consequences
- Native compatibility with MCP clients.
- Clear separation between tools and underlying persistence/model logic.
- Requires disciplined tool contract management as features evolve.

---

## ADR-002: Gate writes behind a proposal + commit verification flow

- **Status:** Accepted
- **Date:** 2026-04-23

### Context
AI-generated writes can be unsafe or unintended; direct writes from free-form prompts are high risk.

### Decision
Use MCP Observatory to enforce a two-step write flow:
1. Propose (`propose_data_element`)
2. Commit (`commit_data_element`) with token verification

### Consequences
- Adds safety and explicit user intent confirmation.
- Introduces additional flow complexity for clients.
- Current proposal storage uses in-memory backend and is non-durable.

---

## ADR-003: Use DynamoDB as the source of truth

- **Status:** Accepted
- **Date:** 2026-04-23

### Context
The system needs low-ops, scalable key-value/document storage with straightforward AWS-native deployment.

### Decision
Store `DataElement` records in DynamoDB with:
- Partition key: `dataElement`
- GSI: `context-index` on (`context`, `dataElement`)

### Consequences
- Simple point lookups and context-scoped queries.
- Search is implemented via scan + filter and may require redesign for very large datasets.
- Tight coupling to AWS services.

---

## ADR-004: Generate definitions with Amazon Bedrock and validate via Pydantic

- **Status:** Accepted
- **Date:** 2026-04-23

### Context
Generating structured field definitions from natural language requires LLM support, but outputs must be validated against a strict schema.

### Decision
Use Bedrock Runtime `converse` to generate JSON, then parse/validate into `DataElement` with Pydantic v2.

### Consequences
- Faster authoring of high-quality data dictionary entries.
- Runtime dependency on Bedrock model availability/permissions.
- Validation failures are surfaced early if model output is malformed.

---

## ADR-005: Deploy as AWS Lambda behind Function URL using SAM

- **Status:** Accepted
- **Date:** 2026-04-23

### Context
Need cost-efficient, minimal-ops deployment with IaC and easy stage-based rollout.

### Decision
Package as a SAM application:
- Python 3.12 Lambda
- Mangum adapter for MCP ASGI app
- Function URL for HTTP access
- Stage-specific table naming and config parameters

### Consequences
- Simple serverless deployment and repeatable infrastructure.
- Public Function URL (`AuthType: NONE`) requires compensating controls for production environments.
- Cold starts and ephemeral memory affect proposal lifecycle in current design.

---

## ADR-006: Keep a canonical shared schema in `models.py`

- **Status:** Accepted
- **Date:** 2026-04-23

### Context
Multiple components (Bedrock generation, validation, persistence, API tools) must agree on field semantics.

### Decision
Define a single `DataElement` Pydantic model as the canonical schema and reuse it across generation and storage layers.

### Consequences
- Strong consistency across the codebase.
- Easier future schema evolution with one source of truth.
- Backward-compatibility planning is needed for field changes.
