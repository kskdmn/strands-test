from django.test import TestCase

from chat.prompts import build_orchestrator_system_prompt
from chat.tools.catalog import fetch_product_catalog, format_product_catalog
from chat.tools.inventory import fetch_inventory_status


class CatalogTests(TestCase):
    def test_orchestrator_prompt_includes_database_products(self):
        from chat.models import Product

        Product.objects.create(name="Widget A", sku="WGT-A")
        Product.objects.create(name="Gadget Pro", sku="GAD-PRO")

        prompt = build_orchestrator_system_prompt()
        self.assertIn("Widget A", prompt)
        self.assertIn("Gadget Pro", prompt)
        self.assertIn("list_available_products", prompt)

    def test_format_product_catalog_uses_database_names(self):
        from chat.models import Product

        Product.objects.create(name="Widget A", sku="WGT-A")
        Product.objects.create(name="Gadget Pro", sku="GAD-PRO")

        text = format_product_catalog(fetch_product_catalog())
        self.assertIn("Widget A", text)
        self.assertIn("Gadget Pro", text)
        self.assertNotIn("Widget X", text)


class InventoryTests(TestCase):
    def test_fetch_inventory_status_returns_stock_levels(self):
        import json
        from datetime import UTC, datetime

        from chat.models import InventoryRecord, Product

        product = Product.objects.create(name="Widget A", sku="WGT-A")
        InventoryRecord.objects.create(
            product=product,
            quantity_on_hand=250,
            reserved_quantity=50,
            reorder_point=100,
            warehouse="Main Warehouse",
            last_updated=datetime.now(tz=UTC),
        )

        payload = json.loads(fetch_inventory_status(product_name="Widget A"))
        row = payload["inventory"][0]
        self.assertEqual(row["available_quantity"], 200)
        self.assertEqual(row["stock_status"], "healthy")

    def test_orchestrator_prompt_mentions_inventory_assistant(self):
        prompt = build_orchestrator_system_prompt()
        self.assertIn("inventory_assistant", prompt)
