"""
نظام الكوتش أكاديمي - إدارة الحضور والاشتراكات الموسمية
=====================================================
تطبيق شامل لإدارة أكاديمية كرة القدم من حيث الحضور والاشتراكات والمدفوعات
مع تقارير مالية محمية وواجهة مستخدم عربية بالكامل.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import pandas as pd
import re
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
# دوال مساعدة للتخزين المؤقت وإعادة المحاولة (لحل مشكلة 429)
# =============================================================================
def retry_on_quota(func, max_retries=5, delay=2.0):
    """إعادة محاولة تنفيذ الدالة عند حدوث خطأ quota (429) من Google Sheets."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if ("429" in str(e) or "Quota exceeded" in str(e)) and attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                else:
                    raise e
        return None
    return wrapper

# =============================================================================
# إعداد Google Sheets مع تحسين إدارة الاتصال وورقة Finance موحدة
# =============================================================================
@st.cache_resource
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

@st.cache_resource
def get_worksheet(sheet_name):
    workbook = get_workbook()
    if workbook:
        try:
            return workbook.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return None
        except Exception as e:
            st.error(f"❌ خطأ في الوصول إلى ورقة {sheet_name}: {str(e)}")
            return None
    return None

def init_sheets():
    workbook = get_workbook()
    if not workbook:
        return False

    try:
        required_sheets = {
            "Users": ["username", "password", "role", "created_at"],
            "Attendance": ["player_name", "date", "status", "recorded_by", "created_at"],
            "Finance": ["player_name", "season_fee", "start_date", "end_date", "subscription_status",
                        "total_paid", "last_payment_date", "updated_at"],
            "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes", "recorded_by", "created_at"]
        }

        existing_sheets = [sheet.title for sheet in workbook.worksheets()]

        for sheet_name, headers in required_sheets.items():
            if sheet_name not in existing_sheets:
                sheet = workbook.add_worksheet(title=sheet_name, rows=1000, cols=20)
                sheet.append_row(headers)

        get_worksheet.clear()
        return True
    except Exception as e:
        st.error(f"❌ خطأ في تهيئة Sheets: {str(e)}")
        return False

# =============================================================================
# دوال قراءة البيانات مع التخزين المؤقت وإعادة المحاولة
# =============================================================================
@retry_on_quota
def _get_all_records_safe(sheet_name):
    sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            return sheet.get_all_records()
        except Exception as e:
            st.error(f"⚠️ خطأ في قراءة ورقة {sheet_name}: {str(e)}")
            return []
    return []

@st.cache_data(ttl=60)
def get_users_sheet_data():
    return _get_all_records_safe("Users")

@st.cache_data(ttl=60)
def get_attendance_sheet_data():
    return _get_all_records_safe("Attendance")

@st.cache_data(ttl=60)
def get_finance_sheet_data():
    return _get_all_records_safe("Finance")

@st.cache_data(ttl=60)
def get_payments_sheet_data():
    return _get_all_records_safe("Payments")

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

def get_all_finance():
    return clean_records(get_finance_sheet_data())

def get_all_payments():
    return clean_records(get_payments_sheet_data())

# =============================================================================
# دوال الكتابة (مع إعادة المحاولة)
# =============================================================================
@retry_on_quota
def append_row_to_sheet(sheet_name, row_data):
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        init_sheets()
        sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.append_row(row_data)
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ خطأ في الإضافة إلى {sheet_name}: {str(e)}")
            return False
    return False

@retry_on_quota
def update_cell_in_sheet(sheet_name, row, col, value):
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        init_sheets()
        sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.update_cell(row, col, value)
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ خطأ في تحديث الخلية: {str(e)}")
            return False
    return False

@retry_on_quota
def delete_row_from_sheet(sheet_name, row_index):
    sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.delete_rows(row_index)
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ خطأ في حذف الصف: {str(e)}")
            return False
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
    if get_user(username):
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
# دوال الاشتراكات والمدفوعات (ورقة Finance موحدة مع Payments منفصلة)
# =============================================================================
def get_player_finance(player_name: str):
    records = get_all_finance()
    for r in records:
        if r.get("player_name", "").strip() == player_name.strip():
            return r
    return None

def calculate_total_paid_from_payments(player_name: str) -> float:
    payments = get_all_payments()
    total = 0.0
    for p in payments:
        if p.get("player_name", "").strip() == player_name.strip():
            try:
                total += float(p.get("amount", 0))
            except:
                pass
    return total

def sync_total_paid_in_finance(player_name: str):
    finance = get_player_finance(player_name)
    if not finance:
        return
    correct_total = calculate_total_paid_from_payments(player_name)
    all_finance = get_all_finance()
    row_idx = None
    for idx, rec in enumerate(all_finance, start=2):
        if rec.get("player_name", "").strip() == player_name.strip():
            row_idx = idx
            break
    if row_idx:
        update_cell_in_sheet("Finance", row_idx, 6, correct_total)
        payments = get_player_payments(player_name)
        if payments:
            latest_date = max(p["payment_date"] for p in payments)
            update_cell_in_sheet("Finance", row_idx, 7, latest_date)

def get_player_payments(player_name: str):
    records = get_all_payments()
    return [r for r in records if r.get("player_name", "").strip() == player_name.strip()]

def add_or_update_finance_record(player_name: str, season_fee: float, start_date: str, end_date: str, status: str,
                                 amount_paid: float = 0, payment_method: str = "", payment_date: str = "", notes: str = ""):
    workbook = get_workbook()
    if not workbook:
        return False, "خطأ في الاتصال بقاعدة البيانات"

    sheet = get_worksheet("Finance")
    if sheet is None:
        init_sheets()
        sheet = get_worksheet("Finance")
        if sheet is None:
            return False, "تعذر الوصول إلى ورقة المالية"

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_records = get_all_finance()

    row_idx = None
    for idx, record in enumerate(all_records, start=2):
        if record.get("player_name", "").strip() == player_name.strip():
            row_idx = idx
            break

    if row_idx:
        update_cell_in_sheet("Finance", row_idx, 2, season_fee)
        update_cell_in_sheet("Finance", row_idx, 3, start_date)
        update_cell_in_sheet("Finance", row_idx, 4, end_date)
        update_cell_in_sheet("Finance", row_idx, 5, status)
        update_cell_in_sheet("Finance", row_idx, 8, updated_at)
        action = "تحديث"
    else:
        row_data = [player_name.strip(), season_fee, start_date, end_date, status, 0, "", updated_at]
        if not append_row_to_sheet("Finance", row_data):
            return False, "فشل في إضافة البيانات المالية"
        action = "إضافة"

    if amount_paid > 0:
        if not record_payment(player_name, amount_paid, payment_method, payment_date, notes, st.session_state.username):
            return False, "تم حفظ الاشتراك ولكن فشل تسجيل الدفعة"
        sync_total_paid_in_finance(player_name)

    return True, f"تم {action} الاشتراك بنجاح"

def delete_finance_record(player_name: str):
    all_finance = get_all_finance()
    row_idx = None
    for idx, rec in enumerate(all_finance, start=2):
        if rec.get("player_name", "").strip() == player_name.strip():
            row_idx = idx
            break
    if row_idx:
        return delete_row_from_sheet("Finance", row_idx)
    return False

def record_payment(player_name: str, amount: float, payment_method: str, payment_date: str, notes: str = "", recorded_by: str = ""):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if append_row_to_sheet("Payments", [player_name.strip(), amount, payment_method, payment_date, notes, recorded_by.strip(), created_at]):
        sync_total_paid_in_finance(player_name)
        return True, "تم تسجيل الدفعة بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def update_payment_record(payment_row_index: int, player_name: str, old_amount: float, new_amount: float,
                          payment_method: str, payment_date: str, notes: str = ""):
    sheet = get_worksheet("Payments")
    if sheet:
        update_cell_in_sheet("Payments", payment_row_index, 2, new_amount)
        update_cell_in_sheet("Payments", payment_row_index, 3, payment_method)
        update_cell_in_sheet("Payments", payment_row_index, 4, payment_date)
        update_cell_in_sheet("Payments", payment_row_index, 5, notes)
        sync_total_paid_in_finance(player_name)
        return True, "تم تحديث الدفعة بنجاح"
    return False, "خطأ في تحديث الدفعة"

def delete_payment_record(payment_row_index: int, player_name: str):
    sheet = get_worksheet("Payments")
    if sheet:
        if delete_row_from_sheet("Payments", payment_row_index):
            sync_total_paid_in_finance(player_name)
            return True, "تم حذف الدفعة بنجاح"
    return False, "خطأ في حذف الدفعة"

def get_payment_summary(player_name: str):
    finance = get_player_finance(player_name)
    if not finance:
        return {"season_fee": 0, "total_paid": 0, "remaining": 0, "status": "No Subscription"}
    try:
        season_fee = float(finance.get("season_fee", 0))
    except:
        season_fee = 0
    total_paid = calculate_total_paid_from_payments(player_name)
    remaining = max(0, season_fee - total_paid)
    return {"season_fee": season_fee, "total_paid": total_paid, "remaining": remaining, "status": finance.get("subscription_status", "Unknown")}

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
        st.session_state.finance_authenticated = False
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
# CSS مخصص (تحسين الألوان والوضوح)
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
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
        max-width: 500px;
        margin: 50px auto;
        padding: 40px;
        background: rgba(255, 255, 255, 0.98);
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        text-align: center;
    }
    .login-icon {
        font-size: 60px;
        margin-bottom: 15px;
        text-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .login-title {
        color: #1a5f3f !important;
        font-size: 46px !important;
        font-weight: 800 !important;
        margin-bottom: 5px;
        text-shadow: 3px 3px 10px rgba(0,0,0,0.2);
        letter-spacing: 3px;
        background: linear-gradient(135deg, #1a5f3f, #2e8b57);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .login-subtitle {
        color: #1e3c2c !important;
        font-size: 24px !important;
        font-weight: 600 !important;
        margin-bottom: 30px;
        text-shadow: 1px 1px 4px rgba(0,0,0,0.15);
    }
    
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
        background: #2c3e50;
        border-right: 6px solid #1a5f3f;
        padding: 15px 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        color: white !important;
        font-weight: 500;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .info-box p {
        color: white !important;
        margin: 0;
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
    col_title, col_user = st.columns([3, 1])
    with col_title:
        st.markdown('<h2 style="color:white; margin:0; font-size:26px; text-align:right; padding-right:20px;">⚽ الكوتش أكاديمي</h2>', unsafe_allow_html=True)
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
            "finance_reports": "🔒 التقارير المالية"
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
# صفحة المصادقة المالية
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
# صفحات الكابتن
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
            if success:
                st.success(msg)
                st.toast("✅ تم تسجيل الحضور لجميع اللاعبين!", icon="✅")
                st.rerun()
            else:
                st.error(msg)
    with col2:
        if st.button("❌ تسجيل غياب الجميع", use_container_width=True):
            success, msg = record_multiple_attendance(players, "Absent", st.session_state.username)
            if success:
                st.success(msg)
                st.toast("✅ تم تسجيل الغياب لجميع اللاعبين!", icon="✅")
                st.rerun()
            else:
                st.error(msg)
    st.markdown("---")
    st.markdown("### ✅ الحضور")
    present = st.multiselect("اختر الحاضرين", players, key="present")
    if st.button("تسجيل حضور المحددين"):
        if present:
            success, msg = record_multiple_attendance(present, "Present", st.session_state.username)
            if success:
                st.success(msg)
                st.toast(f"✅ تم تسجيل حضور {len(present)} لاعب!", icon="✅")
                st.rerun()
            else:
                st.error(msg)
        else:
            st.warning("⚠️ يرجى اختيار لاعب واحد على الأقل")
    st.markdown("### ❌ الغياب")
    remaining = [p for p in players if p not in present]
    absent = st.multiselect("اختر الغائبين", remaining, key="absent")
    if st.button("تسجيل غياب المحددين"):
        if absent:
            success, msg = record_multiple_attendance(absent, "Absent", st.session_state.username)
            if success:
                st.success(msg)
                st.toast(f"✅ تم تسجيل غياب {len(absent)} لاعب!", icon="✅")
                st.rerun()
            else:
                st.error(msg)
        else:
            st.warning("⚠️ يرجى اختيار لاعب واحد على الأقل")
    st.markdown("---")
    st.markdown("### 📝 تسجيل فردي")
    c1, c2, c3 = st.columns([2,1,1])
    with c1: sp = st.selectbox("اللاعب", players)
    with c2: ss = st.selectbox("الحالة", ["Present","Absent"], format_func=lambda x: "✅ حاضر" if x=="Present" else "❌ غائب")
    with c3:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if st.button("تسجيل"):
            success, msg = record_attendance(sp, ss, st.session_state.username)
            if success:
                st.success(msg)
                st.toast(f"✅ تم تسجيل {'الحضور' if ss=='Present' else 'الغياب'} لـ {sp}!", icon="✅")
                st.rerun()
            else:
                st.error(msg)

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
    tab1, tab2, tab3, tab4 = st.tabs(["➕ تسجيل اشتراك جديد", "✏️ تعديل اشتراك", "💰 إدارة المدفوعات", "📋 عرض الاشتراكات"])

    with tab1:
        st.markdown("### ➕ تسجيل اشتراك جديد (مع دفعة أولى)")
        users = get_all_users()
        existing = {f["player_name"] for f in get_all_finance()}
        players = [u["username"].strip() for u in users if u.get("role")=="player" and u["username"].strip() not in existing]
        if not players:
            st.info("جميع اللاعبين لديهم اشتراكات.")
        else:
            sel = st.selectbox("اختر اللاعب", players, key="new_finance_player")
            c1, c2 = st.columns(2)
            with c1: fee = st.number_input("قيمة الاشتراك", min_value=0.0, step=50.0, key="new_fee")
            with c2: status = st.selectbox("الحالة", ["Active","Expired","Suspended"], format_func=lambda x: "🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"), key="new_status")
            c3, c4 = st.columns(2)
            with c3: start = st.date_input("بداية الموسم", value=date.today(), key="new_start")
            with c4: end = st.date_input("نهاية الموسم", value=date.today()+timedelta(days=90), key="new_end")
            st.markdown("---")
            st.markdown("#### 💰 الدفعة الأولى")
            p1, p2 = st.columns(2)
            with p1: amt = st.number_input("المبلغ", min_value=0.0, value=fee, step=50.0, key="new_amt")
            with p2: method = st.selectbox("طريقة الدفع", ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"], key="new_method")
            pdate = st.date_input("تاريخ الدفع", value=date.today(), key="new_pdate")
            notes = st.text_area("ملاحظات", key="new_notes")
            if st.button("💾 حفظ الاشتراك والدفعة", key="btn_new_finance"):
                if fee <=0 or amt <=0: st.error("يرجى إدخال قيم صحيحة")
                else:
                    success, msg = add_or_update_finance_record(sel, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status, amt, method, pdate.strftime("%Y-%m-%d"), notes)
                    if success:
                        st.success("✅ تم حفظ الاشتراك والدفعة بنجاح!")
                        st.toast("✅ اشتراك جديد مع دفعة!", icon="💳")
                        st.rerun()
                    else:
                        st.error(msg)

    with tab2:
        st.markdown("### ✏️ تعديل بيانات الاشتراك")
        finance_records = get_all_finance()
        if not finance_records:
            st.info("لا توجد اشتراكات")
        else:
            players = [f["player_name"] for f in finance_records]
            sel = st.selectbox("اختر اللاعب", players, key="edit_finance_player")
            current = next((f for f in finance_records if f["player_name"]==sel), None)
            if current:
                c1, c2 = st.columns(2)
                with c1: fee = st.number_input("قيمة الاشتراك", value=float(current.get("season_fee",0)), step=50.0, key="edit_fee")
                with c2:
                    opts = ["Active","Expired","Suspended"]
                    idx = opts.index(current.get("subscription_status","Active")) if current.get("subscription_status","Active") in opts else 0
                    status = st.selectbox("الحالة", opts, index=idx, format_func=lambda x: "🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"), key="edit_status")
                c3, c4 = st.columns(2)
                with c3:
                    dstart = datetime.strptime(current.get("start_date", date.today().strftime("%Y-%m-%d")), "%Y-%m-%d").date()
                    start = st.date_input("بداية الموسم", value=dstart, key="edit_start")
                with c4:
                    dend = datetime.strptime(current.get("end_date", (date.today()+timedelta(days=90)).strftime("%Y-%m-%d")), "%Y-%m-%d").date()
                    end = st.date_input("نهاية الموسم", value=dend, key="edit_end")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📝 تحديث الاشتراك", key="btn_update_finance"):
                        success, msg = add_or_update_finance_record(sel, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status, 0)
                        if success:
                            st.success("✅ تم تحديث الاشتراك بنجاح!")
                            st.toast("✅ تم تحديث الاشتراك!", icon="✏️")
                            st.rerun()
                        else:
                            st.error(msg)
                with col2:
                    if st.button("🗑️ حذف الاشتراك", key="btn_delete_finance"):
                        if delete_finance_record(sel):
                            st.success("✅ تم حذف الاشتراك بنجاح!")
                            st.toast("✅ تم حذف الاشتراك!", icon="🗑️")
                            st.rerun()
                        else:
                            st.error("❌ فشل حذف الاشتراك")

    with tab3:
        st.markdown("### 💰 إدارة المدفوعات (تعديل / حذف)")
        payments = get_all_payments()
        if not payments:
            st.info("لا توجد مدفوعات مسجلة")
        else:
            df = pd.DataFrame(payments)
            df["row_index"] = range(2, len(payments)+2)
            df_display = df.rename(columns={"player_name":"اللاعب","amount":"المبلغ","payment_method":"الطريقة","payment_date":"التاريخ","notes":"ملاحظات"})
            st.dataframe(df_display[["row_index","اللاعب","المبلغ","الطريقة","التاريخ","ملاحظات"]], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("#### تعديل دفعة")
            row_num = st.number_input("أدخل رقم الصف (row_index) للتعديل", min_value=2, step=1, key="edit_row")
            selected_row = df[df["row_index"]==row_num]
            if not selected_row.empty:
                row = selected_row.iloc[0]
                st.write(f"اللاعب: {row['player_name']} | المبلغ الحالي: {row['amount']}")
                new_amt = st.number_input("المبلغ الجديد", value=float(row['amount']), step=50.0, key="edit_payment_amt")
                new_method = st.selectbox("طريقة الدفع", ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"], index=["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"].index(row['payment_method']) if row['payment_method'] in ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"] else 0, key="edit_payment_method")
                new_date = st.date_input("تاريخ الدفع", value=datetime.strptime(row['payment_date'], "%Y-%m-%d").date(), key="edit_payment_date")
                new_notes = st.text_area("ملاحظات", value=row.get('notes',''), key="edit_payment_notes")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📝 تحديث الدفعة", key="btn_update_payment"):
                        success, msg = update_payment_record(row_num, row['player_name'], float(row['amount']), new_amt, new_method, new_date.strftime("%Y-%m-%d"), new_notes)
                        if success:
                            st.success("✅ تم تحديث الدفعة بنجاح!")
                            st.toast("✅ تم تحديث الدفعة!", icon="💰")
                            st.rerun()
                        else:
                            st.error(msg)
                with col2:
                    if st.button("🗑️ حذف الدفعة", key="btn_delete_payment"):
                        success, msg = delete_payment_record(row_num, row['player_name'])
                        if success:
                            st.success("✅ تم حذف الدفعة بنجاح!")
                            st.toast("✅ تم حذف الدفعة!", icon="🗑️")
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                st.warning("رقم الصف غير موجود")

    with tab4:
        st.markdown("### 📋 الاشتراكات المسجلة")
        finance = get_all_finance()
        if finance:
            df = pd.DataFrame(finance)
            df = df.rename(columns={"player_name":"اللاعب","season_fee":"القيمة","start_date":"بداية","end_date":"نهاية","subscription_status":"الحالة","total_paid":"المدفوع"})
            df["المتبقي"] = df.apply(lambda r: max(0, float(r["القيمة"]) - float(r["المدفوع"])), axis=1)
            def status_color(s):
                if s=="Active": return "🟢 نشط"
                elif s=="Expired": return "🔴 منتهي"
                else: return "🟡 معلق"
            df["الحالة"] = df["الحالة"].apply(status_color)
            st.dataframe(df[["اللاعب","القيمة","المدفوع","المتبقي","بداية","نهاية","الحالة"]], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد اشتراكات")

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
        sub = get_player_finance(name)
        data.append({
            "اللاعب": name,
            "نسبة الحضور": f"{stats['percentage']}%",
            "الاشتراك": "🟢 نشط" if sub and sub.get("subscription_status")=="Active" else "🔴 غير نشط"
        })
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    st.markdown("---")
    sel = st.selectbox("اختر لاعب", [p["username"].strip() for p in players])
    if sel:
        c1, c2 = st.columns(2)
        with c1:
            s = get_attendance_stats(sel)
            st.write(f"الحضور: {s['present']} | الغياب: {s['absent']} | النسبة: {s['percentage']}%")
        with c2:
            sub = get_player_finance(sel)
            if sub:
                st.write(f"القيمة: {sub.get('season_fee')} جنيه | المدفوع: {sub.get('total_paid')} | المتبقي: {max(0, float(sub.get('season_fee',0))-float(sub.get('total_paid',0))):.0f}")
                st.write(f"الحالة: {'🟢 نشط' if sub.get('subscription_status')=='Active' else '🔴 غير نشط'}")

def coach_finance_reports_page():
    if not st.session_state.get("finance_authenticated", False):
        finance_auth_wall()
        return

    st.markdown("# 📊 التقارير المالية")
    finance = get_all_finance()
    if not finance:
        st.info("لا توجد بيانات مالية")
        return

    df = pd.DataFrame(finance)
    df["season_fee"] = df["season_fee"].astype(float)
    df["total_paid"] = df["player_name"].apply(lambda name: calculate_total_paid_from_payments(name))
    df["remaining"] = df["season_fee"] - df["total_paid"]

    def get_payment_status(row):
        if row["remaining"] <= 0:
            return "مدفوع بالكامل"
        elif row["total_paid"] > 0:
            return "مدفوع جزئيًا"
        else:
            return "غير مدفوع"

    df["payment_status"] = df.apply(get_payment_status, axis=1)

    filter_option = st.selectbox("عرض اللاعبين:", ["الكل", "مدفوع بالكامل", "مدفوع جزئيًا", "غير مدفوع"])
    if filter_option != "الكل":
        df = df[df["payment_status"] == filter_option]

    total_fee = df["season_fee"].sum()
    total_paid = df["total_paid"].sum()
    total_remaining = df["remaining"].sum()
    collection_rate = (total_paid / total_fee * 100) if total_fee > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_fee:,.0f}</div><div class="stat-label">💰 إجمالي المستحق</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_paid:,.0f}</div><div class="stat-label">💵 إجمالي المدفوع</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total_remaining:,.0f}</div><div class="stat-label">📉 إجمالي المتبقي</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{collection_rate:.1f}%</div><div class="stat-label">📈 نسبة التحصيل</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.dataframe(df[["player_name", "season_fee", "total_paid", "remaining", "payment_status", "subscription_status"]].rename(
        columns={"player_name":"اللاعب","season_fee":"القيمة","total_paid":"المدفوع","remaining":"المتبقي","payment_status":"حالة الدفع","subscription_status":"حالة الاشتراك"}
    ), use_container_width=True, hide_index=True)

# =============================================================================
# صفحات اللاعب
# =============================================================================
def player_dashboard_page():
    st.markdown("# 📊 ملخصي")
    st.markdown(f"مرحباً **{st.session_state.username}** 👋")
    stats = get_attendance_stats(st.session_state.username)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["percentage"]}%</div><div class="stat-label">نسبة الحضور</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["present"]}</div><div class="stat-label">الحضور</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["absent"]}</div><div class="stat-label">الغياب</div></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("## 💳 الاشتراك والمدفوعات")
    summ = get_payment_summary(st.session_state.username)
    sub = get_player_finance(st.session_state.username)
    if sub:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("القيمة", f"{summ['season_fee']:,.0f} جنيه")
        with c2: st.metric("المدفوع", f"{summ['total_paid']:,.0f} جنيه")
        with c3: st.metric("المتبقي", f"{summ['remaining']:,.0f} جنيه")
        with c4: st.metric("الحالة", "🟢 نشط" if summ['status']=="Active" else "🔴 غير نشط")
        st.write(f"الموسم: {sub.get('start_date')} - {sub.get('end_date')}")

def player_attendance_page():
    st.markdown("# 📋 سجل حضوري")
    records = get_player_attendance(st.session_state.username)
    if records:
        df = pd.DataFrame(records)[["date","status"]].rename(columns={"date":"التاريخ","status":"الحالة"})
        df["الحالة"] = df["الحالة"].apply(lambda x: "✅ حاضر" if x=="Present" else "❌ غائب")
        st.dataframe(df.sort_values("التاريخ", ascending=False), hide_index=True)

def player_subscription_page():
    st.markdown("# 💳 اشتراكي ومدفوعاتي")
    summ = get_payment_summary(st.session_state.username)
    sub = get_player_finance(st.session_state.username)
    if sub:
        st.write(f"القيمة: {summ['season_fee']:,.0f} جنيه | المدفوع: {summ['total_paid']:,.0f} | المتبقي: {summ['remaining']:,.0f}")
        st.write(f"الموسم: {sub.get('start_date')} - {sub.get('end_date')}")
        st.write(f"الحالة: {'🟢 نشط' if sub.get('subscription_status')=='Active' else '🔴 غير نشط'}")

# =============================================================================
# صفحة تسجيل الدخول (نصوص واضحة والرسالة تظهر فقط عند التسجيل)
# =============================================================================
def login_page():
    coach_exists = check_coach_exists()
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-icon">⚽</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">الكوتش أكاديمي</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">نظام إدارة الحضور والاشتراكات الموسمية</div>', unsafe_allow_html=True)
    if not coach_exists:
        st.markdown('<div class="welcome-box"><h3>👋 مرحباً بك!</h3><p>سيتم تسجيلك كـ <strong>كابتن</strong>.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="welcome-box"><h3>👋 مرحباً بك!</h3><p>قم بتسجيل الدخول أو إنشاء حساب جديد.</p></div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔐 تسجيل الدخول", "📝 تسجيل حساب جديد"])

    with tab1:
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)", key="login_user")
        password = st.text_input("كلمة المرور", type="password", key="login_pass")
        if st.button("تسجيل الدخول"):
            if username and password:
                success, msg = login(username, password)
                if success:
                    st.success(msg)
                    st.toast("✅ تم تسجيل الدخول بنجاح!", icon="🔓")
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور")

    with tab2:
        # الرسالة تظهر هنا فقط
        if coach_exists:
            st.markdown('<div class="info-box"><p>👋 سيتم تسجيلك كـ <strong>لاعب</strong>.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="info-box"><p>👋 سيتم تسجيلك كـ <strong>كابتن</strong>.</p></div>', unsafe_allow_html=True)

        new_user = st.text_input("الاسم الثلاثي", key="reg_user")
        new_pass = st.text_input("كلمة المرور", type="password", key="reg_pass")
        confirm = st.text_input("تأكيد كلمة المرور", type="password", key="reg_confirm")
        if st.button("تسجيل حساب جديد"):
            if not new_user or not new_pass:
                st.error("يرجى ملء جميع الحقول")
            elif not validate_triple_name(new_user):
                st.error("الاسم يجب أن يكون ثلاثياً (مثال: أحمد محمد علي)")
            elif new_pass != confirm:
                st.error("كلمة المرور غير متطابقة")
            elif len(new_pass) < 6:
                st.error("كلمة المرور يجب أن تكون 6 أحرف على الأقل")
            else:
                role = "coach" if not coach_exists else "player"
                success, msg = add_user(new_user, new_pass, role)
                if success:
                    st.success(msg)
                    st.toast("✅ تم إنشاء الحساب بنجاح!", icon="🎉")
                    st.info("يمكنك الآن تسجيل الدخول")
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
