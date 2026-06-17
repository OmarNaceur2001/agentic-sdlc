import os
import subprocess
import sys
from pathlib import Path

import requests as req
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

screenshots_dir = Path("screenshots")
screenshots_dir.mkdir(exist_ok=True)

app = FastAPI(title="Agentic SDLC Dashboard")

app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")

# Mount static si existe
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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
            "stderr": f"Timeout : {timeout}s dépassé.",
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


@app.post("/api/run-code-agent")
def run_code_agent():
    return JSONResponse(executer_commande([sys.executable, "code_agent.py"]))


@app.post("/api/run-testing-agent")
def run_testing_agent():
    return JSONResponse(executer_commande([sys.executable, "testing_agent.py"]))


@app.post("/api/run-full-pipeline")
def run_full_pipeline():
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
        return JSONResponse({"success": True, "logs": "Aucun log trouvé."})
    logs = log_path.read_text(encoding="utf-8", errors="replace")
    return JSONResponse({"success": True, "logs": logs[-15000:]})


load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")


@app.get("/api/screenshots")
def get_screenshots():
    # Return metadata for files inside ./screenshots
    items = []
    for p in sorted(screenshots_dir.glob("*.png")):
        filename = p.name
        # Expect patterns like <ticket_id>_*.png or <ticket_id>.png
        ticket_id = filename.split("_")[0].rsplit(".", 1)[0]
        items.append({
            "ticket_id": ticket_id,
            "filename": filename,
            "title": ticket_id,
        })
    return items


@app.get("/api/tickets")
def get_tickets():
    if not (JIRA_URL and JIRA_EMAIL and JIRA_TOKEN):
        return {"error": "Missing JIRA credentials (JIRA_URL/JIRA_EMAIL/JIRA_TOKEN)."}

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

