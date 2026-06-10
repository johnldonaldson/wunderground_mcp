from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from wunderground_server import get_current_conditions_payload, get_forecast_payload


async def current_conditions(request):
    conditions = await get_current_conditions_payload()

    if isinstance(conditions, str):
        return JSONResponse({"error": conditions}, status_code=502)

    return JSONResponse(conditions)


async def forecast(request):
    forecast_payload = await get_forecast_payload()

    if isinstance(forecast_payload, str):
        return JSONResponse({"error": forecast_payload}, status_code=502)

    return JSONResponse(forecast_payload)


app = Starlette(
    routes=[
        Route("/ha/current", current_conditions, methods=["GET"]),
        Route("/ha/forecast", forecast, methods=["GET"]),
    ]
)