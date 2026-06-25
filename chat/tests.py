from unittest.mock import MagicMock, patch

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
        from datetime import date

        from chat.models import InventoryMonthlyData, Product

        product = Product.objects.create(
            name="Widget A",
            sku="WGT-A",
            reserved_quantity=50,
            reorder_point=100,
            warehouse="Main Warehouse",
        )
        InventoryMonthlyData.objects.create(
            product=product,
            month=date(2025, 5, 1),
            actual_quantity=250,
        )

        payload = json.loads(fetch_inventory_status(product_name="Widget A"))
        row = payload["inventory"][0]
        self.assertEqual(row["available_quantity"], 200)
        self.assertEqual(row["stock_status"], "healthy")

    def test_orchestrator_prompt_mentions_inventory_assistant(self):
        prompt = build_orchestrator_system_prompt()
        self.assertIn("inventory_assistant", prompt)


class PlanningTests(TestCase):
    def _previous_month_start(self):
        from datetime import timedelta

        from chat.monthly_data import current_month_start

        return (current_month_start() - timedelta(days=1)).replace(day=1)

    def _create_planning_product(self, *, on_hand: int, reserved: int = 0):
        from chat.models import FactoryLine, InventoryMonthlyData, Product

        product = Product.objects.create(
            name="Widget A",
            sku="WGT-A",
            reserved_quantity=reserved,
            reorder_point=50,
            warehouse="Main Warehouse",
        )
        InventoryMonthlyData.objects.create(
            product=product,
            month=self._previous_month_start(),
            actual_quantity=on_hand,
        )
        FactoryLine.objects.create(name="Assembly Line 1", status=FactoryLine.Status.RUNNING)
        return product

    def test_update_sales_forecast_creates_record(self):
        import json
        from datetime import date

        from chat.models import Product, SalesMonthlyData

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
        self.assertEqual(SalesMonthlyData.objects.count(), 1)
        record = SalesMonthlyData.objects.get()
        self.assertEqual(record.month, date(2026, 8, 1))
        self.assertEqual(record.plan_units, 1500)

    def test_suggest_production_plan_recommends_reduction_for_excess_supply(self):
        import json

        from chat.monthly_data import current_month_start
        from chat.models import ProductionMonthlyData, SalesMonthlyData

        product = self._create_planning_product(on_hand=700)
        SalesMonthlyData.objects.create(
            product=product,
            month=current_month_start(),
            plan_units=500,
        )

        payload = json.loads(suggest_production_plan(product_name="Widget A"))

        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["supply_gap"], -200)
        self.assertEqual(recommendation["recommended_action"], "reduce_or_delay_production")
        self.assertIn("Supply exceeds forecast", recommendation["recommendation"])
        self.assertIsNone(recommendation["suggested_line"])
        self.assertEqual(ProductionMonthlyData.objects.count(), 0)

    def test_suggest_production_plan_maintains_balanced_plan(self):
        import json

        from chat.monthly_data import current_month_start
        from chat.models import ProductionMonthlyData, SalesMonthlyData

        product = self._create_planning_product(on_hand=500)
        SalesMonthlyData.objects.create(
            product=product,
            month=current_month_start(),
            plan_units=500,
        )

        payload = json.loads(suggest_production_plan(product_name="Widget A"))

        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["supply_gap"], 0)
        self.assertEqual(recommendation["recommended_action"], "maintain_current_plan")
        self.assertIn("match forecast demand", recommendation["recommendation"])
        self.assertIsNone(recommendation["suggested_line"])
        self.assertEqual(ProductionMonthlyData.objects.count(), 0)

    def test_orchestrator_prompt_mentions_planning_assistant(self):
        prompt = build_orchestrator_system_prompt()
        self.assertIn("planning_assistant", prompt)
        self.assertIn("Do NOT use production_schedule_assistant", prompt)


class ChatServiceTests(TestCase):
    def test_combined_forecast_plan_request_routes_through_orchestrator(self):
        from chat.models import Conversation
        from chat.services import ChatService

        conversation = Conversation.objects.create()
        content = "Update Widget A forecast to 1500 units for August 2026 and suggest a production plan."
        mock_agent = MagicMock(return_value="Forecast updated. Production plan suggested.")

        service = ChatService()
        with patch.object(service, "_get_agent", return_value=mock_agent) as mock_get_agent:
            user_message, assistant_message = service.send_message(conversation.id, content)

        mock_get_agent.assert_called_once_with(conversation.id)
        mock_agent.assert_called_once()
        self.assertEqual(user_message.content, content)
        self.assertEqual(assistant_message.content, "Forecast updated. Production plan suggested.")


class ToolFallbackTests(TestCase):
    def test_runs_json_tool_code_block_through_planning_assistant(self):
        leaked = (
            "```tool_code\n"
            "{\n"
            '  "tool": "planning_assistant",\n'
            '  "query": "Update Widget A forecast to 1500 units for August 2026 and suggest a production plan."\n'
            "}\n"
            "```"
        )
        with patch("chat.tool_fallback.planning_assistant") as mock_planning:
            mock_planning.return_value = "Forecast updated. Build 200 units on Assembly Line 1."
            result = resolve_leaked_tool_response(leaked)

        mock_planning.assert_called_once_with(
            query="Update Widget A forecast to 1500 units for August 2026 and suggest a production plan."
        )
        self.assertEqual(result, "Forecast updated. Build 200 units on Assembly Line 1.")

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
        from chat.models import Product, SalesMonthlyData

        Product.objects.create(name="Widget A", sku="WGT-A")
        leaked = (
            "```tool_code\n"
            'update_sales_forecast(product_name="Widget A", month="2026-08", forecast_units=1500)\n'
            "```"
        )

        result = resolve_leaked_tool_response(leaked)

        self.assertIn("created", result)
        self.assertEqual(SalesMonthlyData.objects.count(), 1)
