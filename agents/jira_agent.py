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

import sys

from config.jira_config import (
    JIRA_PROGRESS_STATUS,
    JIRA_URL,
    extraire_texte_adf,
    changer_status,
    lire_tickets_todo,
    verifier_configuration,
)


def afficher_ticket(ticket: dict) -> None:
    """
    Affiche les informations principales d'un ticket Jira.
    """
    ticket_id = ticket.get("key", "ID inconnu")
    champs = ticket.get("fields", {})

    titre = champs.get("summary", "Titre inconnu")
    statut = champs.get("status", {}).get("name", "Statut inconnu")
    description_adf = champs.get("description")
    description = extraire_texte_adf(description_adf) if description_adf else "Aucune description"

    print(f"┌─ Ticket : {ticket_id}")
    print(f"│  Titre       : {titre}")
    print(f"│  Statut      : {statut}")
    print(f"│  Description : {description}")
    print(f"└{'─' * 60}")


def afficher_transitions_disponibles(ticket_id: str) -> None:
    """Affiche les transitions disponibles pour aider au débogage."""
    from config.jira_config import obtenir_transitions
    transitions = obtenir_transitions(ticket_id)
    print("   Transitions disponibles :")
    for transition in transitions:
        identifiant = transition.get("id", "id inconnu")
        nom = transition.get("name", "nom inconnu")
        destination = transition.get("to", {}).get("name", "destination inconnue")
        print(f"   - ID {identifiant} | Action: {nom} | Vers: {destination}")


def main() -> None:
    """
    Point d'entrée principal du Jira Agent.
    """
    print("=" * 65)
    print("  [AI] Jira Agent -- Lecture et mise a jour automatique des tickets")
    print("=" * 65)
    print()

    verifier_configuration()

    tickets = lire_tickets_todo()

    if not tickets:
        print("[OK] Aucun ticket dans la categorie 'To Do' trouve. Rien a traiter.")
        return

    total_succes = 0
    total_echecs = 0

    for ticket in tickets:
        afficher_ticket(ticket)

        ticket_id = ticket.get("key")

        if not ticket_id:
            print("   [ERR] Ticket sans identifiant. Passage au suivant.")
            total_echecs += 1
            continue

        print(f"   [..] Changement du statut vers '{JIRA_PROGRESS_STATUS}'...")

        succes = changer_status(ticket_id, JIRA_PROGRESS_STATUS)

        if succes:
            total_succes += 1
        else:
            total_echecs += 1

        print()

    print("=" * 65)
    print("  [OK] Traitement termine")
    print("=" * 65)
    print(f"Tickets modifiés avec succès : {total_succes}")
    print(f"Tickets en échec            : {total_echecs}")


if __name__ == "__main__":
    main()
