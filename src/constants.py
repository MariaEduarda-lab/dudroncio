import os


SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))

# Onde moram os arquivos de schema — os .json que descrevem o formato
# que cada requisicao precisa ter. Quem le essa pasta e o
# src/utils/schema_handler.py.
SCHEMA_PATH = os.path.join(SERVICE_ROOT, "schemas")

APP_ENV = os.environ.get("APP_ENV", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "bootcamp-api")

DATABASE_URL = os.environ.get("DATABASE_URL")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("ACCESS_TOKEN_SECRET")
LOCAL_ACCESS_TOKEN_SECRET = "local-access-token-secret-change-me-2026"

try:
    ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("ACCESS_TOKEN_TTL_SECONDS", "3600"))
except ValueError as exception:
    raise EnvironmentError("ACCESS_TOKEN_TTL_SECONDS precisa ser um número inteiro positivo.") from exception

if ACCESS_TOKEN_TTL_SECONDS <= 0:
    raise EnvironmentError("ACCESS_TOKEN_TTL_SECONDS precisa ser um número inteiro positivo.")

# Rotas públicas: não exigem INTERNAL-TOKEN nem Bearer. Além da raiz e do
# health check, o login precisa ser acessível antes de existir um Bearer.
BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
    "/auth/token",
]

# Estas rotas usam a identidade do cliente. Elas nunca aceitam o token
# interno como substituto e nunca recebem uma chave de conta como escopo.
CUSTOMER_ENDPOINTS = [
    "/transactions",
    "/statement",
]

REQUIRED_VARIABLES = ["DATABASE_URL", "INTERNAL_TOKEN", "ACCESS_TOKEN_SECRET"]


def check_variables():
    missing = []
    for name in REQUIRED_VARIABLES:
        if not globals().get(name):
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Faltam variáveis de ambiente: {', '.join(missing)}. "
            "Rodando com 'docker compose up' elas já vêm preenchidas. "
            "Fora do Docker, copie o .env.example para .env."
        )

    if len(ACCESS_TOKEN_SECRET) < 32:
        raise EnvironmentError("ACCESS_TOKEN_SECRET precisa ter pelo menos 32 caracteres.")
    if ACCESS_TOKEN_SECRET == INTERNAL_TOKEN:
        raise EnvironmentError("ACCESS_TOKEN_SECRET precisa ser diferente de INTERNAL_TOKEN.")
    if APP_ENV != "local" and ACCESS_TOKEN_SECRET == LOCAL_ACCESS_TOKEN_SECRET:
        raise EnvironmentError("ACCESS_TOKEN_SECRET de exemplo só pode ser usado em APP_ENV=local.")

# Codigo do nosso banco nas TEDs. Uma TED com este codigo e para um cliente
# nosso e e liquidada aqui dentro, sem passar pelo Banco Central.
OUR_BANK_CODE = "999"

# O Banco Central fake: quem confirma ou recusa os envios para outro banco.
# O envio espera a resposta no maximo CENTRAL_BANK_API_TIMEOUT segundos;
# sem resposta, o pedido e recusado (TRA-18).
CENTRAL_BANK_API_URL = os.environ.get("CENTRAL_BANK_API_URL", "http://localhost:1080")
CENTRAL_BANK_API_INTERNAL_TOKEN = os.environ.get("CENTRAL_BANK_API_INTERNAL_TOKEN", "default_token")
CENTRAL_BANK_API_TIMEOUT = int(os.environ.get("CENTRAL_BANK_API_TIMEOUT", "5"))
