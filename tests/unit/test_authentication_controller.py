import importlib
import os

import pytest

_VARIABLES = {
    "DATABASE_URL": "postgresql+psycopg2://test:test@localhost/test",
    "INTERNAL_TOKEN": "unit-internal-token",
    "ACCESS_TOKEN_SECRET": "unit-test-secret-with-at-least-32-characters",
}
_previous = {name: os.environ.get(name) for name in _VARIABLES}
for name, value in _VARIABLES.items():
    os.environ[name] = value

import constants
importlib.reload(constants)
from controllers import authentication_controller
from errors import InvalidCustomerCredentials

for name, value in _previous.items():
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class MissingIdentityRepository:
    def get_by_email(self, email):
        return None

    def get_representative_by_email(self, email):
        return None


def test_unknown_identity_still_runs_password_verification(monkeypatch):
    verified_hashes = []
    monkeypatch.setattr(
        authentication_controller,
        "verify_password",
        lambda password, password_hash: verified_hashes.append(password_hash) or False,
    )
    controller = authentication_controller.AuthenticationController.__new__(
        authentication_controller.AuthenticationController
    )
    controller.client_repository = MissingIdentityRepository()

    with pytest.raises(InvalidCustomerCredentials):
        controller.authenticate("unknown@example.com", "wrong-password")

    assert verified_hashes == [authentication_controller.DUMMY_PASSWORD_HASH]
