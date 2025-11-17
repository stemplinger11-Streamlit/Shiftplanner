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
# ===== CSS INJECTION (PROFESSIONELLES DESIGN) =====
def inject_css(dark=False):
    """
    Modernes Blau-Weiß-Rot Design mit perfekter Lesbarkeit
    Inspiriert von aktuellen UI/UX Trends 2025
    """
    
    if dark:
        # DARK MODE - Elegante dunkle Töne mit kräftigen Akzenten
        bg_primary = "#0A0E27"          # Sehr dunkles Blau (fast schwarz)
        bg_secondary = "#1A1F3A"        # Dunkles Blau
        bg_surface = "#242B4A"          # Heller als Secondary
        bg_elevated = "#2D3454"         # Noch heller für Cards
        
        text_primary = "#FFFFFF"        # Reines Weiß
        text_secondary = "#B8C5D6"      # Helles Blau-Grau
        text_muted = "#8897AA"          # Gedämpftes Grau
        
        accent_blue = "#4A90E2"         # Helles, freundliches Blau
        accent_red = "#FF4757"          # Kräftiges Rot
        accent_green = "#26DE81"        # Erfolgsmeldungen
        accent_orange = "#FFA502"       # Warnungen
        
        border_color = "#3D4563"        # Subtile Borders
        divider_color = "#2D3454"       # Trennlinien
        
        # Slot-spezifische Farben
        slot_free_bg = "#1E3A5F"        # Dunkles Blau für freie Slots
        slot_free_border = "#4A90E2"    # Helles Blau
        slot_booked_bg = "#3D2A1F"      # Warmes Dunkelbraun
        slot_booked_border = "#FFA502"  # Orange
        slot_blocked_bg = "#2A2A2A"     # Neutrales Grau
        slot_blocked_border = "#555555" # Dunkles Grau
        
    else:
        # LIGHT MODE - Klares, modernes Weiß mit blauen Akzenten
        bg_primary = "#FFFFFF"          # Reines Weiß
        bg_secondary = "#F8FAFB"        # Sehr helles Blau-Grau
        bg_surface = "#F0F4F8"          # Helles Grau-Blau
        bg_elevated = "#FFFFFF"         # Weiß für erhobene Elemente
        
        text_primary = "#1A2332"        # Fast Schwarz
        text_secondary = "#4A5568"      # Dunkles Grau
        text_muted = "#718096"          # Mittleres Grau
        
        accent_blue = "#2B6CB0"         # Kräftiges Blau
        accent_red = "#DC143C"          # Klassisches Crimson Rot
        accent_green = "#38A169"        # Erfolgsmeldungen
        accent_orange = "#DD6B20"       # Warnungen
        
        border_color = "#E2E8F0"        # Helle Borders
        divider_color = "#CBD5E0"       # Sichtbare Trennlinien
        
        # Slot-spezifische Farben
        slot_free_bg = "#EBF8FF"        # Sehr helles Blau
        slot_free_border = "#2B6CB0"    # Kräftiges Blau
        slot_booked_bg = "#FFF5F5"      # Sehr helles Rot
        slot_booked_border = "#FC8181"  # Helles Rot
        slot_blocked_bg = "#F7FAFC"     # Fast Weiß
        slot_blocked_border = "#CBD5E0" # Helles Grau
    
    st.markdown(f"""
    <style>
        /* ===== GLOBALE STYLES ===== */
        .main {{
            background-color: {bg_primary} !important;
            color: {text_primary} !important;
        }}
        
        /* ===== SIDEBAR ===== */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {bg_secondary} 0%, {bg_surface} 100%) !important;
            border-right: 1px solid {border_color} !important;
        }}
        
        section[data-testid="stSidebar"] * {{
            color: {text_primary} !important;
        }}
        
        section[data-testid="stSidebar"] .stButton>button {{
            background-color: {bg_elevated} !important;
            color: {text_primary} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
        }}
        
        section[data-testid="stSidebar"] .stButton>button:hover {{
            background-color: {accent_blue} !important;
            border-color: {accent_blue} !important;
            transform: translateX(4px) !important;
        }}
        
        /* ===== BUTTONS ===== */
        .stButton>button {{
            background: linear-gradient(135deg, {accent_blue} 0%, {accent_blue}DD 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1.5rem !important;
            font-weight: 600 !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        }}
        
        .stButton>button:hover {{
            background: linear-gradient(135deg, {accent_blue}EE 0%, {accent_blue} 100%) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(42, 106, 176, 0.3) !important;
        }}
        
        /* Primary Button (rot für wichtige Aktionen) */
        button[kind="primary"] {{
            background: linear-gradient(135deg, {accent_red} 0%, {accent_red}DD 100%) !important;
        }}
        
        button[kind="primary"]:hover {{
            background: linear-gradient(135deg, {accent_red}EE 0%, {accent_red} 100%) !important;
            box-shadow: 0 4px 12px rgba(220, 20, 60, 0.3) !important;
        }}
        
        /* ===== FORMS & INPUTS ===== */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>select,
        .stNumberInput>div>div>input {{
            background-color: {bg_elevated} !important;
            color: {text_primary} !important;
            border: 2px solid {border_color} !important;
            border-radius: 8px !important;
            padding: 0.5rem !important;
            transition: all 0.3s ease !important;
        }}
        
        .stTextInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus,
        .stSelectbox>div>div>select:focus {{
            border-color: {accent_blue} !important;
            box-shadow: 0 0 0 3px {accent_blue}33 !important;
        }}
        
        /* ===== TABS ===== */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: {bg_secondary} !important;
            border-radius: 8px !important;
            padding: 0.25rem !important;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            color: {text_secondary} !important;
            border-radius: 6px !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
        }}
        
        .stTabs [aria-selected="true"] {{
            background-color: {bg_elevated} !important;
            color: {accent_blue} !important;
            font-weight: 600 !important;
        }}
        
        /* ===== EXPANDER ===== */
        .streamlit-expanderHeader {{
            background-color: {bg_elevated} !important;
            color: {text_primary} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }}
        
        .streamlit-expanderContent {{
            background-color: {bg_surface} !important;
            border: 1px solid {border_color} !important;
            border-radius: 0 0 8px 8px !important;
            border-top: none !important;
        }}
        
        /* ===== METRICS ===== */
        [data-testid="stMetricValue"] {{
            color: {accent_blue} !important;
            font-size: 2rem !important;
            font-weight: 700 !important;
        }}
        
        [data-testid="stMetricLabel"] {{
            color: {text_secondary} !important;
        }}
        
        /* ===== ALERTS ===== */
        .stAlert {{
            border-radius: 8px !important;
            border-left: 4px solid !important;
        }}
        
        div[data-baseweb="notification"][kind="info"] {{
            background-color: {accent_blue}15 !important;
            border-left-color: {accent_blue} !important;
        }}
        
        div[data-baseweb="notification"][kind="success"] {{
            background-color: {accent_green}15 !important;
            border-left-color: {accent_green} !important;
        }}
        
        div[data-baseweb="notification"][kind="warning"] {{
            background-color: {accent_orange}15 !important;
            border-left-color: {accent_orange} !important;
        }}
        
        div[data-baseweb="notification"][kind="error"] {{
            background-color: {accent_red}15 !important;
            border-left-color: {accent_red} !important;
        }}
        
        /* ===== SLOT CARDS (KRITISCH FÜR KALENDER) ===== */
        .slot-card {{
            background-color: {slot_free_bg} !important;
            border: 2px solid {slot_free_border} !important;
            border-radius: 12px !important;
            padding: 1.25rem !important;
            margin: 0.75rem 0 !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
        }}
        
        .slot-card:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
        }}
        
        .slot-card.free {{
            background-color: {slot_free_bg} !important;
            border-color: {slot_free_border} !important;
            border-left: 6px solid {slot_free_border} !important;
        }}
        
        .slot-card.booked {{
            background-color: {slot_booked_bg} !important;
            border-color: {slot_booked_border} !important;
            border-left: 6px solid {slot_booked_border} !important;
        }}
        
        .slot-card.blocked {{
            background-color: {slot_blocked_bg} !important;
            border-color: {slot_blocked_border} !important;
            border-left: 6px solid {slot_blocked_border} !important;
            opacity: 0.6 !important;
        }}
        
        /* ===== TYPOGRAPHY ===== */
        h1, h2, h3, h4, h5, h6 {{
            color: {text_primary} !important;
            font-weight: 700 !important;
        }}
        
        h1 {{
            border-bottom: 3px solid {accent_blue} !important;
            padding-bottom: 0.5rem !important;
            margin-bottom: 1.5rem !important;
        }}
        
        p, span, div {{
            color: {text_primary} !important;
        }}
        
        .stMarkdown {{
            color: {text_primary} !important;
        }}
        
        /* ===== DIVIDER ===== */
        hr {{
            border-color: {divider_color} !important;
            margin: 1.5rem 0 !important;
        }}
        
        /* ===== CHECKBOX & RADIO ===== */
        .stCheckbox label,
        .stRadio label {{
            color: {text_primary} !important;
        }}
        
        /* ===== CODE BLOCKS ===== */
        .stCodeBlock {{
            background-color: {bg_surface} !important;
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
        }}
        
        code {{
            color: {accent_blue} !important;
            background-color: {bg_surface} !important;
            padding: 0.2rem 0.4rem !important;
            border-radius: 4px !important;
        }}
        
        /* ===== DATAFRAMES ===== */
        .dataframe {{
            border: 1px solid {border_color} !important;
            border-radius: 8px !important;
        }}
        
        /* ===== FORMS ===== */
        [data-testid="stForm"] {{
            background-color: {bg_elevated} !important;
            border: 1px solid {border_color} !important;
            border-radius: 12px !important;
            padding: 1.5rem !important;
        }}
        
        /* ===== CONTAINER ===== */
        .element-container {{
            margin-bottom: 0.75rem !important;
        }}
        
        /* ===== CAPTION ===== */
        .st-emotion-cache-16idsys p {{
            color: {text_muted} !important;
            font-size: 0.875rem !important;
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

# ===== E-MAIL KLASSE (VOLLSTÄNDIG MIT TEMPLATE-SUPPORT) =====
class Mailer:
    """E-Mail Versand mit detailliertem Error-Handling und Template-System"""
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
            msg.attach(MIMEText(body, 'plain'))
            
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
        """Buchungsbestätigung senden - verwendet Template"""
        # Lade Template aus Firestore
        subject_template = ww_db.get_setting('email_booking_subject', 'Buchungsbestätigung - {date}')
        body_template = ww_db.get_setting('email_booking_body', 
            """Hallo {name},

deine Buchung wurde bestätigt:

📅 Datum: {date}
⏰ Uhrzeit: {time}

Bei Fragen melde dich gerne unter {org_email}.

Viele Grüße,
Dein {org_name} Team 🌊""")
        
        # Platzhalter ersetzen
        data = {
            'name': user_name,
            'date': fmt_de(slot_date),
            'time': slot_time,
            'email': user_email,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht'),
            'org_email': self.admin_receiver,
            'current_date': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        
        subject = subject_template
        body = body_template
        for key, value in data.items():
            subject = subject.replace('{' + key + '}', str(value))
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(user_email, subject, body)
    
    def send_cancellation(self, user_email, user_name, slot_date, slot_time):
        """Stornierungsbestätigung senden - verwendet Template"""
        subject_template = ww_db.get_setting('email_cancellation_subject', 'Stornierung - {date}')
        body_template = ww_db.get_setting('email_cancellation_body',
            """Hallo {name},

deine Buchung wurde storniert:

📅 Datum: {date}
⏰ Uhrzeit: {time}

Viele Grüße,
Dein {org_name} Team 🌊""")
        
        data = {
            'name': user_name,
            'date': fmt_de(slot_date),
            'time': slot_time,
            'email': user_email,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht'),
            'org_email': self.admin_receiver,
            'current_date': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        
        subject = subject_template
        body = body_template
        for key, value in data.items():
            subject = subject.replace('{' + key + '}', str(value))
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(user_email, subject, body)
    
    def send_reminder(self, user_email, user_name, slot_date, slot_time):
        """Erinnerung senden - verwendet Template"""
        subject_template = ww_db.get_setting('email_reminder_subject', '⏰ Erinnerung: Dienst morgen - {date}')
        body_template = ww_db.get_setting('email_reminder_body',
            """Hallo {name},

dein Dienst ist morgen:

📅 Datum: {date}
⏰ Uhrzeit: {time}

Bis morgen!
Dein {org_name} Team 🌊""")
        
        data = {
            'name': user_name,
            'date': fmt_de(slot_date),
            'time': slot_time,
            'email': user_email,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht'),
            'org_email': self.admin_receiver,
            'current_date': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        
        subject = subject_template
        body = body_template
        for key, value in data.items():
            subject = subject.replace('{' + key + '}', str(value))
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(user_email, subject, body)
    
    def send_welcome(self, user_email, user_name):
        """Willkommens-E-Mail senden - NEU"""
        subject_template = ww_db.get_setting('email_welcome_subject', 'Willkommen bei {org_name}!')
        body_template = ww_db.get_setting('email_welcome_body',
            """Hallo {name},

herzlich willkommen bei {org_name}! 🌊

Dein Account wurde erfolgreich erstellt.
Du kannst dich jetzt anmelden und Schichten buchen.

📧 E-Mail: {email}

Bei Fragen erreichst du uns unter {org_email}.

Viele Grüße,
Dein {org_name} Team""")
        
        data = {
            'name': user_name,
            'email': user_email,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht'),
            'org_email': self.admin_receiver,
            'current_date': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        
        subject = subject_template
        body = body_template
        for key, value in data.items():
            subject = subject.replace('{' + key + '}', str(value))
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(user_email, subject, body)
    
    def send_admin_notification(self, user_name, user_email, user_phone, slot_date, slot_time):
        """Admin-Benachrichtigung bei neuer Buchung - NEU"""
        if not self.admin_receiver:
            return False, "Keine Admin-E-Mail konfiguriert"
        
        subject_template = ww_db.get_setting('email_admin_notification_subject', '🔔 Neue Buchung: {name} - {date}')
        body_template = ww_db.get_setting('email_admin_notification_body',
            """Neue Buchung im Dienstplan:

👤 Name: {name}
📧 E-Mail: {email}
📱 Telefon: {phone}

📅 Datum: {date}
⏰ Uhrzeit: {time}

Gebucht am: {current_date}""")
        
        data = {
            'name': user_name,
            'email': user_email,
            'phone': user_phone if user_phone else 'Nicht angegeben',
            'date': fmt_de(slot_date),
            'time': slot_time,
            'org_name': ww_db.get_setting('org_name', 'Wasserwacht'),
            'org_email': self.admin_receiver,
            'current_date': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        
        subject = subject_template
        body = body_template
        for key, value in data.items():
            subject = subject.replace('{' + key + '}', str(value))
            body = body.replace('{' + key + '}', str(value))
        
        return self.send(self.admin_receiver, subject, body)

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
            ('profil', '👤 Profil'),
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
# ===== KALENDER SEITE (KOMPLETT ÜBERARBEITET) =====
def kalender_page():
    user = st.session_state.user
    
    st.title("📅 Wochenschichten buchen")
    st.caption("Buchen Sie Ihre Schichten für die kommenden Wochen")
    
    # Session State für ausgewählte Woche
    if 'selected_week' not in st.session_state:
        st.session_state.selected_week = week_start()
    
    # Wochenauswahl - Übersichtliche Darstellung
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    
    with col1:
        kw = st.session_state.selected_week.isocalendar()[1]
        jahr = st.session_state.selected_week.year
        st.markdown(f"### KW {kw}, {jahr}")
        st.caption(f"Woche ab {fmt_de(st.session_state.selected_week)}")
    
    with col2:
        if st.button("⬅️ Vorherige", use_container_width=True):
            st.session_state.selected_week = week_start(
                st.session_state.selected_week - timedelta(days=7)
            )
            st.rerun()
    
    with col3:
        if st.button("Nächste ➡️", use_container_width=True):
            st.session_state.selected_week = week_start(
                st.session_state.selected_week + timedelta(days=7)
            )
            st.rerun()
    
    with col4:
        if st.button("🔄 Diese Woche", use_container_width=True):
            st.session_state.selected_week = week_start()
            st.rerun()
    
    st.divider()
    
    # Lade Buchungen für diese Woche
    ws_str = st.session_state.selected_week.strftime("%Y-%m-%d")
    bookings = ww_db.get_week_bookings(ws_str)
    
    # Info-Box für User
    with st.expander("ℹ️ Legende", expanded=False):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**🟢 Verfügbar**")
            st.caption("Slot kann gebucht werden")
        with col_b:
            st.markdown("**✅ Gebucht**")
            st.caption("Bereits von einem User gebucht")
        with col_c:
            st.markdown("**🚫 Blockiert**")
            st.caption("Feiertag oder Sommerpause")
    
    st.markdown("---")
    
    # Slots anzeigen mit neuem Design
    for slot_config in WEEKLY_SLOTS:
        sd = slot_date(st.session_state.selected_week, slot_config['day'])
        slot_time = f"{slot_config['start']} - {slot_config['end']}"
        
        # Prüfe Status
        blocked = is_blocked(sd)
        reason = block_reason(sd) if blocked else None
        booking = next((b for b in bookings if b['slot_date'] == sd and slot_time in b.get('slot_time', '')), None)
        
        # Bestimme CSS-Klasse und Farbe
        if blocked:
            card_class = "slot-card blocked"
            status_icon = "🚫"
            status_text = f"Blockiert: {reason}"
            border_color = "#CBD5E0" if not st.session_state.dark_mode else "#555555"
        elif booking:
            card_class = "slot-card booked"
            status_icon = "✅"
            status_text = f"Gebucht von: {booking.get('user_name', 'N/A')}"
            border_color = "#FFA502"
        else:
            card_class = "slot-card free"
            status_icon = "🟢"
            status_text = "Verfügbar"
            border_color = "#4A90E2"
        
        # Slot-Card mit HTML für bessere Kontrolle
        st.markdown(
            f'<div class="{card_class}" style="border-left: 6px solid {border_color} !important;">', 
            unsafe_allow_html=True
        )
        
        # Slot-Inhalt in Spalten
        col_info, col_status, col_action = st.columns([4, 3, 2])
        
        with col_info:
            # Datum & Uhrzeit prominent darstellen
            st.markdown(f"### {slot_config['day_name']}, {fmt_de(sd)}")
            st.markdown(f"**⏰ {slot_time}**")
        
        with col_status:
            # Status mit Icon
            if blocked:
                st.error(f"{status_icon} {status_text}")
            elif booking:
                st.warning(f"{status_icon} {status_text}")
                if booking.get('user_phone'):
                    st.caption(f"📱 {booking.get('user_phone')}")
            else:
                st.success(f"{status_icon} {status_text}")
        
        with col_action:
            # Aktions-Buttons
            if not blocked:
                if booking:
                    # User kann nur eigene Buchungen stornieren
                    if booking.get('user_email') == user['email']:
                        if st.button("❌ Stornieren", key=f"cancel_{sd}_{slot_time}", use_container_width=True):
                            if ww_db.cancel_booking(booking['id'], user['email']):
                                # Stornierungsbestätigung senden
                                success, msg = mailer.send_cancellation(
                                    user['email'], 
                                    user['name'], 
                                    sd, 
                                    slot_time
                                )
                                st.success("✅ Buchung storniert!")
                                if success:
                                    st.info("📧 Bestätigung per E-Mail versendet")
                                st.rerun()
                            else:
                                st.error("❌ Fehler beim Stornieren")
                    else:
                        # Andere Buchung - nur Info
                        st.caption(f"Gebucht von\n{booking.get('user_name', 'N/A')}")
                else:
                    # Slot ist frei - Buchungsbutton
                    if st.button("📝 Jetzt buchen", key=f"book_{sd}_{slot_time}", use_container_width=True, type="primary"):
                        # Buchung erstellen
                        success, msg = ww_db.create_booking(
                            sd, 
                            slot_time, 
                            user['email'], 
                            user['name'], 
                            user.get('phone', '')
                        )
                        
                        if success:
                            st.success(f"✅ {msg}")
                            
                            # E-Mail-Benachrichtigung
                            if user.get('email_notifications_booking', True):
                                mail_success, mail_msg = mailer.send_booking_confirmation(
                                    user['email'], 
                                    user['name'], 
                                    sd, 
                                    slot_time
                                )
                                if mail_success:
                                    st.info("📧 Bestätigung per E-Mail versendet")
                                else:
                                    st.warning(f"⚠️ E-Mail konnte nicht versendet werden: {mail_msg}")
                            
                            # SMS-Benachrichtigung (falls aktiviert)
                            if user.get('sms_notifications_booking', False) and user.get('phone'):
                                sms_success, sms_msg = sms_client.send_booking_confirmation(
                                    user['phone'], 
                                    user['name'], 
                                    sd, 
                                    slot_time
                                )
                                if sms_success:
                                    st.info("📱 Bestätigung per SMS versendet")
                            
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
        
        # Card schließen
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Abstand zwischen Slots
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
    
    # Footer-Info
    st.divider()
    
    # Zusammenfassung für diese Woche
    total_slots = len(WEEKLY_SLOTS)
    booked_slots = len([b for b in bookings if b.get('status') == 'confirmed'])
    free_slots = total_slots - booked_slots - len([s for s in WEEKLY_SLOTS if is_blocked(slot_date(st.session_state.selected_week, s['day']))])
    
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    
    with col_sum1:
        st.metric("Slots gesamt", total_slots)
    with col_sum2:
        st.metric("Gebucht", booked_slots)
    with col_sum3:
        st.metric("Verfügbar", free_slots)
    
    # Hilfe-Text
    st.caption("💡 **Tipp:** Buchen Sie frühzeitig, um Ihren Wunschtermin zu sichern!")

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

# ===== PROFIL-SEITE (FÜR ALLE USER) =====
def profil_page():
    user = st.session_state.user
    is_admin = user.get('role') == 'admin'
    
    # Titel mit Admin-Badge
    if is_admin:
        st.title("👤 Mein Profil 🔑")
        st.info("👑 **Administrator**")
    else:
        st.title("👤 Mein Profil")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📋 Profil-Info", "🔔 Benachrichtigungen", "🔒 Sicherheit"])
    
    # ===== TAB 1: PROFIL-INFO =====
    with tab1:
        st.subheader("Persönliche Informationen")
        
        with st.form("profil_info"):
            # Name (editierbar)
            name = st.text_input(
                "Name",
                value=user.get('name', ''),
                help="Ihr vollständiger Name"
            )
            
            # E-Mail (editierbar mit Warnung)
            st.markdown("**E-Mail-Adresse**")
            email = st.text_input(
                "E-Mail",
                value=user.get('email', ''),
                help="Ihre E-Mail-Adresse für Login und Benachrichtigungen",
                label_visibility="collapsed"
            )
            st.warning("⚠️ Wichtig: Prüfen Sie die E-Mail-Adresse sorgfältig! Sie benötigen sie für den Login.")
            
            # Telefon (editierbar mit Auto-Format)
            st.markdown("**Telefonnummer**")
            phone = st.text_input(
                "Telefon",
                value=user.get('phone', ''),
                placeholder="z.B. 0172 1234567 oder +49 172 1234567",
                help="Für SMS-Benachrichtigungen (optional)",
                label_visibility="collapsed"
            )
            
            # Vorschau der formatierten Nummer
            if phone:
                formatted_phone = sms_client.format_phone_number(phone)
                if formatted_phone:
                    st.caption(f"📱 Formatiert: {formatted_phone}")
                else:
                    st.caption("⚠️ Ungültiges Format - bitte prüfen")
            
            st.divider()
            
            # Read-Only Felder
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Rolle", value=user.get('role', 'user'), disabled=True)
            with col2:
                created = user.get('created_at')
                if created and hasattr(created, 'strftime'):
                    created_str = created.strftime('%d.%m.%Y')
                else:
                    created_str = "N/A"
                st.text_input("Mitglied seit", value=created_str, disabled=True)
            
            # Speichern-Button
            submit = st.form_submit_button("💾 Änderungen speichern", use_container_width=True, type="primary")
            
            if submit:
                # Validierung
                if not name or not email:
                    st.error("❌ Name und E-Mail sind Pflichtfelder!")
                elif len(name) < 2:
                    st.error("❌ Name muss mindestens 2 Zeichen haben")
                elif '@' not in email or '.' not in email:
                    st.error("❌ Ungültige E-Mail-Adresse")
                else:
                    # Prüfe ob E-Mail bereits von anderem User verwendet wird
                    existing_user = ww_db.get_user(email)
                    if existing_user and existing_user.get('id') != user['id']:
                        st.error(f"❌ E-Mail-Adresse '{email}' wird bereits verwendet!")
                    else:
                        # Speichern
                        success = ww_db.update_user(
                            user['id'],
                            name=name,
                            email=email,
                            phone=phone
                        )
                        
                        if success:
                            # Session aktualisieren
                            st.session_state.user['name'] = name
                            st.session_state.user['email'] = email
                            st.session_state.user['phone'] = phone
                            
                            st.success("✅ Profil erfolgreich aktualisiert!")
                            st.rerun()
                        else:
                            st.error("❌ Fehler beim Speichern")
    
    # ===== TAB 2: BENACHRICHTIGUNGEN =====
    with tab2:
        st.subheader("Benachrichtigungs-Einstellungen")
        st.caption("Wählen Sie, welche Benachrichtigungen Sie erhalten möchten")
        
        with st.form("benachrichtigungen"):
            st.markdown("### ✉️ E-Mail-Benachrichtigungen")
            
            email_booking = st.checkbox(
                "Buchungsbestätigungen",
                value=user.get('email_notifications_booking', True),
                help="E-Mail bei jeder neuen Buchung"
            )
            
            email_reminder = st.checkbox(
                "Erinnerungen (24h vorher)",
                value=user.get('email_notifications_reminder', True),
                help="E-Mail-Erinnerung 24h vor Ihrem Dienst"
            )
            
            email_cancellation = st.checkbox(
                "Stornierungen",
                value=user.get('email_notifications_cancellation', True),
                help="E-Mail bei Stornierung"
            )
            
            st.divider()
            st.markdown("### 📱 SMS-Benachrichtigungen")
            
            if not user.get('phone'):
                st.info("💡 Tipp: Hinterlegen Sie eine Telefonnummer unter 'Profil-Info', um SMS zu erhalten.")
            
            sms_booking = st.checkbox(
                "Buchungsbestätigungen",
                value=user.get('sms_notifications_booking', False),
                help="SMS bei jeder neuen Buchung",
                disabled=not user.get('phone')
            )
            
            sms_reminder = st.checkbox(
                "Erinnerungen",
                value=user.get('sms_notifications_reminder', False),
                help="SMS-Erinnerung vor Ihrem Dienst",
                disabled=not user.get('phone')
            )
            
            st.divider()
            
            # Speichern-Button
            submit = st.form_submit_button("💾 Einstellungen speichern", use_container_width=True, type="primary")
            
            if submit:
                success = ww_db.update_user(
                    user['id'],
                    email_notifications_booking=email_booking,
                    email_notifications_reminder=email_reminder,
                    email_notifications_cancellation=email_cancellation,
                    sms_notifications_booking=sms_booking,
                    sms_notifications_reminder=sms_reminder
                )
                
                if success:
                    # Session aktualisieren
                    st.session_state.user['email_notifications_booking'] = email_booking
                    st.session_state.user['email_notifications_reminder'] = email_reminder
                    st.session_state.user['email_notifications_cancellation'] = email_cancellation
                    st.session_state.user['sms_notifications_booking'] = sms_booking
                    st.session_state.user['sms_notifications_reminder'] = sms_reminder
                    
                    st.success("✅ Einstellungen gespeichert!")
                    st.rerun()
                else:
                    st.error("❌ Fehler beim Speichern")
    
    # ===== TAB 3: SICHERHEIT (PASSWORT ÄNDERN) =====
    with tab3:
        st.subheader("Passwort ändern")
        st.caption("Ändern Sie hier Ihr Passwort")
        
        with st.form("passwort_aendern"):
            old_password = st.text_input(
                "Aktuelles Passwort",
                type="password",
                help="Geben Sie Ihr aktuelles Passwort ein"
            )
            
            new_password = st.text_input(
                "Neues Passwort",
                type="password",
                help="Mindestens 6 Zeichen"
            )
            
            new_password_confirm = st.text_input(
                "Neues Passwort bestätigen",
                type="password",
                help="Wiederholen Sie das neue Passwort"
            )
            
            st.divider()
            
            # Speichern-Button
            submit = st.form_submit_button("🔒 Passwort ändern", use_container_width=True, type="primary")
            
            if submit:
                # Validierung
                if not old_password or not new_password or not new_password_confirm:
                    st.error("❌ Bitte alle Felder ausfüllen!")
                elif hash_pw(old_password) != user.get('password_hash'):
                    st.error("❌ Aktuelles Passwort ist falsch!")
                elif new_password != new_password_confirm:
                    st.error("❌ Neue Passwörter stimmen nicht überein!")
                elif len(new_password) < 6:
                    st.error("❌ Passwort muss mindestens 6 Zeichen haben!")
                elif old_password == new_password:
                    st.error("❌ Neues Passwort muss sich vom alten unterscheiden!")
                else:
                    # Passwort ändern
                    success = ww_db.update_user(
                        user['id'],
                        password_hash=hash_pw(new_password)
                    )
                    
                    if success:
                        # Session aktualisieren
                        st.session_state.user['password_hash'] = hash_pw(new_password)
                        
                        st.success("✅ Passwort erfolgreich geändert!")
                        st.balloons()
                    else:
                        st.error("❌ Fehler beim Ändern des Passworts")

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
# ===== VERWALTUNG (ADMIN) - ERWEITERT MIT FREIEN SLOTS =====
# ===== VERWALTUNG (ADMIN) - KOMPLETT MIT ADMIN-BUCHUNG =====
def verwaltung_page():
    st.title("⚙️ Verwaltung")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Alle Buchungen", 
        "🔍 Freie Slots", 
        "👥 Admin-Buchung", 
        "🗑️ Archivieren", 
        "⚙️ Einstellungen"
    ])
    
    # ===== TAB 1: ALLE BUCHUNGEN (wie gehabt) =====
    with tab1:
        st.subheader("Alle Buchungen")
        
        col1, col2 = st.columns(2)
        with col1:
            filter_status = st.selectbox("Status", ["alle", "confirmed", "cancelled"])
        with col2:
            filter_future = st.checkbox("Nur zukünftige", value=True)
        
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
    
    # ===== TAB 2: FREIE SLOTS (wie zuvor erstellt) =====
    with tab2:
        st.subheader("🔍 Freie Slots in den nächsten 4 Wochen")
        st.caption("Übersicht über alle noch nicht gebuchten Schichten")
        
        today = datetime.now().date()
        weeks_ahead = 4
        end_date = today + timedelta(days=7 * weeks_ahead)
        
        all_slots = []
        current_week = week_start(today)
        
        for week_offset in range(weeks_ahead):
            ws = current_week + timedelta(days=7 * week_offset)
            
            for slot_config in WEEKLY_SLOTS:
                slot_d = slot_date(ws, slot_config['day'])
                slot_date_obj = datetime.strptime(slot_d, '%Y-%m-%d').date()
                
                if slot_date_obj < today:
                    continue
                
                if is_blocked(slot_d):
                    continue
                
                slot_time = f"{slot_config['start']} - {slot_config['end']}"
                booking = ww_db.get_booking(slot_d, slot_time)
                
                if not booking:
                    days_until = (slot_date_obj - today).days
                    
                    if days_until < 7:
                        color = "🔴"
                        urgency = "kritisch"
                    elif days_until < 14:
                        color = "🟠"
                        urgency = "achtung"
                    else:
                        color = "🟢"
                        urgency = "entspannt"
                    
                    all_slots.append({
                        'date': slot_d,
                        'date_obj': slot_date_obj,
                        'weekday': slot_config['day_name'],
                        'time': slot_time,
                        'days_until': days_until,
                        'color': color,
                        'urgency': urgency
                    })
        
        all_slots.sort(key=lambda x: x['date'])
        
        if all_slots:
            st.markdown("### 📊 Zusammenfassung")
            
            kritisch = len([s for s in all_slots if s['urgency'] == 'kritisch'])
            achtung = len([s for s in all_slots if s['urgency'] == 'achtung'])
            entspannt = len([s for s in all_slots if s['urgency'] == 'entspannt'])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Gesamt", len(all_slots))
            with col2:
                st.metric("🔴 Kritisch", kritisch)
            with col3:
                st.metric("🟠 Achtung", achtung)
            with col4:
                st.metric("🟢 Entspannt", entspannt)
            
            st.divider()
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                df = pd.DataFrame([{
                    'Datum': fmt_de(s['date']),
                    'Wochentag': s['weekday'],
                    'Uhrzeit': s['time'],
                    'Tage bis Slot': s['days_until'],
                    'Dringlichkeit': s['urgency']
                } for s in all_slots])
                
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Als CSV exportieren",
                    csv,
                    file_name=f"freie_slots_{today.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col_b:
                if st.button("📧 Per E-Mail senden", use_container_width=True):
                    if mailer.admin_receiver:
                        email_body = f"""Freie Slots - Übersicht vom {today.strftime('%d.%m.%Y')}

Gesamt: {len(all_slots)} freie Slots
🔴 Kritisch: {kritisch}
🟠 Achtung: {achtung}
🟢 Entspannt: {entspannt}

Details:
---

"""
                        for s in all_slots:
                            email_body += f"{s['color']} {fmt_de(s['date'])} ({s['weekday']}) - {s['time']} - in {s['days_until']} Tagen\n"
                        
                        csv_bytes = csv.encode('utf-8')
                        
                        success, msg = mailer.send(
                            mailer.admin_receiver,
                            f"🔍 Freie Slots - {today.strftime('%d.%m.%Y')}",
                            email_body,
                            attachments=[(f"freie_slots_{today.strftime('%Y%m%d')}.csv", csv_bytes)]
                        )
                        
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.error("❌ Keine Admin-E-Mail konfiguriert")
            
            st.divider()
            st.markdown("### 📋 Details")
            
            for slot in all_slots:
                with st.container():
                    col1, col2, col3, col4 = st.columns([1, 3, 3, 2])
                    
                    with col1:
                        st.markdown(f"### {slot['color']}")
                    with col2:
                        st.markdown(f"**{fmt_de(slot['date'])}**")
                        st.caption(slot['weekday'])
                    with col3:
                        st.markdown(f"**{slot['time']}**")
                        st.caption(f"in {slot['days_until']} Tagen")
                    with col4:
                        if slot['urgency'] == 'kritisch':
                            st.error("Dringend!")
                        elif slot['urgency'] == 'achtung':
                            st.warning("Bald fällig")
                        else:
                            st.success("Zeit vorhanden")
                    
                    st.divider()
        else:
            st.success("🎉 Alle Slots in den nächsten 4 Wochen sind gebucht!")
    
    # ===== TAB 3: ADMIN-BUCHUNG (NEU) =====
    with tab3:
        st.subheader("👥 Schichten für User buchen & umbuchen")
        
        sub_tab1, sub_tab2 = st.tabs(["➕ Neue Buchung", "🔄 Umbuchung"])
        
        # --- SUB-TAB 1: NEUE BUCHUNG ---
        with sub_tab1:
            st.markdown("### Neue Buchung für User erstellen")
            st.caption("Buchen Sie eine Schicht im Namen eines Users")
            
            with st.form("admin_neue_buchung"):
                # User auswählen
                all_users = ww_db.get_all_users()
                active_users = [u for u in all_users if u.get('active', True)]
                
                if not active_users:
                    st.error("Keine aktiven User gefunden!")
                else:
                    user_options = {f"{u['name']} ({u['email']})": u for u in active_users}
                    selected_user_str = st.selectbox(
                        "User auswählen",
                        options=list(user_options.keys()),
                        help="Wählen Sie den User, für den Sie buchen möchten"
                    )
                    selected_user = user_options[selected_user_str]
                    
                    # Datum & Zeit
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Wähle Woche
                        today = datetime.now().date()
                        weeks = []
                        for i in range(8):  # Nächsten 8 Wochen
                            ws = week_start(today + timedelta(days=7*i))
                            weeks.append((f"KW {ws.isocalendar()[1]} ({fmt_de(ws)})", ws))
                        
                        selected_week_str = st.selectbox(
                            "Woche auswählen",
                            options=[w[0] for w in weeks]
                        )
                        selected_week = [w[1] for w in weeks if w[0] == selected_week_str][0]
                    
                    with col2:
                        # Verfügbare Slots für diese Woche
                        available_slots = []
                        for slot_config in WEEKLY_SLOTS:
                            slot_d = slot_date(selected_week, slot_config['day'])
                            slot_date_obj = datetime.strptime(slot_d, '%Y-%m-%d').date()
                            
                            if slot_date_obj < today:
                                continue
                            
                            slot_time = f"{slot_config['start']} - {slot_config['end']}"
                            booking = ww_db.get_booking(slot_d, slot_time)
                            blocked = is_blocked(slot_d)
                            
                            label = f"{slot_config['day_name']} {fmt_de(slot_d)} | {slot_time}"
                            
                            if booking:
                                label += f" (Gebucht: {booking['user_name']})"
                                available_slots.append((label, slot_d, slot_time, True, booking))
                            elif blocked:
                                label += f" (Blockiert: {block_reason(slot_d)})"
                                available_slots.append((label, slot_d, slot_time, True, None))
                            else:
                                label += " (Frei)"
                                available_slots.append((label, slot_d, slot_time, False, None))
                        
                        if not available_slots:
                            st.warning("Keine Slots in dieser Woche verfügbar")
                        else:
                            selected_slot_str = st.selectbox(
                                "Slot auswählen",
                                options=[s[0] for s in available_slots]
                            )
                            selected_slot = [s for s in available_slots if s[0] == selected_slot_str][0]
                    
                    # Optionen
                    notify_user = st.checkbox("User per E-Mail/SMS benachrichtigen", value=True)
                    
                    # Submit
                    submit = st.form_submit_button("📝 Buchung erstellen", use_container_width=True, type="primary")
                    
                    if submit:
                        slot_d = selected_slot[1]
                        slot_time = selected_slot[2]
                        is_occupied = selected_slot[3]
                        
                        if is_occupied:
                            st.error("❌ Dieser Slot ist bereits gebucht oder blockiert!")
                        else:
                            # Buchung erstellen
                            success, msg = ww_db.create_booking(
                                slot_d,
                                slot_time,
                                selected_user['email'],
                                selected_user['name'],
                                selected_user.get('phone', '')
                            )
                            
                            if success:
                                st.success(f"✅ Buchung erstellt für {selected_user['name']}!")
                                
                                # Benachrichtigung
                                if notify_user:
                                    # E-Mail
                                    email_success, email_msg = mailer.send_booking_confirmation(
                                        selected_user['email'],
                                        selected_user['name'],
                                        slot_d,
                                        slot_time
                                    )
                                    if email_success:
                                        st.info(f"📧 {email_msg}")
                                    
                                    # SMS
                                    if selected_user.get('phone') and selected_user.get('sms_notifications_booking'):
                                        sms_success, sms_msg = sms_client.send_booking_confirmation(
                                            selected_user['phone'],
                                            selected_user['name'],
                                            slot_d,
                                            slot_time
                                        )
                                        if sms_success:
                                            st.info(f"📱 {sms_msg}")
                                
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
        
        # --- SUB-TAB 2: UMBUCHUNG ---
        with sub_tab2:
            st.markdown("### Bestehende Buchung umbuchen")
            st.caption("Übertragen Sie eine Buchung von einem User auf einen anderen")
            
            with st.form("admin_umbuchung"):
                # Zukünftige Buchungen laden
                today = datetime.now().date().strftime("%Y-%m-%d")
                future_bookings = []
                
                try:
                    for doc in db.collection('bookings').where('status', '==', 'confirmed').stream():
                        b = doc.to_dict()
                        b['id'] = doc.id
                        if b.get('slot_date', '') >= today:
                            future_bookings.append(b)
                except:
                    pass
                
                if not future_bookings:
                    st.info("Keine zukünftigen Buchungen vorhanden")
                else:
                    # Sortieren
                    future_bookings.sort(key=lambda x: x['slot_date'])
                    
                    # Buchung auswählen
                    booking_options = {
                        f"{fmt_de(b['slot_date'])} | {b['slot_time']} | {b['user_name']}": b
                        for b in future_bookings
                    }
                    
                    selected_booking_str = st.selectbox(
                        "Buchung auswählen",
                        options=list(booking_options.keys()),
                        help="Wählen Sie die Buchung, die umgebucht werden soll"
                    )
                    selected_booking = booking_options[selected_booking_str]
                    
                    st.info(f"**Aktuell gebucht von:** {selected_booking['user_name']} ({selected_booking['user_email']})")
                    
                    # Neuen User auswählen
                    all_users = ww_db.get_all_users()
                    active_users = [u for u in all_users if u.get('active', True) and u['email'] != selected_booking['user_email']]
                    
                    if not active_users:
                        st.error("Keine anderen User verfügbar!")
                    else:
                        user_options = {f"{u['name']} ({u['email']})": u for u in active_users}
                        new_user_str = st.selectbox(
                            "Neuer User",
                            options=list(user_options.keys()),
                            help="Wählen Sie den neuen User für diese Buchung"
                        )
                        new_user = user_options[new_user_str]
                        
                        # Kommentar
                        comment = st.text_area(
                            "Kommentar (optional)",
                            placeholder="z.B. 'Krankheit', 'Urlaub', 'Tausch', etc.",
                            help="Grund für die Umbuchung (wird in Benachrichtigung erwähnt)"
                        )
                        
                        # Benachrichtigung
                        notify_users = st.checkbox("Beide User benachrichtigen", value=True)
                        
                        # Submit
                        submit = st.form_submit_button("🔄 Umbuchung durchführen", use_container_width=True, type="primary")
                        
                        if submit:
                            # Alte Buchung löschen
                            try:
                                db.collection('bookings').document(selected_booking['id']).delete()
                            except:
                                st.error("Fehler beim Löschen der alten Buchung")
                                st.stop()
                            
                            # Neue Buchung erstellen
                            success, msg = ww_db.create_booking(
                                selected_booking['slot_date'],
                                selected_booking['slot_time'],
                                new_user['email'],
                                new_user['name'],
                                new_user.get('phone', '')
                            )
                            
                            if success:
                                st.success(f"✅ Umbuchung erfolgreich! Slot wurde von {selected_booking['user_name']} auf {new_user['name']} übertragen.")
                                
                                # Benachrichtigungen
                                if notify_users:
                                    # Alter User: Stornierung
                                    mailer.send_cancellation(
                                        selected_booking['user_email'],
                                        selected_booking['user_name'],
                                        selected_booking['slot_date'],
                                        selected_booking['slot_time']
                                    )
                                    
                                    # Neuer User: Buchungsbestätigung
                                    mailer.send_booking_confirmation(
                                        new_user['email'],
                                        new_user['name'],
                                        selected_booking['slot_date'],
                                        selected_booking['slot_time']
                                    )
                                    
                                    if comment:
                                        st.info(f"💬 Kommentar: {comment}")
                                    
                                    st.info("📧 Beide User wurden benachrichtigt")
                                
                                st.rerun()
                            else:
                                st.error(f"❌ Fehler bei neuer Buchung: {msg}")
    
    # ===== TAB 4: ARCHIVIEREN (wie gehabt) =====
    with tab4:
        st.subheader("🗑️ Alte Buchungen archivieren")
        st.info("Buchungen älter als 12 Monate werden archiviert.")
        
        if st.button("Archivierung starten"):
            count = ww_db.archive_old()
            if count > 0:
                st.success(f"✅ {count} Buchungen archiviert")
            else:
                st.info("Keine Buchungen zum Archivieren gefunden")
    
    # ===== TAB 5: EINSTELLUNGEN (wie gehabt) =====
    with tab5:
        st.subheader("⚙️ Systemeinstellungen")
        
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
        
    elif page == 'impressum':
        impressum_page()
        
    elif page == 'profil':
        profil_page()
        
    elif page == 'vorlagen':
        if is_admin:
            vorlagen_page()
        else:
            st.error("❌ Keine Berechtigung")
    
    else:
        st.error(f"❌ Unbekannte Seite: {page}")

if __name__ == "__main__":
    main()