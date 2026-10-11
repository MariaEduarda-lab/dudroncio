from constants import ACCESS_TOKEN_TTL_SECONDS
from controllers.base_controller import BaseController
from errors import InvalidCustomerCredentials
from models import Client
from repositories import ClientRepository
from utils.access_token import create_access_token
from utils.password import hash_password, verify_password


# Um login desconhecido precisa pagar o mesmo Argon2id de uma senha errada
# para que o tempo de resposta nao denuncie se o e-mail esta cadastrado.
# Este hash nasce uma vez no startup e nunca representa uma credencial real.
DUMMY_PASSWORD_HASH = hash_password("invalid-customer-credential-dummy")


class AuthenticationController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)

    def authenticate(self, raw_email: str, password: str) -> dict:
        email = raw_email.strip().lower()
        client = self.client_repository.get_by_email(email)
        representative = self.client_repository.get_representative_by_email(email)

        if client is not None and client.person_type == Client.PF and client.password_hash:
            password_hash = client.password_hash
            kind = "PF"
            subject = str(client.client_key)
            identity_exists = True
        elif representative is not None:
            password_hash = representative.password_hash
            kind = "REPRESENTATIVE"
            subject = str(representative.representative_key)
            identity_exists = True
        else:
            password_hash = DUMMY_PASSWORD_HASH
            kind = ""
            subject = ""
            identity_exists = False

        if not verify_password(password, password_hash) or not identity_exists:
            raise InvalidCustomerCredentials()
        return {
            "access_token": create_access_token(kind, subject),
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        }
