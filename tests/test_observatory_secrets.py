"""
Tests for data_dictionary.observatory's mcp-observatory 0.3.0 integration.

data_dictionary.observatory builds its proposer/verifier/token-manager triple
(now via mcp_observatory.aws.build_gate) at *import time*, so the fail-closed
secret behaviour can only be observed by controlling the environment before
the module is imported. Every test that cares about that reloads the module
under a monkeypatched environment and clears it from sys.modules afterwards
so later tests import a clean copy.
"""

from __future__ import annotations

import importlib
import sys

import pytest

MODULE_NAME = "data_dictionary.observatory"


def _reload_observatory():
    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("OBSERVATORY_SECRET_KEY", raising=False)
    monkeypatch.delenv("OBSERVATORY_BLOCK_THRESHOLD", raising=False)
    monkeypatch.delenv("MCP_OBSERVATORY_ALLOW_DEV_SECRET", raising=False)
    monkeypatch.delenv("MCP_OBSERVATORY_COMMIT_SECRET", raising=False)
    yield
    sys.modules.pop(MODULE_NAME, None)


def test_import_fails_closed_without_secret_or_dev_flag():
    """No more hardcoded 'change-me-in-production' fallback: an unset
    OBSERVATORY_SECRET_KEY must raise at construction time.
    """
    from mcp_observatory.utils.secrets import InsecureDefaultSecretError

    with pytest.raises(InsecureDefaultSecretError):
        _reload_observatory()


def test_import_succeeds_with_dev_flag_for_local_and_test_use(monkeypatch):
    monkeypatch.setenv("MCP_OBSERVATORY_ALLOW_DEV_SECRET", "1")
    module = _reload_observatory()
    assert module._proposer is not None
    assert module._verifier is not None
    assert module._token_manager.secret == b"dev-commit-secret"


def test_import_succeeds_with_real_secret_set(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_SECRET_KEY", "a-real-strong-secret-value")
    module = _reload_observatory()
    assert module._token_manager.secret == b"a-real-strong-secret-value"


def test_build_gate_uses_data_dictionarys_existing_env_var_names(monkeypatch):
    """build_gate must read OBSERVATORY_SECRET_KEY / OBSERVATORY_BLOCK_THRESHOLD
    (this repo's already-deployed env var names), not the library's own
    MCP_OBSERVATORY_* defaults, so the swap needed no template.yaml changes.
    """
    monkeypatch.setenv("OBSERVATORY_SECRET_KEY", "a-real-strong-secret-value")
    monkeypatch.setenv("OBSERVATORY_BLOCK_THRESHOLD", "0.9")
    module = _reload_observatory()
    assert module._proposer.config.block_threshold == 0.9


def test_proposer_and_verifier_share_storage_and_token_manager(monkeypatch):
    monkeypatch.setenv("OBSERVATORY_SECRET_KEY", "a-real-strong-secret-value")
    module = _reload_observatory()
    assert module._proposer.token_manager is module._token_manager
    assert module._verifier.token_manager is module._token_manager
    assert module._proposer.storage is module._verifier.storage
