-- Lua script for idempotency semantics (atomic check -> set in Redis)
-- KEYS[1] = idempotency_key
-- ARGV[1] = value (cached response as JSON)
-- ARGV[2] = ttl seconds

local existing = redis.call('GET', KEYS[1])
if existing then
    return {err="EXISTS"}
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return {ok='OK'}
