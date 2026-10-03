from tests.utils import PayloadGenerator, RequestGenerator


class TestClientFlow:
    def test_refuses_invalid_payload(self):
        status, response = RequestGenerator.POST_client({})
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_creates_and_gets_client_without_operational_status_or_sensitive_fields(self):
        payload = PayloadGenerator.create_client_payload()

        status, response = RequestGenerator.POST_client(payload)
        assert status == 201
        assert set(response) == {"client_key"}

        status, client = RequestGenerator.GET_client(response["client_key"])
        assert status == 200
        assert client["cnpj"] == "".join(character for character in payload["cnpj"] if character.isalnum())
        assert client["legal_name"] == payload["legal_name"]
        assert "status" not in client
        assert "status_events" not in client

        representative = client["legal_representatives"][0]
        assert representative["cpf"].startswith("***.***.***-")
        assert representative["cpf"].endswith(payload["legal_representative"]["cpf"][-2:])
        assert "password" not in representative
        assert "password_hash" not in representative
        assert "status" not in representative
        assert "id" not in representative
        assert "id" not in client

    def test_refuses_invalid_cnpj(self):
        payload = PayloadGenerator.create_client_payload(cnpj="11.111.111/1111-11")

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002002"

    def test_refuses_duplicated_cnpj(self):
        first = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        second = PayloadGenerator.create_client_payload(cnpj=first["cnpj"])
        status, response = RequestGenerator.POST_client(second)
        assert status == 409
        assert response["code"] == "QIT002003"

    def test_refuses_duplicated_representative_email(self):
        first = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        second = PayloadGenerator.create_client_payload(
            representative_email=first["legal_representative"]["email"]
        )
        status, response = RequestGenerator.POST_client(second)
        assert status == 409
        assert response["code"] == "QIT002004"

    def test_invalid_representative_does_not_leave_partial_client(self):
        payload = PayloadGenerator.create_client_payload()
        payload["legal_representative"]["cpf"] = "111.111.111-11"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002005"

        payload["legal_representative"]["cpf"] = "529.982.247-25"
        status, _ = RequestGenerator.POST_client(payload)
        assert status == 201

    def test_client_not_found(self):
        status, response = RequestGenerator.GET_client("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT002001"
