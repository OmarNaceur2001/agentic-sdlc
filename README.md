# 🤖 Agentic SDLC

> Un système d'ingénierie logicielle autonome qui transforme un ticket Jira en page web deployée — automatiquement.

![Pipeline](https://img.shields.io/badge/Pipeline-Automated-brightgreen)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Jira](https://img.shields.io/badge/Jira-Cloud-0052CC?logo=jira)
![GitHub](https://img.shields.io/badge/GitHub-API-181717?logo=github)
![Groq](https://img.shields.io/badge/Groq-Llama_3.3-orange)
![Playwright](https://img.shields.io/badge/Tests-Playwright-45ba4b)

---

## 🎯 Vue d'ensemble

**Agentic SDLC** est un système multi-agents qui automatise le cycle de développement logiciel complet :

```
Ticket Jira (To Do)
       │
       ▼  30 secondes
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
       ├── ✅ Tests OK  → Jira : DONE
       └── ❌ Tests KO  → Jira : TO DO (retry x3)
```

**Résultat :** Un ticket créé dans Jira devient une page web testée et archivée sur GitHub en moins de 60 secondes, sans intervention humaine.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    JIRA CLOUD                           │
│         (Tickets : To Do / In Review / Done)           │
└──────────────────────┬──────────────────────────────────┘
                       │ Poll toutes les 30s
                       ▼
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (Python)                      │
│  • Détecte les tickets "À faire"                       │
│  • Coordonne Code Agent + Testing Agent                │
│  • Gère les retries (max 3)                            │
│  • Log toutes les actions                              │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐      ┌──────────────────────────────┐
│   CODE AGENT     │      │      TESTING AGENT           │
│                  │      │                              │
│ • Lit ticket     │      │ • Télécharge HTML (GitHub)  │
│ • Prompt Llama   │      │ • Valide structure HTML      │
│ • Génère HTML    │      │ • Ouvre dans Chromium        │
│ • Upload GitHub  │      │ • Vérifie erreurs JS         │
│ • Status: Review │      │ • Screenshot automatique     │
└────────┬─────────┘      │ • Status: Done ou To Do      │
         │                └──────────────────────────────┘
         ▼
┌─────────────────────────────────────────────────────────┐
│                    GITHUB                               │
│         tickets/SCRUM-X/index.html                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🧰 Stack technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Orchestration | Python 3.11 | Coordination des agents |
| API Ticketing | Jira REST API v3 | Source des tickets |
| LLM | Groq / Llama 3.3 70B | Génération de code |
| Stockage code | GitHub REST API | Versioning du code généré |
| Tests navigateur | Playwright / Chromium | Validation E2E |
| Variables | python-dotenv | Configuration sécurisée |

---

## 📁 Structure du projet

```text
agentic-sdlc/
├── orchestrator.py          # Cerveau du système — pipeline complet
├── code_agent.py            # Génération HTML via Llama + upload GitHub
├── testing_agent.py         # Validation Playwright + mise à jour Jira
├── jira_agent.py            # Utilitaires Jira
├── dashboard_app.py         # Backend FastAPI du dashboard web
├── test_connections.py      # Vérification initiale des APIs
├── requirements.txt         # Dépendances Python
├── .env.example             # Template de configuration
├── .gitignore               # Exclusions Git
├── templates/
│   └── dashboard.html       # Interface web du dashboard
├── static/                  # Fichiers statiques éventuels
├── tickets/                 # Code généré par ticket
│   ├── SCRUM-5/
│   │   └── index.html
│   ├── SCRUM-6/
│   │   └── index.html
│   └── ...
└── screenshots/             # Screenshots Playwright générés localement
    ├── SCRUM-5.png
    └── ...
---

## 🚀 Installation

### Prérequis

- Python 3.10+
- Compte Jira Cloud (gratuit)
- Compte GitHub
- Clé API Groq (gratuite)

### Étapes

```bash
# 1. Cloner le repository
git clone https://github.com/OmarNaceur2001/agentic-sdlc.git
cd agentic-sdlc

# 2. Créer l'environnement virtuel
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux

# 3. Installer les dépendances
pip install -r requirements.txt
playwright install chromium

# 4. Configurer les variables
cp .env.example .env
# Éditer .env avec vos clés API

# 5. Vérifier les connexions
python test_connections.py

# 6. Lancer le pipeline
python orchestrator.py
```

---

## ⚙️ Configuration `.env`

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

# Statuts Jira
JIRA_REVIEW_STATUS=Revue en cours
JIRA_DONE_STATUS=Terminé(e)
JIRA_REOPEN_STATUS=À faire
```

---

## 🔄 Workflow détaillé

### 1. Créer un ticket dans Jira

```
Title: Create a login page
Description: Simple login form with email and password fields
Status: To Do
```

### 2. L'Orchestrator détecte le ticket (≤ 30s)

```
2026-06-16 23:38:24  INFO  [CODE AGENT] Traitement : SCRUM-10
```

### 3. Le Code Agent génère et uploade

```
✅ Code généré (1282 caractères)
✅ Fichier uploadé : github.com/.../tickets/SCRUM-10/index.html
```

### 4. Le Testing Agent valide

```
✅ Structure HTML valide
✅ Page chargée : 78 caractères visibles
✅ Aucune erreur JavaScript
📸 Screenshot : screenshots/SCRUM-10.png
```

### 5. Résultat dans Jira

```
Status : Terminé(e) ✅
Commentaire : Tests automatiques réussis + rapport complet
```

---

## 📊 Résultats obtenus

| Ticket | Description | Résultat | Temps |
|--------|-------------|----------|-------|
| SCRUM-5 | Login page | ✅ DONE | ~45s |
| SCRUM-6 | Calculator | ✅ DONE | ~45s |
| SCRUM-7 | Contact form | ✅ DONE | ~45s |
| SCRUM-9 | Salary dashboard | ✅ DONE | ~45s |
| SCRUM-10 | Profile page | ✅ DONE | ~49s |
| SCRUM-11 | Profile page | ✅ DONE | ~49s |

**Temps moyen ticket → DONE : ~47 secondes**

---

## 📡 Dashboard temps réel — WebSocket Live Logs

Le Dashboard FastAPI intègre désormais un système de journaux en temps réel basé sur WebSocket.

### Fonctionnalités

- Streaming live des logs depuis le backend vers le navigateur
- Exécution du Code Agent depuis le Dashboard
- Exécution du Testing Agent depuis le Dashboard
- Exécution du pipeline complet depuis le Dashboard
- Affichage progressif des logs dans la page `Logs`
- Connexion directe entre l’interface web et les scripts Python

### Endpoints WebSocket

```text
/ws/code-agent
/ws/testing-agent
/ws/full-pipeline
```

### Fonctionnement

```text
Dashboard Web
    ↓ WebSocket
FastAPI Backend
    ↓ subprocess
Code Agent / Testing Agent
    ↓ stdout ligne par ligne
Page Logs du Dashboard
```

### Résultat

Le point `Dashboard temps réel — WebSocket live logs` est maintenant implémenté.
Le dashboard ne se limite plus à lancer les scripts en mode synchrone : il peut afficher les journaux d’exécution en direct pendant le traitement.

---

## 🗺️ Roadmap

- [x] Jira Agent — lecture et mise à jour des tickets
- [x] Code Agent — génération HTML avec Llama 3.3
- [x] Testing Agent — validation Playwright
- [x] Orchestrator — pipeline complet avec retry
- [x] Dashboard Web — interface locale FastAPI
- [x] Dashboard temps réel — WebSocket live logs
- [ ] Création dynamique de tickets Jira depuis le dashboard
- [ ] Affichage dynamique des tickets depuis Jira API
- [ ] Affichage réel des screenshots Playwright
- [ ] Deploy Agent — GitHub Pages automatique
- [ ] Multi-Agent — Developer + Tester + DevOps Agent


---

## 👨‍💻 Auteur

**Omar Naceur**
Étudiant ingénieur AI & Data Science — ESPRIM (ESPRIT), Monastir, Tunisie

[![GitHub](https://img.shields.io/badge/GitHub-OmarNaceur2001-181717?logo=github)](https://github.com/OmarNaceur2001)

---

## 📄 Licence

MIT License — libre d'utilisation et de modification.