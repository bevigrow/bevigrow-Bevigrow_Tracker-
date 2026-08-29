"""Create tables, the admin account, and (in dev) representative demo data."""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, ensure_schema
from .models import (
    Activity,
    Channel,
    Contact,
    DealStatus,
    DocType,  # noqa: F401  (imported so the enum is registered before create_all)
    Reminder,
    Role,
    TradeType,
    User,
)
from .bevi_stoq_models import StockMovementType  # noqa: F401  (imported so the enum is registered before create_all)
from .security import hash_password

log = logging.getLogger("bevigrow.seed")


# Columns added after the first release. `create_all` only creates missing
# TABLES — it never alters an existing one — so a deployed database would keep
# its old shape and every query naming a new column would fail. Each entry is
# applied with ADD COLUMN IF NOT EXISTS, which is safe to re-run on every boot.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    # (table, column, DDL type)
    ("users", "auth_provider", "VARCHAR(20) DEFAULT 'password' NOT NULL"),
    ("users", "google_sub", "VARCHAR(64)"),
    ("users", "avatar_url", "VARCHAR(500)"),
    ("users", "last_login", "TIMESTAMP WITH TIME ZONE"),
    ("users", "reset_token_hash", "VARCHAR(128)"),
    ("users", "reset_token_expires", "TIMESTAMP WITH TIME ZONE"),
    # RFQ fields — marketplace enquiries carry trade terms the first release
    # had nowhere to put.
    ("contacts", "quantity_note", "VARCHAR(200)"),
    ("contacts", "hs_code", "VARCHAR(60)"),
    ("contacts", "shipping_terms", "VARCHAR(40)"),
    ("contacts", "destination_port", "VARCHAR(150)"),
    ("contacts", "payment_terms", "VARCHAR(80)"),
    ("contacts", "origin_preference", "VARCHAR(200)"),
    ("contacts", "sourcing_from", "VARCHAR(150)"),
    ("contacts", "rfq_source", "VARCHAR(150)"),
    ("contacts", "rfq_reference", "VARCHAR(120)"),
    # File bytes moved off the ephemeral container filesystem.
    ("documents", "content", "BYTEA"),
    # Sending moved off SMTP: the hosting plan blocks outbound mail ports, so
    # an HTTP provider is needed and the account has to say which one it is.
    ("campaigns", "deleted_at", "TIMESTAMP WITH TIME ZONE"),
    ("campaigns", "allow_recontact", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("email_accounts", "imap_host", "VARCHAR(200) DEFAULT 'imap.gmail.com'"),
    ("email_accounts", "imap_port", "INTEGER DEFAULT 993"),
    ("email_accounts", "imap_user", "VARCHAR(255) DEFAULT ''"),
    ("email_accounts", "imap_password_enc", "BYTEA"),
    ("email_accounts", "reply_check_enabled", "BOOLEAN DEFAULT TRUE NOT NULL"),
    ("email_accounts", "last_reply_check_at", "TIMESTAMP WITH TIME ZONE"),
    ("email_accounts", "last_reply_error", "VARCHAR(400)"),
    ("email_accounts", "provider", "VARCHAR(20) DEFAULT 'smtp' NOT NULL"),
    ("email_accounts", "api_key_enc", "BYTEA"),
    ("email_accounts", "reply_to", "VARCHAR(255)"),
    # Links a prospect to the quote it became.
    # The foreign key is added separately below — ADD COLUMN alone would
    # not create one, and ON DELETE SET NULL is the point of it.
    ("outreach", "quote_id", "INTEGER"),
    # Pre-send review and controlled resend workflow.
    ("campaign_targets", "is_resend_approved", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("campaign_targets", "resend_reason", "VARCHAR(200)"),
    ("campaign_targets", "resend_notes", "TEXT"),
    ("campaign_targets", "approved_by_id", "INTEGER"),
    ("campaign_targets", "approved_at", "TIMESTAMP WITH TIME ZONE"),
    # Bevi Stoq inventory management - COMPLETE SCHEMA
    # Added in phases; safe to re-run (uses ADD COLUMN IF NOT EXISTS)

    # Categories: audit timestamps
    ("bs_categories", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_categories", "updated_by_user_id", "INTEGER"),

    # Products: alert quantity (optional) + audit
    ("bs_products", "alert_quantity", "FLOAT"),
    ("bs_products", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_products", "updated_by_user_id", "INTEGER"),

    # Locations: audit timestamps
    ("bs_locations", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_locations", "updated_by_user_id", "INTEGER"),

    # Inventory: audit timestamps (updated_by_user_id required for FK)
    ("bs_inventory", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_inventory", "updated_by_user_id", "INTEGER DEFAULT 1"),

    # Stock movements: location tracking
    ("bs_stock_movements", "from_location_id", "INTEGER"),
    ("bs_stock_movements", "to_location_id", "INTEGER"),

    # Restocks: supplier + cost tracking + status
    ("bs_restocks", "restock_date", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_restocks", "supplier_name", "VARCHAR(200)"),
    ("bs_restocks", "cost_per_unit", "FLOAT"),
    ("bs_restocks", "total_cost", "FLOAT"),
    ("bs_restocks", "reference_id", "VARCHAR(100)"),
    ("bs_restocks", "notes", "TEXT"),
    ("bs_restocks", "status", "VARCHAR(50) DEFAULT 'pending'"),
    ("bs_restocks", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_restocks", "updated_by_user_id", "INTEGER"),

    # Customer requirements: contact link + audit
    ("bs_customer_requirements", "contact_id", "INTEGER"),
    ("bs_customer_requirements", "status", "VARCHAR(50) DEFAULT 'pending'"),
    ("bs_customer_requirements", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_customer_requirements", "updated_by_user_id", "INTEGER"),

    # Requirement items: fulfilled tracking
    ("bs_requirement_items", "quantity_reserved", "FLOAT DEFAULT 0 NOT NULL"),
    ("bs_requirement_items", "quantity_fulfilled", "FLOAT DEFAULT 0 NOT NULL"),

    # Customer purchases: payment + audit
    ("bs_customer_purchases", "contact_id", "INTEGER"),
    ("bs_customer_purchases", "payment_status", "VARCHAR(50) DEFAULT 'pending'"),
    ("bs_customer_purchases", "payment_method", "VARCHAR(100)"),
    ("bs_customer_purchases", "amount", "FLOAT DEFAULT 0 NOT NULL"),
    ("bs_customer_purchases", "notes", "TEXT"),
    ("bs_customer_purchases", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_customer_purchases", "updated_by_user_id", "INTEGER"),

    # Combos: audit timestamps
    ("bs_combos", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
    ("bs_combos", "updated_by_user_id", "INTEGER"),
]


def _existing_columns(conn, table: str) -> set[str]:
    if settings.is_sqlite:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).all()
        return {r[1] for r in rows}
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t AND table_schema = :s"
        ),
        {"t": table, "s": settings.schema or "public"},
    ).scalars()
    return set(rows)


def migrate_columns() -> None:
    """Add columns introduced after the initial deployment. Idempotent."""
    prefix = f'"{settings.schema}".' if settings.schema else ""
    with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            if column in _existing_columns(conn, table):
                continue
            # SQLite understands neither IF NOT EXISTS here nor a timezone-aware
            # type, so keep the statement plain and rely on the guard above.
            col_type = ddl.replace("TIMESTAMP WITH TIME ZONE", "TIMESTAMP") if settings.is_sqlite else ddl
            conn.execute(text(f"ALTER TABLE {prefix}{table} ADD COLUMN {column} {col_type}"))
            log.info("Added column %s.%s", table, column)

        # A column added by ALTER TABLE carries no foreign key, however the
        # model declares one: `create_all` never alters an existing table, and
        # the DDL above is only a type. Without the constraint the database
        # will not apply ON DELETE SET NULL, so deleting a quote leaves the
        # outreach row pointing at an id that no longer exists — and the UI
        # then offers to open a quote that is gone.
        #
        # Adding it separately also repairs deployments that already ran the
        # plain ADD COLUMN. Stale references are cleared first, because
        # Postgres validates existing rows before accepting the constraint.
        if not settings.is_sqlite:
            has_fk = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON tc.constraint_name = kcu.constraint_name "
                    "WHERE tc.table_name = 'outreach' AND tc.table_schema = :s "
                    "  AND tc.constraint_type = 'FOREIGN KEY' "
                    "  AND kcu.column_name = 'quote_id'"
                ),
                {"s": settings.schema or "public"},
            ).first()
            if not has_fk:
                conn.execute(
                    text(
                        f"UPDATE {prefix}outreach SET quote_id = NULL WHERE quote_id IS NOT NULL "
                        f"AND quote_id NOT IN (SELECT id FROM {prefix}contacts)"
                    )
                )
                conn.execute(
                    text(
                        f"ALTER TABLE {prefix}outreach "
                        f"ADD CONSTRAINT outreach_quote_id_fkey "
                        f"FOREIGN KEY (quote_id) REFERENCES {prefix}contacts (id) "
                        f"ON DELETE SET NULL"
                    )
                )
                log.info("Added foreign key outreach.quote_id -> contacts.id")

        # `country` started out NOT NULL. Marketplace RFQs often omit it, and
        # rejecting the row would lose the enquiry, so the constraint is
        # dropped where it still exists.
        if not settings.is_sqlite:
            try:
                conn.execute(
                    text(f"ALTER TABLE {prefix}contacts ALTER COLUMN country DROP NOT NULL")
                )
            except Exception:  # noqa: BLE001 - already nullable
                pass

        # google_sub must be unique, but only where it is set.
        if not settings.is_sqlite:
            conn.execute(
                text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub "
                    f"ON {prefix}users (google_sub) WHERE google_sub IS NOT NULL"
                )
            )

        # Drop old low_stock_alert_level column if it still exists (renamed to alert_quantity)
        if not settings.is_sqlite:
            try:
                existing_cols = _existing_columns(conn, "bs_products")
                if "low_stock_alert_level" in existing_cols:
                    conn.execute(text(f"ALTER TABLE {prefix}bs_products DROP COLUMN low_stock_alert_level CASCADE"))
                    log.info("Dropped old column bs_products.low_stock_alert_level (migrated to alert_quantity)")
            except Exception as e:
                log.warning(f"Could not drop old low_stock_alert_level column: {e}")


def create_tables() -> None:
    ensure_schema()
    Base.metadata.create_all(bind=engine)
    migrate_columns()


def ensure_admin(db: Session) -> User:
    email = settings.SEED_ADMIN_EMAIL.lower().strip()
    admin = db.scalar(select(User).where(User.email == email))
    if admin:
        return admin
    admin = User(
        name=settings.SEED_ADMIN_NAME,
        email=email,
        role=Role.admin,
        hashed_password=hash_password(settings.SEED_ADMIN_PASSWORD),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    log.info("Created admin account %s", email)
    return admin


DEMO_CONTACTS = [
    ("ABC Coffee GmbH", "Germany", "Lukas Weber", TradeType.export, "Arabica Roasted Beans", 2000, "Medium Roast", "Arabica", DealStatus.quotation_sent, 18500),
    ("Nordic Roasters AB", "Sweden", "Elin Karlsson", TradeType.export, "Single Origin Green Beans", 5000, "Light Roast", "Arabica", DealStatus.negotiation, 41000),
    ("Bosphorus Coffee Co.", "Turkey", "Emre Yilmaz", TradeType.export, "Espresso Blend", 3200, "Dark Roast", "Arabica/Robusta", DealStatus.sample_sent, 26400),
    ("Sakura Bean Trading", "Japan", "Aiko Tanaka", TradeType.export, "Washed Specialty Grade", 800, "Light Roast", "Arabica", DealStatus.order_confirmed, 22000),
    ("Gulf Beverage LLC", "UAE", "Omar Al Farsi", TradeType.export, "Instant Coffee Granules", 12000, "Medium Roast", "Robusta", DealStatus.shipment_in_progress, 68000),
    ("Highland Estates Ltd", "Kenya", "Grace Wanjiru", TradeType.import_, "AA Washed Green Beans", 9000, "Green", "Arabica", DealStatus.production, 54000),
    ("Cerrado Growers Coop", "Brazil", "Rafael Souza", TradeType.import_, "Natural Process Green", 25000, "Green", "Arabica", DealStatus.completed, 112000),
    ("Dalat Robusta Farms", "Vietnam", "Nguyen Minh", TradeType.import_, "Grade 1 Robusta", 30000, "Green", "Robusta", DealStatus.delivered, 87000),
    ("Andes Origin SAS", "Colombia", "Camila Restrepo", TradeType.import_, "Excelso EP Green", 15000, "Green", "Arabica", DealStatus.contacted, 63000),
    ("Maple Cup Distributors", "Canada", "Ryan Doucette", TradeType.export, "Retail Ground Coffee", 1500, "Medium-Dark", "Arabica", DealStatus.new_lead, 9800),
    ("Milano Caffe Srl", "Italy", "Giulia Rossi", TradeType.export, "Espresso Blend", 4000, "Dark Roast", "Arabica/Robusta", DealStatus.new_lead, 31000),
    ("Sydney Brew Works", "Australia", "Hannah Price", TradeType.export, "Cold Brew Concentrate Base", 2600, "Medium Roast", "Arabica", DealStatus.rejected, 0),
]

DEMO_NOTES = [
    ("Called {company}. They asked for {qty} kg of {product} and requested a quotation by tomorrow.",
     "Buyer confirmed budget is approved and wants FOB pricing."),
    ("Sent the {product} spec sheet over email to {company}. Discussed lead times and packaging options.",
     "They will review internally and revert within three working days."),
    ("WhatsApp check-in with {company} about the pending sample shipment of {product}.",
     "Samples received; cupping scheduled for next week."),
    ("Video meeting with {company}. Walked through certifications, moisture content and shipping schedule for {qty} kg.",
     "Requested a revised offer with CIF terms."),
    ("LinkedIn outreach to {company} introducing BeviGrow's {product} programme.",
     "Connected and asked for the current origin list."),
]


def seed_demo_data(db: Session, admin: User) -> None:
    if db.scalar(select(func.count(Contact.id))):
        return  # already seeded

    rng = random.Random(30)
    now = datetime.now(timezone.utc)

    for (
        company, country, person, trade, product, qty, roast, bean, status, value,
    ) in DEMO_CONTACTS:
        created = now - timedelta(days=rng.randint(8, 70))
        slug = company.lower().replace(" ", "").replace(".", "")[:14]
        contact = Contact(
            company_name=company,
            country=country,
            contact_person=person,
            email=f"{person.split()[0].lower()}@{slug}.com",
            phone=f"+{rng.randint(1, 99)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
            whatsapp=f"+{rng.randint(1, 99)}{rng.randint(1000000, 9999999)}",
            trade_type=trade,
            coffee_product=product,
            quantity_kg=float(qty),
            roast_preference=roast,
            bean_type=bean,
            estimated_value_usd=float(value),
            status=status,
            owner_id=admin.id,
            created_at=created,
            updated_at=created,
            notes=f"{trade.value.rstrip('_').title()} opportunity for {product}.",
        )
        db.add(contact)
        db.flush()

        for i in range(rng.randint(2, 5)):
            occurred = now - timedelta(days=rng.randint(1, 40), hours=rng.randint(0, 20))
            template, reply = DEMO_NOTES[rng.randrange(len(DEMO_NOTES))]
            discussion = template.format(company=company, qty=f"{qty:,}", product=product)
            activity = Activity(
                contact_id=contact.id,
                user_id=admin.id,
                occurred_at=occurred,
                channel=rng.choice(list(Channel)),
                discussion=discussion,
                customer_reply=reply,
                ai_summary=(
                    f"Spoke with {company}, {country}, regarding a requirement for "
                    f"{qty:,} kg of {product}. {reply} Follow-up pending."
                ),
            )
            db.add(activity)
            if i == 0:
                contact.last_contacted_at = occurred

        if status not in {DealStatus.completed, DealStatus.rejected, DealStatus.delivered}:
            due = date.today() + timedelta(days=rng.randint(-4, 8))
            contact.next_follow_up = due
            db.add(
                Reminder(
                    contact_id=contact.id,
                    due_date=due,
                    message=f"Follow up with {company} on the {product} discussion",
                    source="manual",
                    priority=rng.choice(["low", "medium", "high"]),
                )
            )

    db.commit()
    log.info("Seeded %d demo contacts", len(DEMO_CONTACTS))


def run(with_demo: bool | None = None) -> None:
    create_tables()
    db = SessionLocal()
    try:
        admin = ensure_admin(db)
        should_seed = (not settings.is_production) if with_demo is None else with_demo
        if should_seed:
            seed_demo_data(db, admin)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
    print("Database ready.")
