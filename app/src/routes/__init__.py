from .admin import router as admin_router
from .analytics import router as analytics_router
from .attendance import router as attendance_router
from .employees import router as employees_router
from .health import router as health_router

__all__ = [
    "admin_router",
    "analytics_router",
    "attendance_router",
    "employees_router",
    "health_router",
]
