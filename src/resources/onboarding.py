from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import OnboardingController
from utils.schema_handler import SchemaHandler


class OnboardingResource:
    @SchemaHandler.validate("post_client.json")
    def on_post(self, payload: dict) -> JSONResponse:
        onboarding = OnboardingController().create(payload)
        return JSONResponse(content=jsonable_encoder(onboarding), status_code=http_status.HTTP_201_CREATED)
