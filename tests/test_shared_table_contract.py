"""DataDictionary's position on the shared OBSERVATORY_METRICS contract.

The shared ``OBSERVATORY_METRICS`` table (provisioned by the
``tarun-teamweave-shared`` stack) is written by several services and read by
several dashboards, none of which can see each other's code, so its item shape
is a cross-repository interface. It is pinned in ``contracts/`` — a verbatim
copy of the canonical files in ``rajatarun/mcp-observatory``.

**DataDictionary does not write to that table.** This was checked rather than
assumed: the only ``put_item`` call sites in the package are in
``dynamo_client.py`` and both target DataDictionary's *own* tables
(``TABLE_NAME``, keyed on ``dataElement``; ``PROPOSALS_TABLE_NAME``, keyed on
``proposal_id``). ``data_dictionary/observatory.py`` uses mcp-observatory only
for the propose/commit gate and emits no span telemetry, and ``template.yaml``
grants no access to the shared table.

So there is no writer here whose emitted ``pk`` could be checked against the
contract, and the sibling repo's upper-case ``PK``/``SK`` key bug has no
counterpart in this repo. Rather than assert nothing, these tests pin that
state so it cannot drift unnoticed:

1. the vendored contract is the version its siblings check against;
2. no module in this package writes to the shared table (if one is added, this
   test fails and points the author at the conformance checks);
3. the two real writers this repo *does* have carry no upper-case ``PK``/``SK``
   key attributes, so the sibling bug cannot arrive here by copy-paste;
4. the namespace a future exporter would have to target to be *read* is
   recorded, since writing to an unread namespace is the other half of the
   sibling repo's problem.

Test style follows the existing suite: real code paths, monkeypatched module
globals, no moto (it is a declared dev dependency but is not installed in CI).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.conformance import check_item, load_contract, readers_for

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "src" / "data_dictionary"


class _CapturingTable:
    """Stand-in for ``boto3.resource('dynamodb').Table(...)`` that records items."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def put_item(self, Item: dict) -> dict:  # noqa: N803 - boto3 kwarg name
        self.items.append(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(self, Key: dict) -> dict:  # noqa: N803 - boto3 kwarg name
        return {}


@pytest.fixture
def dynamo_client(monkeypatch):
    from data_dictionary import dynamo_client as module

    elements = _CapturingTable()
    proposals = _CapturingTable()
    monkeypatch.setattr(module, "_table", elements)
    monkeypatch.setattr(module, "_proposals_table", proposals)
    module.captured_elements = elements
    module.captured_proposals = proposals
    return module


# ---------------------------------------------------------------------------
# 1. The vendored copy matches what the siblings check against
# ---------------------------------------------------------------------------


def test_vendored_contract_is_the_shared_version():
    """A vendored copy that has drifted is worse than no copy at all."""
    contract = load_contract()
    assert contract["contract"] == "observatory_metrics_item"
    assert contract["version"] == "1.0.0"
    assert contract["key_schema"] == {
        **contract["key_schema"],
        "partition_key": "pk",
        "sort_key": "sk",
    }


def test_vendored_files_are_verbatim_json():
    raw = json.loads((REPO_ROOT / "contracts" / "observatory_metrics_item.json").read_text())
    assert raw["canonical_home"].startswith("https://github.com/rajatarun/mcp-observatory")


# ---------------------------------------------------------------------------
# 2. This repo has no shared-table writer
# ---------------------------------------------------------------------------


def test_package_does_not_write_to_the_shared_metrics_table():
    """Pins the CURRENT truth: DataDictionary emits no OBSERVATORY_METRICS rows.

    If someone adds a span exporter here, this test fails — which is the point.
    The failure message is the pointer to the conformance assertions above and
    to the namespace question in ``test_readable_namespace_is_recorded``, both
    of which a new writer has to satisfy to be worth deploying.
    """
    offenders = [
        path.name
        for path in sorted(PACKAGE_DIR.glob("*.py"))
        if "OBSERVATORY_METRICS" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"{offenders} now reference the shared OBSERVATORY_METRICS table. "
        "Assert the emitted item with contracts.conformance.check_item and pick "
        "a namespace that contracts.conformance.readers_for says is read."
    )


# ---------------------------------------------------------------------------
# 3. The real writers carry no upper-case key attributes
# ---------------------------------------------------------------------------


def test_data_element_writer_emits_no_upper_case_key_attributes(dynamo_client):
    """Regression guard against the sibling repo's bug arriving by copy-paste.

    ToolWeave's exporter spelled its key attributes ``PK``/``SK`` while the
    shared table declares ``pk``/``sk``; DynamoDB attribute names are case
    sensitive, so every write was rejected and swallowed. This repo's element
    writer is keyed on ``dataElement`` and has never had ``PK``/``SK``. The
    assertion keeps it that way.
    """
    from data_dictionary.models import DataElement

    dynamo_client.put_data_element(
        DataElement(
            dataElement="customerId",
            meaning="UUID v4 identifier assigned to a customer at account creation.",
            context="OrdersAPI",
            dataType="string",
        )
    )
    item = dynamo_client.captured_elements.items[0]

    assert "PK" not in item and "SK" not in item
    assert item["dataElement"] == "customerId"


def test_proposal_writer_emits_no_upper_case_key_attributes(dynamo_client):
    """Same guard for the proposals table, keyed on ``proposal_id``."""
    dynamo_client.save_proposal("prop-123", {"tool_name": "commit_data_element", "tool_args": {}})
    item = dynamo_client.captured_proposals.items[0]

    assert "PK" not in item and "SK" not in item
    assert item["proposal_id"] == "prop-123"


def test_local_writers_are_not_shared_table_items(dynamo_client):
    """The local items are *not* contract items, and the contract says so loudly.

    Running ``check_item`` on them is not a failure of this repo — it documents
    why the shared contract does not govern these two tables. The emitted items
    carry no ``pk`` at all, so there is no namespace to look up with
    ``readers_for``; that is the honest answer for DataDictionary, as opposed to
    ToolWeave, whose ``WRAPPER#`` pk resolves to an empty reader list.
    """
    dynamo_client.save_proposal("prop-456", {"tool_name": "commit_data_element"})
    item = dynamo_client.captured_proposals.items[0]

    assert "pk" not in item and "sk" not in item
    assert readers_for(item.get("pk") or "") == []

    problems = check_item(item, load_contract())
    assert any(problem.startswith("I1") for problem in problems)


# ---------------------------------------------------------------------------
# 4. Which namespace a future exporter would have to use to be read
# ---------------------------------------------------------------------------


def test_readable_namespace_is_recorded_for_any_future_exporter():
    """Records which namespace actually reaches a dashboard, as of contract 1.0.0.

    Getting the key spelling right only makes a write *succeed*. Choosing a
    namespace no reader enumerates makes it succeed and stay invisible — which
    is the state ToolWeave is in even after its key-case fix. Anything added
    here should target ``OBSERVATORY#{operation}``, the only namespace with
    registered readers, unless the portfolio-wide namespace decision has landed
    and this contract has been re-vendored with a different answer.
    """
    assert readers_for("OBSERVATORY#invoke_model") != []
    assert readers_for("WRAPPER#invoke_agent") == []
    assert readers_for("SPAN#some_tool") == []
