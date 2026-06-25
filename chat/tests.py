from unittest.mock import MagicMock, patch

from django.test import TestCase

from chat.message_parts import build_assistant_parts, split_turn_messages
from chat.prompts import build_orchestrator_system_prompt
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
                year=2026,
                month="August",
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

    def test_update_sales_forecast_accepts_flexible_month_formats(self):
        import json
        from datetime import date

        from chat.models import Product, SalesMonthlyData

        Product.objects.create(name="Widget A", sku="WGT-A")
        cases = [
            ("8", 2026, date(2026, 8, 1)),
            ("08", 2026, date(2026, 8, 1)),
            ("Aug", 2026, date(2026, 8, 1)),
            ("August", 2026, date(2026, 8, 1)),
            (8, 2026, date(2026, 8, 1)),
            ("1", 2027, date(2027, 1, 1)),
            ("01", 2027, date(2027, 1, 1)),
            ("Jan", 2027, date(2027, 1, 1)),
            ("January", 2027, date(2027, 1, 1)),
        ]

        for month_value, year_value, expected_month in cases:
            with self.subTest(month=month_value, year=year_value):
                SalesMonthlyData.objects.all().delete()
                payload = json.loads(
                    update_sales_forecast(
                        product_name="Widget A",
                        year=year_value,
                        month=month_value,
                        forecast_units=100,
                    )
                )
                self.assertEqual(payload["action"], "created")
                record = SalesMonthlyData.objects.get()
                self.assertEqual(record.month, expected_month)

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


class MessagePartsTests(TestCase):
    def test_split_turn_messages_treats_tool_use_as_thinking(self):
        new_messages = [
            {
                "role": "assistant",
                "content": [
                    {"text": "I'll check inventory details."},
                    {"toolUse": {"name": "inventory_assistant", "input": {"query": "Stock for Widget A"}}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "status": "success",
                            "content": [{"text": "500 units available."}],
                        }
                    }
                ],
            },
            {
                "role": "assistant",
                "content": [{"text": "Widget A has 500 units available."}],
            },
        ]

        thinking, final_answer = split_turn_messages(new_messages)

        self.assertIn("I'll check inventory details.", thinking)
        self.assertIn("inventory_assistant", thinking)
        self.assertIn("500 units available.", thinking)
        self.assertEqual(final_answer, "Widget A has 500 units available.")

    def test_build_assistant_parts_keeps_unstructured_blob_as_final_answer(self):
        from types import SimpleNamespace

        blob = (
            "Okay, I'm on it.\n\n"
            "**1. Update Sales Forecast:**\n\n"
            "```python\nupdate_sales_forecast('Widget A', 'August 2026', 1500)\n```\n\n"
            "**3. Summary of Recommended Production Changes:**\n\n"
            "* **Recommendation:** Increase production by 800 units."
        )
        agent = SimpleNamespace(
            messages=[
                {"role": "user", "content": [{"text": "plan this"}]},
                {"role": "assistant", "content": [{"text": blob}]},
            ]
        )
        result = SimpleNamespace(message={"role": "assistant", "content": [{"text": blob}]})

        thinking, final_answer = build_assistant_parts(agent, 1, result, blob)

        self.assertEqual(thinking, "")
        self.assertEqual(final_answer, blob)


class ChatServiceTests(TestCase):
    def test_send_message_stores_user_and_assistant_messages(self):
        from chat.models import Conversation
        from chat.services import ChatService

        conversation = Conversation.objects.create()
        content = "What is the current inventory for Widget A?"
        mock_agent = MagicMock()
        mock_agent.messages = []
        mock_result = MagicMock()
        mock_result.message = {
            "role": "assistant",
            "content": [{"text": "Widget A has 500 units available."}],
        }
        mock_result.__str__ = MagicMock(
            return_value="Widget A has 500 units available.",
        )
        mock_agent.return_value = mock_result

        service = ChatService()
        with patch.object(service, "_get_agent", return_value=mock_agent) as mock_get_agent:
            user_message, assistant_message = service.send_message(conversation.id, content)

        mock_get_agent.assert_called_once_with(conversation.id)
        mock_agent.assert_called_once()
        self.assertEqual(user_message.content, content)
        self.assertEqual(assistant_message.content, "Widget A has 500 units available.")
        self.assertEqual(assistant_message.thinking, "")
