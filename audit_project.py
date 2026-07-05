#!/usr/bin/env python3
"""
audit_project.py — Analyse complète d'un projet Python
Détecte : bugs, sécurité, cohérence config/routes, gestion d'erreurs,
          dépendances, qualité code, problèmes de base de données.
Usage : python audit_project.py
"""

import re, os, ast, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(".").resolve()
EXCLUDE = {"venv", ".venv", ".git", "__pycache__", ".qodo", ".vscode", "node_modules"}
PY_FILES = [p for p in ROOT.rglob("*.py")
            if not any(x in p.parts for x in EXCLUDE)]
HTML_FILES = [p for p in ROOT.rglob("*.html")
              if not any(x in p.parts for x in EXCLUDE)]

ERRORS   = []
WARNINGS = []
INFO     = []

def E(phase, msg): ERRORS.append(f"[{phase}] ❌ {msg}")
def W(phase, msg): WARNINGS.append(f"[{phase}] ⚠️  {msg}")
def I(phase, msg): INFO.append(f"[{phase}] ℹ️  {msg}")

def read(p):
    try: return p.read_text(encoding="utf-8", errors="ignore")
    except: return ""

# ─────────────────────────────────────────────
# 1. SYNTAXE — compile chaque fichier Python
# ─────────────────────────────────────────────
def check_syntax():
    for f in PY_FILES:
        src = read(f)
        try:
            compile(src, str(f), "exec")
        except SyntaxError as e:
            E("SYNTAX", f"{f.name}:{e.lineno} — {e.msg}")

# ─────────────────────────────────────────────
# 2. IMPORTS — inutilisés + manquants dans requirements
# ─────────────────────────────────────────────
def check_imports():
    req_path = ROOT / "requirements.txt"
    declared = set()
    if req_path.exists():
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower().split("==")[0].split(">=")[0].split("[")[0]
            if line and not line.startswith("#"):
                declared.add(line.replace("-", "_"))

    STDLIB = {"os","sys","re","json","time","datetime","logging","pathlib",
              "subprocess","threading","asyncio","typing","collections",
              "functools","itertools","math","random","hashlib","base64",
              "urllib","http","socket","io","abc","copy","enum","inspect",
              "unittest","contextlib","warnings","traceback","sqlite3",
              "csv","html","xml","email","shutil","tempfile","glob",
              "fnmatch","struct","binascii","pprint","dataclasses"}

    for f in PY_FILES:
        src = read(f)
        try:
            tree = ast.parse(src)
        except:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    pkg = node.module.split(".")[0].lower().replace("-","_")
                else:
                    for alias in node.names:
                        pkg = alias.name.split(".")[0].lower().replace("-","_")
                        break
                    else:
                        continue
                if pkg in STDLIB:
                    continue
                if pkg not in declared and pkg not in {"__future__","dotenv",
                   "pydantic","starlette","anyio","httpx","certifi",
                   "feature_extractor","code_agent","testing_agent",
                   "jira_agent","orchestrator","dashboard_app"}:
                    W("IMPORTS", f"{f.name} importe '{pkg}' absent de requirements.txt")

# ─────────────────────────────────────────────
# 3. SÉCURITÉ — secrets, injections, exec
# ─────────────────────────────────────────────
SECRET_PAT = re.compile(
    r"""(?i)(api[_-]?key|token|password|secret|passwd|pwd)\s*=\s*['"][^'"]{6,}['"]""")
SQL_PAT    = re.compile(r"""cursor\.execute\(\s*f['"]|cursor\.execute\(\s*['"][^?%]*\+""")
EXEC_PAT   = re.compile(r"""\beval\(|\bexec\(""")
SHELL_PAT  = re.compile(r"""subprocess\.(call|run|Popen).*shell\s*=\s*True""")
HARDCODE_URL = re.compile(r"""https?://[^\s'"]{10,}""")

def check_security():
    for f in PY_FILES:
        src = read(f)
        for m in SECRET_PAT.finditer(src):
            E("SECURITY", f"{f.name}:{src[:m.start()].count(chr(10))+1} — secret potentiellement codé en dur : {m.group()[:60]}")
        for m in SQL_PAT.finditer(src):
            W("SECURITY", f"{f.name}:{src[:m.start()].count(chr(10))+1} — injection SQL potentielle (f-string ou concaténation dans execute)")
        for m in EXEC_PAT.finditer(src):
            W("SECURITY", f"{f.name}:{src[:m.start()].count(chr(10))+1} — eval/exec détecté")
        for m in SHELL_PAT.finditer(src):
            W("SECURITY", f"{f.name}:{src[:m.start()].count(chr(10))+1} — subprocess avec shell=True (risque injection)")
        for m in HARDCODE_URL.finditer(src):
            url = m.group()
            if "atlassian.net" in url or "github.com/OmarNaceur" in url:
                W("SECURITY", f"{f.name}:{src[:m.start()].count(chr(10))+1} — URL hardcodée : {url[:70]}")

    # .env ne doit pas être dans git
    gitignore = ROOT / ".gitignore"
    if gitignore.exists():
        gi = read(gitignore)
        if ".env" not in gi:
            E("SECURITY", ".env absent de .gitignore — risque exposition de secrets")
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in read(env_path).splitlines():
            if re.match(r"[A-Z_]+=.{10,}", line.strip()) and "#" not in line:
                if any(k in line for k in ["TOKEN","KEY","PASSWORD","SECRET"]):
                    W("SECURITY", f".env contient une valeur sensible non vide : {line.split('=')[0]}")
                    break

# ─────────────────────────────────────────────
# 4. GESTION D'ERREURS
# ─────────────────────────────────────────────
BARE_EXCEPT = re.compile(r"^\s*except\s*:", re.MULTILINE)
BROAD_EXCEPT = re.compile(r"^\s*except\s+Exception\s*:", re.MULTILINE)
PASS_IN_EXCEPT = re.compile(r"except[^\n]*:\n\s*pass", re.MULTILINE)
SILENT_EXCEPT  = re.compile(r"except[^\n]*:\n(\s*)(pass|\.\.\.)", re.MULTILINE)

def check_error_handling():
    for f in PY_FILES:
        src = read(f)
        for m in BARE_EXCEPT.finditer(src):
            W("ERRORS", f"{f.name}:{src[:m.start()].count(chr(10))+1} — bare except: (capture tout, masque les bugs)")
        for m in SILENT_EXCEPT.finditer(src):
            W("ERRORS", f"{f.name}:{src[:m.start()].count(chr(10))+1} — except silencieux (pass/...)")

# ─────────────────────────────────────────────
# 5. VARIABLES D'ENV — cohérence code / .env.example
# ─────────────────────────────────────────────
ENV_READ = re.compile(r"""os\.(?:getenv|environ\.get)\(\s*['"]([A-Z_][A-Z0-9_]*)['"]|os\.environ\[\s*['"]([A-Z_][A-Z0-9_]*)['"]\s*\]""")
ENV_DEF  = re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE)

def check_env():
    used = defaultdict(set)
    for f in PY_FILES:
        src = read(f)
        for m in ENV_READ.finditer(src):
            var = m.group(1) or m.group(2)
            used[var].add(f.name)

    ex = ROOT / ".env.example"
    defined = set(ENV_DEF.findall(read(ex))) if ex.exists() else set()

    missing = set(used) - defined
    orphaned = defined - set(used)

    for var in sorted(missing):
        E("ENV", f"Utilisée dans {', '.join(sorted(used[var]))} — ABSENTE de .env.example : {var}")
    for var in sorted(orphaned):
        W("ENV", f"Dans .env.example, jamais lue dans le code : {var}")

# ─────────────────────────────────────────────
# 6. ROUTES — cohérence frontend / backend
# ─────────────────────────────────────────────
ROUTE_DEF  = re.compile(r"""@app\.(?:get|post|put|delete|patch)\(\s*['"](/[^'"]+)['"]""")
ROUTE_CALL = re.compile(r"""fetch\(\s*[`'"](/api/[^`'"?\s]+)""")

def check_routes():
    backend = defaultdict(set)
    for f in PY_FILES:
        src = read(f)
        for m in ROUTE_DEF.finditer(src):
            backend[m.group(1)].add(f.name)

    frontend = defaultdict(set)
    for f in HTML_FILES:
        src = read(f)
        for m in ROUTE_CALL.finditer(src):
            frontend[m.group(1)].add(f.name)

    for route in sorted(set(frontend) - set(backend)):
        E("ROUTES", f"Appelée depuis HTML ({', '.join(sorted(frontend[route]))}) — ABSENTE du backend : {route}")
    for route in sorted(set(backend) - set(frontend)):
        I("ROUTES", f"Définie dans le backend, non appelée depuis HTML : {route}")

# ─────────────────────────────────────────────
# 7. BASE DE DONNÉES — schéma et requêtes
# ─────────────────────────────────────────────
SQL_NO_PARAM = re.compile(r"""cursor\.execute\(\s*['"][^'"]*%s[^'"]*['"]|cursor\.execute\(\s*['"][^'"]*\?[^'"]*['"]""")
COMMIT_PAT   = re.compile(r"""conn\.commit\(\)""")
CLOSE_PAT    = re.compile(r"""conn\.close\(\)""")

def check_database():
    for f in PY_FILES:
        src = read(f)
        if "sqlite3" not in src:
            continue
        connects = src.count("sqlite3.connect(")
        commits  = len(COMMIT_PAT.findall(src))
        closes   = len(CLOSE_PAT.findall(src))
        if connects > closes:
            W("DATABASE", f"{f.name} — {connects} connexion(s) SQLite, {closes} close() — risque de connexion non fermée")
        if connects > 0 and commits == 0:
            W("DATABASE", f"{f.name} — connexion SQLite sans commit() visible — écritures peut-être perdues")
        if "CREATE TABLE" in src and "IF NOT EXISTS" not in src:
            W("DATABASE", f"{f.name} — CREATE TABLE sans IF NOT EXISTS — crash si la table existe déjà")

# ─────────────────────────────────────────────
# 8. QUALITÉ CODE — TODO/FIXME, prints de debug, fichiers vides
# ─────────────────────────────────────────────
TODO_PAT  = re.compile(r"#.*(TODO|FIXME|HACK|XXX|BUG)", re.IGNORECASE)
PRINT_PAT = re.compile(r"^\s*print\(", re.MULTILINE)

def check_quality():
    for f in PY_FILES:
        src = read(f)
        if not src.strip():
            W("QUALITY", f"{f.name} — fichier vide ou quasi-vide")
        for m in TODO_PAT.finditer(src):
            line = src[:m.start()].count("\n") + 1
            W("QUALITY", f"{f.name}:{line} — {m.group().strip()}")
        prints = PRINT_PAT.findall(src)
        if len(prints) > 5:
            I("QUALITY", f"{f.name} — {len(prints)} print() de debug (envisager logging)")

    # Fichier tatus (résidu) à la racine
    for f in ROOT.iterdir():
        if f.is_file() and f.name in {"tatus", "status", "tmp", "temp"}:
            W("QUALITY", f"Fichier résidu à la racine : '{f.name}' — probablement à supprimer")

# ─────────────────────────────────────────────
# 9. LOGS RUNTIME — erreurs réelles en production
# ─────────────────────────────────────────────
def check_logs():
    log_path = ROOT / "orchestrator.log"
    if not log_path.exists():
        I("LOGS", "orchestrator.log absent — pipeline jamais lancé ou log non configuré")
        return
    lines = read(log_path).splitlines()
    errors   = [l for l in lines if "ERROR" in l or "CRITICAL" in l or "Traceback" in l]
    warnings = [l for l in lines if "WARNING" in l or "WARN" in l]
    retries  = [l for l in lines if "retry" in l.lower() or "tentative" in l.lower()]
    if errors:
        E("LOGS", f"{len(errors)} ligne(s) ERROR/CRITICAL dans orchestrator.log")
        for l in errors[-3:]:
            E("LOGS", f"  → {l.strip()[:120]}")
    if retries:
        W("LOGS", f"{len(retries)} retry(s) détecté(s) dans les logs")
    I("LOGS", f"Total lignes log : {len(lines)} | Erreurs : {len(errors)} | Warnings : {len(warnings)} | Retries : {len(retries)}")

# ─────────────────────────────────────────────
# 10. DÉPENDANCES — versions et conflits
# ─────────────────────────────────────────────
def check_deps():
    req = ROOT / "requirements.txt"
    if not req.exists():
        E("DEPS", "requirements.txt absent")
        return
    lines = [l.strip() for l in read(req).splitlines() if l.strip() and not l.startswith("#")]
    no_version = [l for l in lines if not re.search(r"[><=!]", l)]
    if no_version:
        W("DEPS", f"Packages sans version fixée (risque de rupture) : {', '.join(no_version)}")
    I("DEPS", f"{len(lines)} dépendance(s) déclarée(s) dans requirements.txt")

# ─────────────────────────────────────────────
# RAPPORT FINAL
# ─────────────────────────────────────────────
def main():
    print("=" * 65)
    print(" AUDIT COMPLET — Agentic SDLC")
    print(f" Racine : {ROOT}")
    print(f" Fichiers Python analysés : {len(PY_FILES)}")
    print(f" Fichiers HTML analysés   : {len(HTML_FILES)}")
    print("=" * 65)

    checks = [
        ("1. Syntaxe",            check_syntax),
        ("2. Imports",            check_imports),
        ("3. Sécurité",           check_security),
        ("4. Gestion d'erreurs",  check_error_handling),
        ("5. Variables d'env",    check_env),
        ("6. Routes API",         check_routes),
        ("7. Base de données",    check_database),
        ("8. Qualité code",       check_quality),
        ("9. Logs runtime",       check_logs),
        ("10. Dépendances",       check_deps),
    ]

    for label, fn in checks:
        before_e = len(ERRORS)
        before_w = len(WARNINGS)
        before_i = len(INFO)
        try:
            fn()
        except Exception as ex:
            W("AUDIT", f"Erreur dans le check '{label}' : {ex}")
        after_e = len(ERRORS)  - before_e
        after_w = len(WARNINGS) - before_w
        after_i = len(INFO)    - before_i
        status = "✅" if after_e == 0 else "❌"
        print(f"\n{'─'*65}")
        print(f" {status} {label}  [{after_e} err | {after_w} warn | {after_i} info]")
        print(f"{'─'*65}")
        for m in ERRORS[-after_e:]   if after_e else []:   print(f"  {m}")
        for m in WARNINGS[-after_w:] if after_w else []:   print(f"  {m}")
        for m in INFO[-after_i:]     if after_i else []:   print(f"  {m}")

    print(f"\n{'='*65}")
    print(f" RÉSUMÉ : {len(ERRORS)} ERREUR(S)  |  {len(WARNINGS)} AVERTISSEMENT(S)  |  {len(INFO)} INFO(S)")
    print(f"{'='*65}")

    if ERRORS:
        print("\n 🔴 ERREURS À CORRIGER EN PRIORITÉ :")
        for m in ERRORS: print(f"   {m}")
    if WARNINGS:
        print("\n 🟡 AVERTISSEMENTS :")
        for m in WARNINGS: print(f"   {m}")
    print()

if __name__ == "__main__":
    main()