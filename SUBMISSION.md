# StackPilot AI — Devpost Submission Kit

## Required fields

- **Category:** Developer tools
- **Repository URL:** `https://github.com/redcappp/stackpilot-ai`
- **Live demo URL (optional):** `REPLACE_WITH_DEPLOYED_URL`
- **Codex feedback session ID:** `REPLACE_WITH_REAL_/feedback_SESSION_ID`

Do not submit placeholders. Get the session ID from the Codex `/feedback` action for this build session, then paste it into the Devpost form.

## Short description

StackPilot AI converts a spreadsheet into an inspectable application blueprint and a downloadable, runnable FastAPI + React + PostgreSQL project. It identifies field types, likely keys and relationships, flags personal data, offers an AI architecture review, and generates protected CRUD APIs, documentation, Docker, CI, and an admin dashboard.

## What makes it different

Most code generators produce isolated snippets. StackPilot gives a judge a complete loop: upload real business data, inspect the inferred blueprint, review the architecture, download a repository, run one Docker command, then use the generated dashboard and Swagger docs. Its AI is focused on higher-value design judgement while deterministic profiling keeps every inference visible and reliable.

## GPT-5.6 and Codex usage

GPT-5.6 is used for the optional architecture-review step: the model sees only the compact inferred schema and returns structured recommendations about relationships, validation, security, and API ergonomics. The app falls back to a clearly marked local review so judges can test it without a key.

Codex accelerated the implementation from idea to tested product: generator architecture, FastAPI endpoints, React interaction design, deployment artifacts, automated verification, and this submission package. The key design decision was to keep the generated application readable and testable instead of hiding it behind a black-box agent.

## Three-minute video script

**0:00–0:20 — Problem.** “Teams often begin with a spreadsheet, then lose days translating it into a database, APIs, dashboard, authentication, and deployment.”

**0:20–0:55 — Upload.** Upload the sample CSV or a multi-sheet library workbook. Point out detected types and the blueprint.

**0:55–1:25 — AI review.** Click **AI architecture review**. Explain that GPT-5.6 gives focused design recommendations when configured; the offline fallback makes the tool reproducible.

**1:25–2:05 — Export.** Click **Download project**, unzip, and briefly show the generated backend, React dashboard, Docker Compose, test, CI, and `docs/schema.json`.

**2:05–2:35 — Run.** Run `docker compose up --build`, log in to the generated dashboard with the demo account, and open `/docs` to prove the generated CRUD API exists.

**2:35–3:00 — Technical story.** Explain where Codex accelerated the build and why StackPilot separates deterministic extraction from GPT-5.6 architecture judgement. Close with: “From spreadsheet to an auditable app baseline in minutes.”

## Publish the repository

1. Create a public GitHub repository named `stackpilot-ai` (or make a private one and add `testing@devpost.com` and `build-week-event@openai.com`).
2. Push this folder, add the final GitHub URL above and in the README clone command.
3. Confirm that `README.md`, `LICENSE`, `samples/`, and the local run instructions are visible without credentials.
4. Record the demo video as **public** on YouTube and add its URL to Devpost.

## Judge test account

The generated demo app includes a test account: `admin` / `stackpilot-demo`. This is intentionally demo-only; the generated README calls out required secret and password changes before deployment.
