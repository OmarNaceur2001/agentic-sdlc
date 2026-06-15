"""
Jira Agent — Semaine 2

Objectif :
- Lire tous les tickets Jira avec la catégorie de statut "To Do" (équivalent de "À faire")
- Afficher les informations principales de chaque ticket
- Changer automatiquement leur statut vers le statut cible défini dans .env

Remarque :
- Les informations sensibles sont lues depuis le fichier .env
- Le fichier .env ne doit jamais être envoyé sur GitHub
"""

import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv


# Charger les variables d'environnement depuis le fichier .env
load_dotenv()


# ─────────────────────────────────────────────────────────────
# Configuration Jira
# ─────────────────────────────────────────────────────────────

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

# Statut cible configurable dans .env (ex: "En cours")
JIRA_TARGET_STATUS = os.getenv("JIRA_TARGET_STATUS", "En cours")

AUTH = (JIRA_EMAIL, JIRA_TOKEN)

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


# ─────────────────────────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────────────────────────

def verifier_configuration() -> None:
    """
    Vérifie que toutes les variables nécessaires existent dans le fichier .env.
    Si une variable manque, le programme s'arrête proprement.
    """
    variables_obligatoires = {
        "JIRA_URL": JIRA_URL,
        "JIRA_EMAIL": JIRA_EMAIL,
        "JIRA_TOKEN": JIRA_TOKEN,
        "JIRA_PROJECT_KEY": JIRA_PROJECT_KEY,
    }

    variables_manquantes = [
        nom for nom, valeur in variables_obligatoires.items() if not valeur
    ]

    if variables_manquantes:
        print("❌ Configuration incomplète dans le fichier .env")
        print("Variables manquantes :")
        for variable in variables_manquantes:
            print(f"   - {variable}")
        sys.exit(1)


def extraire_texte_adf(noeud: Any) -> str:
    """
    Extrait récursivement le texte brut depuis un document ADF Jira.
    """
    morceaux_texte = []

    if isinstance(noeud, dict):
        if noeud.get("type") == "text":
            morceaux_texte.append(noeud.get("text", ""))

        for valeur in noeud.values():
            morceaux_texte.append(extraire_texte_adf(valeur))

    elif isinstance(noeud, list):
        for element in noeud:
            morceaux_texte.append(extraire_texte_adf(element))

    return " ".join(morceau for morceau in morceaux_texte if morceau).strip()


def nettoyer_description(description_adf: dict | None) -> str:
    """
    Convertit la description Jira depuis ADF vers un texte lisible.
    """
    if not description_adf:
        return "Aucune description"

    description = extraire_texte_adf(description_adf)

    if not description:
        return "Description vide"

    return description


# ─────────────────────────────────────────────────────────────
# Lecture des tickets Jira
# ─────────────────────────────────────────────────────────────

def lire_tickets_todo() -> list:
    """
    Lit les tickets Jira dont la catégorie de statut est "To Do".
    C'est l'équivalent de "À faire" dans toutes les langues.
    """
    print("🔍 Recherche des tickets avec la catégorie 'To Do' (travail à faire)...\n")

    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND statusCategory = "To Do" '
        f'ORDER BY created ASC'
    )

    params = {
        "jql": jql,
        "fields": "summary,description,status",
        "maxResults": 50,
    }

    try:
        reponse = requests.get(
            f"{JIRA_URL}/rest/api/3/search/jql",
            auth=AUTH,
            headers=HEADERS,
            params=params,
            timeout=20,
        )

        if reponse.status_code != 200:
            print(f"❌ Erreur Jira pendant la recherche : {reponse.status_code}")
            print(reponse.text[:500])
            return []

        donnees = reponse.json()
        tickets = donnees.get("issues", [])

        print(f"📋 {len(tickets)} ticket(s) trouvé(s)\n")
        return tickets

    except requests.exceptions.RequestException as erreur:
        print("❌ Erreur réseau pendant la recherche Jira.")
        print(f"Détail : {erreur}")
        return []


def afficher_ticket(ticket: dict) -> None:
    """
    Affiche les informations principales d'un ticket Jira.
    """
    ticket_id = ticket.get("key", "ID inconnu")
    champs = ticket.get("fields", {})

    titre = champs.get("summary", "Titre inconnu")
    statut = champs.get("status", {}).get("name", "Statut inconnu")
    description = nettoyer_description(champs.get("description"))

    print(f"┌─ Ticket : {ticket_id}")
    print(f"│  Titre       : {titre}")
    print(f"│  Statut      : {statut}")
    print(f"│  Description : {description}")
    print(f"└{'─' * 60}")


# ─────────────────────────────────────────────────────────────
# Changement de statut Jira
# ─────────────────────────────────────────────────────────────

def obtenir_transitions(ticket_id: str) -> list:
    """
    Récupère les transitions disponibles pour un ticket.
    """
    try:
        reponse = requests.get(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
            auth=AUTH,
            headers=HEADERS,
            timeout=20,
        )

        if reponse.status_code != 200:
            print(f"   ❌ Impossible de lire les transitions pour {ticket_id}")
            print(f"   Code HTTP : {reponse.status_code}")
            print(f"   Détail : {reponse.text[:300]}")
            return []

        return reponse.json().get("transitions", [])

    except requests.exceptions.RequestException as erreur:
        print(f"   ❌ Erreur réseau pendant la lecture des transitions de {ticket_id}")
        print(f"   Détail : {erreur}")
        return []


def trouver_transition_vers_statut(
    transitions: list[dict],
    statut_cible: str
) -> str | None:
    """
    Trouve l'identifiant de transition qui mène vers le statut cible.
    Compare avec le nom de la transition et le nom du statut de destination.
    """
    statut_cible_normalise = statut_cible.lower().strip()

    for transition in transitions:
        nom_transition = transition.get("name", "").lower().strip()
        statut_destination = (
            transition.get("to", {})
            .get("name", "")
            .lower()
            .strip()
        )

        if statut_cible_normalise == statut_destination:
            return transition.get("id")

        if statut_cible_normalise in nom_transition:
            return transition.get("id")

    return None


def afficher_transitions_disponibles(transitions: list[dict]) -> None:
    """
    Affiche les transitions disponibles pour aider au débogage.
    """
    print("   Transitions disponibles :")

    for transition in transitions:
        identifiant = transition.get("id", "id inconnu")
        nom = transition.get("name", "nom inconnu")
        destination = transition.get("to", {}).get("name", "destination inconnue")

        print(f"   - ID {identifiant} | Action: {nom} | Vers: {destination}")


def changer_status(ticket_id: str, nouveau_status: str) -> bool:
    """
    Change le statut d'un ticket Jira.
    """
    transitions = obtenir_transitions(ticket_id)

    if not transitions:
        print(f"   ❌ Aucune transition disponible pour {ticket_id}")
        return False

    transition_id = trouver_transition_vers_statut(transitions, nouveau_status)

    if not transition_id:
        print(f"   ❌ Impossible de trouver une transition vers '{nouveau_status}'")
        afficher_transitions_disponibles(transitions)
        return False

    payload = {
        "transition": {
            "id": transition_id
        }
    }

    try:
        reponse = requests.post(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
            auth=AUTH,
            headers=HEADERS,
            json=payload,
            timeout=20,
        )

        if reponse.status_code == 204:
            print(f"   ✅ {ticket_id} → '{nouveau_status}' avec succès")
            return True

        print(f"   ❌ Échec du changement de statut pour {ticket_id}")
        print(f"   Code HTTP : {reponse.status_code}")
        print(f"   Détail : {reponse.text[:300]}")
        return False

    except requests.exceptions.RequestException as erreur:
        print(f"   ❌ Erreur réseau pendant le changement de statut de {ticket_id}")
        print(f"   Détail : {erreur}")
        return False


# ─────────────────────────────────────────────────────────────
# Programme principal
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """
    Point d'entrée principal du Jira Agent.
    """
    print("=" * 65)
    print("  🤖 Jira Agent — Lecture et mise à jour automatique des tickets")
    print("=" * 65)
    print()

    verifier_configuration()

    tickets = lire_tickets_todo()

    if not tickets:
        print("✅ Aucun ticket dans la catégorie 'To Do' trouvé. Rien à traiter.")
        return

    total_succes = 0
    total_echecs = 0

    for ticket in tickets:
        afficher_ticket(ticket)

        ticket_id = ticket.get("key")

        if not ticket_id:
            print("   ❌ Ticket sans identifiant. Passage au suivant.")
            total_echecs += 1
            continue

        print(f"   ⏳ Changement du statut vers '{JIRA_TARGET_STATUS}'...")

        succes = changer_status(ticket_id, JIRA_TARGET_STATUS)

        if succes:
            total_succes += 1
        else:
            total_echecs += 1

        print()

    print("=" * 65)
    print("  ✅ Traitement terminé")
    print("=" * 65)
    print(f"Tickets modifiés avec succès : {total_succes}")
    print(f"Tickets en échec            : {total_echecs}")


if __name__ == "__main__":
    main()