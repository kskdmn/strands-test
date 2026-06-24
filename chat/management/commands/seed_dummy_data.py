from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from chat.models import FactoryLine, InventoryRecord, Product, ProductionOrder, SalesRecord


def month_offset(reference: date, offset: int) -> date:
    year = reference.year
    month = reference.month - offset
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


class Command(BaseCommand):
    help = "Load dummy sales and factory data into SQLite."

    @transaction.atomic
    def handle(self, *args, **options):
        SalesRecord.objects.all().delete()
        ProductionOrder.objects.all().delete()
        InventoryRecord.objects.all().delete()
        FactoryLine.objects.all().delete()
        Product.objects.all().delete()

        products = [
            Product.objects.create(name="Widget A", sku="WGT-A"),
            Product.objects.create(name="Widget B", sku="WGT-B"),
            Product.objects.create(name="Gadget Pro", sku="GAD-PRO"),
        ]

        base_month = date(2025, 6, 1)
        sales_templates = {
            "Widget A": [820, 790, 860, 910, 880, 940, 980, 1020, 990, 1050, 1100, 1150],
            "Widget B": [430, 410, 450, 470, 460, 490, 505, 520, 515, 530, 545, 560],
            "Gadget Pro": [210, 205, 220, 235, 230, 245, 260, 275, 270, 290, 305, 320],
        }
        unit_prices = {
            "Widget A": Decimal("24.50"),
            "Widget B": Decimal("18.75"),
            "Gadget Pro": Decimal("89.00"),
        }

        for product in products:
            for index, units in enumerate(sales_templates[product.name]):
                month = month_offset(base_month, 11 - index)
                SalesRecord.objects.create(
                    product=product,
                    month=month,
                    units_sold=units,
                    revenue=unit_prices[product.name] * units,
                )

        lines = [
            FactoryLine.objects.create(name="Assembly Line 1", status=FactoryLine.Status.RUNNING),
            FactoryLine.objects.create(name="Assembly Line 2", status=FactoryLine.Status.MAINTENANCE),
            FactoryLine.objects.create(name="Packaging Line", status=FactoryLine.Status.RUNNING),
        ]

        now = datetime.now(tz=UTC)
        production_rows = [
            ("Widget A", lines[0], ProductionOrder.Status.IN_PROGRESS, 1200, now - timedelta(days=2), now + timedelta(days=3)),
            ("Widget B", lines[2], ProductionOrder.Status.PLANNED, 800, now + timedelta(days=1), now + timedelta(days=6)),
            ("Gadget Pro", lines[0], ProductionOrder.Status.PLANNED, 450, now + timedelta(days=4), now + timedelta(days=10)),
            ("Widget A", lines[2], ProductionOrder.Status.PLANNED, 1500, now + timedelta(days=8), now + timedelta(days=14)),
        ]

        for product_name, line, status, quantity, start, completion in production_rows:
            product = Product.objects.get(name=product_name)
            ProductionOrder.objects.create(
                product=product,
                line=line,
                status=status,
                quantity=quantity,
                scheduled_start=start,
                estimated_completion=completion,
            )

        inventory_rows = [
            ("Widget A", 1850, 320, 500, "Main Warehouse"),
            ("Widget B", 420, 75, 300, "Main Warehouse"),
            ("Gadget Pro", 95, 40, 150, "East Distribution Center"),
        ]
        for product_name, on_hand, reserved, reorder_point, warehouse in inventory_rows:
            product = Product.objects.get(name=product_name)
            InventoryRecord.objects.create(
                product=product,
                quantity_on_hand=on_hand,
                reserved_quantity=reserved,
                reorder_point=reorder_point,
                warehouse=warehouse,
                last_updated=now,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Product.objects.count()} products, "
                f"{SalesRecord.objects.count()} sales records, "
                f"{FactoryLine.objects.count()} factory lines, "
                f"{ProductionOrder.objects.count()} production orders, and "
                f"{InventoryRecord.objects.count()} inventory records."
            )
        )
