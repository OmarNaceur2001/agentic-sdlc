"""
Script de test des connexions API.

Objectif :
- Vérifier la connexion à Jira Cloud
- Vérifier la connexion à GitHub
- Vérifier la connexion à Gemini API

Important :
- Les clés API sont stockées dans le fichier .env
- Le fichier .env ne doit jamais être envoyé sur GitHub
"""

import os
import sys
import requests
from dotenv import load_dotenv
from groq import Groq


# Charger les variables d'environnement depuis le fichier .env
load_dotenv()


def verifier_variable_env(nom_variable: str) -> str:
    """
    Vérifie qu'une variable d'environnement existe.

    Paramètre :
        nom_variable : nom de la variable à vérifier

    Retour :
        La valeur de la variable si elle existe

    Arrêt :
        Le programme s'arrête si la variable est absente
    """
    valeur = os.getenv(nom_variable)

    if not valeur:
        print(f"❌ Variable manquante dans .env : {nom_variable}")
        sys.exit(1)

    return valeur


def tester_jira() -> None:
    """
    Teste la connexion à Jira Cloud avec l'API REST.
    """
    print("🔵 Test de connexion Jira...")

    jira_url = verifier_variable_env("JIRA_URL")
    jira_email = verifier_variable_env("JIRA_EMAIL")
    jira_token = verifier_variable_env("JIRA_TOKEN")

    endpoint = f"{jira_url}/rest/api/3/myself"

    try:
        reponse = requests.get(
            endpoint,
            auth=(jira_email, jira_token),
            headers={
                "Accept": "application/json"
            },
            timeout=15
        )

        if reponse.status_code == 200:
            utilisateur = reponse.json()
            nom = utilisateur.get("displayName", "Utilisateur inconnu")
            print(f"   ✅ Jira OK — connecté en tant que : {nom}")

        elif reponse.status_code == 401:
            print("   ❌ Jira Erreur 401 — email ou token incorrect.")

        elif reponse.status_code == 403:
            print("   ❌ Jira Erreur 403 — accès refusé.")

        else:
            print(f"   ❌ Jira Erreur : {reponse.status_code}")
            print(f"   Détail : {reponse.text[:300]}")

    except requests.exceptions.RequestException as erreur:
        print("   ❌ Erreur réseau avec Jira.")
        print(f"   Détail : {erreur}")


def tester_github() -> None:
    """
    Teste la connexion à GitHub avec l'API REST.
    """
    print("🐙 Test de connexion GitHub...")

    github_token = verifier_variable_env("GITHUB_TOKEN")

    endpoint = "https://api.github.com/user"

    try:
        reponse = requests.get(
            endpoint,
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            timeout=15
        )

        if reponse.status_code == 200:
            utilisateur = reponse.json()
            login = utilisateur.get("login", "login inconnu")
            print(f"   ✅ GitHub OK — connecté en tant que : {login}")

        elif reponse.status_code == 401:
            print("   ❌ GitHub Erreur 401 — token invalide ou expiré.")

        elif reponse.status_code == 403:
            print("   ❌ GitHub Erreur 403 — accès refusé ou limite API atteinte.")

        else:
            print(f"   ❌ GitHub Erreur : {reponse.status_code}")
            print(f"   Détail : {reponse.text[:300]}")

    except requests.exceptions.RequestException as erreur:
        print("   ❌ Erreur réseau avec GitHub.")
        print(f"   Détail : {erreur}")


def tester_gemini() -> None:
    """
    Teste la connexion à Groq API (modèle Llama).
    """
    print("🤖 Test de connexion Groq (Llama)...")

    groq_api_key = verifier_variable_env("GROQ_API_KEY")

    try:
        client = Groq(api_key=groq_api_key)

        reponse = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Réponds exactement : Connexion API réussie"}],
            max_tokens=20
        )

        texte = reponse.choices[0].message.content.strip()
        print(f"   ✅ Groq OK — {texte}")

    except Exception as erreur:
        print("   ❌ Erreur avec Groq API.")
        print(f"   Détail : {erreur}")

def main() -> None:
    """
    Fonction principale du programme.
    """
    print("\n🚀 Démarrage des tests API...\n")

    tester_jira()
    tester_github()
    tester_gemini()

    print("\n🎉 Tests terminés.")


if __name__ == "__main__":
    main()