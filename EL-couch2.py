# -*- coding: utf-8 -*-
"""
تطبيق إدارة الحضور والاشتراكات لأكاديمية كرة قدم "الكوتش أكاديمي"
باستخدام Streamlit و Google Sheets
- القائمة الجانبية على اليسار وتعمل بشكل كامل
- إخفاء شريط Streamlit العلوي
- دعم كامل للغة العربية
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
from io import BytesIO

# ==================== إعدادات الصفحة ====================
st.set_page_config(
    page_title="الكوتش أكاديمي",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== تحميل الشعار ====================
def get_logo_base64() -> Optional[str]:
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

def display_logo():
    logo_base64 = get_logo_base64()
    if logo_base64:
        st.sidebar.markdown(
            f"""
            <div style="text-align: center; padding: 10px;">
                <img src="data:image/jpeg;base64,{logo_base64}" width="120"
                     style="border-radius: 50%; border: 2px solid #2e7d32;">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.markdown("""<div style="text-align: center;"><h1>⚽</h1></div>""", unsafe_allow_html=True)

# ==================== أنماط CSS محسنة ومضمونة ====================
def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
    }

    /* المحتوى الرئيسي بالعربية */
    .main .block-container {
        direction: rtl !important;
        text-align: right !important;
        padding-top: 1rem !important;
    }

    /* إخفاء شريط Streamlit العلوي */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    button[kind="header"] {
        display: none !important;
    }
    div[data-testid="stStatusWidget"] {
        display: none !important;
    }

    /* تنسيق الشريط الجانبي */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e0e0e0 !important;
    }
    section[data-testid="stSidebar"] .block-container {
        padding: 1rem 0.5rem !important;
    }
    section[data-testid="stSidebar"] * {
        color: #1e1e1e !important;
    }

    /* تنسيق أزرار الراديو */
    .stRadio label {
        font-weight: 500;
        padding: 0.5rem 0.75rem;
        border-radius: 8px;
        margin-bottom: 0.25rem;
    }
    .stRadio label:hover {
        background-color: #f0f0f0 !important;
    }

    /* أزرار */
    .stButton button {
        background-color: #2e7d32 !important;
        color: white !important;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        border: none;
    }
    .stButton button:hover {
        background-color: #1b5e20 !important;
    }

    /* بطاقات */
    .card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: 1px solid #e0e0e0;
    }

    /* تنبيهات */
    .alert-warning {
        background-color: #fff3e0;
        border-right: 4px solid #ff9800;
        padding: 1rem;
        border-radius: 8px;
        color: #1e1e1e !important;
    }

    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e0e0e0;
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
            st.warning("انتهت الجلسة")
            st.stop()
        st.session_state.last_activity = time.time()

# ==================== قاعدة البيانات ====================
class GoogleSheetsDB:
    def __init__(self):
        self.spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
        self._client = None
        self._spreadsheet = None
        self._init_connection()
        self._ensure_sheets_exist()
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
                private_key = service_account_info['private_key'].replace('\\n', '\n')
                if '-----BEGIN PRIVATE KEY-----' not in private_key:
                    private_key = '-----BEGIN PRIVATE KEY-----\n' + private_key + '\n-----END PRIVATE KEY-----'
                service_account_info['private_key'] = private_key
            creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            self._client = gspread.authorize(creds)
            self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
        except Exception as e:
            st.error(f"❌ فشل الاتصال بـ Google Sheets: {str(e)}")
            st.stop()

    def _ensure_sheets_exist(self):
        required = {
            "Users": ["username", "password", "role", "created_at"],
            "Attendance": ["player_name", "date", "status", "recorded_by", "recorded_at"],
            "Memberships": ["player_name", "monthly_fee", "start_date", "end_date",
                           "notes", "amount_paid", "payment_method", "payment_date",
                           "recorded_by", "recorded_at"]
        }
        for name, headers in required.items():
            try:
                self._spreadsheet.worksheet(name)
            except gspread.exceptions.WorksheetNotFound:
                ws = self._spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
                ws.append_row(headers)

    def _initialize_default_coach(self):
        try:
            ws = self._spreadsheet.worksheet("Users")
            try:
                users = ws.get_all_records()
            except:
                users = []
            if not any(u.get("role") == "coach" for u in users):
                ws.append_row(["أحمد محمد علي", "coach123", "coach", str(date.today())])
        except Exception:
            pass

    # ---------- المستخدمين ----------
    def get_users_sheet(self):
        return self._spreadsheet.worksheet("Users")

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        for u in users:
            if u.get("username") == username and u.get("password") == password:
                return u
        return None

    def user_exists(self, username: str) -> bool:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        return any(u.get("username") == username for u in users)

    def add_user(self, username: str, password: str, role: str) -> Tuple[bool, str]:
        if not self._validate_three_part_name(username):
            return False, "❌ يجب أن يكون الاسم ثلاثياً على الأقل (مثال: أحمد محمد علي)"
        if self.user_exists(username):
            return False, "❌ اسم المستخدم موجود مسبقاً"
        if len(password) < 4:
            return False, "❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل"
        self.get_users_sheet().append_row([username, password, role, str(date.today())])
        return True, "✅ تم إنشاء الحساب بنجاح"

    def get_all_players(self) -> List[str]:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        return [u["username"] for u in users if u.get("role") == "player"]

    def update_user_password(self, username: str, new_password: str) -> bool:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        for i, u in enumerate(users, start=2):
            if u.get("username") == username:
                ws.update(f'B{i}', new_password)
                return True
        return False

    # ---------- الحضور ----------
    def get_attendance_sheet(self):
        return self._spreadsheet.worksheet("Attendance")

    def record_attendance(self, date_str: str, absent_players: List[str], coach_name: str) -> bool:
        ws = self.get_attendance_sheet()
        all_players = self.get_all_players()
        records = ws.get_all_records()
        for i, r in enumerate(records, start=2):
            if r.get("date") == date_str:
                ws.delete_rows(i)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in all_players:
            status = "Absent" if p in absent_players else "Present"
            ws.append_row([p, date_str, status, coach_name, timestamp])
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

    # ---------- الاشتراكات والمدفوعات ----------
    def get_memberships_sheet(self):
        return self._spreadsheet.worksheet("Memberships")

    def add_membership(self, player_name: str, monthly_fee: float,
                      start_date: str, end_date: str, notes: str,
                      amount_paid: float, payment_method: str,
                      payment_date: str, recorded_by: str) -> bool:
        ws = self.get_memberships_sheet()
        ws.append_row([player_name, monthly_fee, start_date, end_date, notes,
                      amount_paid, payment_method, payment_date, recorded_by,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        return True

    def get_all_memberships(self) -> pd.DataFrame:
        ws = self.get_memberships_sheet()
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_player_memberships(self, player_name: str) -> pd.DataFrame:
        df = self.get_all_memberships()
        if not df.empty:
            return df[df["player_name"] == player_name].sort_values("start_date", ascending=False)
        return df

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
        for col, val in updates.items():
            if col in headers:
                col_idx = headers.index(col) + 1
                ws.update_cell(sheet_row, col_idx, val)
        return True

    def delete_membership(self, row_index: int) -> bool:
        ws = self.get_memberships_sheet()
        ws.delete_rows(row_index + 2)
        return True

    def get_players_payment_status(self) -> pd.DataFrame:
        players = self.get_all_players()
        df = self.get_all_memberships()
        if df.empty:
            return pd.DataFrame(columns=["اللاعب", "إجمالي المستحق", "إجمالي المدفوع", "المتبقي", "الحالة"])
        summary = df.groupby("player_name").agg({"monthly_fee": "sum", "amount_paid": "sum"}).reset_index()
        summary.columns = ["اللاعب", "إجمالي المستحق", "إجمالي المدفوع"]
        summary["المتبقي"] = summary["إجمالي المستحق"] - summary["إجمالي المدفوع"]
        summary["الحالة"] = summary["المتبقي"].apply(lambda x: "✅ مسدد" if x <= 0 else "❌ غير مسدد")
        for p in players:
            if p not in summary["اللاعب"].values:
                summary = pd.concat([summary, pd.DataFrame([{
                    "اللاعب": p, "إجمالي المستحق": 0, "إجمالي المدفوع": 0,
                    "المتبقي": 0, "الحالة": "⚠️ لا يوجد اشتراك"
                }])], ignore_index=True)
        return summary.sort_values("المتبقي", ascending=False)

    @staticmethod
    def _validate_three_part_name(name: str) -> bool:
        if not name: return False
        return len(name.strip().split()) >= 3

    @staticmethod
    def validate_three_part_name(name: str) -> Tuple[bool, str]:
        if not name: return False, "الاسم غير صالح"
        parts = name.strip().split()
        if len(parts) < 3:
            return False, "يجب أن يكون الاسم ثلاثياً (مثال: أحمد محمد علي)"
        if any(len(p) < 2 for p in parts):
            return False, "كل جزء يجب أن يكون حرفين على الأقل"
        if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', name):
            return False, "أحرف عربية أو إنجليزية فقط"
        return True, ""

# ==================== واجهات المستخدم ====================
def show_header():
    col1, col2, col3 = st.columns([1,3,1])
    with col2:
        if os.path.exists("logo.jpg"):
            st.image("logo.jpg", width=150)
        st.markdown("""
        <div style="text-align:center;">
            <h1 style="color:#2e7d32;">⚽ الكوتش أكاديمي</h1>
            <h3>نظام إدارة الحضور والاشتراكات</h3>
        </div>
        """, unsafe_allow_html=True)

def login_page():
    show_header()
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.container():
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align:center;'>🔐 تسجيل الدخول</h3>", unsafe_allow_html=True)
            username = st.text_input("👤 الاسم الثلاثي", placeholder="أحمد محمد علي")
            password = st.text_input("🔒 كلمة المرور", type="password")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🚪 دخول", type="primary", use_container_width=True):
                    if not username or not password:
                        st.error("أدخل البيانات")
                    else:
                        db = GoogleSheetsDB()
                        user = db.authenticate_user(username, password)
                        if user:
                            SessionManager.login(username, user["role"])
                            st.success("تم الدخول")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("بيانات خاطئة")
            with col_b:
                if st.button("📝 حساب جديد", use_container_width=True):
                    st.session_state.show_register = True
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("ℹ️ معلومات"):
            st.markdown("- الاسم ثلاثي\n- كلمة المرور 4 أحرف\n- الكابتن الافتراضي: أحمد محمد علي / coach123")

def register_page():
    show_header()
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;'>📝 إنشاء حساب لاعب</h3>", unsafe_allow_html=True)
        new_username = st.text_input("👤 الاسم الثلاثي", placeholder="أحمد محمد علي")
        new_password = st.text_input("🔒 كلمة المرور", type="password")
        confirm = st.text_input("🔒 تأكيد كلمة المرور", type="password")
        if st.button("✅ تسجيل", type="primary", use_container_width=True):
            db = GoogleSheetsDB()
            valid, msg = db.validate_three_part_name(new_username)
            if not valid: st.error(msg)
            elif new_password != confirm: st.error("كلمة المرور غير متطابقة")
            elif len(new_password) < 4: st.error("4 أحرف على الأقل")
            else:
                success, msg = db.add_user(new_username, new_password, "player")
                if success:
                    st.success(msg)
                    st.session_state.show_register = False
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(msg)
        if st.button("🔙 العودة", use_container_width=True):
            st.session_state.show_register = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

def coach_sidebar():
    with st.sidebar:
        display_logo()
        st.markdown(f"<h3 style='text-align:center;'>👋 كابتن<br>{st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {
            "📋 تسجيل الغياب": "attendance",
            "💰 الاشتراكات والمدفوعات": "memberships",
            "📊 الإحصائيات": "statistics",
            "👥 اللاعبين": "players",
            "⚙️ الإعدادات": "settings"
        }
        selected = st.radio("القائمة", list(menu.keys()))
        st.markdown("---")
        db = GoogleSheetsDB()
        st.metric("👥 عدد اللاعبين", len(db.get_all_players()))
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        return menu[selected]

def player_sidebar():
    with st.sidebar:
        display_logo()
        st.markdown(f"<h3 style='text-align:center;'>👋 {st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {
            "📊 لوحة المعلومات": "dashboard",
            "📅 سجل الحضور": "attendance_history",
            "💰 اشتراكاتي": "financial",
            "⚙️ الإعدادات": "settings"
        }
        selected = st.radio("القائمة", list(menu.keys()))
        st.markdown("---")
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        return menu[selected]

# ==================== صفحات الكابتن ====================
def coach_attendance_page():
    st.header("📋 تسجيل الغياب")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون")
        return
    att_date = st.date_input("📅 التاريخ", value=date.today())
    ws = db.get_attendance_sheet()
    records = ws.get_all_records()
    today_absent = [r["player_name"] for r in records if r.get("date") == str(att_date) and r.get("status") == "Absent"]
    st.info("اختر الغائبين فقط، الباقي حضور تلقائي")
    selected = st.multiselect("❌ الغائبين", players, default=today_absent)
    col1, col2, col3 = st.columns(3)
    col1.metric("الإجمالي", len(players))
    col2.metric("✅ حضور", len(players)-len(selected))
    col3.metric("❌ غياب", len(selected))
    if st.button("💾 حفظ", type="primary", use_container_width=True):
        db.record_attendance(str(att_date), selected, st.session_state.username)
        st.success("تم الحفظ")
        st.rerun()
    st.markdown("---")
    st.subheader("سجل الحضور السابق")
    att_data = ws.get_all_records()
    if att_data:
        df = pd.DataFrame(att_data).sort_values("date", ascending=False)
        dates = sorted(df["date"].unique(), reverse=True)
        if dates:
            selected_date = st.selectbox("اختر تاريخ", dates)
            st.dataframe(df[df["date"] == selected_date][["player_name", "status", "recorded_by", "recorded_at"]], use_container_width=True)

def coach_memberships_page():
    st.header("💰 الاشتراكات والمدفوعات")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون")
        return
    tab1, tab2, tab3 = st.tabs(["➕ إضافة", "📋 السجلات", "💳 حالة الدفع"])
    with tab1:
        with st.form("new_mem"):
            col1, col2 = st.columns(2)
            with col1:
                player = st.selectbox("اللاعب", players)
                fee = st.number_input("الرسوم الشهرية", value=1500.0, step=50.0)
                start = st.date_input("بداية الاشتراك", value=date.today())
                end = st.date_input("نهاية الاشتراك", value=date.today()+timedelta(days=30))
                notes = st.text_area("ملاحظات")
            with col2:
                paid = st.number_input("المبلغ المدفوع", step=50.0)
                method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
                pay_date = st.date_input("تاريخ الدفع", value=date.today())
            if st.form_submit_button("💾 حفظ"):
                db.add_membership(player, fee, str(start), str(end), notes, paid, method, str(pay_date), st.session_state.username)
                st.success("تم الحفظ")
                st.rerun()
    with tab2:
        df = db.get_all_memberships()
        if not df.empty:
            st.dataframe(df.sort_values("start_date", ascending=False), use_container_width=True)
    with tab3:
        pay_df = db.get_players_payment_status()
        if not pay_df.empty:
            st.dataframe(pay_df, use_container_width=True)
            unpaid = pay_df[pay_df["المتبقي"] > 0]
            if not unpaid.empty:
                st.markdown(f"""<div class="alert-warning"><strong>⚠️ متأخرين:</strong> {len(unpaid)} لاعبين، المتبقي {unpaid['المتبقي'].sum():,.0f} ج.م</div>""", unsafe_allow_html=True)
            df_all = db.get_all_memberships()
            if not df_all.empty:
                method_counts = df_all["payment_method"].value_counts()
                fig = px.pie(values=method_counts.values, names=method_counts.index, title="طرق الدفع")
                st.plotly_chart(fig, use_container_width=True)

def coach_statistics_page():
    st.header("📊 الإحصائيات")
    db = GoogleSheetsDB()
    tab1, tab2 = st.tabs(["📈 مقارنة الحضور", "📋 تصدير"])
    with tab1:
        att_data = db.get_attendance_sheet().get_all_records()
        if att_data:
            df = pd.DataFrame(att_data)
            df["date"] = pd.to_datetime(df["date"])
            df["month"] = df["date"].dt.to_period("M").astype(str)
            months = sorted(df["month"].unique(), reverse=True)
            if len(months) >= 2:
                m1 = st.selectbox("الشهر الأول", months, index=0)
                m2 = st.selectbox("الشهر الثاني", months, index=1)
                rates1 = df[df["month"]==m1].groupby("player_name")["status"].apply(lambda x: (x=="Present").sum()/len(x)*100 if len(x) else 0).reset_index(name=f"{m1} %")
                rates2 = df[df["month"]==m2].groupby("player_name")["status"].apply(lambda x: (x=="Present").sum()/len(x)*100 if len(x) else 0).reset_index(name=f"{m2} %")
                merged = rates1.merge(rates2, on="player_name", how="outer").fillna(0)
                st.dataframe(merged)
    with tab2:
        if st.button("تصدير تقرير الحضور"):
            summary = db.get_attendance_summary()
            if not summary.empty:
                output = BytesIO()
                summary.to_excel(output, index=False)
                st.download_button("تحميل", output.getvalue(), "attendance.xlsx")

def coach_players_page():
    st.header("👥 اللاعبين")
    db = GoogleSheetsDB()
    users = db.get_users_sheet().get_all_records()
    if users:
        df = pd.DataFrame(users)
        players = df[df["role"]=="player"]
        if not players.empty:
            st.dataframe(players[["username", "created_at"]])
            sel = st.selectbox("اختر لاعب", players["username"])
            new_pass = st.text_input("كلمة مرور جديدة", type="password")
            if st.button("تحديث"):
                if len(new_pass) < 4: st.error("4 أحرف")
                elif db.update_user_password(sel, new_pass): st.success("تم")

def coach_settings_page():
    st.header("⚙️ الإعدادات")
    with st.form("pass"):
        curr = st.text_input("الحالية", type="password")
        new = st.text_input("الجديدة", type="password")
        conf = st.text_input("تأكيد", type="password")
        if st.form_submit_button("تحديث"):
            if new != conf: st.error("غير متطابقة")
            elif len(new) < 4: st.error("4 أحرف")
            else:
                db = GoogleSheetsDB()
                if db.authenticate_user(st.session_state.username, curr):
                    db.update_user_password(st.session_state.username, new)
                    st.success("تم")

# ==================== صفحات اللاعب ====================
def player_dashboard_page():
    st.header("لوحة المعلومات")
    db = GoogleSheetsDB()
    p = st.session_state.username
    att = db.get_attendance_for_player(p)
    if not att.empty:
        total = len(att)
        present = len(att[att["status"]=="Present"])
        st.metric("نسبة الحضور", f"{(present/total*100):.1f}%" if total else "0%")
    mem = db.get_player_memberships(p)
    if not mem.empty:
        paid = mem["amount_paid"].sum()
        owed = mem["monthly_fee"].sum()
        st.metric("المدفوع", f"{paid:,.0f} ج.م")
        st.metric("المتبقي", f"{owed-paid:,.0f} ج.م")

def player_attendance_history_page():
    st.header("سجل الحضور")
    db = GoogleSheetsDB()
    df = db.get_attendance_for_player(st.session_state.username)
    if not df.empty:
        st.dataframe(df[["date", "status"]])

def player_financial_page():
    st.header("اشتراكاتي")
    db = GoogleSheetsDB()
    df = db.get_player_memberships(st.session_state.username)
    if not df.empty:
        st.dataframe(df)

def player_settings_page():
    st.header("الإعدادات")
    with st.form("player_pass"):
        curr = st.text_input("الحالية", type="password")
        new = st.text_input("الجديدة", type="password")
        conf = st.text_input("تأكيد", type="password")
        if st.form_submit_button("تحديث"):
            if new != conf: st.error("غير متطابقة")
            elif len(new) < 4: st.error("4 أحرف")
            else:
                db = GoogleSheetsDB()
                if db.authenticate_user(st.session_state.username, curr):
                    db.update_user_password(st.session_state.username, new)
                    st.success("تم")

# ==================== الرئيسية ====================
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
            if page == "attendance": coach_attendance_page()
            elif page == "memberships": coach_memberships_page()
            elif page == "statistics": coach_statistics_page()
            elif page == "players": coach_players_page()
            elif page == "settings": coach_settings_page()
        else:
            page = player_sidebar()
            if page == "dashboard": player_dashboard_page()
            elif page == "attendance_history": player_attendance_history_page()
            elif page == "financial": player_financial_page()
            elif page == "settings": player_settings_page()

if __name__ == "__main__":
    main()
