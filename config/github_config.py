"""
github_config.py — Configuration centralisée GitHub API

Module unique pour l'authentification, les headers, et les fonctions
communes d'accès à GitHub avec retry automatique.
"""

import time
import base64
import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("github_config")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_PAGES_BRANCH = os.getenv("GITHUB_PAGES_BRANCH", "gh-pages")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 2


def _request_with_retry(
    method: str,
    url: str,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> requests.Response | None:
    """Exécute une requête HTTP avec retry et backoff exponentiel."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    kwargs.setdefault("headers", GITHUB_HEADERS)

    for tentative in range(max_retries):
        try:
            reponse = requests.request(method, url, **kwargs)
            if reponse.status_code < 500:
                return reponse
            log.warning(
                f"GitHub {method} {url} → {reponse.status_code} "
                f"(tentative {tentative + 1}/{max_retries})"
            )
        except requests.exceptions.RequestException as e:
            log.warning(
                f"GitHub {method} {url} réseau error: {e} "
                f"(tentative {tentative + 1}/{max_retries})"
            )

        if tentative < max_retries - 1:
            time.sleep(RETRY_BACKOFF ** (tentative + 1))

    log.error(f"GitHub {method} {url} échoué après {max_retries} tentatives")
    return None


def construire_url_pages(ticket_id: str) -> str:
    """Construit l'URL GitHub Pages pour un ticket donné."""
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        return ""
    owner, repo = GITHUB_REPO.split("/", 1)
    return f"https://{owner}.github.io/{repo}/tickets/{ticket_id}/"


def pages_deja_actives() -> bool:
    """Vérifie si GitHub Pages est déjà actif pour ce dépôt."""
    if not GITHUB_TOKEN or not GITHUB_REPO or "/" not in GITHUB_REPO:
        return False
    owner, repo = GITHUB_REPO.split("/", 1)
    reponse = _request_with_retry(
        "GET",
        f"https://api.github.com/repos/{owner}/{repo}/pages",
    )
    return reponse is not None and reponse.status_code == 200


def telecharger_fichier(chemin: str) -> str | None:
    """Télécharge un fichier depuis le dépôt GitHub. Retourne le contenu ou None."""
    if not GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{chemin}"
    reponse = _request_with_retry("GET", url)
    if reponse is None or reponse.status_code != 200:
        return None
    contenu_b64 = reponse.json().get("content", "").replace("\n", "")
    return base64.b64decode(contenu_b64).decode("utf-8")


def uploader_fichier(
    chemin_repo: str,
    contenu: str,
    message_commit: str,
) -> str | None:
    """Upload ou met à jour un fichier sur GitHub. Retourne l'URL ou None."""
    if not GITHUB_REPO:
        return None

    contenu_b64 = base64.b64encode(contenu.encode("utf-8")).decode("utf-8")
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{chemin_repo}"

    # Vérifier si le fichier existe déjà
    check = _request_with_retry("GET", url)
    sha_existant = None
    if check is not None and check.status_code == 200:
        sha_existant = check.json().get("sha")

    payload = {"message": message_commit, "content": contenu_b64}
    if sha_existant:
        payload["sha"] = sha_existant

    reponse = _request_with_retry("PUT", url, json=payload)
    if reponse is not None and reponse.status_code in (200, 201):
        return reponse.json().get("content", {}).get("html_url")
    return None
