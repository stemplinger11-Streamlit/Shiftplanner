"""
Wasserwacht Dienstplan+ V8.0 - Debug Edition
Alle Bugs behoben | Admin Debug-Panel | E-Mail/SMS funktionieren | Production-Ready
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
VERSION = "8.0 - Debug Edition"
TIMEZONE_STR = "Europe/Berlin"
TZ = pytz.timezone(TIMEZONE_STR)

# ===== FIRESTORE SETUP =====
try:
    if hasattr(st, 'secrets') and 'firebase' in st.secrets:
        firebase_config = dict(st.secrets['firebase'])
        creds = service_account.Credentials.from_service_account_info(firebase_config)
        db = firestore.Client(credentials=creds, project=firebase_config['project_id'])
    else:
        db = None
except Exception as e:
    st.error(f"Firebase Initialisierung fehlgeschlagen: {e}")
    db = None

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
        # Validierung
        if not self.user or not self.pw:
            error_msg = "❌ E-Mail: Keine SMTP Credentials in secrets.toml konfiguriert"
            return False, error_msg
        
        if not to:
            error_msg = "❌ E-Mail: Keine Empfänger-Adresse angegeben"
            return False, error_msg
        
        try:
            # E-Mail erstellen
            msg = MIMEMultipart()
            msg['From'] = email.utils.formataddr((self.fromname, self.user))
            msg['To'] = to
            msg['Subject'] = subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            
            # Body hinzufügen
            msg.attach(MIMEText(body, 'html'))
            
            # Attachments hinzufügen
            if attachments:
                for filename, data in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(data)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={filename}')
                    msg.attach(part)
            
            # SMTP Verbindung mit erhöhtem Timeout
            with smtplib.SMTP(self.server, self.port, timeout=60) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                
                # Login
                try:
                    smtp.login(self.user, self.pw)
                except smtplib.SMTPAuthenticationError as auth_err:
                    error_msg = f"❌ SMTP Login fehlgeschlagen: {str(auth_err)}\n\nPrüfen Sie:\n1. Ist SMTP_USER korrekt? (aktuell: {self.user})\n2. Verwenden Sie ein Gmail App-Passwort (nicht Ihr normales Passwort)?\n3. Ist 2-Faktor-Auth bei Gmail aktiviert?"
                    return False, error_msg
                
                # E-Mail senden
                smtp.send_message(msg)
            
            success_msg = f"✅ E-Mail erfolgreich an {to} gesendet"
            return True, success_msg
            
        except smtplib.SMTPException as smtp_err:
            error_msg = f"❌ SMTP Fehler: {type(smtp_err).__name__}: {str(smtp_err)}"
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ E-Mail Fehler: {type(e).__name__}: {str(e)}"
            return False, error_msg

# ===== SMS KLASSE (KORRIGIERT) =====
class TwilioSMS:
    """SMS Versand mit Twilio und robuster Telefonnummer-Formatierung"""
    def __init__(self):
        if hasattr(st, 'secrets'):
            self.enabled = st.secrets.get("ENABLE_SMS_REMINDER", "false").lower() == "true"
            self.account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
            self.auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
            self.from_number = st.secrets.get("TWILIO_PHONE_NUMBER", "")
            
            # Client nur initialisieren wenn credentials vorhanden
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
        """
        Formatiert Telefonnummern für Twilio (E.164 Format: +49...)
        Unterstützt: 0172..., +49172..., 172...
        """
        if not phone:
            return None
        
        # Entferne alle Leerzeichen und Sonderzeichen außer +
        phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Fall 1: Beginnt mit + → bereits im E.164 Format
        if phone.startswith('+'):
            return phone
        
        # Fall 2: Beginnt mit 0 → deutsche Nummer (0172 → +49172)
        if phone.startswith('0'):
            return '+49' + phone[1:]
        
        # Fall 3: Beginnt mit Ziffer → deutsche Nummer ohne 0 (172 → +49172)
        if phone[0].isdigit():
            return '+49' + phone
        
        # Fallback: Ungültiges Format
        return None
    
    def send(self, to, body):
        """
        Sendet SMS über Twilio
        Returns: (success: bool, error_message: str)
        """
        # Validierung
        if not self.enabled:
            return False, "SMS ist deaktiviert (ENABLE_SMS_REMINDER=false oder fehlende Credentials)"
        
        if not self.client:
            return False, "❌ Twilio Client konnte nicht initialisiert werden (prüfen Sie Account SID und Auth Token)"
        
        if not self.from_number:
            return False, "❌ Keine Twilio-Telefonnummer konfiguriert (TWILIO_PHONE_NUMBER fehlt)"
        
        if not self.from_number.startswith('+'):
            return False, f"❌ Twilio-Nummer muss mit + beginnen (aktuell: {self.from_number})"
        
        # Telefonnummer formatieren
        formatted_to = self.format_phone_number(to)
        if not formatted_to:
            return False, f"❌ Ungültige Telefonnummer: {to}"
        
        try:
            # SMS senden
            message = self.client.messages.create(
                to=formatted_to,
                from_=self.from_number,
                body=body
            )
            
            # Status prüfen
            if message.sid:
                success_msg = f"✅ SMS erfolgreich an {formatted_to} gesendet (SID: {message.sid})"
                return True, success_msg
            else:
                return False, f"❌ SMS-Versand fehlgeschlagen (keine Message SID erhalten)"
                
        except Exception as e:
            error_msg = f"❌ Twilio Fehler: {type(e).__name__}: {str(e)}"
            # Spezielle Twilio-Fehler behandeln
            if "Unable to create record" in str(e):
                error_msg += f"\n\nMögliche Ursachen:\n1. Ziel-Nummer ist ungültig: {formatted_to}\n2. Twilio-Nummer ist nicht SMS-fähig\n3. Land ist für Twilio gesperrt"
            elif "authenticate" in str(e).lower():
                error_msg += "\n\nPrüfen Sie TWILIO_ACCOUNT_SID und TWILIO_AUTH_TOKEN in secrets.toml"
            
            return False, error_msg
# ===== FIRESTORE FUNKTIONEN =====
def load_dienste():
    """Lädt alle Dienste aus Firestore"""
    if not db:
        return []
    try:
        docs = db.collection('dienste').stream()
        dienste = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            dienste.append(d)
        return dienste
    except Exception as e:
        st.error(f"Fehler beim Laden der Dienste: {e}")
        return []

def save_dienst(dienst_data):
    """Speichert oder aktualisiert einen Dienst"""
    if not db:
        return False
    try:
        if 'id' in dienst_data and dienst_data['id']:
            # Update
            doc_id = dienst_data.pop('id')
            db.collection('dienste').document(doc_id).set(dienst_data)
        else:
            # Neu
            dienst_data.pop('id', None)
            db.collection('dienste').add(dienst_data)
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False

def delete_dienst(dienst_id):
    """Löscht einen Dienst"""
    if not db:
        return False
    try:
        db.collection('dienste').document(dienst_id).delete()
        return True
    except Exception as e:
        st.error(f"Fehler beim Löschen: {e}")
        return False

def load_users():
    """Lädt alle Benutzer"""
    if not db:
        return []
    try:
        docs = db.collection('users').stream()
        users = []
        for doc in docs:
            u = doc.to_dict()
            u['id'] = doc.id
            users.append(u)
        return users
    except Exception as e:
        st.error(f"Fehler beim Laden der Benutzer: {e}")
        return []

def save_user(user_data):
    """Speichert oder aktualisiert einen Benutzer"""
    if not db:
        return False
    try:
        if 'id' in user_data and user_data['id']:
            doc_id = user_data.pop('id')
            db.collection('users').document(doc_id).set(user_data)
        else:
            user_data.pop('id', None)
            db.collection('users').add(user_data)
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern des Benutzers: {e}")
        return False

def delete_user(user_id):
    """Löscht einen Benutzer"""
    if not db:
        return False
    try:
        db.collection('users').document(user_id).delete()
        return True
    except Exception as e:
        st.error(f"Fehler beim Löschen des Benutzers: {e}")
        return False

# ===== HILFSFUNKTIONEN =====
def hash_password(password):
    """Erstellt einen Hash eines Passworts"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(username, password):
    """Überprüft Benutzername und Passwort"""
    users = load_users()
    pw_hash = hash_password(password)
    for user in users:
        if user.get('username') == username and user.get('password') == pw_hash:
            return True, user
    return False, None

def format_date(date_obj):
    """Formatiert ein Datum für die Anzeige"""
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
    return date_obj.strftime('%d.%m.%Y')

def get_weekday(date_obj):
    """Gibt den Wochentag auf Deutsch zurück"""
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
    weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    return weekdays[date_obj.weekday()]

# ===== INITIALISIERUNG =====
mailer = Mailer()
sms_client = TwilioSMS()

# Session State initialisieren
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'page' not in st.session_state:
    st.session_state.page = 'calendar'
# ===== LOGIN =====
def login_page():
    """Zeigt die Login-Seite an"""
    st.title("🌊 Wasserwacht Dienstplan+")
    st.markdown(f"**Version:** {VERSION}")
    
    with st.form("login_form"):
        username = st.text_input("Benutzername")
        password = st.text_input("Passwort", type="password")
        submit = st.form_submit_button("Anmelden")
        
        if submit:
            if username and password:
                success, user = check_password(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("❌ Ungültige Anmeldedaten")
            else:
                st.warning("⚠️ Bitte Benutzername und Passwort eingeben")

def logout():
    """Meldet den Benutzer ab"""
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.page = 'calendar'
    st.rerun()

# ===== NAVIGATION =====
def show_navigation():
    """Zeigt die Navigationsleiste"""
    user = st.session_state.user
    is_admin = user.get('role') == 'admin' if user else False
    
    st.sidebar.title(f"👤 {user.get('name', 'Benutzer')}")
    st.sidebar.markdown(f"**Rolle:** {user.get('role', 'user')}")
    st.sidebar.markdown("---")
    
    # Navigation
    pages = {
        'calendar': '📅 Kalender',
        'meine_dienste': '📋 Meine Dienste',
        'statistik': '📊 Statistik'
    }
    
    if is_admin:
        pages.update({
            'verwaltung': '⚙️ Verwaltung',
            'benutzer': '👥 Benutzer',
            'backup': '💾 Backup',
            'debug': '🔧 Debug-Panel'
        })
    
    for key, label in pages.items():
        if st.sidebar.button(label, use_container_width=True):
            st.session_state.page = key
            st.rerun()
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Abmelden", use_container_width=True):
        logout()

# ===== KALENDERANSICHT =====
def calendar_page():
    """Zeigt die Kalenderansicht"""
    st.title("📅 Dienstplan Kalender")
    
    # Monat/Jahr Auswahl
    col1, col2, col3 = st.columns([2, 2, 6])
    with col1:
        selected_month = st.selectbox(
            "Monat",
            range(1, 13),
            index=datetime.now().month - 1,
            format_func=lambda x: cal_module.month_name[x]
        )
    with col2:
        selected_year = st.selectbox(
            "Jahr",
            range(datetime.now().year - 1, datetime.now().year + 3),
            index=1
        )
    
    # Kalender erstellen
    cal = cal_module.monthcalendar(selected_year, selected_month)
    dienste = load_dienste()
    
    # Dienste nach Datum gruppieren
    dienste_by_date = {}
    for dienst in dienste:
        datum = dienst.get('datum')
        if datum:
            if datum not in dienste_by_date:
                dienste_by_date[datum] = []
            dienste_by_date[datum].append(dienst)
    
    # Kalender anzeigen
    st.markdown("### " + cal_module.month_name[selected_month] + " " + str(selected_year))
    
    # Wochentage
    weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    cols = st.columns(7)
    for i, day in enumerate(weekdays):
        cols[i].markdown(f"**{day}**")
    
    # Tage
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
            else:
                date_str = f"{selected_year}-{selected_month:02d}-{day:02d}"
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Dienste für diesen Tag
                dienste_heute = dienste_by_date.get(date_str, [])
                
                with cols[i]:
                    # Tag-Nummer
                    if date_obj == datetime.now().date():
                        st.markdown(f"**🔴 {day}**")
                    else:
                        st.markdown(f"**{day}**")
                    
                    # Dienste anzeigen
                    if dienste_heute:
                        for dienst in dienste_heute:
                            typ = dienst.get('typ', 'Dienst')
                            teilnehmer = dienst.get('teilnehmer', [])
                            st.markdown(f"🔹 {typ} ({len(teilnehmer)})")
                    else:
                        st.markdown("_Kein Dienst_")
# ===== MEINE DIENSTE =====
def meine_dienste_page():
    """Zeigt die persönlichen Dienste des Benutzers"""
    st.title("📋 Meine Dienste")
    
    user = st.session_state.user
    user_id = user.get('id')
    dienste = load_dienste()
    
    # Filtern nach Teilnahme
    meine_dienste = [d for d in dienste if user_id in d.get('teilnehmer', [])]
    
    # Sortieren nach Datum
    meine_dienste.sort(key=lambda x: x.get('datum', ''), reverse=True)
    
    if not meine_dienste:
        st.info("Sie sind aktuell in keinen Diensten eingetragen.")
        return
    
    # Anzeigen
    for dienst in meine_dienste:
        datum = dienst.get('datum')
        typ = dienst.get('typ', 'Dienst')
        zeit = dienst.get('zeit', '')
        ort = dienst.get('ort', '')
        
        with st.expander(f"{format_date(datum)} - {typ}", expanded=False):
            st.markdown(f"**Datum:** {format_date(datum)} ({get_weekday(datum)})")
            st.markdown(f"**Typ:** {typ}")
            if zeit:
                st.markdown(f"**Zeit:** {zeit}")
            if ort:
                st.markdown(f"**Ort:** {ort}")
            
            # Teilnehmer
            teilnehmer_ids = dienst.get('teilnehmer', [])
            users = load_users()
            teilnehmer_namen = [u.get('name') for u in users if u.get('id') in teilnehmer_ids]
            st.markdown(f"**Teilnehmer:** {', '.join(teilnehmer_namen)}")
            
            # Abmelden
            if st.button(f"❌ Abmelden", key=f"abmelden_{dienst.get('id')}"):
                teilnehmer_ids.remove(user_id)
                dienst['teilnehmer'] = teilnehmer_ids
                if save_dienst(dienst):
                    st.success("✅ Erfolgreich abgemeldet")
                    st.rerun()

# ===== STATISTIK =====
def statistik_page():
    """Zeigt Statistiken zu Diensten"""
    st.title("📊 Statistik")
    
    dienste = load_dienste()
    users = load_users()
    
    if not dienste:
        st.info("Noch keine Dienste vorhanden.")
        return
    
    # Anzahl Dienste pro Benutzer
    user_dienste_count = Counter()
    for dienst in dienste:
        for user_id in dienst.get('teilnehmer', []):
            user_dienste_count[user_id] += 1
    
    # Top 10
    st.subheader("🏆 Top 10 Helfer")
    top_users = user_dienste_count.most_common(10)
    
    if top_users:
        df_data = []
        for user_id, count in top_users:
            user = next((u for u in users if u.get('id') == user_id), None)
            if user:
                df_data.append({
                    'Name': user.get('name'),
                    'Anzahl Dienste': count
                })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Chart
        fig = px.bar(df, x='Name', y='Anzahl Dienste', title='Dienste pro Helfer')
        st.plotly_chart(fig, use_container_width=True)
    
    # Dienste pro Monat
    st.subheader("📅 Dienste pro Monat")
    dienste_by_month = Counter()
    for dienst in dienste:
        datum = dienst.get('datum')
        if datum:
            month_key = datum[:7]  # YYYY-MM
            dienste_by_month[month_key] += 1
    
    if dienste_by_month:
        df_month = pd.DataFrame([
            {'Monat': k, 'Anzahl': v} 
            for k, v in sorted(dienste_by_month.items())
        ])
        fig_month = px.line(df_month, x='Monat', y='Anzahl', title='Dienste pro Monat')
        st.plotly_chart(fig_month, use_container_width=True)

# ===== VERWALTUNG (ADMIN) =====
def verwaltung_page():
    """Verwaltungsseite für Admins"""
    st.title("⚙️ Dienstverwaltung")
    
    # Tabs
    tab1, tab2 = st.tabs(["📋 Alle Dienste", "➕ Neuer Dienst"])
    
    with tab1:
        dienste = load_dienste()
        if not dienste:
            st.info("Noch keine Dienste vorhanden.")
        else:
            for dienst in sorted(dienste, key=lambda x: x.get('datum', ''), reverse=True):
                datum = dienst.get('datum')
                typ = dienst.get('typ', 'Dienst')
                
                with st.expander(f"{format_date(datum)} - {typ}"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**Datum:** {format_date(datum)}")
                        st.markdown(f"**Typ:** {typ}")
                        st.markdown(f"**Zeit:** {dienst.get('zeit', 'N/A')}")
                        st.markdown(f"**Ort:** {dienst.get('ort', 'N/A')}")
                        
                        # Teilnehmer
                        teilnehmer_ids = dienst.get('teilnehmer', [])
                        users = load_users()
                        teilnehmer_namen = [u.get('name') for u in users if u.get('id') in teilnehmer_ids]
                        st.markdown(f"**Teilnehmer ({len(teilnehmer_namen)}):** {', '.join(teilnehmer_namen)}")
                    
                    with col2:
                        if st.button("🗑️ Löschen", key=f"del_{dienst.get('id')}"):
                            if delete_dienst(dienst.get('id')):
                                st.success("✅ Gelöscht")
                                st.rerun()
    
    with tab2:
        with st.form("neuer_dienst"):
            datum = st.date_input("Datum")
            typ = st.selectbox("Typ", ["Wachdienst", "Ausbildung", "Einsatz", "Sonstiges"])
            zeit = st.time_input("Uhrzeit")
            ort = st.text_input("Ort")
            beschreibung = st.text_area("Beschreibung")
            
            # Teilnehmer auswählen
            users = load_users()
            user_options = {u.get('name'): u.get('id') for u in users}
            selected_users = st.multiselect("Teilnehmer", options=list(user_options.keys()))
            
            submit = st.form_submit_button("💾 Speichern")
            
            if submit:
                dienst_data = {
                    'id': None,
                    'datum': datum.strftime('%Y-%m-%d'),
                    'typ': typ,
                    'zeit': zeit.strftime('%H:%M'),
                    'ort': ort,
                    'beschreibung': beschreibung,
                    'teilnehmer': [user_options[name] for name in selected_users],
                    'erstellt_am': datetime.now(TZ).isoformat()
                }
                
                if save_dienst(dienst_data):
                    st.success("✅ Dienst erstellt")
                    st.rerun()
# ===== BENUTZER-VERWALTUNG (ADMIN) =====
def benutzer_page():
    """Benutzerverwaltung für Admins"""
    st.title("👥 Benutzerverwaltung")
    
    tab1, tab2 = st.tabs(["📋 Alle Benutzer", "➕ Neuer Benutzer"])
    
    with tab1:
        users = load_users()
        if not users:
            st.info("Noch keine Benutzer vorhanden.")
        else:
            for user in users:
                with st.expander(f"{user.get('name')} ({user.get('username')})"):
                    st.markdown(f"**Name:** {user.get('name')}")
                    st.markdown(f"**Username:** {user.get('username')}")
                    st.markdown(f"**Rolle:** {user.get('role')}")
                    st.markdown(f"**E-Mail:** {user.get('email', 'N/A')}")
                    st.markdown(f"**Telefon:** {user.get('phone', 'N/A')}")
                    
                    if st.button("🗑️ Löschen", key=f"del_user_{user.get('id')}"):
                        if delete_user(user.get('id')):
                            st.success("✅ Benutzer gelöscht")
                            st.rerun()
    
    with tab2:
        with st.form("neuer_benutzer"):
            name = st.text_input("Name")
            username = st.text_input("Benutzername")
            password = st.text_input("Passwort", type="password")
            email = st.text_input("E-Mail")
            phone = st.text_input("Telefon")
            role = st.selectbox("Rolle", ["user", "admin"])
            
            submit = st.form_submit_button("💾 Speichern")
            
            if submit:
                if name and username and password:
                    user_data = {
                        'id': None,
                        'name': name,
                        'username': username,
                        'password': hash_password(password),
                        'email': email,
                        'phone': phone,
                        'role': role,
                        'erstellt_am': datetime.now(TZ).isoformat()
                    }
                    
                    if save_user(user_data):
                        st.success("✅ Benutzer erstellt")
                        st.rerun()
                else:
                    st.error("❌ Bitte alle Pflichtfelder ausfüllen")

# ===== BACKUP (ADMIN) =====
def backup_page():
    """Backup-Funktionen"""
    st.title("💾 Backup & Export")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Export")
        if st.button("📄 Dienste exportieren (JSON)"):
            dienste = load_dienste()
            json_str = json.dumps(dienste, indent=2, ensure_ascii=False)
            st.download_button(
                "⬇️ Download",
                json_str,
                file_name=f"dienste_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
        
        if st.button("📄 Benutzer exportieren (JSON)"):
            users = load_users()
            # Passwörter entfernen für Sicherheit
            users_export = [{k:v for k,v in u.items() if k != 'password'} for u in users]
            json_str = json.dumps(users_export, indent=2, ensure_ascii=False)
            st.download_button(
                "⬇️ Download",
                json_str,
                file_name=f"benutzer_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
    with col2:
        st.subheader("📧 E-Mail Backup")
        if st.button("📧 Backup per E-Mail senden"):
            if mailer.admin_receiver:
                dienste = load_dienste()
                users = load_users()
                
                # Erstelle ZIP
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Dienste
                    dienste_json = json.dumps(dienste, indent=2, ensure_ascii=False)
                    zip_file.writestr('dienste.json', dienste_json)
                    
                    # Benutzer (ohne Passwörter)
                    users_export = [{k:v for k,v in u.items() if k != 'password'} for u in users]
                    users_json = json.dumps(users_export, indent=2, ensure_ascii=False)
                    zip_file.writestr('benutzer.json', users_json)
                
                zip_buffer.seek(0)
                
                # E-Mail senden
                subject = f"Dienstplan Backup - {datetime.now().strftime('%d.%m.%Y')}"
                body = f"<html><body><h2>Automatisches Backup</h2><p>Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p></body></html>"
                
                success, message = mailer.send(
                    mailer.admin_receiver,
                    subject,
                    body,
                    attachments=[(f"backup_{datetime.now().strftime('%Y%m%d')}.zip", zip_buffer.getvalue())]
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("❌ Keine Admin-E-Mail konfiguriert")

# ===== DEBUG-PANEL (ADMIN) =====
def debug_page():
    """Debug-Panel für Admins"""
    st.title("🔧 Debug-Panel")
    
    st.markdown("### 📧 E-Mail Test")
    with st.form("email_test"):
        test_email = st.text_input("Test E-Mail Adresse")
        test_subject = st.text_input("Betreff", value="Test E-Mail")
        test_body = st.text_area("Nachricht", value="Dies ist eine Test-E-Mail vom Dienstplan.")
        
        if st.form_submit_button("📧 Test-E-Mail senden"):
            if test_email:
                success, message = mailer.send(test_email, test_subject, test_body)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("Bitte E-Mail-Adresse eingeben")
    
    st.markdown("---")
    st.markdown("### 📱 SMS Test")
    with st.form("sms_test"):
        test_phone = st.text_input("Test Telefonnummer", placeholder="0172...")
        test_sms_body = st.text_area("SMS Text", value="Test SMS vom Dienstplan")
        
        if st.form_submit_button("📱 Test-SMS senden"):
            if test_phone:
                success, message = sms_client.send(test_phone, test_sms_body)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("Bitte Telefonnummer eingeben")
    
    st.markdown("---")
    st.markdown("### ⚙️ System-Info")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**SMTP Konfiguration:**")
        st.code(f"""
Server: {mailer.server}
Port: {mailer.port}
User: {mailer.user[:10]}... (gesetzt: {bool(mailer.user)})
Password: {'***' if mailer.pw else 'NICHT GESETZT'}
Admin: {mailer.admin_receiver}
        """)
    
    with col2:
        st.markdown("**Twilio Konfiguration:**")
        st.code(f"""
Enabled: {sms_client.enabled}
Account SID: {sms_client.account_sid[:10]}... (gesetzt: {bool(sms_client.account_sid)})
Auth Token: {'***' if sms_client.auth_token else 'NICHT GESETZT'}
From Number: {sms_client.from_number}
Client: {'Initialisiert' if sms_client.client else 'FEHLER'}
        """)
    
    st.markdown("**Firestore:**")
    st.code(f"Verbindung: {'✅ OK' if db else '❌ FEHLER'}")

# ===== MAIN =====
def main():
    """Hauptfunktion der App"""
    if not st.session_state.logged_in:
        login_page()
    else:
        show_navigation()
        
        # Seiten-Router
        page = st.session_state.page
        
        if page == 'calendar':
            calendar_page()
        elif page == 'meine_dienste':
            meine_dienste_page()
        elif page == 'statistik':
            statistik_page()
        elif page == 'verwaltung':
            if st.session_state.user.get('role') == 'admin':
                verwaltung_page()
            else:
                st.error("❌ Keine Berechtigung")
        elif page == 'benutzer':
            if st.session_state.user.get('role') == 'admin':
                benutzer_page()
            else:
                st.error("❌ Keine Berechtigung")
        elif page == 'backup':
            if st.session_state.user.get('role') == 'admin':
                backup_page()
            else:
                st.error("❌ Keine Berechtigung")
        elif page == 'debug':
            if st.session_state.user.get('role') == 'admin':
                debug_page()
            else:
                st.error("❌ Keine Berechtigung")

if __name__ == "__main__":
    main()
