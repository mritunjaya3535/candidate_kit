from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import DuplicateKeyError

from app.src.config.database import db
from app.src.model.employee import EmployeeIn
from app.src.utils.formatters import format_employee

router = APIRouter()


@router.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    if body.shift_start == body.shift_end:
        raise HTTPException(422, "shift_start and shift_end must differ")
    try:
        datetime.strptime(body.joined_on, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "Invalid joined_on date")

    doc = body.model_dump()
    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    doc["created_at"] = created_at
    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "emp_code already exists")

    return format_employee(doc)


@router.get("/employees")
def list_employees(
    department: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = {}
    if department is not None:
        q["department"] = department
    skip = (page - 1) * page_size
    total = db.employees.count_documents(q)
    cursor = db.employees.find(q, {"_id": 0}).sort("emp_code", 1).skip(skip).limit(page_size)
    items = [format_employee(d) for d in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
