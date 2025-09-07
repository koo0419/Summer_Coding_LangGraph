# FINAL_PROJECT/tools/gmail_tool.py

# Gmail 인증 + 메일 전송 함수
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
import os

# 스코프 설정
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CREDENTIALS_PATH = 'credentials/credentials.json'
TOKEN_PATH = 'credentials/token.json'

# 인증
def gmail_authenticate():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# 이메일 전송
def send_email(service, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['subject'] = subject
    encoded_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
    
    send_message = service.users().messages().send(userId='me', body=encoded_message).execute()
    print(f"Message Id: {send_message['id']}")
    return send_message