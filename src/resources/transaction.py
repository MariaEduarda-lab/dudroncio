from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import TransactionController
from utils.schema_handler import SchemaHandler

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


class TransactionResource:
    @SchemaHandler.validate("post_transaction.json")
    def on_post(self, account_key: str, payload: dict, request: Request) -> JSONResponse:
        transaction, created = TransactionController().send(
            account_key, payload, request.headers.get(IDEMPOTENCY_KEY_HEADER)
        )
        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK,
        )
