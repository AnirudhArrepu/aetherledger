what
- backend financial server (minimal)

how to run (quick)
- docker-compose up --build
- api: http://localhost:8000

or locally
- pip install -r requirements.txt
- set DATABASE_URL and REDIS_URL in app/core/config.py or env
- make sure DB tables exist (accounts, ledger_entries, outbox_events, balance_snapshots)
- run: uvicorn app.main:app --reload
- worker: python -m app.outbox.worker

snapshotting (basics)
- we use balance_snapshots + projection.
- create snapshots regularly (cron/k8s cronjob). snapshot endpoint example:

  curl -X POST "http://localhost:8000/api/admin/snapshot?account_id=42" -H "Authorization: ******"

- crontab example (every 5m):
  */5 * * * * /usr/bin/curl -s -X POST "http://localhost:8000/api/admin/snapshot?account_id=42" -H "Authorization: ******" >/dev/null 2>&1

notes
- ledger writes must use SERIALIZABLE + retry on serialization failures
- snapshot creation should be atomic/consistent
- idempotency: concurrent in-flight duplicates return 409 by default
- rate limiter: sliding-window via Redis Lua script

tests
- pytest

want me to add the admin snapshot endpoint + migration + snapshotter? say which and i'll add it.
