# DECISIONS.md  (about 150-200 words in total - plain language, your own words)

1. **Indexes.** Which indexes did you create, and which query or guarantee does each one serve? Which one did you consider and reject?
We created:
- `employees`: unique `emp_code` (identity guarantee); `department` and `(joined_on, department)` (headcount filtering).
- `attendance_logs`: unique `(emp_code, date)` (concurrency and natural key guarantee); `(date, emp_code)` (fast list pagination/sort); `(date, late_minutes)` (leaderboard index scan).
We considered and rejected standalone indexes on `work_hours` and `history`, as date-anchored compound indexes provide far superior selectivity for range analytics.

2. **Punch-in race.** Two identical punch-in requests arrive at the same instant. Walk through exactly what happens in your code.
Both concurrent requests validate input, compute the identical attendance date, and execute `insert_one()`. MongoDB's unique compound index on `(emp_code, date)` serializes write operations at the storage engine level. Exactly one insert succeeds and returns 201. The concurrent duplicate raises `DuplicateKeyError`, which our exception handler intercepts to return HTTP 409 cleanly.

3. **Ties.** Two employees are tied on late minutes at the cutoff of `limit`. What does your leaderboard return, and why?
We use `$setWindowFields` with `$rank` for standard competition ranking (1, 2, 2, 4). Filtering `rank <= limit` ensures all tied employees sharing the cutoff rank are returned, intentionally yielding more than `limit` total records per the contract, ordered secondarily by `emp_code` ascending.

4. **Headcount.** How does your department summary make sure employees with zero logs are counted?
The pipeline originates on the `employees` collection (filtering `joined_on <= month_end`) and groups by department to establish authoritative headcount before joining `attendance_logs` via `$lookup`. Zero-log employees are thus fully counted in the baseline headcount.

5. **One thing you would change** if this had to serve 100x the data.
I would pre-aggregate daily and monthly statistics asynchronously via change streams or scheduled rollups (`$merge`), and shard `attendance_logs` by hashed `emp_code` and date, avoiding full on-the-fly cross-collection aggregations.
