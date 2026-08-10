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
- Récupérer les tickets orphelins bloqués
"""

import os
import time
import logging
import threading
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config.jira_config import (
    JIRA_PROGRESS_STATUS,
    JIRA_REVIEW_STATUS,
    JIRA_DONE_STATUS,
    JIRA_REOPEN_STATUS,
    changer_status,
    commenter_jira,
    lire_tickets_todo,
    lire_tickets_in_review,
    lire_tickets_bloques,
)

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# ─────────────────────────────────────────────────────────────
# Thread safety
# ─────────────────────────────────────────────────────────────

_lock = threading.Lock()

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

# ── Feature 4: broadcast logs to WebSocket clients ───────────
try:
    from core.websocket_manager import manager, WebSocketLogHandler
    _ws_handler = WebSocketLogHandler(manager)
    _ws_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    log.addHandler(_ws_handler)
    print("[ORCH] WebSocket log handler branché.")
except ImportError:
    print("[ORCH] websocket_manager non disponible — logs WebSocket désactivés.")


# ─────────────────────────────────────────────────────────────
# Mémoire de retries pendant la session (protégée par lock)
# ─────────────────────────────────────────────────────────────

retries: dict[str, int] = {}


def _get_retry(ticket_id: str) -> int:
    with _lock:
        return retries.get(ticket_id, 0)


def _inc_retry(ticket_id: str) -> int:
    with _lock:
        retries[ticket_id] = retries.get(ticket_id, 0) + 1
        return retries[ticket_id]


def _clear_retry(ticket_id: str) -> None:
    with _lock:
        retries.pop(ticket_id, None)


# ─────────────────────────────────────────────────────────────
# Affichage
# ─────────────────────────────────────────────────────────────

def afficher_banniere() -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       [AI] Agentic SDLC -- Full Pipeline Orchestrator v2   ║")
    print("║                                                              ║")
    print("║  A faire -> Code Agent -> Testing Agent -> Termine(e)       ║")
    print("║  Echec tests -> A faire -> Retry automatique                ║")
    print("║  Recovery : tickets orphelins -> A faire                    ║")
    print("║                                                              ║")
    print("║  Ctrl+C pour arreter proprement.                            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def afficher_separateur(cycle: int) -> None:
    heure = datetime.now().strftime("%H:%M:%S")
    print()
    print("═" * 62)
    print(f"  Cycle #{cycle:04d}  |  {heure}")
    print("═" * 62)


# ─────────────────────────────────────────────────────────────
# Phase 0 — Recovery des tickets orphelins
# ─────────────────────────────────────────────────────────────

def phase_recovery() -> int:
    """
    Récupère les tickets bloqués en 'En cours' ou 'Revue en cours' depuis >5 minutes
    et les remet en 'À faire' pour relancer le pipeline.
    """
    tickets_bloques = lire_tickets_bloques(minutes=5)

    if not tickets_bloques:
        return 0

    log.info(f"[RECOVERY] {len(tickets_bloques)} ticket(s) orphelin(s) détecté(s)")

    recuperes = 0
    for ticket in tickets_bloques:
        ticket_id = ticket.get("key", "INCONNU")
        titre = ticket.get("fields", {}).get("summary", "Titre inconnu")
        statut = ticket.get("fields", {}).get("status", {}).get("name", "inconnu")

        log.info(f"[RECOVERY] {ticket_id} — '{statut}' depuis >5 min → retour À faire")
        if changer_status(ticket_id, JIRA_REOPEN_STATUS):
            _clear_retry(ticket_id)
            recuperes += 1
            log.info(f"[RECOVERY] [OK] {ticket_id} remis en '{JIRA_REOPEN_STATUS}'")
        else:
            log.warning(f"[RECOVERY] [ERR] Impossible de remettre {ticket_id} en '{JIRA_REOPEN_STATUS}'")

    return recuperes


# ─────────────────────────────────────────────────────────────
# Phase 1 — Code Agent
# ─────────────────────────────────────────────────────────────

def phase_code_generation() -> int:
    """Lit les tickets À faire et lance le Code Agent."""
    from agents.code_agent import traiter_ticket

    tickets = lire_tickets_todo()

    if not tickets:
        log.info("[CODE AGENT] Aucun ticket À faire")
        return 0

    log.info(f"[CODE AGENT] {len(tickets)} ticket(s) À faire détecté(s)")

    traites = 0

    for ticket in tickets:
        ticket_id = ticket.get("key", "INCONNU")
        titre = ticket.get("fields", {}).get("summary", "Titre inconnu")

        nb_retries = _get_retry(ticket_id)

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
            succes_generation = traiter_ticket(ticket)
            if succes_generation:
                traites += 1
            else:
                _inc_retry(ticket_id)
                log.warning(
                    f"[CODE AGENT] {ticket_id} : échec génération/transition "
                    f"(tentative {_get_retry(ticket_id)}/{MAX_RETRIES})"
                )

        except Exception as erreur:
            log.exception(f"[CODE AGENT] Erreur sur {ticket_id} : {erreur}")
            _inc_retry(ticket_id)

    return traites


# ─────────────────────────────────────────────────────────────
# Phase 2 — Testing Agent avec résultat booléen
# ─────────────────────────────────────────────────────────────

def tester_ticket_avec_resultat(ticket: dict) -> bool:
    """
    Teste un ticket avec la logique du Testing Agent.
    Retourne True si tests réussis, False sinon.
    """
    from agents.testing_agent import (
        telecharger_html_github,
        tester_structure_html,
        tester_elements_metier,
        tester_avec_playwright,
        ResultatTest,
    )

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
        playwright_metrics = tester_avec_playwright(html, ticket_id, resultat)

        try:
            from core.feature_extractor import enregistrer_features_ml
            enregistrer_features_ml(
                ticket=ticket,
                html=html,
                playwright_metrics=playwright_metrics,
                test_passed=resultat.succes,
                retry_number=_get_retry(ticket_id),
                prompt_version="v1",
                run_id="",
            )
            log.info(f"[ML] Features sauvegardées pour {ticket_id}")
        except Exception as e:
            log.warning(f"[ML] Impossible de sauvegarder les features : {e}")

    rapport = resultat.rapport()

    print()
    print(rapport)

    if resultat.succes:
        commenter_jira(
            ticket_id,
            "Tests automatiques reussis.\n\n" + rapport,
        )
        changer_status(ticket_id, JIRA_DONE_STATUS)
        return True

    commenter_jira(
        ticket_id,
        "Tests automatiques echoues.\n\n" + rapport,
    )
    changer_status(ticket_id, JIRA_REOPEN_STATUS)
    return False


def phase_testing() -> tuple[int, int, list[dict]]:
    """Lit les tickets en review et lance les tests."""
    tickets = lire_tickets_in_review()

    if not tickets:
        log.info("[TEST AGENT] Aucun ticket en review")
        return 0, 0, []

    log.info(f"[TEST AGENT] {len(tickets)} ticket(s) en review détecté(s)")

    succes = 0
    echecs = 0
    tickets_reussis = []

    for ticket in tickets:
        ticket_id = ticket.get("key", "INCONNU")
        titre = ticket.get("fields", {}).get("summary", "Titre inconnu")

        log.info(f"[TEST AGENT] Test : {ticket_id} — {titre}")

        try:
            resultat_ok = tester_ticket_avec_resultat(ticket)

            if resultat_ok:
                succes += 1
                _clear_retry(ticket_id)
                tickets_reussis.append(ticket)
                log.info(f"[TEST AGENT] [OK] {ticket_id} valide -> DONE")

            else:
                echecs += 1
                current_retry = _inc_retry(ticket_id)
                log.warning(
                    f"[TEST AGENT] [ERR] {ticket_id} echoue -> retour {JIRA_REOPEN_STATUS} "
                    f"(tentative {current_retry}/{MAX_RETRIES})"
                )
                if current_retry >= MAX_RETRIES:
                    log.error(
                        f"[TEST AGENT] {ticket_id} a atteint "
                        f"le maximum de retries. Intervention manuelle requise."
                    )

        except Exception as erreur:
            echecs += 1
            log.exception(f"[TEST AGENT] Erreur sur {ticket_id} : {erreur}")

    return succes, echecs, tickets_reussis


# ─────────────────────────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────────────────────────

def boucle_principale(stop_event: threading.Event | None = None) -> None:
    """
    Boucle principale du Full Pipeline.

    Args:
        stop_event: threading.Event optionnel. Si fourni, la boucle s'arrête
                    proprement dès que stop_event.is_set() est True.
                    Si None, tourne indéfiniment (mode standalone).
    """
    if stop_event is None:
        stop_event = threading.Event()

    cycle = 0
    total_done = 0
    total_echecs = 0

    log.info(f"Orchestrator v2 démarré — poll toutes les {POLL_INTERVAL}s")
    log.info(f"Max retries par ticket : {MAX_RETRIES}")

    while not stop_event.is_set():
        cycle += 1
        afficher_separateur(cycle)

        try:
            # Phase 0 — Recovery
            recuperes = phase_recovery()
            if recuperes > 0:
                log.info(f"[RECOVERY] {recuperes} ticket(s) récupéré(s)")

            # Phase 1 — Code generation
            codes_traites = phase_code_generation()

            if codes_traites > 0:
                log.info("Pause 5s avant la phase de test...")
                for _ in range(5):
                    if stop_event.is_set():
                        break
                    time.sleep(1)

            if stop_event.is_set():
                break

            # Phase 2 — Testing
            succes, echecs, tickets_reussis = phase_testing()

            total_done += succes
            total_echecs += echecs

            # Phase 3 — Deploy
            for ticket in tickets_reussis:
                run_id = ticket.get("key", "INCONNU")

                try:
                    log.info(f"[DEPLOY] {run_id} — téléchargement HTML...")
                    from agents.testing_agent import telecharger_html_github
                    html = telecharger_html_github(run_id)

                    if not html:
                        log.error(f"[DEPLOY] Impossible de télécharger le HTML pour {run_id}")
                        continue

                    path = Path("generated") / run_id / "index.html"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(html, encoding="utf-8")

                    from agents.deployment_agent import deploy_to_github_pages, DeploymentError
                    result = deploy_to_github_pages(run_id, str(path))
                    log.info(f"[DEPLOY] {run_id} → {result['url']}")

                except DeploymentError as e:
                    log.error(f"[DEPLOY] FAILED {run_id}: {e}")

            log.info(f"Résumé cycle #{cycle:04d} :")
            log.info(f"  Récupérés     : {recuperes} ticket(s)")
            log.info(f"  Code généré   : {codes_traites} ticket(s)")
            log.info(f"  Tests réussis : {succes} ticket(s)")
            log.info(f"  Tests échoués : {echecs} ticket(s)")
            log.info(f"  Total DONE    : {total_done} ticket(s)")
            log.info(f"  Total échecs  : {total_echecs} ticket(s)")

            with _lock:
                if retries:
                    log.info(f"  Retries actifs: {dict(retries)}")

        except Exception as erreur:
            log.exception(f"Erreur inattendue dans le cycle #{cycle} : {erreur}")

        log.info(f"Pause {POLL_INTERVAL}s...")
        stop_event.wait(timeout=POLL_INTERVAL)

    log.info("Orchestrator arrêté proprement (stop_event déclenché).")


# ─────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """Point d'entrée principal (mode standalone — Ctrl+C pour arrêter)."""
    afficher_banniere()
    _stop = threading.Event()

    try:
        boucle_principale(_stop)

    except KeyboardInterrupt:
        print()
        _stop.set()
        log.info("Orchestrator arrêté par Ctrl+C")
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║                  [OK] Arret propre -- A bientot !          ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()


if __name__ == "__main__":
    main()
