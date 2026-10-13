from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.src.config.database import init_indexes
from app.src.routes import (
    admin_router,
    analytics_router,
    attendance_router,
    employees_router,
    health_router,
)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    init_indexes()
    yield


app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(employees_router)
app.include_router(attendance_router)
app.include_router(analytics_router)
app.include_router(admin_router)
