"""
deployment_agent.py — Déploiement automatique sur GitHub Pages
"""

import base64
import logging
from pathlib import Path

from dotenv import load_dotenv

from config.jira_config import (
    JIRA_URL,
    JIRA_AUTH,
    JIRA_HEADERS,
    commenter_jira,
)
from config.github_config import (
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_PAGES_BRANCH,
    _request_with_retry,
)

load_dotenv()

log = logging.getLogger("deployment_agent")


class DeploymentError(Exception):
    pass


def construire_url_pages(ticket_id: str) -> str:
    """Construit l'URL GitHub Pages pour un ticket donné."""
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return ""
    owner, repo = GITHUB_REPO.split("/", 1)
    return f"https://{owner}.github.io/{repo}/tickets/{ticket_id}/"


def pages_deja_actives() -> bool:
    """Vérifie si GitHub Pages est déjà actif pour ce dépôt."""
    from config.github_config import pages_deja_actives as _pages_actives
    return _pages_actives()


def _ensure_branch_exists(owner: str, repo: str, branch: str) -> bool:
    """Cree la branche gh-pages si elle n'existe pas encore."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}"
    r = _request_with_retry("GET", url)
    if r is not None and r.status_code == 200:
        return True

    # La branche n'existe pas, creer depuis le commit HEAD de main
    main_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/main"
    r_main = _request_with_retry("GET", main_url)
    if r_main is None or r_main.status_code != 200:
        log.warning("[DEPLOY] Impossible de lire le ref HEAD de main")
        return False

    sha_main = r_main.json().get("object", {}).get("sha")
    if not sha_main:
        log.warning("[DEPLOY] SHA main introuvable")
        return False

    create_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
    r_create = _request_with_retry(
        "POST",
        create_url,
        json={"ref": f"refs/heads/{branch}", "sha": sha_main},
    )
    if r_create is not None and r_create.status_code in (200, 201):
        log.info(f"[DEPLOY] Branche '{branch}' creee depuis main")
        return True

    log.warning(f"[DEPLOY] Echec creation branche '{branch}': {r_create.status_code if r_create else 'timeout'}")
    return False


def deploy_to_github_pages(run_id: str, generated_html_path: str) -> dict:
    if not GITHUB_TOKEN:
        raise DeploymentError("GITHUB_TOKEN manquant dans .env")
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        raise DeploymentError(f"GITHUB_REPO invalide : '{GITHUB_REPO}' -- format attendu : 'owner/repo'")

    owner, repo = GITHUB_REPO.split("/", 1)

    if not _ensure_branch_exists(owner, repo, GITHUB_PAGES_BRANCH):
        raise DeploymentError(f"Branche '{GITHUB_PAGES_BRANCH}' introuvable et impossible a creer")

    content = Path(generated_html_path).read_text(encoding="utf-8")
    b64 = base64.b64encode(content.encode("utf-8")).decode()

    check_url = f"https://api.github.com/repos/{owner}/{repo}/contents/index.html"

    r = _request_with_retry("GET", check_url, params={"ref": GITHUB_PAGES_BRANCH})
    sha = None
    if r is not None and r.status_code == 200:
        sha = r.json().get("sha")

    payload = {
        "message": f"deploy: {run_id}",
        "content": b64,
        "branch": GITHUB_PAGES_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    r = _request_with_retry("PUT", check_url, json=payload)

    if r is None or r.status_code not in (200, 201):
        raise DeploymentError(f"Echec depot GitHub : {r.status_code if r else 'timeout'}")

    deployed_url = f"https://{owner}.github.io/{repo}/"

    _commenter_jira_deploy(run_id, deployed_url)

    return {"success": True, "url": deployed_url, "run_id": run_id}


def _commenter_jira_deploy(ticket_id: str, url: str) -> None:
    """Ajoute un commentaire Jira avec l'URL de déploiement."""
    if not JIRA_URL or not JIRA_AUTH:
        log.warning("Config Jira manquante, commentaire de déploiement ignoré.")
        return

    try:
        import requests as req
        commentaire = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Application deployee sur GitHub Pages.\n\n"},
                        ]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "URL : "},
                            {
                                "type": "text",
                                "text": url,
                                "marks": [{"type": "link", "attrs": {"href": url}}],
                            },
                        ]
                    },
                ]
            }
        }
        r = req.post(
            f"{JIRA_URL}/rest/api/3/issue/{ticket_id}/comment",
            auth=JIRA_AUTH,
            headers=JIRA_HEADERS,
            json=commentaire,
            timeout=20,
        )
        if r.status_code in (200, 201):
            log.info(f"[DEPLOY] Commentaire Jira ajouté pour {ticket_id}")
        else:
            log.warning(f"[DEPLOY] Commentaire Jira échoué {r.status_code}")
    except Exception as e:
        log.error(f"[DEPLOY] Exception commentaire Jira : {e}")


def deployer_ticket(ticket_id: str, titre: str) -> dict:
    """Déploie un ticket sur GitHub Pages."""
    from config.github_config import telecharger_fichier
    html = telecharger_fichier(f"tickets/{ticket_id}/index.html")
    if not html:
        return {"success": False, "error": "HTML non disponible"}

    path = Path("generated") / ticket_id / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")

    return deploy_to_github_pages(ticket_id, str(path))
