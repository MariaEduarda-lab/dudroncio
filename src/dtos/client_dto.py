from models import Client, LegalRepresentative


def _masked_cpf(cpf: str) -> str:
    return f"***.***.***-{cpf[-2:]}"


class ClientDTO:
    @staticmethod
    def only_key(client: Client) -> dict:
        return {"client_key": str(client.client_key)}

    @staticmethod
    def obj_to_dict(client: Client) -> dict:
        response = {
            "client_key": str(client.client_key),
            "person_type": client.person_type,
            "monthly_income_cents": client.monthly_income_cents,
            "email": client.email,
            "phone_number": client.phone_number,
            "address": dict(client.address),
            "created_at": client.created_at.isoformat(),
            "updated_at": client.updated_at.isoformat(),
        }

        if client.person_type == Client.PF:
            # O CPF e dado pessoal: sai mascarado, como o do representante.
            response["document_number"] = _masked_cpf(client.document_number)
            response["full_name"] = client.full_name
            response["birthdate"] = client.birthdate.isoformat()
            return response

        # O CNPJ e publico (consta na Receita) e sai inteiro.
        response["document_number"] = client.document_number
        response["legal_name"] = client.legal_name
        response["trade_name"] = client.trade_name
        response["cnpj_status"] = client.cnpj_status
        response["primary_activity"] = client.primary_activity
        response["legal_representatives"] = [
            ClientDTO.representative_to_dict(representative) for representative in client.legal_representatives
        ]
        return response

    @staticmethod
    def representative_to_dict(representative: LegalRepresentative) -> dict:
        return {
            "representative_key": str(representative.representative_key),
            "cpf": _masked_cpf(representative.cpf),
            "full_name": representative.full_name,
            "birthdate": representative.birthdate.isoformat(),
            "email": representative.email,
            "phone_number": representative.phone_number,
            "role": representative.role,
            "created_at": representative.created_at.isoformat(),
            "updated_at": representative.updated_at.isoformat(),
        }
