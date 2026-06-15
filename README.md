# Agentic SDLC

Projet d'automatisation du cycle de vie logiciel avec des agents IA.

## Objectif

Ce projet vise à construire progressivement un système capable de connecter :

- Jira pour la gestion des tâches
- GitHub pour la gestion du code
- Groq/Llama pour l'intelligence artificielle
- Python pour l'orchestration

L'objectif final est de créer un assistant agentique capable de lire des tickets Jira, analyser les besoins, générer des propositions techniques, interagir avec GitHub et automatiser certaines étapes du cycle de développement logiciel.

---

## État actuel

- Connexion Jira : OK
- Connexion GitHub : OK
- Connexion Groq : OK
- Lecture des tickets Jira : OK
- Transition automatique des tickets Jira : OK

---

## Structure du projet

```text
agentic-sdlc/
├── .gitignore
├── requirements.txt
├── test_connections.py
├── jira_agent.py
└── README.md