from __future__ import annotations

from typing import Any, Dict

from mcp_observatory.aws import build_gate

# mcp-observatory>=0.3.0: build_gate wires InMemoryStorage/CommitTokenManager/
# ToolProposer/CommitVerifier exactly as this module used to by hand, but
# resolves the HMAC secret through mcp_observatory.utils.secrets.resolve_secret,
# which raises InsecureDefaultSecretError at construction time instead of the
# hardcoded "change-me-in-production" fallback this module previously used
# when OBSERVATORY_SECRET_KEY was unset. Set OBSERVATORY_SECRET_KEY in every
# deployed environment; set MCP_OBSERVATORY_ALLOW_DEV_SECRET=1 for local runs
# and tests only.
_proposer, _verifier, _token_manager = build_gate(
    secret_env="OBSERVATORY_SECRET_KEY",
    block_threshold_env="OBSERVATORY_BLOCK_THRESHOLD",
)


async def propose(tool_name: str, tool_args: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    """Propose a write operation via MCP Observatory.

    Returns a dict with keys: status, proposal_id, commit_token (if allowed), signals.
    Persists proposal data to DynamoDB so it survives across Lambda invocations.
    """
    result = await _proposer.propose(
        tool_name=tool_name,
        tool_args=tool_args,
        prompt=prompt,
        candidate_output_a=f"Store data element: {tool_args.get('dataElement', '')}",
        candidate_output_b=f"Add {tool_args.get('dataElement', '')} to DataDictionary",
    )

    proposal_id = result.get("proposal_id")
    if proposal_id:
        from . import dynamo_client
        dynamo_client.save_proposal(
            proposal_id,
            {"tool_name": tool_name, "tool_args": tool_args},
        )

    return result


async def verify(proposal_id: str, commit_token: str, tool_name: str, tool_args: Dict[str, Any]):
    """Verify a commit token against its proposal.

    Returns a CommitVerification object with .ok (bool) and optional .failure_reason.
    """
    return await _verifier.verify_commit(
        proposal_id=proposal_id,
        commit_token=commit_token,
        tool_name=tool_name,
        tool_args=tool_args,
    )


async def get_proposal(proposal_id: str) -> Dict[str, Any] | None:
    """Retrieve a stored proposal by ID from DynamoDB."""
    from . import dynamo_client
    return dynamo_client.get_proposal_data(proposal_id)
