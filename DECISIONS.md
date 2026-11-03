# Architectural Decisions & Trade-Offs (DECISIONS.md)

**Project**: Netzence Sustainability Carbon Credits Service  
**Stack**: Python 3.12, FastAPI, PostgreSQL 16, Redis 7, SQLAlchemy 2.0 (asyncpg), Alembic, Docker Compose

---

## 1. The Three Biggest Trade-Offs Made (and Why)

### Trade-Off 1: Separate Credit Lots + Append-Only Audit Ledger vs. Single Mutable Balance
- **Decision**: Modeled credit issuance as discrete `credit_lots` (storing original amount, remaining amount, and expiration date) alongside an immutable `ledger_transactions` table recording all credits, debits, and reversals.
- **Trade-Off**: Requires updating lot balances and inserting ledger rows in a single transaction, using slightly more storage than a single `driver_accounts.balance` column.
- **Why**: A single balance column cannot enforce **FIFO consumption** or **12-month expiration** without re-scanning all historical events. The lot-based design guarantees $O(1)$ unexpired balance summation via indexed queries and clean FIFO consumption, while the ledger provides a tamper-proof audit trail for driver transaction history.

### Trade-Off 2: Explicit Row-Level Locking (`FOR UPDATE`) vs. Optimistic Locking
- **Decision**: Implemented pessimistic row-level locking via a dedicated `driver_locks` synchronization table (`SELECT ... FOR UPDATE`) during redemptions.
- **Trade-Off**: Concurrent redemption requests for the *same* driver are serialized rather than executing in parallel and retrying on version conflict.
- **Why**: Drivers rarely submit concurrent redemptions in genuine usage; concurrent requests are typically race conditions or double-click bugs. Optimistic locking under high contention causes retry storms and client-side failures. Row-level pessimistic locking strictly guarantees that two simultaneous redemptions **never drive the balance below zero**, meeting the core safety requirement with predictable latency.

### Trade-Off 3: Pre-Cancellation Tombstones vs. Rejecting Out-of-Order Cancellations
- **Decision**: If a cancellation event arrives *before* the corresponding completion event, the system records a `CANCELLED` tombstone.
- **Trade-Off**: The system stores a minimal ride record with incomplete telemetry until completion arrives.
- **Why**: In distributed ride-hailing networks, network latency and message queues can invert event order. Rejecting early cancellations could cause rides cancelled by the user to erroneously award non-reversible credits when the delayed completion event finally lands. The tombstone prevents any credit issuance regardless of arrival sequence.

---

## 2. Core Questions Left Open in Specification

### Q1: What happens if a cancellation arrives before the completion event?
- The system writes a ride record with status `CANCELLED` (pre-cancellation tombstone).
- When `POST /rides/completed` subsequently arrives for that `ride_id`, the service recognizes the prior cancellation, records the ride details, but awards **0 credits**.

### Q2: How do you store credit amounts so rounding errors never appear?
- Stored as PostgreSQL `NUMERIC(12, 4)` and handled in Python strictly via `decimal.Decimal` with explicit `ROUND_HALF_UP` quantization.
- Floating-point `float` types are prohibited across database columns and domain models, eliminating IEEE 754 precision loss.

### Q3: What happens if your service crashes halfway through a request?
- Every mutation (ride insert, lot creation, ledger transaction, cache eviction) is wrapped inside an **atomic database transaction** (`AsyncSession` transaction block).
- If the service process crashes or loses network connectivity mid-request, PostgreSQL automatically aborts the connection and rolls back all uncommitted writes.
- Because `ride_id` is a primary key, retried requests either succeed cleanly or trigger the idempotency check, preventing partial writes and double awards.

---

## 3. Data Model & Rejected Alternative

### Main Tables & Constraints
1. **`rides`**: `id` (PK, string `ride_id` natural key), `driver_id` (indexed), `distance_km`, `vehicle_type`, `completed_at`, `status` (`COMPLETED`, `CANCELLED`).
2. **`credit_lots`**: `id` (BigInt PK), `driver_id` (indexed), `ride_id` (FK), `original_amount`, `remaining_amount`, `earned_at`, `expires_at` (indexed), `status`. Composite index: `(driver_id, expires_at, earned_at)`.
3. **`ledger_transactions`**: `id` (BigInt PK), `driver_id` (indexed), `transaction_type` (`CREDIT`, `DEBIT`, `REVERSAL`), `amount` (signed), `reason`, `ride_id`, `created_at`.
4. **`driver_locks`**: `driver_id` (PK), `updated_at`. Dedicated lock target isolating driver concurrency.

### Rejected Alternative Design: Pure Event Sourcing without Remaining Amounts
- **Rejected**: Deriving current balance and unexpired credits dynamically on every request by running a full SQL aggregation over raw ledger entries.
- **Why Rejected**: Matching debits against older credit lots dynamically in SQL requires recursive CTEs or window functions that degrade to $O(N^2)$ as driver transaction history grows. Storing `remaining_amount` directly on credit lots keeps balance queries and FIFO deductions at $O(1)$ and $O(\text{active lots})$.

---

## 4. What We Would Do With Two More Days
1. **Distributed Outbox Pattern & Asynchronous Messaging**: Emit domain events (`CreditAwarded`, `CreditRedeemed`) via a PostgreSQL outbox table to Apache Kafka or RabbitMQ for asynchronous analytics and partner notifications.
2. **Scheduled Proactive Expiration Worker**: A background cron/Celery worker or Redis TTL listener to mark expired lots as `EXPIRED` and write formal expiration entries into the ledger on their 12-month anniversary.
3. **Dynamic Emissions Engine**: Integrate vehicle efficiency lookup tables (e.g. EPA / WLTP ratings) to dynamically calculate exact carbon emissions avoided based on vehicle make and model.
4. **Read-Replica Routing**: Route high-frequency balance checks to PostgreSQL read replicas while routing write mutations to the primary.

---

## 5. One Thing We Tried That Did Not Work
- **Initial Attempt**: Attempted to manage concurrent redemption limits using Redis distributed locks (`SET key val NX EX`).
- **Failure Mode**: While Redis locks work well under normal conditions, if the database transaction commits slowly or Redis connection drops mid-request, race conditions can occur between the lock release and database commit boundary.
- **Resolution**: Replaced Redis locking with native PostgreSQL row-level locks (`SELECT ... FOR UPDATE` on `driver_locks`). Because the lock is held directly within the database transaction, lock release and commit are strictly atomic.

