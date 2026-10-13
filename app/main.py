"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
from app.src.config.database import IST, client, db, init_indexes
from app.src.main import app
from app.src.model import EmployeeIn, PunchInIn, PunchOutIn, RegularizeIn
from app.src.utils.calculations import (
    compute_half_day,
    compute_late_minutes,
    compute_overtime,
    compute_work_hours,
    get_attendance_date,
    round_half_up,
)
from app.src.utils.formatters import (
    format_attendance_record,
    format_employee,
    format_history_entry,
    from_epoch_ms,
    to_epoch_ms,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# TODO - the rest of the contract (see openapi.yaml):
#   POST  /attendance/punch-out
#   PATCH /attendance/{emp_code}/{date}
#   GET   /analytics/employees/{emp_code}/monthly
#   GET   /analytics/departments/summary
#   GET   /analytics/leaderboard/late
#   GET   /analytics/departments/{department}/trend
#   GET   /admin/explain/{endpoint}
# --------------------------------------------------------------------------- #
