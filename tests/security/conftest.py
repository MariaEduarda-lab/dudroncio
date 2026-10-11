import os

import psycopg2
import pytest


OWNER_URL = os.environ.get(
    "SECURITY_OWNER_DATABASE_URL",
    "postgresql://database_owner:security-owner-local-only@127.0.0.1:55432/security_test",
)
RUNTIME_URL = os.environ.get(
    "SECURITY_RUNTIME_DATABASE_URL",
    "postgresql://application_user:security-runtime-local-only@127.0.0.1:55432/security_test",
)


def _connection_or_skip(url: str):
    try:
        connection = psycopg2.connect(url, connect_timeout=2)
    except psycopg2.OperationalError:
        pytest.skip(
            "banco de seguranca indisponivel; suba docker-compose.security.yml",
            allow_module_level=True,
        )
    connection.autocommit = True
    return connection


@pytest.fixture(scope="session")
def owner_connection():
    connection = _connection_or_skip(OWNER_URL)
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def runtime_connection():
    connection = _connection_or_skip(RUNTIME_URL)
    yield connection
    connection.close()

