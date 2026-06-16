"""
Orchestrator — Agentic SDLC
Poll Jira toutes les 30s et déclenche le Code Agent automatiquement.
"""

import os
import time
import logging
from dotenv import load_dotenv
from code_agent import lire_tickets_todo, traiter_ticket

load_dotenv()

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("orchestrator.log"),
    ]
)
log = logging.getLogger("orchestrator")


def main() -> None:
    print()
    print("==========================================================")
    print("   Agentic SDLC -- Orchestrator v1.0")
    print("   Surveille Jira et genere du code automatiquement.")
    print("   Ctrl+C pour arreter.")
    print("==========================================================")
    print()

    log.info(f"Orchestrator demarre -- poll toutes les {POLL_INTERVAL}s")
    cycle = 0
    total = 0

    try:
        while True:
            cycle += 1
            print(f"\n{'─' * 55}")
            log.info(f"Cycle #{cycle:04d} -- Verification Jira...")

            try:
                tickets = lire_tickets_todo()
                if not tickets:
                    log.info("Aucun ticket 'A faire' -- en attente...")
                else:
                    log.info(f"{len(tickets)} ticket(s) detecte(s)")
                    for ticket in tickets:
                        tid   = ticket.get("key", "?")
                        titre = ticket.get("fields", {}).get("summary", "")
                        log.info(f"Traitement : {tid} -- {titre}")
                        try:
                            traiter_ticket(ticket)
                            total += 1
                            log.info(f"{tid} traite avec succes")
                        except Exception as e:
                            log.error(f"Erreur sur {tid}: {e}")
                log.info(f"Total traites depuis demarrage : {total}")
            except Exception as e:
                log.error(f"Erreur cycle #{cycle}: {e}")

            log.info(f"Pause {POLL_INTERVAL}s...")
            for s in range(POLL_INTERVAL, 0, -1):
                print(f"  Prochain poll dans {s:2d}s", end="\r")
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n")
        log.info("Arret par Ctrl+C")
        print("==========================================================")
        print("   Arret propre -- A bientot !")
        print("==========================================================")


if __name__ == "__main__":
    main()
