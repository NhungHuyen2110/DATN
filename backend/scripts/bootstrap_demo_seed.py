"""STDIN-only bootstrap of a new, empty, migrated demo DB. Never updates existing rows."""
from decimal import Decimal
import json
import sys
sys.path.insert(0, '/srv')


def main():
    from sqlalchemy import inspect, text
    from app.core.database import engine, SessionLocal
    from app.core.security import hash_password
    from app.models import Role, User, Product, Category, Brand, Material, Gemstone, Collection
    from shared.recovery import validate_backup_reference
    if (engine.url.host, engine.url.port, engine.url.database) != ('postgres', 5432, 'lumiere_test_demo_hosting'):
        raise ValueError('Only the new named demo hosting database is allowed')
    validate_backup_reference('/recovery/backup-reference.json', 'test', 'postgres', 5432, engine.url.database)
    payload = json.load(sys.stdin)
    rows = payload['records']
    if payload.get('confirm_demo') is not True or len(rows) != 500 or len({r['ProductID'] for r in rows}) != 500:
        raise ValueError('Explicit validated 500-product demo payload required')
    with SessionLocal() as db, db.begin():
        if db.scalar(text('SELECT version_num FROM alembic_version')) != '20261121_0009':
            raise ValueError('Expected additive migration head')
        quote = engine.dialect.identifier_preparer.quote
        for table in inspect(engine).get_table_names():
            if table != 'alembic_version' and db.scalar(text('SELECT count(*) FROM ' + quote(table))):
                raise ValueError('Existing data preserved; bootstrap refuses any nonempty table')
        for prefix, model in (('Category', Category), ('Brand', Brand), ('Material', Material),
                              ('Gemstone', Gemstone), ('Collection', Collection)):
            values = {}
            for row in rows:
                key, name = row[prefix+'ID'], row[prefix+'Name']
                if key in values and values[key] != name:
                    raise ValueError('Inconsistent canonical identity')
                values[key] = name
            db.add_all([model(id=key, name=name) for key, name in values.items()])
        db.flush()
        db.add_all([Product(id=r['ProductID'], sku=r['SKU'], barcode=r['Barcode'], name=r['ProductName'],
            category_id=r['CategoryID'], brand_id=r['BrandID'], material_id=r['MaterialID'],
            gemstone_id=r['GemstoneID'], collection_id=r['CollectionID'], weight=Decimal(r['Weight']),
            sale_price=Decimal(r['SalePrice']), wholesale_price=Decimal(r['WholesalePrice']),
            cost_price=Decimal(r['CostPrice']), stock=r['Stock']) for r in rows])
        for identity, role in enumerate(('customer', 'admin', 'staff'), 1):
            password = payload['passwords'][role]
            if not isinstance(password, str) or len(password) < 20:
                raise ValueError('Strong generated demo password required')
            db.add(Role(id=identity, name=role))
            db.flush()
            db.add(User(id=identity, role_id=identity, full_name='Demo '+role, email='demo-'+role+'@example.com',
                        phone='0901234567', password_hash=hash_password(password), is_active=True))
        db.flush()
        for table in ('roles', 'users'):
            db.execute(text("SELECT setval(pg_get_serial_sequence('"+table+"','id'),(SELECT max(id) FROM "+table+'),true)'))
    engine.dispose()
    print(json.dumps({'successful':True, 'products':500, 'demo_users':3, 'orders':0,
                      'existing_rows_overwritten':False, 'credentials_printed':False}))


if __name__ == '__main__':
    main()
