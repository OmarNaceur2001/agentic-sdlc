"""
Streamlit Chatbot — Human-in-the-loop Agentic SDLC

Objectif :
- Fournir une interface conversationnelle avant de déclencher le pipeline
- Permettre à l'utilisateur de demander une action en langage naturel
- Demander une confirmation humaine avant exécution
- Lancer Code Agent, Testing Agent ou Full Pipeline depuis Streamlit
"""

import subprocess
import sys
from datetime import datetime

import streamlit as st


# ─────────────────────────────────────────────────────────────
# Configuration page
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Agentic SDLC — Chatbot",
    page_icon="🤖",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def executer_commande(command: list[str], timeout: int = 600) -> dict:
    """
    Exécute une commande Python locale et retourne stdout/stderr.
    """
    try:
        resultat = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        return {
            "success": resultat.returncode == 0,
            "stdout": resultat.stdout,
            "stderr": resultat.stderr,
            "returncode": resultat.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Timeout : la commande a dépassé {timeout} secondes.",
            "returncode": -1,
        }

    except Exception as erreur:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Erreur inattendue : {erreur}",
            "returncode": -2,
        }


def ajouter_message(role: str, content: str) -> None:
    """
    Ajoute un message dans l'historique du chat.
    """
    st.session_state.messages.append(
        {
            "role": role,
            "content": content,
            "time": datetime.now().strftime("%H:%M:%S"),
        }
    )


def detecter_intention(message: str) -> dict:
    """
    Détecte simplement l'intention utilisateur.

    Version volontairement simple et gratuite :
    - Pas d'appel LLM ici
    - Règles keyword-based
    """
    msg = message.lower().strip()

    if any(mot in msg for mot in ["pipeline", "full", "complet", "tout lancer"]):
        return {
            "intent": "full_pipeline",
            "action": "Lancer le pipeline complet",
            "command": [sys.executable, "code_agent.py"],
            "needs_testing": True,
        }

    if any(mot in msg for mot in ["code agent", "générer", "generer", "html", "code"]):
        return {
            "intent": "code_agent",
            "action": "Lancer le Code Agent",
            "command": [sys.executable, "code_agent.py"],
            "needs_testing": False,
        }

    if any(mot in msg for mot in ["test", "testing", "playwright", "validation"]):
        return {
            "intent": "testing_agent",
            "action": "Lancer le Testing Agent",
            "command": [sys.executable, "testing_agent.py"],
            "needs_testing": False,
        }

    if any(mot in msg for mot in ["ticket", "jira", "créer", "creer"]):
        return {
            "intent": "ticket_request",
            "action": "Préparer la création d'un ticket Jira",
            "command": None,
            "needs_testing": False,
        }

    return {
        "intent": "unknown",
        "action": "Clarifier la demande",
        "command": None,
        "needs_testing": False,
    }


def lancer_action_confirmee() -> None:
    """
    Lance l'action actuellement en attente de confirmation.
    """
    pending = st.session_state.get("pending_action")

    if not pending:
        ajouter_message(
            "assistant",
            "Aucune action n'est en attente de confirmation."
        )
        return

    intent = pending.get("intent")

    if intent == "full_pipeline":
        ajouter_message(
            "assistant",
            "🚀 Lancement du pipeline complet : Code Agent puis Testing Agent..."
        )

        code_result = executer_commande([sys.executable, "code_agent.py"])
        test_result = executer_commande([sys.executable, "testing_agent.py"])

        rapport = "## Résultat pipeline complet\n\n"

        rapport += "### Code Agent\n"
        rapport += "```text\n"
        rapport += code_result["stdout"][-4000:]
        if code_result["stderr"]:
            rapport += "\nSTDERR:\n" + code_result["stderr"][-2000:]
        rapport += "\n```\n\n"

        rapport += "### Testing Agent\n"
        rapport += "```text\n"
        rapport += test_result["stdout"][-4000:]
        if test_result["stderr"]:
            rapport += "\nSTDERR:\n" + test_result["stderr"][-2000:]
        rapport += "\n```\n"

        if code_result["success"] and test_result["success"]:
            rapport += "\n✅ Pipeline terminé avec succès."
        else:
            rapport += "\n⚠️ Pipeline terminé avec erreurs ou avertissements."

        ajouter_message("assistant", rapport)

    elif intent == "code_agent":
        ajouter_message("assistant", "🤖 Lancement du Code Agent...")

        result = executer_commande([sys.executable, "code_agent.py"])

        rapport = "## Résultat Code Agent\n\n"
        rapport += "```text\n"
        rapport += result["stdout"][-5000:]
        if result["stderr"]:
            rapport += "\nSTDERR:\n" + result["stderr"][-2000:]
        rapport += "\n```\n"

        if result["success"]:
            rapport += "\n✅ Code Agent terminé avec succès."
        else:
            rapport += "\n❌ Code Agent terminé avec erreur."

        ajouter_message("assistant", rapport)

    elif intent == "testing_agent":
        ajouter_message("assistant", "🧪 Lancement du Testing Agent...")

        result = executer_commande([sys.executable, "testing_agent.py"])

        rapport = "## Résultat Testing Agent\n\n"
        rapport += "```text\n"
        rapport += result["stdout"][-5000:]
        if result["stderr"]:
            rapport += "\nSTDERR:\n" + result["stderr"][-2000:]
        rapport += "\n```\n"

        if result["success"]:
            rapport += "\n✅ Testing Agent terminé avec succès."
        else:
            rapport += "\n❌ Testing Agent terminé avec erreur."

        ajouter_message("assistant", rapport)

    elif intent == "ticket_request":
        ajouter_message(
            "assistant",
            (
                "📝 Création de ticket Jira non encore activée dans ce chatbot.\n\n"
                "Prochaine étape recommandée : connecter ce chatbot à l'endpoint "
                "`POST /api/tickets` du dashboard FastAPI."
            )
        )

    else:
        ajouter_message(
            "assistant",
            "Je n'ai pas pu déterminer une action exécutable."
        )

    st.session_state.pending_action = None


# ─────────────────────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Bonjour Omar 👋\n\n"
                "Je suis le chatbot Agentic SDLC.\n\n"
                "Je peux t'aider à :\n"
                "- lancer le Code Agent,\n"
                "- lancer le Testing Agent,\n"
                "- lancer le pipeline complet,\n"
                "- préparer la création d'un ticket Jira.\n\n"
                "Exemple : `lance le pipeline complet`"
            ),
            "time": datetime.now().strftime("%H:%M:%S"),
        }
    ]

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None


# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────

st.title("🤖 Agentic SDLC — Chatbot Human-in-the-loop")

st.caption(
    "Interface conversationnelle Streamlit avant déclenchement du pipeline."
)

col1, col2 = st.columns([3, 1])

with col2:
    st.subheader("Actions rapides")

    if st.button("🚀 Proposer Full Pipeline", use_container_width=True):
        st.session_state.pending_action = {
            "intent": "full_pipeline",
            "action": "Lancer le pipeline complet",
        }
        ajouter_message(
            "assistant",
            (
                "Action proposée : **Lancer le pipeline complet**.\n\n"
                "Confirme avec : `oui lancer pipeline`"
            )
        )
        st.rerun()

    if st.button("🤖 Proposer Code Agent", use_container_width=True):
        st.session_state.pending_action = {
            "intent": "code_agent",
            "action": "Lancer le Code Agent",
        }
        ajouter_message(
            "assistant",
            (
                "Action proposée : **Lancer le Code Agent**.\n\n"
                "Confirme avec : `oui lancer code agent`"
            )
        )
        st.rerun()

    if st.button("🧪 Proposer Testing Agent", use_container_width=True):
        st.session_state.pending_action = {
            "intent": "testing_agent",
            "action": "Lancer le Testing Agent",
        }
        ajouter_message(
            "assistant",
            (
                "Action proposée : **Lancer le Testing Agent**.\n\n"
                "Confirme avec : `oui lancer testing agent`"
            )
        )
        st.rerun()

    if st.button("🧹 Effacer conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_action = None
        st.rerun()


with col1:
    # Afficher l'historique
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]

        with st.chat_message(role):
            st.markdown(content)

    # Chat input
    prompt = st.chat_input(
        "Écris une demande, ex: lance le pipeline complet..."
    )

    if prompt:
        ajouter_message("user", prompt)

        prompt_normalise = prompt.lower().strip()

        confirmation_positive = any(
            expression in prompt_normalise
            for expression in [
                "oui",
                "confirme",
                "lancer",
                "vas-y",
                "go",
                "exécute",
                "execute",
            ]
        )

        if st.session_state.pending_action and confirmation_positive:
            lancer_action_confirmee()

        else:
            intention = detecter_intention(prompt)

            if intention["intent"] == "unknown":
                ajouter_message(
                    "assistant",
                    (
                        "Je n'ai pas compris l'action exacte.\n\n"
                        "Tu peux écrire par exemple :\n"
                        "- `lance le code agent`\n"
                        "- `lance le testing agent`\n"
                        "- `lance le pipeline complet`\n"
                        "- `je veux créer un ticket Jira`"
                    )
                )

            else:
                st.session_state.pending_action = intention

                ajouter_message(
                    "assistant",
                    (
                        f"J'ai détecté l'action suivante : "
                        f"**{intention['action']}**.\n\n"
                        "Avant d'exécuter, je demande une confirmation humaine.\n\n"
                        "Confirme avec : `oui lancer`"
                    )
                )

        st.rerun()