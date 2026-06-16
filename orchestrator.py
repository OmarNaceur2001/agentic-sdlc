"""
Orchestrator v2 — Full Pipeline Agentic SDLC

Objectif :
- Surveiller Jira en continu
- Détecter les tickets "À faire"
- Lancer le Code Agent
- Lancer le Testing Agent
- Si les tests réussissent : ticket → Terminé(e)
- Si les tests échouent : ticket → À faire
- Réessayer automatiquement jusqu'à MAX_RETRIES
"""

import os
import time
import logging
from datetime import datetime

from dotenv import load_dotenv

from code_agent import lire_tickets_todo, traiter_ticket

from testing_agent import (
    lire_tickets_in_review,
    telecharger_html_github,
    tester_structure_html,
    tester_elements_metier,
    tester_avec_playwright,
    commenter_jira,
    changer_status_jira,
    ResultatTest,
    JIRA_DONE_STATUS,
    JIRA_REOPEN_STATUS,
)


load_dotenv()


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))


# ─────────────────────────────────────────────────────────────
# Logger
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("orchestrator.log", encoding="utf-8"),
    ],
)

log = logging.getLogger("orchestrator")


# ─────────────────────────────────────────────────────────────
# Mémoire de retries pendant la session
# ─────────────────────────────────────────────────────────────

retries: dict[str, int] = {}


# ─────────────────────────────────────────────────────────────
# Affichage
# ─────────────────────────────────────────────────────────────

def afficher_banniere() -> None:
    """
    Affiche la bannière de démarrage.
    """
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       🤖 Agentic SDLC — Full Pipeline Orchestrator v2       ║")
    print("║                                                              ║")
    print("║  À faire → Code Agent → Testing Agent → Terminé(e)          ║")
    print("║  Échec tests → À faire → Retry automatique                  ║")
    print("║                                                              ║")
    print("║  Ctrl+C pour arrêter proprement.                            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def afficher_separateur(cycle: int) -> None:
    """
    Affiche un séparateur clair à chaque cycle.
    """
    heure = datetime.now().strftime("%H:%M:%S")

    print()
    print("═" * 62)
    print(f"  Cycle #{cycle:04d}  |  {heure}")
    print("═" * 62)


def attendre_prochain_cycle() -> None:
    """
    Attend avant le prochain cycle.
    """
    log.info(f"Pause {POLL_INTERVAL}s...")

    for secondes in range(POLL_INTERVAL, 0, -1):
        print(f"  ⏳ Prochain cycle dans {secondes:2d}s", end="\r")
        time.sleep(1)

    print()


# ─────────────────────────────────────────────────────────────
# Phase 1 — Code Agent
# ─────────────────────────────────────────────────────────────

def phase_code_generation() -> int:
    """
    Lit les tickets À faire et lance le Code Agent.

    Retour :
        Nombre de tickets envoyés au Code Agent.
    """
    tickets = lire_tickets_todo()

    if not tickets:
        log.info("[CODE AGENT] Aucun ticket À faire")
        return 0

    log.info(f"[CODE AGENT] {len(tickets)} ticket(s) À faire détecté(s)")

    traites = 0

    for ticket in tickets:
        ticket_id = ticket.get("key", "INCONNU")
        titre = ticket.get("fields", {}).get("summary", "Titre inconnu")

        nb_retries = retries.get(ticket_id, 0)

        if nb_retries >= MAX_RETRIES:
            log.warning(
                f"[CODE AGENT] {ticket_id} ignoré : "
                f"maximum de retries atteint ({nb_retries}/{MAX_RETRIES})"
            )
            continue

        if nb_retries > 0:
            log.info(
                f"[CODE AGENT] Retry {ticket_id} : "
                f"tentative {nb_retries + 1}/{MAX_RETRIES}"
            )

        log.info(f"[CODE AGENT] Traitement : {ticket_id} — {titre}")

        try:
            traiter_ticket(ticket)
            traites += 1

        except Exception as erreur:
            log.exception(f"[CODE AGENT] Erreur sur {ticket_id} : {erreur}")

    return traites


# ─────────────────────────────────────────────────────────────
# Phase 2 — Testing Agent avec résultat booléen
# ─────────────────────────────────────────────────────────────

def tester_ticket_avec_resultat(ticket: dict) -> bool:
    """
    Teste un ticket avec la logique du Testing Agent.

    Retour :
        True  → tests réussis
        False → tests échoués
    """
    ticket_id = ticket.get("key", "INCONNU")
    champs = ticket.get("fields", {})
    titre = champs.get("summary", "Titre inconnu")

    print()
    print(f"┌─ Test : {ticket_id} — {titre}")
    print(f"└{'─' * 60}")

    resultat = ResultatTest(ticket_id)

    html = telecharger_html_github(ticket_id)

    if not html:
        resultat.ajouter_erreur("Impossible de télécharger le HTML depuis GitHub")
    else:
        tester_structure_html(html, resultat)
        tester_elements_metier(html, titre, resultat)
        tester_avec_playwright(html, ticket_id, resultat)

    rapport = resultat.rapport()

    print()
    print(rapport)

    if resultat.succes:
        commenter_jira(
            ticket_id,
            "✅ Tests automatiques réussis.\n\n" + rapport,
        )

        changer_status_jira(ticket_id, JIRA_DONE_STATUS)
        return True

    commenter_jira(
        ticket_id,
        "❌ Tests automatiques échoués.\n\n" + rapport,
    )

    changer_status_jira(ticket_id, JIRA_REOPEN_STATUS)
    return False


def phase_testing() -> tuple[int, int]:
    """
    Lit les tickets en review et lance les tests.

    Retour :
        (nombre de succès, nombre d'échecs)
    """
    tickets = lire_tickets_in_review()

    if not tickets:
        log.info("[TEST AGENT] Aucun ticket en review")
        return 0, 0

    log.info(f"[TEST AGENT] {len(tickets)} ticket(s) en review détecté(s)")

    succes = 0
    echecs = 0

    for ticket in tickets:
        ticket_id = ticket.get("key", "INCONNU")
        titre = ticket.get("fields", {}).get("summary", "Titre inconnu")

        log.info(f"[TEST AGENT] Test : {ticket_id} — {titre}")

        try:
            resultat_ok = tester_ticket_avec_resultat(ticket)

            if resultat_ok:
                succes += 1
                retries.pop(ticket_id, None)
                log.info(f"[TEST AGENT] ✅ {ticket_id} validé → DONE")

            else:
                echecs += 1
                retries[ticket_id] = retries.get(ticket_id, 0) + 1

                log.warning(
                    f"[TEST AGENT] ❌ {ticket_id} échoué → retour À faire "
                    f"(tentative {retries[ticket_id]}/{MAX_RETRIES})"
                )

                if retries[ticket_id] >= MAX_RETRIES:
                    log.error(
                        f"[TEST AGENT] {ticket_id} a atteint "
                        f"le maximum de retries. Intervention manuelle requise."
                    )

        except Exception as erreur:
            echecs += 1
            log.exception(f"[TEST AGENT] Erreur sur {ticket_id} : {erreur}")

    return succes, echecs


# ─────────────────────────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────────────────────────

def boucle_principale() -> None:
    """
    Boucle principale du Full Pipeline.
    """
    cycle = 0
    total_done = 0
    total_echecs = 0

    log.info(f"Orchestrator v2 démarré — poll toutes les {POLL_INTERVAL}s")
    log.info(f"Max retries par ticket : {MAX_RETRIES}")

    while True:
        cycle += 1
        afficher_separateur(cycle)

        try:
            codes_traites = phase_code_generation()

            if codes_traites > 0:
                log.info("Pause 5s avant la phase de test...")
                time.sleep(5)

            succes, echecs = phase_testing()

            total_done += succes
            total_echecs += echecs

            log.info(f"Résumé cycle #{cycle:04d} :")
            log.info(f"  Code généré   : {codes_traites} ticket(s)")
            log.info(f"  Tests réussis : {succes} ticket(s)")
            log.info(f"  Tests échoués : {echecs} ticket(s)")
            log.info(f"  Total DONE    : {total_done} ticket(s)")
            log.info(f"  Total échecs  : {total_echecs} ticket(s)")

            if retries:
                log.info(f"  Retries actifs: {dict(retries)}")

        except Exception as erreur:
            log.exception(f"Erreur inattendue dans le cycle #{cycle} : {erreur}")

        attendre_prochain_cycle()


# ─────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """
    Point d'entrée principal.
    """
    afficher_banniere()

    try:
        boucle_principale()

    except KeyboardInterrupt:
        print()
        log.info("Orchestrator arrêté par Ctrl+C")
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                  ✅ Arrêt propre — À bientôt !              ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()


if __name__ == "__main__":
    main()