from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AuthenticationController
from utils.schema_handler import SchemaHandler


class AuthenticationResource:
    @SchemaHandler.validate("post_auth_token.json")
    def on_post(self, payload: dict) -> JSONResponse:
        token = AuthenticationController().authenticate(payload["email"], payload["password"])
        return JSONResponse(content=jsonable_encoder(token), status_code=http_status.HTTP_200_OK)
