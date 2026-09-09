#!/usr/bin/env python3
"""
Concurrency test driver for /api/transactions

Usage:
  python tools/concurrency_test.py --url http://localhost:8000 --concurrency 100 --requests 1000 --mode random_key

Modes:
 - random_key: every request gets a fresh Idempotency-Key (best for throughput)
 - same_key: all requests use the same Idempotency-Key (tests idempotency under concurrent duplicates)
"""
import argparse
import asyncio
import aiohttp
import time
import statistics
import uuid
import json

# By default use many accounts to avoid lock contention. NUM_ACCOUNTS defines size of the pool.
NUM_ACCOUNTS = 500

async def make_payload_for_index(i):
    # pick two distinct accounts deterministically from index
    a = (i % NUM_ACCOUNTS) + 1
    b = ((i + 1) % NUM_ACCOUNTS) + 1
    # ensure they are different
    if a == b:
        b = (b % NUM_ACCOUNTS) + 1
    return {
        "entries": [
            {"account_id": a, "currency": "USD", "amount": 10.0},
            {"account_id": b, "currency": "USD", "amount": -10.0}
        ],
        "base_currency": "USD"
    }


async def worker(name, session, endpoint, queue, results, mode):
    while True:
        try:
            idx = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        if mode == "random_key":
            key = str(uuid.uuid4())
        else:
            key = "concurrent-same-key-001"
        headers = {
            "X-Client-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Idempotency-Key": key
        }
        payload = await make_payload_for_index(idx)
        start = time.perf_counter()
        try:
            async with session.post(endpoint, data=json.dumps(payload), headers=headers, timeout=30) as resp:
                text = await resp.text()
                elapsed = (time.perf_counter() - start) * 1000.0
                results.append((resp.status, elapsed, text))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000.0
            results.append(("err", elapsed, str(e)))

async def run_test(endpoint, concurrency, total_requests, mode):
    q = asyncio.Queue()
    for i in range(total_requests):
        await q.put(i)
    # Ensure there are accounts seeded for the NUM_ACCOUNTS range (user should seed in DB before running)
    results = []
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = []
        for i in range(concurrency):
            t = asyncio.create_task(worker(f"w-{i}", session, endpoint, q, results, mode))
            tasks.append(t)
        start = time.perf_counter()
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start

    # summarize
    statuses = {}
    latencies = []
    for status, elapsed, body in results:
        statuses[status] = statuses.get(status, 0) + 1
        if isinstance(elapsed, (int, float)):
            latencies.append(elapsed)
    latencies_sorted = sorted(latencies)
    def pct(p):
        if not latencies_sorted:
            return None
        idx = int(len(latencies_sorted) * p / 100)
        idx = min(len(latencies_sorted) - 1, max(0, idx))
        return latencies_sorted[idx]

    print("=== Concurrency test summary ===")
    print(f"endpoint: {endpoint}")
    print(f"mode: {mode}")
    print(f"concurrency: {concurrency}, total_requests: {total_requests}")
    print(f"wall time: {total_time:.2f}s, achieved rps: {len(results)/total_time:.2f}")
    print("status counts:", statuses)
    if latencies_sorted:
        print(f"latency ms: avg={statistics.mean(latencies_sorted):.2f}, med={pct(50):.2f}, p95={pct(95):.2f}, p99={pct(99):.2f}, max={latencies_sorted[-1]:.2f}")
    else:
        print("no latency data")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000", help="base url")
    p.add_argument("--concurrency", type=int, default=50)
    p.add_argument("--requests", type=int, default=200)
    p.add_argument("--mode", choices=["random_key", "same_key"], default="random_key")
    return p.parse_args()

def main():
    args = parse_args()
    endpoint = args.url.rstrip("/") + "/transactions"
    asyncio.run(run_test(endpoint, args.concurrency, args.requests, args.mode))

if __name__ == "__main__":
    main()