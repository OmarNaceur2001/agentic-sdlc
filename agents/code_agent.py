"""
Code Agent — Semaine 3

Objectif :
- Lire les tickets Jira avec statut "À faire"
- Générer du HTML autonome via Groq/Llama
- Uploader le fichier HTML sur GitHub
- Mettre à jour le statut Jira → "En cours" puis "In Review"
"""

import html as html_lib
import os
import unicodedata

from dotenv import load_dotenv
from groq import Groq

from config.jira_config import (
    JIRA_PROGRESS_STATUS,
    JIRA_REVIEW_STATUS,
    commenter_jira,
    changer_status,
    extraire_texte_adf,
    normaliser_texte,
)
from config.github_config import uploader_fichier, GITHUB_REPO

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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
        s = s[debut : fin + len("</html>")].strip()
    elif debut != -1:
        s = s[debut:].strip()
    elif fin != -1:
        debut_html = s_lower.find("<html")
        if debut_html != -1:
            s = "<!DOCTYPE html>\n" + s[debut_html : fin + len("</html>")].strip()
        else:
            s = "<!DOCTYPE html>\n<html>\n" + s[: fin + len("</html>")].strip()
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
        s = s.replace("</head>", "</head>\n<body>", 1).replace(
            "</html>", "</body>\n</html>", 1
        )

    s_lower = s.lower()
    if not s_lower.startswith("<!doctype html"):
        s = "<!DOCTYPE html>\n" + s

    # 4) Vérifications utiles
    if "<body" not in s.lower():
        print("   [WARN] Attention : aucune vraie balise <body> detectee apres normalisation")

    if "&lt;" in s or "&gt;" in s or "&amp;lt;" in s or "&amp;gt;" in s:
        print("   [WARN] Attention : le HTML contient encore des entites echapees")

    return s.strip()


def extraire_description(description_adf: dict | None) -> str:
    """Extrait le texte brut depuis le format ADF de Jira."""
    if not description_adf:
        return ""
    return extraire_texte_adf(description_adf)


def generer_code_html(titre: str, description: str) -> str:
    """Génère un HTML autonome et directement testable."""
    print("   [AI] Generation du code avec Llama...")

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
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
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


def ajouter_commentaire_jira(ticket_id: str, url_github: str) -> None:
    """Ajoute un commentaire dans le ticket Jira avec le lien GitHub."""
    from config.jira_config import JIRA_URL, JIRA_AUTH, JIRA_HEADERS
    import requests

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
                                "Code genere automatiquement par le Code Agent.\n"
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


def traiter_ticket(ticket: dict) -> bool:
    """Traite un ticket complet : génération + upload + mise à jour Jira.

    Retourne True si le traitement est complet (génération + upload + transition 'In Review'),
    False dans tous les cas d'échec (avec rollback du statut vers 'À faire' si nécessaire).
    """
    ticket_id = ticket["key"]
    champs = ticket["fields"]
    titre = champs.get("summary", "")
    description = extraire_description(champs.get("description"))

    print(f"┌─ Ticket : {ticket_id}")
    print(f"│  Titre  : {titre}")
    print(f"│  Desc   : {description[:80]}...")
    print(f"└{'─' * 60}")

    # ── 1. Transition vers 'En cours' ──────────────────────────────
    print(f"   [..] Status -> '{JIRA_PROGRESS_STATUS}'...")
    if not changer_status(ticket_id, JIRA_PROGRESS_STATUS):
        print(f"   [ERR] Impossible de passer {ticket_id} en '{JIRA_PROGRESS_STATUS}' - ticket ignore ce cycle.")
        return False
    print(f"   [OK] Status mis a jour ({JIRA_PROGRESS_STATUS})")

    # -- 2. Generation LLM --
    code_html = generer_code_html(titre, description)
    print(f"   [OK] Code genere ({len(code_html)} caracteres)")

    # -- 3. Upload GitHub --
    nom_fichier = f"tickets/{ticket_id}/index.html"
    print(f"   [>>] Upload sur GitHub -> {nom_fichier}")
    url_github = uploader_fichier(
        nom_fichier,
        code_html,
        f"feat({ticket_id}): génération automatique — {titre}",
    )
    if not url_github:
        print(f"   [ERR] Echec upload GitHub -- rollback {ticket_id} vers 'A faire'")
        changer_status(ticket_id, "A faire")
        return False

    ajouter_commentaire_jira(ticket_id, url_github)
    print("   [OK] Commentaire ajoute dans Jira")

    # -- Feature 3: Deploy to GitHub Pages (non-blocking) --
    try:
        from agents.deployment_agent import deployer_ticket
        deploy_result = deployer_ticket(ticket_id, titre)
        if deploy_result.get("success"):
            print(f"   [DEPLOY] {ticket_id} -> {deploy_result['url_pages']}")
    except Exception as e:
        print(f"   [WARN] [DEPLOY] Non critique : {e}")

    # -- 4. Transition vers 'In Review' --
    print(f"   [..] Status -> '{JIRA_REVIEW_STATUS}'...")
    if changer_status(ticket_id, JIRA_REVIEW_STATUS):
        print("   [OK] Status mis a jour")
    else:
        print(f"   [ERR] Impossible de passer en '{JIRA_REVIEW_STATUS}' -- rollback vers 'A faire'")
        changer_status(ticket_id, "A faire")
        return False

    print()
    return True


def main() -> None:
    print("=" * 65)
    print("  [AI] Code Agent -- Generation automatique de code")
    print("=" * 65)
    print()

    from config.jira_config import lire_tickets_todo
    tickets = lire_tickets_todo()
    if not tickets:
        print("[OK] Aucun ticket 'A faire'. Rien a traiter.")
        return

    for ticket in tickets:
        traiter_ticket(ticket)

    print("=" * 65)
    print("  [OK] Code Agent termine")
    print("=" * 65)


if __name__ == "__main__":
    main()
