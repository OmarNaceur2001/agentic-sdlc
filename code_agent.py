"""
Code Agent — Semaine 3

Objectif :
- Lire les tickets Jira avec statut "À faire"
- Générer du code HTML/CSS/JS avec Groq (Llama)
- Uploader le code généré sur GitHub
- Mettre à jour le statut Jira → "En cours" puis "In Review"
"""

import os
import sys
import base64
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ── Configuration ─────────────────────────────────────
JIRA_URL          = os.getenv("JIRA_URL")
JIRA_EMAIL        = os.getenv("JIRA_EMAIL")
JIRA_TOKEN        = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY  = os.getenv("JIRA_PROJECT_KEY")
GITHUB_TOKEN      = os.getenv("GITHUB_TOKEN")
GITHUB_REPO       = os.getenv("GITHUB_REPO")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")

JIRA_AUTH    = (JIRA_EMAIL, JIRA_TOKEN)
JIRA_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

groq_client = Groq(api_key=GROQ_API_KEY)


# ── Jira : lire tickets ────────────────────────────────

def lire_tickets_todo() -> list:
    """
    Lit les tickets Jira avec statusCategory = To Do.
    """
    print("🔍 Recherche des tickets 'À faire'...\n")

    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND statusCategory = "To Do" '
        f'ORDER BY created ASC'
    )

    params = {
        "jql": jql,
        "fields": "summary,description,status",
        "maxResults": 10
    }

    reponse = requests.get(
        f"{JIRA_URL}/rest/api/3/search/jql",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        params=params,
        timeout=20
    )

    if reponse.status_code != 200:
        print(f"❌ Erreur Jira: {reponse.status_code}")
        return []

    tickets = reponse.json().get("issues", [])
    print(f"📋 {len(tickets)} ticket(s) trouvé(s)\n")
    return tickets


def extraire_description(description_adf: dict | None) -> str:
    """
    Extrait le texte brut depuis le format ADF de Jira.
    """
    if not description_adf:
        return ""

    texte = []

    def parcourir(noeud):
        if isinstance(noeud, dict):
            if noeud.get("type") == "text":
                texte.append(noeud.get("text", ""))
            for valeur in noeud.values():
                parcourir(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                parcourir(element)

    parcourir(description_adf)
    return " ".join(texte).strip()


# ── Jira : changer status ──────────────────────────────

def changer_status(ticket_id: str, status_cible: str) -> bool:
    """
    Change le statut d'un ticket Jira.
    """
    # 1) récupérer les transitions disponibles
    reponse = requests.get(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        timeout=20
    )

    if reponse.status_code != 200:
        return False

    transitions = reponse.json().get("transitions", [])

    # 2) trouver la bonne transition
    transition_id = None
    for t in transitions:
        destination = t.get("to", {}).get("name", "").lower().strip()
        if status_cible.lower().strip() == destination:
            transition_id = t["id"]
            break

    if not transition_id:
        noms = [t.get("to", {}).get("name", "") for t in transitions]
        print(f"   ⚠️  Status '{status_cible}' introuvable. Disponibles: {noms}")
        return False

    # 3) appliquer la transition
    reponse = requests.post(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        json={"transition": {"id": transition_id}},
        timeout=20
    )

    return reponse.status_code == 204


# ── Groq : générer le code ─────────────────────────────

def generer_code_html(titre: str, description: str) -> str:
    """
    Envoie le titre et la description à Groq (Llama).
    Reçoit en retour une page HTML complète et fonctionnelle.
    """
    print(f"   🤖 Génération du code avec Llama...")

    prompt = f"""Tu es un développeur web expert.

Crée une page HTML complète et fonctionnelle basée sur ces informations :

Titre : {titre}
Description : {description}

Règles STRICTES :
1. Réponds UNIQUEMENT avec le code HTML — rien d'autre
2. Pas d'explication, pas de commentaire en dehors du code
3. Tout doit être dans un seul fichier HTML (CSS dans <style>, JS dans <script>)
4. Design moderne avec fond sombre (#1a1a2e), couleurs vives
5. Le code doit être complet et fonctionnel immédiatement
6. Commence par <!DOCTYPE html> et termine par </html>
"""

    reponse = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.3   # moins de créativité = plus de code stable
    )

    code = reponse.choices[0].message.content.strip()

    # nettoyer si Llama ajoute des backticks markdown
    if code.startswith("```"):
        lignes = code.split("\n")
        # supprimer première ligne (```html) et dernière (```)
        code = "\n".join(lignes[1:-1])

    return code


# ── GitHub : uploader le fichier ──────────────────────

def uploader_sur_github(ticket_id: str, titre: str, code_html: str) -> str | None:
    """
    Upload un fichier HTML sur GitHub via l'API.
    Retourne l'URL du fichier si succès, None sinon.
    """
    # nom du fichier basé sur l'ID du ticket
    nom_fichier = f"tickets/{ticket_id}/index.html"

    print(f"   📤 Upload sur GitHub → {nom_fichier}")

    # GitHub API demande le contenu en base64
    contenu_base64 = base64.b64encode(code_html.encode("utf-8")).decode("utf-8")

    # vérifier si le fichier existe déjà (pour obtenir son SHA)
    sha_existant = None
    verification = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{nom_fichier}",
        headers=GITHUB_HEADERS,
        timeout=20
    )
    if verification.status_code == 200:
        sha_existant = verification.json().get("sha")

    # préparer le payload
    payload = {
        "message": f"feat({ticket_id}): génération automatique — {titre}",
        "content": contenu_base64,
    }

    # si le fichier existe déjà, on doit inclure son SHA pour le mettre à jour
    if sha_existant:
        payload["sha"] = sha_existant

    # envoyer la requête
    reponse = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{nom_fichier}",
        headers=GITHUB_HEADERS,
        json=payload,
        timeout=30
    )

    if reponse.status_code in (200, 201):
        url = reponse.json().get("content", {}).get("html_url", "")
        print(f"   ✅ Fichier uploadé : {url}")
        return url
    else:
        print(f"   ❌ Échec upload GitHub: {reponse.status_code}")
        print(f"   Détail: {reponse.text[:300]}")
        return None


# ── Jira : ajouter un commentaire ─────────────────────

def ajouter_commentaire_jira(ticket_id: str, url_github: str) -> None:
    """
    Ajoute un commentaire dans le ticket Jira avec le lien GitHub.
    """
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": f"✅ Code généré automatiquement par le Code Agent.\n🔗 Fichier GitHub : {url_github}"
                        }
                    ]
                }
            ]
        }
    }

    requests.post(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/comment",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        json=payload,
        timeout=20
    )


# ── Programme principal ────────────────────────────────

def traiter_ticket(ticket: dict) -> None:
    """
    Traite un ticket complet : génération + upload + mise à jour Jira.
    """
    ticket_id   = ticket["key"]
    champs      = ticket["fields"]
    titre       = champs.get("summary", "")
    description = extraire_description(champs.get("description"))

    print(f"┌─ Ticket : {ticket_id}")
    print(f"│  Titre  : {titre}")
    print(f"│  Desc   : {description[:80]}...")
    print(f"└{'─' * 60}")

    # Étape 1 : changer status → En cours
    print(f"   ⏳ Status → 'En cours'...")
    if changer_status(ticket_id, "En cours"):
        print(f"   ✅ Status mis à jour")
    else:
        print(f"   ⚠️  Impossible de changer le status")

    # Étape 2 : générer le code HTML
    code_html = generer_code_html(titre, description)
    print(f"   ✅ Code généré ({len(code_html)} caractères)")

    # Étape 3 : uploader sur GitHub
    url_github = uploader_sur_github(ticket_id, titre, code_html)

    if not url_github:
        print(f"   ❌ Échec — ticket {ticket_id} non traité\n")
        return

    # Étape 4 : ajouter commentaire dans Jira
    ajouter_commentaire_jira(ticket_id, url_github)
    print(f"   💬 Commentaire ajouté dans Jira")

    # Étape 5 : changer status → In Review
    print(f"   ⏳ Status → 'In Review'...")
    if changer_status(ticket_id, os.getenv("JIRA_REVIEW_STATUS", "Revue en cours")):
        print(f"   ✅ Status mis à jour")
    else:
        print(f"   ⚠️  Impossible de changer vers 'In Review'")

    print()


def main() -> None:
    print("=" * 65)
    print("  🤖 Code Agent — Génération automatique de code")
    print("=" * 65)
    print()

    tickets = lire_tickets_todo()

    if not tickets:
        print("✅ Aucun ticket 'À faire'. Rien à traiter.")
        return

    for ticket in tickets:
        traiter_ticket(ticket)

    print("=" * 65)
    print("  ✅ Code Agent terminé")
    print("=" * 65)


if __name__ == "__main__":
    main()