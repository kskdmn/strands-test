# strands-test

A Django app with a chat UI and JSON HTTP API, backed by a [Strands Agents](https://strandsagents.com/) agent on Amazon Bedrock using `google.gemma-3-4b-it`.

The browser UI at `/` sends messages to the API, which stores conversation history in SQLite and returns assistant replies. No login or other pages are included.

The main agent routes specialized questions to two subagents:

- **Sales forecast agent** — uses `fetch_past_sales_data` to read historical sales from SQLite
- **Production schedule agent** — uses `fetch_factory_status` to read factory lines and production orders

## Setup

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_dummy_data
```

Set AWS credentials for Bedrock (for example `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).

## Run

```bash
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/

## API

- `POST /api/conversations/` — create a conversation
- `GET /api/conversations/<uuid>/messages/` — list messages
- `POST /api/conversations/<uuid>/messages/send/` — send a message and get a reply
