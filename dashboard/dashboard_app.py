import asyncio
import os
import sqlite3
import subprocess
import sys
import threading
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import requests as req
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.jira_ticket_creator import creer_ticket_jira
from agents.deployment_agent import construire_url_pages, pages_deja_actives

try:
    from core.websocket_manager import manager, WebSocketLogHandler, router as ws_router
    _ws_available = True
except ImportError:
    _ws_available = False

from orchestrator import boucle_principale

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger("dashboard")

SCREENSHOTS_DIR = os.path.abspath("./screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

_stop_event = threading.Event()
_orch_thread: threading.Thread | None = None


def _is_orchestrator_running() -> bool:
    return _orch_thread is not None and _orch_thread.is_alive() and not _stop_event.is_set()


def _start_orchestrator_thread() -> None:
    global _orch_thread
    _stop_event.clear()
    _orch_thread = threading.Thread(
        target=boucle_principale,
        args=(_stop_event,),
        daemon=True,
        name="OrchestratorThread",
    )
    _orch_thread.start()
    log.info("[DASHBOARD] Orchestrator demarre en thread daemon.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _ws_available:
        loop = asyncio.get_event_loop()
        manager.set_loop(loop)
        log.info("[WS] ConnectionManager pret.")
    _start_orchestrator_thread()
    yield
    _stop_event.set()
    if _orch_thread and _orch_thread.is_alive():
        _orch_thread.join(timeout=5)
    log.info("[DASHBOARD] Orchestrator arrete au shutdown FastAPI.")


app = FastAPI(title="Agentic SDLC Dashboard", lifespan=lifespan)

if _ws_available:
    app.include_router(ws_router)

app.mount("/screenshots", StaticFiles(directory=SCREENSHOTS_DIR), name="screenshots")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _get_db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect("pipeline_runs.db")
    conn.row_factory = sqlite3.Row
    return conn


def executer_commande(command: list[str], timeout: int = 600) -> dict:
    try:
        resultat = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "success": resultat.returncode == 0,
            "returncode": resultat.returncode,
            "stdout": resultat.stdout,
            "stderr": resultat.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout : {timeout}s depasse.",
        }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = Path("templates/dashboard.html")
    if not html_path.exists():
        return HTMLResponse("<h1>dashboard.html introuvable dans /templates</h1>", status_code=404)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"success": True, "message": "API running"}


@app.get("/api/config")
def get_config():
    owner_repo = GITHUB_REPO
    pages_base = ""
    if owner_repo and "/" in owner_repo:
        owner, repo = owner_repo.split("/", 1)
        pages_base = f"https://{owner}.github.io/{repo}"
    return {
        "github_repo": owner_repo,
        "github_pages_base": pages_base,
    }


@app.get("/api/orchestrator/status")
def orchestrator_status():
    running = _is_orchestrator_running()
    return {
        "running": running,
        "thread_name": _orch_thread.name if _orch_thread else None,
        "stop_requested": _stop_event.is_set(),
    }


@app.post("/api/orchestrator/stop")
def orchestrator_stop():
    if _stop_event.is_set():
        return {"success": True, "message": "Orchestrator deja arrete."}
    _stop_event.set()
    return {"success": True, "message": "Signal d'arret envoye a l'orchestrator."}


@app.post("/api/orchestrator/start")
def orchestrator_start():
    global _orch_thread
    if _orch_thread and _orch_thread.is_alive() and not _stop_event.is_set():
        return {"success": False, "message": "Orchestrator deja en cours d'execution."}
    _start_orchestrator_thread()
    return {"success": True, "message": "Orchestrator redemarre."}


@app.post("/api/run-code-agent")
def run_code_agent():
    if _is_orchestrator_running():
        return JSONResponse(
            status_code=409,
            content={"success": False, "error": "Orchestrator actif. Arretez-le d'abord."},
        )
    return JSONResponse(executer_commande([sys.executable, "code_agent.py"]))


@app.post("/api/run-testing-agent")
def run_testing_agent():
    if _is_orchestrator_running():
        return JSONResponse(
            status_code=409,
            content={"success": False, "error": "Orchestrator actif. Arretez-le d'abord."},
        )
    return JSONResponse(executer_commande([sys.executable, "testing_agent.py"]))


@app.post("/api/run-full-pipeline")
def run_full_pipeline():
    if _is_orchestrator_running():
        return JSONResponse(
            status_code=409,
            content={"success": False, "error": "Orchestrator actif. Arretez-le d'abord."},
        )
    code = executer_commande([sys.executable, "code_agent.py"])
    testing = executer_commande([sys.executable, "testing_agent.py"])
    return JSONResponse(
        {
            "success": code["success"] and testing["success"],
            "code_agent": code,
            "testing_agent": testing,
        }
    )


@app.get("/api/logs")
def get_logs():
    log_path = Path("orchestrator.log")
    if not log_path.exists():
        return JSONResponse({"success": True, "logs": "Aucun log trouve."})
    logs = log_path.read_text(encoding="utf-8", errors="replace")
    return JSONResponse({"success": True, "logs": logs[-15000:]})


@app.get("/api/screenshots")
def get_screenshots(run_id: str = None):
    screenshots_path = Path(SCREENSHOTS_DIR)
    if not screenshots_path.exists():
        return {"screenshots": [], "total": 0}

    fichiers = sorted(
        [f for f in screenshots_path.glob("*.png")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    items = []
    for p in fichiers:
        filename = p.name
        base = p.stem
        if "_screenshot" in base:
            ticket_id = base.split("_screenshot")[0]
        elif "_" in base:
            ticket_id = base.split("_")[0]
        else:
            ticket_id = base

        file_run_id = base.split("_")[0] if "_" in base else "unknown"

        items.append({
            "ticket_id": ticket_id,
            "filename": filename,
            "title": ticket_id,
            "timestamp": p.stat().st_mtime,
            "size_kb": round(p.stat().st_size / 1024, 1),
            "url": f"/screenshots/{filename}",
            "run_id": file_run_id,
        })

    if run_id:
        items = [s for s in items if s["run_id"] == run_id]

    return {"screenshots": items, "total": len(items)}


@app.get("/api/tickets")
def get_tickets():
    if not (JIRA_URL and JIRA_EMAIL and JIRA_TOKEN):
        return {"error": "Missing JIRA credentials."}

    jql = f'project = "{JIRA_PROJECT_KEY}" ORDER BY created ASC'
    params = {"jql": jql, "fields": "summary,status", "maxResults": 50}
    try:
        r = req.get(
            f"{JIRA_URL}/rest/api/3/search/jql",
            auth=(JIRA_EMAIL, JIRA_TOKEN),
            headers={"Accept": "application/json"},
            params=params,
            timeout=20,
        )
        tickets = r.json().get("issues", [])
        return [
            {
                "key": t["key"],
                "summary": t["fields"]["summary"],
                "status": t["fields"]["status"]["name"],
            }
            for t in tickets
        ]
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/pipeline-runs")
def get_pipeline_runs():
    if not os.path.exists("pipeline_runs.db"):
        return []
    conn = _get_db_conn()
    try:
        rows = conn.execute("SELECT * FROM pipeline_runs ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


@app.get("/api/pipeline-runs/stats")
def get_pipeline_runs_stats():
    try:
        from core.feature_extractor import statistiques_features
        return statistiques_features()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/pipeline-runs/ticket/{ticket_id}")
def get_pipeline_runs_by_ticket(ticket_id: str):
    if not os.path.exists("pipeline_runs.db"):
        return []
    conn = _get_db_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs WHERE ticket_id = ? ORDER BY id DESC",
            (ticket_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


class NouveauTicketRequest(BaseModel):
    summary: str
    description: str = ""


def _handle_create_ticket(body: NouveauTicketRequest) -> JSONResponse:
    if not body.summary or not body.summary.strip():
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Le titre (summary) est obligatoire."},
        )

    resultat = creer_ticket_jira(
        summary=body.summary.strip(),
        description=body.description.strip(),
    )

    if resultat.get("success"):
        return JSONResponse(status_code=201, content=resultat)
    return JSONResponse(status_code=500, content=resultat)


@app.post("/api/create-ticket", tags=["tickets"])
async def create_ticket(body: NouveauTicketRequest):
    return _handle_create_ticket(body)


@app.post("/api/tickets/create", tags=["tickets"])
async def create_ticket_canonical(body: NouveauTicketRequest):
    return _handle_create_ticket(body)


@app.get("/api/deploy/{ticket_id}")
async def get_deploy_url(ticket_id: str):
    url_pages = construire_url_pages(ticket_id)
    return {
        "ticket_id": ticket_id,
        "url_pages": url_pages,
        "pages_actif": pages_deja_actives(),
    }


if __name__ == "__main__":
    uvicorn.run("dashboard_app:app", host="127.0.0.1", port=8000, reload=True)
