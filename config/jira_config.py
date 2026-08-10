"""
jira_config.py — Configuration centralisée Jira

Module unique pour l'authentification, les headers, et les fonctions
communes d'accès à Jira. Élimine la duplication entre code_agent,
testing_agent, jira_agent, jira_ticket_creator et deployment_agent.
"""

import os
import unicodedata
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────
JIRA_URL = os.getenv("JIRA_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")

JIRA_REVIEW_STATUS = os.getenv("JIRA_REVIEW_STATUS", "Revue en cours")
JIRA_DONE_STATUS = os.getenv("JIRA_DONE_STATUS", "Terminé(e)")
JIRA_REOPEN_STATUS = os.getenv("JIRA_REOPEN_STATUS", "À faire")
JIRA_PROGRESS_STATUS = os.getenv("JIRA_PROGRESS_STATUS", "En cours")

JIRA_AUTH = (JIRA_EMAIL, JIRA_TOKEN) if JIRA_EMAIL and JIRA_TOKEN else None

JIRA_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

REQUEST_TIMEOUT = 20


def verifier_configuration() -> None:
    """Vérifie que toutes les variables Jira sont définies."""
    variables = {
        "JIRA_URL": JIRA_URL,
        "JIRA_EMAIL": JIRA_EMAIL,
        "JIRA_TOKEN": JIRA_TOKEN,
        "JIRA_PROJECT_KEY": JIRA_PROJECT_KEY,
    }
    manquantes = [nom for nom, val in variables.items() if not val]
    if manquantes:
        raise SystemExit(
            f"Configuration Jira incomplète. Variables manquantes : {', '.join(manquantes)}"
        )


# ── Utilitaires texte ─────────────────────────────────────────

def normaliser_texte(texte: str) -> str:
    """Normalise un texte pour comparer les statuts Jira (supprime accents, minuscule)."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(
        c for c in texte if unicodedata.category(c) != "Mn"
    )
    return texte


# ── Extraction ADF ────────────────────────────────────────────

def extraire_texte_adf(noeud: Any) -> str:
    """Extrait récursivement le texte brut depuis un document ADF Jira."""
    morceaux: list[str] = []

    if isinstance(noeud, dict):
        if noeud.get("type") == "text":
            morceaux.append(noeud.get("text", ""))
        for valeur in noeud.values():
            morceaux.append(extraire_texte_adf(valeur))
    elif isinstance(noeud, list):
        for element in noeud:
            morceaux.append(extraire_texte_adf(element))

    return " ".join(m for m in morceaux if m).strip()


def creer_document_adf(texte: str) -> dict:
    """Convertit un texte multi-lignes en document ADF Jira."""
    paragraphes = []
    for ligne in texte.splitlines():
        paragraphes.append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": ligne if ligne else " "}
            ],
        })
    return {"type": "doc", "version": 1, "content": paragraphes}


# ── Lecture des tickets ───────────────────────────────────────

def lire_tickets_par_jql(jql: str, max_results: int = 50) -> list[dict]:
    """Exécute une requête JQL et retourne la liste des tickets."""
    if not JIRA_AUTH:
        return []

    params = {
        "jql": jql,
        "fields": "summary,description,status",
        "maxResults": max_results,
    }
    try:
        reponse = requests.get(
            f"{JIRA_URL}/rest/api/3/search/jql",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        if reponse.status_code != 200:
            return []
        return reponse.json().get("issues", [])
    except requests.exceptions.RequestException:
        return []


def lire_tickets_todo() -> list[dict]:
    """Lit les tickets avec statusCategory = To Do."""
    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND statusCategory = "To Do" '
        f"ORDER BY created ASC"
    )
    return lire_tickets_par_jql(jql)


def lire_tickets_in_review() -> list[dict]:
    """Lit les tickets en statut de révision."""
    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND status = "{JIRA_REVIEW_STATUS}" '
        f"ORDER BY updated ASC"
    )
    return lire_tickets_par_jql(jql)


def lire_tickets_bloques( minutes: int = 5) -> list[dict]:
    """Lit les tickets bloqués en 'En cours' ou 'Revue en cours' depuis plus de N minutes."""
    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND status in ("{JIRA_PROGRESS_STATUS}", "{JIRA_REVIEW_STATUS}") '
        f'AND updated <= "-{minutes}m" '
        f"ORDER BY updated ASC"
    )
    return lire_tickets_par_jql(jql)


# ── Transitions ──────────────────────────────────────────────

def obtenir_transitions(ticket_id: str) -> list[dict]:
    """Récupère les transitions disponibles pour un ticket."""
    if not JIRA_AUTH:
        return []
    try:
        reponse = requests.get(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if reponse.status_code != 200:
            return []
        return reponse.json().get("transitions", [])
    except requests.exceptions.RequestException:
        return []


def trouver_transition_vers_statut(transitions: list[dict], statut_cible: str) -> str | None:
    """Trouve l'ID de transition menant vers le statut cible."""
    cible = normaliser_texte(statut_cible)

    for transition in transitions:
        destination = normaliser_texte(transition.get("to", {}).get("name", ""))
        action = normaliser_texte(transition.get("name", ""))

        if cible == destination or cible == action or cible in action:
            return transition.get("id")

    return None


def changer_status(ticket_id: str, statut_cible: str) -> bool:
    """Change le statut d'un ticket Jira. Retourne True si succès."""
    transitions = obtenir_transitions(ticket_id)
    if not transitions:
        return False

    transition_id = trouver_transition_vers_statut(transitions, statut_cible)
    if not transition_id:
        disponibles = [t.get("to", {}).get("name", "") for t in transitions]
        print(f"   [WARN] Transition vers '{statut_cible}' introuvable. Disponibles : {disponibles}")
        return False

    try:
        reponse = requests.post(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            json={"transition": {"id": transition_id}},
            timeout=REQUEST_TIMEOUT,
        )
        return reponse.status_code == 204
    except requests.exceptions.RequestException:
        return False


# ── Commentaires ─────────────────────────────────────────────

def commenter_jira(ticket_id: str, texte: str) -> bool:
    """Ajoute un commentaire Jira avec un document ADF."""
    if not JIRA_AUTH:
        return False
    payload = {"body": creer_document_adf(texte)}
    try:
        reponse = requests.post(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/comment",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        return reponse.status_code in (200, 201)
    except requests.exceptions.RequestException:
        return False
