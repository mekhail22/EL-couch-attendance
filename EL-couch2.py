# -*- coding: utf-8 -*-
"""
الكوتش أكاديمي - نظام إدارة الحضور والاشتراكات
ملف واحد متكامل للعمل مع Streamlit و Google Sheets
"""

import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import re
import json
from typing import Optional, List, Dict, Any, Tuple
import plotly.express as px
import plotly.graph_objects as go

# =============================================================================
# إعدادات الصفحة والتنسيقات
# =============================================================================
st.set_page_config(
    page_title="الكوتش أكاديمي",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تطبيق CSS مخصص للخط العربي والتنسيق
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Tajawal', sans-serif;
}
.stButton button {
    width: 100%;
    background-color: #2e7d32;
    color: white;
    font-weight: bold;
    border-radius: 8px;
    border: none;
    padding: 0.5rem 1rem;
    transition: all 0.3s ease;
}
.stButton button:hover {
    background-color: #1b5e20;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
}
.metric-card {
    background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border-right: 4px solid #2e7d32;
}
h1, h2, h3 {
    color: #1a1a1a;
}
.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# إدارة Google Sheets (قاعدة البيانات)
# =============================================================================
class GSheetManager:
    """
    مدير الاتصال بـ Google Sheets مع تخزين مؤقت لتحسين الأداء.
    يدعم جميع عمليات القراءة والكتابة والتحديث.
    """
    def __init__(self):
        self._client = None
        self._spreadsheet = None
        self._cache = {}
        self._init_complete = False
    
    def _get_client(self) -> gspread.Client:
        """إنشاء عميل Google Sheets باستخدام بيانات الخدمة من secrets."""
        if self._client is None:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            # استخدام بيانات الاعتماد من Streamlit secrets
            service_account_info = st.secrets["google"]["service_account"]
            if isinstance(service_account_info, str):
                service_account_info = json.loads(service_account_info)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                service_account_info, scope
            )
            self._client = gspread.authorize(creds)
        return self._client
    
    def _get_spreadsheet(self):
        """فتح جدول البيانات الرئيسي."""
        if self._spreadsheet is None:
            client = self._get_client()
            sheet_id = st.secrets["google"]["spreadsheet_id"]
            self._spreadsheet = client.open_by_key(sheet_id)
        return self._spreadsheet
    
    def get_worksheet(self, name: str, create_if_missing: bool = True, 
                     rows: int = 2000, cols: int = 20) -> gspread.Worksheet:
        """
        الحصول على ورقة عمل باسم محدد.
        إذا لم تكن موجودة و create_if_missing=True، يتم إنشاؤها تلقائياً.
        """
        sh = self._get_spreadsheet()
        try:
            return sh.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            if create_if_missing:
                ws = sh.add_worksheet(name, rows=rows, cols=cols)
                return ws
            else:
                raise
    
    def load_dataframe(self, sheet_name: str, use_cache: bool = True) -> pd.DataFrame:
        """
        تحميل بيانات ورقة العمل كـ pandas DataFrame.
        يدعم التخزين المؤقت لتسريع القراءات المتكررة.
        """
        cache_key = f"df_{sheet_name}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        try:
            ws = self.get_worksheet(sheet_name, create_if_missing=False)
            data = ws.get_all_records()
            df = pd.DataFrame(data) if data else pd.DataFrame()
        except gspread.exceptions.WorksheetNotFound:
            df = pd.DataFrame()
        
        self._cache[cache_key] = df.copy()
        return df
    
    def save_dataframe(self, sheet_name: str, df: pd.DataFrame, clear_sheet: bool = True):
        """حفظ DataFrame كامل في ورقة العمل."""
        ws = self.get_worksheet(sheet_name, create_if_missing=True)
        if clear_sheet:
            ws.clear()
        headers = df.columns.tolist()
        rows = [headers] + df.values.tolist()
        if rows:
            ws.update(rows, value_input_option='USER_ENTERED')
        cache_key = f"df_{sheet_name}"
        self._cache[cache_key] = df.copy()
    
    def append_row(self, sheet_name: str, row_data: List[Any]):
        """إضافة صف جديد في نهاية الورقة."""
        ws = self.get_worksheet(sheet_name, create_if_missing=True)
        ws.append_row(row_data, value_input_option='USER_ENTERED')
        cache_key = f"df_{sheet_name}"
        if cache_key in self._cache:
            del self._cache[cache_key]
    
    def update_cell(self, sheet_name: str, row: int, col: int, value: Any):
        """تحديث خلية محددة."""
        ws = self.get_worksheet(sheet_name, create_if_missing=False)
        if ws:
            ws.update_cell(row, col, value)
            cache_key = f"df_{sheet_name}"
            if cache_key in self._cache:
                del self._cache[cache_key]
    
    def delete_rows(self, sheet_name: str, row_indices: List[int]):
        """حذف صفوف محددة (الأرقام تبدأ من 1 في الشيت)."""
        ws = self.get_worksheet(sheet_name, create_if_missing=False)
        if ws and row_indices:
            for idx in sorted(row_indices, reverse=True):
                ws.delete_rows(idx)
            cache_key = f"df_{sheet_name}"
            if cache_key in self._cache:
                del self._cache[cache_key]
    
    def clear_cache(self, sheet_name: Optional[str] = None):
        """مسح التخزين المؤقت لورقة محددة أو للكل."""
        if sheet_name:
            cache_key = f"df_{sheet_name}"
            if cache_key in self._cache:
                del self._cache[cache_key]
        else:
            self._cache.clear()
    
    def initialize_all_sheets(self):
        """تهيئة جميع الأوراق المطلوبة مع البيانات الافتراضية."""
        if self._init_complete:
            return
        
        # Users sheet
        ws_users = self.get_worksheet("Users", create_if_missing=True, rows=500)
        existing_users = self.load_dataframe("Users", use_cache=False)
        if existing_users.empty:
            self.append_row("Users", ["username", "password", "role"])
            # إضافة كابتن افتراضي
            self.append_row("Users", ["أحمد محمد علي", "coach123", "coach"])
            # إضافة لاعبين افتراضيين للاختبار
            self.append_row("Users", ["محمد خالد سعيد", "pass123", "player"])
            self.append_row("Users", ["فاطمة حسن محمود", "pass123", "player"])
            self.append_row("Users", ["عمر أحمد فوزي", "pass123", "player"])
            self.append_row("Users", ["كريم محمود عبدالله", "pass123", "player"])
        
        # Attendance sheet
        ws_att = self.get_worksheet("Attendance", create_if_missing=True, rows=5000)
        if len(ws_att.get_all_values()) == 0:
            ws_att.append_row(["player_name", "date", "status", "recorded_by"])
        
        # Subscriptions sheet (الاشتراكات)
        ws_subs = self.get_worksheet("Subscriptions", create_if_missing=True, rows=1000)
        if len(ws_subs.get_all_values()) == 0:
            ws_subs.append_row(["player_name", "monthly_fee", "start_date", "end_date", "subscription_status"])
            today = date.today().isoformat()
            next_year = (date.today() + timedelta(days=365)).isoformat()
            self.append_row("Subscriptions", ["محمد خالد سعيد", 300, today, next_year, "نشط"])
            self.append_row("Subscriptions", ["فاطمة حسن محمود", 250, today, next_year, "نشط"])
            self.append_row("Subscriptions", ["عمر أحمد فوزي", 350, today, next_year, "نشط"])
        
        # Payments sheet (المدفوعات)
        ws_pay = self.get_worksheet("Payments", create_if_missing=True, rows=5000)
        if len(ws_pay.get_all_values()) == 0:
            ws_pay.append_row(["player_name", "amount", "payment_method", "payment_date", "notes"])
            # إضافة دفعات افتراضية
            self.append_row("Payments", ["محمد خالد سعيد", 300, "Cash", date.today().isoformat(), "دفعة يناير"])
            self.append_row("Payments", ["فاطمة حسن محمود", 250, "Vodafone Cash", date.today().isoformat(), "دفعة يناير"])
        
        self._init_complete = True

# إنشاء نسخة عامة من مدير Google Sheets
gsm = GSheetManager()

# =============================================================================
# دوال المصادقة والتحقق من المستخدمين
# =============================================================================
def is_valid_arabic_name(name: str) -> bool:
    """التحقق من أن الاسم يتكون من ثلاث كلمات على الأقل (عربي أو إنجليزي)."""
    if not name or not isinstance(name, str):
        return False
    parts = name.strip().split()
    return len(parts) >= 3

def normalize_username(username: str) -> str:
    """تنظيف اسم المستخدم من الفراغات الزائدة."""
    return ' '.join(username.strip().split())

def username_exists(username: str) -> bool:
    """التحقق من وجود اسم المستخدم في قاعدة البيانات."""
    df = gsm.load_dataframe("Users", use_cache=True)
    if df.empty:
        return False
    return username in df['username'].values

def authenticate(username: str, password: str) -> Optional[str]:
    """التحقق من صحة بيانات الدخول وإرجاع الدور (coach/player) أو None."""
    df = gsm.load_dataframe("Users", use_cache=True)
    if df.empty:
        return None
    user_row = df[(df['username'] == username) & (df['password'] == password)]
    if not user_row.empty:
        return user_row.iloc[0]['role']
    return None

def create_user(username: str, password: str, role: str = "player") -> Tuple[bool, str]:
    """إنشاء مستخدم جديد مع التحقق من صحة البيانات."""
    username = normalize_username(username)
    if not is_valid_arabic_name(username):
        return False, "يجب أن يكون الاسم ثلاثيًا (ثلاث كلمات على الأقل)."
    if username_exists(username):
        return False, "هذا الاسم مستخدم بالفعل."
    if len(password) < 6:
        return False, "كلمة المرور يجب أن تكون 6 أحرف على الأقل."
    
    gsm.append_row("Users", [username, password, role])
    gsm.clear_cache("Users")
    return True, "تم إنشاء الحساب بنجاح."

def get_all_players() -> List[str]:
    """جلب قائمة بأسماء جميع اللاعبين."""
    df = gsm.load_dataframe("Users", use_cache=True)
    if df.empty:
        return []
    return df[df['role'] == 'player']['username'].tolist()

def get_all_coaches() -> List[str]:
    """جلب قائمة بأسماء المدربين."""
    df = gsm.load_dataframe("Users", use_cache=True)
    if df.empty:
        return []
    return df[df['role'] == 'coach']['username'].tolist()

# =============================================================================
# دوال الحسابات المالية (اشتراكات ومدفوعات موحدة)
# =============================================================================
def calculate_months_between(start_date: date, end_date: date) -> int:
    """حساب عدد الأشهر بين تاريخين (تقريب شهري)."""
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day >= start_date.day:
        months += 1
    return max(0, months)

def calculate_total_due(subscription: Dict, as_of_date: Optional[date] = None) -> float:
    """حساب المبلغ المستحق للاعب منذ بداية الاشتراك حتى تاريخ معين."""
    if as_of_date is None:
        as_of_date = date.today()
    start = datetime.strptime(subscription['start_date'], "%Y-%m-%d").date()
    monthly_fee = float(subscription['monthly_fee'])
    months_passed = calculate_months_between(start, as_of_date)
    return months_passed * monthly_fee

def get_player_subscription(player_name: str) -> Optional[Dict]:
    """استرجاع أحدث اشتراك نشط للاعب."""
    df = gsm.load_dataframe("Subscriptions", use_cache=True)
    if df.empty:
        return None
    player_subs = df[df['player_name'] == player_name]
    if player_subs.empty:
        return None
    player_subs = player_subs.sort_values('start_date', ascending=False)
    return player_subs.iloc[0].to_dict()

def get_player_payments(player_name: str) -> pd.DataFrame:
    """جلب جميع مدفوعات لاعب معين."""
    df = gsm.load_dataframe("Payments", use_cache=True)
    if df.empty:
        return pd.DataFrame()
    return df[df['player_name'] == player_name]

def get_player_financial_summary(player_name: str) -> Dict:
    """
    ملخص مالي موحد للاعب يشمل:
    - تفاصيل الاشتراك
    - إجمالي المستحق
    - إجمالي المدفوع
    - المتبقي
    """
    sub = get_player_subscription(player_name)
    if not sub:
        return {
            'has_subscription': False,
            'total_due': 0.0,
            'total_paid': 0.0,
            'remaining': 0.0,
            'subscription': None
        }
    total_due = calculate_total_due(sub)
    payments_df = get_player_payments(player_name)
    total_paid = payments_df['amount'].sum() if not payments_df.empty else 0.0
    remaining = total_due - total_paid
    return {
        'has_subscription': True,
        'subscription': sub,
        'total_due': total_due,
        'total_paid': total_paid,
        'remaining': remaining
    }

def save_payment(player_name: str, amount: float, method: str, pay_date: str, notes: str = ""):
    """تسجيل دفعة جديدة."""
    gsm.append_row("Payments", [player_name, amount, method, pay_date, notes])
    gsm.clear_cache("Payments")

def save_subscription(player_name: str, monthly_fee: float, start_date: str, 
                     end_date: str, status: str):
    """حفظ اشتراك جديد."""
    gsm.append_row("Subscriptions", [player_name, monthly_fee, start_date, end_date, status])
    gsm.clear_cache("Subscriptions")

def get_all_financial_overview() -> pd.DataFrame:
    """تقرير مالي لجميع اللاعبين (اشتراكات ومدفوعات مجمعة)."""
    players = get_all_players()
    data = []
    for player in players:
        summary = get_player_financial_summary(player)
        sub_info = summary.get('subscription', {})
        data.append({
            'اللاعب': player,
            'الرسوم الشهرية': sub_info.get('monthly_fee', 0) if sub_info else 0,
            'بداية الاشتراك': sub_info.get('start_date', '') if sub_info else '',
            'نهاية الاشتراك': sub_info.get('end_date', '') if sub_info else '',
            'حالة الاشتراك': sub_info.get('subscription_status', 'لا يوجد') if sub_info else 'لا يوجد',
            'المستحق': summary['total_due'],
            'المدفوع': summary['total_paid'],
            'المتبقي': summary['remaining']
        })
    return pd.DataFrame(data)

# =============================================================================
# دوال مساعدة للواجهة والجلسات
# =============================================================================
def init_session_state():
    """تهيئة متغيرات الجلسة الافتراضية."""
    defaults = {
        'logged_in': False,
        'username': None,
        'role': None,
        'current_page': 'login',
        'attendance_date': date.today(),
        'selected_players': []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def logout():
    """تسجيل الخروج ومسح بيانات الجلسة."""
    for key in ['logged_in', 'username', 'role']:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.current_page = 'login'
    gsm.clear_cache()
    st.rerun()

def login_required(func):
    """ديكوريتور للتأكد من تسجيل الدخول قبل الوصول للصفحات."""
    def wrapper(*args, **kwargs):
        if not st.session_state.get('logged_in', False):
            st.warning("يجب تسجيل الدخول أولاً.")
            st.stop()
        return func(*args, **kwargs)
    return wrapper

def coach_required(func):
    """ديكوريتور للتأكد من أن المستخدم كابتن."""
    def wrapper(*args, **kwargs):
        if not st.session_state.get('logged_in', False):
            st.warning("يجب تسجيل الدخول أولاً.")
            st.stop()
        if st.session_state.role != 'coach':
            st.error("هذه الصفحة مخصصة للكابتن فقط.")
            st.stop()
        return func(*args, **kwargs)
    return wrapper

def filter_dataframe(df: pd.DataFrame, column: str, search_term: str) -> pd.DataFrame:
    """تصفية DataFrame بناءً على عمود معين (بحث نصي)."""
    if search_term and not df.empty:
        return df[df[column].astype(str).str.contains(search_term, case=False, na=False)]
    return df

def plot_attendance_pie(present: int, absent: int) -> go.Figure:
    """رسم بياني دائري لنسبة الحضور."""
    labels = ['حاضر', 'غائب']
    values = [present, absent]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3,
                                 marker=dict(colors=['#2e7d32', '#d32f2f']))])
    fig.update_layout(title="نسبة الحضور والغياب", font=dict(family="Tajawal"))
    return fig

def display_metric_card(title: str, value: str, delta: Optional[str] = None):
    """عرض بطاقة قياس مخصصة."""
    delta_html = ''
    if delta:
        try:
            delta_val = float(delta)
            color = 'green' if delta_val >= 0 else 'red'
            delta_html = f'<span style="color: {color};">{delta}</span>'
        except ValueError:
            delta_html = f'<span>{delta}</span>'
    st.markdown(f"""
    <div class="metric-card">
        <h3>{title}</h3>
        <h2>{value}</h2>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# واجهات المستخدم (الصفحات)
# =============================================================================
def login_page():
    """صفحة تسجيل الدخول وإنشاء الحساب."""
    st.markdown("<h1 style='text-align: center;'>⚽ الكوتش أكاديمي</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>نظام إدارة الحضور والاشتراكات</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 تسجيل الدخول", "📝 إنشاء حساب لاعب"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("الاسم الثلاثي (اسم المستخدم)")
                password = st.text_input("كلمة المرور", type="password")
                submitted = st.form_submit_button("دخول", use_container_width=True)
                
                if submitted:
                    username = normalize_username(username)
                    if not is_valid_arabic_name(username):
                        st.error("❌ يجب إدخال الاسم الثلاثي كاملاً.")
                    else:
                        role = authenticate(username, password)
                        if role:
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.role = role
                            st.session_state.current_page = 'dashboard' if role == 'coach' else 'home'
                            st.success("✅ تم تسجيل الدخول بنجاح!")
                            st.rerun()
                        else:
                            st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة.")
        
        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("الاسم الثلاثي (سيُستخدم كاسم مستخدم)")
                new_password = st.text_input("كلمة المرور", type="password", help="6 أحرف على الأقل")
                confirm_password = st.text_input("تأكيد كلمة المرور", type="password")
                submitted = st.form_submit_button("إنشاء حساب", use_container_width=True)
                
                if submitted:
                    success, msg = create_user(new_username, new_password, "player")
                    if success:
                        st.success(f"✅ {msg}")
                        st.balloons()
                    else:
                        st.error(f"❌ {msg}")

def render_sidebar():
    """عرض الشريط الجانبي مع معلومات المستخدم والتنقل."""
    with st.sidebar:
        st.markdown("## ⚽ الكوتش أكاديمي")
        st.markdown(f"**مرحباً، {st.session_state.username}**")
        st.markdown(f"*الدور: {st.session_state.role}*")
        st.divider()
        
        # قائمة التنقل حسب الدور
        if st.session_state.role == 'coach':
            pages = {
                "📋 لوحة التحكم": "dashboard",
                "✅ تسجيل الحضور": "attendance",
                "📊 إحصائيات الغياب": "stats",
                "💳 إدارة الاشتراكات": "subscriptions",
                "💰 تسجيل دفعة": "payment",
                "📈 التقارير المالية": "reports",
                "👥 إدارة المستخدمين": "users"
            }
        else:
            pages = {
                "🏠 الصفحة الرئيسية": "home",
                "📅 سجل الحضور": "my_attendance",
                "💰 حالتي المالية": "my_finance"
            }
        
        page_names = list(pages.keys())
        selected_page = st.radio("القائمة", page_names, label_visibility="collapsed")
        st.session_state.current_page = pages[selected_page]
        
        st.divider()
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout()

# -----------------------------------------------------------------------------
# صفحات الكابتن
# -----------------------------------------------------------------------------
@login_required
@coach_required
def coach_dashboard():
    """لوحة تحكم الكابتن - نظرة عامة."""
    st.title("📋 لوحة تحكم الكابتن")
    
    players = get_all_players()
    att_df = gsm.load_dataframe("Attendance", use_cache=True)
    payments_df = gsm.load_dataframe("Payments", use_cache=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 إجمالي اللاعبين", len(players))
    with col2:
        if not att_df.empty:
            today = date.today().isoformat()
            today_att = att_df[att_df['date'] == today]
            present = len(today_att[today_att['status'] == 'Present'])
            st.metric("✅ حضور اليوم", present)
        else:
            st.metric("✅ حضور اليوم", 0)
    with col3:
        if not att_df.empty and 'today_att' in locals():
            absent = len(today_att[today_att['status'] == 'Absent'])
            st.metric("❌ غياب اليوم", absent)
        else:
            st.metric("❌ غياب اليوم", 0)
    with col4:
        if not payments_df.empty:
            current_month = date.today().strftime("%Y-%m")
            month_payments = payments_df[payments_df['payment_date'].str.startswith(current_month, na=False)]
            total = month_payments['amount'].sum() if not month_payments.empty else 0
            st.metric("💰 مدفوعات الشهر", f"{total:.0f} ج")
        else:
            st.metric("💰 مدفوعات الشهر", "0 ج")
    
    st.divider()
    st.subheader("📈 اتجاه الحضور الشهري")
    if not att_df.empty:
        att_df['date'] = pd.to_datetime(att_df['date'])
        att_df['month'] = att_df['date'].dt.to_period('M')
        monthly = att_df.groupby(['month', 'status']).size().unstack(fill_value=0)
        if not monthly.empty:
            monthly['نسبة الحضور'] = (monthly.get('Present', 0) / (monthly.get('Present', 0) + monthly.get('Absent', 0))) * 100
            fig = px.line(monthly.reset_index(), x='month', y='نسبة الحضور', markers=True)
            fig.update_layout(font=dict(family="Tajawal"))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد سجلات حضور بعد.")

@login_required
@coach_required
def attendance_page():
    """صفحة تسجيل الحضور والغياب (متعدد الاختيار)."""
    st.title("✅ تسجيل حضور وغياب اللاعبين")
    
    players = get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون مسجلون.")
        return
    
    today = date.today().isoformat()
    st.subheader(f"📅 تاريخ اليوم: {today}")
    
    att_df = gsm.load_dataframe("Attendance", use_cache=True)
    today_records = att_df[att_df['date'] == today] if not att_df.empty else pd.DataFrame()
    present_players = today_records[today_records['status'] == 'Present']['player_name'].tolist() if not today_records.empty else []
    
    st.markdown("**اختر اللاعبين الغائبين (سيتم اعتبار الباقين حاضرين):**")
    absent_choices = st.multiselect(
        "اللاعبون الغائبون",
        options=players,
        default=[p for p in players if p not in present_players],
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 تسجيل الحضور والغياب", use_container_width=True, type="primary"):
            recorded_by = st.session_state.username
            
            # حذف سجلات اليوم السابقة
            if not att_df.empty:
                rows_to_delete = []
                for idx, row in att_df.iterrows():
                    if row['date'] == today:
                        rows_to_delete.append(idx + 2)
                if rows_to_delete:
                    gsm.delete_rows("Attendance", rows_to_delete)
            
            # إضافة السجلات الجديدة
            for player in players:
                status = "Absent" if player in absent_choices else "Present"
                gsm.append_row("Attendance", [player, today, status, recorded_by])
            
            st.success("✅ تم تسجيل الحضور بنجاح!")
            gsm.clear_cache("Attendance")
            st.rerun()
    
    with col2:
        if st.button("🔄 تحديث العرض", use_container_width=True):
            gsm.clear_cache("Attendance")
            st.rerun()
    
    st.subheader("📋 سجل الحضور اليوم")
    updated_att = gsm.load_dataframe("Attendance", use_cache=False)
    today_att = updated_att[updated_att['date'] == today][['player_name', 'status']] if not updated_att.empty else pd.DataFrame()
    if not today_att.empty:
        st.dataframe(today_att, use_container_width=True)
        present_count = len(today_att[today_att['status'] == 'Present'])
        absent_count = len(today_att[today_att['status'] == 'Absent'])
        fig = plot_attendance_pie(present_count, absent_count)
        st.plotly_chart(fig, use_container_width=True)

@login_required
@coach_required
def stats_page():
    """صفحة إحصائيات الحضور والغياب."""
    st.title("📊 إحصائيات الغياب والحضور")
    
    att_df = gsm.load_dataframe("Attendance", use_cache=True)
    if att_df.empty:
        st.info("لا توجد سجلات حضور.")
        return
    
    total_counts = att_df['player_name'].value_counts().reset_index()
    total_counts.columns = ['اللاعب', 'إجمالي الأيام']
    absent_counts = att_df[att_df['status'] == 'Absent']['player_name'].value_counts().reset_index()
    absent_counts.columns = ['اللاعب', 'أيام الغياب']
    
    stats = pd.merge(total_counts, absent_counts, on='اللاعب', how='left').fillna(0)
    stats['أيام الغياب'] = stats['أيام الغياب'].astype(int)
    stats['نسبة الحضور %'] = ((stats['إجمالي الأيام'] - stats['أيام الغياب']) / stats['إجمالي الأيام'] * 100).round(1)
    stats = stats.sort_values('نسبة الحضور %', ascending=False)
    
    search_term = st.text_input("🔍 بحث عن لاعب", "")
    if search_term:
        stats = filter_dataframe(stats, 'اللاعب', search_term)
    
    st.dataframe(stats, use_container_width=True, height=500)
    
    st.subheader("🏆 أعلى 10 لاعبين حضوراً")
    top10 = stats.head(10)
    fig = px.bar(top10, x='اللاعب', y='نسبة الحضور %', color='نسبة الحضور %',
                 color_continuous_scale='greens', text='نسبة الحضور %')
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(font=dict(family="Tajawal"), xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

@login_required
@coach_required
def subscriptions_page():
    """صفحة إدارة الاشتراكات."""
    st.title("💳 إدارة الاشتراكات")
    
    players = get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون.")
        return
    
    tab1, tab2 = st.tabs(["📋 الاشتراكات الحالية", "➕ إضافة/تعديل اشتراك"])
    
    with tab1:
        st.subheader("الاشتراكات المسجلة")
        subs_df = gsm.load_dataframe("Subscriptions", use_cache=True)
        if not subs_df.empty:
            search = st.text_input("بحث عن لاعب", key="sub_search")
            display_df = subs_df.copy()
            if search:
                display_df = display_df[display_df['player_name'].str.contains(search, case=False, na=False)]
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("لا توجد اشتراكات مسجلة.")
    
    with tab2:
        st.subheader("إضافة أو تعديل اشتراك لاعب")
        with st.form("subscription_form"):
            player = st.selectbox("اختر اللاعب", players)
            current_sub = get_player_subscription(player)
            if current_sub:
                st.info(f"الاشتراك الحالي: {current_sub['monthly_fee']} ج شهرياً")
            
            monthly_fee = st.number_input("الرسوم الشهرية (جنيه)", min_value=0.0, step=50.0,
                                          value=float(current_sub['monthly_fee']) if current_sub else 300.0)
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("تاريخ البداية", value=date.today())
            with col2:
                end_date = st.date_input("تاريخ النهاية", value=date.today() + timedelta(days=365))
            status = st.selectbox("حالة الاشتراك", ["نشط", "منتهي", "متوقف"])
            
            submitted = st.form_submit_button("💾 حفظ الاشتراك", use_container_width=True)
            if submitted:
                save_subscription(player, monthly_fee, start_date.isoformat(), end_date.isoformat(), status)
                st.success("✅ تم حفظ الاشتراك بنجاح!")
                gsm.clear_cache("Subscriptions")
                st.rerun()

@login_required
@coach_required
def payment_page():
    """صفحة تسجيل دفعة مالية."""
    st.title("💰 تسجيل دفعة مالية")
    
    players = get_all_players()
    if not players:
        st.warning("لا يوجد لاعبون.")
        return
    
    with st.form("payment_form"):
        player = st.selectbox("اختر اللاعب", players)
        summary = get_player_financial_summary(player)
        if summary['has_subscription']:
            st.info(f"المستحق: {summary['total_due']:.2f} ج | المدفوع: {summary['total_paid']:.2f} ج | المتبقي: {summary['remaining']:.2f} ج")
        
        amount = st.number_input("المبلغ", min_value=0.0, step=50.0)
        method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
        pay_date = st.date_input("تاريخ الدفع", value=date.today())
        notes = st.text_area("ملاحظات (اختياري)")
        
        submitted = st.form_submit_button("💾 تسجيل الدفعة", use_container_width=True)
        if submitted:
            if amount <= 0:
                st.error("يجب أن يكون المبلغ أكبر من صفر.")
            else:
                save_payment(player, amount, method, pay_date.isoformat(), notes)
                st.success("✅ تم تسجيل الدفعة بنجاح!")
                gsm.clear_cache("Payments")
                st.rerun()

@login_required
@coach_required
def reports_page():
    """صفحة التقارير المالية الشاملة."""
    st.title("📈 التقارير المالية")
    
    finance_df = get_all_financial_overview()
    if finance_df.empty:
        st.info("لا توجد بيانات مالية.")
        return
    
    total_due = finance_df['المستحق'].sum()
    total_paid = finance_df['المدفوع'].sum()
    total_remaining = finance_df['المتبقي'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي المستحقات", f"{total_due:,.0f} ج")
    col2.metric("إجمالي المدفوعات", f"{total_paid:,.0f} ج")
    col3.metric("إجمالي المتبقي", f"{total_remaining:,.0f} ج")
    
    st.divider()
    st.subheader("تفاصيل الحسابات المالية للاعبين")
    search = st.text_input("🔍 بحث عن لاعب", key="finance_search")
    display_df = finance_df.copy()
    if search:
        display_df = filter_dataframe(display_df, 'اللاعب', search)
    
    st.dataframe(display_df, use_container_width=True, height=400)
    
    st.subheader("المبالغ المتبقية لكل لاعب")
    fig = px.bar(display_df.sort_values('المتبقي', ascending=False).head(15),
                 x='اللاعب', y='المتبقي', color='المتبقي',
                 color_continuous_scale='reds', text='المتبقي')
    fig.update_traces(texttemplate='%{text:.0f} ج', textposition='outside')
    fig.update_layout(font=dict(family="Tajawal"), xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

@login_required
@coach_required
def users_page():
    """صفحة إدارة المستخدمين."""
    st.title("👥 إدارة المستخدمين")
    
    tab1, tab2 = st.tabs(["📋 قائمة المستخدمين", "➕ إضافة كابتن جديد"])
    
    with tab1:
        users_df = gsm.load_dataframe("Users", use_cache=True)
        if not users_df.empty:
            display_df = users_df.copy()
            display_df['password'] = '••••••'
            st.dataframe(display_df, use_container_width=True)
            
            coaches = len(users_df[users_df['role'] == 'coach'])
            players = len(users_df[users_df['role'] == 'player'])
            col1, col2 = st.columns(2)
            col1.metric("عدد الكباتن", coaches)
            col2.metric("عدد اللاعبين", players)
    
    with tab2:
        st.subheader("إضافة كابتن جديد")
        with st.form("add_coach_form"):
            new_username = st.text_input("الاسم الثلاثي للكابتن")
            new_password = st.text_input("كلمة المرور", type="password")
            confirm = st.text_input("تأكيد كلمة المرور", type="password")
            submitted = st.form_submit_button("إضافة كابتن")
            if submitted:
                success, msg = create_user(new_username, new_password, "coach")
                if success:
                    st.success(f"✅ {msg}")
                    gsm.clear_cache("Users")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

# -----------------------------------------------------------------------------
# صفحات اللاعب
# -----------------------------------------------------------------------------
@login_required
def player_home():
    """الصفحة الرئيسية للاعب."""
    st.title(f"👤 مرحباً، {st.session_state.username}")
    
    summary = get_player_financial_summary(st.session_state.username)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        sub_status = summary['subscription']['subscription_status'] if summary['has_subscription'] else "لا يوجد"
        st.metric("حالة الاشتراك", sub_status)
    with col2:
        st.metric("المستحق", f"{summary['total_due']:.0f} ج")
    with col3:
        st.metric("المتبقي", f"{summary['remaining']:.0f} ج")
    
    att_df = gsm.load_dataframe("Attendance", use_cache=True)
    if not att_df.empty:
        player_att = att_df[att_df['player_name'] == st.session_state.username]
        total = len(player_att)
        if total > 0:
            present = len(player_att[player_att['status'] == 'Present'])
            pct = (present / total) * 100
            st.subheader("📊 نسبة حضورك")
            st.progress(pct / 100, text=f"{pct:.1f}%")
    
    st.divider()
    st.subheader("📋 آخر 5 نشاطات حضور")
    if not att_df.empty:
        recent = player_att.sort_values('date', ascending=False).head(5)[['date', 'status']]
        st.dataframe(recent, use_container_width=True)

@login_required
def player_attendance():
    """صفحة سجل الحضور للاعب."""
    st.title("📅 سجل الحضور والغياب")
    
    att_df = gsm.load_dataframe("Attendance", use_cache=True)
    if att_df.empty:
        st.info("لا توجد سجلات حضور.")
        return
    
    player_att = att_df[att_df['player_name'] == st.session_state.username].sort_values('date', ascending=False)
    if player_att.empty:
        st.info("لا توجد سجلات حضور لك بعد.")
        return
    
    total = len(player_att)
    present = len(player_att[player_att['status'] == 'Present'])
    absent = total - present
    pct = (present / total) * 100 if total > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي الأيام", total)
    col2.metric("أيام الحضور", present)
    col3.metric("أيام الغياب", absent)
    st.metric("نسبة الحضور", f"{pct:.1f}%")
    
    fig = plot_attendance_pie(present, absent)
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("تفاصيل السجلات")
    st.dataframe(player_att[['date', 'status', 'recorded_by']], use_container_width=True)

@login_required
def player_finance():
    """صفحة الحالة المالية للاعب."""
    st.title("💰 حالتي المالية")
    
    summary = get_player_financial_summary(st.session_state.username)
    
    if not summary['has_subscription']:
        st.warning("لا يوجد اشتراك مسجل لك. يرجى التواصل مع الكابتن.")
        return
    
    sub = summary['subscription']
    
    st.subheader("💳 تفاصيل الاشتراك")
    col1, col2, col3 = st.columns(3)
    col1.metric("الرسوم الشهرية", f"{sub['monthly_fee']} ج")
    col2.metric("تاريخ البداية", sub['start_date'])
    col3.metric("تاريخ النهاية", sub['end_date'])
    
    st.divider()
    st.subheader("💰 المستحقات والمدفوعات")
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي المستحق", f"{summary['total_due']:.2f} ج")
    col2.metric("إجمالي المدفوع", f"{summary['total_paid']:.2f} ج")
    col3.metric("المتبقي", f"{summary['remaining']:.2f} ج")
    
    st.subheader("🧾 سجل المدفوعات")
    payments_df = get_player_payments(st.session_state.username)
    if not payments_df.empty:
        st.dataframe(payments_df[['amount', 'payment_method', 'payment_date', 'notes']], use_container_width=True)
    else:
        st.info("لا توجد مدفوعات مسجلة بعد.")

# =============================================================================
# الدالة الرئيسية والتوجيه
# =============================================================================
def main():
    """الدالة الرئيسية لتوجيه الصفحات وإدارة التطبيق."""
    # تهيئة الجلسة والأوراق
    init_session_state()
    gsm.initialize_all_sheets()
    
    # التحقق من تسجيل الدخول
    if not st.session_state.get('logged_in', False):
        login_page()
        return
    
    # عرض الشريط الجانبي
    render_sidebar()
    
    # توجيه الصفحة الحالية
    current = st.session_state.get('current_page', 'dashboard')
    
    if st.session_state.role == 'coach':
        pages = {
            'dashboard': coach_dashboard,
            'attendance': attendance_page,
            'stats': stats_page,
            'subscriptions': subscriptions_page,
            'payment': payment_page,
            'reports': reports_page,
            'users': users_page
        }
    else:
        pages = {
            'home': player_home,
            'my_attendance': player_attendance,
            'my_finance': player_finance
        }
    
    # تنفيذ الصفحة المطلوبة
    if current in pages:
        pages[current]()
    else:
        # الصفحة الافتراضية
        if st.session_state.role == 'coach':
            coach_dashboard()
        else:
            player_home()

if __name__ == "__main__":
    main()
