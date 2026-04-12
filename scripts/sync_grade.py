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
    github_username = results["github_username"]
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
        "component": "mod_assign",
        "courseid": course_id,
        "activityid": activity_id,
        "source": "GitHub Classroom",
        "grades[0][studentid]": student_id,
        "grades[0][grade]": results["score"],
    }

    response = requests.post(moodle_url, data=payload, timeout=30)
    response.raise_for_status()
    print(response.text)


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
