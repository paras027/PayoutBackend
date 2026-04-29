# PlaytoPayout — Payout Engine

Minimal payout engine for Playto Pay. Merchants accumulate balance via credits, request payouts, and track status through a background worker.

## Stack

- Backend: Django + Django REST Framework
- Database: PostgreSQL
- Background jobs: Celery + Redis
- Frontend: React + Tailwind (see `/frontend`)

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd PlaytoPayout
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file or export these in your shell:

```bash
export DB_NAME=playtopay
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_HOST=localhost
export DB_PORT=5432
export REDIS_URL=redis://127.0.0.1:6379/0
```

### 3. Create the PostgreSQL database

```bash
psql -U postgres -c "CREATE DATABASE playtopay;"
```

### 4. Start Redis (required for Celery)

```bash
redis-server
```

Or use Docker:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Seed merchants with credit history

```bash
python manage.py seed
```

This creates 3 merchants (Acme Agency, Freelancer Hub, Digital Studio) with credit balances.

### 7. Start Django

```bash
python manage.py runserver
```

### 8. Start Celery worker

```bash
celery -A PlaytoPayout worker --loglevel=info
```

### 9. Start Celery beat (for stuck payout retry)

```bash
celery -A PlaytoPayout beat --loglevel=info
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/merchants/user/` | List all merchants |
| POST | `/api/v1/merchants/user/` | Create merchant |
| GET | `/api/v1/ledger/details/` | List all ledger entries |
| POST | `/api/v1/ledger/details/` | Create ledger entry (credit/debit) |
| POST | `/api/v1/payouts/` | Request a payout |

### POST `/api/v1/payouts/`

**Headers:**
```
Idempotency-Key: <uuid>
Content-Type: application/json
```

**Body:**
```json
{
  "merchant_id": 1,
  "amount": 500000,
  "bank_account_id": "HDFC001"
}
```

**Response:**
```json
{
  "payout_id": 1,
  "amount": 500000,
  "balance": 1000000
}
```

---

## Running Tests

Requires PostgreSQL and Redis running locally.

Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Then run:
```bash
python manage.py test payouts --verbosity=2
```

Expected output:
```
test_different_keys_create_separate_payouts ... ok
test_only_one_payout_created ... ok
test_same_key_returns_same_response ... ok
test_balance_never_goes_negative ... ok
test_only_one_of_two_concurrent_requests_succeeds ... ok

Ran 5 tests in ~0.5s
OK
```

Includes:
- Idempotency test: same key twice returns identical response, only one payout created
- Concurrency test: two simultaneous 6000 paise requests against 10000 paise balance — exactly one succeeds

---

## Key Design Decisions

- **Amounts in paise as BigIntegerField** — no floats, no decimals, no rounding errors
- **Balance derived at query time** — never stored, always computed from ledger rows
- **`select_for_update()` on merchant row** — database-level lock prevents concurrent overdraw
- **`on_commit` for Celery dispatch** — task only fires after the transaction commits, preventing the worker from picking up a payout that doesn't exist yet
- **Atomic refund on failure** — ledger credit and status update happen in the same transaction
- **Idempotency keys scoped per merchant, expire after 24h**
