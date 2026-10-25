# Coupons / Vouchers

Backend-only implementation. No frontend change, real payment, live migration,
production database modification or Git commit/push is performed by this change.

## API

Existing HttpOnly session cookie authentication is reused. Only an active Admin
can call `/admin/coupons*`. Only an active Customer can validate/redeem coupons.
Unauthenticated/invalid sessions return 401; wrong roles return 403.

| Method | Path | Request / response |
| --- | --- | --- |
| GET | `/admin/coupons` | `page=1`, `page_size=20` (1..100), optional `search` (max 255), `is_active`; returns `{items,page,page_size,total}` |
| GET | `/admin/coupons/{id}` | Coupon record; 404 if absent |
| POST | `/admin/coupons` | Create fields below; 201 and coupon record |
| PATCH | `/admin/coupons/{id}` | At least one create field; 200 and updated record |
| PATCH | `/admin/coupons/{id}/status` | `{"is_active": false}`; 200 and updated record |
| POST | `/checkout/coupon/validate` | `{"coupon_code":"SAVE10"}`; preview below |
| POST | `/orders` | Existing checkout fields plus optional `coupon_code`; existing order response plus nullable `coupon_id`, `coupon_code` |

List order is ascending ID. Search matches literal case-insensitive substrings in
code/description; `%` and `_` are escaped. `is_active` filters the on/off flag,
not derived expiration/exhaustion. IDs: 1..2147483647; invalid queries/body: 422.

Create example:

```json
{
  "code": "SAVE10",
  "discount_type": "percent",
  "discount_value": "10.00",
  "max_discount_vnd": "80000.00",
  "min_order_vnd": "1000000.00",
  "usage_limit": 100,
  "starts_at": "2026-10-01T00:00:00+07:00",
  "ends_at": "2027-01-01T00:00:00+07:00",
  "is_active": true,
  "description": "Example offer"
}
```

Required: code, type, value, starts_at, ends_at. Defaults: min_order=0,
usage_limit=null (unlimited), cap=null (uncapped percent), active=true,
description=null. Fixed coupons require cap=null. Financial fields are finite
Decimal values, up to 38 digits including at most 2 fractional digits. Value and
non-null cap must be positive; percent <=100. Limit is a positive 32-bit integer
or null. Booleans must be JSON booleans. Dates require timezone and start < end.
Description is nullable, max 500 characters, no NUL.

Response adds `id`, server-controlled `used_count`, `created_at`, `updated_at`.
Times are UTC; monetary values are Decimal strings. Partial update permits null
only for cap, limit and description. `used_count` and extra fields are forbidden.
Updates validate the complete merged record. Lowering limit below current count
or colliding with another normalized code returns 409. Missing IDs return 404.
Write database failures return generic 500; validation errors omit input values.

## Pricing and eligibility

Codes are trimmed, uppercased, then restricted to `[A-Z0-9_-]{3,24}`.
Duplicate normalized codes are rejected by a database unique constraint too.
Each order can use one coupon. Fixed reductions or percent reductions (with an
optional cap) apply to merchandise subtotal, excluding shipping. All arithmetic
uses Decimal with sufficient precision for the existing Numeric range.

Coupon reductions are rounded to whole VND using **ROUND_HALF_UP**. Existing
product prices/subtotal retain the existing two-decimal representation. A
rounded reduction of zero, reduction above subtotal, or non-positive payable
total is invalid. There is no free-order payment flow. Old non-coupon checkout
behavior remains unchanged, including existing shipping rules.

Eligibility requires active=true, `starts_at <= now < ends_at`, subtotal meeting
the minimum, available global capacity, and no active usage by this customer.
`used_count` counts currently active usages, not cumulative lifetime redemptions.
Unlimited coupons still respect the storage capacity of a 32-bit usage counter.

Preview reads the real server cart, prices and stock. It never increments the
counter or inserts usage. For a valid 1,000,000 VND cart with the example cap:

```json
{
  "valid": true,
  "reason": null,
  "coupon_code": "SAVE10",
  "subtotal_vnd": "1000000.00",
  "discount_vnd": "80000.00",
  "total_vnd": "920000.00"
}
```

Business-invalid codes return HTTP 200 with `valid=false`, zero discount and the
undiscounted total. Reasons: `not_found`, `inactive`, `not_started`, `expired`,
`exhausted`, `counter_capacity`, `min_order`, `already_used`, `invalid_discount`.
Empty/unavailable cart or insufficient stock returns 409. At actual checkout an
invalid coupon returns 409 instead of silently creating an undiscounted order.
Preview is advisory; every condition is rechecked when placing the order.

## Models, constraints and transactions

- `coupons`: unique normalized code; type/value/amount/time checks;
  `used_count >= 0`, nullable positive limit, count cannot exceed non-null limit.
- `coupon_usages`: restricted foreign keys to coupon/user/order; unique order;
  active/returned status and matching nullable return timestamp.
- Partial unique index `(coupon_id,user_id) WHERE status='active'` enforces one
  active use per customer on PostgreSQL and on memory SQLite fixtures.
- Orders add nullable `coupon_id` and immutable-at-checkout `coupon_code`.
  Existing `discount_vnd` stores the applied reduction. Later Admin edits never
  rewrite existing orders or usages. Coupon IDs retain links if code is renamed;
  customers cannot reuse that same coupon ID merely because its code changed.

Checkout locks User -> CartItems -> Products (ascending ID) -> Coupon. The coupon
row is refreshed after lock acquisition before checking capacity, time, status
and active usage. Order, usage, counter, stock and cart changes commit together.
Same-user calls also serialize on User. Database uniqueness is a final defense;
integrity conflicts roll back the checkout and return 409. Other transaction
failures roll back and return generic errors, preserving stock/cart/counter.

Cancellation retains all existing payment and order transition restrictions.
Only after those checks pass does it lock Products -> Coupon -> Usage, return
the active usage and decrement the counter in the same transaction as stock and
order status changes. A repeated cancellation does not return another use.
Returned usages remain in history but do not block reuse if the coupon is still
valid. Paid, pending-payment or reconciliation-blocked cancellations do not
return coupons. No automatic payment-expiry or refund behavior is introduced.

COD collection and VNPay URL/IPN use the existing order `total_vnd`, now after
discount. Checkout's VNPay amount validation also uses total after discount.
Callback verification, duplicate protection and reconciliation rules are unchanged.
If payment URL creation fails after an order was committed, that order retains
its active usage; only a permitted successful cancellation releases it.

## Migration safety

New revision: `20261023_0006`, parent `20261017_0005`. Creates coupon tables/index,
adds two nullable order columns and their foreign key. No UPDATE/DELETE/reset,
seed or rewriting existing order amounts. Downgrade intentionally refuses to
delete history. The prior migration-head test is updated for the new revision.

**This revision has not been applied to the existing PostgreSQL database.**
Deploying the new code that selects Order requires the migration to be applied
first during the approved deployment window.

After explicit approval, first verify a restorable backup and the current
revision/schema on the intended database. Review the revision and rehearse it on
a restored test database. If the parent is missing or schema diverges, stop and
reconcile; do not use stamp/reset to force it. From the repository root:

```powershell
# Read current revision; connects to the configured database.
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini current

# Inspect only this revision's PostgreSQL SQL, without connecting to the database.
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261017_0005:20261023_0006 --sql

# ONLY after approval of the actual deployment/migration:
.\.venv\Scripts\python.exe -B -m alembic -c backend/alembic.ini upgrade 20261023_0006
```

Adding constraints can lock the orders table; plan the deployment window and
verify revision, existing order amounts/counts and a designated test checkout
after applying. No migration command above was run against live PostgreSQL here.

## Automated tests

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_coupons_api.py
.\.venv\Scripts\python.exe -B backend/tests/run_safe.py
```

Both entry points block all non-memory database connections. Tests cover API
permissions/validation/duplicates, previews without writes, pricing/time/limits,
once-per-customer/reuse after cancellation, last-use recheck, rollback, COD,
mock VNPay URL/IPN and duplicate notifications, SQL lock order and DB uniqueness.
Migration is exercised on memory SQLite with a pre-existing order and compiled
to PostgreSQL SQL offline. These do not establish real PostgreSQL race behavior
or prove migration on the restored production schema.

Final safe regression result: **552 tests passed, 827 subtests passed** (baseline
463 / 727). CouponTests adds 18 coupon-specific test methods and inherits 71
existing Auth/Orders/Payments regression methods, so discovery adds 89 executed
tests rather than 89 distinct new test cases. PostgreSQL race tests below are
not included in these passing totals.

`backend/tests/pg_coupon_races.py` supplies two opt-in PostgreSQL tests: two
customers competing for the last use, and the same customer placing two orders.
They acquire different physical connections and start via a barrier. They only
accept `COUPON_TEST_DATABASE_URL` targeting a dedicated database ending `_test`,
create a unique fixture schema and remove only that schema afterward. They use
model metadata, not live migrations; no real payments are called. Run this file
explicitly after preparing/approving a separate PostgreSQL test environment.
It is excluded from default discovery and has **not been run on PostgreSQL**.

## Swagger and future frontend integration

After approved migration/deployment, open `http://localhost:8001/docs`, log in
with an existing Admin via `/auth/login`, and use the Coupons group. Use future
timezone-aware dates when creating a test coupon. Log out and log in as an active
Customer with a backend cart, preview the code, then POST `/orders` with shipping
fields and optional coupon_code. Use designated test data for write operations.

Frontend remains unchanged. Replace Admin coupon sessionStorage and seed data
with real list/detail/create/patch/status calls using cookie credentials. Map
`type/value/maxDiscount/minOrder/limit/used/start/end/active` to the backend
fields. Remove demo resets and never send used_count. Convert UI dates to
explicit timestamps; for an inclusive final calendar date in Vietnam, send the
next day's local midnight as exclusive ends_at (offset +07:00). Display server
time values in the selected local timezone rather than slicing UTC dates.

Checkout must display the backend cart, call preview with coupon_code only,
render backend monetary strings, and send coupon_code with POST /orders.
Reconcile invalidation between preview and checkout, and use the returned order
total for payment display. Preview does not reserve a use. Handle 401/403/409/422
and loading states; do not silently fall back to demo data or client discounts.
