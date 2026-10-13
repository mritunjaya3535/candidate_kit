# Employee Attendance & Analytics API

FastAPI + MongoDB backend for attendance logging and analytics, following the OpenAPI 3.0 specification.

## How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment variables (defaults connect to local MongoDB):
   - `MONGO_URI`: MongoDB connection string (default: `mongodb://localhost:27017`)
   - `MONGO_DB`: Database name (default: `attendance_db`)

3. Start the application:
   ```bash
   uvicorn app.main:app --port 8000
   ```

4. Verify health check:
   ```bash
   curl http://localhost:8000/health
   ```

## Key Highlights

- **Indexes**: All required unique and compound indexes are created automatically at application startup.
- **Concurrency**: Guaranteed conflict prevention for simultaneous punch-ins and punch-outs via atomic database operations and unique indexes.
- **Analytics**: Analytics pipelines (employee monthly summary, department summary, late leaderboard, department trend) run entirely within MongoDB aggregations using `$lookup`, `$densify`, and `$setWindowFields`.
- **Explain**: Endpoint `/admin/explain/{endpoint}` reports execution stats and index scans (`IXSCAN`) for query validation.

