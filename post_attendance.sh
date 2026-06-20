#!/usr/bin/env bash
# post_attendance.sh – post attendance for a given course ID, CSV list, or via ARMS API using a subject ID.
#
# Usage:
#   ./post_attendance.sh -c <COURSE_ID>          # Post attendance for a single 5‑digit course ID.
#   ./post_attendance.sh -f <CSV_FILE>           # Post attendance for all courses listed in CSV (default: slot_c.csv).
#   ./post_attendance.sh -s <SUBJECT_ID>         # Fetch course list from ARMS API and post attendance for the matching subject ID.
#   ./post_attendance.sh -t <TYPE>                # Attendance type (default: ABS, others: PR, etc).
#   ./post_attendance.sh -h                     # Show this help.
#
# The CSV must have a header line and rows like:
#   SubjectId,SubjectCode
#   41205,SomeCourse
# The first column (SubjectId) is the 5‑digit course ID.
#
# The script posts to the Flask endpoint /api/submit. Adjust BASE_URL if your server runs elsewhere.

set -euo pipefail

# ----- Configuration -------------------------------------------------
BASE_URL="http://localhost:5000"                 # Change if your server runs elsewhere.
DEFAULT_CSV="$(pwd)/slot_c.csv"                 # Default CSV file containing course IDs.
ATTENDANCE_TYPE="ABS"                           # Default attendance type.
# ARMS API endpoint that returns a JSON array of courses.
COURSE_API_URL="https://arms.sse.saveetha.com/Handler/Administration.ashx?Page=GETCOURSEBYSELECTPGM&Mode=RUNDROPDOWN&Id=0"
# --------------------------------------------------------------------

usage() {
  cat <<EOF
$(basename "$0") – post attendance via the ARMS API.

Options:
  -c <COURSE_ID>   Post attendance for a single 5‑digit course ID.
  -f <CSV_FILE>    CSV file containing course IDs (default: ${DEFAULT_CSV}).
  -s <SUBJECT_ID>  Fetch course list from ARMS API and post attendance for the matching subject ID.
  -l               List available courses from the ARMS API.
  -t <TYPE>        Attendance type (default: ${ATTENDANCE_TYPE}).
  -h               Show this help message.

Examples:
  $0 -c 41205
  $0 -f ${DEFAULT_CSV}
  $0 -s 12345 -t PR
  $0 -l
EOF
  exit 0
}

# ----- Helper: post attendance for a given course -------------------
post_attendance() {
  local cid="$1"
  echo "Posting attendance ($ATTENDANCE_TYPE) for course ID $cid..."
  curl -s -X POST "${BASE_URL}/api/submit" \
    -H "Content-Type: application/json" \
    -d "{\"course_id\": \"${cid}\", \"student_id_list\": \"\", \"type\": \"${ATTENDANCE_TYPE}\"}" \
    -w "\nHTTP %{http_code}\n"
  echo "---"
}

# ----- Helper: fetch course ID for a given subject ID ---------------
fetch_course_id_by_subject() {
  local subject_id="$1"
  # Fetch the full course list from ARMS API
  local response=$(curl -s "$COURSE_API_URL")
  if [[ -z "$response" ]]; then
    echo "Error: Empty response from ARMS API" >&2
    return 1
  fi
  # Ensure jq is installed
  if ! command -v jq > /dev/null 2>&1; then
    echo "Error: jq is required to parse JSON. Please install jq and retry." >&2
    return 1
  fi
  # Find matching subject
  local course_id=$(echo "$response" | jq -r --arg sid "$subject_id" '.[] | select(.SubjectId == ($sid|tonumber)) | .SubjectId')
  if [[ -z "$course_id" ]]; then
    echo "Error: No course found for subject ID ${subject_id}" >&2
    return 1
  fi
  echo "$course_id"
}
# ----- Helper: list available courses from ARMS API
list_courses() {
  local response=$(curl -s "$COURSE_API_URL")
  if [[ -z "$response" ]]; then
    echo "Error: Empty response from ARMS API" >&2
    return 1
  fi
  if ! command -v jq > /dev/null 2>&1; then
    echo "Error: jq is required to parse JSON. Please install jq and retry." >&2
    return 1
  fi
  echo "Available courses:"
  echo "$response" | jq -r '.[] | "\(.SubjectId) - \(.SubjectCode)"'
}


# ----- Parse command‑line options ----------------------------------
while getopts "c:f:s:t:lh" opt; do
  case $opt in
    c) SINGLE_COURSE="$OPTARG" ;;
    f) CSV_FILE="$OPTARG" ;;
    s) SUBJECT_ID="$OPTARG" ;;
    t) ATTENDANCE_TYPE="$OPTARG" ;;
    l) list_courses; exit 0 ;;
    h) usage ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage ;;
    :) echo "Option -$OPTARG requires an argument." >&2; usage ;;
  esac
done

# ----- Single course mode ------------------------------------------
if [[ -n "${SINGLE_COURSE:-}" ]]; then
  if [[ ! "$SINGLE_COURSE" =~ ^[0-9]{5}$ ]]; then
    echo "Error: Course ID must be a 5‑digit number." >&2
    exit 1
  fi
  post_attendance "$SINGLE_COURSE"
  exit 0
fi

# ----- Subject ID mode (API) ---------------------------------------
if [[ -n "${SUBJECT_ID:-}" ]]; then
  cid=$(fetch_course_id_by_subject "$SUBJECT_ID")
  if [[ -n "$cid" ]]; then
    post_attendance "$cid"
    exit 0
  else
    exit 1
  fi
fi

# ----- CSV mode ---------------------------------------------------
CSV_FILE="${CSV_FILE:-$DEFAULT_CSV}"
if [[ ! -f "$CSV_FILE" ]]; then
  echo "Error: CSV file '$CSV_FILE' not found." >&2
  exit 1
fi

echo "Reading course IDs from $CSV_FILE..."
# Skip header, extract first column (SubjectId) which is the 5‑digit ID.
tail -n +2 "$CSV_FILE" | while IFS=, read -r course_id _; do
  course_id=$(echo "$course_id" | tr -d ' \t\r')
  if [[ "$course_id" =~ ^[0-9]{5}$ ]]; then
    post_attendance "$course_id"
  elif [[ -n "$course_id" ]]; then
    echo "Skipping invalid line: $course_id"
  fi
done

echo "All done."
