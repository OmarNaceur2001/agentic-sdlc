#!/usr/bin/env python3
"""
check_config_consistency.py

Vérifie deux types de cohérence dans le projet Agentic SDLC :

1. Variables d'environnement : compare les os.getenv(...) / os.environ[...]
   trouvés dans le code Python avec celles définies dans .env.example
   -> détecte les variables utilisées mais non documentées (bug potentiel,
      ex: JIRA_TARGET_STATUS)
   -> détecte les variables documentées mais jamais utilisées (variable
      morte, ex: JIRA_SOURCE_STATUS / JIRA_PROGRESS_STATUS)

2. Routes API : compare les fetch('/api/...') trouvés dans les fichiers
   .html avec les routes @app.get/post/put/delete(...) définies dans le
   code -> détecte les appels frontend vers des routes backend
   inexistantes (ex: /api/create-ticket)

Usage :
    python check_config_consistency.py
À exécuter depuis la racine du projet (là où se trouve .env.example).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE_DIRS = {"venv", ".venv", ".git", "__pycache__", ".qodo", ".vscode", "node_modules"}

ENV_VAR_PATTERNS = [
    re.compile(r"""os\.getenv\(\s*['"]([A-Z_][A-Z0-9_]*)['"]"""),
    re.compile(r"""os\.environ\.get\(\s*['"]([A-Z_][A-Z0-9_]*)['"]"""),
    re.compile(r"""os\.environ\[\s*['"]([A-Z_][A-Z0-9_]*)['"]\s*\]"""),
]
ROUTE_DEF_PATTERN = re.compile(r"""@app\.(?:get|post|put|delete)\(\s*['"](/api/[^'"]+)['"]""")
ROUTE_CALL_PATTERN = re.compile(r"""fetch\(\s*[`'"](/api/[^`'"]+)[`'"]""")
ENV_DEF_PATTERN = re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE)


def iter_py_files(root):
    for p in root.rglob("*.py"):
        if not any(part in EXCLUDE_DIRS for part in p.parts):
            yield p


def find_used_env_vars(root):
    used = {}
    for f in iter_py_files(root):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in ENV_VAR_PATTERNS:
            for m in pattern.finditer(text):
                used.setdefault(m.group(1), set()).add(f.name)
    return used


def find_defined_env_vars(path):
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    return set(ENV_DEF_PATTERN.findall(text))


def find_backend_routes(root):
    routes = {}
    for f in iter_py_files(root):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in ROUTE_DEF_PATTERN.finditer(text):
            routes.setdefault(m.group(1), set()).add(f.name)
    return routes


def find_frontend_routes(root):
    calls = {}
    for html_path in root.rglob("*.html"):
        if any(part in EXCLUDE_DIRS for part in html_path.parts):
            continue
        text = html_path.read_text(encoding="utf-8", errors="ignore")
        for m in ROUTE_CALL_PATTERN.finditer(text):
            calls.setdefault(m.group(1), set()).add(html_path.name)
    return calls


def main():
    print("=" * 60)
    print("1) Variables d'environnement : code vs .env.example")
    print("=" * 60)
    used = find_used_env_vars(ROOT)
    defined = find_defined_env_vars(ROOT / ".env.example")

    missing = set(used) - defined
    orphaned = defined - set(used)

    if missing:
        print("\n❌ Utilisées dans le code, ABSENTES de .env.example :")
        for var in sorted(missing):
            print(f"   {var}  <- {', '.join(sorted(used[var]))}")
    else:
        print("\n✅ Toutes les variables utilisées sont documentées.")

    if orphaned:
        print("\n⚠️  Documentées dans .env.example, JAMAIS utilisées dans le code :")
        for var in sorted(orphaned):
            print(f"   {var}")

    print("\n" + "=" * 60)
    print("2) Routes API : frontend (.html) vs backend")
    print("=" * 60)
    frontend = find_frontend_routes(ROOT)
    backend = find_backend_routes(ROOT)

    dangling = set(frontend) - set(backend)
    unused_routes = set(backend) - set(frontend)

    if dangling:
        print("\n❌ Appelées depuis le frontend, ABSENTES du backend :")
        for route in sorted(dangling):
            print(f"   {route}  <- {', '.join(sorted(frontend[route]))}")
    else:
        print("\n✅ Toutes les routes appelées existent côté backend.")

    if unused_routes:
        print("\nℹ️  Définies côté backend, jamais appelées depuis le frontend :")
        for route in sorted(unused_routes):
            print(f"   {route}")

    print()


if __name__ == "__main__":
    main()