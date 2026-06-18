import requests
from bs4 import BeautifulSoup
import argparse

def get_session_id(username, password):
    login_url = "https://arms.sse.saveetha.com/"
    
    # Use a session to persist cookies
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    })
    
    print("Fetching login page...")
    resp = session.get(login_url)
    if resp.status_code != 200:
        print(f"Failed to load login page. Status code: {resp.status_code}")
        return None
        
    # Parse the page to find the ASP.NET hidden fields
    soup = BeautifulSoup(resp.text, 'html.parser')
    viewstate = soup.find('input', {'name': '__VIEWSTATE'})
    viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
    eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
    
    if not viewstate:
        print("Could not find __VIEWSTATE on the page.")
        return None

    # Prepare login data
    payload = {
        '__VIEWSTATE': viewstate.get('value', '') if viewstate else '',
        '__VIEWSTATEGENERATOR': viewstategenerator.get('value', '') if viewstategenerator else '',
        '__EVENTVALIDATION': eventvalidation.get('value', '') if eventvalidation else '',
        'txtusername': username,
        'txtpassword': password,
        'btnlogin': 'Login'
    }
    
    print("Logging in...")
    post_resp = session.post(login_url, data=payload)
    
    # Extract the session ID cookie
    cookies = session.cookies.get_dict()
    session_id = cookies.get('ASP.NET_SessionId')
    
    if session_id:
        print("\nLogin Successful!")
        print(f"Your ASP.NET_SessionId is: {session_id}")
        print("\nYou can use this value in your requests or postman.")
    else:
        print("\nLogin Failed. Could not find ASP.NET_SessionId cookie.")
        print("Please check if your username and password are correct.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Get ARMS Session ID')
    parser.add_argument('--username', required=True, help='Your ARMS username')
    parser.add_argument('--password', required=True, help='Your ARMS password')
    args = parser.parse_args()
    
    get_session_id(args.username, args.password)
