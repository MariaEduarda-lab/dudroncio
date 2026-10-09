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

# Rotas públicas: não exigem o header INTERNAL-TOKEN. São as duas que
# precisam responder pra quem ainda não tem token nenhum: a raiz, que
# diz quem é este serviço, e o health check, que o Docker consulta pra
# saber se a API já está de pé.
BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
]

REQUIRED_VARIABLES = ["DATABASE_URL", "INTERNAL_TOKEN"]


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

# Codigo do nosso banco nas TEDs. Uma TED com este codigo e para um cliente
# nosso e e liquidada aqui dentro, sem passar pelo Banco Central.
OUR_BANK_CODE = "999"

# O Banco Central fake: quem confirma ou recusa os envios para outro banco.
# O envio espera a resposta no maximo CENTRAL_BANK_API_TIMEOUT segundos;
# sem resposta, o pedido e recusado (TRA-18).
CENTRAL_BANK_API_URL = os.environ.get("CENTRAL_BANK_API_URL", "http://localhost:1080")
CENTRAL_BANK_API_INTERNAL_TOKEN = os.environ.get("CENTRAL_BANK_API_INTERNAL_TOKEN", "default_token")
CENTRAL_BANK_API_TIMEOUT = int(os.environ.get("CENTRAL_BANK_API_TIMEOUT", "5"))
