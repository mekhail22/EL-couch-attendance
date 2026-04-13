# -*- coding: utf-8 -*-
"""
تطبيق إدارة الحضور والاشتراكات لأكاديمية كرة قدم "الكوتش أكاديمي"
باستخدام Streamlit و Google Sheets
- دمج الاشتراكات والمدفوعات في نموذج واحد
- رسوم الاشتراك الافتراضية 1500 جنيه
- عرض شعار الأكاديمية من ملف logo.jpg
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import re
import time
import json
import base64
import os
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image

# ==================== إعدادات الصفحة ====================
st.set_page_config(
    page_title="الكوتش أكاديمي - إدارة الحضور والاشتراكات",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== تحميل الشعار ====================
def get_logo_base64():
    """تحويل صورة الشعار إلى base64 لعرضها في HTML إذا كانت موجودة"""
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

def display_logo():
    """عرض الشعار في الشريط الجانبي أو في الواجهة"""
    logo_base64 = get_logo_base64()
    if logo_base64:
        st.sidebar.markdown(
            f"""
            <div style="text-align: center; padding: 10px;">
                <img src="data:image/jpeg;base64,{logo_base64}" width="150" style="border-radius: 50%; border: 3px solid #2e7d32;">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.markdown(
            """
            <div style="text-align: center; padding: 10px;">
                <h1>⚽</h1>
            </div>
            """,
            unsafe_allow_html=True
        )

# ==================== أنماط CSS مخصصة ====================
def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
    }
    
    .main-header {
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #e0e0e0;
    }
    
    .metric-card {
        background: linear-gradient(145deg, #f5f5f5 0%, #ffffff 100%);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 4px solid #2e7d32;
    }
    
    .stButton button {
        background-color: #2e7d32;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        border: none;
        transition: all 0.3s;
    }
    
    .stButton button:hover {
        background-color: #1b5e20;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    .logout-btn {
        background-color: #d32f2f !important;
    }
    
    .logout-btn:hover {
        background-color: #b71c1c !important;
    }
    
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e0e0e0;
    }
    
    .success-message {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 1rem;
        border-radius: 8px;
        border-right: 4px solid #2e7d32;
    }
    
    .error-message {
        background-color: #ffebee;
        color: #c62828;
        padding: 1rem;
        border-radius: 8px;
        border-right: 4px solid #c62828;
    }
    </style>
    """, unsafe_allow_html=True)

# ==================== إدارة الجلسات ====================
class SessionManager:
    @staticmethod
    def init_session():
        defaults = {
            "logged_in": False,
            "username": None,
            "role": None,
            "show_register": False,
            "current_page": "login",
            "last_activity": time.time()
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def login(username: str, role: str):
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.role = role
        st.session_state.last_activity = time.time()
    
    @staticmethod
    def logout():
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        SessionManager.init_session()
    
    @staticmethod
    def check_auth():
        if not st.session_state.logged_in:
            st.warning("الرجاء تسجيل الدخول أولاً")
            st.stop()
        if time.time() - st.session_state.last_activity > 7200:
            SessionManager.logout()
            st.warning("انتهت الجلسة، الرجاء تسجيل الدخول مرة أخرى")
            st.stop()
        st.session_state.last_activity = time.time()

# ==================== الاتصال بقاعدة البيانات (Google Sheets) ====================
class GoogleSheetsDB:
    def __init__(self):
        self.spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
        self._client = None
        self._spreadsheet = None
        self._init_connection()
        self._initialize_default_coach()
    
    def _init_connection(self):
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            service_account_info = st.secrets["google"]["service_account"]
            
            if hasattr(service_account_info, 'to_dict'):
                service_account_info = service_account_info.to_dict()
            elif not isinstance(service_account_info, dict):
                service_account_info = json.loads(service_account_info)
            
            if 'private_key' in service_account_info:
                private_key = service_account_info['private_key']
                private_key = private_key.replace('\\n', '\n')
                if '-----BEGIN PRIVATE KEY-----' not in private_key:
                    private_key = '-----BEGIN PRIVATE KEY-----\n' + private_key + '\n-----END PRIVATE KEY-----'
                service_account_info['private_key'] = private_key
            
            creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            self._client = gspread.authorize(creds)
            self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
        except Exception as e:
            st.error(f"❌ فشل الاتصال بـ Google Sheets: {str(e)}")
            st.stop()
    
    def _initialize_default_coach(self):
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        coach_exists = any(user.get("role") == "coach" for user in users)
        if not coach_exists:
            default_username = "أحمد محمد علي"
            default_password = "coach123"
            ws.append_row([default_username, default_password, "coach", str(date.today())])
    
    def get_or_create_worksheet(self, title: str, headers: List[str]) -> gspread.Worksheet:
        try:
            ws = self._spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            ws = self._spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
            ws.append_row(headers)
        return ws
    
    # ========== المستخدمين ==========
    def get_users_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Users", ["username", "password", "role", "created_at"])
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        for user in users:
            if user["username"] == username and user["password"] == password:
                return user
        return None
    
    def user_exists(self, username: str) -> bool:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        return any(u["username"] == username for u in users)
    
    def add_user(self, username: str, password: str, role: str) -> Tuple[bool, str]:
        if not self._validate_three_part_name(username):
            return False, "❌ يجب أن يكون الاسم ثلاثياً على الأقل (مثال: أحمد محمد علي)"
        if self.user_exists(username):
            return False, "❌ اسم المستخدم موجود مسبقاً"
        if len(password) < 4:
            return False, "❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل"
        ws = self.get_users_sheet()
        ws.append_row([username, password, role, str(date.today())])
        return True, "✅ تم إنشاء الحساب بنجاح"
    
    def get_all_players(self) -> List[str]:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        return [u["username"] for u in users if u["role"] == "player"]
    
    def update_user_password(self, username: str, new_password: str) -> bool:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        for i, user in enumerate(users, start=2):
            if user["username"] == username:
                ws.update(f'B{i}', new_password)
                return True
        return False
    
    # ========== الحضور ==========
    def get_attendance_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Attendance", 
            ["player_name", "date", "status", "recorded_by", "recorded_at"])
    
    def record_attendance(self, date_str: str, present_players: List[str], coach_name: str) -> bool:
        ws = self.get_attendance_sheet()
        all_players = self.get_all_players()
        records = ws.get_all_records()
        rows_to_delete = [i for i, r in enumerate(records, start=2) if r["date"] == date_str]
        for row in sorted(rows_to_delete, reverse=True):
            ws.delete_rows(row)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for player in all_players:
            status = "Present" if player in present_players else "Absent"
            ws.append_row([player, date_str, status, coach_name, timestamp])
        return True
    
    def get_attendance_for_player(self, player_name: str) -> pd.DataFrame:
        ws = self.get_attendance_sheet()
        data = ws.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if not df.empty:
            return df[df["player_name"] == player_name].sort_values("date", ascending=False)
        return df
    
    def get_attendance_summary(self) -> pd.DataFrame:
        ws = self.get_attendance_sheet()
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        summary = df.groupby(["player_name", "status"]).size().unstack(fill_value=0)
        summary["Total"] = summary.sum(axis=1)
        if "Present" in summary.columns:
            summary["Attendance %"] = (summary["Present"] / summary["Total"] * 100).round(1)
        else:
            summary["Attendance %"] = 0
        return summary.reset_index()
    
    # ========== الاشتراكات والمدفوعات (موحد) ==========
    def get_memberships_sheet(self) -> gspread.Worksheet:
        """ورقة موحدة للاشتراكات والمدفوعات"""
        return self.get_or_create_worksheet("Memberships",
            ["player_name", "monthly_fee", "start_date", "end_date", 
             "notes", "amount_paid", "payment_method", "payment_date",
             "recorded_by", "recorded_at"])
    
    def add_membership(self, player_name: str, monthly_fee: float,
                      start_date: str, end_date: str, notes: str,
                      amount_paid: float, payment_method: str,
                      payment_date: str, recorded_by: str) -> bool:
        ws = self.get_memberships_sheet()
        ws.append_row([
            player_name, monthly_fee, start_date, end_date,
            notes, amount_paid, payment_method, payment_date,
            recorded_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
        return True
    
    def get_player_memberships(self, player_name: str) -> pd.DataFrame:
        ws = self.get_memberships_sheet()
        data = ws.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if not df.empty:
            return df[df["player_name"] == player_name].sort_values("start_date", ascending=False)
        return df
    
    def get_all_memberships(self) -> pd.DataFrame:
        ws = self.get_memberships_sheet()
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_active_membership(self, player_name: str) -> Optional[Dict]:
        df = self.get_player_memberships(player_name)
        if not df.empty:
            today = date.today().isoformat()
            for _, row in df.iterrows():
                if row.get("end_date", "") >= today:
                    return row.to_dict()
        return None
    
    def update_membership(self, row_index: int, updates: Dict) -> bool:
        ws = self.get_memberships_sheet()
        sheet_row = row_index + 2
        headers = ws.row_values(1)
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                ws.update_cell(sheet_row, col_idx, value)
        return True
    
    def delete_membership(self, row_index: int) -> bool:
        ws = self.get_memberships_sheet()
        ws.delete_rows(row_index + 2)
        return True
    
    @staticmethod
    def _validate_three_part_name(name: str) -> bool:
        if not name or not isinstance(name, str):
            return False
        parts = name.strip().split()
        return len(parts) >= 3
    
    @staticmethod
    def validate_three_part_name(name: str) -> Tuple[bool, str]:
        if not name or not isinstance(name, str):
            return False, "الاسم غير صالح"
        parts = name.strip().split()
        if len(parts) < 3:
            return False, "يجب أن يتكون الاسم من ثلاثة أجزاء على الأقل (مثال: أحمد محمد علي)"
        if any(len(part) < 2 for part in parts):
            return False, "يجب أن يتكون كل جزء من الاسم من حرفين على الأقل"
        if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', name):
            return False, "يجب أن يحتوي الاسم على أحرف عربية أو إنجليزية فقط"
        return True, ""

# ==================== واجهات المستخدم ====================

def show_header():
    """عرض رأس الصفحة مع الشعار"""
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        logo_path = "logo.jpg"
        if os.path.exists(logo_path):
            st.image(logo_path, width=150)
        st.markdown("""
        <div style="text-align: center;">
            <h1 style="color: #2e7d32;">⚽ الكوتش أكاديمي</h1>
            <h3>نظام إدارة الحضور والاشتراكات</h3>
        </div>
        """, unsafe_allow_html=True)

def login_page():
    show_header()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center;'>🔐 تسجيل الدخول</h3>", unsafe_allow_html=True)
            username = st.text_input("👤 الاسم الثلاثي (اسم المستخدم)", placeholder="أحمد محمد علي")
            password = st.text_input("🔒 كلمة المرور", type="password")
            col_a, col_b = st.columns(2)
            with col_a:
                login_btn = st.button("🚪 دخول", type="primary", use_container_width=True)
            with col_b:
                register_btn = st.button("📝 إنشاء حساب جديد", use_container_width=True)
            if login_btn:
                if not username or not password:
                    st.error("الرجاء إدخال اسم المستخدم وكلمة المرور")
                else:
                    db = GoogleSheetsDB()
                    user = db.authenticate_user(username, password)
                    if user:
                        SessionManager.login(username, user["role"])
                        st.success("تم تسجيل الدخول بنجاح! جاري التحويل...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
            if register_btn:
                st.session_state.show_register = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("ℹ️ معلومات هامة"):
            st.markdown("""
            - يجب أن يكون اسم المستخدم **ثلاثياً** (مثال: أحمد محمد علي)
            - كلمة المرور يجب أن تكون 4 أحرف على الأقل
            - حساب الكابتن الافتراضي: **أحمد محمد علي** / **coach123**
            """)

def register_page():
    show_header()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center;'>📝 إنشاء حساب لاعب جديد</h3>", unsafe_allow_html=True)
            new_username = st.text_input("👤 الاسم الثلاثي (مطلوب)", placeholder="أحمد محمد علي")
            new_password = st.text_input("🔒 كلمة المرور", type="password")
            confirm_password = st.text_input("🔒 تأكيد كلمة المرور", type="password")
            if st.button("✅ تسجيل", type="primary", use_container_width=True):
                db = GoogleSheetsDB()
                valid, msg = db.validate_three_part_name(new_username)
                if not valid:
                    st.error(msg)
                elif new_password != confirm_password:
                    st.error("❌ كلمة المرور غير متطابقة")
                elif len(new_password) < 4:
                    st.error("❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل")
                else:
                    success, msg = db.add_user(new_username, new_password, "player")
                    if success:
                        st.success(msg)
                        st.info("يمكنك الآن تسجيل الدخول باستخدام بياناتك")
                        st.session_state.show_register = False
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(msg)
            if st.button("🔙 العودة لتسجيل الدخول", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

def coach_sidebar():
    with st.sidebar:
        display_logo()
        st.markdown(f"<h3>👋 مرحباً كابتن<br>{st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {
            "📋 تسجيل الحضور": "attendance",
            "💰 الاشتراكات والمدفوعات": "memberships",
            "📊 الإحصائيات والتقارير": "statistics",
            "👥 إدارة اللاعبين": "players",
            "⚙️ الإعدادات": "settings"
        }
        selected = st.radio("القائمة الرئيسية", list(menu.keys()))
        current_page = menu[selected]
        st.markdown("---")
        db = GoogleSheetsDB()
        st.metric("👥 عدد اللاعبين", len(db.get_all_players()))
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        return current_page

def player_sidebar():
    with st.sidebar:
        display_logo()
        st.markdown(f"<h3>👋 مرحباً<br>{st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {
            "📊 لوحة المعلومات": "dashboard",
            "📅 سجل الحضور": "attendance_history",
            "💰 اشتراكاتي ومدفوعاتي": "financial",
            "⚙️ إعدادات الحساب": "settings"
        }
        selected = st.radio("القائمة", list(menu.keys()))
        current_page = menu[selected]
        st.markdown("---")
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        return current_page

# ==================== صفحات الكابتن (التفاصيل الكاملة) ====================
def coach_attendance_page():
    st.header("📋 تسجيل حضور وغياب اللاعبين")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون بعد")
        return
    col1, col2 = st.columns([1, 2])
    with col1:
        att_date = st.date_input("📅 تاريخ الحضور", value=date.today())
    ws_att = db.get_attendance_sheet()
    records = ws_att.get_all_records()
    today_present = [r["player_name"] for r in records if r["date"] == str(att_date) and r["status"] == "Present"]
    st.subheader(f"تسجيل حضور يوم {att_date}")
    selected_present = st.multiselect("✅ اختر اللاعبين الحاضرين", players, default=today_present)
    absent_players = [p for p in players if p not in selected_present]
    col1, col2, col3 = st.columns(3)
    col1.metric("👥 إجمالي اللاعبين", len(players))
    col2.metric("✅ الحاضرين", len(selected_present))
    col3.metric("❌ الغائبين", len(absent_players))
    if absent_players:
        with st.expander(f"📋 قائمة الغائبين ({len(absent_players)})"):
            for p in absent_players:
                st.write(f"- {p}")
    if st.button("💾 حفظ تسجيل الحضور", type="primary", use_container_width=True):
        with st.spinner("جاري حفظ البيانات..."):
            db.record_attendance(str(att_date), selected_present, st.session_state.username)
            st.success(f"✅ تم تسجيل الحضور لعدد {len(players)} لاعب بنجاح")
            st.balloons()
            time.sleep(1)
            st.rerun()
    st.markdown("---")
    st.subheader("📜 سجل الحضور السابق")
    att_data = ws_att.get_all_records()
    if att_data:
        df = pd.DataFrame(att_data).sort_values("date", ascending=False)
        unique_dates = sorted(df["date"].unique(), reverse=True)
        selected_date_view = st.selectbox("اختر تاريخ للعرض", unique_dates)
        filtered_df = df[df["date"] == selected_date_view]
        st.dataframe(filtered_df[["player_name", "status", "recorded_by", "recorded_at"]], use_container_width=True)

def coach_memberships_page():
    st.header("💰 إدارة الاشتراكات والمدفوعات")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون بعد")
        return
    tab1, tab2 = st.tabs(["➕ إضافة اشتراك / دفعة جديدة", "📋 سجل الاشتراكات والمدفوعات"])
    with tab1:
        st.subheader("تسجيل اشتراك مع دفعة")
        with st.form("new_membership_form"):
            col1, col2 = st.columns(2)
            with col1:
                player = st.selectbox("👤 اللاعب", players)
                monthly_fee = st.number_input("💵 رسوم الاشتراك الشهرية (جنيه)", 
                                            min_value=0.0, step=50.0, value=1500.0)
                start_date = st.date_input("📅 تاريخ بداية الاشتراك", value=date.today())
                end_date = st.date_input("📅 تاريخ نهاية الاشتراك", 
                                       value=date.today() + timedelta(days=30))
                notes = st.text_area("📝 ملاحظات إضافية", placeholder="أي ملاحظات")
            with col2:
                amount_paid = st.number_input("💵 المبلغ المدفوع", min_value=0.0, step=50.0)
                payment_method = st.selectbox("💳 طريقة الدفع", 
                                            ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
                payment_date = st.date_input("📅 تاريخ الدفع", value=date.today())
            if st.form_submit_button("💾 حفظ", type="primary"):
                if monthly_fee <= 0:
                    st.error("يجب أن تكون رسوم الاشتراك أكبر من صفر")
                elif end_date <= start_date:
                    st.error("تاريخ النهاية يجب أن يكون بعد تاريخ البداية")
                else:
                    db.add_membership(player, monthly_fee, str(start_date), str(end_date),
                                    notes, amount_paid, payment_method, str(payment_date),
                                    st.session_state.username)
                    st.success("✅ تم حفظ بيانات الاشتراك والدفع بنجاح")
                    time.sleep(1)
                    st.rerun()
    with tab2:
        st.subheader("سجل الاشتراكات والمدفوعات")
        df = db.get_all_memberships()
        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                filter_player = st.selectbox("تصفية حسب اللاعب", ["الكل"] + players)
            with col2:
                methods = ["الكل"] + df["payment_method"].unique().tolist()
                filter_method = st.selectbox("طريقة الدفع", methods)
            filtered_df = df.copy()
            if filter_player != "الكل":
                filtered_df = filtered_df[filtered_df["player_name"] == filter_player]
            if filter_method != "الكل":
                filtered_df = filtered_df[filtered_df["payment_method"] == filter_method]
            total_fees = filtered_df["monthly_fee"].sum()
            total_paid = filtered_df["amount_paid"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 عدد السجلات", len(filtered_df))
            col2.metric("💰 إجمالي رسوم الاشتراكات", f"{total_fees:,.0f} ج.م")
            col3.metric("💵 إجمالي المدفوعات", f"{total_paid:,.0f} ج.م")
            st.dataframe(filtered_df.sort_values("start_date", ascending=False), use_container_width=True)
            if not filtered_df.empty:
                st.markdown("---")
                st.subheader("✏️ تعديل أو حذف سجل")
                idx = st.selectbox("اختر السجل", filtered_df.index,
                                 format_func=lambda x: f"{filtered_df.loc[x, 'player_name']} - {filtered_df.loc[x, 'start_date']}")
                if idx is not None:
                    row = filtered_df.loc[idx]
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ حذف السجل"):
                            db.delete_membership(idx)
                            st.success("تم الحذف")
                            time.sleep(1)
                            st.rerun()
                    with col2:
                        with st.expander("تعديل البيانات"):
                            with st.form("edit_membership"):
                                new_fee = st.number_input("رسوم الاشتراك", value=float(row["monthly_fee"]))
                                new_end = st.date_input("تاريخ النهاية", value=pd.to_datetime(row["end_date"]).date())
                                new_notes = st.text_area("ملاحظات", value=row.get("notes", ""))
                                new_paid = st.number_input("المبلغ المدفوع", value=float(row.get("amount_paid", 0)))
                                new_method = st.selectbox("طريقة الدفع",
                                                        ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"],
                                                        index=["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"].index(row.get("payment_method", "Cash")))
                                if st.form_submit_button("تحديث"):
                                    updates = {
                                        "monthly_fee": new_fee,
                                        "end_date": str(new_end),
                                        "notes": new_notes,
                                        "amount_paid": new_paid,
                                        "payment_method": new_method
                                    }
                                    db.update_membership(idx, updates)
                                    st.success("تم التحديث")
                                    time.sleep(1)
                                    st.rerun()
        else:
            st.info("لا توجد سجلات بعد")

def coach_statistics_page():
    st.header("📊 الإحصائيات والتقارير")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون بعد")
        return
    tab1, tab2 = st.tabs(["📈 إحصائيات الحضور", "💰 التحليل المالي"])
    with tab1:
        st.subheader("إحصائيات الحضور والغياب")
        summary_df = db.get_attendance_summary()
        if not summary_df.empty:
            summary_df = summary_df.sort_values("Attendance %", ascending=False)
            st.dataframe(summary_df, use_container_width=True)
            fig = px.bar(summary_df, x="player_name", y="Attendance %", title="نسبة حضور اللاعبين",
                        color="Attendance %", color_continuous_scale="RdYlGn")
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
            avg_att = summary_df["Attendance %"].mean()
            best = summary_df.iloc[0]["player_name"] if not summary_df.empty else "-"
            worst = summary_df.iloc[-1]["player_name"] if not summary_df.empty else "-"
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 متوسط نسبة الحضور", f"{avg_att:.1f}%")
            col2.metric("🏆 الأعلى حضوراً", best)
            col3.metric("⚠️ الأقل حضوراً", worst)
        else:
            st.info("لا توجد بيانات حضور بعد")
    with tab2:
        st.subheader("التحليل المالي")
        df = db.get_all_memberships()
        if not df.empty:
            df["payment_month"] = pd.to_datetime(df["payment_date"]).dt.to_period("M").astype(str)
            monthly_payments = df.groupby("payment_month")["amount_paid"].sum().reset_index()
            total_paid = df["amount_paid"].sum()
            total_fees = df["monthly_fee"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 إجمالي رسوم الاشتراكات", f"{total_fees:,.0f} ج.م")
            col2.metric("💵 إجمالي المدفوعات", f"{total_paid:,.0f} ج.م")
            col3.metric("📊 نسبة التحصيل", f"{(total_paid/total_fees*100):.1f}%" if total_fees else "0%")
            fig = px.bar(monthly_payments, x="payment_month", y="amount_paid", title="المدفوعات الشهرية")
            st.plotly_chart(fig, use_container_width=True)
            method_counts = df["payment_method"].value_counts()
            fig2 = px.pie(values=method_counts.values, names=method_counts.index, title="توزيع طرق الدفع")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("لا توجد بيانات مالية")

def coach_players_page():
    st.header("👥 إدارة اللاعبين")
    db = GoogleSheetsDB()
    ws_users = db.get_users_sheet()
    users_data = ws_users.get_all_records()
    if users_data:
        df = pd.DataFrame(users_data)
        players_df = df[df["role"] == "player"]
        if not players_df.empty:
            st.subheader("قائمة اللاعبين المسجلين")
            st.dataframe(players_df[["username", "created_at"]], use_container_width=True)
            st.markdown("---")
            st.subheader("🔐 إعادة تعيين كلمة مرور لاعب")
            selected_player = st.selectbox("اختر اللاعب", players_df["username"].tolist())
            new_password = st.text_input("كلمة المرور الجديدة", type="password")
            if st.button("تحديث كلمة المرور"):
                if len(new_password) < 4:
                    st.error("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
                else:
                    if db.update_user_password(selected_player, new_password):
                        st.success(f"تم تحديث كلمة مرور اللاعب {selected_player} بنجاح")
                    else:
                        st.error("فشل تحديث كلمة المرور")
        else:
            st.info("لا يوجد لاعبون مسجلون بعد")

def coach_settings_page():
    st.header("⚙️ الإعدادات")
    st.subheader("تغيير كلمة المرور")
    with st.form("change_password_form"):
        curr = st.text_input("كلمة المرور الحالية", type="password")
        new = st.text_input("كلمة المرور الجديدة", type="password")
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        if st.form_submit_button("تحديث كلمة المرور"):
            if new != confirm:
                st.error("كلمة المرور الجديدة غير متطابقة")
            elif len(new) < 4:
                st.error("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            else:
                db = GoogleSheetsDB()
                user = db.authenticate_user(st.session_state.username, curr)
                if user:
                    if db.update_user_password(st.session_state.username, new):
                        st.success("تم تحديث كلمة المرور بنجاح")
                    else:
                        st.error("فشل تحديث كلمة المرور")
                else:
                    st.error("كلمة المرور الحالية غير صحيحة")

# ==================== صفحات اللاعب ====================
def player_dashboard_page():
    st.header("📊 لوحة المعلومات")
    db = GoogleSheetsDB()
    player = st.session_state.username
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📅 ملخص الحضور")
        att_df = db.get_attendance_for_player(player)
        if not att_df.empty:
            total = len(att_df)
            present = len(att_df[att_df["status"] == "Present"])
            rate = (present / total * 100) if total else 0
            st.metric("نسبة الحضور", f"{rate:.1f}%")
            fig = go.Figure(data=[go.Pie(labels=["حاضر", "غائب"], values=[present, total-present],
                                        hole=.3, marker_colors=["#2e7d32", "#d32f2f"])])
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور بعد")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("💰 ملخص الاشتراك والمدفوعات")
        mem_df = db.get_player_memberships(player)
        if not mem_df.empty:
            active = db.get_active_membership(player)
            if active:
                st.write(f"**الرسوم الشهرية:** {active['monthly_fee']} ج.م")
                st.write(f"**ينتهي في:** {active['end_date']}")
            total_paid = mem_df["amount_paid"].sum()
            total_fees = mem_df["monthly_fee"].sum()
            st.metric("إجمالي المدفوع", f"{total_paid:,.0f} ج.م")
            st.metric("إجمالي المستحق", f"{total_fees:,.0f} ج.م")
            st.metric("المتبقي", f"{total_fees - total_paid:,.0f} ج.م", delta_color="inverse")
        else:
            st.info("لا توجد بيانات مالية")
        st.markdown("</div>", unsafe_allow_html=True)

def player_attendance_history_page():
    st.header("📅 سجل الحضور والغياب")
    db = GoogleSheetsDB()
    att_df = db.get_attendance_for_player(st.session_state.username)
    if not att_df.empty:
        st.dataframe(att_df[["date", "status", "recorded_at"]].sort_values("date", ascending=False),
                    use_container_width=True)
    else:
        st.info("لا توجد بيانات حضور")

def player_financial_page():
    st.header("💰 اشتراكاتي ومدفوعاتي")
    db = GoogleSheetsDB()
    df = db.get_player_memberships(st.session_state.username)
    if not df.empty:
        st.dataframe(df.sort_values("start_date", ascending=False), use_container_width=True)
        total_paid = df["amount_paid"].sum()
        total_fees = df["monthly_fee"].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي المستحق", f"{total_fees:,.0f} ج.م")
        col2.metric("إجمالي المدفوع", f"{total_paid:,.0f} ج.م")
        col3.metric("المتبقي", f"{total_fees - total_paid:,.0f} ج.م")
    else:
        st.info("لا توجد سجلات")

def player_settings_page():
    st.header("⚙️ إعدادات الحساب")
    with st.form("player_change_password"):
        curr = st.text_input("كلمة المرور الحالية", type="password")
        new = st.text_input("كلمة المرور الجديدة", type="password")
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        if st.form_submit_button("تحديث كلمة المرور"):
            if new != confirm:
                st.error("كلمة المرور الجديدة غير متطابقة")
            elif len(new) < 4:
                st.error("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            else:
                db = GoogleSheetsDB()
                user = db.authenticate_user(st.session_state.username, curr)
                if user:
                    if db.update_user_password(st.session_state.username, new):
                        st.success("تم تحديث كلمة المرور بنجاح")
                    else:
                        st.error("فشل التحديث")
                else:
                    st.error("كلمة المرور الحالية غير صحيحة")

# ==================== التطبيق الرئيسي ====================
def main():
    load_css()
    SessionManager.init_session()
    if not st.session_state.logged_in:
        if st.session_state.show_register:
            register_page()
        else:
            login_page()
    else:
        SessionManager.check_auth()
        if st.session_state.role == "coach":
            page = coach_sidebar()
            if page == "attendance":
                coach_attendance_page()
            elif page == "memberships":
                coach_memberships_page()
            elif page == "statistics":
                coach_statistics_page()
            elif page == "players":
                coach_players_page()
            elif page == "settings":
                coach_settings_page()
        else:
            page = player_sidebar()
            if page == "dashboard":
                player_dashboard_page()
            elif page == "attendance_history":
                player_attendance_history_page()
            elif page == "financial":
                player_financial_page()
            elif page == "settings":
                player_settings_page()

if __name__ == "__main__":
    main()
