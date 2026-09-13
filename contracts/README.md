# Vendored contracts

**Canonical home: [`rajatarun/mcp-observatory`](https://github.com/rajatarun/mcp-observatory) → `contracts/`.**

The files in this directory are **verbatim copies** and are not edited here.
Fix problems upstream in mcp-observatory and re-vendor; a local edit silently
forks the interface the shared table depends on.

| File | Purpose |
|------|---------|
| `observatory_metrics_item.json` | Item contract (v1.0.0) for the shared `OBSERVATORY_METRICS` DynamoDB table provisioned by the `tarun-teamweave-shared` stack. |
| `conformance.py` | Dependency-free checker (`load_contract`, `check_item`, `readers_for`) run by `tests/test_shared_table_contract.py`. |

## Why it is vendored rather than imported

The shared table has writers in more than one language and several readers that
build dashboards from it, none of which can see each other's code. The item
shape is therefore a cross-repository interface. Each consumer keeps a copy
next to a conformance test so its writer is checked against the same file its
siblings check against, with no runtime dependency and no network access.

Vendored copies must carry the same `version` string as upstream (`1.0.0`).

## What DataDictionary asserts against it

**DataDictionary does not currently write to the shared `OBSERVATORY_METRICS`
table at all.** It uses mcp-observatory only for the propose/commit gate
(`src/data_dictionary/observatory.py`), which emits no span telemetry. Its two
`put_item` call sites in `src/data_dictionary/dynamo_client.py` write to
DataDictionary's *own* tables under their own key schemas (`dataElement` and
`proposal_id`), which this contract does not govern.

`tests/test_shared_table_contract.py` therefore pins that fact: it asserts that
no module in this package writes to the shared table, and it checks the two
real writers it does have for the upper-case `PK`/`SK` spelling that broke the
sibling repo, so the bug cannot arrive here by copy-paste. The contract is
vendored now so that the conformance assertions already exist the day a span
exporter is added.
