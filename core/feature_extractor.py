"""
Feature Extractor — Agentic SDLC v3
Extrait les caractéristiques (features) structurelles et Playwright des pages HTML générées,
et les sauvegarde dans une base de données SQLite.

Schéma versionné — migrations gérées automatiquement.
"""

import os
import re
import html as html_lib
import sqlite3
import copy
from datetime import datetime
from bs4 import BeautifulSoup

# ── Version du schéma ────────────────────────────────────────
SCHEMA_VERSION = 2
DB_PATH = "pipeline_runs.db"


def _features_code_vides() -> dict:
    """Retourne un ensemble de caractéristiques vides en cas d'erreur."""
    return {
        "has_doctype": 0,
        "has_title_tag": 0,
        "has_button": 0,
        "has_body": 0,
        "has_head": 0,
        "css_rules_count": 0,
        "js_scripts_count": 0,
        "js_length": 0,
        "html_length": 0,
        "keyword_coverage": 0.0,
    }


def extraire_features_code(html: str, summary: str) -> dict:
    """Extrait les features structurelles depuis le HTML généré."""
    if not html:
        return _features_code_vides()

    html = html_lib.unescape(html)
    soup = BeautifulSoup(html, "html.parser")
    html_lower = html.lower()

    has_doctype = 1 if "<!doctype html" in html_lower else 0

    has_title_tag = 0
    if soup.title and soup.title.string and len(soup.title.string.strip()) > 0:
        has_title_tag = 1

    has_button = 0
    if soup.find("button") or soup.find("input", type=re.compile("button|submit", re.I)):
        has_button = 1
    else:
        btn_elements = soup.find_all(class_=re.compile("btn|button", re.I))
        if btn_elements:
            has_button = 1

    has_body = 1 if soup.body else 0
    has_head = 1 if soup.head else 0

    css_rules_count = 0
    for style in soup.find_all("style"):
        if style.string:
            css_rules_count += style.string.count("{")

    js_scripts = soup.find_all("script")
    js_scripts_count = len(js_scripts)
    js_length = sum(len(script.string or "") for script in js_scripts)

    html_length = len(html)

    soup_copy = copy.deepcopy(soup)
    for element in soup_copy(["script", "style"]):
        element.extract()
    visible_text = soup_copy.get_text()

    summary_words = set(re.findall(r"\w+", summary.lower()))
    visible_words = set(re.findall(r"\w+", visible_text.lower()))

    if summary_words:
        keyword_coverage = len(summary_words.intersection(visible_words)) / len(summary_words)
    else:
        keyword_coverage = 0.0

    return {
        "has_doctype": has_doctype,
        "has_title_tag": has_title_tag,
        "has_button": has_button,
        "has_body": has_body,
        "has_head": has_head,
        "css_rules_count": css_rules_count,
        "js_scripts_count": js_scripts_count,
        "js_length": js_length,
        "html_length": html_length,
        "keyword_coverage": keyword_coverage,
    }


def extraire_toutes_features(
    ticket: dict,
    html: str,
    playwright_result: dict,
    retry_number: int = 0,
    prompt_version: str = "v1",
    generation_time_sec: float = 0.0,
) -> dict:
    """Combine les caractéristiques HTML et les métriques Playwright pour un ticket."""
    summary = ticket.get("fields", {}).get("summary", "")
    html_feats = extraire_features_code(html, summary)

    return {
        "retry_number": retry_number,
        "prompt_version": prompt_version,
        "generation_time_sec": generation_time_sec,
        "has_doctype": html_feats.get("has_doctype", 0),
        "has_title_tag": html_feats.get("has_title_tag", 0),
        "has_button": html_feats.get("has_button", 0),
        "has_body": html_feats.get("has_body", 0),
        "has_head": html_feats.get("has_head", 0),
        "css_rules_count": html_feats.get("css_rules_count", 0),
        "js_scripts_count": html_feats.get("js_scripts_count", 0),
        "js_length": html_feats.get("js_length", 0),
        "html_length": html_feats.get("html_length", 0),
        "keyword_coverage": html_feats.get("keyword_coverage", 0.0),
        "playwright_load_ok": 1 if playwright_result.get("loaded", False) else 0,
        "visible_text_length": playwright_result.get("text_length", 0),
        "js_errors_count": playwright_result.get("js_errors", 0),
        "console_errors_count": playwright_result.get("console_errors", 0),
        "playwright_load_time_ms": playwright_result.get("load_time_ms", 0.0),
    }


# ── Gestion du schéma SQLite ──────────────────────────────────

_TABLE_COLUMNS = [
    "id INTEGER PRIMARY KEY AUTOINCREMENT",
    "ticket_id TEXT",
    "test_passed INTEGER",
    "run_id TEXT",
    "created_at TEXT",
    "retry_number INTEGER",
    "prompt_version TEXT",
    "generation_time_sec REAL",
    "has_doctype INTEGER",
    "has_title_tag INTEGER",
    "has_button INTEGER",
    "has_body INTEGER",
    "has_head INTEGER",
    "css_rules_count INTEGER",
    "js_scripts_count INTEGER",
    "js_length INTEGER",
    "html_length INTEGER",
    "keyword_coverage REAL",
    "playwright_load_ok INTEGER",
    "visible_text_length INTEGER",
    "js_errors_count INTEGER",
    "console_errors_count INTEGER",
    "playwright_load_time_ms REAL",
]


def _creer_table_v2(cursor: sqlite3.Cursor) -> None:
    """Crée la table pipeline_runs version 2."""
    colonnes = ", ".join(_TABLE_COLUMNS)
    cursor.execute("CREATE TABLE IF NOT EXISTS pipeline_runs (" + colonnes + ")")


def _creer_table_versions(cursor: sqlite3.Cursor) -> None:
    """Crée la table de versioning du schéma."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT
        )
    """)


def _obtenir_version(cursor: sqlite3.Cursor) -> int:
    """Retourne la version actuelle du schéma."""
    try:
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def _appliquer_migration(cursor: sqlite3.Cursor, version_actuelle: int) -> int:
    """Applique les migrations nécessaires. Retourne la nouvelle version."""
    if version_actuelle < 2:
        # Migration v1 → v2 : vérifier que toutes les colonnes existent
        try:
            cursor.execute("SELECT COUNT(*) FROM pipeline_runs LIMIT 1")
        except sqlite3.OperationalError:
            _creer_table_v2(cursor)
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (2, datetime.now().isoformat()),
            )
            return 2

    return version_actuelle


def _initialiser_db(conn: sqlite3.Connection) -> None:
    """Initialise ou migre la base de données."""
    cursor = conn.cursor()
    _creer_table_versions(cursor)
    version = _obtenir_version(cursor)
    version = _appliquer_migration(cursor, version)
    if version >= SCHEMA_VERSION:
        cursor.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now().isoformat()),
        )
    conn.commit()


def sauvegarder_features(
    ticket_id: str,
    features: dict,
    test_passed: bool,
    run_id: str = "",
) -> None:
    """Enregistre les caractéristiques extraites dans la base SQLite."""
    conn = sqlite3.connect(DB_PATH)
    try:
        _initialiser_db(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_runs (
                ticket_id, test_passed, run_id, created_at,
                retry_number, prompt_version, generation_time_sec,
                has_doctype, has_title_tag, has_button, has_body, has_head,
                css_rules_count, js_scripts_count, js_length, html_length,
                keyword_coverage, playwright_load_ok, visible_text_length,
                js_errors_count, console_errors_count, playwright_load_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            1 if test_passed else 0,
            run_id,
            datetime.now().isoformat(),
            features.get("retry_number", 0),
            features.get("prompt_version", "v1"),
            features.get("generation_time_sec", 0.0),
            features.get("has_doctype", 0),
            features.get("has_title_tag", 0),
            features.get("has_button", 0),
            features.get("has_body", 0),
            features.get("has_head", 0),
            features.get("css_rules_count", 0),
            features.get("js_scripts_count", 0),
            features.get("js_length", 0),
            features.get("html_length", 0),
            features.get("keyword_coverage", 0.0),
            features.get("playwright_load_ok", 0),
            features.get("visible_text_length", 0),
            features.get("js_errors_count", 0),
            features.get("console_errors_count", 0),
            features.get("playwright_load_time_ms", 0.0),
        ))
        conn.commit()
    finally:
        conn.close()


def enregistrer_features_ml(
    ticket: dict,
    html: str,
    playwright_metrics: dict,
    test_passed: bool,
    retry_number: int = 0,
    prompt_version: str = "v1",
    run_id: str = "",
) -> dict:
    """Extrait les features et les sauvegarde en base SQLite."""
    if not html:
        return {}

    features = extraire_toutes_features(
        ticket=ticket,
        html=html,
        playwright_result=playwright_metrics,
        retry_number=retry_number,
        prompt_version=prompt_version,
        generation_time_sec=0.0,
    )

    sauvegarder_features(
        ticket_id=ticket.get("key", "INCONNU"),
        features=features,
        test_passed=test_passed,
        run_id=run_id,
    )
    return features


def statistiques_features() -> dict:
    """Calcule des statistiques globales sur les features stockées en base."""
    if not os.path.exists(DB_PATH):
        return {
            "total_samples": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate_pct": 0.0,
        }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*), SUM(test_passed) FROM pipeline_runs")
        row = cursor.fetchone()
        total = row[0] if row else 0
        passed = row[1] if row and row[1] is not None else 0
        failed = total - passed
        pass_rate_pct = (passed / total * 100.0) if total > 0 else 0.0

        cursor.execute("""
            SELECT
                AVG(playwright_load_time_ms),
                AVG(js_errors_count),
                AVG(keyword_coverage),
                AVG(html_length)
            FROM pipeline_runs
        """)
        row_avg = cursor.fetchone()
        avg_load_time = row_avg[0] if row_avg and row_avg[0] is not None else 0.0
        avg_js_errors = row_avg[1] if row_avg and row_avg[1] is not None else 0.0
        avg_keyword_cov = row_avg[2] if row_avg and row_avg[2] is not None else 0.0
        avg_html_len = row_avg[3] if row_avg and row_avg[3] is not None else 0.0

        return {
            "total_samples": total,
            "passed": passed,
            "failed": failed,
            "pass_rate_pct": round(pass_rate_pct, 2),
            "avg_playwright_load_time_ms": round(avg_load_time, 2),
            "avg_js_errors_count": round(avg_js_errors, 2),
            "avg_keyword_coverage": round(avg_keyword_cov, 4),
            "avg_html_length": round(avg_html_len, 2),
        }
    except Exception as e:
        return {
            "error": str(e),
            "total_samples": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate_pct": 0.0,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    _initialiser_db(conn)
    conn.close()

    # Insertion d'un mock sample si la table est complètement vide
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs")
    count = cursor.fetchone()[0]
    if count == 0:
        mock_ticket = {
            "key": "SCRUM-MOCK",
            "fields": {
                "summary": "Create a dummy test page",
                "description": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "This is a mock description text for feature extractor testing."
                                }
                            ]
                        }
                    ]
                }
            }
        }
        mock_html = "<!DOCTYPE html><html><head><title>dummy test page</title></head><body><button>Click me</button></body></html>"
        mock_playwright = {
            "loaded": True,
            "text_length": len("dummy test page Click me"),
            "js_errors": 0,
            "console_errors": 0,
            "load_time_ms": 120.5
        }

        feats = extraire_toutes_features(
            ticket=mock_ticket,
            html=mock_html,
            playwright_result=mock_playwright,
            retry_number=0,
            prompt_version="v1",
            generation_time_sec=1.5
        )

        sauvegarder_features(
            ticket_id="SCRUM-MOCK",
            features=feats,
            test_passed=True,
            run_id="mock-run-id"
        )
        print("Mock sample inserted in SQLite database.")

    conn.close()

    print("\n--- Statistiques Actuelles ---")
    print(statistiques_features())
