from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import StatementController
from utils.schema_handler import SchemaHandler


class StatementResource:
    @SchemaHandler.validate_query_params("get_statement.json")
    def on_get(self, account_key: str, request: Request) -> JSONResponse:
        limit = request.query_params.get("limit")
        statement = StatementController().get(
            account_key, int(limit) if limit is not None else None, request.query_params.get("after")
        )
        return JSONResponse(content=jsonable_encoder(statement), status_code=http_status.HTTP_200_OK)
