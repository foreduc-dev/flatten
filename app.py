from flask import Flask, request, jsonify, render_template, Response
import requests
from bs4 import BeautifulSoup
import time
from functools import wraps

app = Flask(__name__)

BASE_URL = "https://arms.sse.saveetha.com"
USERNAME = "Ssetssh239"
PASSWORD = "Ssetssh239"
USER_ID = "1141"

cached_session = None
cookie_timestamp = 0

def _get_logged_in_session(force_refresh=False):
    global cached_session, cookie_timestamp
    if not force_refresh and cached_session and (time.time() - cookie_timestamp < 900):
        return cached_session

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Referer": f"{BASE_URL}/FacultyPortal/Attendance.aspx"
    })

    resp = session.get(BASE_URL, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Failed to load login page. Status: {resp.status_code}")

    soup = BeautifulSoup(resp.text, 'html.parser')
    viewstate = soup.find('input', {'name': '__VIEWSTATE'})
    viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
    eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

    payload = {
        '__VIEWSTATE': viewstate.get('value', '') if viewstate else '',
        '__VIEWSTATEGENERATOR': viewstategenerator.get('value', '') if viewstategenerator else '',
        '__EVENTVALIDATION': eventvalidation.get('value', '') if eventvalidation else '',
        'txtusername': USERNAME,
        'txtpassword': PASSWORD,
        'btnlogin': 'Login'
    }

    post_resp = session.post(BASE_URL, data=payload, timeout=15)
    
    # Check if login was successful by checking if ASP.NET_SessionId exists or if we got redirected
    cookies = session.cookies.get_dict()
    if 'ASP.NET_SessionId' not in cookies:
        raise Exception("Login failed. Check hardcoded username/password.")

    cached_session = session
    cookie_timestamp = time.time()
    return session

def check_auth(username, password):
    # Set your desired username and password here for accessing the web app
    return username == 'admin' and password == 'saveetha'

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route("/")
@requires_auth
def index():
    return render_template("index.html")

@app.route("/api/attendance", methods=["POST"])
@requires_auth
def get_attendance():
    data = request.json
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"error": "course_id is required"}), 400

    try:
        req_session = _get_logged_in_session()
        url = f"{BASE_URL}/Handler/Fees.ashx"
        params = {
            "Page": "StudentByCourseSection",
            "Mode": "GETDATABYPGMCOURSE",
            "StudentId": USER_ID,
            "CourseId": course_id,
            "SectionId": "0"
        }

        resp = req_session.get(url, params=params, timeout=15)

        # If session is invalid, try fetching a new session once
        if resp.text.strip().startswith("<"):
            req_session = _get_logged_in_session(force_refresh=True)
            resp = req_session.get(url, params=params, timeout=15)
            
            if resp.text.strip().startswith("<"):
                return jsonify({"error": "Session error even after relogin."}), 401

        students = resp.json()
        return jsonify({"success": True, "students": students})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/courses", methods=["POST"])
@requires_auth
def get_courses():
    try:
        req_session = _get_logged_in_session()
        url = f"{BASE_URL}/Handler/Administration.ashx"
        params = {
            "Page": "CourseApprovePending",
            "Mode": "GETCOURSEBYUSERID",
            "Id": "0"
        }

        resp = req_session.get(url, params=params, timeout=15)

        if resp.text.strip().startswith("<"):
            req_session = _get_logged_in_session(force_refresh=True)
            resp = req_session.get(url, params=params, timeout=15)
            
            if resp.text.strip().startswith("<"):
                return jsonify({"error": "Session error even after relogin."}), 401

        courses = resp.json()
        return jsonify({"courses": courses})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/submit", methods=["POST"])
@requires_auth
def submit_attendance():
    data = request.json
    course_id = data.get("course_id")
    student_id_list = data.get("student_id_list", "")
    submit_type = data.get("type", "")

    if not course_id:
        return jsonify({"error": "course_id is required"}), 400

    try:
        req_session = _get_logged_in_session()
        url = f"{BASE_URL}/FacultyPortal/Attendance.aspx"
        
        # 1. GET request to fetch viewstate
        get_resp = req_session.get(url, timeout=15)
        soup = BeautifulSoup(get_resp.text, 'html.parser')
        
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

        # 2. POST request
        payload = {
            '__EVENTTARGET': 'ctl00$cphbody$btnSubmit',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': viewstate.get('value', '') if viewstate else '',
            '__VIEWSTATEGENERATOR': viewstategenerator.get('value', '') if viewstategenerator else '',
            '__EVENTVALIDATION': eventvalidation.get('value', '') if eventvalidation else '',
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

        post_resp = req_session.post(url, data=payload, timeout=15)
        
        return jsonify({"success": True, "message": "Attendance posted successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
