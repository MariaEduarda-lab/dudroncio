import importlib

import pytest


@pytest.fixture
def access_token_module(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_SECRET", "unit-test-secret-with-at-least-32-characters")
    monkeypatch.setenv("ACCESS_TOKEN_TTL_SECONDS", "60")
    import constants
    import utils.access_token

    importlib.reload(constants)
    return importlib.reload(utils.access_token)


def test_round_trip_does_not_embed_account_key(access_token_module):
    token = access_token_module.create_access_token("PF", "client-key", now=100)
    principal = access_token_module.verify_access_token(token, now=159)
    assert principal.kind == "PF"
    assert principal.subject == "client-key"

    encoded_payload = token.split(".")[0]
    payload = access_token_module.json.loads(access_token_module._decode(encoded_payload))
    assert set(payload) == {"exp", "iat", "kind", "sub"}


def test_expired_token_is_rejected(access_token_module):
    token = access_token_module.create_access_token("PF", "client-key", now=100)
    with pytest.raises(access_token_module.InvalidAccessToken):
        access_token_module.verify_access_token(token, now=160)


def test_tampered_and_malformed_tokens_are_rejected(access_token_module):
    token = access_token_module.create_access_token("REPRESENTATIVE", "representative-key", now=100)
    for invalid in (token + "x", "not-a-token", ".", ""):
        with pytest.raises(access_token_module.InvalidAccessToken):
            access_token_module.verify_access_token(invalid, now=101)
