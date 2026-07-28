from fastapi import APIRouter

from app.routers import auth, catches, spots, species

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(spots.router)
api_router.include_router(catches.router)
api_router.include_router(species.router)
