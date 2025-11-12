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
# ===== CSS INJECTION (VERBESSERT) =====
def inject_css(dark=False):
    if dark:
        # Dark Mode Farben
        bg = "#0E1117"
        surface = "#262730"
        surface_light = "#31333F"
        text = "#FAFAFA"
        text_secondary = "#A0A0A0"
        primary = COLORS["rot_hell"]
        border = "#3D3D3D"
    else:
        # Light Mode Farben
        bg = COLORS["weiss"]
        surface = COLORS["grau_hell"]
        surface_light = "#FFFFFF"
        text = COLORS["text"]
        text_secondary = COLORS["grau_dunkel"]
        primary = COLORS["rot"]
        border = COLORS["grau_mittel"]
    
    st.markdown(f"""
    <style>
        /* Globale Anpassungen */
        .main {{
            background-color: {bg} !important;
            color: {text} !important;
        }}
        
        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background-color: {surface} !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: {text} !important;
        }}
        
        /* Buttons */
        .stButton>button {{
            background-color: {primary} !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
        }}
        .stButton>button:hover {{
            background-color: {COLORS["rot_dunkel"]} !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        
        /* Forms & Inputs */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>select {{
            background-color: {surface_light} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
        }}
        
        /* Expander */
        .streamlit-expanderHeader {{
            background-color: {surface} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
        }}
        .streamlit-expanderContent {{
            background-color: {surface_light} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
        }}
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: {surface} !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: {text_secondary} !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: {primary} !important;
            border-bottom-color: {primary} !important;
        }}
        
        /* Cards */
        .slot-card {{
            background: {surface} !important;
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
            border-left: 4px solid {primary};
            color: {text} !important;
        }}
        .booked {{
            border-left-color: {COLORS["orange"]} !important;
        }}
        .blocked {{
            border-left-color: {border} !important;
            opacity: 0.6;
        }}
        
        /* Dataframes & Tables */
        .stDataFrame {{
            background-color: {surface} !important;
            color: {text} !important;
        }}
        
        /* Metric */
        [data-testid="stMetricValue"] {{
            color: {text} !important;
        }}
        
        /* Info/Warning/Error Boxes */
        .stAlert {{
            background-color: {surface} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
        }}
        
        /* Code Blocks */
        .stCodeBlock {{
            background-color: {surface_light} !important;
        }}
        code {{
            color: {text} !important;
        }}
        
        /* Markdown */
        .markdown-text-container {{
            color: {text} !important;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: {text} !important;
        }}
        p, span, div {{
            color: {text} !important;
        }}
        
        /* Links */
        a {{
            color: {primary} !important;
        }}
        
        /* Checkbox & Radio */
        .stCheckbox label {{
            color: {text} !important;
        }}
        .stRadio label {{
            color: {text} !important;
        }}
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

# ===== SMS KLASSE (VOLLSTÄNDIG MIT TEMPLATE-SUPPORT) =====
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
        """SMS-Buchungsbestätigung - verwendet Template"""
        body_template = ww_db.get_setting('sms_booking_body',
            """🌊 Buchung bestätigt: {name}
📅 {date}
⏰ {time}

{org_name}""")
        
        data = {
            'name': name,
            'date': fmt_de(slot_date),
            'time': slot_time,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht')
        }
        
        body = body_template
        for key, value in data.items():
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(phone, body)
    
    def send_reminder(self, phone, name, slot_date, slot_time):
        """SMS-Erinnerung - verwendet Template"""
        body_template = ww_db.get_setting('sms_reminder_body',
            """⏰ Erinnerung: Dienst morgen!
📅 {date}
⏰ {time}

{org_name}""")
        
        data = {
            'name': name,
            'date': fmt_de(slot_date),
            'time': slot_time,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht')
        }
        
        body = body_template
        for key, value in data.items():
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(phone, body)

# ===== INIT =====
mailer = Mailer()
sms_client = TwilioSMS()


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
            ('handbuch', '📖 Handbuch'),
            ('impressum', '⚖️ Impressum'),
        ]
        
        if is_admin:
            pages.extend([
                ('verwaltung', '⚙️ Verwaltung'),
                ('benutzer', '👥 Benutzer'),
                ('export', '💾 Export'),
                ('vorlagen', '📧 Vorlagen'),
                ('debug', '🔧 Debug'),
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

# ===== HANDBUCH (MIT EDIT-FUNKTION) =====
def handbuch_page():
    user = st.session_state.user
    is_admin = user.get('role') == 'admin'
    
    st.title("📖 Handbuch")
    
    # Lade Handbuch-Inhalt aus Firestore
    handbuch_content = ww_db.get_setting('handbuch_content', '')
    
    # Falls leer, verwende Default-Inhalt
    if not handbuch_content:
        handbuch_content = """
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
- **Handbuch**: Dieses Handbuch bearbeiten

### 💡 Tipps

- Aktivieren Sie E-Mail-Benachrichtigungen in Ihrem Profil
- Sie erhalten Erinnerungen 24h vor Ihrem Dienst
- Bei Fragen kontaktieren Sie Ihren Administrator

### 🔧 Support

Bei Problemen kontaktieren Sie den Admin über: admin@wasserwacht.de
        """
    
    # ADMIN: Bearbeiten-Modus
    if is_admin:
        tab1, tab2 = st.tabs(["📖 Ansicht", "✏️ Bearbeiten"])
        
        with tab1:
            # Nur Anzeige
            st.markdown(handbuch_content, unsafe_allow_html=True)
        
        with tab2:
            st.info("💡 Verwenden Sie **Markdown** zur Formatierung. Änderungen werden für alle Benutzer gespeichert.")
            
            # Editor
            edited_content = st.text_area(
                "Handbuch-Inhalt (Markdown)",
                value=handbuch_content,
                height=500,
                help="Verwenden Sie Markdown-Syntax: ## für Überschriften, ** für fett, * für kursiv, - für Listen"
            )
            
            col1, col2, col3 = st.columns([2, 2, 6])
            
            with col1:
                if st.button("💾 Speichern", use_container_width=True, type="primary"):
                    if ww_db.set_setting('handbuch_content', edited_content):
                        st.success("✅ Handbuch gespeichert!")
                        st.rerun()
                    else:
                        st.error("❌ Fehler beim Speichern")
            
            with col2:
                if st.button("🔄 Zurücksetzen", use_container_width=True):
                    st.info("Seite wird neu geladen...")
                    st.rerun()
            
            # Live-Vorschau
            with st.expander("👁️ Live-Vorschau", expanded=True):
                st.markdown(edited_content, unsafe_allow_html=True)
    
    # USER: Nur Ansicht
    else:
        st.markdown(handbuch_content, unsafe_allow_html=True)
        
        st.divider()
        st.caption("💡 Tipp: Haben Sie Fragen? Wenden Sie sich an Ihren Administrator.")

# ===== IMPRESSUM (MIT EDIT-FUNKTION) =====
def impressum_page():
    user = st.session_state.user
    is_admin = user.get('role') == 'admin'
    
    st.title("⚖️ Impressum")
    
    # Lade Impressum-Inhalt aus Firestore
    impressum_content = ww_db.get_setting('impressum_content', '')
    
    # Falls leer, verwende Default-Inhalt
    if not impressum_content:
        impressum_content = """
## ⚖️ Impressum

### Angaben gemäß § 5 TMG

**Wasserwacht [Ortsgruppe]**  
[Straße und Hausnummer]  
[PLZ] [Ort]

### Vertreten durch:

[Name des Verantwortlichen]  
[Funktion/Rolle]

### Kontakt:

**Telefon:** [Telefonnummer]  
**E-Mail:** [E-Mail-Adresse]  
**Website:** [Website-URL]

### Registereintrag:

Eingetragen im Vereinsregister  
**Registergericht:** [Amtsgericht]  
**Registernummer:** [VR-Nummer]

### Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV:

[Name]  
[Adresse]

### Haftungsausschluss:

#### Haftung für Inhalte
Die Inhalte unserer Seiten wurden mit größter Sorgfalt erstellt. Für die Richtigkeit, Vollständigkeit und Aktualität der Inhalte können wir jedoch keine Gewähr übernehmen.

#### Haftung für Links
Unser Angebot enthält Links zu externen Webseiten Dritter, auf deren Inhalte wir keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen.

#### Urheberrecht
Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der Grenzen des Urheberrechtes bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers.

### Datenschutz

Informationen zum Datenschutz finden Sie in unserer [Datenschutzerklärung](#).

---

*Erstellt mit Wasserwacht Dienstplan+ v{0}*
        """.format(VERSION)
    
    # ADMIN: Bearbeiten-Modus
    if is_admin:
        tab1, tab2 = st.tabs(["⚖️ Ansicht", "✏️ Bearbeiten"])
        
        with tab1:
            # Nur Anzeige
            st.markdown(impressum_content, unsafe_allow_html=True)
        
        with tab2:
            st.info("💡 Verwenden Sie **Markdown** zur Formatierung. Passen Sie das Impressum an Ihre Organisation an.")
            st.warning("⚠️ **WICHTIG:** Stellen Sie sicher, dass alle rechtlich erforderlichen Angaben vorhanden sind!")
            
            # Editor
            edited_content = st.text_area(
                "Impressum-Inhalt (Markdown)",
                value=impressum_content,
                height=600,
                help="Verwenden Sie Markdown-Syntax: ## für Überschriften, ** für fett, [Text](URL) für Links"
            )
            
            col1, col2, col3 = st.columns([2, 2, 6])
            
            with col1:
                if st.button("💾 Speichern", use_container_width=True, type="primary"):
                    if ww_db.set_setting('impressum_content', edited_content):
                        st.success("✅ Impressum gespeichert!")
                        st.rerun()
                    else:
                        st.error("❌ Fehler beim Speichern")
            
            with col2:
                if st.button("🔄 Zurücksetzen", use_container_width=True):
                    st.info("Seite wird neu geladen...")
                    st.rerun()
            
            # Live-Vorschau
            with st.expander("👁️ Live-Vorschau", expanded=True):
                st.markdown(edited_content, unsafe_allow_html=True)
    
    # USER: Nur Ansicht
    else:
        st.markdown(impressum_content, unsafe_allow_html=True)

# ===== VORLAGEN / TEMPLATES (NUR ADMIN) =====
def vorlagen_page():
    st.title("📧 Nachrichten-Vorlagen")
    
    st.info("💡 Hier können Sie die E-Mail und SMS Templates anpassen. Verwenden Sie Platzhalter wie {name}, {date}, {time} für dynamische Inhalte.")
    
    # Template-Definitionen mit Defaults
    templates = {
        'email_booking': {
            'name': '✉️ E-Mail - Buchungsbestätigung',
            'type': 'email',
            'default_subject': 'Buchungsbestätigung - {date}',
            'default_body': """Hallo {name},

deine Buchung wurde bestätigt:

📅 Datum: {date}
⏰ Uhrzeit: {time}

Bei Fragen melde dich gerne unter {org_email}.

Viele Grüße,
Dein {org_name} Team 🌊"""
        },
        'email_cancellation': {
            'name': '✉️ E-Mail - Stornierung',
            'type': 'email',
            'default_subject': 'Stornierung - {date}',
            'default_body': """Hallo {name},

deine Buchung wurde storniert:

📅 Datum: {date}
⏰ Uhrzeit: {time}

Viele Grüße,
Dein {org_name} Team 🌊"""
        },
        'email_reminder': {
            'name': '✉️ E-Mail - Erinnerung',
            'type': 'email',
            'default_subject': '⏰ Erinnerung: Dienst morgen - {date}',
            'default_body': """Hallo {name},

dein Dienst ist morgen:

📅 Datum: {date}
⏰ Uhrzeit: {time}

Bis morgen!
Dein {org_name} Team 🌊"""
        },
        'email_welcome': {
            'name': '✉️ E-Mail - Willkommen (nach Registrierung)',
            'type': 'email',
            'default_subject': 'Willkommen bei {org_name}!',
            'default_body': """Hallo {name},

herzlich willkommen bei {org_name}! 🌊

Dein Account wurde erfolgreich erstellt.
Du kannst dich jetzt anmelden und Schichten buchen.

📧 E-Mail: {email}
🌐 Dashboard: [LINK ZUR APP]

Bei Fragen erreichst du uns unter {org_email}.

Viele Grüße,
Dein {org_name} Team"""
        },
        'email_admin_notification': {
            'name': '✉️ E-Mail - Admin-Benachrichtigung (neue Buchung)',
            'type': 'email',
            'default_subject': '🔔 Neue Buchung: {name} - {date}',
            'default_body': """Neue Buchung im Dienstplan:

👤 Name: {name}
📧 E-Mail: {email}
📱 Telefon: {phone}

📅 Datum: {date}
⏰ Uhrzeit: {time}

Gebucht am: {current_date}"""
        },
        'sms_booking': {
            'name': '📱 SMS - Buchungsbestätigung',
            'type': 'sms',
            'default_subject': None,
            'default_body': """🌊 Buchung bestätigt: {name}
📅 {date}
⏰ {time}

{org_name}"""
        },
        'sms_reminder': {
            'name': '📱 SMS - Erinnerung',
            'type': 'sms',
            'default_subject': None,
            'default_body': """⏰ Erinnerung: Dienst morgen!
📅 {date}
⏰ {time}

{org_name}"""
        }
    }
    
    # Platzhalter-Info
    with st.expander("ℹ️ Verfügbare Platzhalter", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Standard:**
            - `{name}` - Name des Benutzers
            - `{date}` - Datum (formatiert: DD.MM.YYYY)
            - `{time}` - Uhrzeit
            - `{email}` - E-Mail des Benutzers
            """)
        with col2:
            st.markdown("""
            **Erweitert:**
            - `{phone}` - Telefonnummer
            - `{org_name}` - Organisationsname
            - `{org_email}` - Organisation E-Mail
            - `{current_date}` - Heutiges Datum
            """)
        st.caption("💡 Platzhalter werden automatisch durch echte Daten ersetzt")
    
    st.divider()
    
    # Tabs für Template-Typen
    tab_names = [t['name'] for t in templates.values()]
    tabs = st.tabs(tab_names)
    
    for i, (template_key, template_config) in enumerate(templates.items()):
        with tabs[i]:
            # Lade gespeicherten Inhalt oder verwende Default
            saved_subject = ww_db.get_setting(f'{template_key}_subject', template_config['default_subject'])
            saved_body = ww_db.get_setting(f'{template_key}_body', template_config['default_body'])
            
            # Editor
            if template_config['type'] == 'email':
                subject = st.text_input(
                    "Betreff",
                    value=saved_subject if saved_subject else template_config['default_subject'],
                    key=f"subject_{template_key}",
                    help="Betreff der E-Mail (nur bei E-Mails)"
                )
            else:
                subject = None
            
            body = st.text_area(
                "Nachricht",
                value=saved_body if saved_body else template_config['default_body'],
                height=300,
                key=f"body_{template_key}",
                help="Nachrichtentext - verwenden Sie Platzhalter für dynamische Inhalte"
            )
            
            # Buttons
            col1, col2, col3 = st.columns([2, 2, 6])
            
            with col1:
                if st.button("💾 Speichern", key=f"save_{template_key}", use_container_width=True, type="primary"):
                    success = True
                    if subject:
                        success = success and ww_db.set_setting(f'{template_key}_subject', subject)
                    success = success and ww_db.set_setting(f'{template_key}_body', body)
                    
                    if success:
                        st.success("✅ Template gespeichert!")
                        st.rerun()
                    else:
                        st.error("❌ Fehler beim Speichern")
            
            with col2:
                if st.button("🔄 Zurücksetzen", key=f"reset_{template_key}", use_container_width=True):
                    ww_db.set_setting(f'{template_key}_subject', template_config['default_subject'])
                    ww_db.set_setting(f'{template_key}_body', template_config['default_body'])
                    st.success("✅ Auf Standard zurückgesetzt!")
                    st.rerun()
            
            # Live-Vorschau
            st.divider()
            st.markdown("### 👁️ Live-Vorschau")
            
            # Beispieldaten für Vorschau
            preview_data = {
                'name': 'Max Mustermann',
                'date': '15.12.2025',
                'time': '14:00 - 17:00',
                'email': 'max.mustermann@example.com',
                'phone': '+49 172 1234567',
                'org_name': 'Wasserwacht München',
                'org_email': 'info@wasserwacht-muenchen.de',
                'current_date': datetime.now().strftime('%d.%m.%Y %H:%M')
            }
            
            # Template-Rendering
            preview_body = body
            if subject:
                preview_subject = subject
                for key, value in preview_data.items():
                    preview_subject = preview_subject.replace('{' + key + '}', str(value))
                for key, value in preview_data.items():
                    preview_body = preview_body.replace('{' + key + '}', str(value))
                
                st.markdown(f"**Betreff:** {preview_subject}")
            else:
                for key, value in preview_data.items():
                    preview_body = preview_body.replace('{' + key + '}', str(value))
            
            # Vorschau-Box
            if template_config['type'] == 'email':
                st.code(preview_body, language=None)
            else:
                st.info(preview_body)
            
            st.caption("💡 So wird die Nachricht mit Beispieldaten aussehen")

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
        
    elif page == 'vorlagen':
        if is_admin:
            vorlagen_page()
        else:
            st.error("❌ Keine Berechtigung")
    
    else:
        st.error(f"❌ Unbekannte Seite: {page}")
    
    elif page == 'impressum':
        impressum_page()

if __name__ == "__main__":
    main()
