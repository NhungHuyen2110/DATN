"""Synthetic acceptance fixture ONLY for the named isolated Compose database; refuses existing business rows."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-isolated', action='store_true', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Fixture report exists')
    from sqlalchemy import func, select, text
    from app.core.database import engine, SessionLocal
    from app.core.security import hash_password
    from app.models import Role, User, Product, Category, Brand, Material, Gemstone, Collection, Order, OrderItem
    from app.routers.password_reset import PasswordResetToken
    if engine.url.host != 'postgres' or engine.url.database != 'lumiere_test_rebuild' or engine.url.port != 5432:
        parser.error('Only the dedicated Compose test DB is allowed')
    password = 'test-only-compose-password-2026!'
    reset_token = 'synthetic-compose-reset-2026-abcdef0123456789'
    fixture_env = {}
    with SessionLocal() as db, db.begin():
        if db.scalar(text('SELECT version_num FROM alembic_version')) != '20261121_0009':
            raise ValueError('Expected the verified additive migration head')
        for model in (Role, User, Product, Category, Brand, Material, Gemstone, Collection, Order):
            if db.scalar(select(func.count()).select_from(model)):
                raise ValueError('Existing fixture/business rows: preserve DB without reseeding')
        for index, role in enumerate(('customer', 'admin', 'staff'), 1):
            db.add(Role(id=index, name=role))
            db.flush()
            email = 'lumiere-e2e-' + role + '@example.com'
            db.add(User(id=index, role_id=index, full_name='Synthetic ' + role, email=email,
                        phone='0901234567', password_hash=hash_password(password), is_active=True))
            fixture_env['LUMIERE_E2E_' + role.upper() + '_EMAIL'] = email
            fixture_env['LUMIERE_E2E_' + role.upper() + '_PASSWORD'] = password
        db.add(User(id=4, role_id=1, full_name='Synthetic reset customer', email='lumiere-reset@example.com',
                    phone='0901234567', password_hash=hash_password(password), is_active=True))
        db.flush()
        db.add(PasswordResetToken(user_id=4, token_hash=hashlib.sha256(reset_token.encode()).hexdigest(),
                                 expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
        fixture_env.update({'LUMIERE_E2E_RESET_EMAIL': 'lumiere-reset@example.com',
            'LUMIERE_E2E_RESET_OLD_PASSWORD': password, 'LUMIERE_E2E_RESET_TOKEN': reset_token})
        for model, name, identity in ((Category, 'Nhẫn', 1), (Brand, 'Synthetic', 1),
            (Material, 'Bạc 925', 1), (Gemstone, 'CZ', 6), (Collection, 'Synthetic', 1)):
            db.add(model(id=identity, name=name))
        db.flush()
        for pid in range(1, 6):
            db.add(Product(id=pid, sku='SYNTHETIC' + str(pid), barcode='90000' + str(pid),
                name='Nhẫn kiểm thử ' + str(pid), category_id=1, brand_id=1, material_id=1,
                gemstone_id=6, collection_id=1, weight=1, sale_price=1000000, wholesale_price=800000,
                cost_price=600000, stock=100))
        db.flush()
        for oid, state in ((101, 'pending'), (102, 'pending'), (201, 'delivered'), (202, 'delivered')):
            db.add(Order(id=oid, code='E2E-' + str(oid), user_id=1, recipient_name='Synthetic customer',
                phone='0901234567', address='Synthetic isolated address', status=state, payment_status='unpaid',
                payment_method='cod', stock_restored=False, subtotal_vnd=1000000, shipping_vnd=0,
                discount_vnd=0, total_vnd=1000000))
            db.flush()
            db.add(OrderItem(order_id=oid, product_id=1, sku='SYNTHETIC1', product_name='Synthetic ring',
                            quantity=1, unit_price_vnd=1000000, line_total_vnd=1000000))
        db.flush()
        for table in ('roles', 'users', 'orders'):
            db.execute(text("SELECT setval(pg_get_serial_sequence('" + table + "', 'id'), (SELECT max(id) FROM " + table + '), true)'))
    fixture_env.update({'LUMIERE_E2E_ORDER_ID': '101', 'LUMIERE_E2E_ORDER_STATUS': 'confirmed',
        'LUMIERE_E2E_COD_ORDER_ID': '201', 'LUMIERE_E2E_ADMIN_ORDER_ID': '101', 'LUMIERE_E2E_STAFF_ORDER_ID': '102',
        'LUMIERE_E2E_ADMIN_COD_ORDER_ID': '201', 'LUMIERE_E2E_STAFF_COD_ORDER_ID': '202',
        'LUMIERE_E2E_STOCK_PRODUCT_ID': '1'})
    with args.report.open('x', encoding='utf-8') as output:
        json.dump({'synthetic_only': True, 'products': 5, 'roles': 3, 'fixture_env': fixture_env}, output)
    engine.dispose()
    print(json.dumps({'synthetic_only': True, 'products': 5, 'roles': 3, 'production_accessed': False}))


if __name__ == '__main__':
    main()
