"""Append synthetic browser fixtures to the dedicated Compose test DB, preserving prior test rows."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Existing report preserved')
    from sqlalchemy import select, func, text
    from app.core.database import engine, SessionLocal
    from app.core.security import hash_password
    from app.models import User, Role, Product, Order, OrderItem
    from app.routers.password_reset import PasswordResetToken
    if (engine.url.host, engine.url.port, engine.url.database) != ('postgres', 5432, 'lumiere_test_rebuild'):
        parser.error('Only the dedicated synthetic Compose DB is allowed')
    nonce = secrets.token_hex(8)
    password = 'test-only-compose-password-2026!'
    token = secrets.token_urlsafe(32)
    email = 'lumiere-reset-' + nonce + '@example.com'
    fixture = {'synthetic_only': True, 'project': 'lumiere-rebuild-test', 'fixture_env': {}}
    with SessionLocal() as db, db.begin():
        if db.scalar(text('SELECT version_num FROM alembic_version')) not in {'20261121_0009','20261122_0010'}:
            raise ValueError('Unexpected migration head')
        if db.scalar(select(func.count()).select_from(Product)) != 5:
            raise ValueError('Only the five-product synthetic fixture is supported')
        for pid in range(1, 6):
            if db.get(Product, pid).sku != 'SYNTHETIC' + str(pid):
                raise ValueError('Not the expected synthetic catalog')
        for identity, role in ((1, 'customer'), (2, 'admin'), (3, 'staff')):
            user = db.get(User, identity)
            if not user or user.email != 'lumiere-e2e-' + role + '@example.com' or db.get(Role, user.role_id).name != role:
                raise ValueError('Expected synthetic role identities')
        reset = User(role_id=1, full_name='Synthetic reset customer', email=email,
                     phone='0901234567', password_hash=hash_password(password), is_active=True)
        db.add(reset)
        db.flush()
        db.add(PasswordResetToken(user_id=reset.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                 expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
        fixture['fixture_env'].update({'LUMIERE_E2E_RESET_EMAIL': email,
            'LUMIERE_E2E_RESET_OLD_PASSWORD': password, 'LUMIERE_E2E_RESET_TOKEN': token})
        for role in ('ADMIN', 'STAFF'):
            for state in ('pending', 'delivered'):
                order = Order(code='LAB-' + nonce + '-' + role + '-' + state, user_id=1,
                    recipient_name='Synthetic customer', phone='0901234567', address='Synthetic isolated address',
                    status=state, payment_status='unpaid', payment_method='cod', stock_restored=False,
                    subtotal_vnd=1000000, shipping_vnd=0, discount_vnd=0, total_vnd=1000000)
                db.add(order)
                db.flush()
                db.add(OrderItem(order_id=order.id, product_id=1, sku='SYNTHETIC1', product_name='Synthetic ring',
                    quantity=1, unit_price_vnd=1000000, line_total_vnd=1000000))
                suffix = '_COD_ORDER_ID' if state == 'delivered' else '_ORDER_ID'
                fixture['fixture_env']['LUMIERE_E2E_' + role + suffix] = str(order.id)
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(fixture, output)
    engine.dispose()
    print(json.dumps({'synthetic_only': True, 'new_reset_users': 1, 'new_orders': 4,
                      'previous_rows_preserved': True, 'production_accessed': False}))


if __name__ == '__main__':
    main()
