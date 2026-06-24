from django.test import TestCase

from chat.prompts import build_orchestrator_system_prompt
from chat.tools.catalog import fetch_product_catalog, format_product_catalog


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
