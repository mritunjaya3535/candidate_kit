import math
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.src.config.database import IST


def round_half_up(val: Optional[float], decimals: int = 2) -> Optional[float]:
    if val is None:
        return None
    quant = Decimal("10") ** -decimals
    d = Decimal(str(val))
    return float(d.quantize(quant, rounding=ROUND_HALF_UP))


def get_attendance_date(punch_in_utc: datetime, shift_start: str, shift_end: str) -> str:
    punch_in_ist = punch_in_utc.astimezone(IST)
    sh, sm = map(int, shift_start.split(":"))
    eh, em = map(int, shift_end.split(":"))
    if (eh, em) <= (sh, sm):
        if (punch_in_ist.hour, punch_in_ist.minute) < (eh, em):
            return (punch_in_ist.date() - timedelta(days=1)).isoformat()
    return punch_in_ist.date().isoformat()


def compute_late_minutes(punch_in_utc: datetime, shift_start: str, shift_end: str, attendance_date_str: str) -> int:
    punch_in_ist = punch_in_utc.astimezone(IST)
    sh, sm = map(int, shift_start.split(":"))
    d = datetime.fromisoformat(attendance_date_str).date()
    start_dt = datetime(d.year, d.month, d.day, sh, sm, 0, 0, tzinfo=IST)
    diff = (punch_in_ist - start_dt).total_seconds()
    if diff <= 600:
        return 0
    return int(math.floor(diff / 60))


def compute_work_hours(punch_in_utc: datetime, punch_out_utc: datetime) -> float:
    diff_sec = (punch_out_utc - punch_in_utc).total_seconds()
    val = Decimal(str(diff_sec)) / Decimal("3600")
    return float(val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_overtime(punch_out_utc: datetime, shift_start: str, shift_end: str, attendance_date_str: str) -> int:
    punch_out_ist = punch_out_utc.astimezone(IST)
    sh, sm = map(int, shift_start.split(":"))
    eh, em = map(int, shift_end.split(":"))
    d = datetime.fromisoformat(attendance_date_str).date()
    if (eh, em) <= (sh, sm):
        d = d + timedelta(days=1)
    end_dt = datetime(d.year, d.month, d.day, eh, em, 0, 0, tzinfo=IST)
    diff = (punch_out_ist - end_dt).total_seconds()
    mins = int(math.floor(diff / 60))
    return mins if mins >= 30 else 0


def compute_half_day(work_hours: Optional[float]) -> bool:
    return work_hours is not None and work_hours < 4.50
