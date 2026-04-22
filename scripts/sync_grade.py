import argparse
import csv
import json
import os
from pathlib import Path
from typing import Optional

import requests

REPORT_PATH = Path("report.json")
RESULTS_PATH = Path("results.json")
MAP_PATH = Path("github_moodle_map.csv")


def compute_score() -> dict:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    summary = report.get("summary", {})
    total = int(summary.get("total", 0))
    passed = int(summary.get("passed", 0))
    failed = int(summary.get("failed", 0))
    errors = int(summary.get("error", 0))
    max_score = 100
    score = round((passed / total) * max_score, 2) if total else 0.0

    result = {
        "github_username": os.getenv("GITHUB_ACTOR", "unknown"),
        "assignment": os.getenv("ASSIGNMENT_NAME", "FM3 - Python Programming"),
        "score": score,
        "max_score": max_score,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
    }
    RESULTS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def resolve_github_username():
    # First try explicit env var
    github_username = os.getenv("GITHUB_USERNAME", "").strip()
    if github_username and github_username.lower() != "izen-academy":
        return github_username

    # Fallback: derive from repo name
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    # Example: Izen-Academy/fm3-python-programming-izenaiclassroom
    if "/" in repo:
        repo_name = repo.split("/", 1)[1]
    else:
        repo_name = repo

    # Split by hyphen and take the last chunk
    # For fm3-python-programming-izenaiclassroom -> izenaiclassroom
    if "-" in repo_name:
        return repo_name.split("-")[-1]

    raise RuntimeError("Could not determine GitHub username from environment")


def lookup_moodle_student_id(github_username: str) -> Optional[str]:
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Mapping file not found: {MAP_PATH}")
    with MAP_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("github_username", "").strip().lower() == github_username.strip().lower():
                return row.get("moodle_student_id", "").strip()
    return None


def sync_score() -> None:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError("results.json not found. Run compute mode first.")

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    github_username = resolve_github_username()
    print(f"Resolved GitHub username: {github_username}")

    student_id = lookup_moodle_student_id(github_username)
    if not student_id:
        raise RuntimeError(f"No Moodle student id found for GitHub user: {github_username}")

    moodle_url = os.environ["MOODLE_URL"]
    moodle_token = os.environ["MOODLE_TOKEN"]
    course_id = os.environ["MOODLE_COURSE_ID"]
    activity_id = os.environ["MOODLE_ACTIVITY_ID"]

    payload = {
        "wstoken": moodle_token,
        "wsfunction": "core_grades_update_grades",
        "moodlewsrestformat": "json",
        "source": "mod/assign",
        "courseid": course_id,
        "component": "mod_assign",
        "activityid": activity_id,
        "itemnumber": 0,
        "grades[0][studentid]": student_id,
        "grades[0][grade]": results["score"],
    }

    print("Sending Moodle payload:")
    for k, v in payload.items():
        print(f"{k}: {v}")

    response = requests.post(moodle_url, data=payload, timeout=30)
    print("Response status:", response.status_code)
    print("Response body:", response.text)
    response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["compute", "sync"], required=True)
    args = parser.parse_args()

    if args.mode == "compute":
        compute_score()
    else:
        sync_score()


if __name__ == "__main__":
    main()
