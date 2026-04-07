import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import re
import hashlib
import random
import extra_streamlit_components as stx
from typing import List, Dict, Any, Optional, Tuple

# ========================= إعدادات التطبيق =========================
st.set_page_config(page_title="أكاديمية الكوتش", page_icon="⚽", layout="wide")

APP_TITLE = "⚽ الكوتش أكاديمي - نظام إدارة الحضور والاشتراكات"

# أسماء الأوراق في Google Sheets
SHEET_USERS = "Users"
SHEET_ATTENDANCE = "Attendance"
SHEET_SUBSCRIPTIONS = "Subscriptions"
SHEET_PAYMENTS = "Payments"
SHEET_SESSIONS = "Sessions"

# أعمدة الأوراق
USERS_COLUMNS = ["username", "password_hash", "role", "full_name", "join_date", "is_active"]
ATTENDANCE_COLUMNS = ["player_name", "date", "status", "recorded_by"]
SUBSCRIPTIONS_COLUMNS = ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status"]
PAYMENTS_COLUMNS = ["player_name", "amount", "payment_method", "payment_date", "notes"]
SESSIONS_COLUMNS = ["session_id", "username", "expiry_time"]

# خيارات طرق الدفع
PAYMENT_METHODS = ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"]
ATTENDANCE_STATUSES = ["Present", "Absent"]

# ========================= دوال مساعدة =========================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def validate_three_part_name(name: str) -> bool:
    if not name or not isinstance(name, str):
        return False
    parts = re.split(r'\s+', name.strip())
    return len(parts) >= 3

def get_cookie_manager():
    if 'cookie_manager' not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager()
    return st.session_state.cookie_manager

# ========================= إدارة Google Sheets =========================
class SheetsManager:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.spreadsheet_id = st.secrets["google"]["spreadsheet_id"]

    def connect(self) -> bool:
        try:
            creds_dict = dict(st.secrets["google"]["service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            return True
        except Exception as e:
            st.error(f"❌ فشل الاتصال بـ Google Sheets: {str(e)}")
            return False

    def setup_sheets(self):
        if not self.client and not self.connect():
            return
        self._ensure_sheet(SHEET_USERS, USERS_COLUMNS)
        self._ensure_sheet(SHEET_ATTENDANCE, ATTENDANCE_COLUMNS)
        self._ensure_sheet(SHEET_SUBSCRIPTIONS, SUBSCRIPTIONS_COLUMNS)
        self._ensure_sheet(SHEET_PAYMENTS, PAYMENTS_COLUMNS)
        self._ensure_sheet(SHEET_SESSIONS, SESSIONS_COLUMNS)
        self._add_default_coach()

    def _ensure_sheet(self, sheet_name: str, headers: List[str]):
        try:
            self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            sheet = self.spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
            sheet.append_row(headers)

    def _add_default_coach(self):
        users = self.get_all_users()
        if not any(u.get('role') == 'coach' for u in users):
            # الكابتن الرئيسي - اسم ثلاثي للموافقة مع الشرط
            self.add_user("كابتن أكاديمية الكوتش", "coach123", "coach", "الكابتن الرئيسي")

    def get_all_users(self) -> List[Dict]:
        if 'users_cache' in st.session_state and (datetime.now() - st.session_state.users_cache_time).seconds < 60:
            return st.session_state.users_cache
        try:
            users = self.spreadsheet.worksheet(SHEET_USERS).get_all_records()
            st.session_state.users_cache = users
            st.session_state.users_cache_time = datetime.now()
            return users
        except: return []

    def add_user(self, username: str, password: str, role: str, full_name: str = "") -> Tuple[bool, str]:
        if any(u.get('username') == username for u in self.get_all_users()):
            return False, "اسم المستخدم موجود بالفعل"
        if not validate_three_part_name(username):
            return False, "الاسم يجب أن يكون ثلاثياً على الأقل"

        pw_hash = hash_password(password)
        join_date = datetime.now().strftime("%Y-%m-%d")
        try:
            self.spreadsheet.worksheet(SHEET_USERS).append_row([username, pw_hash, role, full_name or username, join_date, "True"])
            return True, "تمت إضافة المستخدم بنجاح"
        except Exception as e:
            return False, f"خطأ: {e}"

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        users = self.get_all_users()
        for u in users:
            if u['username'] == username and verify_password(password, str(u['password_hash'])):
                if str(u['is_active']) == "True":
                    return u
        return None

    # ----------------- الحضور -----------------
    def record_attendance_bulk(self, players: List[str], status: str, recorded_by: str):
        date = datetime.now().strftime("%Y-%m-%d")
        rows = [[p, date, status, recorded_by] for p in players]
        self.spreadsheet.worksheet(SHEET_ATTENDANCE).append_rows(rows)

    def get_player_attendance(self, player_name: str) -> List[Dict]:
        all_att = self.spreadsheet.worksheet(SHEET_ATTENDANCE).get_all_records()
        return [a for a in all_att if a['player_name'] == player_name]

    def get_all_attendance(self) -> List[Dict]:
        return self.spreadsheet.worksheet(SHEET_ATTENDANCE).get_all_records()

    # ----------------- الاشتراكات -----------------
    def update_subscription(self, player_name: str, fee: float, start: str, end: str, status: str):
        sheet = self.spreadsheet.worksheet(SHEET_SUBSCRIPTIONS)
        data = sheet.get_all_values()
        for i, row in enumerate(data[1:], start=2):
            if row[0] == player_name:
                sheet.update(f"A{i}:E{i}", [[player_name, fee, start, end, status]])
                return
        sheet.append_row([player_name, fee, start, end, status])

    def get_subscription(self, player_name: str) -> Optional[Dict]:
        subs = self.spreadsheet.worksheet(SHEET_SUBSCRIPTIONS).get_all_records()
        for s in subs:
            if s['player_name'] == player_name:
                return s
        return None

    def get_all_subscriptions(self) -> List[Dict]:
        return self.spreadsheet.worksheet(SHEET_SUBSCRIPTIONS).get_all_records()

    # ----------------- المدفوعات -----------------
    def add_payment(self, player_name: str, amount: float, method: str, notes: str):
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.spreadsheet.worksheet(SHEET_PAYMENTS).append_row([player_name, amount, method, date, notes])

    def get_player_payments(self, player_name: str) -> List[Dict]:
        payments = self.spreadsheet.worksheet(SHEET_PAYMENTS).get_all_records()
        return [p for p in payments if p['player_name'] == player_name]

    def get_all_payments(self) -> List[Dict]:
        return self.spreadsheet.worksheet(SHEET_PAYMENTS).get_all_records()

    # ----------------- الجلسات (Persistent Login) -----------------
    def create_session(self, username: str) -> str:
        session_id = hashlib.sha256(f"{username}{datetime.now()}".encode()).hexdigest()
        expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        self.spreadsheet.worksheet(SHEET_SESSIONS).append_row([session_id, username, expiry])
        return session_id

    def validate_session(self, session_id: str) -> Optional[str]:
        sessions = self.spreadsheet.worksheet(SHEET_SESSIONS).get_all_records()
        for s in sessions:
            if s['session_id'] == session_id:
                expiry = datetime.strptime(s['expiry_time'], "%Y-%m-%d %H:%M:%S")
                if expiry > datetime.now():
                    return s['username']
        return None

    def delete_session(self, session_id: str):
        sheet = self.spreadsheet.worksheet(SHEET_SESSIONS)
        data = sheet.get_all_values()
        for i, row in enumerate(data[1:], start=2):
            if row[0] == session_id:
                sheet.delete_rows(i)
                break

# ========================= واجهة المستخدم =========================

def login_page(mgr: SheetsManager, cookie_mgr):
    st.markdown("<h2 style='text-align: center;'>🔐 تسجيل الدخول</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)")
        password = st.text_input("كلمة المرور", type="password")
        if st.button("دخول", use_container_width=True):
            if not validate_three_part_name(username):
                st.error("❌ يجب إدخال الاسم الثلاثي")
            else:
                user = mgr.authenticate(username, password)
                if user:
                    session_id = mgr.create_session(username)
                    cookie_mgr.set("el_couch_session", session_id, expires_at=datetime.now() + timedelta(days=30))
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")

def coach_dashboard(mgr: SheetsManager):
    st.title("👨‍✈️ لوحة تحكم الكابتن")

    users = mgr.get_all_users()
    players = [u['username'] for u in users if u['role'] == 'player']

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 الحضور", "💰 الاشتراكات والمدفوعات", "📊 الإحصائيات", "👥 إدارة اللاعبين", "📜 سجلات"])

    with tab1:
        st.subheader("تسجيل الحضور الجماعي")
        selected_players = st.multiselect("اختر اللاعبين", players)
        status = st.radio("الحالة", ["Present", "Absent"], horizontal=True)
        if st.button("تسجيل الحضور"):
            if selected_players:
                mgr.record_attendance_bulk(selected_players, status, st.session_state.user['username'])
                st.success(f"تم تسجيل {status} لـ {len(selected_players)} لاعب")
            else:
                st.warning("يرجى اختيار لاعب واحد على الأقل")

    with tab2:
        st.subheader("إدارة المبالغ المالية")
        player = st.selectbox("اختر اللاعب", players, key="pay_player")
        sub_col, pay_col = st.columns(2)

        with sub_col:
            st.markdown("### تحديث الاشتراك")
            sub = mgr.get_subscription(player)
            fee = st.number_input("قيمة الاشتراك الشهري", value=float(sub['monthly_fee']) if sub else 500.0)
            start = st.date_input("تاريخ البداية", value=datetime.strptime(sub['start_date'], "%Y-%m-%d") if sub else datetime.now())
            end = st.date_input("تاريخ النهاية", value=datetime.strptime(sub['end_date'], "%Y-%m-%d") if sub else datetime.now() + timedelta(days=30))
            status_sub = st.selectbox("حالة الاشتراك", ["Active", "Expired", "Pending"], index=0 if not sub or sub['subscription_status']=="Active" else 1)
            if st.button("حفظ الاشتراك"):
                mgr.update_subscription(player, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status_sub)
                st.success("تم تحديث الاشتراك")

        with pay_col:
            st.markdown("### تسجيل دفعة")
            amount = st.number_input("المبلغ المدفوع", min_value=0.0)
            method = st.selectbox("طريقة الدفع", PAYMENT_METHODS)
            notes = st.text_input("ملاحظات")
            if st.button("تسجيل الدفعة"):
                mgr.add_payment(player, amount, method, notes)
                st.success("تم تسجيل الدفعة بنجاح")

    with tab3:
        st.subheader("نظرة عامة")
        all_att = mgr.get_all_attendance()
        if all_att:
            df_att = pd.DataFrame(all_att)
            att_counts = df_att['status'].value_counts().reset_index()
            fig = px.pie(att_counts, values='count', names='status', title="توزيع الحضور والغياب العام")
            st.plotly_chart(fig)

        all_pay = mgr.get_all_payments()
        if all_pay:
            df_pay = pd.DataFrame(all_pay)
            total_revenue = df_pay['amount'].sum()
            st.metric("إجمالي الإيرادات", f"{total_revenue} جنيه")

    with tab4:
        st.subheader("إضافة لاعب جديد")
        with st.form("add_player"):
            new_user = st.text_input("الاسم الثلاثي للاعب")
            new_pass = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("إضافة"):
                if not validate_three_part_name(new_user):
                    st.error("الاسم يجب أن يكون ثلاثياً")
                else:
                    success, msg = mgr.add_user(new_user, new_pass, "player")
                    if success: st.success(msg)
                    else: st.error(msg)

        st.subheader("قائمة المستخدمين")
        st.table(pd.DataFrame(users)[["username", "role", "join_date", "is_active"]])

    with tab5:
        st.subheader("سجل الحضور")
        st.dataframe(pd.DataFrame(mgr.get_all_attendance()))
        st.subheader("سجل المدفوعات")
        st.dataframe(pd.DataFrame(mgr.get_all_payments()))

def player_dashboard(mgr: SheetsManager):
    player_name = st.session_state.user['username']
    st.title(f"👋 أهلاً بك، {player_name}")

    sub = mgr.get_subscription(player_name)
    payments = mgr.get_player_payments(player_name)
    attendance = mgr.get_player_attendance(player_name)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📋 حاله الاشتراك")
        if sub:
            st.write(f"**القيمة:** {sub['monthly_fee']} جنيه")
            st.write(f"**ينتهي في:** {sub['end_date']}")
            st.write(f"**الحالة:** {sub['subscription_status']}")
        else:
            st.warning("لا يوجد اشتراك مسجل")

    with col2:
        st.markdown("### 💰 الموقف المالي")
        total_paid = sum(p['amount'] for p in payments)
        st.write(f"**إجمالي المدفوع:** {total_paid} جنيه")
        if sub:
            remaining = float(sub['monthly_fee']) - total_paid # مبدئياً للشهر الحالي
            st.write(f"**المتبقي (تقديري):** {max(0, remaining)} جنيه")

    with col3:
        st.markdown("### 📈 الحضور")
        if attendance:
            present = sum(1 for a in attendance if a['status'] == 'Present')
            rate = (present / len(attendance)) * 100
            st.metric("نسبة الحضور", f"{rate:.1f}%")
        else:
            st.write("لا توجد سجلات حضور")

    st.divider()

    p_tab1, p_tab2 = st.tabs(["📅 سجل الحضور", "💸 سجل المدفوعات"])
    with p_tab1:
        if attendance: st.table(pd.DataFrame(attendance)[["date", "status"]])
    with p_tab2:
        if payments: st.table(pd.DataFrame(payments)[["amount", "payment_method", "payment_date", "notes"]])

# ========================= المحرك الرئيسي =========================

def main():
    mgr = SheetsManager()
    if not mgr.connect():
        st.stop()
    mgr.setup_sheets()

    cookie_mgr = get_cookie_manager()

    if 'user' not in st.session_state:
        session_id = cookie_mgr.get("el_couch_session")
        if session_id:
            username = mgr.validate_session(session_id)
            if username:
                users = mgr.get_all_users()
                user = next((u for u in users if u['username'] == username), None)
                if user:
                    st.session_state.user = user

    if 'user' in st.session_state:
        # شريط جانبي للخروج
        with st.sidebar:
            st.write(f"👤 {st.session_state.user['username']}")
            if st.button("تسجيل الخروج"):
                session_id = cookie_mgr.get("el_couch_session")
                if session_id:
                    mgr.delete_session(session_id)
                cookie_mgr.delete("el_couch_session")
                del st.session_state.user
                st.rerun()

        if st.session_state.user['role'] == 'coach':
            coach_dashboard(mgr)
        else:
            player_dashboard(mgr)
    else:
        login_page(mgr, cookie_mgr)

if __name__ == "__main__":
    main()
