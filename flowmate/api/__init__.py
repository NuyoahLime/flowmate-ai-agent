from fastapi import APIRouter

from .agent import router as agent_router
from .cross_device import router as cross_device_router
from .demo import router as demo_router
from .evals import router as evals_router
from .health import router as health_router
from .system import router as system_router
from .tasks import router as tasks_router
from .triggers import router as triggers_router

router = APIRouter()
router.include_router(health_router)
router.include_router(agent_router)
router.include_router(cross_device_router)
router.include_router(tasks_router)
router.include_router(triggers_router)
router.include_router(demo_router)
router.include_router(evals_router)
router.include_router(system_router)
