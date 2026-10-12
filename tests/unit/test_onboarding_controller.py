import os
import importlib

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

from controllers.onboarding_controller import OnboardingController

for name, value in _previous.items():
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class FakeSession:
    def __init__(self):
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FailingAccountCreator:
    def create(self, client):
        raise RuntimeError("forced account opening failure")


class FakeClientCreator:
    def create(self, raw_client_data):
        return object(), {"person_type": "PF"}


def test_failure_after_client_and_registered_email_flush_rolls_back_without_commit():
    # registered_email is inserted by a database trigger in the same flush/
    # transaction as client; one rollback therefore covers both records.
    controller = OnboardingController.__new__(OnboardingController)
    controller.session = FakeSession()
    controller.client_creator = FakeClientCreator()
    controller.account_creator = FailingAccountCreator()

    with pytest.raises(RuntimeError, match="forced account opening failure"):
        controller.create({})

    assert controller.session.flushes == 1
    assert controller.session.rollbacks == 1
    assert controller.session.commits == 0
