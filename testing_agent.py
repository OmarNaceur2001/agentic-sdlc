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

import base64
import os
import re
import unicodedata
import logging
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Error as PlaywrightError

try:
    from feature_extractor import enregistrer_features_ml
except Exception:
    enregistrer_features_ml = None


# Charger les variables depuis .env
load_dotenv()


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SCRUM")

JIRA_REVIEW_STATUS = os.getenv("JIRA_REVIEW_STATUS", "Revue en cours")
JIRA_DONE_STATUS = os.getenv("JIRA_DONE_STATUS", "Terminé(e)")
JIRA_REOPEN_STATUS = os.getenv("JIRA_REOPEN_STATUS", "À faire")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

JIRA_AUTH = (JIRA_EMAIL, JIRA_TOKEN)

JIRA_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


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
            lignes.append("✅ Résultat : SUCCÈS")
        else:
            lignes.append("❌ Résultat : ÉCHEC")

        if self.erreurs:
            lignes.append("")
            lignes.append("Erreurs :")
            for erreur in self.erreurs:
                lignes.append(f"  ❌ {erreur}")

        if self.avertissements:
            lignes.append("")
            lignes.append("Avertissements :")
            for avertissement in self.avertissements:
                lignes.append(f"  ⚠️ {avertissement}")

        return "\n".join(lignes)


# ─────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────

def verifier_configuration() -> None:
    """
    Vérifie que les variables nécessaires existent.
    """
    variables = {
        "JIRA_URL": JIRA_URL,
        "JIRA_EMAIL": JIRA_EMAIL,
        "JIRA_TOKEN": JIRA_TOKEN,
        "JIRA_PROJECT_KEY": JIRA_PROJECT_KEY,
        "GITHUB_TOKEN": GITHUB_TOKEN,
        "GITHUB_REPO": GITHUB_REPO,
    }

    manquantes = [nom for nom, valeur in variables.items() if not valeur]

    if manquantes:
        print("❌ Configuration incomplète dans .env")
        for variable in manquantes:
            print(f"   - {variable}")
        raise SystemExit(1)


def normaliser_texte(texte: str) -> str:
    """
    Normalise un texte pour comparer les statuts Jira.

    Exemple :
    - "À faire" -> "a faire"
    - "Terminé(e)" -> "termine(e)"
    """
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )
    return texte


def creer_document_adf(texte: str) -> dict:
    """
    Convertit un texte multi-lignes en document ADF Jira.
    """
    paragraphes = []

    for ligne in texte.splitlines():
        paragraphes.append(
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": ligne if ligne else " ",
                    }
                ],
            }
        )

    return {
        "type": "doc",
        "version": 1,
        "content": paragraphes,
    }


# ─────────────────────────────────────────────────────────────
# GitHub : télécharger le HTML
# ─────────────────────────────────────────────────────────────

def telecharger_html_github(ticket_id: str) -> str | None:
    """
    Télécharge le fichier HTML généré depuis GitHub.

    Chemin attendu :
    tickets/SCRUM-X/index.html
    """
    chemin = f"tickets/{ticket_id}/index.html"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{chemin}"

    log.info(f"Téléchargement du HTML depuis GitHub : {chemin}")

    try:
        reponse = requests.get(
            url,
            headers=GITHUB_HEADERS,
            timeout=20,
        )

        if reponse.status_code != 200:
            log.error(f"GitHub erreur {reponse.status_code} pour {chemin}")
            log.error(reponse.text[:300])
            return None

        contenu_b64 = reponse.json().get("content", "")
        contenu_b64 = contenu_b64.replace("\n", "")

        html = base64.b64decode(contenu_b64).decode("utf-8")

        log.info(f"HTML téléchargé : {len(html)} caractères")
        return html

    except Exception as erreur:
        log.error(f"Erreur téléchargement GitHub : {erreur}")
        return None


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
        
        contenu_body = re.sub(r"</html\s*>\s*$", "", contenu_body, flags=re.IGNORECASE).strip()
        
        if len(contenu_body) < 20:
            resultat.ajouter_erreur("Le <body> semble vide ou trop court")
            
    if resultat.succes:
        log.info("   ✅ Structure HTML valide")
    else:
        log.error("   ❌ Structure HTML invalide")


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

    if "login" in titre_normalise:
        if 'type="email"' not in html_min and "email" not in html_min:
            resultat.ajouter_erreur("Login : champ email introuvable")

        if 'type="password"' not in html_min and "password" not in html_min:
            resultat.ajouter_erreur("Login : champ password introuvable")

        if "<button" not in html_min:
            resultat.ajouter_erreur("Login : bouton de soumission introuvable")

    elif "calculator" in titre_normalise:
        mots_attendus = ["add", "subtract", "multiply", "divide"]

        for mot in mots_attendus:
            if mot not in html_min:
                resultat.ajouter_avertissement(
                    f"Calculator : mot ou action '{mot}' non détecté"
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

    elif "dashboard" in titre_normalise:
        mots_attendus = ["dashboard", "chart", "statistics", "analytics"]

        trouves = [mot for mot in mots_attendus if mot in html_min]

        if len(trouves) < 2:
            resultat.ajouter_avertissement(
                "Dashboard : peu d'indices dashboard/chart/statistics détectés"
            )

    else:
        resultat.ajouter_avertissement(
            "Aucun test métier spécifique défini pour ce type de ticket"
        )

    if resultat.succes:
        log.info("   ✅ Éléments métier vérifiés")


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
    import time
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
            navigateur = playwright.chromium.launch(headless=True)
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
                    f"   ✅ Page chargée : {len(texte_visible)} caractères visibles"
                )

            playwright_metrics["text_length"] = len(texte_visible.strip())

            if erreurs_js:
                for erreur in erreurs_js:
                    resultat.ajouter_erreur(f"Erreur JavaScript : {erreur}")
            else:
                log.info("   ✅ Aucune erreur JavaScript détectée")

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
            log.info(f"   📸 Screenshot : {chemin_screenshot}")

            navigateur.close()

    except PlaywrightError as erreur:
        resultat.ajouter_erreur(f"Erreur Playwright : {erreur}")

    except Exception as erreur:
        resultat.ajouter_erreur(f"Erreur inattendue Playwright : {erreur}")

    finally:
        if chemin_temp.exists():
            chemin_temp.unlink()

    return playwright_metrics


# ─────────────────────────────────────────────────────────────
# Jira : lire tickets en review
# ─────────────────────────────────────────────────────────────

def lire_tickets_in_review() -> list:
    """
    Récupère les tickets en statut de revue.

    Par défaut :
    JIRA_REVIEW_STATUS=Revue en cours
    """
    log.info(f"Recherche des tickets '{JIRA_REVIEW_STATUS}'")

    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND status = "{JIRA_REVIEW_STATUS}" '
        f'ORDER BY updated ASC'
    )

    params = {
        "jql": jql,
        "fields": "summary,status",
        "maxResults": 20,
    }

    try:
        reponse = requests.get(
            f"{JIRA_URL}/rest/api/3/search/jql",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            params=params,
            timeout=20,
        )

        if reponse.status_code != 200:
            log.error(f"Erreur Jira : {reponse.status_code}")
            log.error(reponse.text[:300])
            return []

        tickets = reponse.json().get("issues", [])
        log.info(f"{len(tickets)} ticket(s) en révision")
        return tickets

    except Exception as erreur:
        log.error(f"Erreur réseau Jira : {erreur}")
        return []


# ─────────────────────────────────────────────────────────────
# Jira : transitions
# ─────────────────────────────────────────────────────────────

def obtenir_transitions(ticket_id: str) -> list[dict]:
    """
    Récupère les transitions disponibles pour un ticket Jira.
    """
    try:
        reponse = requests.get(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            timeout=20,
        )

        if reponse.status_code != 200:
            log.error(f"Impossible de lire les transitions : {ticket_id}")
            log.error(reponse.text[:300])
            return []

        return reponse.json().get("transitions", [])

    except Exception as erreur:
        log.error(f"Erreur transition Jira : {erreur}")
        return []


def changer_status_jira(ticket_id: str, status_cible: str) -> bool:
    """
    Change le statut Jira via une transition.
    """
    transitions = obtenir_transitions(ticket_id)

    cible = normaliser_texte(status_cible)

    transition_id = None

    for transition in transitions:
        destination = normaliser_texte(
            transition.get("to", {}).get("name", "")
        )

        action = normaliser_texte(
            transition.get("name", "")
        )

        if cible == destination or cible == action or cible in action:
            transition_id = transition.get("id")
            break

    if not transition_id:
        disponibles = [
            transition.get("to", {}).get("name", "")
            for transition in transitions
        ]
        log.warning(
            f"Status '{status_cible}' introuvable. Disponibles : {disponibles}"
        )
        return False

    try:
        reponse = requests.post(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            json={"transition": {"id": transition_id}},
            timeout=20,
        )

        return reponse.status_code == 204

    except Exception as erreur:
        log.error(f"Erreur changement statut Jira : {erreur}")
        return False


# ─────────────────────────────────────────────────────────────
# Jira : commentaire
# ─────────────────────────────────────────────────────────────

def commenter_jira(ticket_id: str, texte: str) -> bool:
    """
    Ajoute un commentaire Jira avec un document ADF.
    """
    payload = {
        "body": creer_document_adf(texte)
    }

    try:
        reponse = requests.post(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/comment",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            json=payload,
            timeout=20,
        )

        if reponse.status_code in (200, 201):
            log.info(f"Commentaire ajouté dans Jira : {ticket_id}")
            return True

        log.warning(f"Commentaire Jira non ajouté : {reponse.status_code}")
        log.warning(reponse.text[:300])
        return False

    except Exception as erreur:
        log.error(f"Erreur commentaire Jira : {erreur}")
        return False


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
            "✅ Tests automatiques réussis.\n\n" + rapport,
        )

        if changer_status_jira(ticket_id, JIRA_DONE_STATUS):
            log.info(f"✅ {ticket_id} → {JIRA_DONE_STATUS}")
        else:
            log.warning(f"Impossible de passer {ticket_id} à {JIRA_DONE_STATUS}")

    else:
        commenter_jira(
            ticket_id,
            "❌ Tests automatiques échoués.\n\n" + rapport,
        )

        if changer_status_jira(ticket_id, JIRA_REOPEN_STATUS):
            log.info(f"🔄 {ticket_id} → {JIRA_REOPEN_STATUS}")
        else:
            log.warning(f"Impossible de retourner {ticket_id} à {JIRA_REOPEN_STATUS}")


# ─────────────────────────────────────────────────────────────
# Programme principal
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """
    Point d'entrée du Testing Agent.
    """
    print("=" * 60)
    print("  🧪 Testing Agent — Validation automatique du code")
    print("=" * 60)

    verifier_configuration()

    tickets = lire_tickets_in_review()

    if not tickets:
        print("✅ Aucun ticket en révision. Rien à tester.")
        return

    for ticket in tickets:
        tester_ticket(ticket)

    print()
    print("=" * 60)
    print("  ✅ Testing Agent terminé")
    print("=" * 60)


if __name__ == "__main__":
    main()