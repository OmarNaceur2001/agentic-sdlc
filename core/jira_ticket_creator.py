"""
jira_ticket_creator.py — Création dynamique de tickets Jira
Feature 1 de la feuille de route Agentic SDLC
"""

import os
import requests
from dotenv import load_dotenv

from config.jira_config import (
    JIRA_URL,
    JIRA_EMAIL,
    JIRA_TOKEN,
    JIRA_PROJECT_KEY,
    JIRA_AUTH,
    JIRA_HEADERS,
    creer_document_adf,
)

load_dotenv()


def creer_ticket_jira(summary: str, description: str = "") -> dict:
    """
    Crée un nouveau ticket Jira de type Task dans le projet configuré.

    Args:
        summary: Titre du ticket (obligatoire).
        description: Description en texte brut (optionnelle).

    Returns:
        {"success": True, "key": "SCRUM-X", "url": "https://..."} en cas de succès.
        {"success": False, "error": "message"} en cas d'échec.
    """
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT_KEY]):
        return {
            "success": False,
            "error": "Variables d'environnement Jira manquantes (JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT_KEY)."
        }

    if not summary or not summary.strip():
        return {"success": False, "error": "Le titre du ticket est obligatoire."}

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary.strip(),
            "description": creer_document_adf(description or "Ticket créé depuis le Dashboard Agentic SDLC."),
            "issuetype": {"name": "Task"},
        }
    }

    url = f"{JIRA_URL}/rest/api/3/issue"

    try:
        response = requests.post(
            url,
            json=payload,
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            timeout=15,
        )

        if response.status_code == 201:
            data = response.json()
            ticket_key = data.get("key", "")
            ticket_url = f"{JIRA_URL}/browse/{ticket_key}"
            print(f"[TICKET CREATOR] [OK] Ticket cree : {ticket_key} - {summary}")
            return {
                "success": True,
                "key": ticket_key,
                "url": ticket_url,
                "summary": summary,
            }
        else:
            print(f"[TICKET CREATOR] [ERR] Erreur Jira {response.status_code} : {response.text}")
            return {
                "success": False,
                "error": f"Jira a répondu {response.status_code} : {response.text[:300]}"
            }

    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Impossible de joindre Jira à {JIRA_URL}. Vérifiez la connexion."}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Timeout — Jira n'a pas répondu en 15s."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── TEST RAPIDE ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Test de création de ticket Jira...")
    resultat = creer_ticket_jira(
        summary="Test depuis jira_ticket_creator.py",
        description="Ticket de test automatique créé depuis le Dashboard Agentic SDLC."
    )
    print(resultat)
