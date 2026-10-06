from fastapi import APIRouter
from app.api.v1.auth import auth_router
from app.api.v1.consultants import consultants_router

api_v1_router = APIRouter()
api_v1_router.include_router(consultants_router)
api_v1_router.include_router(auth_router)
