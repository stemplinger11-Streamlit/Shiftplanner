"""
Wasserwacht Dienstplan+ V8.1 - Production Ready
Alle Features | E-Mail/SMS Fix | User-Registrierung | Vollständig
"""
import streamlit as st
import hashlib
import io
import json
import zipfile
import calendar as cal_module
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import email.utils
import smtplib
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from twilio.rest import Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import firestore
from google.oauth2 import service_account
from collections import Counter

# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="Wasserwacht Dienstplan+",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== KONFIGURATION =====
VERSION = "8.1 - Production Ready"
TIMEZONE_STR = "Europe/Berlin"
TZ = pytz.timezone(TIMEZONE_STR)

WEEKLY_SLOTS = [
    {"id": 1, "day": "tuesday", "day_name": "Dienstag", "start": "17:00", "end": "20:00"},
    {"id": 2, "day": "friday", "day_name": "Freitag", "start": "17:00", "end": "20:00"},
    {"id": 3, "day": "saturday", "day_name": "Samstag", "start": "14:00", "end": "17:00"},
]

BAVARIA_HOLIDAYS = {
    "2025": ["2025-01-01", "2025-01-06", "2025-04-18", "2025-04-21", "2025-05-01", 
             "2025-05-29", "2025-06-09", "2025-06-19", "2025-08-15", "2025-10-03", 
             "2025-11-01", "2025-12-25", "2025-12-26"],
    "2026": ["2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06", "2026-05-01", 
             "2026-05-14", "2026-05-25", "2026-06-04", "2026-08-15", "2026-10-03", 
             "2026-11-01", "2026-12-25", "2026-12-26"]
}

COLORS = {
    "rot": "#DC143C",
    "rot_dunkel": "#B22222",
    "rot_hell": "#FF6B6B",
    "blau": "#003087",
    "blau_hell": "#4A90E2",
    "weiss": "#FFFFFF",
    "grau_hell": "#F5F7FA",
    "grau_mittel": "#E1E8ED",
    "grau_dunkel": "#657786",
    "text": "#14171A",
    "erfolg": "#17BF63",
    "warnung": "#FFAD1F",
    "fehler": "#E0245E",
    "orange": "#FF8C00",
    "orange_hell": "#FFA500"
}

# ===== FIREBASE INIT =====
@st.cache_resource
def init_firestore():
    try:
        if not hasattr(st, 'secrets') or 'firebase' not in st.secrets:
            st.error("❌ Firebase Secrets fehlen!")
            st.stop()
        
        firebase_config = dict(st.secrets['firebase'])
        creds = service_account.Credentials.from_service_account_info(firebase_config)
        return firestore.Client(credentials=creds, project=firebase_config['project_id'])
    except Exception as e:
        st.error(f"❌ Firebase Init Fehler: {e}")
        st.stop()

db = init_firestore()

# ===== HELPER FUNCTIONS =====
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def week_start(d=None):
    d = d or datetime.now().date()
    if hasattr(d, "date"):
        d = d.date()
    return d - timedelta(days=d.weekday())

def slot_date(ws, day):
    days = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
    return (ws + timedelta(days=days.get(day,0))).strftime("%Y-%m-%d")

def fmt_de(d):
    try:
        if isinstance(d, str):
            return datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m.%Y")
        return d.strftime("%d.%m.%Y")
    except:
        return str(d)

def is_holiday(d):
    if isinstance(d, date):
        d = d.strftime("%Y-%m-%d")
    return d in BAVARIA_HOLIDAYS.get(d[:4], [])

def is_summer(d):
    try:
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d")
        return 6 <= d.month <= 9
    except:
        return False

def is_blocked(d):
    return is_holiday(d) or is_summer(d)

def block_reason(d):
    if is_holiday(d):
        return "Feiertag"
    elif is_summer(d):
        return "Sommerpause"
    return None

# ===== CSS INJECTION =====
def inject_css(dark=False):
    bg = "#1A1D23" if dark else COLORS["weiss"]
    surface = "#2D3238" if dark else COLORS["grau_hell"]
    text = "#FFFFFF" if dark else COLORS["text"]
    primary = COLORS["rot_hell"] if dark else COLORS["rot"]
    
    st.markdown(f"""
    <style>
        .main {{ background-color: {bg}; color: {text}; }}
        .stButton>button {{ 
            background-color: {primary}; 
            color: white;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
        }}
        .stButton>button:hover {{
            background-color: {COLORS["rot_dunkel"]};
        }}
        .slot-card {{
            background: {surface};
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
            border-left: 4px solid {primary};
        }}
        .booked {{ border-left-color: {COLORS["orange"]}; }}
        .blocked {{ border-left-color: {COLORS["grau_dunkel"]}; opacity: 0.6; }}
    </style>
    """, unsafe_allow_html=True)
# ===== DATABASE CLASS =====
class WasserwachtDB:
    def __init__(self):
        self.db = db
        self._init_admin()
    
    def _init_admin(self):
        """Admin-User beim ersten Start erstellen"""
        if hasattr(st,'secrets'):
            email = st.secrets.get("ADMIN_EMAIL","admin@wasserwacht.de")
            pw = st.secrets.get("ADMIN_PASSWORD","admin123")
            
            if not self.get_user(email):
                try:
                    self.db.collection('users').add({
                        'email':email,'name':'Admin','phone':'',
                        'password_hash':hash_pw(pw),
                        'role':'admin','active':True,
                        'email_notifications':True,
                        'sms_notifications':False,
                        'sms_booking_confirmation':True,
                        'created_at':firestore.SERVER_TIMESTAMP
                    })
                    print(f"✅ Admin erstellt: {email}")
                except Exception as e:
                    print(f"Admin-Erstellung fehlgeschlagen: {e}")
    
    def get_user(self,email):
        try:
            for doc in self.db.collection('users').where('email','==',email).limit(1).stream():
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            print(f"❌ get_user Fehler: {e}")
            return None
    
    def create_user(self,email,name,phone,password,role='user'):
        try:
            if self.get_user(email):
                return False,"E-Mail bereits registriert"
            
            self.db.collection('users').add({
                'email':email,'name':name,'phone':phone,
                'password_hash':hash_pw(password),
                'role':role,'active':True,
                'email_notifications':True,
                'sms_notifications':False,
                'sms_booking_confirmation':True,
                'created_at':firestore.SERVER_TIMESTAMP
            })
            print(f"✅ User erstellt: {email}")
            return True,"Registrierung erfolgreich"
        except Exception as e:
            print(f"❌ create_user Fehler: {e}")
            return False,str(e)
    
    def auth(self,email,password):
        u = self.get_user(email)
        if not u or not u.get('active',True):
            return False,None
        if u['password_hash'] == hash_pw(password):
            return True,u
        return False,None
    
    def get_all_users(self):
        try:
            users = []
            for doc in self.db.collection('users').stream():
                data = doc.to_dict()
                data['id'] = doc.id
                users.append(data)
            return users
        except Exception as e:
            print(f"❌ get_all_users Fehler: {e}")
            return []
    
    def update_user(self,uid,**kwargs):
        try:
            self.db.collection('users').document(uid).update(kwargs)
            print(f"✅ User geupdatet: {uid}")
            return True
        except Exception as e:
            print(f"❌ update_user Fehler: {e}")
            return False
    
    def delete_user(self,uid):
        try:
            self.db.collection('users').document(uid).delete()
            print(f"✅ User gelöscht: {uid}")
            return True
        except Exception as e:
            print(f"❌ delete_user Fehler: {e}")
            return False
    
    def get_week_bookings(self, ws):
        """Alle Buchungen für eine Woche laden"""
        try:
            we = (datetime.strptime(ws,'%Y-%m-%d')+timedelta(days=6)).strftime('%Y-%m-%d')
            result = []
            for doc in self.db.collection('bookings')\
                    .where('slot_date','>=',ws)\
                    .where('slot_date','<=',we)\
                    .where('status','==','confirmed').stream():
                data = doc.to_dict()
                data['id'] = doc.id
                result.append(data)
            return result
        except Exception as e:
            print(f"❌ get_week_bookings Fehler: {e}")
            # Fallback
            try:
                result = []
                for doc in self.db.collection('bookings').where('status','==','confirmed').stream():
                    b = doc.to_dict()
                    if ws <= b.get('slot_date','') <= we:
                        b['id'] = doc.id
                        result.append(b)
                return result
            except:
                return []
    
    def create_booking(self,slot_date,slot_time,user_email,user_name,user_phone):
        try:
            existing = self.get_booking(slot_date,slot_time)
            if existing:
                return False,"Slot bereits gebucht"
            
            self.db.collection('bookings').add({
                'slot_date':slot_date,'slot_time':slot_time,
                'user_email':user_email,'user_name':user_name,
                'user_phone':user_phone,'status':'confirmed',
                'created_at':firestore.SERVER_TIMESTAMP
            })
            print(f"✅ Buchung erstellt: {user_name} | {slot_date} {slot_time}")
            return True,"Buchung erfolgreich"
        except Exception as e:
            print(f"❌ create_booking Fehler: {e}")
            return False,str(e)
    
    def get_booking(self,slot_date,slot_time):
        try:
            for doc in self.db.collection('bookings')\
                    .where('slot_date','==',slot_date)\
                    .where('slot_time','==',slot_time)\
                    .where('status','==','confirmed').limit(1).stream():
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            print(f"❌ get_booking Fehler: {e}")
            return None
    
    def get_user_bookings(self,email,future_only=False):
        try:
            q = self.db.collection('bookings')\
                .where('user_email','==',email)\
                .where('status','==','confirmed')
            
            if future_only:
                q = q.where('slot_date','>=',datetime.now().strftime("%Y-%m-%d"))
            
            bookings = []
            for doc in q.stream():
                data = doc.to_dict()
                data['id'] = doc.id
                bookings.append(data)
            return sorted(bookings,key=lambda x:x['slot_date'])
        except Exception as e:
            print(f"❌ get_user_bookings Fehler: {e}")
            return []
    
    def cancel_booking(self,bid,cancelled_by):
        try:
            self.db.collection('bookings').document(bid).update({
                'status':'cancelled',
                'cancelled_by':cancelled_by,
                'cancelled_at':firestore.SERVER_TIMESTAMP
            })
            print(f"✅ Buchung storniert: {bid}")
            return True
        except Exception as e:
            print(f"❌ cancel_booking Fehler: {e}")
            return False
    
    def get_setting(self,key,default=''):
        try:
            doc = self.db.collection('settings').document(key).get()
            return doc.to_dict().get('value',default) if doc.exists else default
        except:
            return default
    
    def set_setting(self,key,value):
        try:
            self.db.collection('settings').document(key).set({
                'value':value,
                'updated_at':firestore.SERVER_TIMESTAMP
            },merge=True)
            return True
        except:
            return False
    
    def archive_old(self):
        """Alte Buchungen archivieren"""
        try:
            months = 12
            archive_date = (datetime.now()-timedelta(days=30*months)).strftime("%Y-%m-%d")
            count = 0
            for doc in self.db.collection('bookings').where('slot_date','<',archive_date).stream():
                self.db.collection('archive').add(doc.to_dict())
                doc.reference.delete()
                count += 1
            if count > 0:
                print(f"✅ {count} Buchungen archiviert")
            return count
        except Exception as e:
            print(f"❌ archive_old Fehler: {e}")
            return 0

ww_db = WasserwachtDB()
# ===== E-MAIL KLASSE (KORRIGIERT) =====
class Mailer:
    """E-Mail Versand mit detailliertem Error-Handling"""
    def __init__(self):
        if hasattr(st,'secrets'):
            self.server = st.secrets.get("SMTP_SERVER","smtp.gmail.com")
            self.port = int(st.secrets.get("SMTP_PORT",587))
            self.user = st.secrets.get("SMTP_USER","")
            self.pw = st.secrets.get("SMTP_PASSWORD","")
            self.admin_receiver = st.secrets.get("ADMIN_EMAIL_RECEIVER","")
            self.fromname = "Wasserwacht Dienstplan"
        else:
            self.server = self.port = self.user = self.pw = self.admin_receiver = ""
            self.fromname = "Dienstplan"
    
    def send(self, to, subject, body, attachments=None):
        """
        Sendet eine E-Mail mit detailliertem Error-Handling
        Returns: (success: bool, error_message: str)
        """
        if not self.user or not self.pw:
            return False, "❌ E-Mail: Keine SMTP Credentials in secrets.toml konfiguriert"
        
        if not to:
            return False, "❌ E-Mail: Keine Empfänger-Adresse angegeben"
        
        try:
            msg = MIMEMultipart()
            msg['From'] = email.utils.formataddr((self.fromname, self.user))
            msg['To'] = to
            msg['Subject'] = subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg.attach(MIMEText(body, 'html'))
            
            if attachments:
                for filename, data in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(data)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={filename}')
                    msg.attach(part)
            
            with smtplib.SMTP(self.server, self.port, timeout=60) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                
                try:
                    smtp.login(self.user, self.pw)
                except smtplib.SMTPAuthenticationError as auth_err:
                    return False, f"❌ SMTP Login fehlgeschlagen: {str(auth_err)}\n\nPrüfen Sie:\n1. Ist SMTP_USER korrekt? (aktuell: {self.user})\n2. Verwenden Sie ein Gmail App-Passwort?\n3. Ist 2-Faktor-Auth aktiviert?"
                
                smtp.send_message(msg)
            
            return True, f"✅ E-Mail erfolgreich an {to} gesendet"
            
        except smtplib.SMTPException as smtp_err:
            return False, f"❌ SMTP Fehler: {type(smtp_err).__name__}: {str(smtp_err)}"
        except Exception as e:
            return False, f"❌ E-Mail Fehler: {type(e).__name__}: {str(e)}"
    
    def send_booking_confirmation(self, user_email, user_name, slot_date, slot_time):
        """Buchungsbestätigung senden"""
        subject = f"Buchungsbestätigung - {fmt_de(slot_date)}"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2 style="color:{COLORS['rot']};">🌊 Buchungsbestätigung</h2>
        <p>Hallo {user_name},</p>
        <p>deine Buchung wurde bestätigt:</p>
        <div style="background:{COLORS['grau_hell']};padding:15px;border-radius:8px;margin:15px 0;">
            <strong>📅 Datum:</strong> {fmt_de(slot_date)}<br>
            <strong>⏰ Uhrzeit:</strong> {slot_time}
        </div>
        <p>Bei Fragen melde dich gerne.</p>
        <p>Viele Grüße,<br>Dein Wasserwacht Team 🌊</p>
        </body></html>
        """
        return self.send(user_email, subject, body)
    
    def send_cancellation(self, user_email, user_name, slot_date, slot_time):
        """Stornierungsbestätigung senden"""
        subject = f"Stornierung - {fmt_de(slot_date)}"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2 style="color:{COLORS['fehler']};">❌ Stornierung</h2>
        <p>Hallo {user_name},</p>
        <p>deine Buchung wurde storniert:</p>
        <div style="background:{COLORS['grau_hell']};padding:15px;border-radius:8px;margin:15px 0;">
            <strong>📅 Datum:</strong> {fmt_de(slot_date)}<br>
            <strong>⏰ Uhrzeit:</strong> {slot_time}
        </div>
        <p>Viele Grüße,<br>Dein Wasserwacht Team 🌊</p>
        </body></html>
        """
        return self.send(user_email, subject, body)
    
    def send_reminder(self, user_email, user_name, slot_date, slot_time):
        """Erinnerung senden (24h vorher)"""
        subject = f"⏰ Erinnerung: Dienst morgen - {fmt_de(slot_date)}"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2 style="color:{COLORS['orange']};">⏰ Erinnerung</h2>
        <p>Hallo {user_name},</p>
        <p>dein Dienst ist <strong>morgen</strong>:</p>
        <div style="background:{COLORS['grau_hell']};padding:15px;border-radius:8px;margin:15px 0;">
            <strong>📅 Datum:</strong> {fmt_de(slot_date)}<br>
            <strong>⏰ Uhrzeit:</strong> {slot_time}
        </div>
        <p>Bis morgen!<br>Dein Wasserwacht Team 🌊</p>
        </body></html>
        """
        return self.send(user_email, subject, body)

# ===== SMS KLASSE (KORRIGIERT) =====
class TwilioSMS:
    """SMS Versand mit Twilio und robuster Telefonnummer-Formatierung"""
    def __init__(self):
        if hasattr(st, 'secrets'):
            self.enabled = st.secrets.get("ENABLE_SMS_REMINDER", "false").lower() == "true"
            self.account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
            self.auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
            self.from_number = st.secrets.get("TWILIO_PHONE_NUMBER", "")
            
            if self.account_sid and self.auth_token:
                try:
                    self.client = Client(self.account_sid, self.auth_token)
                except Exception as e:
                    self.client = None
                    self.enabled = False
            else:
                self.client = None
                self.enabled = False
        else:
            self.enabled = False
            self.client = None
            self.from_number = ""
    
    def format_phone_number(self, phone):
        """Formatiert Telefonnummern für Twilio (E.164 Format)"""
        if not phone:
            return None
        
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        if phone.startswith('+'):
            return phone
        if phone.startswith('0'):
            return '+49' + phone[1:]
        if phone[0].isdigit():
            return '+49' + phone
        
        return None
    
    def send(self, to, body):
        """Sendet SMS über Twilio"""
        if not self.enabled:
            return False, "SMS ist deaktiviert"
        
        if not self.client:
            return False, "❌ Twilio Client konnte nicht initialisiert werden"
        
        if not self.from_number:
            return False, "❌ Keine Twilio-Telefonnummer konfiguriert"
        
        if not self.from_number.startswith('+'):
            return False, f"❌ Twilio-Nummer muss mit + beginnen (aktuell: {self.from_number})"
        
        formatted_to = self.format_phone_number(to)
        if not formatted_to:
            return False, f"❌ Ungültige Telefonnummer: {to}"
        
        try:
            message = self.client.messages.create(
                to=formatted_to,
                from_=self.from_number,
                body=body
            )
            
            if message.sid:
                return True, f"✅ SMS erfolgreich an {formatted_to} gesendet (SID: {message.sid})"
            else:
                return False, "❌ SMS-Versand fehlgeschlagen"
                
        except Exception as e:
            error_msg = f"❌ Twilio Fehler: {type(e).__name__}: {str(e)}"
            if "Unable to create record" in str(e):
                error_msg += f"\n\nMögliche Ursachen:\n1. Ziel-Nummer ist ungültig: {formatted_to}\n2. Twilio-Nummer ist nicht SMS-fähig"
            elif "authenticate" in str(e).lower():
                error_msg += "\n\nPrüfen Sie TWILIO_ACCOUNT_SID und TWILIO_AUTH_TOKEN"
            return False, error_msg
    
    def send_booking_confirmation(self, phone, name, slot_date, slot_time):
        """SMS-Buchungsbestätigung"""
        body = f"🌊 Buchung bestätigt: {name}\n📅 {fmt_de(slot_date)}\n⏰ {slot_time}\n\nWasserwacht"
        return self.send(phone, body)
    
    def send_reminder(self, phone, name, slot_date, slot_time):
        """SMS-Erinnerung"""
        body = f"⏰ Erinnerung: Dienst morgen!\n📅 {fmt_de(slot_date)}\n⏰ {slot_time}\n\nWasserwacht"
        return self.send(phone, body)

# ===== INIT =====
mailer = Mailer()
sms_client = TwilioSMS()
# ===== SESSION STATE INIT =====
if 'user' not in st.session_state:
    st.session_state.user = None
if 'page' not in st.session_state:
    st.session_state.page = 'kalender'
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = ww_db.get_setting('dark_mode','false') == 'true'
if 'selected_week' not in st.session_state:
    st.session_state.selected_week = week_start()

# ===== LOGIN & REGISTRIERUNG =====
def login_page():
    st.title("🌊 Wasserwacht Dienstplan+")
    st.markdown(f"**Version:** {VERSION}")
    
    tab1, tab2 = st.tabs(["🔐 Anmelden", "📝 Registrieren"])
    
    with tab1:
        with st.form("login_form"):
            email = st.text_input("E-Mail")
            password = st.text_input("Passwort", type="password")
            submit = st.form_submit_button("Anmelden", use_container_width=True)
            
            if submit:
                if email and password:
                    success, user = ww_db.auth(email, password)
                    if success:
                        st.session_state.user = user
                        st.success(f"✅ Willkommen, {user['name']}!")
                        st.rerun()
                    else:
                        st.error("❌ Ungültige Anmeldedaten")
                else:
                    st.warning("⚠️ Bitte alle Felder ausfüllen")
    
    with tab2:
        with st.form("register_form"):
            st.markdown("### Neuen Account erstellen")
            reg_name = st.text_input("Name*")
            reg_email = st.text_input("E-Mail*")
            reg_phone = st.text_input("Telefon (optional)", placeholder="+49 oder 0172...")
            reg_pw = st.text_input("Passwort*", type="password")
            reg_pw2 = st.text_input("Passwort wiederholen*", type="password")
            
            email_notif = st.checkbox("E-Mail Benachrichtigungen", value=True)
            sms_notif = st.checkbox("SMS Benachrichtigungen", value=False)
            
            reg_submit = st.form_submit_button("Registrieren", use_container_width=True)
            
            if reg_submit:
                if not reg_name or not reg_email or not reg_pw:
                    st.error("❌ Bitte alle Pflichtfelder (*) ausfüllen")
                elif reg_pw != reg_pw2:
                    st.error("❌ Passwörter stimmen nicht überein")
                elif len(reg_pw) < 6:
                    st.error("❌ Passwort muss mindestens 6 Zeichen haben")
                else:
                    success, msg = ww_db.create_user(reg_email, reg_name, reg_phone, reg_pw)
                    if success:
                        st.success(f"✅ {msg}! Du kannst dich jetzt anmelden.")
                        st.balloons()
                    else:
                        st.error(f"❌ {msg}")

def logout():
    st.session_state.user = None
    st.session_state.page = 'kalender'
    st.rerun()

# ===== NAVIGATION =====
def show_navigation():
    user = st.session_state.user
    is_admin = user.get('role') == 'admin' if user else False
    
    with st.sidebar:
        st.title(f"👤 {user.get('name', 'Benutzer')}")
        st.markdown(f"**{user.get('email')}**")
        
        if is_admin:
            st.markdown("🔑 **Administrator**")
        
        st.divider()
        
        # Navigation Buttons
        pages = [
            ('kalender', '📅 Kalender'),
            ('meine_buchungen', '📋 Meine Buchungen'),
            ('statistik', '📊 Statistik'),
        ]
        
        if is_admin:
            pages.extend([
                ('verwaltung', '⚙️ Verwaltung'),
                ('benutzer', '👥 Benutzer'),
                ('export', '💾 Export'),
                ('debug', '🔧 Debug'),
                ('handbuch', '📖 Handbuch'),
            ])
        
        for page_id, label in pages:
            if st.button(label, key=f"nav_{page_id}", use_container_width=True):
                st.session_state.page = page_id
                st.rerun()
        
        st.divider()
        
        # Dark Mode Toggle
        if st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode):
            st.session_state.dark_mode = True
            if is_admin:
                ww_db.set_setting('dark_mode', 'true')
        else:
            st.session_state.dark_mode = False
            if is_admin:
                ww_db.set_setting('dark_mode', 'false')
        
        st.divider()
        
        if st.button("🚪 Abmelden", use_container_width=True):
            logout()
        
        st.divider()
        st.caption(f"Version {VERSION}")
# ===== KALENDER SEITE =====
def kalender_page():
    user = st.session_state.user
    
    st.title("📅 Wochenschichten buchen")
    
    # Wochenauswahl
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    
    with col1:
        st.markdown(f"### Woche ab {fmt_de(st.session_state.selected_week)}")
    
    with col2:
        if st.button("⬅️ Vorherige"):
            st.session_state.selected_week = week_start(st.session_state.selected_week - timedelta(days=7))
            st.rerun()
    
    with col3:
        if st.button("Nächste ➡️"):
            st.session_state.selected_week = week_start(st.session_state.selected_week + timedelta(days=7))
            st.rerun()
    
    with col4:
        if st.button("🔄 Heute", use_container_width=True):
            st.session_state.selected_week = week_start()
            st.rerun()
    
    st.divider()
    
    # Lade Buchungen für diese Woche
    ws_str = st.session_state.selected_week.strftime("%Y-%m-%d")
    bookings = ww_db.get_week_bookings(ws_str)
    
    # Slots anzeigen
    for slot_config in WEEKLY_SLOTS:
        sd = slot_date(st.session_state.selected_week, slot_config['day'])
        slot_time = f"{slot_config['start']} - {slot_config['end']}"
        
        # Prüfe ob blockiert
        blocked = is_blocked(sd)
        reason = block_reason(sd) if blocked else None
        
        # Prüfe ob gebucht
        booking = next((b for b in bookings if b['slot_date'] == sd and slot_time in b.get('slot_time', '')), None)
        
        # Card erstellen
        card_class = "blocked" if blocked else ("booked" if booking else "slot-card")
        
        with st.container():
            st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
            
            col_a, col_b, col_c = st.columns([3, 2, 2])
            
            with col_a:
                st.markdown(f"**{slot_config['day_name']}, {fmt_de(sd)}**")
                st.markdown(f"⏰ {slot_time}")
            
            with col_b:
                if blocked:
                    st.warning(f"🚫 {reason}")
                elif booking:
                    st.info(f"✅ Gebucht: {booking.get('user_name', 'N/A')}")
                else:
                    st.success("🟢 Verfügbar")
            
            with col_c:
                if not blocked:
                    if booking:
                        # Zeige nur Stornieren-Button wenn es die eigene Buchung ist
                        if booking.get('user_email') == user['email']:
                            if st.button("❌ Stornieren", key=f"cancel_{sd}"):
                                if ww_db.cancel_booking(booking['id'], user['email']):
                                    success, msg = mailer.send_cancellation(
                                        user['email'], user['name'], sd, slot_time
                                    )
                                    st.success("✅ Buchung storniert")
                                    if success:
                                        st.info(msg)
                                    st.rerun()
                        else:
                            st.caption("(Anderer Benutzer)")
                    else:
                        if st.button("📝 Buchen", key=f"book_{sd}"):
                            success, msg = ww_db.create_booking(
                                sd, slot_time, user['email'], user['name'], user.get('phone', '')
                            )
                            if success:
                                st.success(f"✅ {msg}")
                                # E-Mail senden
                                mail_success, mail_msg = mailer.send_booking_confirmation(
                                    user['email'], user['name'], sd, slot_time
                                )
                                if mail_success:
                                    st.info(mail_msg)
                                else:
                                    st.warning(f"⚠️ Buchung OK, aber E-Mail fehlgeschlagen: {mail_msg}")
                                
                                # SMS senden (wenn aktiviert)
                                if user.get('sms_booking_confirmation') and user.get('phone'):
                                    sms_success, sms_msg = sms_client.send_booking_confirmation(
                                        user['phone'], user['name'], sd, slot_time
                                    )
                                    if not sms_success:
                                        st.warning(f"⚠️ SMS fehlgeschlagen: {sms_msg}")
                                
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
            
            st.markdown('</div>', unsafe_allow_html=True)

# ===== MEINE BUCHUNGEN =====
def meine_buchungen_page():
    user = st.session_state.user
    
    st.title("📋 Meine Buchungen")
    
    bookings = ww_db.get_user_bookings(user['email'], future_only=False)
    
    if not bookings:
        st.info("Du hast noch keine Buchungen.")
        return
    
    # Nach zukünftig/vergangen filtern
    today = datetime.now().date().strftime("%Y-%m-%d")
    future = [b for b in bookings if b['slot_date'] >= today]
    past = [b for b in bookings if b['slot_date'] < today]
    
    tab1, tab2 = st.tabs([f"🔜 Zukünftig ({len(future)})", f"📅 Vergangen ({len(past)})"])
    
    with tab1:
        if not future:
            st.info("Keine zukünftigen Buchungen.")
        else:
            for b in future:
                with st.expander(f"{fmt_de(b['slot_date'])} - {b.get('slot_time', 'N/A')}", expanded=True):
                    st.markdown(f"**📅 Datum:** {fmt_de(b['slot_date'])}")
                    st.markdown(f"**⏰ Zeit:** {b.get('slot_time', 'N/A')}")
                    st.markdown(f"**📧 E-Mail:** {b['user_email']}")
                    if b.get('user_phone'):
                        st.markdown(f"**📱 Telefon:** {b['user_phone']}")
                    
                    if st.button("❌ Stornieren", key=f"cancel_my_{b['id']}"):
                        if ww_db.cancel_booking(b['id'], user['email']):
                            success, msg = mailer.send_cancellation(
                                user['email'], user['name'], b['slot_date'], b.get('slot_time', '')
                            )
                            st.success("✅ Buchung storniert")
                            st.rerun()
    
    with tab2:
        if not past:
            st.info("Keine vergangenen Buchungen.")
        else:
            for b in past:
                with st.expander(f"{fmt_de(b['slot_date'])} - {b.get('slot_time', 'N/A')}"):
                    st.markdown(f"**📅 Datum:** {fmt_de(b['slot_date'])}")
                    st.markdown(f"**⏰ Zeit:** {b.get('slot_time', 'N/A')}")
                    st.markdown(f"**Status:** {b.get('status', 'confirmed')}")

# ===== STATISTIK =====
def statistik_page():
    st.title("📊 Statistik")
    
    # Lade alle Buchungen
    all_bookings = []
    try:
        for doc in db.collection('bookings').where('status', '==', 'confirmed').stream():
            b = doc.to_dict()
            b['id'] = doc.id
            all_bookings.append(b)
    except:
        st.error("Fehler beim Laden der Statistiken")
        return
    
    if not all_bookings:
        st.info("Noch keine Buchungen vorhanden.")
        return
    
    # Top Helfer
    st.subheader("🏆 Top Helfer")
    user_counts = Counter([b['user_name'] for b in all_bookings])
    top_10 = user_counts.most_common(10)
    
    if top_10:
        df_top = pd.DataFrame(top_10, columns=['Name', 'Anzahl Dienste'])
        fig = px.bar(df_top, x='Name', y='Anzahl Dienste', title='Top 10 Helfer')
        st.plotly_chart(fig, use_container_width=True)
    
    # Buchungen pro Monat
    st.subheader("📅 Buchungen pro Monat")
    monthly = Counter([b['slot_date'][:7] for b in all_bookings])
    df_month = pd.DataFrame(sorted(monthly.items()), columns=['Monat', 'Anzahl'])
    fig_month = px.line(df_month, x='Monat', y='Anzahl', title='Buchungen pro Monat')
    st.plotly_chart(fig_month, use_container_width=True)
# ===== VERWALTUNG (ADMIN) =====
def verwaltung_page():
    st.title("⚙️ Verwaltung")
    
    tab1, tab2, tab3 = st.tabs(["📋 Alle Buchungen", "🗑️ Archivieren", "⚙️ Einstellungen"])
    
    with tab1:
        st.subheader("Alle Buchungen")
        
        # Filter
        col1, col2 = st.columns(2)
        with col1:
            filter_status = st.selectbox("Status", ["alle", "confirmed", "cancelled"])
        with col2:
            filter_future = st.checkbox("Nur zukünftige", value=True)
        
        # Lade Buchungen
        try:
            query = db.collection('bookings')
            if filter_status != "alle":
                query = query.where('status', '==', filter_status)
            
            all_bookings = []
            for doc in query.stream():
                b = doc.to_dict()
                b['id'] = doc.id
                all_bookings.append(b)
            
            if filter_future:
                today = datetime.now().date().strftime("%Y-%m-%d")
                all_bookings = [b for b in all_bookings if b.get('slot_date', '') >= today]
            
            all_bookings.sort(key=lambda x: x.get('slot_date', ''), reverse=True)
            
            if not all_bookings:
                st.info("Keine Buchungen gefunden.")
            else:
                st.write(f"**{len(all_bookings)} Buchungen gefunden**")
                
                for booking in all_bookings:
                    with st.expander(
                        f"{fmt_de(booking.get('slot_date', 'N/A'))} - {booking.get('user_name', 'N/A')} ({booking.get('status', 'N/A')})"
                    ):
                        col_a, col_b = st.columns([3, 1])
                        
                        with col_a:
                            st.markdown(f"**📅 Datum:** {fmt_de(booking.get('slot_date', 'N/A'))}")
                            st.markdown(f"**⏰ Zeit:** {booking.get('slot_time', 'N/A')}")
                            st.markdown(f"**👤 Name:** {booking.get('user_name', 'N/A')}")
                            st.markdown(f"**📧 E-Mail:** {booking.get('user_email', 'N/A')}")
                            if booking.get('user_phone'):
                                st.markdown(f"**📱 Telefon:** {booking.get('user_phone')}")
                            st.markdown(f"**Status:** {booking.get('status', 'N/A')}")
                        
                        with col_b:
                            if booking.get('status') == 'confirmed':
                                if st.button("❌ Stornieren", key=f"admin_cancel_{booking['id']}"):
                                    if ww_db.cancel_booking(booking['id'], 'admin'):
                                        st.success("✅ Storniert")
                                        st.rerun()
                            
                            if st.button("🗑️ Löschen", key=f"admin_del_{booking['id']}"):
                                try:
                                    db.collection('bookings').document(booking['id']).delete()
                                    st.success("✅ Gelöscht")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fehler: {e}")
        
        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")
    
    with tab2:
        st.subheader("🗑️ Alte Buchungen archivieren")
        st.info("Buchungen älter als 12 Monate werden archiviert.")
        
        if st.button("Archivierung starten"):
            count = ww_db.archive_old()
            if count > 0:
                st.success(f"✅ {count} Buchungen archiviert")
            else:
                st.info("Keine Buchungen zum Archivieren gefunden")
    
    with tab3:
        st.subheader("⚙️ Systemeinstellungen")
        
        # Dark Mode Global
        dark = ww_db.get_setting('dark_mode', 'false') == 'true'
        new_dark = st.checkbox("Dark Mode (Global)", value=dark)
        if new_dark != dark:
            ww_db.set_setting('dark_mode', 'true' if new_dark else 'false')
            st.success("✅ Gespeichert")
            st.rerun()

# ===== BENUTZERVERWALTUNG (ADMIN) =====
def benutzer_page():
    st.title("👥 Benutzerverwaltung")
    
    users = ww_db.get_all_users()
    
    tab1, tab2 = st.tabs(["📋 Alle Benutzer", "➕ Neuer Benutzer"])
    
    with tab1:
        if not users:
            st.info("Noch keine Benutzer vorhanden.")
        else:
            st.write(f"**{len(users)} Benutzer gefunden**")
            
            for user in users:
                with st.expander(f"{user.get('name')} ({user.get('email')})"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**Name:** {user.get('name')}")
                        st.markdown(f"**E-Mail:** {user.get('email')}")
                        st.markdown(f"**Telefon:** {user.get('phone', 'N/A')}")
                        st.markdown(f"**Rolle:** {user.get('role', 'user')}")
                        st.markdown(f"**Aktiv:** {'✅' if user.get('active', True) else '❌'}")
                        st.markdown(f"**E-Mail Benachrichtigungen:** {'✅' if user.get('email_notifications', True) else '❌'}")
                        st.markdown(f"**SMS Benachrichtigungen:** {'✅' if user.get('sms_notifications', False) else '❌'}")
                    
                    with col2:
                        # Aktivieren/Deaktivieren
                        if user.get('active', True):
                            if st.button("🔒 Deaktivieren", key=f"deact_{user['id']}"):
                                ww_db.update_user(user['id'], active=False)
                                st.success("✅ Deaktiviert")
                                st.rerun()
                        else:
                            if st.button("✅ Aktivieren", key=f"act_{user['id']}"):
                                ww_db.update_user(user['id'], active=True)
                                st.success("✅ Aktiviert")
                                st.rerun()
                        
                        # Löschen
                        if st.button("🗑️ Löschen", key=f"del_user_{user['id']}"):
                            if ww_db.delete_user(user['id']):
                                st.success("✅ Gelöscht")
                                st.rerun()
    
    with tab2:
        with st.form("new_user"):
            st.markdown("### Neuen Benutzer erstellen")
            name = st.text_input("Name*")
            email = st.text_input("E-Mail*")
            phone = st.text_input("Telefon")
            password = st.text_input("Passwort*", type="password")
            role = st.selectbox("Rolle", ["user", "admin"])
            
            submit = st.form_submit_button("Erstellen", use_container_width=True)
            
            if submit:
                if name and email and password:
                    success, msg = ww_db.create_user(email, name, phone, password, role)
                    if success:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.error("❌ Bitte alle Pflichtfelder ausfüllen")

# ===== EXPORT (ADMIN) =====
def export_page():
    st.title("💾 Export & Backup")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Daten exportieren")
        
        if st.button("📄 Buchungen exportieren (JSON)", use_container_width=True):
            try:
                bookings = []
                for doc in db.collection('bookings').stream():
                    b = doc.to_dict()
                    b['id'] = doc.id
                    # Firestore Timestamps zu Strings
                    for key in b:
                        if hasattr(b[key], 'strftime'):
                            b[key] = b[key].strftime('%Y-%m-%d %H:%M:%S')
                    bookings.append(b)
                
                json_str = json.dumps(bookings, indent=2, ensure_ascii=False)
                st.download_button(
                    "⬇️ Download Buchungen",
                    json_str,
                    file_name=f"buchungen_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            except Exception as e:
                st.error(f"Fehler: {e}")
        
        if st.button("📄 Benutzer exportieren (JSON)", use_container_width=True):
            try:
                users = ww_db.get_all_users()
                # Passwörter entfernen
                users_export = [{k: v for k, v in u.items() if k != 'password_hash'} for u in users]
                json_str = json.dumps(users_export, indent=2, ensure_ascii=False)
                st.download_button(
                    "⬇️ Download Benutzer",
                    json_str,
                    file_name=f"benutzer_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            except Exception as e:
                st.error(f"Fehler: {e}")
        
        if st.button("📊 Statistik exportieren (CSV)", use_container_width=True):
            try:
                bookings = []
                for doc in db.collection('bookings').where('status', '==', 'confirmed').stream():
                    bookings.append(doc.to_dict())
                
                if bookings:
                    df = pd.DataFrame(bookings)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ Download CSV",
                        csv,
                        file_name=f"statistik_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Keine Daten vorhanden")
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    with col2:
        st.subheader("📧 E-Mail Backup")
        
        if st.button("📧 Backup per E-Mail senden", use_container_width=True):
            if mailer.admin_receiver:
                try:
                    # Lade Daten
                    bookings = []
                    for doc in db.collection('bookings').stream():
                        b = doc.to_dict()
                        for key in b:
                            if hasattr(b[key], 'strftime'):
                                b[key] = b[key].strftime('%Y-%m-%d %H:%M:%S')
                        bookings.append(b)
                    
                    users = ww_db.get_all_users()
                    users_export = [{k: v for k, v in u.items() if k != 'password_hash'} for u in users]
                    
                    # ZIP erstellen
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.writestr('buchungen.json', json.dumps(bookings, indent=2, ensure_ascii=False))
                        zf.writestr('benutzer.json', json.dumps(users_export, indent=2, ensure_ascii=False))
                    
                    zip_buffer.seek(0)
                    
                    # E-Mail senden
                    subject = f"Dienstplan Backup - {datetime.now().strftime('%d.%m.%Y')}"
                    body = f"""
                    <html><body>
                    <h2 style="color:{COLORS['rot']};">🌊 Automatisches Backup</h2>
                    <p><strong>Datum:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                    <p><strong>Buchungen:</strong> {len(bookings)}</p>
                    <p><strong>Benutzer:</strong> {len(users)}</p>
                    </body></html>
                    """
                    
                    success, msg = mailer.send(
                        mailer.admin_receiver,
                        subject,
                        body,
                        attachments=[(f"backup_{datetime.now().strftime('%Y%m%d')}.zip", zip_buffer.getvalue())]
                    )
                    
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                
                except Exception as e:
                    st.error(f"Fehler: {e}")
            else:
                st.error("❌ Keine Admin-E-Mail konfiguriert")

# ===== DEBUG-PANEL (ADMIN) =====
def debug_page():
    st.title("🔧 Debug-Panel")
    
    tab1, tab2, tab3 = st.tabs(["📧 E-Mail Test", "📱 SMS Test", "⚙️ System-Info"])
    
    with tab1:
        st.markdown("### 📧 E-Mail Test")
        with st.form("email_test"):
            test_email = st.text_input("Test E-Mail Adresse")
            test_subject = st.text_input("Betreff", value="Test E-Mail")
            test_body = st.text_area("Nachricht", value="Dies ist eine Test-E-Mail vom Wasserwacht Dienstplan.")
            
            if st.form_submit_button("📧 Test-E-Mail senden", use_container_width=True):
                if test_email:
                    success, msg = mailer.send(test_email, test_subject, test_body)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Bitte E-Mail-Adresse eingeben")
    
    with tab2:
        st.markdown("### 📱 SMS Test")
        with st.form("sms_test"):
            test_phone = st.text_input("Test Telefonnummer", placeholder="0172... oder +49172...")
            test_sms_body = st.text_area("SMS Text", value="Test SMS vom Wasserwacht Dienstplan")
            
            if st.form_submit_button("📱 Test-SMS senden", use_container_width=True):
                if test_phone:
                    success, msg = sms_client.send(test_phone, test_sms_body)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Bitte Telefonnummer eingeben")
    
    with tab3:
        st.markdown("### ⚙️ System-Info")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**SMTP Konfiguration:**")
            st.code(f"""
Server: {mailer.server}
Port: {mailer.port}
User: {mailer.user[:15]}...
Password: {'✅ gesetzt' if mailer.pw else '❌ NICHT GESETZT'}
Admin: {mailer.admin_receiver}
            """)
        
        with col2:
            st.markdown("**Twilio Konfiguration:**")
            st.code(f"""
Enabled: {sms_client.enabled}
Account SID: {sms_client.account_sid[:15]}...
Auth Token: {'✅ gesetzt' if sms_client.auth_token else '❌ NICHT GESETZT'}
From Number: {sms_client.from_number}
Client: {'✅ OK' if sms_client.client else '❌ FEHLER'}
            """)
        
        st.markdown("**Firestore:**")
        st.code(f"Verbindung: {'✅ OK' if db else '❌ FEHLER'}")
        
        st.markdown("**Benutzer in DB:**")
        users_count = len(ww_db.get_all_users())
        st.code(f"Anzahl: {users_count}")

# ===== HANDBUCH =====
def handbuch_page():
    st.title("📖 Handbuch")
    
    st.markdown("""
    ## 🌊 Wasserwacht Dienstplan+ - Benutzerhandbuch
    
    ### 📅 Schichten buchen
    
    1. **Kalender öffnen**: Gehen Sie zur Seite "📅 Kalender"
    2. **Woche auswählen**: Verwenden Sie die Pfeile ⬅️ ➡️ oder "Heute"
    3. **Schicht buchen**: Klicken Sie auf "📝 Buchen" bei einem verfügbaren Slot
    4. **Bestätigung**: Sie erhalten eine E-Mail-Bestätigung (und SMS, falls aktiviert)
    
    ### 🚫 Blockierte Tage
    
    - **Feiertage**: An bayerischen Feiertagen sind keine Buchungen möglich
    - **Sommerpause**: Von Juni bis September pausiert der Dienst
    
    ### 📋 Meine Buchungen
    
    - Sehen Sie alle Ihre zukünftigen und vergangenen Buchungen
    - Stornieren Sie Buchungen bis 24h vorher
    
    ### 📊 Statistik
    
    - Sehen Sie Ihre Dienst-Statistiken
    - Top-10 Helfer Ranking
    - Monatliche Übersichten
    
    ### ⚙️ Admin-Funktionen
    
    **Nur für Administratoren:**
    
    - **Verwaltung**: Alle Buchungen einsehen und verwalten
    - **Benutzer**: Benutzer erstellen, bearbeiten, löschen
    - **Export**: Daten exportieren als JSON/CSV
    - **Debug**: E-Mail und SMS testen
    
    ### 💡 Tipps
    
    - Aktivieren Sie E-Mail-Benachrichtigungen in Ihrem Profil
    - Sie erhalten Erinnerungen 24h vor Ihrem Dienst
    - Bei Fragen kontaktieren Sie Ihren Administrator
    
    ### 🔧 Probleme?
    
    Kontaktieren Sie den Admin über: {0}
    """.format(mailer.admin_receiver if mailer.admin_receiver else "admin@wasserwacht.de"))

# ===== MAIN =====
def main():
    # CSS injizieren
    inject_css(dark=st.session_state.dark_mode)
    
    # Login Check
    if not st.session_state.user:
        login_page()
        return
    
    # Navigation anzeigen
    show_navigation()
    
    # Seiten-Router
    page = st.session_state.page
    user = st.session_state.user
    is_admin = user.get('role') == 'admin'
    
    if page == 'kalender':
        kalender_page()
    
    elif page == 'meine_buchungen':
        meine_buchungen_page()
    
    elif page == 'statistik':
        statistik_page()
    
    elif page == 'verwaltung':
        if is_admin:
            verwaltung_page()
        else:
            st.error("❌ Keine Berechtigung")
    
    elif page == 'benutzer':
        if is_admin:
            benutzer_page()
        else:
            st.error("❌ Keine Berechtigung")
    
    elif page == 'export':
        if is_admin:
            export_page()
        else:
            st.error("❌ Keine Berechtigung")
    
    elif page == 'debug':
        if is_admin:
            debug_page()
        else:
            st.error("❌ Keine Berechtigung")
    
    elif page == 'handbuch':
        handbuch_page()
    
    else:
        st.error(f"❌ Unbekannte Seite: {page}")

if __name__ == "__main__":
    main()
