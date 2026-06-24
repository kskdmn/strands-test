# Sales Plan Inventory Production Advice Design

## Context

The chat app already has a main orchestrator plus specialist subagents for sales, production schedule, inventory, and planning. The planning path currently owns forecast updates and production recommendations through `update_sales_forecast` and `suggest_production_plan`.

The user wants to tell the chat agent that a sales plan will change. The agent should check how the change affects inventory, then suggest a new production order or production change. The recommendation is advisory only: it must not create or update production orders in the database.

## Goals

- Route sales-plan changes to the planning subagent.
- Keep the existing planning subagent instead of deleting it.
- Use structured backend tools for inventory and production schedule data.
- Suggest production actions after comparing updated demand against inventory and incoming production.
- Return concise, human-readable recommendations with enough numeric detail to justify the suggestion.

## Non-Goals

- Do not persist new production orders.
- Do not update existing production orders.
- Do not make the planning subagent depend on calling other subagents for numeric planning data.
- Do not change the chat UI unless implementation reveals a missing state or error display.

## Architecture

The main orchestrator continues to route combined forecast-change and production-planning requests to `planning_assistant`.

`planning_assistant` remains the specialist for this workflow. It may use direct structured tools such as `update_sales_forecast`, `suggest_production_plan`, `fetch_inventory_status`, and `fetch_factory_status`. It should not call `inventory_assistant` or `production_schedule_assistant` for the core calculation because those subagents return narrative text, which is less reliable for numeric planning decisions.

The deterministic planning calculation should live in `suggest_production_plan`. The subagent can interpret the user's natural-language request, save any explicit forecast updates, invoke the planning tool, and summarize the structured output.

## Workflow

1. User says a sales plan or forecast will change.
2. Orchestrator sends the full request to `planning_assistant`.
3. Planning assistant calls `update_sales_forecast` for each explicit product and month in the request.
4. Planning assistant calls `suggest_production_plan` for the affected product or products.
5. `suggest_production_plan` compares forecast demand with available inventory and incoming production.
6. Planning assistant summarizes the result as advisory production guidance.

## Recommendation Actions

`suggest_production_plan` should return one recommendation per product:

- `new_production_order`: demand exceeds projected supply and there is no incoming production for the planning window.
- `increase_production`: demand exceeds projected supply and incoming production already exists.
- `reduce_or_delay_production`: projected supply exceeds forecast demand.
- `maintain_current_plan`: projected supply matches forecast demand closely enough that no change is needed.

Each recommendation should include product, SKU, forecast months, forecast demand, available inventory, incoming production, projected supply, supply gap, recommended action, recommendation text, and suggested production line when extra production is needed.

## Error Handling

- If the product cannot be found, return a clear product-not-found error from the tool.
- If the month is invalid, return a clear month-format error.
- If the request does not include enough detail to update a forecast, the planning assistant should ask for the missing product, month, or quantity.
- If no forecasts exist for the requested period, the assistant should explain that a forecast must be saved before a production recommendation can be calculated.

## Testing

Add focused tests around `suggest_production_plan` and planning routing:

- Forecast increase with no incoming production returns `new_production_order`.
- Forecast increase with existing incoming production returns `increase_production`.
- Excess projected supply returns `reduce_or_delay_production`.
- Balanced supply returns `maintain_current_plan`.
- The orchestrator prompt continues routing sales-plan changes to `planning_assistant`.

These tests should cover the advisory-only behavior by asserting that production order records are not created or modified by recommendation generation.
