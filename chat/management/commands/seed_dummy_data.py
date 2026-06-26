import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from chat.models import (
    FactoryLine,
    InventoryMonthlyData,
    Product,
    ProductionMonthlyData,
    SalesMonthlyData,
)
from chat.monthly_data import current_month_start

MONTH_ABBREV = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

PRODUCT_SPECS = {
    "Widget A": ("WGT-A", 500, 320, "Main Warehouse", Decimal("24.50")),
    "Widget B": ("WGT-B", 300, 75, "Main Warehouse", Decimal("18.75")),
    "Gadget Pro": ("GAD-PRO", 150, 40, "East Distribution Center", Decimal("89.00")),
}


def _parse_month_label(label: str) -> date:
    left, right = (part.strip() for part in label.split("-", 1))
    if left.isdigit():
        return date(2000 + int(left), MONTH_ABBREV[right], 1)
    return date(2000 + int(right), MONTH_ABBREV[left], 1)


def _parse_int_cells(cells: list[str]) -> list[int]:
    return [int(cell) for cell in cells if cell.strip()]


def load_psi_csv(path: Path) -> dict[str, dict[date, dict[str, int]]]:
    products: dict[str, dict[date, dict[str, int]]] = {}
    current_product: str | None = None
    current_months: list[date] = []

    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row or not row[0].strip():
                continue

            label = row[0].strip()
            if label.startswith("Product Name:"):
                current_product = label.split(":", 1)[1].strip()
                products[current_product] = {}
                current_months = []
                continue

            if current_product is None:
                continue

            if label == "Month":
                current_months = [_parse_month_label(cell) for cell in row[1:] if cell.strip()]
                continue

            if label not in {"Production", "Sales", "Inventory"} or not current_months:
                continue

            values = _parse_int_cells(row[1:])
            product_data = products[current_product]
            for month, value in zip(current_months, values, strict=True):
                product_data.setdefault(month, {})
                product_data[month][label.lower()] = value

    return products


class Command(BaseCommand):
    help = "Load monthly sales, inventory, and production data from docs/dummy_psi.csv."

    @transaction.atomic
    def handle(self, *args, **options):
        psi_path = Path(settings.BASE_DIR) / "docs" / "dummy_psi.csv"
        psi_data = load_psi_csv(psi_path)

        SalesMonthlyData.objects.all().delete()
        InventoryMonthlyData.objects.all().delete()
        ProductionMonthlyData.objects.all().delete()
        FactoryLine.objects.all().delete()
        Product.objects.all().delete()

        current_month = current_month_start()

        for product_name, monthly_values in psi_data.items():
            if product_name not in PRODUCT_SPECS:
                raise ValueError(f"Unknown product in {psi_path.name}: {product_name}")

            sku, reorder_point, reserved, warehouse, unit_price = PRODUCT_SPECS[product_name]
            product = Product.objects.create(
                name=product_name,
                sku=sku,
                reorder_point=reorder_point,
                reserved_quantity=reserved,
                warehouse=warehouse,
            )

            for month in sorted(monthly_values):
                values = monthly_values[month]
                sales_units = values["sales"]
                inventory_quantity = values["inventory"]
                production_quantity = values["production"]

                if month < current_month:
                    SalesMonthlyData.objects.create(
                        product=product,
                        month=month,
                        actual_units=sales_units,
                        actual_revenue=unit_price * sales_units,
                    )
                    InventoryMonthlyData.objects.create(
                        product=product,
                        month=month,
                        actual_quantity=inventory_quantity,
                    )
                    ProductionMonthlyData.objects.create(
                        product=product,
                        month=month,
                        actual_quantity=production_quantity,
                    )
                else:
                    SalesMonthlyData.objects.create(
                        product=product,
                        month=month,
                        plan_units=sales_units,
                        notes="Seeded plan" if month == current_month else "",
                    )
                    InventoryMonthlyData.objects.create(
                        product=product,
                        month=month,
                        plan_quantity=inventory_quantity,
                    )
                    ProductionMonthlyData.objects.create(
                        product=product,
                        month=month,
                        plan_quantity=production_quantity,
                    )

        FactoryLine.objects.bulk_create(
            [
                FactoryLine(name="Assembly Line 1", status=FactoryLine.Status.RUNNING),
                FactoryLine(name="Assembly Line 2", status=FactoryLine.Status.MAINTENANCE),
                FactoryLine(name="Packaging Line", status=FactoryLine.Status.RUNNING),
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Product.objects.count()} products, "
                f"{SalesMonthlyData.objects.count()} sales monthly records, "
                f"{InventoryMonthlyData.objects.count()} inventory monthly records, "
                f"{ProductionMonthlyData.objects.count()} production monthly records, and "
                f"{FactoryLine.objects.count()} factory lines from {psi_path.name}."
            )
        )
