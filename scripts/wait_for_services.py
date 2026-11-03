#!/usr/bin/env python3
"""Wait for PostgreSQL and Redis to be reachable before proceeding with app startup."""

import asyncio
import os
import socket
import sys
import time
from typing import List, Optional

import asyncpg
import redis.asyncio as aioredis


def resolve_candidate_host(candidates: List[str]) -> Optional[str]:
    """Tests candidate hostnames and returns the first one that resolves via DNS."""
    for host in candidates:
        if not host:
            continue
        try:
            socket.gethostbyname(host)
            return host
        except Exception:
            continue
    return None


async def wait_for_postgres(
    hosts: List[str], port: int, user: str, password: str, database: str, timeout: int = 60
) -> bool:
    start_time = time.time()
    print(f"Waiting for PostgreSQL on candidate hosts {hosts}:{port}/{database} (timeout: {timeout}s)...")
    
    while time.time() - start_time < timeout:
        active_host = resolve_candidate_host(hosts)
        if not active_host:
            print(f"None of the PostgreSQL candidate hosts {hosts} could be resolved via DNS yet. Retrying in 2 seconds...")
            await asyncio.sleep(2)
            continue

        try:
            conn = await asyncpg.connect(
                host=active_host,
                port=port,
                user=user,
                password=password,
                database=database,
                timeout=5,
            )
            await conn.close()
            print(f"PostgreSQL is ready and accessible on {active_host}:{port}!")
            # Export resolved host so subsequent commands/processes use the working hostname
            os.environ["POSTGRES_SERVER"] = active_host
            return True
        except Exception as exc:
            print(f"PostgreSQL on {active_host} not ready yet: {exc}. Retrying in 2 seconds...")
            await asyncio.sleep(2)

    print("Timed out waiting for PostgreSQL!")
    return False


async def wait_for_redis(hosts: List[str], port: int, password: str = "", timeout: int = 60) -> bool:
    start_time = time.time()
    print(f"Waiting for Redis on candidate hosts {hosts}:{port} (timeout: {timeout}s)...")
    
    while time.time() - start_time < timeout:
        active_host = resolve_candidate_host(hosts)
        if not active_host:
            print(f"None of the Redis candidate hosts {hosts} could be resolved via DNS yet. Retrying in 2 seconds...")
            await asyncio.sleep(2)
            continue

        try:
            client = aioredis.Redis(
                host=active_host,
                port=port,
                password=password if password else None,
                socket_timeout=3,
            )
            await client.ping()
            await client.aclose()
            print(f"Redis is ready and accessible on {active_host}:{port}!")
            os.environ["REDIS_HOST"] = active_host
            return True
        except Exception as exc:
            print(f"Redis on {active_host} not ready yet: {exc}. Retrying in 2 seconds...")
            await asyncio.sleep(2)

    print("Timed out waiting for Redis!")
    return False


async def main() -> int:
    pg_host = os.getenv("POSTGRES_SERVER", "db")
    pg_candidates = [pg_host]
    if pg_host != "fastapi_postgres":
        pg_candidates.append("fastapi_postgres")
    if pg_host != "db":
        pg_candidates.append("db")

    pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_user = os.getenv("POSTGRES_USER", "postgres")
    pg_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    pg_db = os.getenv("POSTGRES_DB", "app_db")

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_candidates = [redis_host]
    if redis_host != "fastapi_redis":
        redis_candidates.append("fastapi_redis")
    if redis_host != "redis":
        redis_candidates.append("redis")

    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD", "")

    pg_ok = await wait_for_postgres(pg_candidates, pg_port, pg_user, pg_password, pg_db)
    if not pg_ok:
        return 1

    redis_ok = await wait_for_redis(redis_candidates, redis_port, redis_password)
    if not redis_ok:
        return 1

    print("All dependency services are up and healthy!")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
