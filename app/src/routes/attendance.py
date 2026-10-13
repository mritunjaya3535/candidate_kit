from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.src.config.database import db
from app.src.model.attendance import PunchInIn, PunchOutIn, RegularizeIn
from app.src.utils.calculations import (
    compute_half_day,
    compute_late_minutes,
    compute_overtime,
    compute_work_hours,
    get_attendance_date,
)
from app.src.utils.formatters import (
    format_attendance_record,
    from_epoch_ms,
)

router = APIRouter(prefix="/attendance")


@router.post("/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "Employee not found")

    if body.punched_at is not None:
        ts = from_epoch_ms(body.punched_at)
    else:
        ts = datetime.now(timezone.utc).replace(microsecond=0)

    d = get_attendance_date(ts, emp["shift_start"], emp["shift_end"])
    late_minutes = compute_late_minutes(ts, emp["shift_start"], emp["shift_end"], d)

    doc = {
        "emp_code": body.emp_code,
        "date": d,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": late_minutes,
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }
    try:
        db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "already punched in for this date")

    return format_attendance_record(doc)


@router.post("/punch-out")
def punch_out(body: PunchOutIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "Employee not found")

    if body.punched_at is not None:
        ts = from_epoch_ms(body.punched_at)
    else:
        ts = datetime.now(timezone.utc).replace(microsecond=0)

    recs = list(
        db.attendance_logs.find(
            {"emp_code": body.emp_code, "punch_in": {"$ne": None}}
        ).sort("punch_in", -1).limit(1)
    )
    if not recs:
        raise HTTPException(404, "No punch-in found")

    rec = recs[0]
    p_in = rec["punch_in"]
    if p_in.tzinfo is None:
        p_in = p_in.replace(tzinfo=timezone.utc)

    p_in_ms = int(p_in.timestamp() * 1000)
    p_out_ms = int(ts.timestamp() * 1000)

    if p_out_ms <= p_in_ms:
        raise HTTPException(422, "punched_at must be strictly greater than punch_in")
    if p_out_ms - p_in_ms > 24 * 3600 * 1000:
        raise HTTPException(422, "punched_at must be within 24 hours of punch_in")

    if rec.get("punch_out") is not None:
        raise HTTPException(409, "Record already punched out")

    wh = compute_work_hours(p_in, ts)
    ot = compute_overtime(ts, emp["shift_start"], emp["shift_end"], rec["date"])
    hd = compute_half_day(wh)

    updated = db.attendance_logs.find_one_and_update(
        {"_id": rec["_id"], "punch_out": None},
        {"$set": {"punch_out": ts, "work_hours": wh, "overtime_minutes": ot, "half_day": hd}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Record already punched out")

    return format_attendance_record(updated)


@router.get("")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if status is not None and status not in ("PRESENT", "ABSENT", "LEAVE", "WFH", "ON_DUTY"):
        raise HTTPException(422, "Invalid status")
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

    total = db.attendance_logs.count_documents(q)
    skip = (page - 1) * page_size
    cursor = db.attendance_logs.find(q).sort([("date", -1), ("emp_code", 1)]).skip(skip).limit(page_size)
    items = [format_attendance_record(d) for d in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.patch("/{emp_code}/{date}")
def regularize_attendance(emp_code: str, date: str, body: RegularizeIn):
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "Employee not found")

    rec = db.attendance_logs.find_one({"emp_code": emp_code, "date": date})
    if not rec:
        raise HTTPException(404, "Attendance record not found")

    if body.status in ("ABSENT", "LEAVE"):
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(422, "punch times not allowed for ABSENT or LEAVE")

    target_status = body.status if body.status is not None else rec["status"]
    if target_status in ("ABSENT", "LEAVE"):
        new_p_in = None
        new_p_out = None
    else:
        if body.punch_in is not None:
            new_p_in = from_epoch_ms(body.punch_in)
        else:
            new_p_in = rec.get("punch_in")

        if new_p_in is None:
            raise HTTPException(422, "Presence status requires punch_in")
        if new_p_in.tzinfo is None:
            new_p_in = new_p_in.replace(tzinfo=timezone.utc)

        if get_attendance_date(new_p_in, emp["shift_start"], emp["shift_end"]) != date:
            raise HTTPException(422, "punch_in must stay on attendance date")

        if body.punch_out is not None:
            new_p_out = from_epoch_ms(body.punch_out)
        else:
            new_p_out = rec.get("punch_out")

        if new_p_out is not None:
            if new_p_out.tzinfo is None:
                new_p_out = new_p_out.replace(tzinfo=timezone.utc)
            in_ms = int(new_p_in.timestamp() * 1000)
            out_ms = int(new_p_out.timestamp() * 1000)
            if out_ms <= in_ms:
                raise HTTPException(422, "punch_out must be after punch_in")
            if out_ms - in_ms > 24 * 3600 * 1000:
                raise HTTPException(422, "punch_out must be within 24 hours of punch_in")

    if target_status in ("ABSENT", "LEAVE"):
        new_wh = None
        new_late = 0
        new_ot = 0
        new_hd = False
    else:
        new_late = compute_late_minutes(new_p_in, emp["shift_start"], emp["shift_end"], date)
        if new_p_out is not None:
            new_wh = compute_work_hours(new_p_in, new_p_out)
            new_ot = compute_overtime(new_p_out, emp["shift_start"], emp["shift_end"], date)
            new_hd = compute_half_day(new_wh)
        else:
            new_wh = None
            new_ot = 0
            new_hd = False

    old_status = rec["status"]
    old_p_in = rec.get("punch_in")
    if old_p_in and old_p_in.tzinfo is None:
        old_p_in = old_p_in.replace(tzinfo=timezone.utc)
    old_p_out = rec.get("punch_out")
    if old_p_out and old_p_out.tzinfo is None:
        old_p_out = old_p_out.replace(tzinfo=timezone.utc)
    old_wh = rec.get("work_hours")
    old_late = rec.get("late_minutes", 0)
    old_ot = rec.get("overtime_minutes", 0)
    old_hd = rec.get("half_day", False)

    changes = {}
    if old_status != target_status:
        changes["status"] = {"from": old_status, "to": target_status}
    if old_p_in != new_p_in:
        changes["punch_in"] = {"from": old_p_in, "to": new_p_in}
    if old_p_out != new_p_out:
        changes["punch_out"] = {"from": old_p_out, "to": new_p_out}
    if old_wh != new_wh:
        changes["work_hours"] = {"from": old_wh, "to": new_wh}
    if old_late != new_late:
        changes["late_minutes"] = {"from": old_late, "to": new_late}
    if old_ot != new_ot:
        changes["overtime_minutes"] = {"from": old_ot, "to": new_ot}
    if old_hd != new_hd:
        changes["half_day"] = {"from": old_hd, "to": new_hd}

    if not changes:
        raise HTTPException(422, "No fields changed")

    hist_at = datetime.now(timezone.utc).replace(microsecond=0)
    hist_entry = {
        "at": hist_at,
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes,
    }

    current_history = rec.get("history") or []
    current_size = len(current_history)

    updated = db.attendance_logs.find_one_and_update(
        {"_id": rec["_id"], "history": {"$size": current_size}},
        {
            "$set": {
                "status": target_status,
                "punch_in": new_p_in,
                "punch_out": new_p_out,
                "work_hours": new_wh,
                "late_minutes": new_late,
                "overtime_minutes": new_ot,
                "half_day": new_hd,
            },
            "$push": {"history": hist_entry},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Concurrent modification conflict")

    return format_attendance_record(updated)
