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
- Génération automatique de code HTML : OK
- Upload automatique sur GitHub : OK
- Commentaires automatiques dans Jira : OK

---

## Structure du projet

```text
agentic-sdlc/
├── .gitignore
├── requirements.txt
├── test_connections.py
├── jira_agent.py
├── code_agent.py
├── README.md
└── tickets/
    ├── SCRUM-5/
    │   └── index.html
    ├── SCRUM-6/
    │   └── index.html
    └── SCRUM-7/
        └── index.html
```

---

## Installation

### 1. Cloner le projet

```bash
git clone https://github.com/OmarNaceur2001/agentic-sdlc.git
cd agentic-sdlc
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
```

### 3. Activer l'environnement virtuel

Sous Windows :

```powershell
venv\Scripts\activate
```

Sous macOS/Linux :

```bash
source venv/bin/activate
```

### 4. Installer les dépendances

```bash
pip install -r requirements.txt
```

---

## Configuration

Créer un fichier `.env` à la racine du projet.

Exemple :

```env
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_TOKEN=your-jira-token

GITHUB_TOKEN=your-github-token
GITHUB_REPO=your-username/agentic-sdlc

GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

JIRA_PROJECT_KEY=SCRUM
JIRA_SOURCE_STATUS=À faire
JIRA_PROGRESS_STATUS=En cours
JIRA_REVIEW_STATUS=Revue en cours
```

> Important : le fichier `.env` contient des informations sensibles. Il ne doit jamais être envoyé sur GitHub.

---

## Semaine 1 — Setup des connexions API

Le fichier `test_connections.py` permet de tester les connexions vers :

- Jira Cloud
- GitHub
- Groq/Llama

### Exécution

```bash
python test_connections.py
```

### Résultat attendu

```text
🚀 Démarrage des tests API...

🔵 Test de connexion Jira...
   ✅ Jira OK

🐙 Test de connexion GitHub...
   ✅ GitHub OK

🤖 Test de connexion Groq (Llama)...
   ✅ Groq OK

🎉 Tests terminés.
```

---

## Semaine 2 — Jira Agent

Le fichier `jira_agent.py` automatise le traitement des tickets Jira.

### Fonctionnalités

- Lire les tickets Jira à traiter
- Afficher les informations principales :
  - clé du ticket
  - titre
  - statut
  - description
- Déplacer automatiquement les tickets depuis `À faire` vers `En cours`

### Variables d'environnement nécessaires

```env
JIRA_PROJECT_KEY=SCRUM
JIRA_SOURCE_STATUS=À faire
JIRA_TARGET_STATUS=En cours
```

### Exécution

```bash
python jira_agent.py
```

### Exemple de résultat

```text
=================================================================
  🤖 Jira Agent — Lecture et mise à jour automatique des tickets
=================================================================

📋 3 ticket(s) trouvé(s)

SCRUM-5 → En cours avec succès
SCRUM-6 → En cours avec succès
SCRUM-7 → En cours avec succès

Tickets modifiés avec succès : 3
Tickets en échec            : 0
```

---

## Semaine 3 — Code Generation Agent

Le fichier `code_agent.py` automatise la génération de code à partir des tickets Jira.

### Fonctionnalités

- Lire les tickets Jira à traiter
- Passer les tickets vers `En cours`
- Générer une page HTML complète avec Groq/Llama
- Publier le fichier généré dans GitHub
- Ajouter un commentaire Jira avec le lien du fichier généré
- Passer les tickets vers `In Review` / `Revue en cours`

### Variables d'environnement nécessaires

```env
JIRA_PROJECT_KEY=SCRUM
JIRA_SOURCE_STATUS=À faire
JIRA_PROGRESS_STATUS=En cours
JIRA_REVIEW_STATUS=Revue en cours

GITHUB_REPO=OmarNaceur2001/agentic-sdlc
GROQ_MODEL=llama-3.3-70b-versatile
```

### Exécution

```bash
python code_agent.py
```

### Résultat

Les fichiers générés sont publiés dans :

```text
tickets/
├── SCRUM-5/
│   └── index.html
├── SCRUM-6/
│   └── index.html
└── SCRUM-7/
    └── index.html
```

### Exemple de résultat

```text
=================================================================
  🤖 Code Agent — Génération automatique de code
=================================================================

📋 3 ticket(s) trouvé(s)

┌─ Ticket : SCRUM-5
│  Titre  : Create a login page
│  Desc   : Simple login form with email and password fields...
└────────────────────────────────────────────────────────────
   ⏳ Status → 'En cours'...
   ✅ Status mis à jour
   🤖 Génération du code avec Llama...
   ✅ Code généré
   📤 Upload sur GitHub → tickets/SCRUM-5/index.html
   ✅ Fichier uploadé
   💬 Commentaire ajouté dans Jira
   ⏳ Status → 'In Review'...
   ✅ Status mis à jour

=================================================================
  ✅ Code Agent terminé
=================================================================
```

---

## Sécurité

Les fichiers suivants ne doivent jamais être envoyés sur GitHub :

```text
.env
venv/
__pycache__/
```

Le fichier `.gitignore` doit contenir au minimum :

```gitignore
.env
venv/
__pycache__/
*.pyc
```

Si une clé API est exposée accidentellement, il faut immédiatement :

1. Révoquer la clé exposée
2. Générer une nouvelle clé
3. Mettre à jour le fichier `.env`
4. Vérifier que `.env` n'est pas suivi par Git

---

## Roadmap

### Semaine 1

- Initialisation du projet
- Connexion Jira
- Connexion GitHub
- Connexion Groq

### Semaine 2

- Lecture des tickets Jira
- Extraction des informations principales
- Transition automatique des tickets vers `En cours`

### Semaine 3

- Génération de code HTML avec Groq/Llama
- Upload automatique des fichiers dans GitHub
- Ajout automatique de commentaires dans Jira
- Transition automatique des tickets vers `In Review`

### Semaine 4

- Création automatique de GitHub Issues
- Liaison entre tickets Jira et tâches GitHub
- Génération de branches Git par ticket

### Semaine 5

- Génération automatique de pull requests
- Amélioration du workflow agentique
- Ajout de logs et monitoring

---

## Auteur

Omar Naceur

Projet réalisé dans le cadre d'un apprentissage pratique autour de l'automatisation SDLC, Jira, GitHub, Python et agents IA.
