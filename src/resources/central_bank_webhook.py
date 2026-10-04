from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import TransactionController
from utils.schema_handler import SchemaHandler


class CentralBankWebhookResource:
    """Avisos que o Banco Central (fake) manda para o nosso banco."""

    @SchemaHandler.validate("post_central_bank_ted.json")
    def on_post_ted(self, payload: dict) -> JSONResponse:
        transaction, created = TransactionController().receive_ted(payload)
        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_central_bank_pix.json")
    def on_post_pix(self, payload: dict) -> JSONResponse:
        transaction, created = TransactionController().receive_pix(payload)
        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK,
        )
