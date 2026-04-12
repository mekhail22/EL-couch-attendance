# -*- coding: utf-8 -*-
"""
تطبيق إدارة الحضور والاشتراكات لأكاديمية كرة قدم "الكوتش أكاديمي"
باستخدام Streamlit و Google Sheets
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

# ==================== إعدادات الصفحة ====================
st.set_page_config(
    page_title="الكوتش أكاديمي",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
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
    
    def _init_connection(self):
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            service_account_info = st.secrets["google"]["service_account"]
            
            # التعامل مع المفتاح الخاص بشكل صحيح
            if isinstance(service_account_info, dict):
                creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            else:
                creds = Credentials.from_service_account_info(json.loads(service_account_info), scopes=scopes)
            
            self._client = gspread.authorize(creds)
            self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
        except Exception as e:
            st.error(f"❌ فشل الاتصال بـ Google Sheets: {str(e)}")
            st.stop()
    
    def get_or_create_worksheet(self, title: str, headers: list) -> gspread.Worksheet:
        try:
            ws = self._spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            ws = self._spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
            ws.append_row(headers)
        return ws
    
    # ---------- المستخدمون ----------
    def get_users_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Users", ["username", "password", "role", "created_at"])
    
    def authenticate_user(self, username: str, password: str):
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
    
    def add_user(self, username: str, password: str, role: str):
        if not self._validate_three_part_name(username):
            return False, "❌ يجب أن يكون الاسم ثلاثياً على الأقل (مثال: أحمد محمد علي)"
        if self.user_exists(username):
            return False, "❌ اسم المستخدم موجود مسبقاً"
        if len(password) < 4:
            return False, "❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل"
        ws = self.get_users_sheet()
        ws.append_row([username, password, role, str(date.today())])
        return True, "✅ تم إنشاء الحساب بنجاح"
    
    def get_all_players(self) -> list:
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
    
    # ---------- الحضور ----------
    def get_attendance_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Attendance", 
            ["player_name", "date", "status", "recorded_by", "recorded_at"])
    
    def record_attendance(self, date_str: str, present_players: list, coach_name: str) -> bool:
        ws = self.get_attendance_sheet()
        all_players = self.get_all_players()
        records = ws.get_all_records()
        rows_to_delete = [i for i, rec in enumerate(records, start=2) if rec["date"] == date_str]
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
    
    # ---------- الاشتراكات ----------
    def get_subscriptions_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Subscriptions",
            ["player_name", "monthly_fee", "start_date", "end_date", 
             "subscription_status", "notes", "created_at"])
    
    def add_subscription(self, player_name: str, monthly_fee: float, 
                        start_date: str, end_date: str, status: str, notes: str = "") -> bool:
        ws = self.get_subscriptions_sheet()
        ws.append_row([
            player_name, monthly_fee, start_date, end_date, 
            status, notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
        return True
    
    def get_player_subscriptions(self, player_name: str) -> pd.DataFrame:
        ws = self.get_subscriptions_sheet()
        data = ws.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if not df.empty:
            return df[df["player_name"] == player_name].sort_values("start_date", ascending=False)
        return df
    
    def get_active_subscription(self, player_name: str):
        df = self.get_player_subscriptions(player_name)
        if not df.empty:
            active = df[df["subscription_status"] == "نشط"]
            if not active.empty:
                return active.iloc[0].to_dict()
        return None
    
    def update_subscription(self, row_index: int, updates: dict) -> bool:
        ws = self.get_subscriptions_sheet()
        sheet_row = row_index + 2
        headers = ws.row_values(1)
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                ws.update_cell(sheet_row, col_idx, value)
        return True
    
    # ---------- المدفوعات ----------
    def get_payments_sheet(self) -> gspread.Worksheet:
        return self.get_or_create_worksheet("Payments",
            ["player_name", "amount", "payment_method", "payment_date", 
             "notes", "recorded_by", "recorded_at"])
    
    def add_payment(self, player_name: str, amount: float, payment_method: str,
                   payment_date: str, notes: str, recorded_by: str) -> bool:
        ws = self.get_payments_sheet()
        ws.append_row([
            player_name, amount, payment_method, payment_date, 
            notes, recorded_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
        return True
    
    def get_player_payments(self, player_name: str) -> pd.DataFrame:
        ws = self.get_payments_sheet()
        data = ws.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if not df.empty:
            return df[df["player_name"] == player_name].sort_values("payment_date", ascending=False)
        return df
    
    def get_all_payments(self) -> pd.DataFrame:
        ws = self.get_payments_sheet()
        data = ws.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def update_payment(self, row_index: int, updates: dict) -> bool:
        ws = self.get_payments_sheet()
        sheet_row = row_index + 2
        headers = ws.row_values(1)
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                ws.update_cell(sheet_row, col_idx, value)
        return True
    
    def delete_payment(self, row_index: int) -> bool:
        ws = self.get_payments_sheet()
        ws.delete_rows(row_index + 2)
        return True
    
    @staticmethod
    def _validate_three_part_name(name: str) -> bool:
        if not name or not isinstance(name, str):
            return False
        parts = name.strip().split()
        return len(parts) >= 3
    
    @staticmethod
    def validate_three_part_name(name: str):
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

def show_logo():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="main-header">
            <h1>⚽ الكوتش أكاديمي</h1>
            <h3>نظام إدارة الحضور والاشتراكات</h3>
        </div>
        """, unsafe_allow_html=True)

def login_page():
    show_logo()
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
            - إذا كنت كابتن، استخدم بيانات الدخول الخاصة بك
            - اللاعبون الجدد يمكنهم إنشاء حساب من خلال زر "إنشاء حساب جديد"
            """)

def register_page():
    show_logo()
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

# ---------- صفحات الكابتن ----------
def coach_sidebar():
    with st.sidebar:
        st.markdown(f"<h3>👋 مرحباً كابتن<br>{st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {
            "📋 تسجيل الحضور": "attendance",
            "💰 إدارة الاشتراكات": "subscriptions",
            "💵 تسجيل المدفوعات": "payments",
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

def coach_subscriptions_page():
    st.header("💰 إدارة اشتراكات اللاعبين")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون بعد")
        return
    tab1, tab2, tab3 = st.tabs(["➕ اشتراك جديد", "📋 الاشتراكات الحالية", "📊 ملخص الاشتراكات"])
    with tab1:
        st.subheader("تسجيل اشتراك جديد")
        with st.form("new_subscription_form"):
            col1, col2 = st.columns(2)
            with col1:
                player = st.selectbox("👤 اللاعب", players)
                monthly_fee = st.number_input("💵 الرسوم الشهرية (جنيه)", min_value=0.0, step=50.0, value=500.0)
                start_date = st.date_input("📅 تاريخ البداية", value=date.today())
            with col2:
                end_date = st.date_input("📅 تاريخ النهاية", value=date.today() + timedelta(days=30))
                status = st.selectbox("📌 الحالة", ["نشط", "منتهي", "متوقف"])
                notes = st.text_area("📝 ملاحظات")
            if st.form_submit_button("💾 حفظ الاشتراك", type="primary"):
                if monthly_fee <= 0:
                    st.error("يجب أن تكون الرسوم الشهرية أكبر من صفر")
                elif end_date <= start_date:
                    st.error("تاريخ النهاية يجب أن يكون بعد تاريخ البداية")
                else:
                    db.add_subscription(player, monthly_fee, str(start_date), str(end_date), status, notes)
                    st.success("✅ تم حفظ الاشتراك بنجاح")
                    time.sleep(1)
                    st.rerun()
    with tab2:
        st.subheader("الاشتراكات المسجلة")
        ws_subs = db.get_subscriptions_sheet()
        subs_data = ws_subs.get_all_records()
        if subs_data:
            df = pd.DataFrame(subs_data)
            selected_player = st.selectbox("تصفية حسب اللاعب", ["الكل"] + players)
            if selected_player != "الكل":
                df = df[df["player_name"] == selected_player]
            status_filter = st.multiselect("تصفية حسب الحالة", ["نشط", "منتهي", "متوقف"], default=["نشط"])
            if status_filter:
                df = df[df["subscription_status"].isin(status_filter)]
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                st.markdown("---")
                st.subheader("✏️ تعديل اشتراك")
                sub_index = st.selectbox("اختر الاشتراك للتعديل", df.index,
                    format_func=lambda x: f"{df.loc[x, 'player_name']} - {df.loc[x, 'start_date']}")
                if sub_index is not None:
                    row = df.loc[sub_index]
                    with st.form("edit_subscription_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            new_fee = st.number_input("الرسوم الشهرية", value=float(row["monthly_fee"]))
                            new_start = st.date_input("تاريخ البداية", value=pd.to_datetime(row["start_date"]).date(), disabled=True)
                        with col2:
                            new_end = st.date_input("تاريخ النهاية", value=pd.to_datetime(row["end_date"]).date())
                            new_status = st.selectbox("الحالة", ["نشط", "منتهي", "متوقف"],
                                index=["نشط", "منتهي", "متوقف"].index(row["subscription_status"]))
                        new_notes = st.text_area("ملاحظات", value=row.get("notes", ""))
                        if st.form_submit_button("تحديث الاشتراك"):
                            updates = {"monthly_fee": new_fee, "end_date": str(new_end),
                                      "subscription_status": new_status, "notes": new_notes}
                            db.update_subscription(sub_index, updates)
                            st.success("تم تحديث الاشتراك بنجاح")
                            time.sleep(1)
                            st.rerun()
            else:
                st.info("لا توجد اشتراكات تطابق معايير التصفية")
        else:
            st.info("لا توجد اشتراكات مسجلة بعد")
    with tab3:
        st.subheader("ملخص الاشتراكات")
        subs_data = ws_subs.get_all_records()
        if subs_data:
            df = pd.DataFrame(subs_data)
            active_subs = df[df["subscription_status"] == "نشط"]
            total_monthly_income = active_subs["monthly_fee"].sum() if not active_subs.empty else 0
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 عدد الاشتراكات النشطة", len(active_subs))
            col2.metric("💰 إجمالي الدخل الشهري المتوقع", f"{total_monthly_income:,.0f} ج.م")
            players_with_active = active_subs["player_name"].unique().tolist()
            col3.metric("⚠️ لاعبون بدون اشتراك نشط", len([p for p in players if p not in players_with_active]))
            if not active_subs.empty:
                fig = px.bar(active_subs, x="player_name", y="monthly_fee", title="الرسوم الشهرية للاعبين")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات")

def coach_payments_page():
    st.header("💵 تسجيل دفعات اللاعبين")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون بعد")
        return
    tab1, tab2 = st.tabs(["➕ دفعة جديدة", "📜 سجل المدفوعات"])
    with tab1:
        st.subheader("تسجيل دفعة جديدة")
        with st.form("new_payment_form"):
            col1, col2 = st.columns(2)
            with col1:
                player = st.selectbox("👤 اللاعب", players)
                amount = st.number_input("💵 المبلغ", min_value=0.0, step=50.0)
                payment_method = st.selectbox("💳 طريقة الدفع", 
                    ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
            with col2:
                payment_date = st.date_input("📅 تاريخ الدفع", value=date.today())
                notes = st.text_area("📝 ملاحظات")
            if st.form_submit_button("💾 تسجيل الدفعة", type="primary"):
                if amount <= 0:
                    st.error("المبلغ يجب أن يكون أكبر من صفر")
                else:
                    db.add_payment(player, amount, payment_method, str(payment_date), notes, st.session_state.username)
                    st.success("✅ تم تسجيل الدفعة بنجاح")
                    time.sleep(1)
                    st.rerun()
    with tab2:
        st.subheader("سجل المدفوعات")
        payments_df = db.get_all_payments()
        if not payments_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_player = st.selectbox("تصفية حسب اللاعب", ["الكل"] + players)
            with col2:
                methods = ["الكل"] + payments_df["payment_method"].unique().tolist()
                filter_method = st.selectbox("طريقة الدفع", methods)
            filtered_df = payments_df.copy()
            if filter_player != "الكل":
                filtered_df = filtered_df[filtered_df["player_name"] == filter_player]
            if filter_method != "الكل":
                filtered_df = filtered_df[filtered_df["payment_method"] == filter_method]
            st.metric("💰 إجمالي المدفوعات المعروضة", f"{filtered_df['amount'].sum():,.0f} ج.م")
            st.dataframe(filtered_df.sort_values("payment_date", ascending=False), use_container_width=True)
            if not filtered_df.empty:
                st.markdown("---")
                st.subheader("✏️ تعديل أو حذف دفعة")
                payment_idx = st.selectbox("اختر الدفعة", filtered_df.index,
                    format_func=lambda x: f"{filtered_df.loc[x, 'player_name']} - {filtered_df.loc[x, 'amount']} ج.م")
                if payment_idx is not None:
                    row = filtered_df.loc[payment_idx]
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ حذف الدفعة"):
                            db.delete_payment(payment_idx)
                            st.success("تم حذف الدفعة")
                            time.sleep(1)
                            st.rerun()
                    with col2:
                        with st.expander("تعديل الدفعة"):
                            with st.form("edit_payment_form"):
                                new_amount = st.number_input("المبلغ", value=float(row["amount"]))
                                new_method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"],
                                    index=["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"].index(row["payment_method"]))
                                new_date = st.date_input("تاريخ الدفع", value=pd.to_datetime(row["payment_date"]).date())
                                new_notes = st.text_area("ملاحظات", value=row.get("notes", ""))
                                if st.form_submit_button("تحديث الدفعة"):
                                    updates = {"amount": new_amount, "payment_method": new_method,
                                              "payment_date": str(new_date), "notes": new_notes}
                                    db.update_payment(payment_idx, updates)
                                    st.success("تم تحديث الدفعة")
                                    time.sleep(1)
                                    st.rerun()
        else:
            st.info("لا توجد مدفوعات مسجلة بعد")

def coach_statistics_page():
    st.header("📊 الإحصائيات والتقارير")
    db = GoogleSheetsDB()
    players = db.get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون بعد")
        return
    tab1, tab2, tab3 = st.tabs(["📈 إحصائيات الحضور", "💰 التحليل المالي", "📋 تقارير شاملة"])
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
        ws_subs = db.get_subscriptions_sheet()
        subs_data = ws_subs.get_all_records()
        if subs_data:
            subs_df = pd.DataFrame(subs_data)
            active_subs = subs_df[subs_df["subscription_status"] == "نشط"]
            total_monthly = active_subs["monthly_fee"].sum() if not active_subs.empty else 0
            payments_df = db.get_all_payments()
            if not payments_df.empty:
                total_paid = payments_df["amount"].sum()
                payments_df["month"] = pd.to_datetime(payments_df["payment_date"]).dt.to_period("M").astype(str)
                monthly_payments = payments_df.groupby("month")["amount"].sum().reset_index()
                col1, col2, col3 = st.columns(3)
                col1.metric("💰 الدخل الشهري المتوقع", f"{total_monthly:,.0f} ج.م")
                col2.metric("💵 إجمالي المدفوعات المستلمة", f"{total_paid:,.0f} ج.م")
                collection_rate = (total_paid / (total_monthly * max(1, len(monthly_payments)))) * 100 if total_monthly > 0 else 0
                col3.metric("📊 نسبة التحصيل", f"{collection_rate:.1f}%")
                fig = px.bar(monthly_payments, x="month", y="amount", title="المدفوعات الشهرية")
                st.plotly_chart(fig, use_container_width=True)
                method_counts = payments_df["payment_method"].value_counts()
                fig2 = px.pie(values=method_counts.values, names=method_counts.index, title="توزيع طرق الدفع")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("لا توجد مدفوعات مسجلة")
        else:
            st.info("لا توجد اشتراكات مسجلة")
    with tab3:
        st.subheader("تقارير شاملة")
        report_data = []
        for player in players:
            att_df = db.get_attendance_for_player(player)
            total_att = len(att_df)
            present = len(att_df[att_df["status"] == "Present"]) if not att_df.empty else 0
            att_rate = (present / total_att * 100) if total_att > 0 else 0
            active_sub = db.get_active_subscription(player)
            monthly_fee = active_sub["monthly_fee"] if active_sub else 0
            pay_df = db.get_player_payments(player)
            total_paid = pay_df["amount"].sum() if not pay_df.empty else 0
            report_data.append({
                "اللاعب": player,
                "نسبة الحضور": f"{att_rate:.1f}%",
                "الاشتراك الشهري": monthly_fee,
                "إجمالي المدفوع": total_paid,
                "عدد مرات الغياب": total_att - present
            })
        if report_data:
            report_df = pd.DataFrame(report_data)
            st.dataframe(report_df, use_container_width=True)
            csv = report_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تحميل التقرير كملف CSV", data=csv,
                              file_name=f"تقرير_الكوتش_أكاديمي_{date.today()}.csv", mime="text/csv")

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
        current_password = st.text_input("كلمة المرور الحالية", type="password")
        new_password = st.text_input("كلمة المرور الجديدة", type="password")
        confirm_password = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        if st.form_submit_button("تحديث كلمة المرور"):
            if new_password != confirm_password:
                st.error("كلمة المرور الجديدة غير متطابقة")
            elif len(new_password) < 4:
                st.error("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            else:
                db = GoogleSheetsDB()
                user = db.authenticate_user(st.session_state.username, current_password)
                if user:
                    if db.update_user_password(st.session_state.username, new_password):
                        st.success("تم تحديث كلمة المرور بنجاح")
                    else:
                        st.error("فشل تحديث كلمة المرور")
                else:
                    st.error("كلمة المرور الحالية غير صحيحة")

# ---------- صفحات اللاعب ----------
def player_sidebar():
    with st.sidebar:
        st.markdown(f"<h3>👋 مرحباً<br>{st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        menu = {
            "📊 لوحة المعلومات": "dashboard",
            "📅 سجل الحضور": "attendance_history",
            "💰 الاشتراك والمدفوعات": "financial",
            "⚙️ إعدادات الحساب": "settings"
        }
        selected = st.radio("القائمة", list(menu.keys()))
        current_page = menu[selected]
        st.markdown("---")
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            SessionManager.logout()
            st.rerun()
        return current_page

def player_dashboard_page():
    st.header("📊 لوحة المعلومات")
    db = GoogleSheetsDB()
    player_name = st.session_state.username
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📅 ملخص الحضور")
        att_df = db.get_attendance_for_player(player_name)
        if not att_df.empty:
            total_days = len(att_df)
            present_days = len(att_df[att_df["status"] == "Present"])
            absent_days = total_days - present_days
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
            st.metric("إجمالي الأيام", total_days)
            st.metric("أيام الحضور", present_days)
            st.metric("أيام الغياب", absent_days)
            st.metric("نسبة الحضور", f"{attendance_rate:.1f}%")
            fig = go.Figure(data=[go.Pie(labels=["حاضر", "غائب"], values=[present_days, absent_days],
                                        hole=.3, marker_colors=["#2e7d32", "#d32f2f"])])
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور بعد")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("💰 ملخص الاشتراك")
        active_sub = db.get_active_subscription(player_name)
        if active_sub:
            st.markdown(f"""
            - **الرسوم الشهرية:** {active_sub['monthly_fee']} ج.م
            - **تاريخ البداية:** {active_sub['start_date']}
            - **تاريخ النهاية:** {active_sub['end_date']}
            - **الحالة:** {active_sub['subscription_status']}
            """)
            pay_df = db.get_player_payments(player_name)
            total_paid = pay_df["amount"].sum() if not pay_df.empty else 0
            start = pd.to_datetime(active_sub['start_date'])
            end = pd.to_datetime(active_sub['end_date'])
            months = ((end.year - start.year) * 12 + end.month - start.month) + 1
            total_due = active_sub['monthly_fee'] * months
            remaining = total_due - total_paid
            st.metric("إجمالي المدفوع", f"{total_paid:,.0f} ج.م")
            st.metric("المبلغ المستحق", f"{total_due:,.0f} ج.م")
            st.metric("المتبقي", f"{remaining:,.0f} ج.م", delta_color="inverse")
            progress = min(total_paid / total_due, 1.0) if total_due > 0 else 0
            st.progress(progress, text=f"نسبة السداد: {progress*100:.1f}%")
        else:
            st.warning("لا يوجد اشتراك نشط حالياً")
        st.markdown("</div>", unsafe_allow_html=True)

def player_attendance_history_page():
    st.header("📅 سجل الحضور والغياب")
    db = GoogleSheetsDB()
    att_df = db.get_attendance_for_player(st.session_state.username)
    if not att_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("من تاريخ", value=pd.to_datetime(att_df["date"].min()).date())
        with col2:
            end_date = st.date_input("إلى تاريخ", value=date.today())
        att_df["date_parsed"] = pd.to_datetime(att_df["date"]).dt.date
        filtered = att_df[(att_df["date_parsed"] >= start_date) & (att_df["date_parsed"] <= end_date)]
        if not filtered.empty:
            st.dataframe(filtered[["date", "status", "recorded_at"]].sort_values("date", ascending=False), use_container_width=True)
            total = len(filtered)
            present = len(filtered[filtered["status"] == "Present"])
            absent = total - present
            rate = (present / total * 100) if total > 0 else 0
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("إجمالي الأيام", total)
            col2.metric("حاضر", present)
            col3.metric("غائب", absent)
            col4.metric("نسبة الحضور", f"{rate:.1f}%")
            daily = filtered.groupby("date").agg({"status": lambda x: (x == "Present").sum()}).reset_index()
            daily.columns = ["date", "present"]
            daily["rate"] = daily["present"] * 100
            fig = px.line(daily, x="date", y="rate", title="نسبة حضورك خلال الفترة")
            fig.update_yaxes(tickvals=[0, 100], ticktext=["غائب", "حاضر"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد بيانات في الفترة المحددة")
    else:
        st.info("لا توجد بيانات حضور حتى الآن")

def player_financial_page():
    st.header("💰 الاشتراك والمدفوعات")
    db = GoogleSheetsDB()
    player_name = st.session_state.username
    tab1, tab2 = st.tabs(["📋 الاشتراكات", "💵 سجل المدفوعات"])
    with tab1:
        st.subheader("الاشتراكات المسجلة")
        subs_df = db.get_player_subscriptions(player_name)
        if not subs_df.empty:
            st.dataframe(subs_df, use_container_width=True)
            if not subs_df[subs_df["subscription_status"] == "نشط"].empty:
                st.success("✅ لديك اشتراك نشط حالياً")
            else:
                st.warning("⚠️ لا يوجد اشتراك نشط حالياً")
        else:
            st.info("لا توجد اشتراكات مسجلة")
    with tab2:
        st.subheader("سجل المدفوعات")
        pay_df = db.get_player_payments(player_name)
        if not pay_df.empty:
            total_paid = pay_df["amount"].sum()
            st.metric("💵 إجمالي المدفوعات", f"{total_paid:,.0f} ج.م")
            st.dataframe(pay_df[["amount", "payment_method", "payment_date", "notes"]].sort_values("payment_date", ascending=False),
                        use_container_width=True)
            pay_df["payment_date"] = pd.to_datetime(pay_df["payment_date"])
            pay_df["month"] = pay_df["payment_date"].dt.to_period("M").astype(str)
            monthly = pay_df.groupby("month")["amount"].sum().reset_index()
            fig = px.bar(monthly, x="month", y="amount", title="مدفوعاتك الشهرية")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("لا توجد مدفوعات مسجلة")

def player_settings_page():
    st.header("⚙️ إعدادات الحساب")
    st.subheader("تغيير كلمة المرور")
    with st.form("player_change_password"):
        current = st.text_input("كلمة المرور الحالية", type="password")
        new_pass = st.text_input("كلمة المرور الجديدة", type="password")
        confirm = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        if st.form_submit_button("تحديث كلمة المرور"):
            if new_pass != confirm:
                st.error("كلمة المرور الجديدة غير متطابقة")
            elif len(new_pass) < 4:
                st.error("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            else:
                db = GoogleSheetsDB()
                user = db.authenticate_user(st.session_state.username, current)
                if user:
                    if db.update_user_password(st.session_state.username, new_pass):
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
            current_page = coach_sidebar()
            if current_page == "attendance":
                coach_attendance_page()
            elif current_page == "subscriptions":
                coach_subscriptions_page()
            elif current_page == "payments":
                coach_payments_page()
            elif current_page == "statistics":
                coach_statistics_page()
            elif current_page == "players":
                coach_players_page()
            elif current_page == "settings":
                coach_settings_page()
        else:
            current_page = player_sidebar()
            if current_page == "dashboard":
                player_dashboard_page()
            elif current_page == "attendance_history":
                player_attendance_history_page()
            elif current_page == "financial":
                player_financial_page()
            elif current_page == "settings":
                player_settings_page()

if __name__ == "__main__":
    main()
