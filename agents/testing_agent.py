"""
Testing Agent — Semaine 5

Objectif :
- Lire les tickets Jira en statut "Revue en cours"
- Télécharger le fichier HTML généré depuis GitHub
- Valider la structure HTML
- Ouvrir la page avec Chromium via Playwright
- Vérifier les erreurs JavaScript
- Vérifier la présence d'éléments essentiels
- Ajouter un rapport de test dans Jira
- Si succès : déplacer le ticket vers "Terminé(e)"
- Si échec : retourner le ticket vers "À faire"
"""

import logging
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Error as PlaywrightError

try:
    from core.feature_extractor import enregistrer_features_ml
except Exception:
    enregistrer_features_ml = None

from config.jira_config import (
    JIRA_DONE_STATUS,
    JIRA_REOPEN_STATUS,
    JIRA_REVIEW_STATUS,
    commenter_jira,
    changer_status,
    lire_tickets_in_review,
    normaliser_texte,
)
from config.github_config import telecharger_fichier

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Logger
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("testing_agent")


# ─────────────────────────────────────────────────────────────
# Classe résultat
# ─────────────────────────────────────────────────────────────

class ResultatTest:
    """
    Contient le résultat complet du test d'un ticket.
    """

    def __init__(self, ticket_id: str):
        self.ticket_id = ticket_id
        self.succes = True
        self.erreurs: list[str] = []
        self.avertissements: list[str] = []

    def ajouter_erreur(self, message: str) -> None:
        """
        Ajoute une erreur bloquante.
        """
        self.erreurs.append(message)
        self.succes = False

    def ajouter_avertissement(self, message: str) -> None:
        """
        Ajoute un avertissement non bloquant.
        """
        self.avertissements.append(message)

    def rapport(self) -> str:
        """
        Génère un rapport texte lisible.
        """
        lignes = [
            f"=== Rapport de test : {self.ticket_id} ===",
            "",
        ]

        if self.succes:
            lignes.append("[OK] Resultat : SUCCES")
        else:
            lignes.append("[ERR] Resultat : ECHEC")

        if self.erreurs:
            lignes.append("")
            lignes.append("Erreurs :")
            for erreur in self.erreurs:
                lignes.append(f"   [ERR] {erreur}")

        if self.avertissements:
            lignes.append("")
            lignes.append("Avertissements :")
            for avertissement in self.avertissements:
                lignes.append(f"   [WARN] {avertissement}")

        return "\n".join(lignes)


# ─────────────────────────────────────────────────────────────
# GitHub : télécharger le HTML
# ─────────────────────────────────────────────────────────────

def telecharger_html_github(ticket_id: str) -> str | None:
    """
    Télécharge le fichier HTML généré depuis GitHub.
    Chemin attendu : tickets/SCRUM-X/index.html
    """
    chemin = f"tickets/{ticket_id}/index.html"
    log.info(f"Téléchargement du HTML depuis GitHub : {chemin}")
    html = telecharger_fichier(chemin)
    if html:
        log.info(f"HTML téléchargé : {len(html)} caractères")
    else:
        log.error(f"Impossible de télécharger {chemin} depuis GitHub")
    return html


# ─────────────────────────────────────────────────────────────
# Test 1 : structure HTML statique
# ─────────────────────────────────────────────────────────────

def tester_structure_html(html: str, resultat: ResultatTest) -> None:
    """
    Vérifie la structure HTML minimale.
    """
    log.info("Test 1 : validation de la structure HTML")

    html_min = html.lower()

    balises_obligatoires = [
        ("<!doctype", "DOCTYPE manquant"),
        ("<html", "balise <html> manquante"),
        ("<head", "balise <head> manquante"),
        ("<body", "balise <body> manquante"),
        ("</html>", "balise </html> manquante"),
    ]

    for balise, message in balises_obligatoires:
        if balise not in html_min:
            resultat.ajouter_erreur(f"Structure HTML : {message}")

    if "<title" not in html_min:
        resultat.ajouter_avertissement("Balise <title> absente")

    recherche_body = re.search(
        r"<body[^>]*>(.*?)(?:</body\s*>|</html\s*>|$)",
        html,
        re.DOTALL | re.IGNORECASE,
    )

    if not recherche_body:
        resultat.ajouter_erreur("Impossible d'extraire le contenu du <body>")
    else:
        contenu_body = recherche_body.group(1).strip()
        contenu_body = re.sub(
            r"</html\s*>\s*$", "", contenu_body, flags=re.IGNORECASE
        ).strip()
        if len(contenu_body) < 20:
            resultat.ajouter_erreur("Le <body> semble vide ou trop court")

    if resultat.succes:
        log.info("   [OK] Structure HTML valide")
    else:
        log.error("   [ERR] Structure HTML invalide")


# ─────────────────────────────────────────────────────────────
# Test 2 : éléments attendus selon le type de page
# ─────────────────────────────────────────────────────────────

def tester_elements_metier(html: str, titre: str, resultat: ResultatTest) -> None:
    """
    Vérifie des éléments attendus selon le ticket.
    """
    log.info("Test 2 : vérification des éléments métier")

    titre_normalise = normaliser_texte(titre)
    html_min = html.lower()

    if "login" in titre_normalise or "connexion" in titre_normalise:
        if 'type="email"' not in html_min and "email" not in html_min:
            resultat.ajouter_erreur("Login : champ email introuvable")
        if 'type="password"' not in html_min and "password" not in html_min:
            resultat.ajouter_erreur("Login : champ password introuvable")
        if "<button" not in html_min:
            resultat.ajouter_erreur("Login : bouton de soumission introuvable")

    elif "calculator" in titre_normalise or "calculatrice" in titre_normalise:
        mots_attendus = ["add", "subtract", "multiply", "divide", "addition", "soustraction", "multiplication", "division"]
        trouves = [mot for mot in mots_attendus if mot in html_min]
        if len(trouves) < 2:
            resultat.ajouter_avertissement(
                "Calculator : peu d'actions calcul trouvées (add/sub/mul/div)"
            )
        if "<button" not in html_min:
            resultat.ajouter_erreur("Calculator : aucun bouton détecté")

    elif "contact" in titre_normalise:
        if "name" not in html_min:
            resultat.ajouter_erreur("Contact : champ name introuvable")
        if "email" not in html_min:
            resultat.ajouter_erreur("Contact : champ email introuvable")
        if "<textarea" not in html_min and "message" not in html_min:
            resultat.ajouter_erreur("Contact : champ message introuvable")

    elif "dashboard" in titre_normalise or "tableau de bord" in titre_normalise:
        mots_attendus = ["dashboard", "chart", "statistics", "analytics", "données", "graphique"]
        trouves = [mot for mot in mots_attendus if mot in html_min]
        if len(trouves) < 1:
            resultat.ajouter_avertissement(
                "Dashboard : aucun indice dashboard/chart/statistics détecté"
            )

    elif "login" not in titre_normalise and "connexion" not in titre_normalise:
        # Vérification générique : la page doit au moins avoir du contenu
        if len(html_min.strip()) < 200:
            resultat.ajouter_avertissement(
                f"Ticket '{titre}' : aucun test métier spécifique défini, "
                f"vérification générique uniquement"
            )

    if resultat.succes:
        log.info("   [OK] Elements metier verifies")


# ─────────────────────────────────────────────────────────────
# Test 3 : Playwright / Chromium
# ─────────────────────────────────────────────────────────────

def tester_avec_playwright(
    html: str,
    ticket_id: str,
    resultat: ResultatTest,
) -> dict:
    """
    Ouvre le HTML dans Chromium avec Playwright.
    Vérifie :
    - chargement de page
    - contenu visible
    - erreurs JavaScript
    - erreurs console
    - screenshot
    """
    log.info("Test 3 : ouverture dans Chromium avec Playwright")

    playwright_metrics = {
        "loaded": False,
        "text_length": 0,
        "js_errors": 0,
        "console_errors": 0,
        "load_time_ms": 0.0,
    }

    chemin_temp = Path(f"temp_{ticket_id}.html").resolve()
    dossier_screenshots = Path("screenshots")
    chemin_screenshot = dossier_screenshots / f"{ticket_id}.png"

    erreurs_js = []
    erreurs_console = []
    requetes_echouees = []

    try:
        chemin_temp.write_text(html, encoding="utf-8")
        dossier_screenshots.mkdir(exist_ok=True)

        with sync_playwright() as playwright:
            with playwright.chromium.launch(headless=True) as navigateur:
                page = navigateur.new_page(viewport={"width": 1366, "height": 768})

                page.on("pageerror", lambda erreur: erreurs_js.append(str(erreur)))

                page.on(
                    "console",
                    lambda message: erreurs_console.append(message.text)
                    if message.type == "error"
                    else None,
                )

                page.on(
                    "requestfailed",
                    lambda requete: requetes_echouees.append(requete.url),
                )

                t_start = time.time()
                page.goto(chemin_temp.as_uri(), wait_until="load", timeout=15000)

                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightError:
                    resultat.ajouter_avertissement(
                        "Networkidle non atteint dans le délai prévu"
                    )

                playwright_metrics["load_time_ms"] = (time.time() - t_start) * 1000.0
                playwright_metrics["loaded"] = True

                texte_visible = page.inner_text("body")

                if len(texte_visible.strip()) < 5:
                    resultat.ajouter_erreur("La page semble vide dans Chromium")
                else:
                    log.info(
                        f"   [OK] Page chargee : {len(texte_visible)} caracteres visibles"
                    )

                playwright_metrics["text_length"] = len(texte_visible.strip())

                if erreurs_js:
                    for erreur in erreurs_js:
                        resultat.ajouter_erreur(f"Erreur JavaScript : {erreur}")
                else:
                    log.info("   [OK] Aucune erreur JavaScript detectee")

                playwright_metrics["js_errors"] = len(erreurs_js)

                if erreurs_console:
                    for erreur in erreurs_console[:5]:
                        resultat.ajouter_avertissement(
                            f"Erreur console navigateur : {erreur}"
                        )

                playwright_metrics["console_errors"] = len(erreurs_console)

                if requetes_echouees:
                    for url in requetes_echouees[:5]:
                        resultat.ajouter_avertissement(
                            f"Requête échouée : {url}"
                        )

                page.screenshot(path=str(chemin_screenshot), full_page=True)
                log.info(f"   [SCREENSHOT] {chemin_screenshot}")

    except PlaywrightError as erreur:
        resultat.ajouter_erreur(f"Erreur Playwright : {erreur}")

    except Exception as erreur:
        resultat.ajouter_erreur(f"Erreur inattendue Playwright : {erreur}")

    finally:
        if chemin_temp.exists():
            chemin_temp.unlink()

    return playwright_metrics


# ─────────────────────────────────────────────────────────────
# Pipeline de test
# ─────────────────────────────────────────────────────────────

def tester_ticket(ticket: dict) -> None:
    """
    Pipeline complet de test pour un ticket.
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
        playwright_metrics = tester_avec_playwright(html, ticket_id, resultat)

        if enregistrer_features_ml:
            try:
                enregistrer_features_ml(
                    ticket=ticket,
                    html=html,
                    playwright_metrics=playwright_metrics,
                    test_passed=resultat.succes,
                    retry_number=ticket.get("retry_number", 0),
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
        if changer_status(ticket_id, JIRA_DONE_STATUS):
            log.info(f"[OK] {ticket_id} -> {JIRA_DONE_STATUS}")
        else:
            log.warning(f"Impossible de passer {ticket_id} a {JIRA_DONE_STATUS}")
    else:
        commenter_jira(
            ticket_id,
            "Tests automatiques echoues.\n\n" + rapport,
        )
        if changer_status(ticket_id, JIRA_REOPEN_STATUS):
            log.info(f"[RETRY] {ticket_id} -> {JIRA_REOPEN_STATUS}")
        else:
            log.warning(f"Impossible de retourner {ticket_id} a {JIRA_REOPEN_STATUS}")


# ─────────────────────────────────────────────────────────────
# Programme principal
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """
    Point d'entrée du Testing Agent.
    """
    print("=" * 60)
    print("  [TEST] Testing Agent -- Validation automatique du code")
    print("=" * 60)

    from config.jira_config import verifier_configuration
    verifier_configuration()

    tickets = lire_tickets_in_review()

    if not tickets:
        print("[OK] Aucun ticket en revision. Rien a tester.")
        return

    for ticket in tickets:
        tester_ticket(ticket)

    print()
    print("=" * 60)
    print("  [OK] Testing Agent termine")
    print("=" * 60)


if __name__ == "__main__":
    main()
