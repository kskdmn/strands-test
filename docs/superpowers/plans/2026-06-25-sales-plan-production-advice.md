# Sales Plan Production Advice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make sales-plan changes produce advisory-only production recommendations that distinguish new production orders, production increases, reductions, and no-change cases.

**Architecture:** Keep the existing `planning_assistant` and route sales-plan changes to it. Put numeric recommendation decisions in `chat.tools.planning.suggest_production_plan` using structured database-backed tools and models, while the planning subagent handles natural-language interpretation and summarization.

**Tech Stack:** Django, SQLite-backed Django models, Strands Agents tools, Python `unittest`-style Django `TestCase`.

---

## Working Tree Note

The current workspace already has uncommitted changes in app files including `chat/tests.py`, `chat/tools/planning.py`, `chat/agents/subagents.py`, and related monthly-data files. During execution, inspect diffs before staging and avoid committing unrelated existing changes. If clean, task commits can stage the listed files directly. If unrelated local edits remain in the same files, skip the task commit and report that commits were unsafe.

## File Structure

- Modify `chat/tests.py`: add focused planning recommendation tests and a planning subagent contract test.
- Modify `chat/tools/planning.py`: refine `suggest_production_plan` action selection for advisory recommendations.
- Modify `chat/agents/subagents.py`: tighten the planning subagent prompt so it is advisory-only and relies on direct structured tools.
- Modify `chat/prompts.py`: make orchestrator routing explicitly include sales-plan changes and advisory production suggestions.

### Task 1: Add Recommendation Action Tests

**Files:**
- Modify: `chat/tests.py`
- Test: `chat/tests.py`

- [ ] **Step 1: Add planning test helper methods**

In `chat/tests.py`, inside `class PlanningTests(TestCase):`, insert these helper methods before `test_update_sales_forecast_creates_record`:

```python
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
```

- [ ] **Step 2: Add failing action-selection tests**

Still in `class PlanningTests(TestCase):`, replace `test_suggest_production_plan_flags_supply_gap` with these four tests:

```python
    def test_suggest_production_plan_recommends_new_order_without_incoming_production(self):
        import json

        from chat.monthly_data import current_month_start
        from chat.models import ProductionMonthlyData, SalesMonthlyData

        product = self._create_planning_product(on_hand=100)
        SalesMonthlyData.objects.create(
            product=product,
            month=current_month_start(),
            plan_units=500,
        )

        payload = json.loads(suggest_production_plan(product_name="Widget A"))

        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["forecast_demand"], 500)
        self.assertEqual(recommendation["available_inventory"], 100)
        self.assertEqual(recommendation["incoming_production"], 0)
        self.assertEqual(recommendation["supply_gap"], 400)
        self.assertEqual(recommendation["recommended_action"], "new_production_order")
        self.assertIn("new production order", recommendation["recommendation"])
        self.assertEqual(recommendation["suggested_line"], "Assembly Line 1")
        self.assertEqual(ProductionMonthlyData.objects.count(), 0)

    def test_suggest_production_plan_recommends_increase_when_incoming_production_exists(self):
        import json

        from chat.monthly_data import current_month_start
        from chat.models import ProductionMonthlyData, SalesMonthlyData

        product = self._create_planning_product(on_hand=100)
        SalesMonthlyData.objects.create(
            product=product,
            month=current_month_start(),
            plan_units=500,
        )
        ProductionMonthlyData.objects.create(
            product=product,
            month=current_month_start(),
            plan_quantity=100,
        )

        payload = json.loads(suggest_production_plan(product_name="Widget A"))

        recommendation = payload["recommendations"][0]
        self.assertEqual(recommendation["incoming_production"], 100)
        self.assertEqual(recommendation["supply_gap"], 300)
        self.assertEqual(recommendation["recommended_action"], "increase_production")
        self.assertIn("Increase planned production", recommendation["recommendation"])
        self.assertEqual(ProductionMonthlyData.objects.count(), 1)

    def test_suggest_production_plan_recommends_reduction_for_excess_supply(self):
        import json

        from chat.monthly_data import current_month_start
        from chat.models import SalesMonthlyData

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

    def test_suggest_production_plan_maintains_balanced_plan(self):
        import json

        from chat.monthly_data import current_month_start
        from chat.models import SalesMonthlyData

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
```

- [ ] **Step 3: Run tests to verify the new-order test fails**

Run:

```bash
uv run python manage.py test chat.tests.PlanningTests
```

Expected: FAIL. The failure should be in `test_suggest_production_plan_recommends_new_order_without_incoming_production`, with actual action `"increase_production"` instead of expected `"new_production_order"`.

- [ ] **Step 4: Commit or report skipped commit**

If only this task's hunks are staged:

```bash
git add chat/tests.py
git commit -m "test: cover advisory production recommendation actions"
```

If `chat/tests.py` contains unrelated unstaged edits from before execution, do not commit. Report: `Skipped Task 1 commit because chat/tests.py already contained unrelated local changes.`

### Task 2: Implement Advisory Action Selection

**Files:**
- Modify: `chat/tools/planning.py`
- Test: `chat/tests.py`

- [ ] **Step 1: Update positive-gap action logic**

In `chat/tools/planning.py`, inside `suggest_production_plan`, replace the current `if gap > 0:` block with:

```python
        if gap > 0:
            if incoming > 0:
                action = "increase_production"
                detail = f"Increase planned production by {gap} units to cover forecast demand."
            else:
                action = "new_production_order"
                detail = f"Suggest a new production order for {gap} units to cover forecast demand."
        elif gap < 0:
            action = "reduce_or_delay_production"
            detail = (
                f"Supply exceeds forecast by {abs(gap)} units. "
                "Consider delaying or reducing planned production."
            )
        else:
            action = "maintain_current_plan"
            detail = "Current inventory and incoming production match forecast demand."
```

Keep this existing recommendation field unchanged so both positive-gap actions can suggest a line:

```python
                "suggested_line": line.name if line and gap > 0 else None,
```

- [ ] **Step 2: Run planning tests to verify they pass**

Run:

```bash
uv run python manage.py test chat.tests.PlanningTests
```

Expected: PASS for all `PlanningTests`.

- [ ] **Step 3: Commit or report skipped commit**

If only this task's hunks are staged:

```bash
git add chat/tools/planning.py chat/tests.py
git commit -m "feat: distinguish advisory production recommendation actions"
```

If either file contains unrelated pre-existing edits, do not commit. Report: `Skipped Task 2 commit because planning files already contained unrelated local changes.`

### Task 3: Tighten Planning Subagent Contract

**Files:**
- Modify: `chat/tests.py`
- Modify: `chat/agents/subagents.py`
- Test: `chat/tests.py`

- [ ] **Step 1: Add failing planning subagent contract test**

In `chat/tests.py`, after `class PlanningTests(TestCase):` and before `class ToolFallbackTests(TestCase):`, add:

```python
class PlanningAssistantTests(TestCase):
    def test_planning_assistant_uses_direct_tools_and_advisory_prompt(self):
        from chat.agents import subagents

        with patch("chat.agents.subagents.Agent") as mock_agent:
            mock_agent.return_value.return_value = "done"

            result = subagents.planning_assistant(query="Widget A August sales plan becomes 1500.")

        self.assertEqual(result, "done")
        kwargs = mock_agent.call_args.kwargs
        self.assertEqual(kwargs["name"], "planning")
        prompt = kwargs["system_prompt"]
        self.assertIn("Recommendations are advisory only", prompt)
        self.assertIn("Do not create or update production orders", prompt)
        self.assertIn("direct structured tools", prompt)
        self.assertIn(subagents.update_sales_forecast, kwargs["tools"])
        self.assertIn(subagents.suggest_production_plan, kwargs["tools"])
        self.assertIn(subagents.fetch_inventory_status, kwargs["tools"])
        self.assertIn(subagents.fetch_factory_status, kwargs["tools"])
        self.assertNotIn(subagents.inventory_assistant, kwargs["tools"])
        self.assertNotIn(subagents.production_schedule_assistant, kwargs["tools"])
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```bash
uv run python manage.py test chat.tests.PlanningAssistantTests
```

Expected: FAIL because the current prompt does not include advisory-only and direct-structured-tool instructions.

- [ ] **Step 3: Update planning subagent prompt**

In `chat/agents/subagents.py`, in `planning_assistant`, replace the `system_prompt` string with:

```python
        system_prompt=(
            "You are a demand and production planning specialist. "
            "When the user provides new forecast or sales-plan numbers, call update_sales_forecast "
            "for each product and month they mention. "
            "After forecasts are saved, call suggest_production_plan to compare demand "
            "against inventory and incoming production. "
            "Use direct structured tools for inventory and factory data when extra detail is needed. "
            "Recommendations are advisory only. Do not create or update production orders. "
            "Summarize the recommended production changes clearly, including quantities, "
            "whether the action is a new order, an increase, a reduction or delay, or no change, "
            "and which line to use when a gap exists."
        ),
```

- [ ] **Step 4: Run the contract test to verify it passes**

Run:

```bash
uv run python manage.py test chat.tests.PlanningAssistantTests
```

Expected: PASS.

- [ ] **Step 5: Commit or report skipped commit**

If only this task's hunks are staged:

```bash
git add chat/tests.py chat/agents/subagents.py
git commit -m "feat: clarify advisory planning subagent contract"
```

If either file contains unrelated pre-existing edits, do not commit. Report: `Skipped Task 3 commit because planning assistant files already contained unrelated local changes.`

### Task 4: Clarify Orchestrator Routing Prompt

**Files:**
- Modify: `chat/tests.py`
- Modify: `chat/prompts.py`
- Test: `chat/tests.py`

- [ ] **Step 1: Add failing routing prompt assertions**

In `chat/tests.py`, in `PlanningTests.test_orchestrator_prompt_mentions_planning_assistant`, extend the assertions to:

```python
    def test_orchestrator_prompt_mentions_planning_assistant(self):
        prompt = build_orchestrator_system_prompt()
        self.assertIn("planning_assistant", prompt)
        self.assertIn("sales plan", prompt)
        self.assertIn("suggest production", prompt)
        self.assertIn("advisory", prompt)
        self.assertIn("Do NOT use production_schedule_assistant", prompt)
```

- [ ] **Step 2: Run the routing prompt test to verify it fails**

Run:

```bash
uv run python manage.py test chat.tests.PlanningTests.test_orchestrator_prompt_mentions_planning_assistant
```

Expected: FAIL because the current orchestrator prompt does not explicitly mention sales-plan wording and advisory suggestions.

- [ ] **Step 3: Update the routing prompt**

In `chat/prompts.py`, replace the current `### Forecast updates and production planning` bullet group with:

```python
### Forecast updates and production planning
- User says a sales plan or forecast will change, asks to update/change/set a sales forecast,
  OR asks for an advisory production plan to meet forecast demand
  -> call planning_assistant with the user's full question as query
- For a combined request (update forecast + suggest production plan), call planning_assistant once
  with the full user message - do NOT split across production_schedule_assistant
- planning_assistant only suggests production changes; recommendations are advisory and must not
  create or update production orders
- Do NOT use production_schedule_assistant to create or revise plans from forecast changes;
  it only reads the current schedule
```

- [ ] **Step 4: Run the routing prompt test to verify it passes**

Run:

```bash
uv run python manage.py test chat.tests.PlanningTests.test_orchestrator_prompt_mentions_planning_assistant
```

Expected: PASS.

- [ ] **Step 5: Commit or report skipped commit**

If only this task's hunks are staged:

```bash
git add chat/tests.py chat/prompts.py
git commit -m "feat: route sales plan changes to advisory planning"
```

If either file contains unrelated pre-existing edits, do not commit. Report: `Skipped Task 4 commit because routing prompt files already contained unrelated local changes.`

### Task 5: Final Verification

**Files:**
- Test: `chat/tests.py`

- [ ] **Step 1: Run the full chat test suite**

Run:

```bash
uv run python manage.py test chat
```

Expected: PASS.

- [ ] **Step 2: Inspect final diff**

Run:

```bash
git diff -- chat/tests.py chat/tools/planning.py chat/agents/subagents.py chat/prompts.py
```

Expected: Diff only shows advisory planning tests, refined recommendation action logic, and prompt clarifications.

- [ ] **Step 3: Report verification and commit status**

Report the exact test command result, and list any commits made or skipped because of pre-existing local changes.
