from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
OUTPUT = ROOT.parent / "generated"
OUTPUT.mkdir(exist_ok=True)
app = FastAPI(title="StackPilot AI", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def clean_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower()
    if not name:
        return "record"
    if name[0].isdigit():
        return f"field_{name}"
    return name


def title_name(value: str) -> str:
    return clean_name(value).replace("_", " ").title()


def singular(value: str) -> str:
    value = clean_name(value)
    return value[:-3] + "y" if value.endswith("ies") else value[:-1] if value.endswith("s") else value


def infer_type(name: str, series: pd.Series) -> str:
    normalized = clean_name(name)
    # Identifiers are labels, even when a spreadsheet happens to store them as numbers.
    if any(x in normalized for x in ("isbn", "zip", "postal", "sku", "code")):
        return "string"
    if normalized.endswith("_id") or normalized == "id":
        return "integer"
    if "email" in normalized:
        return "email"
    if any(x in normalized for x in ("phone", "mobile", "fax")):
        return "phone"
    if any(x in normalized for x in ("date", "time", "created", "updated")):
        return "datetime"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "decimal"
    return "string"


def analyze_frame(df: pd.DataFrame, sheet: str) -> dict[str, Any]:
    df = df.dropna(axis=1, how="all").head(1000)
    columns = []
    for index, raw in enumerate(df.columns):
        name = clean_name(raw)
        values = df[raw].dropna()
        id_like = name == "id" or name.endswith("_id")
        columns.append({
            "name": name,
            "label": title_name(raw),
            "type": infer_type(str(raw), df[raw]),
            "required": bool(len(df) and len(values) == len(df)),
            "primary": name == "id" or (index == 0 and id_like),
            "sample": "" if values.empty else str(values.iloc[0])[:60],
            "null_count": int(df[raw].isna().sum()),
            "unique_count": int(values.nunique()),
        })
    # Ensure every generated SQLAlchemy model has a reliable primary key.
    if columns and not any(c["primary"] for c in columns):
        columns.insert(0, {"name": "id", "label": "Id", "type": "integer", "required": True, "primary": True, "sample": "generated"})
    return {"name": singular(sheet), "label": title_name(singular(sheet)), "source_sheet": sheet, "rows": len(df), "columns": columns}


def infer_relations(entities: list[dict[str, Any]]) -> list[dict[str, str]]:
    names = {entity["name"]: entity for entity in entities}
    relations = []
    for entity in entities:
        for column in entity["columns"]:
            if not column["name"].endswith("_id") or column["name"] == "id":
                continue
            candidate = singular(column["name"][:-3])
            if candidate in names and candidate != entity["name"]:
                relations.append({"from": entity["name"], "field": column["name"], "target": candidate, "kind": "many-to-one"})
    return relations


def parse_upload(upload: UploadFile, content: bytes) -> dict[str, Any]:
    filename = upload.filename or "upload.csv"
    try:
        if filename.lower().endswith(".csv"):
            entities = [analyze_frame(pd.read_csv(io.BytesIO(content)), "Records")]
        elif filename.lower().endswith((".xlsx", ".xls")):
            book = pd.ExcelFile(io.BytesIO(content))
            entities = [analyze_frame(pd.read_excel(book, sheet_name=sheet), sheet) for sheet in book.sheet_names]
        else:
            raise HTTPException(400, "Please upload a .csv, .xlsx, or .xls file.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"We couldn't read this file: {exc}") from exc
    entities = [entity for entity in entities if entity["columns"]]
    if not entities:
        raise HTTPException(400, "No usable columns were found in this spreadsheet.")
    relations = infer_relations(entities)
    pii_fields = [f"{entity['label']}.{column['label']}" for entity in entities for column in entity["columns"] if column["type"] in {"email", "phone"}]
    return {
        "project": f"{title_name(filename.rsplit('.', 1)[0])} Workspace",
        "source": filename,
        "rows": sum(entity["rows"] for entity in entities),
        "entity": entities[0],  # Compatibility with the visual blueprint.
        "entities": entities,
        "relations": relations,
        "sheets": [entity["source_sheet"] for entity in entities],
        "quality": {"entities": len(entities), "relationships": len(relations), "pii_fields": pii_fields, "warnings": ["Personal data detected: add retention and access policies before production." for _ in pii_fields[:1]]},
        "generated_at": datetime.now().isoformat(),
    }


def heuristic_review(schema: dict[str, Any]) -> dict[str, Any]:
    entities = schema.get("entities") or [schema["entity"]]
    relations = schema.get("relations", [])
    pii = schema.get("quality", {}).get("pii_fields", [])
    missing_keys = [entity["label"] for entity in entities if not any(column.get("primary") for column in entity["columns"])]
    return {
        "mode": "local-architecture-review",
        "summary": f"Prepared {len(entities)} API resource{'s' if len(entities) != 1 else ''}, {len(relations)} inferred relationship{'s' if len(relations) != 1 else ''}, and an admin workspace.",
        "decisions": [
            "Generated REST resources use a consistent plural-free route per data model and pagination defaults capped at 100 records.",
            "JWT protects every data mutation and listing route; health and login remain public for deployment checks.",
            "Docker defaults to PostgreSQL while local development uses SQLite to remove setup friction.",
        ],
        "risks": ([f"Protect or minimize PII fields: {', '.join(pii)}."] if pii else []) + ([f"Confirm primary keys for: {', '.join(missing_keys)}."] if missing_keys else []),
        "next_steps": ["Review inferred relationships before deployment.", "Set a unique SECRET_KEY and DEMO_ADMIN_PASSWORD.", "Add business-specific validation and role rules before production."],
    }


def ai_review(schema: dict[str, Any]) -> dict[str, Any]:
    """Use GPT for architecture advice when configured; retain a deterministic offline demo."""
    fallback = heuristic_review(schema)
    if not os.getenv("OPENAI_API_KEY"):
        return fallback
    try:
        from openai import OpenAI
        prompt = """You are StackPilot's senior application architect. Review this inferred spreadsheet schema. Return strict JSON with keys summary (string), decisions (array of 3 concise strings), risks (array), and next_steps (array of 3 concise strings). Do not invent data fields. Focus on database relationships, validation, security, and generated API ergonomics.\n\nSCHEMA:\n""" + json.dumps(schema, default=str)
        response = OpenAI().responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5.6"), input=prompt)
        content = response.output_text.strip().removeprefix("```json").removesuffix("```").strip()
        reviewed = json.loads(content)
        if not all(key in reviewed for key in ("summary", "decisions", "risks", "next_steps")):
            raise ValueError("Model response did not match review contract")
        return {"mode": "gpt-5.6-architecture-review", **reviewed}
    except Exception:
        # A project can still be demonstrated offline if an API key is absent or a request fails.
        return fallback


TYPE_MAP = {"integer": "Integer", "decimal": "Float", "boolean": "Boolean", "datetime": "DateTime", "email": "String", "phone": "String", "string": "String"}
PYTHON_MAP = {"integer": "int", "decimal": "float", "boolean": "bool", "datetime": "datetime", "email": "str", "phone": "str", "string": "str"}


def class_name(entity: dict[str, Any]) -> str:
    return "".join(part.title() for part in entity["name"].split("_"))


def model_code(entities: list[dict[str, Any]]) -> str:
    blocks = ["from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String\nfrom database import Base\n"]
    for entity in entities:
        fields = []
        for col in entity["columns"]:
            arguments = "primary_key=True, index=True" if col["primary"] else f"nullable={str(not col['required']).lower()}"
            fields.append(f"    {col['name']} = Column({TYPE_MAP.get(col['type'], 'String')}, {arguments})")
        blocks.append(f"\n\nclass {class_name(entity)}(Base):\n    __tablename__ = '{entity['name']}'\n" + "\n".join(fields))
    return "".join(blocks) + "\n"


def endpoint_code(entity: dict[str, Any]) -> str:
    cls, resource = class_name(entity), entity["name"]
    fields = [c for c in entity["columns"] if not c["primary"]]
    annotations = "\n".join(f"    {c['name']}: {PYTHON_MAP[c['type']]} | None = None" for c in fields) or "    name: str | None = None"
    return f'''\n\nclass {cls}Payload(BaseModel):\n{annotations}\n\n\n@app.get("/api/{resource}", dependencies=[Depends(current_user)])\ndef list_{resource}(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):\n    return [serialize(item) for item in db.query(models.{cls}).offset(skip).limit(min(limit, 100)).all()]\n\n\n@app.post("/api/{resource}", status_code=201, dependencies=[Depends(current_user)])\ndef create_{resource}(payload: {cls}Payload, db: Session = Depends(get_db)):\n    item = models.{cls}(**payload.model_dump(exclude_none=True))\n    db.add(item); db.commit(); db.refresh(item)\n    return serialize(item)\n\n\n@app.patch("/api/{resource}/{{item_id}}", dependencies=[Depends(current_user)])\ndef update_{resource}(item_id: int, payload: {cls}Payload, db: Session = Depends(get_db)):\n    item = db.get(models.{cls}, item_id)\n    if not item: raise HTTPException(404, "Record not found")\n    for key, value in payload.model_dump(exclude_none=True).items(): setattr(item, key, value)\n    db.commit(); db.refresh(item)\n    return serialize(item)\n\n\n@app.delete("/api/{resource}/{{item_id}}", status_code=204, dependencies=[Depends(current_user)])\ndef delete_{resource}(item_id: int, db: Session = Depends(get_db)):\n    item = db.get(models.{cls}, item_id)\n    if not item: raise HTTPException(404, "Record not found")\n    db.delete(item); db.commit()\n'''


def generated_backend(schema: dict[str, Any]) -> dict[str, str]:
    entities = schema.get("entities") or [schema["entity"]]
    app_code = '''from datetime import datetime, timedelta, timezone\nimport os\nfrom typing import Generator\n\nfrom fastapi import Depends, FastAPI, HTTPException\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm\nfrom jose import JWTError, jwt\nfrom pydantic import BaseModel\nfrom sqlalchemy.inspection import inspect\nfrom sqlalchemy.orm import Session\n\nimport models\nfrom database import Base, SessionLocal, engine\n\nBase.metadata.create_all(bind=engine)\napp = FastAPI(title="''' + schema["project"] + '''", version="1.0.0")\napp.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])\noauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")\nSECRET_KEY = os.getenv("SECRET_KEY", "change-this-before-production")\nALGORITHM = "HS256"\nDEMO_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "stackpilot-demo")\n\ndef get_db() -> Generator[Session, None, None]:\n    db = SessionLocal()\n    try: yield db\n    finally: db.close()\n\ndef current_user(token: str = Depends(oauth2_scheme)) -> str:\n    try: return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]\n    except (JWTError, KeyError): raise HTTPException(401, "Invalid authentication token")\n\ndef serialize(item):\n    return {column.key: getattr(item, column.key) for column in inspect(item).mapper.column_attrs}\n\n@app.get("/health")\ndef health(): return {"status": "ok"}\n\n@app.post("/auth/login")\ndef login(form: OAuth2PasswordRequestForm = Depends()):\n    if form.username != "admin" or form.password != DEMO_PASSWORD: raise HTTPException(401, "Incorrect username or password")\n    expires = datetime.now(timezone.utc) + timedelta(hours=8)\n    return {"access_token": jwt.encode({"sub": "admin", "exp": expires}, SECRET_KEY, algorithm=ALGORITHM), "token_type": "bearer"}\n'''
    app_code += "".join(endpoint_code(entity) for entity in entities)
    return {
        "backend/requirements.txt": "fastapi==0.115.6\nuvicorn[standard]==0.32.1\nsqlalchemy==2.0.36\npsycopg[binary]==3.2.3\npython-jose[cryptography]==3.3.0\npasslib[bcrypt]==1.7.4\npython-multipart==0.0.19\npytest==8.3.4\nhttpx==0.28.1\n",
        "backend/database.py": "import os\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import declarative_base, sessionmaker\n\nDATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./app.db')\nconnect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}\nengine = create_engine(DATABASE_URL, connect_args=connect_args)\nSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)\nBase = declarative_base()\n",
        "backend/models.py": model_code(entities),
        "backend/main.py": app_code,
        "backend/Dockerfile": "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n",
        "backend/.env.example": "SECRET_KEY=replace-with-a-long-random-value\nDEMO_ADMIN_PASSWORD=stackpilot-demo\nDATABASE_URL=postgresql+psycopg://stackpilot:stackpilot@db:5432/stackpilot\n",
        "backend/tests/test_health.py": "from fastapi.testclient import TestClient\nfrom main import app\n\ndef test_health():\n    assert TestClient(app).get('/health').json() == {'status': 'ok'}\n",
    }


def frontend_files(schema: dict[str, Any]) -> dict[str, str]:
    entities = schema.get("entities") or [schema["entity"]]
    config = [{"name": e["name"], "label": e["label"], "fields": [c for c in e["columns"] if not c["primary"]]} for e in entities]
    return {
        "frontend/package.json": json.dumps({"scripts": {"dev": "vite", "build": "vite build"}, "dependencies": {"@vitejs/plugin-react": "latest", "vite": "latest", "react": "latest", "react-dom": "latest"}, "devDependencies": {}}, indent=2),
        "frontend/index.html": "<div id=\"root\"></div><script type=\"module\" src=\"/src/main.jsx\"></script>",
        "frontend/src/main.jsx": "import React from 'react'; import { createRoot } from 'react-dom/client'; import './style.css'; import App from './App'; createRoot(document.getElementById('root')).render(<App />);\n",
        "frontend/src/schema.js": "export const entities = " + json.dumps(config) + ";\n",
        "frontend/src/App.jsx": '''import { useState } from 'react';\nimport { entities } from './schema';\nconst API = import.meta.env.VITE_API_URL || 'http://localhost:8000';\nexport default function App() {\n  const [active, setActive] = useState(entities[0]); const [token, setToken] = useState(localStorage.token || ''); const [records, setRecords] = useState([]); const [error, setError] = useState('');\n  async function signIn(e) { e.preventDefault(); const body = new URLSearchParams({username:'admin', password:e.target.password.value}); const r = await fetch(API + '/auth/login', {method:'POST', body}); const d = await r.json(); if (!r.ok) return setError(d.detail); localStorage.token=d.access_token; setToken(d.access_token); }\n  async function load(entity=active) { setActive(entity); const r = await fetch(API + '/api/' + entity.name, {headers:{Authorization:'Bearer '+token}}); setRecords(r.ok ? await r.json() : []); }\n  if (!token) return <main className=\"login\"><h1>''' + schema["project"] + '''</h1><p>Sign in to manage your generated data workspace.</p><form onSubmit={signIn}><input value=\"admin\" readOnly/><input name=\"password\" type=\"password\" placeholder=\"Password (stackpilot-demo)\"/><button>Sign in</button>{error && <small>{error}</small>}</form></main>;\n  return <main><header><div><span>STACKPILOT GENERATED</span><h1>''' + schema["project"] + '''</h1></div><button onClick={()=>{localStorage.removeItem('token');setToken('')}}>Sign out</button></header><nav>{entities.map(x=><button className={x.name===active.name?'active':''} onClick={()=>load(x)}>{x.label}</button>)}</nav><section><div className=\"toolbar\"><h2>{active.label}</h2><button onClick={()=>load()}>Refresh records</button></div><p>{records.length ? records.length + ' records loaded' : 'Select Refresh records to fetch data.'}</p><table><thead><tr>{active.fields.map(f=><th>{f.label}</th>)}</tr></thead><tbody>{records.map(row=><tr>{active.fields.map(f=><td>{String(row[f.name] ?? '')}</td>)}</tr>)}</tbody></table></section></main>;\n}\n''',
        "frontend/src/style.css": "*{box-sizing:border-box}body{margin:0;background:#f6f7f3;color:#15271e;font:15px system-ui}main{max-width:1100px;margin:auto;padding:42px 28px}header,.toolbar{display:flex;justify-content:space-between;align-items:center}header span{font-size:11px;letter-spacing:1px;color:#598060}h1{margin:7px 0;font-size:34px}nav{display:flex;gap:8px;border-bottom:1px solid #d8ded5;padding:20px 0}button{border:0;border-radius:6px;padding:10px 14px;background:#244b38;color:white;font-weight:600;cursor:pointer}nav button{background:transparent;color:#536258}.active{background:#e2f0d6!important;color:#244b38!important}section{padding-top:30px}table{width:100%;border-collapse:collapse;background:#fff}th,td{text-align:left;padding:12px;border-bottom:1px solid #e5e9e2}th{font-size:12px;color:#68756b}.login{max-width:440px;margin-top:10vh;background:white;border:1px solid #dce3d9;border-radius:10px}.login form{display:grid;gap:12px;margin-top:25px}.login input{padding:12px;border:1px solid #ccd5ca;border-radius:6px}.login small{color:#b13b3b}\n",
        "frontend/.env.example": "VITE_API_URL=http://localhost:8000\n",
    }


def export_files(schema: dict[str, Any]) -> dict[str, str]:
    entities = schema.get("entities") or [schema["entity"]]
    resources = ", ".join(entity["label"] for entity in entities)
    files = generated_backend(schema) | frontend_files(schema)
    files.update({
        "README.md": f"# {schema['project']}\n\nA full-stack application generated by StackPilot AI from `{schema['source']}`.\n\n## Included\n\n- FastAPI CRUD API for {resources}\n- JWT-protected admin endpoints (demo: `admin` / `stackpilot-demo`)\n- PostgreSQL Docker Compose environment and React/Vite dashboard\n- OpenAPI documentation at `http://localhost:8000/docs`\n\n## Run with Docker\n\n```bash\ndocker compose up --build\n```\n\nOpen the dashboard at `http://localhost:5173`; API docs are at `http://localhost:8000/docs`. Before a production deployment, set a unique `SECRET_KEY` and admin password.\n\n## Run locally\n\n```bash\ncd backend && pip install -r requirements.txt && uvicorn main:app --reload\ncd ../frontend && npm install && npm run dev\n```\n\n## AI generation notes\n\nStackPilot inferred field types, primary keys, and relationships from spreadsheet headers. Review the schema in `docs/schema.json` before using generated code in production.\n",
        "docker-compose.yml": "services:\n  db:\n    image: postgres:16-alpine\n    environment:\n      POSTGRES_DB: stackpilot\n      POSTGRES_USER: stackpilot\n      POSTGRES_PASSWORD: stackpilot\n    volumes: [postgres_data:/var/lib/postgresql/data]\n  api:\n    build: ./backend\n    environment:\n      DATABASE_URL: postgresql+psycopg://stackpilot:stackpilot@db:5432/stackpilot\n      SECRET_KEY: change-this-before-production\n    ports: ['8000:8000']\n    depends_on: [db]\n  web:\n    image: node:22-alpine\n    working_dir: /app\n    volumes: ['./frontend:/app']\n    command: sh -c 'npm install && npm run dev -- --host 0.0.0.0'\n    ports: ['5173:5173']\n    depends_on: [api]\nvolumes:\n  postgres_data:\n",
        ".github/workflows/ci.yml": "name: Verify generated API\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    defaults: {run: {working-directory: backend}}\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with: {python-version: '3.12'}\n      - run: pip install -r requirements.txt\n      - run: pytest\n",
        "docs/schema.json": json.dumps(schema, indent=2),
        ".gitignore": "backend/app.db\nbackend/.env\nfrontend/node_modules\n",
    })
    return files


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if (file.size or 0) > 25 * 1024 * 1024:
        raise HTTPException(413, "Please upload a file smaller than 25 MB.")
    return parse_upload(file, await file.read())


@app.post("/api/review")
async def review(schema: dict[str, Any]):
    if not schema.get("entity") and not schema.get("entities"):
        raise HTTPException(400, "A schema is required before reviewing.")
    return ai_review(schema)


@app.post("/api/export")
async def export(schema: dict[str, Any]):
    if not schema.get("entity") and not schema.get("entities"):
        raise HTTPException(400, "A schema is required before exporting.")
    slug = clean_name(schema.get("project", "stackpilot_project"))
    archive = OUTPUT / f"{slug}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path, body in export_files(schema).items():
            zipped.writestr(f"{slug}/{path}", body)
    return {"download_url": f"/api/download/{archive.name}", "name": archive.name}


@app.get("/api/download/{filename}")
def download(filename: str):
    path = OUTPUT / Path(filename).name
    if not path.exists():
        raise HTTPException(404, "Export expired")
    return FileResponse(path, filename=path.name, media_type="application/zip")
