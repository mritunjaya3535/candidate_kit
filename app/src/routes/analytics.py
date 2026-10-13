import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.src.config.database import db
from app.src.controller.analytics_controller import (
    build_department_summary_pipeline,
    build_department_trend_pipeline,
    build_employee_monthly_pipeline,
    build_late_leaderboard_pipeline,
)
from app.src.utils.calculations import round_half_up

router = APIRouter(prefix="/analytics")


@router.get("/employees/{emp_code}/monthly")
def employee_monthly(emp_code: str, month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "Employee not found")

    year, m = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, m)[1]
    m_start = f"{month}-01"
    m_end = f"{month}-{days_in_month:02d}"

    emp_joined = emp["joined_on"]
    start_str = max(emp_joined, m_start)
    end_str = m_end

    working_days = 0
    if start_str <= end_str:
        curr = datetime.fromisoformat(start_str).date()
        end_d = datetime.fromisoformat(end_str).date()
        while curr <= end_d:
            if curr.weekday() < 5:
                working_days += 1
            curr += timedelta(days=1)

    pipeline = build_employee_monthly_pipeline(emp_code, m_start, m_end)
    res = list(db.attendance_logs.aggregate(pipeline))
    if res:
        agg = res[0]
        present_days = float(agg["present_days"])
        leave_days = int(agg["leave_days"])
        late_count = int(agg["late_count"])
        total_late = int(agg["total_late_minutes"])
        total_ot = int(agg["total_overtime_minutes"])
    else:
        present_days = 0.0
        leave_days = 0
        late_count = 0
        total_late = 0
        total_ot = 0

    if working_days == 0:
        att_pct = None
    else:
        val = Decimal(str(present_days)) / Decimal(str(working_days)) * Decimal("100")
        att_pct = float(val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": leave_days,
        "late_count": late_count,
        "total_late_minutes": total_late,
        "total_overtime_minutes": total_ot,
        "attendance_pct": att_pct,
    }


@router.get("/departments/summary")
def department_summary(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    department: Optional[str] = None,
):
    year, m = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, m)[1]
    m_start = f"{month}-01"
    m_end = f"{month}-{days_in_month:02d}"

    pipeline = build_department_summary_pipeline(m_start, m_end, department)
    results = list(db.employees.aggregate(pipeline))
    items = []
    for doc in results:
        headcount = doc["headcount"]
        if headcount == 0:
            continue
        stats_list = doc.get("stats") or []
        st = stats_list[0] if stats_list else {}
        wh_count = st.get("work_hours_count", 0)
        if wh_count > 0:
            val = Decimal(str(st["work_hours_sum"])) / Decimal(str(wh_count))
            avg_wh = float(val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            avg_wh = None

        items.append(
            {
                "department": doc["_id"],
                "headcount": headcount,
                "present_days": float(st.get("present_days", 0.0)),
                "avg_work_hours": avg_wh,
                "late_count": int(st.get("late_count", 0)),
                "total_late_minutes": int(st.get("total_late_minutes", 0)),
                "leave_count": int(st.get("leave_count", 0)),
                "on_duty_count": int(st.get("on_duty_count", 0)),
            }
        )

    return {"month": month, "items": items}


@router.get("/leaderboard/late")
def late_leaderboard(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(10, ge=1, le=50),
    department: Optional[str] = None,
):
    year, m = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, m)[1]
    m_start = f"{month}-01"
    m_end = f"{month}-{days_in_month:02d}"

    pipeline = build_late_leaderboard_pipeline(m_start, m_end, limit, department)
    items = list(db.attendance_logs.aggregate(pipeline))
    return {"month": month, "items": items}


@router.get("/departments/{department}/trend")
def department_trend(
    department: str,
    from_date: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    try:
        f_d = datetime.strptime(from_date, "%Y-%m-%d").date()
        t_d = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "Invalid date format")

    if t_d < f_d:
        raise HTTPException(422, "to date must be >= from date")

    days_diff = (t_d - f_d).days + 1
    if days_diff > 92:
        raise HTTPException(422, "date range exceeds 92 days")

    dept_emp = db.employees.find_one({"department": department})
    if not dept_emp:
        raise HTTPException(404, "Department not found")

    from_dt = datetime.combine(f_d, datetime.min.time(), tzinfo=timezone.utc)
    to_dt = datetime.combine(t_d + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    pipeline = build_department_trend_pipeline(department, from_date, to_date, from_dt, to_dt)
    raw_items = list(db.attendance_logs.aggregate(pipeline))
    items = []
    for row in raw_items:
        rate = round_half_up(row.get("attendance_rate"), 4)
        mavg = round_half_up(row.get("moving_avg_7d"), 4)
        items.append(
            {
                "date": row["date"],
                "is_working_day": row["is_working_day"],
                "headcount": int(row["headcount"]),
                "present_count": float(row["present_count"]),
                "late_count": int(row["late_count"]),
                "attendance_rate": rate,
                "moving_avg_7d": mavg,
            }
        )

    return {"department": department, "items": items}
