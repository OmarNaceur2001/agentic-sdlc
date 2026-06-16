"""Code Agent — Semaine 3

Objectif :
- Lire les tickets Jira avec statut "À faire"
- Générer du HTML autonome via Groq/Llama
- Uploader le fichier HTML sur GitHub
- Mettre à jour le statut Jira → "En cours" puis "In Review"
"""

import base64
import html as html_lib
import os
import unicodedata

import requests
from dotenv import load_dotenv
from groq import Groq


load_dotenv()

# ── Configuration ─────────────────────────────────────
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

JIRA_AUTH = (JIRA_EMAIL, JIRA_TOKEN)
JIRA_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

groq_client = Groq(api_key=GROQ_API_KEY)


def normaliser_html_modele(code: str) -> str:
    """
    Normalise un HTML potentiellement échappé par le modèle.

    Objectifs :
    - Supprimer les blocs Markdown éventuels
    - Convertir le HTML échappé en vrai HTML
    - Extraire uniquement le document HTML complet
    - Garantir que les balises principales sont réelles : <html>, <body>, </html>
    """
    if not code:
        return ""

    s = code.strip()

    # 1) Supprimer les blocs Markdown éventuels
    if s.startswith("```"):
        lignes = s.splitlines()

        if lignes and lignes[0].startswith("```"):
            lignes = lignes[1:]

        if lignes and lignes[-1].strip() == "```":
            lignes = lignes[:-1]

        s = "\n".join(lignes).strip()

    # 2) Unescape itératif robuste
    for _ in range(10):
        ancien = s
        s = html_lib.unescape(s)

        if s == ancien:
            break

    # 3) Extraire uniquement le vrai document HTML
    s_lower = s.lower()

    debut = s_lower.find("<!doctype html")
    fin = s_lower.rfind("</html>")

    if debut != -1 and fin != -1:
        s = s[debut:fin + len("</html>")].strip()
    elif debut != -1:
        s = s[debut:].strip()
    elif fin != -1:
        debut_html = s_lower.find("<html")
        if debut_html != -1:
            s = "<!DOCTYPE html>\n" + s[debut_html:fin + len("</html>")].strip()
        else:
            s = "<!DOCTYPE html>\n<html>\n" + s[:fin + len("</html>")].strip()
    else:
        if "<html" not in s_lower:
            s = f"<!DOCTYPE html>\n<html>\n<head>\n<title>Page</title>\n</head>\n<body>\n{s}\n</body>\n</html>"
        elif "<!doctype html" not in s_lower:
            s = "<!DOCTYPE html>\n" + s

    # Rétablir les structures de base si absentes
    s_lower = s.lower()
    if "<html" not in s_lower:
        s = s.replace("<!DOCTYPE html>", "<!DOCTYPE html>\n<html>\n", 1) + "\n</html>"
    if "<head" not in s_lower:
        s = s.replace("<html>", "<html>\n<head>\n<title>Page</title>\n</head>", 1)
    if "<body" not in s_lower:
        s = s.replace("</head>", "</head>\n<body>", 1).replace("</html>", "</body>\n</html>", 1)

    s_lower = s.lower()
    if not s_lower.startswith("<!doctype html"):
        s = "<!DOCTYPE html>\n" + s

    # 4) Vérifications utiles
    if "<body" not in s.lower():
        print("   ⚠️ Attention : aucune vraie balise <body> détectée après normalisation")

    if "&lt;" in s or "&gt;" in s or "&amp;lt;" in s or "&amp;gt;" in s:
        print("   ⚠️ Attention : le HTML contient encore des entités échappées")

    return s.strip()

def lire_tickets_todo() -> list:
    """Lit les tickets Jira avec statusCategory = To Do."""

    print("🔍 Recherche des tickets 'À faire'...\n")

    jql = (
        f'project = "{JIRA_PROJECT_KEY}" '
        f'AND statusCategory = "To Do" '
        f"ORDER BY created ASC"
    )

    params = {
        "jql": jql,
        "fields": "summary,description,status",
        "maxResults": 10,
    }

    reponse = requests.get(
        f"{JIRA_URL}/rest/api/3/search/jql",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        params=params,
        timeout=20,
    )

    if reponse.status_code != 200:
        print(f"❌ Erreur Jira: {reponse.status_code}")
        return []

    tickets = reponse.json().get("issues", [])
    print(f"📋 {len(tickets)} ticket(s) trouvé(s)\n")
    return tickets


def extraire_description(description_adf: dict | None) -> str:
    """Extrait le texte brut depuis le format ADF de Jira."""

    if not description_adf:
        return ""

    texte: list[str] = []

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


def normaliser_texte(texte: str) -> str:
    """Normalise un texte en retirant les accents et en le passant en minuscules."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )
    return texte

def changer_status(ticket_id: str, status_cible: str) -> bool:
    """Change le statut d'un ticket Jira en comparant statut de destination et nom de transition."""

    reponse = requests.get(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        timeout=20,
    )

    if reponse.status_code != 200:
        return False

    transitions = reponse.json().get("transitions", [])

    transition_id = None
    cible = normaliser_texte(status_cible)

    for t in transitions:
        destination = normaliser_texte(t.get("to", {}).get("name", ""))
        action = normaliser_texte(t.get("name", ""))
        if cible == destination or cible == action or cible in action:
            transition_id = t.get("id")
            break

    if not transition_id:
        # Fallback simple
        cible_simple = status_cible.lower().strip()
        for t in transitions:
            destination_simple = t.get("to", {}).get("name", "").lower().strip()
            action_simple = t.get("name", "").lower().strip()
            if cible_simple == destination_simple or cible_simple == action_simple or cible_simple in action_simple:
                transition_id = t.get("id")
                break

    if not transition_id:
        return False

    reponse = requests.post(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/transitions",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        json={"transition": {"id": transition_id}},
        timeout=20,
    )

    return reponse.status_code == 204


def generer_code_html(titre: str, description: str) -> str:
    """Génère un HTML autonome et directement testable."""

    print("   🤖 Génération du code avec Llama...")

    prompt = f"""Tu es un développeur front-end senior.

Crée une page HTML complète, valide, autonome et fonctionnelle basée sur ce ticket Jira.

Titre : {titre}
Description : {description}

Règles STRICTES :
1. Réponds uniquement avec du vrai code HTML brut.
2. Le code doit commencer exactement par <!DOCTYPE html>.
3. Le code doit terminer exactement par </html>.
4. N'utilise jamais Markdown.
5. N'utilise jamais de backticks.
6. CRITIQUE : N'utilise jamais de HTML échappé. N'utilise pas d'entités comme &lt;, &gt;, &amp;lt;, &amp;gt;. Écris du vrai HTML avec les caractères `<` et `>` (ex: <html>, <body>, <head>, </html>).
7. Interdit d'écrire des entités comme &lt;html&gt;, &lt;body&gt;, &lt;style&gt;, &lt;script&gt;.
8. Utilise les vraies balises HTML : <html>, <head>, <body>, <style>, <script>.
9. Tout doit être dans un seul fichier HTML autonome.
10. Le CSS doit être dans <style>.
11. Le JavaScript doit être dans <script>.
12. N'utilise aucune bibliothèque externe.
13. N'utilise aucun CDN.
14. N'utilise pas Chart.js.
15. N'utilise pas React, Vue, Bootstrap ou Tailwind.
16. Si tu dois créer des graphiques, utilise HTML/CSS/SVG ou canvas natif uniquement.
17. Le <body> doit contenir du contenu visible et utile.
18. Le JavaScript ne doit produire aucune erreur dans le navigateur.
19. Les formulaires sont uniquement des démonstrations front-end.
20. Ajoute des boutons visibles si la page est interactive.

Aucune explication, aucun commentaire en dehors du HTML.
"""

    reponse = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5000,
        temperature=0.2,
    )

    code = reponse.choices[0].message.content.strip()

    # Anti-Markdown (si le modèle ajoute des clôtures)
    if code.startswith("```"):
        lignes = code.splitlines()
        if lignes and lignes[0].startswith("```"):
            lignes = lignes[1:]
        if lignes and lignes[-1].strip() == "```":
            lignes = lignes[:-1]
        code = "\n".join(lignes).strip()

    return normaliser_html_modele(code)


def uploader_sur_github(ticket_id: str, titre: str, code_html: str) -> str | None:
    """Upload un fichier HTML sur GitHub via l'API."""

    nom_fichier = f"tickets/{ticket_id}/index.html"
    print(f"   📤 Upload sur GitHub → {nom_fichier}")

    contenu_base64 = base64.b64encode(code_html.encode("utf-8")).decode("utf-8")

    sha_existant = None
    verification = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{nom_fichier}",
        headers=GITHUB_HEADERS,
        timeout=20,
    )
    if verification.status_code == 200:
        sha_existant = verification.json().get("sha")

    payload = {
        "message": f"feat({ticket_id}): génération automatique — {titre}",
        "content": contenu_base64,
    }
    if sha_existant:
        payload["sha"] = sha_existant

    reponse = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{nom_fichier}",
        headers=GITHUB_HEADERS,
        json=payload,
        timeout=30,
    )

    if reponse.status_code in (200, 201):
        return reponse.json().get("content", {}).get("html_url")

    print(f"   ❌ Échec upload GitHub: {reponse.status_code}")
    print(f"   Détail: {reponse.text[:300]}")
    return None


def ajouter_commentaire_jira(ticket_id: str, url_github: str) -> None:
    """Ajoute un commentaire dans le ticket Jira avec le lien GitHub."""

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
                            "text": (
                                "✅ Code généré automatiquement par le Code Agent.\n"
                                f"🔗 Fichier GitHub : {url_github}"
                            ),
                        }
                    ],
                }
            ],
        }
    }

    requests.post(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/comment",
        auth=JIRA_AUTH,
        headers=JIRA_HEADERS,
        json=payload,
        timeout=20,
    )


def traiter_ticket(ticket: dict) -> None:
    """Traite un ticket complet : génération + upload + mise à jour Jira."""

    ticket_id = ticket["key"]
    champs = ticket["fields"]
    titre = champs.get("summary", "")
    description = extraire_description(champs.get("description"))

    print(f"┌─ Ticket : {ticket_id}")
    print(f"│  Titre  : {titre}")
    print(f"│  Desc   : {description[:80]}...")
    print(f"└{'─' * 60}")

    print("   ⏳ Status → 'En cours'...")
    if changer_status(ticket_id, "En cours"):
        print("   ✅ Status mis à jour (En cours)")
    else:
        print("   ⚠️  Impossible de passer à 'En cours'")

    code_html = generer_code_html(titre, description)
    print(f"   ✅ Code généré ({len(code_html)} caractères)")

    url_github = uploader_sur_github(ticket_id, titre, code_html)
    if not url_github:
        print(f"   ❌ Échec — ticket {ticket_id} non traité\n")
        return

    ajouter_commentaire_jira(ticket_id, url_github)
    print("   💬 Commentaire ajouté dans Jira")

    review_status = os.getenv("JIRA_REVIEW_STATUS", "In Review")
    print(f"   ⏳ Status → '{review_status}'...")
    if changer_status(ticket_id, review_status):
        print("   ✅ Status mis à jour")
    else:
        print(f"   ⚠️  Impossible de changer vers '{review_status}'")

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