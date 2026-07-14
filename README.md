# StackPilot AI

> Upload a spreadsheet. Download a working, documented, containerized full-stack app.

StackPilot AI is an AI-assisted application generator built for teams that still start with spreadsheets. It reads CSV/XLSX files (including multi-sheet workbooks), profiles data, infers a relational blueprint, gives the user an architecture review, and exports a runnable FastAPI + React + PostgreSQL project.

![Track](https://img.shields.io/badge/OpenAI%20Build%20Week-Developer%20Tools-295441)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![License](https://img.shields.io/badge/license-MIT-c7f36b)

## Why this is useful

The usual spreadsheet-to-software handoff loses days to database design, field interpretation, API scaffolding, auth plumbing, containers, and documentation. StackPilot turns that handoff into an inspectable blueprint and a useful starting repository. It does **not** claim that generated code is ready to deploy unreviewed: privacy, security, validation, and business rules stay visible for the team to review.

## The wow demo

1. Open StackPilot and upload [`samples/library_records.csv`](samples/library_records.csv).
2. Click **AI architecture review**. It identifies the data model, protected API surface, and production risks.
3. Click **Download project**.
4. Unzip the export and run `docker compose up --build`.
5. Open the generated React dashboard at `http://localhost:5173`, log in with `admin` / `stackpilot-demo`, then show the generated Swagger UI at `http://localhost:8000/docs`.

For the most impressive version, upload a workbook with `Customers`, `Orders`, and `Order Items` sheets. Columns such as `customer_id` are inferred as likely relationships.

## Features

- Multi-sheet XLSX and CSV ingestion, type inference, null/uniqueness profiling, primary-key detection, and relationship inference
- Architecture review that uses GPT-5.6 when an API key is present, with a transparent offline fallback for reliable judging
- Generated FastAPI CRUD endpoints, SQLAlchemy persistence, JWT authentication, OpenAPI docs, pagination, update, and delete support
- Generated Vite/React admin workspace, PostgreSQL Docker Compose stack, tests, CI workflow, environment templates, and schema snapshot
- 25 MB upload safety limit and personal-data detection notice

## Quick start

### Prerequisites

- Python 3.11+
- Optional: Docker Desktop, for running an exported project
- Optional: an OpenAI API key, for live GPT-5.6 architecture reviews

```powershell
git clone https://github.com/redcappp/stackpilot-ai.git
cd stackpilot-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000`.

### Enable the model-powered review (optional)

```powershell
$env:OPENAI_API_KEY = "your_api_key"
$env:OPENAI_MODEL = "gpt-5.6"
uvicorn app.main:app --reload
```

Without the key, StackPilot remains fully testable and returns a clearly labelled local architecture review. With a key, it calls the OpenAI Responses API for a schema-aware design review. GPT-5.6 is a capable choice for complex coding and reasoning workflows according to the current [OpenAI model guide](https://developers.openai.com/api/docs/models).

## Deployment

This repository includes [`render.yaml`](render.yaml) for a one-click Render deployment. Create a Render Web Service from this GitHub repository; the service will run with the free plan, install from `requirements.txt`, and start StackPilot with Uvicorn. Set `OPENAI_API_KEY` in Render only if you want live GPT-5.6 reviews—judges can use the full offline flow without it.

## Run the generated application

After downloading and extracting an export:

```bash
docker compose up --build
```

| Surface | Address | Credentials |
| --- | --- | --- |
| Admin dashboard | `http://localhost:5173` | `admin` / `stackpilot-demo` |
| API docs | `http://localhost:8000/docs` | Use `/auth/login` to retrieve a bearer token |
| Health check | `http://localhost:8000/health` | None |

Before any non-demo deployment, replace `SECRET_KEY`, `DEMO_ADMIN_PASSWORD`, database credentials, and the default CORS policy. Review all inferred relationships and validation rules.

## How GPT-5.6 and Codex were used

This project deliberately distinguishes **deterministic generation** from **AI judgement**:

| Area | Decision |
| --- | --- |
| Schema extraction | Deterministic pandas profiling makes field types, nulls, and inferred keys inspectable and repeatable. |
| Architecture review | GPT-5.6 receives the compact inferred schema and returns JSON recommendations on relationships, validation, security, and API ergonomics. A strict JSON contract and offline fallback keep the demo dependable. |
| Code generation | Templates create a complete, readable baseline so generated output is auditable rather than opaque. |
| Codex acceleration | Codex accelerated the end-to-end build: product decomposition, FastAPI API design, UI implementation, generator templates, verification, README, Docker/CI configuration, and demo-story refinement. |

Key product choices were: start with the spreadsheet workflow businesses already have; show a blueprint before exporting; generate a runnable baseline rather than code fragments; and make the no-key judge path fully functional.

## Testing

```powershell
python -m py_compile app\main.py
```

The app’s verification flow covers CSV upload analysis, generated archive creation/download, and generated-backend compilation. Use the sample CSV above for a fast manual end-to-end test.

## Repository and submission checklist

See [SUBMISSION.md](SUBMISSION.md) for ready-to-paste Devpost copy, the video script, the repository publishing checklist, and the `/feedback` session-ID placeholder. The exact repository URL and session ID must be added by the submitting account; do not fabricate either value.

## License

Released under the [MIT License](LICENSE).
