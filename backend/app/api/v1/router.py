from fastapi import APIRouter

from app.api.v1.advisors import router as advisors_router
from app.api.v1.clients import router as clients_router
from app.api.v1.interactions import router as interactions_router
from app.api.v1.message_drafts import router as message_drafts_router

router = APIRouter()

router.include_router(advisors_router)
router.include_router(clients_router)
router.include_router(interactions_router)
router.include_router(message_drafts_router)
