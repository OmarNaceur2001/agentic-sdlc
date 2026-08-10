"""
Script de test des connexions API.

Objectif :
- Verifier la connexion a Jira Cloud
- Verifier la connexion a GitHub
- Verifier la connexion a Groq API

Important :
- Les cles API sont stockees dans le fichier .env
- Le fichier .env ne doit jamais etre envoye sur GitHub
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from dotenv import load_dotenv
from groq import Groq

from config.jira_config import JIRA_URL, JIRA_EMAIL, JIRA_TOKEN
from config.github_config import GITHUB_TOKEN, GITHUB_HEADERS

load_dotenv()


def verifier_variable_env(nom_variable: str) -> str:
    valeur = os.getenv(nom_variable)
    if not valeur:
        print(f"[ERR] Variable manquante dans .env : {nom_variable}")
        sys.exit(1)
    return valeur


def tester_jira() -> None:
    print("[TEST] Connexion Jira...")

    if not all([JIRA_URL, JIRA_EMAIL, JIRA_TOKEN]):
        print("   [ERR] Variables Jira manquantes dans .env")
        return

    endpoint = f"{JIRA_URL}/rest/api/3/myself"

    try:
        reponse = requests.get(
            endpoint,
            auth=(JIRA_EMAIL, JIRA_TOKEN),
            headers={"Accept": "application/json"},
            timeout=15,
        )

        if reponse.status_code == 200:
            utilisateur = reponse.json()
            nom = utilisateur.get("displayName", "Utilisateur inconnu")
            print(f"   [OK] Jira connecte : {nom}")
        elif reponse.status_code == 401:
            print("   [ERR] Jira 401 -- email ou token incorrect.")
        elif reponse.status_code == 403:
            print("   [ERR] Jira 403 -- acces refuse.")
        else:
            print(f"   [ERR] Jira {reponse.status_code}")
            print(f"   Detail : {reponse.text[:300]}")

    except requests.exceptions.RequestException as erreur:
        print("   [ERR] Reseau Jira.")
        print(f"   Detail : {erreur}")


def tester_github() -> None:
    print("[TEST] Connexion GitHub...")

    if not GITHUB_TOKEN:
        print("   [ERR] GITHUB_TOKEN manquant dans .env")
        return

    endpoint = "https://api.github.com/user"

    try:
        reponse = requests.get(
            endpoint,
            headers=GITHUB_HEADERS,
            timeout=15,
        )

        if reponse.status_code == 200:
            utilisateur = reponse.json()
            login = utilisateur.get("login", "login inconnu")
            print(f"   [OK] GitHub connecte : {login}")
        elif reponse.status_code == 401:
            print("   [ERR] GitHub 401 -- token invalide ou expire.")
        elif reponse.status_code == 403:
            print("   [ERR] GitHub 403 -- acces refuse ou limite API.")
        else:
            print(f"   [ERR] GitHub {reponse.status_code}")
            print(f"   Detail : {reponse.text[:300]}")

    except requests.exceptions.RequestException as erreur:
        print("   [ERR] Reseau GitHub.")
        print(f"   Detail : {erreur}")


def tester_groq() -> None:
    print("[TEST] Connexion Groq (Llama)...")

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("   [ERR] GROQ_API_KEY manquant dans .env")
        return

    try:
        client = Groq(api_key=groq_api_key)

        reponse = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reponds exactement : Connexion API reussie"}],
            max_tokens=20,
        )

        texte = reponse.choices[0].message.content.strip()
        print(f"   [OK] Groq OK -- {texte}")

    except Exception as erreur:
        print("   [ERR] Groq API.")
        print(f"   Detail : {erreur}")


def main() -> None:
    print("\n--- Demarrage des tests API ---\n")

    tester_jira()
    tester_github()
    tester_groq()

    print("\n--- Tests termines ---\n")


if __name__ == "__main__":
    main()
