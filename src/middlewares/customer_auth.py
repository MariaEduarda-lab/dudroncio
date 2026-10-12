from fastapi import FastAPI, Request

from constants import CUSTOMER_ENDPOINTS
from errors import InvalidCustomerCredentials
from errors.handlers import qi_exception_to_response
from utils.access_token import InvalidAccessToken, verify_access_token


def register_customer_auth_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def authenticate_customer(request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path not in CUSTOMER_ENDPOINTS:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token or " " in token:
            return qi_exception_to_response(InvalidCustomerCredentials())

        try:
            request.state.authenticated_principal = verify_access_token(token)
        except InvalidAccessToken:
            return qi_exception_to_response(InvalidCustomerCredentials())

        return await call_next(request)
