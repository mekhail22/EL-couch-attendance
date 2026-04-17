"""
الكوتش أكاديمي - نظام إدارة الحضور والاشتراكات الموسمية
=====================================================
تطبيق Streamlit لإدارة الحضور والاشتراكات لأكاديمية كرة القدم

**إعدادات secrets.toml المطلوبة:**
-----------------------------------
[google]
spreadsheet_id = "YOUR_SPREADSHEET_ID"

[google.service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"

[app]
finance_password = "123456"   # كلمة المرور للتقارير المالية
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import pandas as pd
import re
import os
import base64
import time
from functools import wraps

# =============================================================================
# إعدادات الصفحة
# =============================================================================
st.set_page_config(
    page_title="الكوتش أكاديمي",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================================================================
# دوال مساعدة للتخزين المؤقت وإعادة المحاولة
# =============================================================================
def retry_on_quota(func, max_retries=3, delay=2):
    """إعادة محاولة تنفيذ الدالة عند حدوث خطأ quota"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                else:
                    raise e
        return None
    return wrapper

# =============================================================================
# دوال Google Sheets مع التخزين المؤقت
# =============================================================================
def get_google_sheets_client():
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
    except Exception as e:
        st.error(f"❌ خطأ في قراءة الإعدادات: {str(e)}")
        return None, None
    
    try:
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(credentials)
        return client, spreadsheet_id
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بـ Google Sheets: {str(e)}")
        return None, None

@st.cache_resource
def get_workbook():
    client, spreadsheet_id = get_google_sheets_client()
    if client and spreadsheet_id:
        try:
            return client.open_by_key(spreadsheet_id)
        except Exception as e:
            st.error(f"❌ خطأ في فتح ملف Sheets: {str(e)}")
    return None

def init_sheets():
    workbook = get_workbook()
    if not workbook:
        return False
    try:
        required_sheets = {
            "Users": ["username", "password", "role", "created_at"],
            "Attendance": ["player_name", "date", "status", "recorded_by", "created_at"],
            "Subscriptions": ["player_name", "season_fee", "start_date", "end_date", "subscription_status", "updated_at"],
            "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes", "recorded_by", "created_at"]
        }
        existing_sheets = [sheet.title for sheet in workbook.worksheets()]
        for sheet_name, headers in required_sheets.items():
            if sheet_name not in existing_sheets:
                sheet = workbook.add_worksheet(title=sheet_name, rows=1000, cols=20)
                sheet.append_row(headers)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في تهيئة Sheets: {str(e)}")
        return False

# =============================================================================
# دوال قراءة البيانات مع التخزين المؤقت (لتقليل استدعاءات API)
# =============================================================================
@st.cache_data(ttl=60)
def get_users_sheet_data():
    workbook = get_workbook()
    if workbook:
        try:
            sheet = workbook.worksheet("Users")
            return sheet.get_all_records()
        except:
            return []
    return []

@st.cache_data(ttl=60)
def get_attendance_sheet_data():
    workbook = get_workbook()
    if workbook:
        try:
            sheet = workbook.worksheet("Attendance")
            return sheet.get_all_records()
        except:
            return []
    return []

@st.cache_data(ttl=60)
def get_subscriptions_sheet_data():
    workbook = get_workbook()
    if workbook:
        try:
            sheet = workbook.worksheet("Subscriptions")
            return sheet.get_all_records()
        except:
            return []
    return []

@st.cache_data(ttl=60)
def get_payments_sheet_data():
    workbook = get_workbook()
    if workbook:
        try:
            sheet = workbook.worksheet("Payments")
            return sheet.get_all_records()
        except:
            return []
    return []

# دوال مساعدة لتنظيف البيانات
def clean_records(records):
    cleaned = []
    for row in records:
        cleaned_row = {}
        for k, v in row.items():
            if isinstance(v, str):
                cleaned_row[k] = v.strip()
            else:
                cleaned_row[k] = v
        cleaned.append(cleaned_row)
    return cleaned

def get_all_users():
    return clean_records(get_users_sheet_data())

def get_all_attendance():
    return clean_records(get_attendance_sheet_data())

def get_all_subscriptions():
    return clean_records(get_subscriptions_sheet_data())

def get_all_payments():
    return clean_records(get_payments_sheet_data())

# =============================================================================
# دوال الكتابة (مع إعادة المحاولة)
# =============================================================================
@retry_on_quota
def append_row_to_sheet(sheet_name, row_data):
    workbook = get_workbook()
    if workbook:
        sheet = workbook.worksheet(sheet_name)
        sheet.append_row(row_data)
        # مسح ذاكرة التخزين المؤقت بعد الكتابة
        st.cache_data.clear()
        return True
    return False

@retry_on_quota
def update_cell_in_sheet(sheet_name, row, col, value):
    workbook = get_workbook()
    if workbook:
        sheet = workbook.worksheet(sheet_name)
        sheet.update_cell(row, col, value)
        st.cache_data.clear()
        return True
    return False

# =============================================================================
# دوال المستخدمين
# =============================================================================
def get_user(username: str):
    users = get_all_users()
    username_clean = username.strip() if username else ""
    for user in users:
        if user.get("username", "").strip() == username_clean:
            return user
    return None

def check_coach_exists():
    users = get_all_users()
    for user in users:
        if user.get("role", "").strip() == "coach":
            return True
    return False

def add_user(username: str, password: str, role: str = "player"):
    username = username.strip() if username else ""
    password = password.strip() if password else ""
    
    existing = get_user(username)
    if existing:
        return False, "اسم المستخدم موجود بالفعل"
    
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if append_row_to_sheet("Users", [username, password, role, created_at]):
        return True, f"تم إضافة المستخدم بنجاح كـ {'كابتن' if role == 'coach' else 'لاعب'}"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def validate_triple_name(name: str) -> bool:
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
    today = datetime.now().strftime("%Y-%m-%d")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # التحقق من التسجيل المسبق
    records = get_all_attendance()
    for r in records:
        if r.get("player_name", "").strip() == player_name.strip() and r.get("date") == today:
            return False, "تم تسجيل الحضور مسبقاً لهذا اليوم"
    
    if append_row_to_sheet("Attendance", [player_name.strip(), today, status, recorded_by.strip(), created_at]):
        return True, f"تم تسجيل {'الحضور' if status == 'Present' else 'الغياب'} بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def record_multiple_attendance(player_names: list, status: str, recorded_by: str):
    today = datetime.now().strftime("%Y-%m-%d")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = get_all_attendance()
    success_count = 0
    for player_name in player_names:
        exists = False
        for r in records:
            if r.get("player_name", "").strip() == player_name.strip() and r.get("date") == today:
                exists = True
                break
        if not exists:
            if append_row_to_sheet("Attendance", [player_name.strip(), today, status, recorded_by.strip(), created_at]):
                success_count += 1
    return True, f"تم تسجيل {success_count} من {len(player_names)} لاعبين"

def get_player_attendance(player_name: str):
    records = get_all_attendance()
    return [r for r in records if r.get("player_name", "").strip() == player_name.strip()]

def get_attendance_stats(player_name: str):
    records = get_player_attendance(player_name)
    if not records:
        return {"total": 0, "present": 0, "absent": 0, "percentage": 0}
    total = len(records)
    present = len([r for r in records if r.get("status") == "Present"])
    absent = total - present
    percentage = (present / total * 100) if total > 0 else 0
    return {"total": total, "present": present, "absent": absent, "percentage": round(percentage, 1)}

def get_today_attendance():
    today = datetime.now().strftime("%Y-%m-%d")
    records = get_all_attendance()
    return [r for r in records if r.get("date") == today]

# =============================================================================
# دوال الاشتراكات الموسمية
# =============================================================================
def get_player_subscription(player_name: str):
    records = get_all_subscriptions()
    for r in records:
        if r.get("player_name", "").strip() == player_name.strip():
            return r
    return None

def add_or_update_subscription(player_name: str, season_fee: float, start_date: str, end_date: str, status: str = "Active"):
    workbook = get_workbook()
    if not workbook:
        return False, "خطأ في الاتصال بقاعدة البيانات"
    sheet = workbook.worksheet("Subscriptions")
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        all_records = get_all_subscriptions()
        row_idx = None
        for idx, record in enumerate(all_records, start=2):
            if record.get("player_name", "").strip() == player_name.strip():
                row_idx = idx
                break
        
        if row_idx:
            update_cell_in_sheet("Subscriptions", row_idx, 2, season_fee)
            update_cell_in_sheet("Subscriptions", row_idx, 3, start_date)
            update_cell_in_sheet("Subscriptions", row_idx, 4, end_date)
            update_cell_in_sheet("Subscriptions", row_idx, 5, status)
            update_cell_in_sheet("Subscriptions", row_idx, 6, updated_at)
            return True, "تم تحديث الاشتراك بنجاح"
        else:
            append_row_to_sheet("Subscriptions", [player_name.strip(), season_fee, start_date, end_date, status, updated_at])
            return True, "تم إضافة الاشتراك بنجاح"
    except Exception as e:
        return False, f"خطأ: {str(e)}"

# =============================================================================
# دوال المدفوعات
# =============================================================================
def record_payment(player_name: str, amount: float, payment_method: str, payment_date: str, notes: str = "", recorded_by: str = ""):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if append_row_to_sheet("Payments", [player_name.strip(), amount, payment_method, payment_date, notes, recorded_by.strip(), created_at]):
        return True, "تم تسجيل الدفعة بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def get_player_payments(player_name: str):
    records = get_all_payments()
    return [r for r in records if r.get("player_name", "").strip() == player_name.strip()]

def get_payment_summary(player_name: str):
    subscription = get_player_subscription(player_name)
    payments = get_player_payments(player_name)
    if not subscription:
        return {"season_fee": 0, "total_paid": 0, "remaining": 0, "status": "No Subscription"}
    try:
        season_fee = float(subscription.get("season_fee", 0))
    except:
        season_fee = 0
    try:
        total_paid = sum(float(p.get("amount", 0)) for p in payments)
    except:
        total_paid = 0
    remaining = max(0, season_fee - total_paid)
    return {"season_fee": season_fee, "total_paid": total_paid, "remaining": remaining, "status": subscription.get("subscription_status", "Unknown")}

# =============================================================================
# تهيئة الجلسة
# =============================================================================
def init_session():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"
    if "finance_authenticated" not in st.session_state:
        st.session_state.finance_authenticated = False

def login(username: str, password: str):
    username = username.strip() if username else ""
    password = password.strip() if password else ""
    user = get_user(username)
    if user and user.get("password", "").strip() == password:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.role = user.get("role", "player").strip()
        st.session_state.current_page = "dashboard"
        st.session_state.finance_authenticated = False  # إعادة تعيين المصادقة المالية
        return True, "تم تسجيل الدخول بنجاح"
    return False, "اسم المستخدم أو كلمة المرور غير صحيحة"

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.current_page = "login"
    st.session_state.finance_authenticated = False
    st.rerun()

def navigate_to(page: str):
    st.session_state.current_page = page
    st.rerun()

# =============================================================================
# دالة عرض الشعار
# =============================================================================
def get_logo_html(width=50):
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                return f'<img src="data:image/jpeg;base64,{b64}" style="width:{width}px; height:auto; border-radius:10px;">'
        except:
            pass
    return f'<span style="font-size:{width}px;">⚽</span>'

# =============================================================================
# CSS مخصص
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    * { font-family: 'Cairo', sans-serif !important; }
    .main { direction: rtl; }
    .stApp { background: linear-gradient(135deg, #1a5f3f 0%, #0d3321 100%); }
    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .stDeployButton, .stActionButton, #MainMenu, footer,
    div[data-testid="stToolbar"], div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"] { display: none !important; }
    
    .nav-container {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 50px;
        padding: 10px 20px;
        margin: 20px 0;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .nav-container .stButton > button {
        background: transparent !important;
        color: white !important;
        border: 2px solid rgba(255,255,255,0.3) !important;
        border-radius: 30px !important;
        padding: 10px 15px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        width: 100% !important;
    }
    .nav-container .stButton > button:hover {
        background: white !important;
        color: #1a5f3f !important;
        border-color: white !important;
    }
    
    .login-container {
        max-width: 450px;
        margin: 50px auto;
        padding: 40px;
        background: rgba(255, 255, 255, 0.98);
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        text-align: center;
    }
    .logo-login { margin-bottom: 20px; }
    .title { color: #1a5f3f; font-size: 32px; font-weight: 700; margin-bottom: 5px; }
    .subtitle { color: #666; font-size: 16px; margin-bottom: 30px; }
    
    .stat-card {
        background: linear-gradient(135deg, #1a5f3f 0%, #0d3321 100%);
        color: white;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
    }
    .stat-number { font-size: 36px; font-weight: 700; margin-bottom: 5px; }
    .stat-label { font-size: 14px; opacity: 0.9; }
    
    .welcome-box {
        background: linear-gradient(135deg, #1a5f3f 0%, #0d3321 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
        text-align: center;
    }
    .info-box {
        background: #e3f2fd;
        border-right: 4px solid #2196f3;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
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
    }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(26, 95, 63, 0.4); }
    
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 12px 15px;
        text-align: right;
    }
    .stTextInput > div > div > input:focus { border-color: #1a5f3f; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,0.1);
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
        color: white;
    }
    .stTabs [aria-selected="true"] { background: white !important; color: #1a5f3f !important; }
    .user-info { color: white; font-size: 16px; font-weight: 600; padding: 10px 0; text-align: center; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# شريط التنقل
# =============================================================================
def navigation_bar():
    col_logo, col_title, col_user = st.columns([0.5, 2, 1])
    with col_logo:
        st.markdown(get_logo_html(50), unsafe_allow_html=True)
    with col_title:
        st.markdown('<h2 style="color:white; margin:0; font-size:24px;">الكوتش أكاديمي</h2>', unsafe_allow_html=True)
    with col_user:
        role_icon = "👨‍🏫" if st.session_state.role == "coach" else "👤"
        role_text = "كابتن" if st.session_state.role == "coach" else "لاعب"
        st.markdown(f'<div class="user-info">{role_icon} {st.session_state.username} ({role_text})</div>', unsafe_allow_html=True)
    
    if st.session_state.role == "coach":
        pages = {
            "dashboard": "📊 لوحة التحكم",
            "attendance": "✅ تسجيل الحضور",
            "attendance_history": "📋 سجل الحضور",
            "subscriptions_payments": "💳 الاشتراكات والمدفوعات",
            "players": "👥 إدارة اللاعبين",
            "finance_reports": "📊 التقارير المالية"
        }
    else:
        pages = {
            "dashboard": "📊 ملخصي",
            "my_attendance": "📋 سجل الحضور",
            "my_subscription": "💳 اشتراكي ومدفوعاتي"
        }
    
    with st.container():
        st.markdown('<div class="nav-container">', unsafe_allow_html=True)
        num_buttons = len(pages) + 1
        cols = st.columns(num_buttons)
        for idx, (page_key, page_label) in enumerate(pages.items()):
            with cols[idx]:
                is_active = (st.session_state.current_page == page_key)
                if st.button(page_label, key=f"nav_{page_key}", use_container_width=True, type="primary" if is_active else "secondary"):
                    navigate_to(page_key)
        with cols[-1]:
            if st.button("🚪 تسجيل الخروج", key="nav_logout", use_container_width=True):
                logout()
        st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# صفحة المصادقة المالية (تظهر فقط إذا لم يتم التحقق)
# =============================================================================
def finance_auth_wall():
    st.markdown("## 🔐 المصادقة المطلوبة")
    st.markdown("الرجاء إدخال كلمة المرور للوصول إلى التقارير المالية.")
    password = st.text_input("كلمة المرور", type="password", key="finance_pass_input")
    if st.button("تحقق", key="finance_auth_btn"):
        correct_password = st.secrets.get("app", {}).get("finance_password", "")
        if password == correct_password:
            st.session_state.finance_authenticated = True
            st.rerun()
        else:
            st.error("❌ كلمة المرور غير صحيحة")
    st.stop()

# =============================================================================
# صفحة التقارير المالية (للكابتن فقط، محمية)
# =============================================================================
def coach_finance_reports_page():
    if not st.session_state.get("finance_authenticated", False):
        finance_auth_wall()
        return
    
    st.markdown("# 📊 التقارير المالية")
    st.markdown("### ملخص الاشتراكات الموسمية والمدفوعات")
    
    subs = get_all_subscriptions()
    payments = get_all_payments()
    
    total_season_fee = sum(float(s.get("season_fee", 0)) for s in subs)
    total_paid = sum(float(p.get("amount", 0)) for p in payments)
    total_remaining = max(0, total_season_fee - total_paid)
    collection_rate = (total_paid / total_season_fee * 100) if total_season_fee > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_season_fee:,.0f}</div><div class="stat-label">💰 إجمالي المستحق</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_paid:,.0f}</div><div class="stat-label">💵 إجمالي المدفوع</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_remaining:,.0f}</div><div class="stat-label">📉 إجمالي المتبقي</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{collection_rate:.1f}%</div><div class="stat-label">📈 نسبة التحصيل</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📋 تفاصيل اللاعبين")
    
    players_data = []
    users = get_all_users()
    player_names = [u["username"].strip() for u in users if u.get("role") == "player"]
    
    for name in player_names:
        sub = get_player_subscription(name)
        season_fee = float(sub.get("season_fee", 0)) if sub else 0
        player_payments = [p for p in payments if p.get("player_name", "").strip() == name]
        paid = sum(float(p.get("amount", 0)) for p in player_payments)
        remaining = max(0, season_fee - paid)
        status = sub.get("subscription_status", "—") if sub else "—"
        players_data.append({
            "اللاعب": name,
            "قيمة الاشتراك": season_fee,
            "المدفوع": paid,
            "المتبقي": remaining,
            "الحالة": "🟢 نشط" if status == "Active" else ("🔴 منتهي" if status == "Expired" else "🟡 معلق") if sub else "—"
        })
    
    if players_data:
        df = pd.DataFrame(players_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا يوجد لاعبين مسجلين.")

# =============================================================================
# باقي الصفحات (تم تعديل صفحة الاشتراكات لتعكس الموسمية)
# =============================================================================
def coach_dashboard_page():
    st.markdown("# 📊 لوحة التحكم")
    st.markdown(f"مرحباً، **{st.session_state.username}** 👋")
    st.markdown("---")
    
    users = get_all_users()
    players = [u for u in users if u.get("role") == "player"]
    attendance = get_all_attendance()
    today_attendance = get_today_attendance()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(players)}</div><div class="stat-label">👥 عدد اللاعبين</div></div>', unsafe_allow_html=True)
    with col2:
        present_today = len([a for a in today_attendance if a.get("status") == "Present"])
        st.markdown(f'<div class="stat-card"><div class="stat-number">{present_today}</div><div class="stat-label">✅ الحضور اليوم</div></div>', unsafe_allow_html=True)
    with col3:
        absent_today = len([a for a in today_attendance if a.get("status") == "Absent"])
        st.markdown(f'<div class="stat-card"><div class="stat-number">{absent_today}</div><div class="stat-label">❌ الغياب اليوم</div></div>', unsafe_allow_html=True)
    with col4:
        not_recorded = len(players) - len(today_attendance)
        st.markdown(f'<div class="stat-card"><div class="stat-number">{max(0, not_recorded)}</div><div class="stat-label">⏳ لم يُسجل</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📋 آخر سجلات الحضور")
    if attendance:
        df = pd.DataFrame(attendance[-10:])
        df = df.rename(columns={"player_name": "اللاعب", "date": "التاريخ", "status": "الحالة", "recorded_by": "سجل بواسطة"})
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x == "Present" else "❌ غائب")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات حضور بعد")

def coach_attendance_page():
    st.markdown("# ✅ تسجيل الحضور والغياب")
    users = get_all_users()
    players = [u.get("username", "").strip() for u in users if u.get("role") == "player"]
    if not players:
        st.warning("⚠️ لا يوجد لاعبين مسجلين")
        return
    st.date_input("📅 تاريخ التسجيل", value=date.today())
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ تسجيل حضور الجميع", use_container_width=True):
            success, msg = record_multiple_attendance(players, "Present", st.session_state.username)
            if success: st.success(msg); st.rerun()
            else: st.error(msg)
    with col2:
        if st.button("❌ تسجيل غياب الجميع", use_container_width=True):
            success, msg = record_multiple_attendance(players, "Absent", st.session_state.username)
            if success: st.success(msg); st.rerun()
            else: st.error(msg)
    st.markdown("---")
    # بقية الكود كما هو (اختيار الحضور والغياب) مختصر هنا للتركيز على التغييرات المهمة
    st.markdown("### ✅ الحضور")
    present = st.multiselect("اختر الحاضرين", players, key="present")
    if st.button("تسجيل حضور المحددين"):
        if present:
            success, msg = record_multiple_attendance(present, "Present", st.session_state.username)
            if success: st.success(msg); st.rerun()
            else: st.error(msg)
    st.markdown("### ❌ الغياب")
    remaining = [p for p in players if p not in present]
    absent = st.multiselect("اختر الغائبين", remaining, key="absent")
    if st.button("تسجيل غياب المحددين"):
        if absent:
            success, msg = record_multiple_attendance(absent, "Absent", st.session_state.username)
            if success: st.success(msg); st.rerun()
            else: st.error(msg)
    st.markdown("---")
    st.markdown("### 📝 تسجيل فردي")
    c1, c2, c3 = st.columns([2,1,1])
    with c1: sp = st.selectbox("اللاعب", players)
    with c2: ss = st.selectbox("الحالة", ["Present","Absent"], format_func=lambda x: "✅ حاضر" if x=="Present" else "❌ غائب")
    with c3:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if st.button("تسجيل"):
            success, msg = record_attendance(sp, ss, st.session_state.username)
            if success: st.success(msg); st.rerun()
            else: st.error(msg)

def coach_attendance_history_page():
    st.markdown("# 📋 سجل الحضور")
    users = get_all_users()
    players = ["الكل"] + [u["username"].strip() for u in users if u.get("role")=="player"]
    c1, c2, c3 = st.columns(3)
    with c1: fp = st.selectbox("اللاعب", players)
    with c2: fs = st.selectbox("الحالة", ["الكل","Present","Absent"], format_func=lambda x: "الكل" if x=="الكل" else ("✅ حاضر" if x=="Present" else "❌ غائب"))
    with c3: fd = st.date_input("التاريخ", value=None)
    records = get_all_attendance()
    if fp != "الكل": records = [r for r in records if r["player_name"].strip() == fp]
    if fs != "الكل": records = [r for r in records if r["status"] == fs]
    if fd: records = [r for r in records if r["date"] == fd.strftime("%Y-%m-%d")]
    if records:
        df = pd.DataFrame(records)
        df = df.rename(columns={"player_name":"اللاعب","date":"التاريخ","status":"الحالة","recorded_by":"سجل بواسطة"})
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x=="Present" else "❌ غائب")
        st.dataframe(df.sort_values("التاريخ", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات")

def coach_subscriptions_payments_page():
    st.markdown("# 💳 الاشتراكات والمدفوعات")
    tab1, tab2, tab3 = st.tabs(["📋 عرض الاشتراكات", "➕ إضافة/تعديل اشتراك ودفعة", "📊 سجل المدفوعات"])
    
    with tab1:
        subs = get_all_subscriptions()
        if subs:
            payments = get_all_payments()
            pay_dict = {}
            for p in payments:
                name = p["player_name"].strip()
                pay_dict[name] = pay_dict.get(name, 0) + float(p.get("amount",0))
            df = pd.DataFrame(subs)
            df["total_paid"] = df["player_name"].apply(lambda x: pay_dict.get(x.strip(),0))
            df["remaining"] = df.apply(lambda r: max(0, float(r.get("season_fee",0)) - r["total_paid"]), axis=1)
            df = df.rename(columns={"player_name":"اللاعب","season_fee":"قيمة الاشتراك","start_date":"بداية الموسم","end_date":"نهاية الموسم","subscription_status":"الحالة"})
            df["الحالة"] = df["الحالة"].apply(lambda x: "🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"))
            st.dataframe(df[["اللاعب","قيمة الاشتراك","total_paid","remaining","بداية الموسم","نهاية الموسم","الحالة"]], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد اشتراكات")
    
    with tab2:
        st.markdown("### ➕ إضافة/تعديل اشتراك (مع دفعة)")
        users = get_all_users()
        players = [u["username"].strip() for u in users if u.get("role")=="player"]
        if not players:
            st.warning("لا يوجد لاعبين")
        else:
            sel = st.selectbox("اختر اللاعب", players, key="sub_player")
            cur = get_player_subscription(sel)
            c1, c2 = st.columns(2)
            with c1: fee = st.number_input("قيمة الاشتراك (جنيه)", min_value=0.0, value=float(cur.get("season_fee",0)) if cur else 0.0, step=50.0)
            with c2:
                opts = ["Active","Expired","Suspended"]
                idx = opts.index(cur.get("subscription_status","Active")) if cur else 0
                status = st.selectbox("الحالة", opts, index=idx, format_func=lambda x: "🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"))
            c3, c4 = st.columns(2)
            with c3: start = st.date_input("بداية الموسم", value=date.today())
            with c4: end = st.date_input("نهاية الموسم", value=date.today()+timedelta(days=90))
            st.markdown("---")
            st.markdown("#### 💰 تسجيل دفعة")
            p1, p2 = st.columns(2)
            with p1: amt = st.number_input("مبلغ الدفعة", min_value=0.0, value=fee, step=50.0)
            with p2: method = st.selectbox("طريقة الدفع", ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"], format_func=lambda x: {"Cash":"💵 نقدي","InstaPay":"📱 إنستا باي","Vodafone Cash":"📲 فودافون كاش","Bank Transfer":"🏦 تحويل بنكي","Other":"📝 أخرى"}.get(x,x))
            pdate = st.date_input("تاريخ الدفع", value=date.today())
            notes = st.text_area("ملاحظات")
            if st.button("💾 حفظ الاشتراك والدفعة"):
                if amt <= 0:
                    st.error("المبلغ غير صحيح")
                else:
                    s_ok, s_msg = add_or_update_subscription(sel, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status)
                    if s_ok:
                        p_ok, p_msg = record_payment(sel, amt, method, pdate.strftime("%Y-%m-%d"), notes or f"دفعة اشتراك - {start}", st.session_state.username)
                        if p_ok:
                            st.success("✅ تم حفظ الاشتراك والدفعة")
                            st.rerun()
                        else:
                            st.warning(f"⚠️ تم حفظ الاشتراك لكن فشلت الدفعة: {p_msg}")
                    else:
                        st.error(f"❌ فشل حفظ الاشتراك: {s_msg}")
    
    with tab3:
        payments = get_all_payments()
        if payments:
            df = pd.DataFrame(payments)
            df = df.rename(columns={"player_name":"اللاعب","amount":"المبلغ","payment_method":"طريقة الدفع","payment_date":"تاريخ الدفع","notes":"ملاحظات"})
            df["طريقة الدفع"] = df["طريقة الدفع"].map({"Cash":"💵 نقدي","InstaPay":"📱 إنستا باي","Vodafone Cash":"📲 فودافون كاش","Bank Transfer":"🏦 تحويل بنكي","Other":"📝 أخرى"})
            st.dataframe(df.sort_values("تاريخ الدفع", ascending=False), use_container_width=True, hide_index=True)
            st.markdown(f"### 💵 الإجمالي: **{df['المبلغ'].sum():,.0f} جنيه**")
        else:
            st.info("لا توجد مدفوعات")

def coach_players_page():
    st.markdown("# 👥 إدارة اللاعبين")
    users = get_all_users()
    players = [u for u in users if u.get("role")=="player"]
    if not players:
        st.info("لا يوجد لاعبين")
        return
    data = []
    for p in players:
        name = p["username"].strip()
        stats = get_attendance_stats(name)
        summ = get_payment_summary(name)
        sub = get_player_subscription(name)
        data.append({
            "اللاعب": name,
            "نسبة الحضور": f"{stats['percentage']}%",
            "الاشتراك": "🟢 نشط" if sub and sub.get("subscription_status")=="Active" else "🔴 غير نشط",
            "القيمة": f"{summ['season_fee']:,.0f}" if summ['season_fee']>0 else "-",
            "المدفوع": f"{summ['total_paid']:,.0f}",
            "المتبقي": f"{summ['remaining']:,.0f}"
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    st.markdown("---")
    sel = st.selectbox("اختر لاعب", [p["username"].strip() for p in players])
    if sel:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📊 الحضور")
            s = get_attendance_stats(sel)
            st.write(f"الإجمالي: {s['total']} | حضور: {s['present']} | غياب: {s['absent']} | نسبة: {s['percentage']}%")
        with c2:
            st.markdown("#### 💳 الاشتراك")
            sub = get_player_subscription(sel)
            if sub:
                st.write(f"القيمة: {float(sub.get('season_fee',0)):,.0f} جنيه")
                st.write(f"من {sub.get('start_date')} إلى {sub.get('end_date')}")
                st.write(f"الحالة: {'🟢 نشط' if sub.get('subscription_status')=='Active' else '🔴 غير نشط'}")
            else:
                st.write("لا يوجد اشتراك")

# صفحات اللاعب (مختصرة، مع تعديل التسمية)
def player_dashboard_page():
    st.markdown("# 📊 ملخصي")
    st.markdown(f"مرحباً **{st.session_state.username}** 👋")
    st.markdown("---")
    stats = get_attendance_stats(st.session_state.username)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["percentage"]}%</div><div class="stat-label">نسبة الحضور</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["present"]}</div><div class="stat-label">الحضور</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["absent"]}</div><div class="stat-label">الغياب</div></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("## 💳 الاشتراك والمدفوعات")
    summ = get_payment_summary(st.session_state.username)
    sub = get_player_subscription(st.session_state.username)
    if sub:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("قيمة الاشتراك", f"{summ['season_fee']:,.0f} جنيه")
        with c2: st.metric("المدفوع", f"{summ['total_paid']:,.0f} جنيه")
        with c3: st.metric("المتبقي", f"{summ['remaining']:,.0f} جنيه")
        with c4: st.metric("الحالة", f"{'🟢 نشط' if summ['status']=='Active' else '🔴 غير نشط'}")
        st.write(f"**الموسم:** {sub.get('start_date')} - {sub.get('end_date')}")
        payments = get_player_payments(st.session_state.username)
        if payments:
            st.markdown("### آخر المدفوعات")
            df = pd.DataFrame(payments[-5:])[["payment_date","amount","payment_method"]]
            df.columns = ["التاريخ","المبلغ","الطريقة"]
            st.dataframe(df, hide_index=True)
    else:
        st.info("لم يتم تسجيل اشتراك بعد.")

def player_attendance_page():
    st.markdown("# 📋 سجل حضوري")
    records = get_player_attendance(st.session_state.username)
    if records:
        df = pd.DataFrame(records)
        df = df.rename(columns={"date":"التاريخ","status":"الحالة"})
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x=="Present" else "❌ غائب")
        st.dataframe(df.sort_values("التاريخ", ascending=False), hide_index=True)
    else:
        st.info("لا توجد سجلات")

def player_subscription_page():
    st.markdown("# 💳 اشتراكي ومدفوعاتي")
    summ = get_payment_summary(st.session_state.username)
    sub = get_player_subscription(st.session_state.username)
    if sub:
        st.markdown(f"**قيمة الاشتراك:** {summ['season_fee']:,.0f} جنيه")
        st.markdown(f"**المدفوع:** {summ['total_paid']:,.0f} جنيه | **المتبقي:** {summ['remaining']:,.0f} جنيه")
        st.markdown(f"**الموسم:** {sub.get('start_date')} - {sub.get('end_date')}")
        st.markdown(f"**الحالة:** {'🟢 نشط' if sub.get('subscription_status')=='Active' else '🔴 غير نشط'}")
        payments = get_player_payments(st.session_state.username)
        if payments:
            df = pd.DataFrame(payments)
            df = df.rename(columns={"payment_date":"التاريخ","amount":"المبلغ","payment_method":"الطريقة"})
            st.dataframe(df[["التاريخ","المبلغ","الطريقة"]].sort_values("التاريخ", ascending=False), hide_index=True)
    else:
        st.info("لا يوجد اشتراك")

# =============================================================================
# صفحة تسجيل الدخول مع شعار في المنتصف
# =============================================================================
def login_page():
    coach_exists = check_coach_exists()
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="logo-login">{get_logo_html(150)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">الكوتش أكاديمي</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">نظام إدارة الحضور والاشتراكات الموسمية</div>', unsafe_allow_html=True)
    if not coach_exists:
        st.markdown('<div class="welcome-box"><h3>👋 مرحباً بك!</h3><p>سيتم تسجيلك كـ <strong>كابتن</strong>.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box"><p>👋 سيتم تسجيلك كـ <strong>لاعب</strong>.</p></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔐 تسجيل الدخول", "📝 حساب جديد"])
    with tab1:
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)", key="login_user")
        password = st.text_input("كلمة المرور", type="password", key="login_pass")
        if st.button("دخول"):
            if username and password:
                success, msg = login(username, password)
                if success:
                    st.success(msg); st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("املأ الحقول")
    with tab2:
        new_user = st.text_input("الاسم الثلاثي", key="reg_user")
        new_pass = st.text_input("كلمة المرور", type="password", key="reg_pass")
        confirm = st.text_input("تأكيد كلمة المرور", type="password", key="reg_confirm")
        if st.button("تسجيل"):
            if not new_user or not new_pass:
                st.error("املأ الحقول")
            elif not validate_triple_name(new_user):
                st.error("الاسم يجب أن يكون ثلاثياً")
            elif new_pass != confirm:
                st.error("كلمة المرور غير متطابقة")
            elif len(new_pass) < 6:
                st.error("كلمة المرور 6 أحرف على الأقل")
            else:
                role = "coach" if not coach_exists else "player"
                success, msg = add_user(new_user, new_pass, role)
                if success:
                    st.success(msg); st.info("يمكنك الآن تسجيل الدخول")
                else:
                    st.error(msg)
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# الدالة الرئيسية
# =============================================================================
def main():
    init_session()
    if "sheets_initialized" not in st.session_state:
        init_sheets()
        st.session_state.sheets_initialized = True
    
    if not st.session_state.logged_in:
        login_page()
    else:
        navigation_bar()
        page = st.session_state.current_page
        if st.session_state.role == "coach":
            if page == "dashboard": coach_dashboard_page()
            elif page == "attendance": coach_attendance_page()
            elif page == "attendance_history": coach_attendance_history_page()
            elif page == "subscriptions_payments": coach_subscriptions_payments_page()
            elif page == "players": coach_players_page()
            elif page == "finance_reports": coach_finance_reports_page()
            else: coach_dashboard_page()
        else:
            if page == "dashboard": player_dashboard_page()
            elif page == "my_attendance": player_attendance_page()
            elif page == "my_subscription": player_subscription_page()
            else: player_dashboard_page()

if __name__ == "__main__":
    main()
