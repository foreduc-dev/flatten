#!/usr/bin/env bash
# post_attendance.sh – post attendance for a given course or for all courses in a CSV file.
#
# Usage:
#   ./post_attendance.sh -c <COURSE_ID>          # post attendance for a single course ID (5‑digit)
#   ./post_attendance.sh -f <CSV_FILE>           # post attendance for all courses listed in CSV (default: slot_c.csv)
#   ./post_attendance.sh -h                     # show this help
#
# The CSV must have a header line and rows like:
#   SubjectId,SubjectCode
#   41205,SomeCourse
# The first column (SubjectId) is the 5‑digit course ID.
#
# The script posts to the Flask endpoint /api/submit.
# Adjust BASE_URL if your server runs elsewhere.

set -euo pipefail

# ----- Configuration -------------------------------------------------
BASE_URL="http://localhost:5000"   # change if your server runs elsewhere
DEFAULT_CSV="$(pwd)/slot_c.csv"   # default CSV file containing course IDs
# --------------------------------------------------------------------

usage() {
  cat << EOF
$(basename "$0") – post attendance via the ARMS API.

Options:
  -c <COURSE_ID>   Post attendance for a single 5‑digit course ID.
  -f <CSV_FILE>    CSV file containing course IDs (default: ${DEFAULT_CSV}).
  -h               Show this help message.

Examples:
  $0 -c 41205
  $0 -f ${DEFAULT_CSV}
  $0 -f my_new_courses.csv
EOF
  exit 0
}

# Parse options
while getopts ":c:f:h" opt; do
  case $opt in
    c) SINGLE_COURSE="$OPTARG" ;;
    f) CSV_FILE="$OPTARG" ;;
    h) usage ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage ;;
    :) echo "Option -$OPTARG requires an argument." >&2; usage ;;
  esac
done

# ----- Helper: post attendance for a given course -------------------
post_attendance() {
  local cid="$1"
  echo "Posting attendance for course ID $cid..."
  curl -s -X POST "${BASE_URL}/api/submit" \
    -H "Content-Type: application/json" \
    -d "{\"course_id\": \"${cid}\", \"student_id_list\": \"\", \"type\": \"ABS\"}" \
    -w "\nHTTP %{http_code}\n"
  echo "---"
}

# ----- Single course mode ------------------------------------------
if [[ -n "${SINGLE_COURSE:-}" ]]; then
  if [[ ! "$SINGLE_COURSE" =~ ^[0-9]{5}$ ]]; then
    echo "Error: Course ID must be a 5‑digit number." >&2
    exit 1
  fi
  post_attendance "$SINGLE_COURSE"
  exit 0
fi

# ----- CSV mode ---------------------------------------------------
CSV_FILE="${CSV_FILE:-$DEFAULT_CSV}"
if [[ ! -f "$CSV_FILE" ]]; then
  echo "Error: CSV file '$CSV_FILE' not found." >&2
  exit 1
fi

echo "Reading course IDs from $CSV_FILE..."
# Skip header, extract first column (SubjectId) which is the 5‑digit ID
tail -n +2 "$CSV_FILE" | while IFS=, read -r course_id _; do
  course_id=$(echo "$course_id" | tr -d ' \t')
  if [[ "$course_id" =~ ^[0-9]{5}$ ]]; then
    post_attendance "$course_id"
  else
    echo "Skipping invalid line: $course_id"
  fi
done

echo "All done."
