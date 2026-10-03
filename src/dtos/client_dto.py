from models import Client, LegalRepresentative


def _masked_cpf(cpf: str) -> str:
    return f"***.***.***-{cpf[-2:]}"


class ClientDTO:
    @staticmethod
    def only_key(client: Client) -> dict:
        return {"client_key": client.client_key}

    @staticmethod
    def obj_to_dict(client: Client) -> dict:
        response = {
            "client_key": client.client_key,
            "cnpj": client.cnpj,
            "legal_name": client.legal_name,
            "trade_name": client.trade_name,
            "client_type": client.client_type,
            "cnpj_status": client.cnpj_status,
            "primary_activity": client.primary_activity,
            "monthly_revenue_cents": client.monthly_revenue_cents,
            "email": client.email,
            "phone_number": client.phone_number,
            "address": dict(client.address),
            "created_at": client.created_at.isoformat(),
            "legal_representatives": [
                ClientDTO.representative_to_dict(representative)
                for representative in client.legal_representatives
            ],
        }
        return response

    @staticmethod
    def representative_to_dict(representative: LegalRepresentative) -> dict:
        return {
            "representative_key": representative.representative_key,
            "cpf": _masked_cpf(representative.cpf),
            "full_name": representative.full_name,
            "birthdate": representative.birthdate.isoformat(),
            "email": representative.email,
            "phone_number": representative.phone_number,
            "role": representative.role,
        }
