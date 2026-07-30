-- Sliding window rate limiter Lua script
-- KEYS[1] = key (client:route)
-- ARGV[1] = now (ms)
-- ARGV[2] = window_ms
-- ARGV[3] = limit

local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZADD', key, now, now)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
redis.call('PEXPIRE', key, window)
if count > limit then
    return {0, count}
end
return {1, count}
