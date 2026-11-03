from fastapi import APIRouter

from app.api.v1.endpoints import drivers, health, rides

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(rides.router, prefix="/rides", tags=["Rides"])
api_router.include_router(drivers.router, prefix="/drivers", tags=["Drivers"])
