import inspect

from mcp_observatory.proposal_commit import CommitTokenManager
from mcp_observatory.proposal_commit.verifier import CommitVerifier
from mcp_observatory.token import issuer


def test_commit_token_manager_location_and_constructor():
    """Ensure we use the current mcp-observatory token API surface."""
    assert CommitTokenManager is not None
    params = inspect.signature(CommitTokenManager).parameters
    assert "secret" in params


def test_commit_verifier_requires_tool_name():
    """Regression guard for verify_commit call shape."""
    params = inspect.signature(CommitVerifier.verify_commit).parameters
    assert "tool_name" in params


def test_legacy_commit_token_config_removed():
    """Documents why imports from mcp_observatory.token.issuer fail in Lambda."""
    assert not hasattr(issuer, "CommitTokenConfig")
