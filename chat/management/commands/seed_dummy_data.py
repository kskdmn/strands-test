from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from chat.models import (
    FactoryLine,
    InventoryMonthlyData,
    Product,
    ProductionMonthlyData,
    SalesMonthlyData,
)
from chat.monthly_data import DATA_RANGE_END, DATA_RANGE_START, current_month_start, iter_months


def _seasonal_factor(month: date, product_index: int) -> float:
    seasonal = [0.92, 0.95, 1.0, 1.03, 1.05, 1.08, 1.12, 1.1, 1.02, 0.98, 0.94, 0.9]
    growth = 1.0 + (product_index * 0.01) + ((month.year - DATA_RANGE_START.year) * 0.04)
    return seasonal[month.month - 1] * growth


class Command(BaseCommand):
    help = "Load dummy monthly sales, inventory, and production data into SQLite."

    @transaction.atomic
    def handle(self, *args, **options):
        SalesMonthlyData.objects.all().delete()
        InventoryMonthlyData.objects.all().delete()
        ProductionMonthlyData.objects.all().delete()
        FactoryLine.objects.all().delete()
        Product.objects.all().delete()

        product_specs = [
            ("Widget A", "WGT-A", 500, 320, "Main Warehouse", Decimal("24.50"), 900, 1100, 1800),
            ("Widget B", "WGT-B", 300, 75, "Main Warehouse", Decimal("18.75"), 450, 550, 900),
            ("Gadget Pro", "GAD-PRO", 150, 40, "East Distribution Center", Decimal("89.00"), 220, 280, 420),
        ]

        products = []
        for index, (name, sku, reorder_point, reserved, warehouse, unit_price, base_sales, base_inventory, base_production) in enumerate(product_specs):
            products.append(
                {
                    "product": Product.objects.create(
                        name=name,
                        sku=sku,
                        reorder_point=reorder_point,
                        reserved_quantity=reserved,
                        warehouse=warehouse,
                    ),
                    "unit_price": unit_price,
                    "base_sales": base_sales,
                    "base_inventory": base_inventory,
                    "base_production": base_production,
                    "index": index,
                }
            )

        months = iter_months()
        current_month = current_month_start()

        for spec in products:
            product = spec["product"]
            inventory_level = spec["base_inventory"]

            for month in months:
                factor = _seasonal_factor(month, spec["index"])
                sales_units = int(spec["base_sales"] * factor)
                production_units = int(spec["base_production"] * factor)
                inventory_level = max(
                    0,
                    inventory_level + production_units - sales_units,
                )

                if month < current_month:
                    SalesMonthlyData.objects.create(
                        product=product,
                        month=month,
                        actual_units=sales_units,
                        actual_revenue=spec["unit_price"] * sales_units,
                    )
                    InventoryMonthlyData.objects.create(
                        product=product,
                        month=month,
                        actual_quantity=inventory_level,
                    )
                    ProductionMonthlyData.objects.create(
                        product=product,
                        month=month,
                        actual_quantity=production_units,
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
                        plan_quantity=inventory_level,
                    )
                    ProductionMonthlyData.objects.create(
                        product=product,
                        month=month,
                        plan_quantity=production_units,
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
                f"{FactoryLine.objects.count()} factory lines "
                f"from {DATA_RANGE_START.isoformat()} to {DATA_RANGE_END.isoformat()}."
            )
        )
