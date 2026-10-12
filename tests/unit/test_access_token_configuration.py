import os
import subprocess
import sys
from pathlib import Path


def test_known_local_signing_secret_is_rejected_outside_local_environment():
    source_directory = str(Path(__file__).resolve().parents[2] / "src")
    environment = {
        **os.environ,
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg2://test:test@localhost/test",
        "INTERNAL_TOKEN": "different-internal-token",
        "ACCESS_TOKEN_SECRET": "local-access-token-secret-change-me-2026",
        "PYTHONPATH": source_directory,
    }
    result = subprocess.run(
        [sys.executable, "-c", "import constants; constants.check_variables()"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "só pode ser usado" in result.stderr
