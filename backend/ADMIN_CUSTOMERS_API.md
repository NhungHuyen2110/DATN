# Admin Customers

Backend only. No schema change, migration, seed or frontend change is required.
Uses existing `users`, `roles`, `user_sessions`, `orders`, `payment_transactions`.

## Authentication

All routes require an active Admin with the existing `lumiere_session` HttpOnly
cookie and `get_current_user` / `admin` dependencies. Only `customer` accounts
can be listed, read or changed. Staff/Admin target IDs return 404.

## Routes

- `GET /admin/customers?page=1&page_size=20&search=alice&is_active=true`
  - `page`: 1..2147483647; `page_size`: 1..100 (default 20).
  - `search`: optional, at most 255 characters, trimmed, NUL rejected.
    Case-insensitive literal substring over name/email/phone; `%` and `_` are
    literal characters. Accent-insensitive matching is not implemented.
  - `is_active`: optional boolean; omission includes both statuses.
  - Stable ascending User ID order; total reflects the same filters.
- `GET /admin/customers/{id}`
- `PATCH /admin/customers/{id}/status`, body `{"is_active": false}`.
  Only a JSON boolean is accepted; missing/extra fields are rejected.

IDs must be integers from 1 to 2147483647.
All successful routes return 200. Detail and status return:

```json
{
  "id": 1,
  "full_name": "Customer Example",
  "email": "customer@example.com",
  "phone": null,
  "created_at": "2026-10-01T00:00:00Z",
  "is_active": true,
  "order_count": 0,
  "total_spent_vnd": "0.00"
}
```

The list wraps these records in
`{"items": [...], "page": 1, "page_size": 20, "total": 1}`.
Money is serialized as a Decimal string, matching existing backend conventions.
No password hashes, session tokens/hashes or role internals are exposed.

## Statistics and status transactions

`order_count` counts all actual orders belonging to that User, including
cancelled orders. No join to order items or payment rows is used for counting.

`total_spent_vnd` directly reuses `dashboard.payment_summary_query()` and
`dashboard.classify()`. Each eligible order contributes its `total_vnd` once.
The order must be paid, not cancelled, have exactly one valid verified payment,
matching amount and provider, and no reconciliation exclusions. Refunded,
unpaid, pending/failed, unverified or review-required cases do not contribute.
Delivery is not an extra requirement beyond the existing Dashboard rule.
Equal-valued orders are not deduplicated. Empty totals are zero.
Statistics are batched for the returned customers rather than queried per user.
Dashboard implementation and behavior are unchanged.

Status writes lock the active Admin and then the target Customer User row.
Login already locks that same User before checking `is_active` and issuing a
session. Locking a customer deletes all their sessions in the same transaction.
Unlocking does not create or restore any session. Repeated locks also purge
sessions. Failures roll back both status and session deletion.

## Errors

- 401: absent/invalid/expired session or inactive account.
- 403: authenticated account is not Admin.
- 404: target missing or not a Customer.
- 422: invalid ID, query or body; validation responses omit input values.
- 409: database integrity conflict during status update.
- 500: database failure during status update, with a generic error message.

## Safe automated checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -B backend/tests/test_admin_customers.py
.\.venv\Scripts\python.exe -B backend/tests/run_safe.py
```

The new test entry point and whole-suite runner prohibit connections other than
SQLite in memory. The suite runner also disables dotenv loading. Fixtures do not
modify the restored PostgreSQL data or contact payment gateways.

The login/status test checks PostgreSQL SQL row-lock clauses and both serialized
outcomes. It does not simulate PostgreSQL lock waiting with real concurrent
connections. A two-connection race test still requires an isolated PostgreSQL
test environment; it must not be run against the restored `lumiere_db`.

## Swagger

With the configured Business API running at port 8001, open
`http://localhost:8001/docs`. Execute `POST /auth/login` using an existing Admin;
the browser stores the session cookie. Then use the **Admin Customers** group.
Start with the GET routes. PATCH changes the selected real account and revokes
its sessions when locking, so use a designated test customer for manual checks.
No default account or credentials are supplied by this feature.

## Frontend follow-up (not implemented)

Replace `admin-customers.js` seed/sessionStorage with requests using the existing
API client's cookie credentials. Map `name -> full_name`, `joined -> created_at`,
`active -> is_active`, `orders -> order_count`, `spending -> total_spent_vnd`,
and string demo IDs to numeric backend IDs. Send filters/pagination to the list
endpoint, load detail by ID, and PATCH explicit status instead of toggling local
state. Remove demo reset and fake city/statistics. Use loading/error/401/403
states, escape rendered text, and refresh the page data after status changes.
Existing summary cards would need adjustment: paginated records and filtered
`total` do not provide global active/locked counts. No additional reporting
endpoint is included in this change.
