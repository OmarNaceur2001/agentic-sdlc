"""
Generator for Mock ML Dataset — Agentic SDLC v3
Génère 50+ runs de pipeline réalistes dans la base SQLite pour l'entraînement du modèle Random Forest.
"""

import sqlite3
import random
from datetime import datetime, timedelta

def generer_donnees():
    db_path = "pipeline_runs.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # S'assurer que la table existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            test_passed INTEGER,
            run_id TEXT,
            created_at TEXT,
            retry_number INTEGER,
            prompt_version TEXT,
            generation_time_sec REAL,
            has_doctype INTEGER,
            has_title_tag INTEGER,
            has_button INTEGER,
            has_body INTEGER,
            has_head INTEGER,
            css_rules_count INTEGER,
            js_scripts_count INTEGER,
            js_length INTEGER,
            html_length INTEGER,
            keyword_coverage REAL,
            playwright_load_ok INTEGER,
            visible_text_length INTEGER,
            js_errors_count INTEGER,
            console_errors_count INTEGER,
            playwright_load_time_ms REAL
        )
    """)

    tickets_templates = [
        {"summary": "Create a todo list app", "base_key": "SCRUM-20"},
        {"summary": "Create a BMI calculator", "base_key": "SCRUM-21"},
        {"summary": "Create a registration form", "base_key": "SCRUM-22"},
        {"summary": "Create a weather dashboard", "base_key": "SCRUM-23"},
        {"summary": "Create a landing page for a coffee shop", "base_key": "SCRUM-24"},
        {"summary": "Create a recipe finder app", "base_key": "SCRUM-25"},
        {"summary": "Create a pomodoro timer", "base_key": "SCRUM-26"},
        {"summary": "Create a currency converter", "base_key": "SCRUM-27"},
        {"summary": "Create a markdown previewer", "base_key": "SCRUM-28"},
        {"summary": "Create a personal portfolio website", "base_key": "SCRUM-29"},
    ]

    base_time = datetime.now() - timedelta(days=5)
    inserted_count = 0

    # On simule plusieurs runs pour chaque ticket (retries)
    for index, template in enumerate(tickets_templates):
        ticket_id = template["base_key"]
        
        # Simuler 3 tentatives (2 échecs, puis 1 succès ou abandon)
        for retry in range(3):
            created_at = (base_time + timedelta(hours=index * 12 + retry * 2)).isoformat()
            run_id = f"run-{ticket_id}-{retry}"
            
            # Paramètres de simulation en fonction de la tentative
            if retry == 0:
                # Premier essai : souvent des erreurs structurelles ou JS
                test_passed = 0
                has_doctype = random.choice([0, 1])
                has_title_tag = random.choice([0, 1])
                has_button = random.choice([0, 1])
                has_body = 1
                has_head = random.choice([0, 1])
                css_rules_count = random.randint(2, 10)
                js_scripts_count = random.randint(1, 3)
                js_length = random.randint(100, 500)
                html_length = random.randint(400, 1500)
                keyword_coverage = round(random.uniform(0.3, 0.6), 4)
                playwright_load_ok = random.choice([0, 1])
                visible_text_length = random.randint(10, 150) if playwright_load_ok else 0
                js_errors_count = random.randint(1, 4)
                console_errors_count = random.randint(1, 5)
                playwright_load_time_ms = round(random.uniform(500.0, 4500.0), 2)
                generation_time_sec = round(random.uniform(15.0, 25.0), 2)
            
            elif retry == 1:
                # Deuxième essai : amélioration mais encore quelques soucis
                test_passed = 0
                has_doctype = 1
                has_title_tag = 1
                has_button = 1
                has_body = 1
                has_head = 1
                css_rules_count = random.randint(10, 25)
                js_scripts_count = random.randint(1, 2)
                js_length = random.randint(300, 1000)
                html_length = random.randint(1500, 3500)
                keyword_coverage = round(random.uniform(0.5, 0.75), 4)
                playwright_load_ok = 1
                visible_text_length = random.randint(100, 400)
                js_errors_count = random.choice([0, 1])
                console_errors_count = random.randint(0, 2)
                playwright_load_time_ms = round(random.uniform(300.0, 1500.0), 2)
                generation_time_sec = round(random.uniform(18.0, 30.0), 2)

            else:
                # Troisième essai : 80% de chance de réussite
                test_passed = random.choice([1, 1, 1, 1, 0])
                has_doctype = 1
                has_title_tag = 1
                has_button = 1
                has_body = 1
                has_head = 1
                css_rules_count = random.randint(20, 50)
                js_scripts_count = random.randint(1, 2)
                js_length = random.randint(500, 2500)
                html_length = random.randint(3000, 8000)
                keyword_coverage = round(random.uniform(0.7, 0.98), 4)
                playwright_load_ok = 1
                visible_text_length = random.randint(300, 1200)
                js_errors_count = 0 if test_passed else 1
                console_errors_count = 0 if test_passed else 1
                playwright_load_time_ms = round(random.uniform(150.0, 800.0), 2)
                generation_time_sec = round(random.uniform(20.0, 35.0), 2)

            cursor.execute("""
                INSERT INTO pipeline_runs (
                    ticket_id, test_passed, run_id, created_at,
                    retry_number, prompt_version, generation_time_sec,
                    has_doctype, has_title_tag, has_button, has_body, has_head,
                    css_rules_count, js_scripts_count, js_length, html_length,
                    keyword_coverage, playwright_load_ok, visible_text_length,
                    js_errors_count, console_errors_count, playwright_load_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_id, test_passed, run_id, created_at,
                retry, "v1", generation_time_sec,
                has_doctype, has_title_tag, has_button, has_body, has_head,
                css_rules_count, js_scripts_count, js_length, html_length,
                keyword_coverage, playwright_load_ok, visible_text_length,
                js_errors_count, console_errors_count, playwright_load_time_ms
            ))
            inserted_count += 1
            
            # Si le test a réussi, on arrête les tentatives pour ce ticket
            if test_passed == 1:
                break

    # Générer d'autres runs aléatoires pour arriver à 50+
    for idx in range(30):
        ticket_id = f"SCRUM-{30 + idx}"
        retry = random.choice([0, 1])
        test_passed = random.choice([1, 1, 0])
        created_at = (base_time + timedelta(days=random.randint(1, 4), hours=random.randint(0, 23))).isoformat()
        run_id = f"run-{ticket_id}-{retry}"

        has_doctype = 1 if test_passed else random.choice([0, 1])
        has_title_tag = 1 if test_passed else random.choice([0, 1])
        has_button = 1
        has_body = 1
        has_head = 1
        css_rules_count = random.randint(15, 60)
        js_scripts_count = random.randint(0, 3)
        js_length = random.randint(0, 3000)
        html_length = random.randint(2000, 9000)
        keyword_coverage = round(random.uniform(0.65, 0.99), 4) if test_passed else round(random.uniform(0.2, 0.6), 4)
        playwright_load_ok = 1 if test_passed else random.choice([0, 1])
        visible_text_length = random.randint(200, 1500) if playwright_load_ok else 0
        js_errors_count = 0 if test_passed else random.randint(1, 3)
        console_errors_count = 0 if test_passed else random.randint(1, 4)
        playwright_load_time_ms = round(random.uniform(100.0, 700.0), 2) if test_passed else round(random.uniform(800.0, 3500.0), 2)
        generation_time_sec = round(random.uniform(18.0, 35.0), 2)

        cursor.execute("""
            INSERT INTO pipeline_runs (
                ticket_id, test_passed, run_id, created_at,
                retry_number, prompt_version, generation_time_sec,
                has_doctype, has_title_tag, has_button, has_body, has_head,
                css_rules_count, js_scripts_count, js_length, html_length,
                keyword_coverage, playwright_load_ok, visible_text_length,
                js_errors_count, console_errors_count, playwright_load_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id, test_passed, run_id, created_at,
            retry, "v1", generation_time_sec,
            has_doctype, has_title_tag, has_button, has_body, has_head,
            css_rules_count, js_scripts_count, js_length, html_length,
            keyword_coverage, playwright_load_ok, visible_text_length,
            js_errors_count, console_errors_count, playwright_load_time_ms
        ))
        inserted_count += 1

    conn.commit()
    conn.close()
    print(f"Base SQLite alimentée avec {inserted_count} nouveaux runs réalistes.")

if __name__ == "__main__":
    generer_donnees()
