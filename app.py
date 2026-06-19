# ──────────────────────────────────────
#  app.py
# ──────────────────────────────────────
from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
import time
from functools import wraps
import os

app = Flask(__name__)

# -----------------------------------------------------------------
# Auto‑logout: clear the session on every request (except login & static)
# -----------------------------------------------------------------
@app.before_request
def auto_logout():
    # Auto-logout disabled – keep session alive after login
    pass


# ----- CONFIG -------------------------------------------------
BASE_URL = "https://arms.sse.saveetha.com"
USERNAME = os.getenv("ARMS_USERNAME", "Ssetssh239")
PASSWORD = os.getenv("ARMS_PASSWORD", "Ssetssh239")
USER_ID  = os.getenv("ARMS_USER_ID",   "1141")

# Flask secret key – required for sessions
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change‑me‑to‑a‑random‑string")

# ----- AUTH ---------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def check_app_auth(username, password):
    app_user = os.getenv("APP_USERNAME", "admin")
    app_pass = os.getenv("APP_PASSWORD", "kpybala")
    return username == app_user and password == app_pass
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        app_user = os.environ.get('APP_USERNAME', 'admin')
        app_pass = os.environ.get('APP_PASSWORD', 'kpybala')
        if username == app_user and password == app_pass:
            session['logged_in'] = True
            session['allow_next'] = True  # allow immediate home view after login
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('login'))

# ----- ROUTES -------------------------------------------------
@app.route('/')
def home():
    """Home route – shows login if not authenticated, else main app."""
    if session.get('logged_in'):
        return render_template('index.html')
    return redirect(url_for('login'))

# The `/login` route already handles GET (show form) and POST (process credentials).
# No additional route needed.

# ----- API ENDPOINTS (protected) -------------------------------
# Cached ARMS session
cached_session = None
cookie_timestamp = 0

def _get_logged_in_session(force_refresh=False):
    global cached_session, cookie_timestamp
    if not force_refresh and cached_session and (time.time() - cookie_timestamp < 900):
        return cached_session
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Referer": f"{BASE_URL}/FacultyPortal/Attendance.aspx"
    })
    # initial GET to obtain viewstate
    resp = sess.get(BASE_URL, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Failed to load ARMS login page: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")
    viewstate = soup.find('input', {'name': '__VIEWSTATE'})
    viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
    eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
    payload = {
        '__VIEWSTATE': viewstate.get('value','') if viewstate else '',
        '__VIEWSTATEGENERATOR': viewstategenerator.get('value','') if viewstategenerator else '',
        '__EVENTVALIDATION': eventvalidation.get('value','') if eventvalidation else '',
        'txtusername': USERNAME,
        'txtpassword': PASSWORD,
        'btnlogin': 'Login'
    }
    post_resp = sess.post(BASE_URL, data=payload, timeout=15)
    if 'ASP.NET_SessionId' not in sess.cookies.get_dict():
        raise Exception("Login to ARMS failed. Check credentials.")
    cached_session = sess
    cookie_timestamp = time.time()
    return sess

@app.route("/api/attendance", methods=["GET", "POST"])
@login_required
def get_attendance():
    data = request.json or {}
    course_id = data.get('course_id')
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400
    try:
        sess = _get_logged_in_session()
        url = f"{BASE_URL}/Handler/Fees.ashx"
        params = {
            "Page": "StudentByCourseSection",
            "Mode": "GETDATABYPGMCOURSE",
            "StudentId": USER_ID,
            "CourseId": course_id,
            "SectionId": "0"
        }
        resp = sess.get(url, params=params, timeout=15)
        if resp.text.strip().startswith("<"):
            sess = _get_logged_in_session(force_refresh=True)
            resp = sess.get(url, params=params, timeout=15)
            if resp.text.strip().startswith("<"):
                return jsonify({"error": "Session error after relogin."}), 401
        students = resp.json()
        return jsonify({"success": True, "students": students})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/courses", methods=["GET", "POST"])
@login_required
def get_courses():
    try:
        sess = _get_logged_in_session()
        url = f"{BASE_URL}/Handler/Administration.ashx"
        params = {"Page": "CourseApprovePending", "Mode": "GETCOURSEBYUSERID", "Id": "0"}
        resp = sess.get(url, params=params, timeout=15)
        if resp.text.strip().startswith("<"):
            sess = _get_logged_in_session(force_refresh=True)
            resp = sess.get(url, params=params, timeout=15)
            if resp.text.strip().startswith("<"):
                return jsonify({"error": "Session error after relogin."}), 401
        courses = resp.json()
        return jsonify({"courses": courses})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/submit", methods=["POST"])
@login_required
def submit_attendance():
    data = request.json or {}
    course_id = data.get('course_id')
    student_id_list = data.get('student_id_list', "")
    submit_type = data.get('type', "")
    if not course_id:
        return jsonify({"error": "course_id is required"}), 400
    try:
        sess = _get_logged_in_session()
        # fetch viewstate from attendance page
        page_url = f"{BASE_URL}/FacultyPortal/Attendance.aspx"
        get_resp = sess.get(page_url, timeout=15)
        soup = BeautifulSoup(get_resp.text, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
        payload = {
            '__EVENTTARGET': 'ctl00$cphbody$btnSubmit',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': viewstate.get('value','') if viewstate else '',
            '__VIEWSTATEGENERATOR': viewstategenerator.get('value','') if viewstategenerator else '',
            '__EVENTVALIDATION': eventvalidation.get('value','') if eventvalidation else '',
            'ctl00$cphbody$ddlGraduationType': '0',
            'ctl00$cphbody$ddlCourse': course_id,
            'ctl00$cphbody$HdnCourseId': course_id,
            'ctl00$cphbody$HdnCollgeId': '1',
            'ctl00$cphbody$HdnGraduationId': '0',
            'ctl00$cphbody$hdnStudentIdList': student_id_list,
            'ctl00$cphbody$hdnType': submit_type,
            'ctl00$cphbody$hdnUserId': USER_ID,
            'ctl00$hdngradeid': '0',
            'ctl00$hdnfeedback': '2'
        }
        post_resp = sess.post(page_url, data=payload, timeout=15)
        return jsonify({"success": True, "message": "Attendance posted successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------
from flask import send_from_directory

@app.route('/slot_c.csv')
def serve_slot_csv():
    return send_from_directory(os.path.abspath(os.path.dirname(__file__)), 'slot_c.csv')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
