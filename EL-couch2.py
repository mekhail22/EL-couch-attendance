# -*- coding: utf-8 -*-
"""
تطبيق إدارة الحضور والاشتراكات لأكاديمية كرة قدم "الكوتش أكاديمي"
باستخدام Streamlit و Google Sheets
- إصلاح خطأ API في تهيئة الحساب الافتراضي
- ميزات متقدمة في التقارير والإحصائيات
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
    page_title="الكوتش أكاديمي - إدارة الحضور والاشتراكات",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== تحميل الشعار ====================
def get_logo_base64():
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
                <img src="data:image/jpeg;base64,{logo_base64}" width="150" style="border-radius: 50%; border: 3px solid #2e7d32;">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.markdown("""<div style="text-align: center; padding: 10px;"><h1>⚽</h1></div>""", unsafe_allow_html=True)

# ==================== أنماط CSS ====================
def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
    .main-header { text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%); color: white; border-radius: 15px; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .card { background: white; border-radius: 15px; padding: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 1rem; border: 1px solid #e0e0e0; }
    .stButton button { background-color: #2e7d32; color: white; border-radius: 8px; padding: 0.5rem 1rem; font-weight: bold; border: none; }
    .stButton button:hover { background-color: #1b5e20; }
    .logout-btn { background-color: #d32f2f !important; }
    .dataframe { border-radius: 10px; overflow: hidden; border: 1px solid #e0e0e0; }
    .alert-box { padding: 1rem; border-radius: 8px; margin: 1rem 0; }
    .alert-warning { background-color: #fff3e0; border-right: 4px solid #ff9800; }
    .alert-danger { background-color: #ffebee; border-right: 4px solid #f44336; }
    .alert-success { background-color: #e8f5e9; border-right: 4px solid #4caf50; }
    </style>
    """, unsafe_allow_html=True)

# ==================== إدارة الجلسات ====================
class SessionManager:
    @staticmethod
    def init_session():
        defaults = {"logged_in": False, "username": None, "role": None, "show_register": False, "last_activity": time.time()}
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    @staticmethod
    def login(username, role):
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

# ==================== قاعدة البيانات (Google Sheets) ====================
class GoogleSheetsDB:
    def __init__(self):
        self.spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
        self._client = None
        self._spreadsheet = None
        self._init_connection()
        self._initialize_default_coach()

    def _init_connection(self):
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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

    def _initialize_default_coach(self):
        """إضافة كابتن افتراضي بشكل آمن مع معالجة الأخطاء"""
        try:
            ws = self.get_users_sheet()  # هذا ينشئ الورقة إذا لم تكن موجودة
            # محاولة جلب البيانات مع معالجة الخطأ
            try:
                users = ws.get_all_records()
            except gspread.exceptions.APIError:
                # ربما الورقة فارغة، نعتبرها لا تحتوي على كابتن
                users = []
            coach_exists = any(user.get("role") == "coach" for user in users)
            if not coach_exists:
                ws.append_row(["أحمد محمد علي", "coach123", "coach", str(date.today())])
        except Exception as e:
            # إذا فشل كل شيء، تجاهل الخطأ لأن التطبيق سيستمر
            print(f"تحذير: لم يتم إنشاء الكابتن الافتراضي - {e}")

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
            if user.get("username") == username and user.get("password") == password:
                return user
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
        ws = self.get_users_sheet()
        ws.append_row([username, password, role, str(date.today())])
        return True, "✅ تم إنشاء الحساب بنجاح"

    def get_all_players(self) -> List[str]:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        return [u["username"] for u in users if u.get("role") == "player"]

    def update_user_password(self, username: str, new_password: str) -> bool:
        ws = self.get_users_sheet()
        users = ws.get_all_records()
        for i, user in enumerate(users, start=2):
            if user.get("username") == username:
                ws.update(f'B{i}', new_password)
                return True
        return False

    # ========== الحضور ==========
    def get_attendance_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Attendance", ["player_name", "date", "status", "recorded_by", "recorded_at"])

    def record_attendance(self, date_str: str, absent_players: List[str], coach_name: str) -> bool:
        ws = self.get_attendance_sheet()
        all_players = self.get_all_players()
        records = ws.get_all_records()
        rows_to_delete = [i for i, r in enumerate(records, start=2) if r.get("date") == date_str]
        for row in sorted(rows_to_delete, reverse=True):
            ws.delete_rows(row)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for player in all_players:
            status = "Absent" if player in absent_players else "Present"
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

    # ========== الاشتراكات والمدفوعات ==========
    def get_memberships_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Memberships",
            ["player_name", "monthly_fee", "start_date", "end_date", "notes", "amount_paid", "payment_method", "payment_date", "recorded_by", "recorded_at"])

    def add_membership(self, player_name: str, monthly_fee: float, start_date: str, end_date: str, notes: str,
                      amount_paid: float, payment_method: str, payment_date: str, recorded_by: str) -> bool:
        ws = self.get_memberships_sheet()
        ws.append_row([player_name, monthly_fee, start_date, end_date, notes, amount_paid, payment_method, payment_date, recorded_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
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

    def get_players_payment_status(self) -> pd.DataFrame:
        players = self.get_all_players()
        memberships_df = self.get_all_memberships()
        if memberships_df.empty:
            return pd.DataFrame(columns=["اللاعب", "إجمالي المستحق", "إجمالي المدفوع", "المتبقي", "الحالة"])
        summary = memberships_df.groupby("player_name").agg({"monthly_fee": "sum", "amount_paid": "sum"}).reset_index()
        summary.columns = ["اللاعب", "إجمالي المستحق", "إجمالي المدفوع"]
        summary["المتبقي"] = summary["إجمالي المستحق"] - summary["إجمالي المدفوع"]
        summary["الحالة"] = summary["المتبقي"].apply(lambda x: "✅ مسدد" if x <= 0 else "❌ غير مسدد")
        for p in players:
            if p not in summary["اللاعب"].values:
                summary = pd.concat([summary, pd.DataFrame([{"اللاعب": p, "إجمالي المستحق": 0, "إجمالي المدفوع": 0, "المتبقي": 0, "الحالة": "⚠️ لا يوجد اشتراك"}])], ignore_index=True)
        return summary.sort_values("المتبقي", ascending=False)

    @staticmethod
    def _validate_three_part_name(name: str) -> bool:
        if not name or not isinstance(name, str): return False
        parts = name.strip().split()
        return len(parts) >= 3

    @staticmethod
    def validate_three_part_name(name: str) -> Tuple[bool, str]:
        if not name: return False, "الاسم غير صالح"
        parts = name.strip().split()
        if len(parts) < 3: return False, "يجب أن يتكون الاسم من ثلاثة أجزاء على الأقل (مثال: أحمد محمد علي)"
        if any(len(part) < 2 for part in parts): return False, "يجب أن يتكون كل جزء من حرفين على الأقل"
        if not re.match(r'^[\u0600-\u06FFa-zA-Z\s]+$', name): return False, "أحرف عربية أو إنجليزية فقط"
        return True, ""

# ==================== واجهات المستخدم ====================
def show_header():
    col1, col2, col3 = st.columns([1,3,1])
    with col2:
        if os.path.exists("logo.jpg"):
            st.image("logo.jpg", width=150)
        st.markdown("""<div style="text-align:center;"><h1 style="color:#2e7d32;">⚽ الكوتش أكاديمي</h1><h3>نظام إدارة الحضور والاشتراكات</h3></div>""", unsafe_allow_html=True)

def login_page():
    show_header()
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.container():
            st.markdown("<div class='card'><h3 style='text-align:center;'>🔐 تسجيل الدخول</h3>", unsafe_allow_html=True)
            username = st.text_input("👤 الاسم الثلاثي", placeholder="أحمد محمد علي")
            password = st.text_input("🔒 كلمة المرور", type="password")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🚪 دخول", type="primary", use_container_width=True):
                    if not username or not password:
                        st.error("الرجاء إدخال البيانات")
                    else:
                        db = GoogleSheetsDB()
                        user = db.authenticate_user(username, password)
                        if user:
                            SessionManager.login(username, user["role"])
                            st.success("تم الدخول")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("بيانات غير صحيحة")
            with col_b:
                if st.button("📝 إنشاء حساب", use_container_width=True):
                    st.session_state.show_register = True
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("ℹ️ معلومات"):
            st.markdown("- الاسم ثلاثي\n- كلمة المرور 4 أحرف\n- الكابتن الافتراضي: أحمد محمد علي / coach123")

def register_page():
    show_header()
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div class='card'><h3>📝 إنشاء حساب لاعب</h3>", unsafe_allow_html=True)
        new_username = st.text_input("👤 الاسم الثلاثي", placeholder="أحمد محمد علي")
        new_password = st.text_input("🔒 كلمة المرور", type="password")
        confirm_password = st.text_input("🔒 تأكيد كلمة المرور", type="password")
        if st.button("✅ تسجيل", type="primary", use_container_width=True):
            db = GoogleSheetsDB()
            valid, msg = db.validate_three_part_name(new_username)
            if not valid: st.error(msg)
            elif new_password != confirm_password: st.error("كلمة المرور غير متطابقة")
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
        st.markdown(f"<h3>👋 كابتن {st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {"📋 تسجيل الغياب": "attendance", "💰 الاشتراكات والمدفوعات": "memberships", "📊 الإحصائيات والتقارير": "statistics", "👥 اللاعبين": "players", "⚙️ الإعدادات": "settings"}
        selected = st.radio("القائمة", list(menu.keys()))
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
        st.markdown(f"<h3>👋 {st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {"📊 لوحة المعلومات": "dashboard", "📅 سجل الحضور": "attendance_history", "💰 اشتراكاتي": "financial", "⚙️ الإعدادات": "settings"}
        selected = st.radio("القائمة", list(menu.keys()))
        current_page = menu[selected]
        st.markdown("---")
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        return current_page

# ==================== صفحات الكابتن ====================
def coach_attendance_page():
    st.header("📋 تسجيل الغياب (الحضور تلقائي)")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون")
        return
    att_date = st.date_input("📅 التاريخ", value=date.today())
    ws_att = db.get_attendance_sheet()
    records = ws_att.get_all_records()
    today_absent = [r["player_name"] for r in records if r.get("date") == str(att_date) and r.get("status") == "Absent"]
    st.info("اختر الغائبين فقط")
    selected_absent = st.multiselect("❌ الغائبين", players, default=today_absent)
    present_players = [p for p in players if p not in selected_absent]
    col1, col2, col3 = st.columns(3)
    col1.metric("الإجمالي", len(players))
    col2.metric("✅ حضور", len(present_players))
    col3.metric("❌ غياب", len(selected_absent))
    if st.button("💾 حفظ", type="primary", use_container_width=True):
        db.record_attendance(str(att_date), selected_absent, st.session_state.username)
        st.success("تم الحفظ")
        st.rerun()

def coach_memberships_page():
    st.header("💰 الاشتراكات والمدفوعات")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players: st.warning("لا يوجد لاعبون"); return
    tab1, tab2, tab3 = st.tabs(["➕ إضافة", "📋 السجلات", "💳 حالة الدفع"])
    with tab1:
        with st.form("new_membership"):
            col1, col2 = st.columns(2)
            with col1:
                player = st.selectbox("اللاعب", players)
                monthly_fee = st.number_input("الرسوم الشهرية", value=1500.0, step=50.0)
                start_date = st.date_input("بداية الاشتراك", value=date.today())
                end_date = st.date_input("نهاية الاشتراك", value=date.today()+timedelta(days=30))
                notes = st.text_area("ملاحظات")
            with col2:
                amount_paid = st.number_input("المبلغ المدفوع", step=50.0)
                payment_method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
                payment_date = st.date_input("تاريخ الدفع", value=date.today())
            if st.form_submit_button("💾 حفظ"):
                db.add_membership(player, monthly_fee, str(start_date), str(end_date), notes, amount_paid, payment_method, str(payment_date), st.session_state.username)
                st.success("تم الحفظ")
                st.rerun()
    with tab2:
        df = db.get_all_memberships()
        if not df.empty:
            st.dataframe(df.sort_values("start_date", ascending=False), use_container_width=True)
    with tab3:
        payment_df = db.get_players_payment_status()
        if not payment_df.empty:
            st.dataframe(payment_df, use_container_width=True)
            unpaid = payment_df[payment_df["المتبقي"] > 0]
            if not unpaid.empty:
                st.markdown(f"<div class='alert-box alert-warning'><strong>⚠️ تنبيه:</strong> يوجد {len(unpaid)} لاعبين متأخرين في السداد بإجمالي {unpaid['المتبقي'].sum():,.0f} ج.م</div>", unsafe_allow_html=True)
            # رسم بياني واحد فقط
            df_all = db.get_all_memberships()
            if not df_all.empty:
                method_counts = df_all["payment_method"].value_counts()
                fig = px.pie(values=method_counts.values, names=method_counts.index, title="توزيع طرق الدفع")
                st.plotly_chart(fig, use_container_width=True)

def coach_statistics_page():
    st.header("📊 الإحصائيات والتقارير المتقدمة")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون")
        return
    tab1, tab2, tab3 = st.tabs(["📈 تحليل الحضور", "💰 تحليل مالي", "📋 تقارير قابلة للتصدير"])
    with tab1:
        st.subheader("مقارنة الحضور بين شهرين")
        att_df = db.get_attendance_sheet().get_all_records()
        if att_df:
            df = pd.DataFrame(att_df)
            df["date"] = pd.to_datetime(df["date"])
            df["month"] = df["date"].dt.to_period("M").astype(str)
            months = sorted(df["month"].unique(), reverse=True)
            if len(months) >= 2:
                col1, col2 = st.columns(2)
                with col1: month1 = st.selectbox("الشهر الأول", months, index=0)
                with col2: month2 = st.selectbox("الشهر الثاني", months, index=min(1, len(months)-1))
                m1 = df[df["month"] == month1].groupby("player_name")["status"].apply(lambda x: (x=="Present").sum()/len(x)*100 if len(x) else 0).reset_index(name="نسبة الحضور %")
                m2 = df[df["month"] == month2].groupby("player_name")["status"].apply(lambda x: (x=="Present").sum()/len(x)*100 if len(x) else 0).reset_index(name="نسبة الحضور %")
                merged = m1.merge(m2, on="player_name", suffixes=(f"_{month1}", f"_{month2}"), how="outer").fillna(0)
                merged["التغير"] = merged[f"نسبة الحضور %_{month2}"] - merged[f"نسبة الحضور %_{month1}"]
                st.dataframe(merged)
                fig = px.bar(merged.melt(id_vars="player_name", value_vars=[f"نسبة الحضور %_{month1}", f"نسبة الحضور %_{month2}"]),
                            x="player_name", y="value", color="variable", barmode="group", title="مقارنة الحضور")
                st.plotly_chart(fig, use_container_width=True)
    with tab2:
        st.subheader("تحليل مالي")
        payment_df = db.get_players_payment_status()
        if not payment_df.empty:
            total_owed = payment_df["إجمالي المستحق"].sum()
            total_paid = payment_df["إجمالي المدفوع"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("إجمالي المستحقات", f"{total_owed:,.0f} ج.م")
            col2.metric("المدفوع", f"{total_paid:,.0f} ج.م")
            col3.metric("المتبقي", f"{total_owed-total_paid:,.0f} ج.م")
            # رسم بياني للأرباح الشهرية
            df_mem = db.get_all_memberships()
            if not df_mem.empty:
                df_mem["payment_month"] = pd.to_datetime(df_mem["payment_date"]).dt.to_period("M").astype(str)
                monthly = df_mem.groupby("payment_month")["amount_paid"].sum().reset_index()
                fig = px.line(monthly, x="payment_month", y="amount_paid", title="تطور المدفوعات الشهرية", markers=True)
                st.plotly_chart(fig, use_container_width=True)
    with tab3:
        st.subheader("تصدير التقارير")
        if st.button("📥 تصدير تقرير الحضور (Excel)"):
            summary = db.get_attendance_summary()
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                summary.to_excel(writer, sheet_name="الحضور", index=False)
            st.download_button("تحميل", data=output.getvalue(), file_name=f"تقرير_الحضور_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def coach_players_page():
    st.header("👥 إدارة اللاعبين")
    db = GoogleSheetsDB()
    users = db.get_users_sheet().get_all_records()
    if users:
        df = pd.DataFrame(users)
        players_df = df[df["role"] == "player"]
        if not players_df.empty:
            st.dataframe(players_df[["username", "created_at"]], use_container_width=True)
            st.subheader("إعادة تعيين كلمة مرور")
            sel = st.selectbox("اختر اللاعب", players_df["username"].tolist())
            new_pass = st.text_input("كلمة المرور الجديدة", type="password")
            if st.button("تحديث"):
                if len(new_pass) < 4: st.error("4 أحرف على الأقل")
                elif db.update_user_password(sel, new_pass): st.success("تم التحديث")
                else: st.error("فشل")

def coach_settings_page():
    st.header("⚙️ الإعدادات")
    with st.form("change_pass"):
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
                    st.success("تم التحديث")
                else: st.error("كلمة مرور خاطئة")

# ==================== صفحات اللاعب ====================
def player_dashboard_page():
    st.header("📊 لوحة المعلومات")
    db = GoogleSheetsDB()
    player = st.session_state.username
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("الحضور")
        att = db.get_attendance_for_player(player)
        if not att.empty:
            total = len(att)
            present = len(att[att["status"]=="Present"])
            st.metric("نسبة الحضور", f"{(present/total*100):.1f}%" if total else "0%")
    with col2:
        st.subheader("المدفوعات")
        mem = db.get_player_memberships(player)
        if not mem.empty:
            paid = mem["amount_paid"].sum()
            owed = mem["monthly_fee"].sum()
            st.metric("المدفوع", f"{paid:,.0f} ج.م")
            st.metric("المتبقي", f"{owed-paid:,.0f} ج.م")

def player_attendance_history_page():
    st.header("سجل الحضور")
    db = GoogleSheetsDB()
    att = db.get_attendance_for_player(st.session_state.username)
    if not att.empty:
        st.dataframe(att[["date", "status"]], use_container_width=True)

def player_financial_page():
    st.header("اشتراكاتي")
    db = GoogleSheetsDB()
    mem = db.get_player_memberships(st.session_state.username)
    if not mem.empty:
        st.dataframe(mem, use_container_width=True)

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
                    st.success("تم التحديث")

# ==================== الرئيسية ====================
def main():
    load_css()
    SessionManager.init_session()
    if not st.session_state.logged_in:
        if st.session_state.show_register: register_page()
        else: login_page()
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
