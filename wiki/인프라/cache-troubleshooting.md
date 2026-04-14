---
domain: 인프라
process: 서버
status: draft
tags:
  - cache
  - troubleshooting
  - 레디스
---

# Cache Troubleshooting Guide

## Common Issues

### 1. Cache Miss Rate Too High
- Check key expiration settings
- Verify cache warming on deploy
- Monitor hit/miss ratio: target > 90%

### 2. Stale Data
- Ensure cache invalidation on write
- Check pub/sub subscription for invalidation events

### 3. Connection Timeout
- Redis latency check: `redis-cli --latency`
- Network partition detection
- Connection pool tuning
