import calendar
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from bson import json_util
from fastapi import APIRouter, HTTPException, Path, Query

from app.src.config.database import db
from app.src.controller.analytics_controller import (
    build_department_summary_pipeline,
    build_department_trend_pipeline,
    build_late_leaderboard_pipeline,
)

router = APIRouter(prefix="/admin")


@router.get("/explain/{endpoint}")
def explain_endpoint(
    endpoint: str = Path(..., pattern=r"^(attendance_list|employee_monthly|department_summary|late_leaderboard|department_trend)$"),
    emp_code: Optional[str] = None,
    month: Optional[str] = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    department: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = Query(None, alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: Optional[str] = Query(None, alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if endpoint == "attendance_list":
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from must be <= date_to")
        q = {}
        if emp_code:
            q["emp_code"] = emp_code
        if date_from or date_to:
            q["date"] = {}
            if date_from:
                q["date"]["$gte"] = date_from
            if date_to:
                q["date"]["$lte"] = date_to
        if status:
            q["status"] = status
        skip = (page - 1) * page_size
        raw = db.command(
            "explain",
            {
                "find": "attendance_logs",
                "filter": q,
                "sort": {"date": -1, "emp_code": 1},
                "skip": skip,
                "limit": page_size,
            },
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": json.loads(json_util.dumps(raw)),
        }

    elif endpoint == "employee_monthly":
        if not emp_code or not month:
            raise HTTPException(422, "emp_code and month are required")
        year, m = map(int, month.split("-"))
        days_in_month = calendar.monthrange(year, m)[1]
        m_start = f"{month}-01"
        m_end = f"{month}-{days_in_month:02d}"
        pipeline = [
            {"$match": {"emp_code": emp_code, "date": {"$gte": m_start, "$lte": m_end}}},
            {"$group": {"_id": None, "present_days": {"$sum": 1}}},
        ]
        raw = db.command(
            "explain",
            {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": json.loads(json_util.dumps(raw)),
        }

    elif endpoint == "department_summary":
        if not month:
            raise HTTPException(422, "month is required")
        year, m = map(int, month.split("-"))
        days_in_month = calendar.monthrange(year, m)[1]
        m_start = f"{month}-01"
        m_end = f"{month}-{days_in_month:02d}"
        pipeline = build_department_summary_pipeline(m_start, m_end, department)
        raw = db.command(
            "explain",
            {"aggregate": "employees", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "employees",
            "explain": json.loads(json_util.dumps(raw)),
        }

    elif endpoint == "late_leaderboard":
        if not month:
            raise HTTPException(422, "month is required")
        year, m = map(int, month.split("-"))
        days_in_month = calendar.monthrange(year, m)[1]
        m_start = f"{month}-01"
        m_end = f"{month}-{days_in_month:02d}"
        pipeline = build_late_leaderboard_pipeline(m_start, m_end, limit, department)
        raw = db.command(
            "explain",
            {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": json.loads(json_util.dumps(raw)),
        }

    elif endpoint == "department_trend":
        if not department or not from_date or not to_date:
            raise HTTPException(422, "department, from and to are required")
        f_d = datetime.strptime(from_date, "%Y-%m-%d").date()
        t_d = datetime.strptime(to_date, "%Y-%m-%d").date()
        from_dt = datetime.combine(f_d, datetime.min.time(), tzinfo=timezone.utc)
        to_dt = datetime.combine(t_d + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        pipeline = build_department_trend_pipeline(department, from_date, to_date, from_dt, to_dt)
        raw = db.command(
            "explain",
            {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}},
            verbosity="executionStats",
        )
        return {
            "endpoint": endpoint,
            "collection": "attendance_logs",
            "explain": json.loads(json_util.dumps(raw)),
        }
