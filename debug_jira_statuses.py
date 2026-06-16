import os
import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")

AUTH = (JIRA_EMAIL, JIRA_TOKEN)
HEADERS = {"Accept": "application/json"}


def main():
    print("=" * 60)
    print(" Diagnostic Jira — Projects visibles")
    print("=" * 60)

    response = requests.get(
        f"{JIRA_URL}/rest/api/3/project/search",
        auth=AUTH,
        headers=HEADERS,
        timeout=20,
    )

    print("HTTP STATUS:", response.status_code)

    if response.status_code != 200:
        print(response.text[:1000])
        return

    data = response.json()
    projects = data.get("values", [])

    print(f"Nombre de projets visibles : {len(projects)}")
    print()

    for project in projects:
        print(f"KEY  : {project.get('key')}")
        print(f"NAME : {project.get('name')}")
        print(f"ID   : {project.get('id')}")
        print("-" * 50)


if __name__ == "__main__":
    main()