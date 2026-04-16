"""
الكوتش أكاديمي - نظام إدارة الحضور والاشتراكات
==============================================
تطبيق Streamlit لإدارة الحضور والاشتراكات لأكاديمية كرة القدم
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import pandas as pd
import re

# =============================================================================
# إعدادات الصفحة - يجب أن تكون أول أمر Streamlit
# =============================================================================
st.set_page_config(
    page_title="الكوتش أكاديمي",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CSS مخصص - إخفاء الهيدر وتحسين التصميم
# =============================================================================
st.markdown("""
<style>
    /* إخفاء الهيدر العلوي لـ Streamlit */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* إخفاء شريط الأدوات العلوي */
    .stDeployButton {
        display: none !important;
    }
    
    /* إخفاء قائمة Main Menu */
    #MainMenu {
        visibility: hidden !important;
    }
    
    /* إخفاء الشريط العلوي بالكامل */
    .stApp > header {
        display: none !important;
    }
    
    /* إخفاء زر الإعدادات */
    button[kind="header"] {
        display: none !important;
    }
    
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * {
        font-family: 'Cairo', sans-serif !important;
    }
    
    .main {
        direction: rtl;
    }
    
    .stApp {
        background: linear-gradient(135deg, #1a5f3f 0%, #0d3321 100%);
    }
    
    .login-container {
        max-width: 450px;
        margin: 50px auto;
        padding: 40px;
        background: rgba(255, 255, 255, 0.98);
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
    }
    
    .logo-container {
        text-align: center;
        margin-bottom: 30px;
    }
    
    .logo {
        font-size: 80px;
        margin-bottom: 10px;
    }
    
    .title {
        color: #1a5f3f;
        font-size: 32px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 5px;
    }
    
    .subtitle {
        color: #666;
        font-size: 16px;
        text-align: center;
        margin-bottom: 30px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #1a5f3f 0%, #0d3321 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px 30px;
        font-size: 16px;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(26, 95, 63, 0.4);
    }
    
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 12px 15px;
        text-align: right;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #1a5f3f;
    }
    
    .card {
        background: white;
        border-radius: 15px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .stat-card {
        background: linear-gradient(135deg, #1a5f3f 0%, #0d3321 100%);
        color: white;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
    }
    
    .stat-number {
        font-size: 36px;
        font-weight: 700;
        margin-bottom: 5px;
    }
    
    .stat-label {
        font-size: 14px;
        opacity: 0.9;
    }
    
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-right: 4px solid #28a745;
    }
    
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-right: 4px solid #dc3545;
    }
    
    .warning-message {
        background: #fff3cd;
        color: #856404;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-right: 4px solid #ffc107;
    }
    
    .info-message {
        background: #d1ecf1;
        color: #0c5460;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-right: 4px solid #17a2b8;
    }
    
    .nav-button {
        background: transparent !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        border-radius: 10px !important;
        padding: 10px 15px !important;
        margin-bottom: 8px !important;
        text-align: right !important;
        transition: all 0.3s ease !important;
    }
    
    .nav-button:hover {
        background: rgba(255,255,255,0.1) !important;
        border-color: rgba(255,255,255,0.5) !important;
    }
    
    .nav-button.active {
        background: rgba(255,255,255,0.2) !important;
        border-color: white !important;
    }
    
    .data-table {
        background: white;
        border-radius: 15px;
        overflow: hidden;
    }
    
    .present-badge {
        background: #28a745;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    
    .absent-badge {
        background: #dc3545;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    
    .pending-badge {
        background: #ffc107;
        color: #000;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    
    /* تحسينات للـ selectbox */
    .stSelectbox > div > div {
        border-radius: 10px;
    }
    
    /* تحسينات للـ date_input */
    .stDateInput > div > div > input {
        border-radius: 10px;
    }
    
    /* تحسينات للـ number_input */
    .stNumberInput > div > div > input {
        border-radius: 10px;
    }
    
    /* تحسينات للـ multiselect */
    .stMultiSelect > div > div {
        border-radius: 10px;
    }
    
    /* تحسين التبويبات */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,0.1);
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
        color: white;
    }
    
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #1a5f3f !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# إعداد Google Sheets
# =============================================================================
@st.cache_resource
def get_google_sheets_client():
    """إنشاء اتصال بـ Google Sheets"""
    try:
        credentials_dict = {
            "type": st.secrets["google"]["service_account"]["type"],
            "project_id": st.secrets["google"]["service_account"]["project_id"],
            "private_key_id": st.secrets["google"]["service_account"]["private_key_id"],
            "private_key": st.secrets["google"]["service_account"]["private_key"],
            "client_email": st.secrets["google"]["service_account"]["client_email"],
            "client_id": st.secrets["google"]["service_account"]["client_id"],
            "auth_uri": st.secrets["google"]["service_account"]["auth_uri"],
            "token_uri": st.secrets["google"]["service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["google"]["service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["google"]["service_account"]["client_x509_cert_url"],
            "universe_domain": st.secrets["google"]["service_account"]["universe_domain"]
        }
        spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
    except:
        return None, None
    
    try:
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(credentials)
        return client, spreadsheet_id
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بـ Google Sheets: {str(e)}")
        return None, None

def get_workbook():
    """الحصول على ملف Google Sheets"""
    client, spreadsheet_id = get_google_sheets_client()
    if client and spreadsheet_id:
        try:
            return client.open_by_key(spreadsheet_id)
        except Exception as e:
            st.error(f"❌ خطأ في فتح ملف Sheets: {str(e)}")
    return None

# =============================================================================
# دوال قاعدة البيانات
# =============================================================================
def get_users_sheet():
    """الحصول على sheet المستخدمين"""
    workbook = get_workbook()
    if workbook:
        try:
            return workbook.worksheet("Users")
        except:
            sheet = workbook.add_worksheet(title="Users", rows=1000, cols=10)
            sheet.append_row(["username", "password", "role", "created_at"])
            return sheet
    return None

def get_attendance_sheet():
    """الحصول على sheet الحضور"""
    workbook = get_workbook()
    if workbook:
        try:
            return workbook.worksheet("Attendance")
        except:
            sheet = workbook.add_worksheet(title="Attendance", rows=1000, cols=10)
            sheet.append_row(["player_name", "date", "status", "recorded_by", "created_at"])
            return sheet
    return None

def get_subscriptions_sheet():
    """الحصول على sheet الاشتراكات"""
    workbook = get_workbook()
    if workbook:
        try:
            return workbook.worksheet("Subscriptions")
        except:
            sheet = workbook.add_worksheet(title="Subscriptions", rows=1000, cols=10)
            sheet.append_row(["player_name", "monthly_fee", "start_date", "end_date", "subscription_status", "updated_at"])
            return sheet
    return None

def get_payments_sheet():
    """الحصول على sheet المدفوعات"""
    workbook = get_workbook()
    if workbook:
        try:
            return workbook.worksheet("Payments")
        except:
            sheet = workbook.add_worksheet(title="Payments", rows=1000, cols=10)
            sheet.append_row(["player_name", "amount", "payment_method", "payment_date", "notes", "recorded_by", "created_at"])
            return sheet
    return None

# =============================================================================
# دوال المستخدمين
# =============================================================================
def get_all_users():
    """جلب جميع المستخدمين"""
    sheet = get_users_sheet()
    if sheet:
        data = sheet.get_all_records()
        return data
    return []

def get_user(username: str):
    """جلب مستخدم محدد"""
    users = get_all_users()
    for user in users:
        if user.get("username") == username:
            return user
    return None

def add_user(username: str, password: str, role: str = "player"):
    """إضافة مستخدم جديد"""
    sheet = get_users_sheet()
    if sheet:
        existing = get_user(username)
        if existing:
            return False, "اسم المستخدم موجود بالفعل"
        
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([username, password, role, created_at])
        return True, "تم إضافة المستخدم بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def validate_triple_name(name: str) -> bool:
    """التحقق من أن الاسم ثلاثي"""
    if not name or not isinstance(name, str):
        return False
    
    name = name.strip()
    parts = name.split()
    
    if len(parts) != 3:
        return False
    
    for part in parts:
        if len(part) < 2:
            return False
        if not re.match(r'^[\u0600-\u06FF]+$', part):
            return False
    
    return True

# =============================================================================
# دوال الحضور
# =============================================================================
def record_attendance(player_name: str, status: str, recorded_by: str):
    """تسجيل حضور/غياب"""
    sheet = get_attendance_sheet()
    if sheet:
        today = datetime.now().strftime("%Y-%m-%d")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        all_records = sheet.get_all_records()
        for record in all_records:
            if record.get("player_name") == player_name and record.get("date") == today:
                return False, "تم تسجيل الحضور مسبقاً لهذا اليوم"
        
        sheet.append_row([player_name, today, status, recorded_by, created_at])
        return True, f"تم تسجيل {'الحضور' if status == 'Present' else 'الغياب'} بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def record_multiple_attendance(player_names: list, status: str, recorded_by: str):
    """تسجيل حضور/غياب لعدة لاعبين"""
    sheet = get_attendance_sheet()
    if sheet:
        today = datetime.now().strftime("%Y-%m-%d")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        success_count = 0
        for player_name in player_names:
            all_records = sheet.get_all_records()
            exists = False
            for record in all_records:
                if record.get("player_name") == player_name and record.get("date") == today:
                    exists = True
                    break
            
            if not exists:
                sheet.append_row([player_name, today, status, recorded_by, created_at])
                success_count += 1
        
        return True, f"تم تسجيل {success_count} من {len(player_names)} لاعبين"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def get_player_attendance(player_name: str):
    """جلب سجل حضور لاعب"""
    sheet = get_attendance_sheet()
    if sheet:
        all_records = sheet.get_all_records()
        return [r for r in all_records if r.get("player_name") == player_name]
    return []

def get_all_attendance():
    """جلب جميع سجلات الحضور"""
    sheet = get_attendance_sheet()
    if sheet:
        return sheet.get_all_records()
    return []

def get_attendance_stats(player_name: str):
    """إحصائيات الحضور للاعب"""
    records = get_player_attendance(player_name)
    
    if not records:
        return {"total": 0, "present": 0, "absent": 0, "percentage": 0}
    
    total = len(records)
    present = len([r for r in records if r.get("status") == "Present"])
    absent = total - present
    percentage = (present / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "present": present,
        "absent": absent,
        "percentage": round(percentage, 1)
    }

def get_today_attendance():
    """جلب سجلات اليوم"""
    sheet = get_attendance_sheet()
    if sheet:
        today = datetime.now().strftime("%Y-%m-%d")
        all_records = sheet.get_all_records()
        return [r for r in all_records if r.get("date") == today]
    return []

# =============================================================================
# دوال الاشتراكات
# =============================================================================
def get_player_subscription(player_name: str):
    """جلب اشتراك لاعب"""
    sheet = get_subscriptions_sheet()
    if sheet:
        all_records = sheet.get_all_records()
        for record in all_records:
            if record.get("player_name") == player_name:
                return record
    return None

def add_or_update_subscription(player_name: str, monthly_fee: float, 
                                start_date: str, end_date: str, 
                                subscription_status: str = "Active"):
    """إضافة أو تحديث اشتراك"""
    sheet = get_subscriptions_sheet()
    if sheet:
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        all_records = sheet.get_all_records()
        row_idx = None
        for idx, record in enumerate(all_records, start=2):
            if record.get("player_name") == player_name:
                row_idx = idx
                break
        
        if row_idx:
            sheet.update_cell(row_idx, 2, monthly_fee)
            sheet.update_cell(row_idx, 3, start_date)
            sheet.update_cell(row_idx, 4, end_date)
            sheet.update_cell(row_idx, 5, subscription_status)
            sheet.update_cell(row_idx, 6, updated_at)
            return True, "تم تحديث الاشتراك بنجاح"
        else:
            sheet.append_row([player_name, monthly_fee, start_date, end_date, subscription_status, updated_at])
            return True, "تم إضافة الاشتراك بنجاح"
    
    return False, "خطأ في الاتصال بقاعدة البيانات"

def get_all_subscriptions():
    """جلب جميع الاشتراكات"""
    sheet = get_subscriptions_sheet()
    if sheet:
        return sheet.get_all_records()
    return []

# =============================================================================
# دوال المدفوعات
# =============================================================================
def record_payment(player_name: str, amount: float, payment_method: str, 
                   payment_date: str, notes: str = "", recorded_by: str = ""):
    """تسجيل دفعة"""
    sheet = get_payments_sheet()
    if sheet:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([player_name, amount, payment_method, payment_date, notes, recorded_by, created_at])
        return True, "تم تسجيل الدفعة بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def get_player_payments(player_name: str):
    """جلب مدفوعات لاعب"""
    sheet = get_payments_sheet()
    if sheet:
        all_records = sheet.get_all_records()
        return [r for r in all_records if r.get("player_name") == player_name]
    return []

def get_all_payments():
    """جلب جميع المدفوعات"""
    sheet = get_payments_sheet()
    if sheet:
        return sheet.get_all_records()
    return []

def get_payment_summary(player_name: str):
    """ملخص المدفوعات للاعب"""
    subscription = get_player_subscription(player_name)
    payments = get_player_payments(player_name)
    
    if not subscription:
        return {
            "monthly_fee": 0,
            "total_paid": 0,
            "remaining": 0,
            "status": "No Subscription"
        }
    
    monthly_fee = float(subscription.get("monthly_fee", 0))
    total_paid = sum(float(p.get("amount", 0)) for p in payments)
    remaining = monthly_fee - total_paid
    
    return {
        "monthly_fee": monthly_fee,
        "total_paid": total_paid,
        "remaining": max(0, remaining),
        "status": subscription.get("subscription_status", "Unknown")
    }

# =============================================================================
# تهيئة الجلسة
# =============================================================================
def init_session():
    """تهيئة حالة الجلسة"""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"

def login(username: str, password: str):
    """تسجيل الدخول"""
    user = get_user(username)
    if user and user.get("password") == password:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.role = user.get("role", "player")
        st.session_state.current_page = "dashboard"
        return True
    return False

def logout():
    """تسجيل الخروج"""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.current_page = "login"

def navigate_to(page: str):
    """التنقل بين الصفحات"""
    st.session_state.current_page = page
    st.rerun()

# =============================================================================
# الشريط الجانبي - نظام التنقل
# =============================================================================
def sidebar():
    """الشريط الجانبي مع نظام التنقل"""
    with st.sidebar:
        # الشعار
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <div style="font-size: 60px;">⚽</div>
            <h2 style="color: white; margin: 10px 0; font-size: 24px;">الكوتش أكاديمي</h2>
            <p style="color: rgba(255,255,255,0.7); font-size: 12px;">نظام إدارة الحضور والاشتراكات</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        if st.session_state.logged_in:
            # معلومات المستخدم
            role_icon = "👨‍🏫" if st.session_state.role == "coach" else "👤"
            role_text = "كابتن" if st.session_state.role == "coach" else "لاعب"
            
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 20px;">
                <p style="color: rgba(255,255,255,0.7); margin: 0; font-size: 12px;">مرحباً</p>
                <h4 style="color: white; margin: 5px 0; font-size: 16px;">{st.session_state.username}</h4>
                <span style="background: {'#28a745' if st.session_state.role == 'coach' else '#17a2b8'}; color: white; padding: 3px 12px; border-radius: 15px; font-size: 11px;">
                    {role_icon} {role_text}
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 📋 القائمة")
            
            # أزرار التنقل للكابتن
            if st.session_state.role == "coach":
                pages = {
                    "dashboard": "📊 لوحة التحكم",
                    "attendance": "✅ تسجيل الحضور",
                    "attendance_history": "📋 سجل الحضور",
                    "subscriptions": "💳 الاشتراكات",
                    "payments": "💰 المدفوعات",
                    "players": "👥 إدارة اللاعبين"
                }
            else:
                # أزرار التنقل للاعب
                pages = {
                    "dashboard": "📊 ملخصي",
                    "my_attendance": "📋 سجل الحضور",
                    "my_subscription": "💳 اشتراكي",
                    "my_payments": "💰 مدفوعاتي"
                }
            
            # عرض أزرار التنقل
            for page_key, page_label in pages.items():
                is_active = st.session_state.current_page == page_key
                btn_type = "primary" if is_active else "secondary"
                
                if st.button(page_label, key=f"nav_{page_key}", use_container_width=True, type=btn_type):
                    navigate_to(page_key)
            
            st.markdown("---")
            
            # زر تسجيل الخروج
            if st.button("🚪 تسجيل الخروج", key="btn_logout", use_container_width=True):
                logout()
                st.rerun()

# =============================================================================
# صفحات الكابتن
# =============================================================================
def coach_dashboard_page():
    """لوحة تحكم الكابتن - الصفحة الرئيسية"""
    st.markdown("# 📊 لوحة التحكم")
    st.markdown(f"مرحباً، **{st.session_state.username}** 👋")
    st.markdown("---")
    
    # جلب البيانات
    users = get_all_users()
    players = [u for u in users if u.get("role") == "player"]
    attendance = get_all_attendance()
    today_attendance = get_today_attendance()
    
    # عرض الإحصائيات
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{len(players)}</div>
            <div class="stat-label">👥 عدد اللاعبين</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        present_today = len([a for a in today_attendance if a.get("status") == "Present"])
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{present_today}</div>
            <div class="stat-label">✅ الحضور اليوم</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        absent_today = len([a for a in today_attendance if a.get("status") == "Absent"])
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{absent_today}</div>
            <div class="stat-label">❌ الغياب اليوم</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        not_recorded = len(players) - len(today_attendance)
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{max(0, not_recorded)}</div>
            <div class="stat-label">⏳ لم يُسجل</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # آخر سجلات الحضور
    st.markdown("### 📋 آخر سجلات الحضور")
    if attendance:
        df = pd.DataFrame(attendance[-10:])
        df = df.rename(columns={
            "player_name": "اللاعب",
            "date": "التاريخ",
            "status": "الحالة",
            "recorded_by": "سجل بواسطة"
        })
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x == "Present" else "❌ غائب")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات حضور بعد")

def coach_attendance_page():
    """صفحة تسجيل الحضور للكابتن"""
    st.markdown("# ✅ تسجيل الحضور والغياب")
    
    # جلب قائمة اللاعبين
    users = get_all_users()
    players = [u.get("username") for u in users if u.get("role") == "player"]
    
    if not players:
        st.warning("⚠️ لا يوجد لاعبين مسجلين في النظام")
        return
    
    # تاريخ التسجيل
    attendance_date = st.date_input("📅 تاريخ التسجيل", value=date.today())
    
    st.markdown("---")
    
    # Multi-select للاعبين الحاضرين
    st.markdown("### ✅ اللاعبون الحاضرون")
    present_players = st.multiselect(
        "اختر اللاعبين الحاضرين",
        players,
        key="present_select"
    )
    
    if st.button("✅ تسجيل الحضور للمحددين", key="btn_present"):
        if present_players:
            success, message = record_multiple_attendance(
                present_players, "Present", st.session_state.username
            )
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")
        else:
            st.warning("⚠️ يرجى اختيار لاعب واحد على الأقل")
    
    st.markdown("---")
    
    # Multi-select للاعبين الغائبين
    st.markdown("### ❌ اللاعبون الغائبون")
    remaining_players = [p for p in players if p not in present_players]
    
    absent_players = st.multiselect(
        "اختر اللاعبين الغائبين",
        remaining_players,
        key="absent_select"
    )
    
    if st.button("❌ تسجيل الغياب للمحددين", key="btn_absent"):
        if absent_players:
            success, message = record_multiple_attendance(
                absent_players, "Absent", st.session_state.username
            )
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")
        else:
            st.warning("⚠️ يرجى اختيار لاعب واحد على الأقل")
    
    st.markdown("---")
    
    # تسجيل فردي
    st.markdown("### 📝 تسجيل فردي")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        single_player = st.selectbox("اختر اللاعب", players, key="single_player")
    
    with col2:
        single_status = st.selectbox("الحالة", ["Present", "Absent"], 
                                      format_func=lambda x: "✅ حاضر" if x == "Present" else "❌ غائب",
                                      key="single_status")
    
    with col3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("تسجيل", key="btn_single"):
            success, message = record_attendance(single_player, single_status, st.session_state.username)
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")

def coach_attendance_history_page():
    """صفحة سجل الحضور للكابتن"""
    st.markdown("# 📋 سجل الحضور")
    
    # فلاتر البحث
    col1, col2, col3 = st.columns(3)
    
    users = get_all_users()
    players = ["الكل"] + [u.get("username") for u in users if u.get("role") == "player"]
    
    with col1:
        filter_player = st.selectbox("اللاعب", players)
    
    with col2:
        filter_status = st.selectbox("الحالة", ["الكل", "Present", "Absent"],
                                      format_func=lambda x: "الكل" if x == "الكل" else ("✅ حاضر" if x == "Present" else "❌ غائب"))
    
    with col3:
        filter_date = st.date_input("التاريخ", value=None)
    
    # جلب البيانات
    attendance = get_all_attendance()
    
    # تطبيق الفلاتر
    filtered = attendance
    if filter_player != "الكل":
        filtered = [a for a in filtered if a.get("player_name") == filter_player]
    if filter_status != "الكل":
        filtered = [a for a in filtered if a.get("status") == filter_status]
    if filter_date:
        filtered = [a for a in filtered if a.get("date") == filter_date.strftime("%Y-%m-%d")]
    
    # عرض البيانات
    if filtered:
        df = pd.DataFrame(filtered)
        df = df.rename(columns={
            "player_name": "اللاعب",
            "date": "التاريخ",
            "status": "الحالة",
            "recorded_by": "سجل بواسطة",
            "created_at": "وقت التسجيل"
        })
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x == "Present" else "❌ غائب")
        st.dataframe(df.sort_values("التاريخ", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات مطابقة للفلاتر المحددة")
    
    # إحصائيات الغياب
    st.markdown("---")
    st.markdown("## 📊 إحصائيات الغياب")
    
    if attendance:
        players_stats = {}
        for record in attendance:
            player = record.get("player_name")
            if player not in players_stats:
                players_stats[player] = {"total": 0, "absent": 0}
            players_stats[player]["total"] += 1
            if record.get("status") == "Absent":
                players_stats[player]["absent"] += 1
        
        stats_data = []
        for player, stats in players_stats.items():
            absent_rate = (stats["absent"] / stats["total"] * 100) if stats["total"] > 0 else 0
            stats_data.append({
                "اللاعب": player,
                "إجمالي الحصص": stats["total"],
                "عدد الغيابات": stats["absent"],
                "نسبة الغياب (%)": round(absent_rate, 1)
            })
        
        df_stats = pd.DataFrame(stats_data)
        df_stats = df_stats.sort_values("نسبة الغياب (%)", ascending=False)
        st.dataframe(df_stats, use_container_width=True, hide_index=True)

def coach_subscriptions_page():
    """صفحة إدارة الاشتراكات للكابتن"""
    st.markdown("# 💳 إدارة الاشتراكات")
    
    tab1, tab2 = st.tabs(["📋 عرض الاشتراكات", "➕ إضافة/تعديل اشتراك"])
    
    with tab1:
        subscriptions = get_all_subscriptions()
        if subscriptions:
            df = pd.DataFrame(subscriptions)
            df = df.rename(columns={
                "player_name": "اللاعب",
                "monthly_fee": "الرسوم الشهرية",
                "start_date": "تاريخ البدء",
                "end_date": "تاريخ الانتهاء",
                "subscription_status": "الحالة",
                "updated_at": "آخر تحديث"
            })
            
            def status_color(status):
                if status == "Active":
                    return "🟢 نشط"
                elif status == "Expired":
                    return "🔴 منتهي"
                else:
                    return "🟡 معلق"
            
            df["الحالة"] = df["الحالة"].apply(status_color)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد اشتراكات مسجلة")
    
    with tab2:
        st.markdown("### ➕ إضافة أو تعديل اشتراك")
        
        users = get_all_users()
        players = [u.get("username") for u in users if u.get("role") == "player"]
        
        if not players:
            st.warning("⚠️ لا يوجد لاعبين مسجلين")
            return
        
        selected_player = st.selectbox("اختر اللاعب", players, key="sub_player")
        
        current_sub = get_player_subscription(selected_player)
        
        col1, col2 = st.columns(2)
        
        with col1:
            monthly_fee = st.number_input(
                "الرسوم الشهرية (جنيه)",
                min_value=0.0,
                value=float(current_sub.get("monthly_fee", 0)) if current_sub else 0.0,
                step=50.0
            )
        
        with col2:
            status_options = ["Active", "Expired", "Suspended"]
            status_index = 0
            if current_sub:
                try:
                    status_index = status_options.index(current_sub.get("subscription_status", "Active"))
                except:
                    status_index = 0
                    
            status = st.selectbox(
                "حالة الاشتراك",
                status_options,
                index=status_index,
                format_func=lambda x: "🟢 نشط" if x == "Active" else ("🔴 منتهي" if x == "Expired" else "🟡 معلق")
            )
        
        col3, col4 = st.columns(2)
        
        with col3:
            default_start = date.today()
            if current_sub and current_sub.get("start_date"):
                try:
                    default_start = datetime.strptime(current_sub.get("start_date"), "%Y-%m-%d").date()
                except:
                    pass
            start_date = st.date_input("تاريخ البدء", value=default_start)
        
        with col4:
            default_end = date.today() + timedelta(days=30)
            if current_sub and current_sub.get("end_date"):
                try:
                    default_end = datetime.strptime(current_sub.get("end_date"), "%Y-%m-%d").date()
                except:
                    pass
            end_date = st.date_input("تاريخ الانتهاء", value=default_end)
        
        if st.button("💾 حفظ الاشتراك", key="btn_save_sub"):
            success, message = add_or_update_subscription(
                selected_player,
                monthly_fee,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                status
            )
            if success:
                st.success(f"✅ {message}")
            else:
                st.error(f"❌ {message}")

def coach_payments_page():
    """صفحة المدفوعات للكابتن"""
    st.markdown("# 💰 إدارة المدفوعات")
    
    tab1, tab2 = st.tabs(["📋 سجل المدفوعات", "➕ تسجيل دفعة جديدة"])
    
    with tab1:
        payments = get_all_payments()
        if payments:
            df = pd.DataFrame(payments)
            df = df.rename(columns={
                "player_name": "اللاعب",
                "amount": "المبلغ",
                "payment_method": "طريقة الدفع",
                "payment_date": "تاريخ الدفع",
                "notes": "ملاحظات",
                "recorded_by": "سجل بواسطة"
            })
            
            payment_methods = {
                "Cash": "💵 نقدي",
                "InstaPay": "📱 إنستا باي",
                "Vodafone Cash": "📲 فودافون كاش",
                "Bank Transfer": "🏦 تحويل بنكي",
                "Other": "📝 أخرى"
            }
            df["طريقة الدفع"] = df["طريقة الدفع"].apply(lambda x: payment_methods.get(x, x))
            
            st.dataframe(df.sort_values("تاريخ الدفع", ascending=False), use_container_width=True, hide_index=True)
            
            total = df["المبلغ"].sum()
            st.markdown(f"### 💵 إجمالي المدفوعات: **{total:,.0f} جنيه**")
        else:
            st.info("لا توجد مدفوعات مسجلة")
    
    with tab2:
        st.markdown("### ➕ تسجيل دفعة جديدة")
        
        users = get_all_users()
        players = [u.get("username") for u in users if u.get("role") == "player"]
        
        if not players:
            st.warning("⚠️ لا يوجد لاعبين مسجلين")
            return
        
        selected_player = st.selectbox("اختر اللاعب", players, key="pay_player")
        
        summary = get_payment_summary(selected_player)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("الرسوم الشهرية", f"{summary['monthly_fee']:,.0f} جنيه")
        with col2:
            st.metric("إجمالي المدفوع", f"{summary['total_paid']:,.0f} جنيه")
        with col3:
            st.metric("المتبقي", f"{summary['remaining']:,.0f} جنيه")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            amount = st.number_input("المبلغ (جنيه)", min_value=0.0, step=50.0)
        
        with col2:
            payment_method = st.selectbox(
                "طريقة الدفع",
                ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"],
                format_func=lambda x: {
                    "Cash": "💵 نقدي",
                    "InstaPay": "📱 إنستا باي",
                    "Vodafone Cash": "📲 فودافون كاش",
                    "Bank Transfer": "🏦 تحويل بنكي",
                    "Other": "📝 أخرى"
                }.get(x, x)
            )
        
        payment_date = st.date_input("تاريخ الدفع", value=date.today())
        notes = st.text_area("ملاحظات", placeholder="أي ملاحظات إضافية...")
        
        if st.button("💾 تسجيل الدفعة", key="btn_save_payment"):
            if amount <= 0:
                st.error("❌ يرجى إدخال مبلغ صحيح")
            else:
                success, message = record_payment(
                    selected_player,
                    amount,
                    payment_method,
                    payment_date.strftime("%Y-%m-%d"),
                    notes,
                    st.session_state.username
                )
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")

def coach_players_page():
    """صفحة إدارة اللاعبين للكابتن"""
    st.markdown("# 👥 إدارة اللاعبين")
    
    users = get_all_users()
    players = [u for u in users if u.get("role") == "player"]
    
    if not players:
        st.info("لا يوجد لاعبين مسجلين")
        return
    
    players_data = []
    for player in players:
        name = player.get("username")
        attendance_stats = get_attendance_stats(name)
        payment_summary = get_payment_summary(name)
        subscription = get_player_subscription(name)
        
        players_data.append({
            "اللاعب": name,
            "نسبة الحضور": f"{attendance_stats['percentage']}%",
            "الاشتراك": "🟢 نشط" if subscription and subscription.get("subscription_status") == "Active" else "🔴 غير نشط",
            "الرسوم": f"{payment_summary['monthly_fee']:,.0f} جنيه" if payment_summary['monthly_fee'] > 0 else "-",
            "المدفوع": f"{payment_summary['total_paid']:,.0f} جنيه",
            "المتبقي": f"{payment_summary['remaining']:,.0f} جنيه"
        })
    
    df = pd.DataFrame(players_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("### 🔍 تفاصيل لاعب")
    
    selected = st.selectbox("اختر اللاعب", [p.get("username") for p in players])
    
    if selected:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 إحصائيات الحضور")
            stats = get_attendance_stats(selected)
            st.write(f"- إجمالي الحصص: **{stats['total']}**")
            st.write(f"- الحضور: **{stats['present']}**")
            st.write(f"- الغياب: **{stats['absent']}**")
            st.write(f"- نسبة الحضور: **{stats['percentage']}%**")
        
        with col2:
            st.markdown("#### 💳 بيانات الاشتراك")
            sub = get_player_subscription(selected)
            if sub:
                st.write(f"- الرسوم الشهرية: **{float(sub.get('monthly_fee', 0)):,.0f} جنيه**")
                st.write(f"- تاريخ البدء: **{sub.get('start_date', '-')}**")
                st.write(f"- تاريخ الانتهاء: **{sub.get('end_date', '-')}**")
                st.write(f"- الحالة: **{'🟢 نشط' if sub.get('subscription_status') == 'Active' else '🔴 غير نشط'}**")
            else:
                st.write("لا يوجد اشتراك مسجل")

# =============================================================================
# صفحات اللاعب
# =============================================================================
def player_dashboard_page():
    """صفحة ملخص اللاعب"""
    st.markdown("# 📊 ملخص بياناتي")
    st.markdown(f"مرحباً، **{st.session_state.username}** 👋")
    st.markdown("---")
    
    username = st.session_state.username
    
    attendance_stats = get_attendance_stats(username)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{attendance_stats['percentage']}%</div>
            <div class="stat-label">📊 نسبة الحضور</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{attendance_stats['present']}</div>
            <div class="stat-label">✅ عدد الحضور</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{attendance_stats['absent']}</div>
            <div class="stat-label">❌ عدد الغياب</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("## 💳 بيانات الاشتراك")
    
    subscription = get_player_subscription(username)
    payment_summary = get_payment_summary(username)
    
    if subscription:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("الرسوم الشهرية", f"{payment_summary['monthly_fee']:,.0f} جنيه")
        
        with col2:
            st.metric("إجمالي المدفوع", f"{payment_summary['total_paid']:,.0f} جنيه")
        
        with col3:
            st.metric("المتبقي", f"{payment_summary['remaining']:,.0f} جنيه")
        
        with col4:
            status_color = "🟢" if payment_summary['status'] == "Active" else "🔴"
            st.metric("حالة الاشتراك", f"{status_color} {payment_summary['status']}")
        
        st.markdown("---")
        st.write(f"**تاريخ البدء:** {subscription.get('start_date', '-')}")
        st.write(f"**تاريخ الانتهاء:** {subscription.get('end_date', '-')}")
    else:
        st.info("ℹ️ لم يتم تسجيل اشتراك لك بعد. تواصل مع الكابتن للتفعيل.")

def player_attendance_page():
    """صفحة سجل حضور اللاعب"""
    st.markdown("# 📋 سجل الحضور")
    
    username = st.session_state.username
    attendance = get_player_attendance(username)
    
    if attendance:
        df = pd.DataFrame(attendance)
        df = df.rename(columns={
            "date": "التاريخ",
            "status": "الحالة",
            "recorded_by": "سجل بواسطة"
        })
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x == "Present" else "❌ غائب")
        
        st.dataframe(df.sort_values("التاريخ", ascending=False), use_container_width=True, hide_index=True)
        
        stats = get_attendance_stats(username)
        st.markdown("---")
        st.markdown(f"### 📊 الإحصائيات")
        st.write(f"- إجمالي الحصص: **{stats['total']}**")
        st.write(f"- الحضور: **{stats['present']}** ✅")
        st.write(f"- الغياب: **{stats['absent']}** ❌")
        st.write(f"- نسبة الحضور: **{stats['percentage']}%** 📊")
    else:
        st.info("لا توجد سجلات حضور مسجلة لك بعد")

def player_subscription_page():
    """صفحة اشتراك اللاعب"""
    st.markdown("# 💳 اشتراكي")
    
    username = st.session_state.username
    subscription = get_player_subscription(username)
    
    if subscription:
        st.markdown("### 📋 تفاصيل الاشتراك")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div class="card">
                <h4>💰 الرسوم الشهرية</h4>
                <h2>{float(subscription.get("monthly_fee", 0)):,.0f} جنيه</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            status = subscription.get("subscription_status", "Unknown")
            status_text = "🟢 نشط" if status == "Active" else ("🔴 منتهي" if status == "Expired" else "🟡 معلق")
            st.markdown(f"""
            <div class="card">
                <h4>📊 الحالة</h4>
                <h2>{status_text}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📅 تواريخ الاشتراك")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**تاريخ البدء:** {subscription.get('start_date', '-')}")
        
        with col2:
            st.write(f"**تاريخ الانتهاء:** {subscription.get('end_date', '-')}")
        
        try:
            end_date = datetime.strptime(subscription.get('end_date', '2000-01-01'), '%Y-%m-%d').date()
            if end_date < date.today():
                st.warning("⚠️ اشتراكك منتهي! يرجى التواصل مع الكابتن للتجديد.")
            elif (end_date - date.today()).days <= 7:
                st.warning(f"⚠️ اشتراكك على وشك الانتهاء! متبقي {(end_date - date.today()).days} أيام.")
        except:
            pass
    else:
        st.info("ℹ️ لم يتم تسجيل اشتراك لك بعد. تواصل مع الكابتن للتفعيل.")

def player_payments_page():
    """صفحة مدفوعات اللاعب"""
    st.markdown("# 💰 سجل المدفوعات")
    
    username = st.session_state.username
    payments = get_player_payments(username)
    
    summary = get_payment_summary(username)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("الرسوم الشهرية", f"{summary['monthly_fee']:,.0f} جنيه")
    
    with col2:
        st.metric("إجمالي المدفوع", f"{summary['total_paid']:,.0f} جنيه")
    
    with col3:
        st.metric("المتبقي", f"{summary['remaining']:,.0f} جنيه")
    
    st.markdown("---")
    
    st.markdown("### 📋 تفاصيل المدفوعات")
    
    if payments:
        df = pd.DataFrame(payments)
        df = df.rename(columns={
            "amount": "المبلغ",
            "payment_method": "طريقة الدفع",
            "payment_date": "تاريخ الدفع",
            "notes": "ملاحظات"
        })
        
        payment_methods = {
            "Cash": "💵 نقدي",
            "InstaPay": "📱 إنستا باي",
            "Vodafone Cash": "📲 فودافون كاش",
            "Bank Transfer": "🏦 تحويل بنكي",
            "Other": "📝 أخرى"
        }
        df["طريقة الدفع"] = df["طريقة الدفع"].apply(lambda x: payment_methods.get(x, x))
        
        st.dataframe(df.sort_values("تاريخ الدفع", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد مدفوعات مسجلة لك بعد")

# =============================================================================
# صفحة تسجيل الدخول
# =============================================================================
def login_page():
    """صفحة تسجيل الدخول"""
    # إخفاء الشريط الجانبي في صفحة تسجيل الدخول
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="login-container">
        <div class="logo-container">
            <div class="logo">⚽</div>
            <div class="title">الكوتش أكاديمي</div>
            <div class="subtitle">نظام إدارة الحضور والاشتراكات</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 تسجيل الدخول", "📝 تسجيل حساب جديد"])
    
    with tab1:
        st.markdown("### تسجيل الدخول")
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)", key="login_username", 
                                  placeholder="مثال: أحمد محمد علي")
        password = st.text_input("كلمة المرور", type="password", key="login_password")
        
        if st.button("تسجيل الدخول", key="btn_login"):
            if not username or not password:
                st.error("❌ يرجى إدخال اسم المستخدم وكلمة المرور")
            else:
                if login(username, password):
                    st.success("✅ تم تسجيل الدخول بنجاح!")
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    with tab2:
        st.markdown("### تسجيل حساب جديد")
        new_username = st.text_input("الاسم الثلاثي", key="reg_username",
                                      placeholder="مثال: أحمد محمد علي")
        new_password = st.text_input("كلمة المرور", type="password", key="reg_password")
        confirm_password = st.text_input("تأكيد كلمة المرور", type="password", key="reg_confirm")
        role = st.selectbox("نوع الحساب", ["player", "coach"], 
                           format_func=lambda x: "👤 لاعب" if x == "player" else "👨‍🏫 كابتن")
        
        if st.button("تسجيل الحساب", key="btn_register"):
            if not new_username or not new_password:
                st.error("❌ يرجى ملء جميع الحقول")
            elif not validate_triple_name(new_username):
                st.error("❌ الاسم يجب أن يكون ثلاثياً (ثلاث كلمات عربية)")
            elif new_password != confirm_password:
                st.error("❌ كلمات المرور غير متطابقة")
            elif len(new_password) < 6:
                st.error("❌ كلمة المرور يجب أن تكون 6 أحرف على الأقل")
            else:
                success, message = add_user(new_username, new_password, role)
                if success:
                    st.success(f"✅ {message}")
                    st.info("🎉 يمكنك الآن تسجيل الدخول باستخدام بياناتك")
                else:
                    st.error(f"❌ {message}")

# =============================================================================
# الدالة الرئيسية
# =============================================================================
def main():
    """الدالة الرئيسية للتطبيق"""
    init_session()
    
    # عرض الشريط الجانبي فقط إذا كان المستخدم مسجل الدخول
    if st.session_state.logged_in:
        sidebar()
    
    # توجيه المستخدم حسب حالة تسجيل الدخول والصفحة المطلوبة
    if not st.session_state.logged_in:
        login_page()
    else:
        # توجيه المستخدم حسب نوع الحساب والصفحة المطلوبة
        if st.session_state.role == "coach":
            if st.session_state.current_page == "dashboard":
                coach_dashboard_page()
            elif st.session_state.current_page == "attendance":
                coach_attendance_page()
            elif st.session_state.current_page == "attendance_history":
                coach_attendance_history_page()
            elif st.session_state.current_page == "subscriptions":
                coach_subscriptions_page()
            elif st.session_state.current_page == "payments":
                coach_payments_page()
            elif st.session_state.current_page == "players":
                coach_players_page()
            else:
                coach_dashboard_page()
        else:
            if st.session_state.current_page == "dashboard":
                player_dashboard_page()
            elif st.session_state.current_page == "my_attendance":
                player_attendance_page()
            elif st.session_state.current_page == "my_subscription":
                player_subscription_page()
            elif st.session_state.current_page == "my_payments":
                player_payments_page()
            else:
                player_dashboard_page()

# =============================================================================
# تشغيل التطبيق
# =============================================================================
if __name__ == "__main__":
    main()
