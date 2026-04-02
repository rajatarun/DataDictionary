from __future__ import annotations

import os
from typing import Any, Dict

from mcp_observatory import ToolProposer
from mcp_observatory.proposal_commit.proposer import ProposalConfig
from mcp_observatory.proposal_commit.storage import InMemoryStorage
from mcp_observatory.proposal_commit import CommitTokenManager
from mcp_observatory.proposal_commit.verifier import CommitVerifier

_SECRET_KEY = os.environ.get("OBSERVATORY_SECRET_KEY", "change-me-in-production")

_storage = InMemoryStorage()
_token_manager = CommitTokenManager(secret=_SECRET_KEY)
_proposer = ToolProposer(
    storage=_storage,
    config=ProposalConfig(),
    token_manager=_token_manager,
)
_verifier = CommitVerifier(
    storage=_storage,
    token_manager=_token_manager,
)


async def propose(tool_name: str, tool_args: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    """Propose a write operation via MCP Observatory.

    Returns a dict with keys: status, proposal_id, commit_token (if allowed), signals.
    """
    return await _proposer.propose(
        tool_name=tool_name,
        tool_args=tool_args,
        prompt=prompt,
        candidate_output_a=f"Store data element: {tool_args.get('dataElement', '')}",
        candidate_output_b=f"Add {tool_args.get('dataElement', '')} to DataDictionary",
    )


def verify(proposal_id: str, commit_token: str, tool_name: str, tool_args: Dict[str, Any]):
    """Verify a commit token against its proposal.

    Returns a CommitVerification object with .ok (bool) and optional .failure_reason.
    """
    return _verifier.verify_commit(
        proposal_id=proposal_id,
        commit_token=commit_token,
        tool_name=tool_name,
        tool_args=tool_args,
    )


async def get_proposal(proposal_id: str) -> Dict[str, Any] | None:
    """Retrieve a stored proposal by ID to recover tool_args on commit."""
    return await _storage.get_proposal(proposal_id)
