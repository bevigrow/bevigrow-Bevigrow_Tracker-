"""Create tables, the admin account, and (in dev) representative demo data."""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
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
from .security import hash_password

log = logging.getLogger("bevigrow.seed")


def create_tables() -> None:
    ensure_schema()
    Base.metadata.create_all(bind=engine)


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
