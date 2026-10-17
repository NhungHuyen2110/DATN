"""Create missing account and catalog tables without modifying existing data.

Revision ID: 20261015_0001
Revises: None

This revision intentionally freezes the schema instead of importing live models.
Existing tables must pass a structural preflight before any application DDL.
Offline SQL describes an EMPTY database only; it cannot inspect existing tables.
"""

import re

from alembic import context, op
from alembic.operations.ops import CreateIndexOp, CreateTableOp
import sqlalchemy as sa

revision = "20261015_0001"
down_revision = None
branch_labels = None
depends_on = None


def _schema():
    metadata = sa.MetaData()
    sa.Table(
        "roles", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(30), nullable=False, unique=True),
    )
    users = sa.Table(
        "users", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Index("ix_users_email", users.c.email, unique=True)
    sessions = sa.Table(
        "user_sessions", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Index("ix_user_sessions_user_id", sessions.c.user_id)
    sa.Index("ix_user_sessions_token_hash", sessions.c.token_hash, unique=True)
    sa.Table(
        "categories", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.CheckConstraint("id > 0", name="ck_categories_id_positive"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_categories_name_not_blank"
        ),
    )
    sa.Table(
        "brands", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.CheckConstraint("id > 0", name="ck_brands_id_positive"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_brands_name_not_blank"
        ),
    )
    sa.Table(
        "materials", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.CheckConstraint("id > 0", name="ck_materials_id_positive"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_materials_name_not_blank"
        ),
    )
    sa.Table(
        "gemstones", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.CheckConstraint("id > 0", name="ck_gemstones_id_positive"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_gemstones_name_not_blank"
        ),
    )
    sa.Table(
        "collections", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.CheckConstraint("id > 0", name="ck_collections_id_positive"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_collections_name_not_blank"
        ),
    )
    products = sa.Table(
        "products", metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("sku", sa.String(50), nullable=False, unique=True),
        sa.Column("barcode", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "category_id", sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "brand_id", sa.Integer(),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "material_id", sa.Integer(),
            sa.ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "gemstone_id", sa.Integer(),
            sa.ForeignKey("gemstones.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "collection_id", sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("weight", sa.Numeric(10, 2), nullable=False),
        sa.Column("sale_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("wholesale_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("cost_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.CheckConstraint("id > 0", name="ck_products_id_positive"),
        sa.CheckConstraint("length(trim(sku)) > 0", name="ck_products_sku_not_blank"),
        sa.CheckConstraint("length(trim(barcode)) > 0", name="ck_products_barcode_not_blank"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_products_name_not_blank"),
        sa.CheckConstraint("weight > 0", name="ck_products_weight_positive"),
        sa.CheckConstraint("sale_price >= 0", name="ck_products_sale_price_nonnegative"),
        sa.CheckConstraint("wholesale_price >= 0", name="ck_products_wholesale_price_nonnegative"),
        sa.CheckConstraint("cost_price >= 0", name="ck_products_cost_price_nonnegative"),
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )
    for column in ("category_id", "brand_id", "material_id", "gemstone_id", "collection_id"):
        sa.Index("ix_products_" + column, products.c[column])
    return metadata


def _check_expression(expression):
    # PostgreSQL reflection can render trim(name) as TRIM(BOTH FROM name).
    expression = re.sub(r"trim\(both\s+from\s+", "trim(", str(expression).lower())
    return re.sub(r'[\s()"]', "", expression)


def _validate_existing(inspector, table, dialect):
    """Reject incompatible tables; do not silently stamp a mismatched schema."""
    def mismatch(reason):
        raise RuntimeError(
            "Existing table " + table.name + " differs from initial migration: "
            + reason + ". Review the schema manually; no automatic repair is performed."
        )

    columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    if set(columns) != set(table.c.keys()):
        mismatch("column names")
    for column in table.c:
        actual = columns[column.name]
        if actual["type"].compile(dialect=dialect) != column.type.compile(dialect=dialect):
            mismatch("type of " + column.name)
        if actual["nullable"] != column.nullable:
            mismatch("nullability of " + column.name)
        if column.autoincrement is False and (
            actual.get("default") is not None or actual.get("identity") is not None
        ):
            mismatch("unexpected generated ID on " + column.name)
    if inspector.get_pk_constraint(table.name)["constrained_columns"] != [
        column.name for column in table.primary_key.columns
    ]:
        mismatch("primary key")

    actual_indexes = inspector.get_indexes(table.name)
    actual_unique = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints(table.name)
    }
    actual_unique.update(
        tuple(item["column_names"]) for item in actual_indexes
        if item.get("unique") and not item.get("dialect_options", {}).get("postgresql_where")
    )
    for constraint in table.constraints:
        if isinstance(constraint, sa.UniqueConstraint):
            if tuple(column.name for column in constraint.columns) not in actual_unique:
                mismatch("unique constraint")
    for index in table.indexes:
        expected_columns = tuple(column.name for column in index.columns)
        if not any(
            tuple(item["column_names"]) == expected_columns
            and bool(item["unique"]) == index.unique
            and not item.get("dialect_options", {}).get("postgresql_where")
            for item in actual_indexes
        ):
            mismatch("index " + index.name)

    actual_foreign_keys = inspector.get_foreign_keys(table.name)
    for constraint in table.foreign_key_constraints:
        if not any(
            item["constrained_columns"] == list(constraint.column_keys)
            and item["referred_table"] == constraint.referred_table.name
            and item["referred_schema"] in (None, inspector.default_schema_name)
            and item["referred_columns"] == [element.column.name for element in constraint.elements]
            and (item.get("options", {}).get("ondelete") or "NO ACTION")
            == (constraint.ondelete or "NO ACTION")
            for item in actual_foreign_keys
        ):
            mismatch("foreign key")
    actual_checks = {
        _check_expression(item["sqltext"])
        for item in inspector.get_check_constraints(table.name)
    }
    for constraint in table.constraints:
        if isinstance(constraint, sa.CheckConstraint):
            if _check_expression(constraint.sqltext) not in actual_checks:
                mismatch("check constraint " + str(constraint.name))


def upgrade():
    metadata = _schema()
    existing = set()
    if not context.is_offline_mode():
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        existing = set(inspector.get_table_names())
        # Preflight ALL existing application tables before creating anything.
        for table in metadata.sorted_tables:
            if table.name in existing:
                _validate_existing(inspector, table, connection.dialect)

    for table in metadata.sorted_tables:
        if table.name not in existing:
            op.invoke(CreateTableOp.from_table(table))
            for index in sorted(table.indexes, key=lambda item: item.name):
                op.invoke(CreateIndexOp.from_index(index))


def downgrade():
    raise RuntimeError(
        "Initial schema downgrade is intentionally disabled to preserve existing tables and data."
    )
