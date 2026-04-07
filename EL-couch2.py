import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import hashlib
import json
import base64
import random
from typing import List, Dict, Any, Optional, Tuple

# ========================= إعدادات التطبيق =========================
APP_TITLE = "⚽ الكوتش أكاديمي - نظام إدارة أكاديمية كرة القدم"
APP_ICON = "⚽"
LAYOUT = "wide"
SIDEBAR_STATE = "auto"

# أسماء الأوراق في Google Sheets
SHEET_USERS = "Users"
SHEET_ATTENDANCE = "Attendance"
SHEET_SUBSCRIPTIONS = "Subscriptions"
SHEET_PAYMENTS = "Payments"
SHEET_ACTIVITY_LOG = "ActivityLog"
SHEET_SESSIONS = "Sessions"

# أعمدة الأوراق
USERS_COLUMNS = ["username", "password_hash", "role", "full_name", "phone", "email", "join_date", "is_active", "last_login"]
ATTENDANCE_COLUMNS = ["player_name", "date", "status", "recorded_by", "recorded_at", "session_type", "notes"]
SUBSCRIPTIONS_COLUMNS = ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status", "last_updated", "discount", "total_paid_to_date"]
PAYMENTS_COLUMNS = ["player_name", "amount", "payment_method", "payment_date", "notes", "recorded_by", "receipt_id"]
ACTIVITY_LOG_COLUMNS = ["timestamp", "username", "action", "details"]
SESSIONS_COLUMNS = ["session_id", "username", "login_time", "expiry_time", "is_active"]

# قوائم الخيارات
PAYMENT_METHODS = ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"]
SUBSCRIPTION_STATUSES = ["Active", "Expired", "Cancelled", "Pending"]
ATTENDANCE_STATUSES = ["Present", "Absent", "Late", "Excused"]
SESSION_TYPES = ["Training", "Match", "Fitness", "Tactical"]

# إعدادات الجلسة
SESSION_EXPIRY_HOURS = 24

# ========================= دوال مساعدة عامة =========================
def hash_password(password: str) -> str:
    """تشفير كلمة المرور باستخدام SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def validate_three_part_name(name: str) -> bool:
    if not name or not isinstance(name, str):
        return False
    parts = re.split(r'\s+', name.strip())
    return len(parts) >= 3

def format_arabic_date(date_obj=None):
    if date_obj is None:
        date_obj = datetime.now()
    return date_obj.strftime("%Y-%m-%d %H:%M:%S")

def generate_receipt_id() -> str:
    return f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"

def calculate_attendance_rate(attendance_records: List[Dict]) -> Tuple[float, int, int, int]:
    if not attendance_records:
        return 0.0, 0, 0, 0
    total = len(attendance_records)
    present = sum(1 for r in attendance_records if r.get('status') == 'Present')
    late = sum(1 for r in attendance_records if r.get('status') == 'Late')
    absent = sum(1 for r in attendance_records if r.get('status') == 'Absent')
    rate = (present / total) * 100 if total > 0 else 0
    return round(rate, 2), present, absent, late

def calculate_remaining_fee(subscription: Optional[Dict], total_paid: float) -> float:
    if not subscription:
        return 0.0
    try:
        monthly_fee = float(subscription['monthly_fee'])
        discount = float(subscription.get('discount', 0))
        effective_fee = monthly_fee - discount
        start = datetime.strptime(subscription['start_date'], "%Y-%m-%d")
        end = datetime.strptime(subscription['end_date'], "%Y-%m-%d")
        months = max(1, (end.year - start.year) * 12 + (end.month - start.month))
        total_fee = effective_fee * months
        remaining = total_fee - total_paid
        return max(0, remaining)
    except:
        return max(0, monthly_fee - total_paid)

def log_activity(sheets_mgr, username: str, action: str, details: str = ""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheets_mgr.append_to_sheet(SHEET_ACTIVITY_LOG, [timestamp, username, action, details])

def create_download_link(df: pd.DataFrame, filename: str = "data.csv") -> str:
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 تحميل الملف</a>'
    return href

# ========================= إدارة Google Sheets باستخدام secrets =========================
class SheetsManager:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = 30

    def connect(self) -> bool:
        """الاتصال بـ Google Sheets باستخدام st.secrets"""
        try:
            # قراءة بيانات حساب الخدمة من secrets
            if "gcp_service_account" not in st.secrets:
                st.error("لم يتم العثور على secrets 'gcp_service_account'")
                return False
            creds_dict = dict(st.secrets["gcp_service_account"])
            # معالجة private_key (قد تحتوي على \n)
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            return True
        except Exception as e:
            st.error(f"❌ فشل الاتصال بـ Google Sheets: {str(e)}")
            return False

    def setup_spreadsheet(self, spreadsheet_name: str = "الكوتش أكاديمي") -> bool:
        if not self.client and not self.connect():
            raise Exception("لا يمكن الاتصال بـ Google Sheets")
        try:
            self.spreadsheet = self.client.open(spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            self.spreadsheet = self.client.create(spreadsheet_name)
            self.spreadsheet.share(self.client.auth.service_account_email, perm_type='user', role='writer')
        # إنشاء الأوراق
        self._ensure_sheet(SHEET_USERS, USERS_COLUMNS)
        self._ensure_sheet(SHEET_ATTENDANCE, ATTENDANCE_COLUMNS)
        self._ensure_sheet(SHEET_SUBSCRIPTIONS, SUBSCRIPTIONS_COLUMNS)
        self._ensure_sheet(SHEET_PAYMENTS, PAYMENTS_COLUMNS)
        self._ensure_sheet(SHEET_ACTIVITY_LOG, ACTIVITY_LOG_COLUMNS)
        self._ensure_sheet(SHEET_SESSIONS, SESSIONS_COLUMNS)
        self._add_default_coach()
        return True

    def _ensure_sheet(self, sheet_name: str, headers: List[str]):
        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
            if not sheet.row_values(1):
                sheet.append_row(headers)
        except gspread.WorksheetNotFound:
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
            sheet.append_row(headers)

    def _add_default_coach(self):
        users = self.get_all_users(use_cache=False)
        if not any(u.get('role') == 'coach' for u in users):
            self.add_user("كابتن الأكاديمية", "coach123", "coach", "كابتن الأكاديمية", "01000000000", "coach@academy.com")

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache_time:
            return False
        return (datetime.now() - self._cache_time[key]).seconds < self.cache_ttl

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = value
        self._cache_time[key] = datetime.now()

    # ----------------- دوال المستخدمين -----------------
    def get_all_users(self, use_cache: bool = True) -> List[Dict]:
        if use_cache and 'users' in self._cache and self._is_cache_valid('users'):
            return self._cache['users']
        try:
            sheet = self.spreadsheet.worksheet(SHEET_USERS)
            records = sheet.get_all_records()
            self._set_cache('users', records)
            return records
        except:
            return []

    def get_user(self, username: str) -> Optional[Dict]:
        users = self.get_all_users()
        for u in users:
            if u.get('username') == username:
                return u
        return None

    def username_exists(self, username: str) -> bool:
        return self.get_user(username) is not None

    def add_user(self, username: str, password: str, role: str, full_name: str = "", phone: str = "", email: str = "") -> Tuple[bool, str]:
        if self.username_exists(username):
            return False, "اسم المستخدم موجود بالفعل"
        if role == "player" and not validate_three_part_name(username):
            return False, "اسم اللاعب يجب أن يكون ثلاثيًا (مثال: أحمد محمد علي)"
        password_hash = hash_password(password)
        join_date = datetime.now().strftime("%Y-%m-%d")
        try:
            sheet = self.spreadsheet.worksheet(SHEET_USERS)
            sheet.append_row([username, password_hash, role, full_name or username, phone, email, join_date, "True", ""])
            self._set_cache('users', self.get_all_users(use_cache=False))
            log_activity(self, "system", "إضافة مستخدم", f"تم إضافة {role}: {username}")
            return True, "تمت إضافة المستخدم بنجاح"
        except Exception as e:
            return False, f"خطأ: {e}"

    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str]:
        user = self.get_user(username)
        if not user:
            return False, "اسم المستخدم غير موجود"
        if user.get('is_active') != "True":
            return False, "الحساب معطل، يرجى التواصل مع الكابتن"
        if verify_password(password, user['password_hash']):
            self.update_user_field(username, "last_login", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            log_activity(self, username, "تسجيل دخول", "ناجح")
            return True, user['role']
        else:
            log_activity(self, username, "تسجيل دخول", "فشل - كلمة مرور خاطئة")
            return False, "كلمة المرور غير صحيحة"

    def update_user_field(self, username: str, field: str, new_value: str) -> bool:
        try:
            sheet = self.spreadsheet.worksheet(SHEET_USERS)
            all_vals = sheet.get_all_values()
            header = all_vals[0]
            if field not in header:
                return False
            col_idx = header.index(field) + 1
            for i, row in enumerate(all_vals[1:], start=2):
                if row[0] == username:
                    sheet.update_cell(i, col_idx, new_value)
                    self._set_cache('users', self.get_all_users(use_cache=False))
                    return True
            return False
        except:
            return False

    # ----------------- دوال الحضور -----------------
    def record_attendance(self, player_name: str, status: str, recorded_by: str, session_type: str = "Training", notes: str = "") -> bool:
        date = datetime.now().strftime("%Y-%m-%d")
        recorded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            sheet = self.spreadsheet.worksheet(SHEET_ATTENDANCE)
            sheet.append_row([player_name, date, status, recorded_by, recorded_at, session_type, notes])
            if 'attendance' in self._cache:
                del self._cache['attendance']
            log_activity(self, recorded_by, "تسجيل حضور", f"{player_name} - {status}")
            return True
        except:
            return False

    def get_all_attendance(self, use_cache: bool = True) -> List[Dict]:
        if use_cache and 'attendance' in self._cache and self._is_cache_valid('attendance'):
            return self._cache['attendance']
        try:
            sheet = self.spreadsheet.worksheet(SHEET_ATTENDANCE)
            recs = sheet.get_all_records()
            self._set_cache('attendance', recs)
            return recs
        except:
            return []

    def get_player_attendance(self, player_name: str) -> List[Dict]:
        all_rec = self.get_all_attendance()
        return [r for r in all_rec if r.get('player_name') == player_name]

    def get_attendance_summary(self) -> pd.DataFrame:
        recs = self.get_all_attendance()
        if not recs:
            return pd.DataFrame()
        df = pd.DataFrame(recs)
        if df.empty:
            return pd.DataFrame()
        summary = df.groupby('player_name').agg(
            total_days=('status', 'count'),
            present=('status', lambda x: (x == 'Present').sum()),
            absent=('status', lambda x: (x == 'Absent').sum()),
            late=('status', lambda x: (x == 'Late').sum()),
            excused=('status', lambda x: (x == 'Excused').sum())
        ).reset_index()
        summary['attendance_rate'] = (summary['present'] / summary['total_days'] * 100).round(2)
        return summary

    # ----------------- دوال الاشتراكات -----------------
    def get_subscription(self, player_name: str) -> Optional[Dict]:
        try:
            sheet = self.spreadsheet.worksheet(SHEET_SUBSCRIPTIONS)
            recs = sheet.get_all_records()
            for r in recs:
                if r.get('player_name') == player_name:
                    return r
            return None
        except:
            return None

    def update_subscription(self, player_name: str, monthly_fee: float, start_date: str, end_date: str, status: str, discount: float = 0) -> bool:
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            sheet = self.spreadsheet.worksheet(SHEET_SUBSCRIPTIONS)
            all_vals = sheet.get_all_values()
            updated = False
            for i, row in enumerate(all_vals[1:], start=2):
                if row[0] == player_name:
                    sheet.update(f'A{i}:G{i}', [[player_name, monthly_fee, start_date, end_date, status, last_updated, discount]])
                    updated = True
                    break
            if not updated:
                sheet.append_row([player_name, monthly_fee, start_date, end_date, status, last_updated, discount, 0])
            if 'subscriptions' in self._cache:
                del self._cache['subscriptions']
            log_activity(self, st.session_state.get('username', 'system'), "تحديث اشتراك", f"{player_name} - {status}")
            return True
        except:
            return False

    def get_all_subscriptions(self) -> List[Dict]:
        try:
            sheet = self.spreadsheet.worksheet(SHEET_SUBSCRIPTIONS)
            return sheet.get_all_records()
        except:
            return []

    def get_expiring_subscriptions(self, days_threshold: int = 7) -> List[Dict]:
        subs = self.get_all_subscriptions()
        expiring = []
        today = datetime.now().date()
        for s in subs:
            try:
                end_date = datetime.strptime(s['end_date'], "%Y-%m-%d").date()
                days_left = (end_date - today).days
                if 0 <= days_left <= days_threshold and s['subscription_status'] == 'Active':
                    expiring.append(s)
            except:
                continue
        return expiring

    # ----------------- دوال المدفوعات -----------------
    def add_payment(self, player_name: str, amount: float, payment_method: str, notes: str, recorded_by: str) -> Tuple[bool, str]:
        payment_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        receipt_id = generate_receipt_id()
        try:
            sheet = self.spreadsheet.worksheet(SHEET_PAYMENTS)
            sheet.append_row([player_name, amount, payment_method, payment_date, notes, recorded_by, receipt_id])
            if 'payments' in self._cache:
                del self._cache['payments']
            log_activity(self, recorded_by, "تسجيل دفعة", f"{player_name} - {amount} جنيه - {payment_method}")
            return True, receipt_id
        except:
            return False, ""

    def get_player_payments(self, player_name: str) -> List[Dict]:
        all_p = self.get_all_payments()
        return [p for p in all_p if p.get('player_name') == player_name]

    def get_all_payments(self, use_cache: bool = True) -> List[Dict]:
        if use_cache and 'payments' in self._cache and self._is_cache_valid('payments'):
            return self._cache['payments']
        try:
            sheet = self.spreadsheet.worksheet(SHEET_PAYMENTS)
            recs = sheet.get_all_records()
            self._set_cache('payments', recs)
            return recs
        except:
            return []

    def get_player_payment_summary(self, player_name: str) -> Tuple[float, float]:
        payments = self.get_player_payments(player_name)
        total_paid = sum(float(p['amount']) for p in payments)
        sub = self.get_subscription(player_name)
        remaining = calculate_remaining_fee(sub, total_paid)
        return total_paid, remaining

    # ----------------- دوال الجلسات -----------------
    def create_session(self, username: str) -> str:
        session_id = hashlib.sha256(f"{username}{datetime.now()}{random.random()}".encode()).hexdigest()[:16]
        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        expiry_time = (datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
        self.append_to_sheet(SHEET_SESSIONS, [session_id, username, login_time, expiry_time, "True"])
        return session_id

    def is_session_valid(self, username: str, session_id: str) -> bool:
        try:
            sheet = self.spreadsheet.worksheet(SHEET_SESSIONS)
            recs = sheet.get_all_records()
            for r in recs:
                if r.get('username') == username and r.get('session_id') == session_id and r.get('is_active') == "True":
                    expiry = datetime.strptime(r['expiry_time'], "%Y-%m-%d %H:%M:%S")
                    if expiry > datetime.now():
                        return True
                    else:
                        self.end_session(session_id)
                        return False
            return True  # افتراضي
        except:
            return True

    def end_session(self, session_id: str):
        try:
            sheet = self.spreadsheet.worksheet(SHEET_SESSIONS)
            all_vals = sheet.get_all_values()
            for i, row in enumerate(all_vals[1:], start=2):
                if row[0] == session_id:
                    sheet.update_cell(i, 5, "False")
                    break
        except:
            pass

    # ----------------- دوال عامة -----------------
    def append_to_sheet(self, sheet_name: str, row_data: List):
        try:
            sheet = self.spreadsheet.worksheet(sheet_name)
            sheet.append_row(row_data)
        except:
            pass

    def clear_cache(self):
        self._cache = {}
        self._cache_time = {}

# ========================= إدارة الجلسات في Streamlit =========================
def init_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'session_id' not in st.session_state:
        st.session_state.session_id = None

def logout(sheets_mgr):
    if st.session_state.get('session_id'):
        sheets_mgr.end_session(st.session_state.session_id)
    log_activity(sheets_mgr, st.session_state.username, "تسجيل خروج", "")
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.session_id = None

# ========================= لوحة تحكم الكابتن =========================
def show_coach_dashboard(sheets_mgr):
    st.markdown("# 🧑‍🏫 لوحة تحكم الكابتن - أكاديمية الكوتش")
    st.markdown("---")
    
    users = sheets_mgr.get_all_users()
    players = [u for u in users if u['role'] == 'player']
    player_names = [p['username'] for p in players if p.get('is_active') != 'False']
    total_revenue = sum(float(p['amount']) for p in sheets_mgr.get_all_payments())
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 إجمالي اللاعبين", len(players))
    col2.metric("✅ نشطين", len(player_names))
    col3.metric("💰 إجمالي الإيرادات", f"{total_revenue:,.0f} جنيه")
    col4.metric("📅 اشتراكات منتهية قريبًا", len(sheets_mgr.get_expiring_subscriptions()))
    
    st.markdown("---")
    tabs = st.tabs(["📋 تسجيل الحضور", "📊 التقارير", "💰 الاشتراكات", "💵 المدفوعات", "👥 إدارة اللاعبين", "📜 سجل النشاطات"])
    
    # تبويب الحضور
    with tabs[0]:
        st.header("تسجيل الحضور - متعدد")
        if not player_names:
            st.warning("لا يوجد لاعبون")
        else:
            selected = st.multiselect("اختر اللاعبين", player_names)
            session_type = st.selectbox("نوع الجلسة", SESSION_TYPES)
            notes = st.text_area("ملاحظات")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("✅ حضور"):
                    for p in selected:
                        sheets_mgr.record_attendance(p, "Present", st.session_state.username, session_type, notes)
                    st.success(f"تم تسجيل حضور {len(selected)} لاعب")
                    st.rerun()
            with col2:
                if st.button("❌ غياب"):
                    for p in selected:
                        sheets_mgr.record_attendance(p, "Absent", st.session_state.username, session_type, notes)
                    st.success(f"تم تسجيل غياب {len(selected)} لاعب")
                    st.rerun()
            with col3:
                if st.button("⏰ تأخر"):
                    for p in selected:
                        sheets_mgr.record_attendance(p, "Late", st.session_state.username, session_type, notes)
                    st.success(f"تم تسجيل تأخر {len(selected)} لاعب")
                    st.rerun()
            with col4:
                if st.button("🔵 معذور"):
                    for p in selected:
                        sheets_mgr.record_attendance(p, "Excused", st.session_state.username, session_type, notes)
                    st.success(f"تم تسجيل عذر {len(selected)} لاعب")
                    st.rerun()
            st.subheader("آخر السجلات")
            att = sheets_mgr.get_all_attendance()
            if att:
                st.dataframe(pd.DataFrame(att).tail(30), use_container_width=True)
    
    # تبويب التقارير
    with tabs[1]:
        st.header("التقارير والإحصائيات")
        report_type = st.selectbox("نوع التقرير", ["نسبة الحضور", "توزيع الحضور", "المدفوعات الشهرية"])
        if report_type == "نسبة الحضور":
            summary = sheets_mgr.get_attendance_summary()
            if not summary.empty:
                fig = px.bar(summary, x='player_name', y='attendance_rate', title="نسبة الحضور", text='attendance_rate')
                st.plotly_chart(fig)
                st.dataframe(summary)
        elif report_type == "توزيع الحضور":
            att = sheets_mgr.get_all_attendance()
            if att:
                df = pd.DataFrame(att)
                status_counts = df['status'].value_counts().reset_index()
                status_counts.columns = ['الحالة', 'العدد']
                fig = px.pie(status_counts, values='العدد', names='الحالة', title="توزيع الحضور")
                st.plotly_chart(fig)
        else:
            payments = sheets_mgr.get_all_payments()
            if payments:
                df_pay = pd.DataFrame(payments)
                df_pay['payment_date'] = pd.to_datetime(df_pay['payment_date'])
                df_pay['month'] = df_pay['payment_date'].dt.strftime('%Y-%m')
                monthly = df_pay.groupby('month')['amount'].sum().reset_index()
                fig = px.line(monthly, x='month', y='amount', title="الإيرادات الشهرية", markers=True)
                st.plotly_chart(fig)
    
    # تبويب الاشتراكات
    with tabs[2]:
        st.header("إدارة الاشتراكات")
        player_sel = st.selectbox("اختر اللاعب", player_names, key="sub_sel")
        if player_sel:
            sub = sheets_mgr.get_subscription(player_sel)
            with st.form("sub_form"):
                col1, col2 = st.columns(2)
                with col1:
                    fee = st.number_input("القيمة الشهرية", value=float(sub['monthly_fee']) if sub else 500.0, step=50.0)
                    discount = st.number_input("خصم", value=float(sub.get('discount', 0)) if sub else 0.0, step=10.0)
                with col2:
                    start = st.date_input("تاريخ البداية", value=datetime.strptime(sub['start_date'], "%Y-%m-%d") if sub and sub.get('start_date') else datetime.now())
                    end = st.date_input("تاريخ النهاية", value=datetime.strptime(sub['end_date'], "%Y-%m-%d") if sub and sub.get('end_date') else datetime.now() + timedelta(days=30))
                status = st.selectbox("الحالة", SUBSCRIPTION_STATUSES, index=SUBSCRIPTION_STATUSES.index(sub['subscription_status']) if sub and sub.get('subscription_status') in SUBSCRIPTION_STATUSES else 0)
                if st.form_submit_button("حفظ"):
                    sheets_mgr.update_subscription(player_sel, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status, discount)
                    st.success("تم الحفظ")
                    st.rerun()
        st.subheader("جميع الاشتراكات")
        subs_df = pd.DataFrame(sheets_mgr.get_all_subscriptions())
        if not subs_df.empty:
            st.dataframe(subs_df)
    
    # تبويب المدفوعات
    with tabs[3]:
        st.header("تسجيل دفعات")
        player_pay = st.selectbox("اختر اللاعب", player_names, key="pay_sel")
        if player_pay:
            with st.form("pay_form"):
                amount = st.number_input("المبلغ", min_value=0.0, step=10.0)
                method = st.selectbox("طريقة الدفع", PAYMENT_METHODS)
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("تسجيل"):
                    success, receipt = sheets_mgr.add_payment(player_pay, amount, method, notes, st.session_state.username)
                    if success:
                        st.success(f"تم تسجيل {amount} جنيه - إيصال: {receipt}")
                        st.rerun()
            payments = sheets_mgr.get_player_payments(player_pay)
            if payments:
                st.dataframe(pd.DataFrame(payments))
                total_paid, remaining = sheets_mgr.get_player_payment_summary(player_pay)
                col1, col2 = st.columns(2)
                col1.metric("إجمالي المدفوع", f"{total_paid} جنيه")
                col2.metric("المتبقي", f"{remaining} جنيه")
    
    # تبويب إدارة اللاعبين
    with tabs[4]:
        st.header("إدارة اللاعبين")
        tab_add, tab_list = st.tabs(["إضافة لاعب", "قائمة اللاعبين"])
        with tab_add:
            with st.form("add_player"):
                new_name = st.text_input("الاسم الثلاثي")
                new_pass = st.text_input("كلمة المرور", type="password")
                phone = st.text_input("الهاتف")
                email = st.text_input("البريد")
                if st.form_submit_button("تسجيل"):
                    if not validate_three_part_name(new_name):
                        st.error("الاسم يجب أن يكون ثلاثيًا")
                    else:
                        success, msg = sheets_mgr.add_user(new_name, new_pass, "player", new_name, phone, email)
                        if success:
                            st.success(msg)
                            sheets_mgr.update_subscription(new_name, 500, datetime.now().strftime("%Y-%m-%d"), (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d"), "Active")
                        else:
                            st.error(msg)
        with tab_list:
            players_df = pd.DataFrame([u for u in sheets_mgr.get_all_users() if u['role'] == 'player'])
            if not players_df.empty:
                st.dataframe(players_df[['username', 'full_name', 'phone', 'email', 'is_active']])
                st.markdown(create_download_link(players_df, "players.csv"), unsafe_allow_html=True)
    
    # تبويب سجل النشاطات
    with tabs[5]:
        st.header("سجل النشاطات")
        try:
            sheet = sheets_mgr.spreadsheet.worksheet(SHEET_ACTIVITY_LOG)
            logs = sheet.get_all_records()
            if logs:
                st.dataframe(pd.DataFrame(logs).tail(100))
            else:
                st.info("لا توجد سجلات")
        except:
            st.info("لا توجد سجلات")

# ========================= صفحة اللاعب =========================
def show_player_dashboard(sheets_mgr):
    player = st.session_state.username
    st.markdown(f"# 👋 مرحباً {player}")
    st.markdown("---")
    
    attendance = sheets_mgr.get_player_attendance(player)
    sub = sheets_mgr.get_subscription(player)
    payments = sheets_mgr.get_player_payments(player)
    total_paid, remaining = sheets_mgr.get_player_payment_summary(player)
    rate, present, absent, late = calculate_attendance_rate(attendance)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📊 نسبة الحضور", f"{rate}%")
    col2.metric("✅ حضور", present)
    col3.metric("❌ غياب", absent)
    col4.metric("⏰ تأخر", late)
    col5.metric("💰 المدفوع", f"{total_paid} جنيه")
    
    if sub:
        st.info(f"📅 الاشتراك: {sub['monthly_fee']} جنيه/شهر - الحالة: {sub['subscription_status']} - ينتهي {sub['end_date']}")
    else:
        st.warning("لا يوجد اشتراك مسجل")
    
    tabs = st.tabs(["📅 سجل الحضور", "💰 المدفوعات", "📈 إحصائيات"])
    with tabs[0]:
        if attendance:
            df = pd.DataFrame(attendance)
            st.dataframe(df)
            st.markdown(create_download_link(df, f"attendance_{player}.csv"), unsafe_allow_html=True)
        else:
            st.info("لا توجد سجلات")
    with tabs[1]:
        if payments:
            df_pay = pd.DataFrame(payments)
            st.dataframe(df_pay)
            st.metric("المتبقي", f"{remaining} جنيه")
            fig = px.bar(df_pay, x='payment_date', y='amount', title="المدفوعات")
            st.plotly_chart(fig)
        else:
            st.info("لا توجد مدفوعات")
    with tabs[2]:
        if attendance:
            df_att = pd.DataFrame(attendance)
            df_att['date'] = pd.to_datetime(df_att['date'])
            daily = df_att.groupby('date')['status'].apply(lambda x: (x == 'Present').sum() / len(x) * 100).reset_index()
            daily.columns = ['date', 'rate']
            st.line_chart(daily.set_index('date'))

# ========================= التطبيق الرئيسي =========================
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=LAYOUT)
    init_session_state()
    
    try:
        sheets_mgr = SheetsManager()
        sheets_mgr.setup_spreadsheet()
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بـ Google Sheets: {e}")
        st.info("تأكد من وجود secrets 'gcp_service_account' ومشاركة الجدول مع البريد الإلكتروني لحساب الخدمة.")
        st.stop()
    
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/35/35290.png", width=80)
        st.title("⚽ الكوتش أكاديمي")
        if st.session_state.logged_in:
            st.write(f"مرحباً **{st.session_state.username}**")
            if st.button("🚪 تسجيل الخروج"):
                logout(sheets_mgr)
                st.rerun()
        else:
            st.subheader("تسجيل الدخول")
    
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown("## 🔐 دخول")
            username = st.text_input("اسم المستخدم (الاسم الثلاثي)")
            password = st.text_input("كلمة المرور", type="password")
            if st.button("تسجيل الدخول"):
                if not username or not password:
                    st.error("يرجى إدخال البيانات")
                else:
                    success, role = sheets_mgr.authenticate_user(username, password)
                    if success:
                        session_id = sheets_mgr.create_session(username)
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.session_state.session_id = session_id
                        st.success("تم تسجيل الدخول")
                        st.rerun()
                    else:
                        st.error(role)
            st.caption("🔑 كابتن: كابتن الأكاديمية / coach123")
    else:
        # التحقق من صلاحية الجلسة
        if not sheets_mgr.is_session_valid(st.session_state.username, st.session_state.session_id):
            st.warning("انتهت الجلسة، يرجى تسجيل الدخول مجدداً")
            logout(sheets_mgr)
            st.rerun()
        if st.session_state.role == "coach":
            show_coach_dashboard(sheets_mgr)
        elif st.session_state.role == "player":
            show_player_dashboard(sheets_mgr)
        else:
            st.error("دور غير معروف")

if __name__ == "__main__":
    main()
