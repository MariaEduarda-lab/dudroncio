import sys
from pathlib import Path

# Testes unitarios importam funcoes puras de src/ (calculos isolados, como
# digitos verificadores). Os testes de integracao continuam black box.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
