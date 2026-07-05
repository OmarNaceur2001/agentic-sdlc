# 🤖 Agentic SDLC

> Un système d'ingénierie logicielle autonome qui transforme un ticket Jira en page web déployée — automatiquement.

![Pipeline](https://img.shields.io/badge/Pipeline-Automated-brightgreen)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Jira](https://img.shields.io/badge/Jira-Cloud-0052CC?logo=jira)
![GitHub](https://img.shields.io/badge/GitHub-API-181717?logo=github)
![Groq](https://img.shields.io/badge/Groq-Llama_3.3-orange)
![Playwright](https://img.shields.io/badge/Tests-Playwright-45ba4b)

---

## 🎯 Présentation

**Agentic SDLC** est un système multi-agents qui automatise l’intégralité du cycle de développement logiciel, depuis la création d’un ticket dans Jira jusqu’à la génération et la validation d’une page web, sans intervention humaine.

```text
Ticket Jira (À faire)
       │
       ▼  (Polling toutes les 30s)
Orchestrator détecte
       │
       ▼
Code Agent (Llama 3.3)
  → Génère HTML/CSS/JS
  → Upload sur GitHub
       │
       ▼
Testing Agent (Playwright)
  → Valide la structure HTML
  → Teste dans Chromium
  → Vérifie les erreurs JS
       │
       ├── ✅ Tests OK  → Jira : Terminé(e)
       └── ❌ Tests KO  → Jira : À faire (retry x3)
```

### Résultat :
 un ticket créé dans Jira devient une page web testée et archivée sur GitHub en moins d’une minute, sans aucune interaction humaine.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        JIRA CLOUD                          │
│          (Tickets : À faire / En révision / Terminé)       │
└────────────────────────┬────────────────────────────────────┘
                         │ Interrogation toutes les 30s
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Python)                    │
│  • Détecte les tickets « À faire »                         │
│  • Coordonne Code Agent et Testing Agent                   │
│  • Gère les tentatives (max 3)                             │
│  • Journalise toutes les actions                           │
└──────────┬────────────────────────────┬────────────────────┘
           │                            │
           ▼                            ▼
┌──────────────────────┐     ┌───────────────────────────────┐
│     CODE AGENT       │     │      TESTING AGENT            │
│                      │     │                               │
│ • Lit le ticket      │     │ • Télécharge HTML (GitHub)   │
│ • Construit le prompt│     │ • Valide la structure HTML    │
│ • Appelle Llama 3.3  │     │ • Ouvre dans Chromium         │
│ • Génère le code     │     │ • Vérifie les erreurs JS      │
│ • Uploade sur GitHub │     │ • Capture d'écran             │
│ • Passe en révision  │     │ • Met à jour Jira (Done/To Do)│
└──────────────────────┘     └───────────────────────────────┘
           │                            │
           └──────────────┬─────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                        GITHUB                              │
│              tickets/SCRUM-X/index.html                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧰 Stack technique

| Composant          | Technologie               | Rôle                               |
|--------------------|---------------------------|------------------------------------|
| Orchestration      | Python 3.11               | Coordination des agents            |
| API Jira           | REST API v3               | Source des tickets                 |
| LLM                | Groq / Llama 3.3 70B      | Génération de code                 |
| Stockage code      | GitHub REST API           | Versionnement du code généré       |
| Tests navigateur   | Playwright / Chromium     | Validation end-to-end              |
| Configuration      | python-dotenv             | Gestion sécurisée des variables    |

---

## 📁 Structure du projet

```text
agentic-sdlc/
├── orchestrator.py          # Coordonnateur principal du pipeline
├── code_agent.py            # Génération HTML via Llama + upload GitHub
├── testing_agent.py         # Validation Playwright + mise à jour Jira
├── jira_agent.py            # Utilitaires d'accès à Jira
├── dashboard_app.py         # Interface web (FastAPI) de supervision
├── test_connections.py      # Vérification des connexions aux APIs
├── requirements.txt         # Dépendances Python
├── .env.example             # Modèle de configuration
├── .gitignore               # Fichiers exclus de Git
├── templates/
│   └── dashboard.html       # Interface HTML du tableau de bord
├── tickets/                 # Code généré, organisé par ticket
│   ├── SCRUM-5/
│   │   └── index.html
│   └── ...
└── screenshots/             # Captures d'écran Playwright
    ├── SCRUM-5.png
    └── ...
```

---

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- Un compte Jira Cloud (gratuit)
- Un compte GitHub
- Une clé API Groq (gratuite)

### Procédure

```bash
# 1. Cloner le dépôt
git clone https://github.com/OmarNaceur2001/agentic-sdlc.git
cd agentic-sdlc

# 2. Créer et activer l'environnement virtuel
python -m venv venv
venv\Scripts\activate         # Windows
source venv/bin/activate      # macOS / Linux

# 3. Installer les dépendances
pip install -r requirements.txt
playwright install chromium

# 4. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos identifiants et clés API

# 5. Vérifier les connexions
python test_connections.py

# 6. Lancer le pipeline
python orchestrator.py
```

---

## ⚙️ Configuration – `.env`

```env
# Jira
JIRA_URL=https://votre-domaine.atlassian.net
JIRA_EMAIL=votre-email@gmail.com
JIRA_TOKEN=votre-token-jira
JIRA_PROJECT_KEY=SCRUM

# GitHub
GITHUB_TOKEN=votre-token-github
GITHUB_REPO=username/agentic-sdlc

# Groq (LLM)
GROQ_API_KEY=votre-cle-groq
GROQ_MODEL=llama-3.3-70b-versatile

# Orchestrator
POLL_INTERVAL_SECONDS=30
MAX_RETRIES=3

# Statuts Jira (doivent correspondre exactement aux statuts de votre projet)
# Remplissez ces valeurs avec EXACTEMENT les libellés Jira.
# Elles sont utilisées par les agents pour sélectionner les tickets et effectuer les transitions.
JIRA_SOURCE_STATUS=À faire
JIRA_PROGRESS_STATUS=En cours
JIRA_REVIEW_STATUS=Revue en cours
JIRA_DONE_STATUS=Terminé(e)
JIRA_REOPEN_STATUS=À faire
```

> **⚠️ Remarque :** Les libellés des statuts Jira ci-dessus sont donnés à titre d’exemple. Adaptez-les aux statuts réels de votre projet Jira. Le code utilise ces variables pour effectuer les transitions.

---

## 🔄 Déroulement du pipeline

### 1. Création d’un ticket dans Jira

```
Titre : Créer une page de connexion
Description : Formulaire simple avec email et mot de passe
Statut : À faire
```

### 2. L’Orchestrator détecte le ticket (≤ 30 s)

```
2026-06-16 23:38:24  INFO  [CODE AGENT] Traitement : SCRUM-10
```

### 3. Le Code Agent génère la page et l’upload

```
✅ Code généré (1 282 caractères)
✅ Fichier uploadé : github.com/.../tickets/SCRUM-10/index.html
```

### 4. Le Testing Agent valide la page

```
✅ Structure HTML valide
✅ Page chargée – 78 caractères visibles
✅ Aucune erreur JavaScript
📸 Capture d'écran : screenshots/SCRUM-10.png
```

### 5. Mise à jour du ticket dans Jira

```
Statut : Terminé(e) ✅
Commentaire : Tests automatiques réussis + rapport complet
```

---

## 📊 Résultats obtenus

| Ticket   | Description             | Résultat   | Durée |
|----------|-------------------------|------------|-------|
| SCRUM-5  | Page de connexion       | ✅ DONE    | ~45 s |
| SCRUM-6  | Calculatrice            | ✅ DONE    | ~45 s |
| SCRUM-7  | Formulaire de contact   | ✅ DONE    | ~45 s |
| SCRUM-9  | Tableau de bord salaire | ✅ DONE    | ~45 s |
| SCRUM-10 | Page profil             | ✅ DONE    | ~49 s |
| SCRUM-11 | Page profil (bis)       | ✅ DONE    | ~49 s |

**Temps moyen ticket → DONE : ~47 secondes**

---

## 📡 Tableau de bord – Supervision et exécution manuelle

Le tableau de bord FastAPI expose une interface web et des endpoints REST pour interagir avec le pipeline :

- **`/`** – interface HTML (`templates/dashboard.html`)
- **`POST /api/run-code-agent`** – lance le Code Agent (lit les tickets « To Do »/« À faire » côté Jira)
- **`POST /api/run-testing-agent`** – lance le Testing Agent (lit les tickets « Revue en cours » côté Jira)

- **`POST /api/run-full-pipeline`** – exécute l’intégralité du pipeline (Code Agent + Testing Agent)
- **`GET /api/logs`** – retourne les dernières lignes du fichier `orchestrator.log`
- **`GET /api/tickets`** – liste les tickets via l’API Jira (le dashboard n’utilise pas le filesystem pour la liste)

- **`GET /api/screenshots`** – liste les captures d’écran disponibles

L’interface web permet de lancer ces actions manuellement et d’afficher les logs via des appels AJAX classiques.  
Le système reste entièrement autonome grâce à `orchestrator.py` (boucle de polling Jira).


### Flux de données (version REST)

```text
Interface Web  →  Fetch /api/run-*  →  Backend FastAPI  →  subprocess  →  Code/Testing Agent
                                                                                ↓ stdout
Interface ←  Réponse JSON + /api/logs  ←  Backend  ←  logs écrits dans orchestrator.log
```

---

## 🗺️ Feuille de route

- [x] **Jira Agent** – lecture et mise à jour des tickets
- [x] **Code Agent** – génération HTML avec Llama 3.3
- [x] **Testing Agent** – validation avec Playwright
- [x] **Orchestrator** – pipeline complet avec reprise sur erreur
- [x] **Dashboard Web** – interface locale FastAPI
- [x] **API REST** de supervision et d’exécution manuelle
- [ ] **Création dynamique de tickets Jira** depuis le tableau de bord (backend à implémenter)
- [x] **Affichage dynamique** des tickets depuis l’API Jira (au lieu de fichiers locaux)
- [ ] **Affichage réel des captures d’écran** Playwright dans l’interface
- [ ] **Agent de déploiement** – déploiement automatique sur GitHub Pages
- [ ] **WebSocket Live Logs** – remplacement des appels AJAX par une connexion temps réel (amélioration future)

---

## 👨‍💻 Auteur

**Omar Naceur**  
Étudiant ingénieur en IA & Data Science – ESPRIM (ESPRIT), Monastir, Tunisie

[![GitHub](https://img.shields.io/badge/GitHub-OmarNaceur2001-181717?logo=github)](https://github.com/OmarNaceur2001)

---

## 📄 Licence

Ce projet est distribué sous la licence MIT – utilisation et modification libres.