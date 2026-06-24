from unittest.mock import patch

from django.test import TestCase

from chat.prompts import build_orchestrator_system_prompt
from chat.tool_fallback import resolve_leaked_tool_response
from chat.tools.catalog import fetch_product_catalog, format_product_catalog
from chat.tools.inventory import fetch_inventory_status
from chat.tools.planning import suggest_production_plan, update_sales_forecast


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


class PlanningTests(TestCase):
    def test_update_sales_forecast_creates_record(self):
        import json

        from chat.models import Product, SalesForecast

        Product.objects.create(name="Widget A", sku="WGT-A")
        payload = json.loads(
            update_sales_forecast(
                product_name="Widget A",
                month="2026-08",
                forecast_units=1500,
                notes="Promo lift",
            )
        )

        self.assertEqual(payload["action"], "created")
        self.assertEqual(payload["forecast"]["forecast_units"], 1500)
        self.assertEqual(SalesForecast.objects.count(), 1)

    def test_suggest_production_plan_flags_supply_gap(self):
        import json
        from datetime import UTC, datetime

        from chat.models import FactoryLine, InventoryRecord, Product, SalesForecast

        product = Product.objects.create(name="Widget A", sku="WGT-A")
        InventoryRecord.objects.create(
            product=product,
            quantity_on_hand=100,
            reserved_quantity=0,
            reorder_point=50,
            warehouse="Main Warehouse",
            last_updated=datetime.now(tz=UTC),
        )
        SalesForecast.objects.create(
            product=product,
            month=datetime.now(tz=UTC).date().replace(day=1),
            forecast_units=500,
        )

        payload = json.loads(suggest_production_plan(product_name="Widget A"))
        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["recommended_action"], "increase_production")
        self.assertGreater(recommendation["supply_gap"], 0)

    def test_orchestrator_prompt_mentions_planning_assistant(self):
        prompt = build_orchestrator_system_prompt()
        self.assertIn("planning_assistant", prompt)
        self.assertIn("Do NOT use production_schedule_assistant", prompt)


class ToolFallbackTests(TestCase):
    def test_redirects_production_schedule_leak_to_planning_assistant(self):
        leaked = (
            "Okay, I've updated the forecast.\n\n"
            "```tool_code\n"
            'production_schedule_assistant(query="Suggest a production plan for Widget A '
            'to meet a sales forecast of 1500 units in August 2026.")\n'
            "```"
        )
        with patch("chat.tool_fallback.planning_assistant") as mock_planning:
            mock_planning.return_value = "Schedule 200 additional units on Assembly Line 1."
            result = resolve_leaked_tool_response(leaked)

        mock_planning.assert_called_once_with(
            query="Suggest a production plan for Widget A to meet a sales forecast of 1500 units in August 2026."
        )
        self.assertEqual(result, "Schedule 200 additional units on Assembly Line 1.")

    def test_runs_update_sales_forecast_from_leaked_tool_code(self):
        from chat.models import Product, SalesForecast

        Product.objects.create(name="Widget A", sku="WGT-A")
        leaked = (
            "```tool_code\n"
            'update_sales_forecast(product_name="Widget A", month="2026-08", forecast_units=1500)\n'
            "```"
        )

        result = resolve_leaked_tool_response(leaked)

        self.assertIn("created", result)
        self.assertEqual(SalesForecast.objects.count(), 1)
