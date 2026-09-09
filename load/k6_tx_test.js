import http from "k6/http";
import { check } from "k6";
import {
  // randomSeed,
  uuidv4,
} from "https://jslib.k6.io/k6-utils/1.2.0/index.js";

// randomSeed(12345);

const TARGET = __ENV.TARGET_URL || "http://localhost:8000";
const ENDPOINT = `${TARGET}/transactions`;
const NUM_ACCOUNTS = __ENV.NUM_ACCOUNTS ? parseInt(__ENV.NUM_ACCOUNTS) : 1000;

export let options = {
  // Override at runtime: k6 run --vus 200 --duration 60s load/k6_tx_test.js
  // or set environment variables (TARGET_URL)
};

function makePayload() {
  // pick two random distinct account ids to avoid contention
  const a = Math.floor(Math.random() * NUM_ACCOUNTS) + 1;
  let b = Math.floor(Math.random() * NUM_ACCOUNTS) + 1;
  if (b === a) b = ((b % NUM_ACCOUNTS) + 1);
  return JSON.stringify({
    entries: [
      { account_id: a, currency: "USD", amount: 10.0 },
      { account_id: b, currency: "USD", amount: -10.0 },
    ],
    base_currency: "USD",
  });
}

export default function () {
  const idempotencyKey = uuidv4(); // unique per request so idempotency doesn't dedupe
  const headers = {
    "Content-Type": "application/json",
    "Idempotency-Key": idempotencyKey,
    "X-Client-Id": uuidv4(),
  };

  const res = http.post(ENDPOINT, makePayload(), {
    headers: headers,
    tags: { name: "tx" },
  });

  check(res, {
    "status is 200 or 201": (r) => r.status === 200 || r.status === 201,
    "no 5xx": (r) => r.status < 500,
  });
}
