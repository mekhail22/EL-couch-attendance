"""
نظام الكوتش أكاديمي - إدارة الحضور والاشتراكات الموسمية
=====================================================
تطبيق شامل لإدارة أكاديمية كرة القدم من حيث الحضور والاشتراكات والمدفوعات
مع تقارير مالية محمية وواجهة مستخدم عربية بالكامل.
تم تخصيص 50,000 صف لورقة Attendance وباقي الأوراق 1,000 صف.
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
# دالة عرض الشعار
# =============================================================================
def get_logo_html(width=50):
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                return f'<img src="data:image/jpeg;base64,{b64}" style="width:{width}px; height:auto; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">'
        except:
            pass
    return f'<span style="font-size:{width}px;">⚽</span>'

# =============================================================================
# دوال مساعدة للتخزين المؤقت وإعادة المحاولة
# =============================================================================
def retry_on_quota(func, max_retries=5, delay=3.0):
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
# إعداد Google Sheets
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
    """
    تهيئة الأوراق: Attendance بـ 50000 صف، الباقي بـ 1000 صف.
    """
    workbook = get_workbook()
    if not workbook:
        return False

    try:
        required_sheets = {
            "Users": ("Users", ["username", "password", "role", "created_at"], 1000),
            "Attendance": ("Attendance", ["player_name", "date", "status", "recorded_by", "created_at"], 50000),
            "Finance": ("Finance", ["player_name", "season_fee", "start_date", "end_date",
                                    "subscription_status", "total_paid", "last_payment_date", "updated_at"], 1000),
            "Payments": ("Payments", ["player_name", "amount", "payment_method", "payment_date",
                                      "notes", "recorded_by", "created_at"], 1000)
        }

        existing_sheets = {sheet.title: sheet for sheet in workbook.worksheets()}

        for sheet_name, (title, headers, rows_needed) in required_sheets.items():
            if sheet_name not in existing_sheets:
                sheet = workbook.add_worksheet(title=title, rows=str(rows_needed), cols=str(len(headers)))
                sheet.append_row(headers)
            else:
                sheet = existing_sheets[sheet_name]
                # التأكد من العناوين
                existing_headers = sheet.row_values(1)
                if not existing_headers or existing_headers != headers:
                    sheet.clear()
                    sheet.append_row(headers)
                # توسيع الورقة إذا لزم الأمر (خاصة Attendance)
                current_rows = sheet.row_count
                if current_rows < rows_needed:
                    sheet.add_rows(rows_needed - current_rows)

        get_worksheet.clear()
        return True
    except Exception as e:
        st.error(f"❌ خطأ في تهيئة Sheets: {str(e)}")
        return False

def ensure_sheet_has_rows(sheet_name, min_rows=100):
    """
    التأكد من وجود عدد كافٍ من الصفوف الفارغة في الورقة.
    إذا قلت الصفوف المتبقية عن min_rows، نضيف 5000 صف إضافية (لـ Attendance) أو 500 لغيرها.
    """
    sheet = get_worksheet(sheet_name)
    if not sheet:
        return
    try:
        total_rows = sheet.row_count
        # نحتاج معرفة عدد الصفوف المستخدمة حالياً
        all_values = sheet.get_all_values()
        used_rows = len(all_values)
        remaining = total_rows - used_rows
        if remaining < min_rows:
            add_rows = 5000 if sheet_name == "Attendance" else 500
            sheet.add_rows(add_rows)
    except Exception as e:
        st.warning(f"تحذير: تعذر توسيع ورقة {sheet_name}: {str(e)}")

# =============================================================================
# دوال قراءة البيانات مع التخزين المؤقت
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
# دوال الكتابة (مع دعم الكتابة المجمعة)
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
def append_rows_to_sheet(sheet_name, rows_data):
    """
    إضافة عدة صفوف دفعة واحدة لتقليل عدد طلبات API.
    """
    if not rows_data:
        return True
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        init_sheets()
        sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            ensure_sheet_has_rows(sheet_name, len(rows_data) + 5)
            sheet.append_rows(rows_data)
            st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ خطأ في الإضافة المتعددة إلى {sheet_name}: {str(e)}")
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
# دوال الحضور (مع منع التكرار وكتابة مجمعة)
# =============================================================================
def is_attendance_recorded_today(player_name: str) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    records = get_all_attendance()
    for r in records:
        if r.get("player_name", "").strip() == player_name.strip() and r.get("date") == today:
            return True
    return False

def record_attendance(player_name: str, status: str, recorded_by: str):
    if is_attendance_recorded_today(player_name):
        return False, f"تم تسجيل حالة للاعب {player_name} مسبقاً اليوم. لا يمكن التسجيل مرة أخرى."
    today = datetime.now().strftime("%Y-%m-%d")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if append_row_to_sheet("Attendance", [player_name.strip(), today, status, recorded_by.strip(), created_at]):
        return True, f"تم تسجيل {'الحضور' if status == 'Present' else 'الغياب'} بنجاح"
    return False, "خطأ في الاتصال بقاعدة البيانات"

def record_multiple_attendance(player_names: list, status: str, recorded_by: str):
    """
    تسجيل حضور/غياب لمجموعة لاعبين دفعة واحدة لتجنب تجاوز حصة الكتابة.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = get_all_attendance()
    recorded_today = {r["player_name"].strip() for r in records if r.get("date") == today}

    rows_to_add = []
    skipped_players = []
    success_count = 0

    for player_name in player_names:
        if player_name.strip() in recorded_today:
            skipped_players.append(player_name)
            continue
        rows_to_add.append([player_name.strip(), today, status, recorded_by.strip(), created_at])
        success_count += 1

    if rows_to_add:
        if not append_rows_to_sheet("Attendance", rows_to_add):
            return False, "خطأ في تسجيل الحضور الجماعي"

    msg = f"تم تسجيل {success_count} من {len(player_names)} لاعبين."
    if skipped_players:
        msg += f" (تم تخطي {len(skipped_players)} لاعبين لأنهم مسجلين مسبقاً اليوم)"
    return True, msg

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
# دوال الاشتراكات والمدفوعات
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

def get_player_payment_status(player_name: str) -> str:
    summary = get_payment_summary(player_name)
    if summary["status"] == "No Subscription":
        return "لا يوجد اشتراك"
    if summary["remaining"] <= 0:
        return "مدفوع بالكامل"
    elif summary["total_paid"] > 0:
        return "مدفوع جزئيًا"
    else:
        return "غير مدفوع"

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
# تهيئة الجلسة (محفوظة)
# =============================================================================
def init_session():
    defaults = {
        "logged_in": False,
        "username": None,
        "role": None,
        "current_page": "dashboard",
        "finance_authenticated": False,
        "sheets_initialized": False
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

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
# CSS مخصص (ألوان غامقة فاخرة)
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    * { font-family: 'Cairo', sans-serif !important; }
    .main { direction: rtl; }
    .stApp { background: radial-gradient(circle at top left, #0a1c14, #030a07); }
    [data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .stDeployButton, .stActionButton, #MainMenu, footer,
    div[data-testid="stToolbar"], div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"] { display: none !important; }
    
    .nav-container {
        background: rgba(20, 50, 40, 0.7); backdrop-filter: blur(12px);
        border-radius: 50px; padding: 10px 20px; margin: 20px 0;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6); border: 1px solid rgba(80, 180, 140, 0.3);
    }
    .nav-container .stButton > button {
        background: rgba(0, 0, 0, 0.25) !important; color: #e0f0e8 !important;
        border: 1px solid #2a7a5f !important; border-radius: 30px !important;
        padding: 10px 15px !important; font-size: 16px !important; font-weight: 600 !important;
        width: 100% !important; backdrop-filter: blur(4px); transition: all 0.3s;
    }
    .nav-container .stButton > button:hover {
        background: #1f6e54 !important; color: white !important;
        border-color: #4ecb9c !important; transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(30, 200, 120, 0.3);
    }
    
    .login-container {
        max-width: 480px; margin: 40px auto; padding: 40px 35px;
        background: rgba(10, 30, 25, 0.9); backdrop-filter: blur(10px);
        border-radius: 30px; box-shadow: 0 25px 50px rgba(0, 0, 0, 0.7);
        text-align: center; border: 1px solid #2c7a60;
    }
    .login-icon { margin-bottom: 20px; display: flex; justify-content: center; }
    .login-title { color: #c0f0d0 !important; font-size: 42px !important; font-weight: 800 !important; margin-bottom: 8px; text-shadow: 0 4px 12px #0f2f22; }
    .login-subtitle { color: #a0d0b8 !important; font-size: 20px !important; font-weight: 500 !important; margin-bottom: 30px; }
    
    .stat-card { background: linear-gradient(145deg, #15382b, #0c231a); color: white; border-radius: 20px; padding: 20px 10px; text-align: center; box-shadow: 0 10px 20px rgba(0, 0, 0, 0.5); border: 1px solid #2f7a5a; }
    .stat-number { font-size: 40px; font-weight: 800; color: #b0f0c0; margin-bottom: 5px; }
    .stat-label { font-size: 15px; font-weight: 500; color: #c0e0d0; }
    
    .welcome-box { background: linear-gradient(145deg, #1a5a44, #0e3628); color: white; padding: 20px; border-radius: 20px; margin-bottom: 20px; text-align: center; box-shadow: 0 8px 20px rgba(0,0,0,0.4); border: 1px solid #3fa07c; }
    .info-box { background: #163f31; border-right: 6px solid #40c090; padding: 15px 20px; border-radius: 16px; margin-bottom: 20px; color: #e0f5e8 !important; font-weight: 500; }
    
    .stButton > button { background: linear-gradient(145deg, #1f6e54, #144d3a); color: white; border: none; border-radius: 14px; padding: 12px 25px; font-size: 16px; font-weight: 600; width: 100%; box-shadow: 0 6px 15px rgba(0, 20, 0, 0.5); border: 1px solid #3da07a; transition: all 0.2s; }
    .stButton > button:hover { background: #2a8f6a; transform: translateY(-2px); box-shadow: 0 10px 25px rgba(40, 180, 120, 0.4); }
    
    .stTextInput > div > div > input { border-radius: 14px; border: 1.5px solid #2e7a5c; padding: 12px 15px; text-align: right; background: #0f2b20; color: #f0faf0; }
    .stTextInput > div > div > input:focus { border-color: #50d0a0; box-shadow: 0 0 0 3px rgba(80, 200, 150, 0.3); }
    
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; }
    .stTabs [data-baseweb="tab"] { background: #13382a; border-radius: 16px 16px 0 0; padding: 10px 22px; color: #c8e8d8; border: 1px solid #2f785a; border-bottom: none; font-weight: 600; }
    .stTabs [aria-selected="true"] { background: #1f6e54 !important; color: white !important; border-color: #50c898; }
    
    .user-info { color: #e0f0e4; font-size: 16px; font-weight: 600; padding: 10px 0; text-align: center; background: rgba(20, 60, 45, 0.6); backdrop-filter: blur(5px); border-radius: 30px; border: 1px solid #3d8e6e; }
    .stDataFrame { border-radius: 18px; border: 1px solid #2f785a; overflow: hidden; background: #0a1f16; }
    h1, h2, h3, h4, h5, h6 { color: #c0f0d0 !important; }
    p, span, div { color: #d0e8dc; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# شريط التنقل
# =============================================================================
def navigation_bar():
    col_logo, col_title, col_user = st.columns([0.7, 2.5, 1.2])
    with col_logo:
        st.markdown(get_logo_html(50), unsafe_allow_html=True)
    with col_title:
        st.markdown('<h2 style="color:#c0f0d0; margin:0; font-size:26px; text-align:right; padding-right:10px;">⚽ الكوتش أكاديمي</h2>', unsafe_allow_html=True)
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
                time.sleep(2)
                st.rerun()
            else:
                st.error(msg)
    with col2:
        if st.button("❌ تسجيل غياب الجميع", use_container_width=True):
            success, msg = record_multiple_attendance(players, "Absent", st.session_state.username)
            if success:
                st.success(msg)
                st.toast("✅ تم تسجيل الغياب لجميع اللاعبين!", icon="✅")
                time.sleep(2)
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
                time.sleep(2)
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
                time.sleep(2)
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
                time.sleep(2)
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
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(msg)

    with tab2:
        st.markdown("### ✏️ تعديل بيانات الاشتراك")
        finance_records = get_all_finance()
        if not finance_records:
            st.info("لا توجد اشتراكات")
        else:
            all_players = [f["player_name"] for f in finance_records]
            payment_filter = st.selectbox("تصنيف حسب حالة الدفع", ["الكل", "مدفوع بالكامل", "مدفوع جزئيًا", "غير مدفوع"], key="edit_filter")
            filtered_players = [p for p in all_players if payment_filter == "الكل" or get_player_payment_status(p) == payment_filter]
            if not filtered_players:
                st.info("لا يوجد لاعبين مطابقين للتصنيف المحدد.")
            else:
                sel = st.selectbox("اختر اللاعب", filtered_players, key="edit_finance_player")
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
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col2:
                        if st.button("🗑️ حذف الاشتراك", key="btn_delete_finance"):
                            if delete_finance_record(sel):
                                st.success("✅ تم حذف الاشتراك بنجاح!")
                                st.toast("✅ تم حذف الاشتراك!", icon="🗑️")
                                time.sleep(2)
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
            df["payment_status"] = df["player_name"].apply(get_player_payment_status)
            df_display = df.rename(columns={"player_name":"اللاعب","amount":"المبلغ","payment_method":"الطريقة","payment_date":"التاريخ","notes":"ملاحظات","payment_status":"حالة الدفع"})
            filter_payment = st.selectbox("تصنيف حسب حالة الدفع", ["الكل", "مدفوع بالكامل", "مدفوع جزئيًا", "غير مدفوع"], key="payment_filter")
            if filter_payment != "الكل":
                df_display = df_display[df_display["حالة الدفع"] == filter_payment]
            st.dataframe(df_display[["row_index","اللاعب","المبلغ","الطريقة","التاريخ","ملاحظات","حالة الدفع"]], use_container_width=True, hide_index=True)
            st.markdown("---")
            st.markdown("#### تعديل دفعة")
            row_num = st.number_input("أدخل رقم الصف (row_index) للتعديل", min_value=2, step=1, key="edit_row")
            selected_row = df[df["row_index"]==row_num]
            if not selected_row.empty:
                row = selected_row.iloc[0]
                st.write(f"اللاعب: {row['player_name']} | المبلغ الحالي: {row['amount']} | حالة الدفع: {get_player_payment_status(row['player_name'])}")
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
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(msg)
                with col2:
                    if st.button("🗑️ حذف الدفعة", key="btn_delete_payment"):
                        success, msg = delete_payment_record(row_num, row['player_name'])
                        if success:
                            st.success("✅ تم حذف الدفعة بنجاح!")
                            st.toast("✅ تم حذف الدفعة!", icon="🗑️")
                            time.sleep(2)
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
            df["المدفوع"] = df["اللاعب"].apply(calculate_total_paid_from_payments)
            df["المتبقي"] = df.apply(lambda r: max(0, float(r["القيمة"]) - float(r["المدفوع"])), axis=1)
            df["حالة الدفع"] = df["اللاعب"].apply(get_player_payment_status)
            sub_filter = st.selectbox("تصنيف حسب حالة الدفع", ["الكل", "مدفوع بالكامل", "مدفوع جزئيًا", "غير مدفوع"], key="sub_filter")
            if sub_filter != "الكل":
                df = df[df["حالة الدفع"] == sub_filter]
            def status_color(s):
                if s=="Active": return "🟢 نشط"
                elif s=="Expired": return "🔴 منتهي"
                else: return "🟡 معلق"
            df["الحالة"] = df["الحالة"].apply(status_color)
            st.dataframe(df[["اللاعب","القيمة","المدفوع","المتبقي","بداية","نهاية","الحالة","حالة الدفع"]], use_container_width=True, hide_index=True)
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
# صفحة تسجيل الدخول
# =============================================================================
def login_page():
    coach_exists = check_coach_exists()
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="login-icon">{get_logo_html(120)}</div>', unsafe_allow_html=True)
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
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
    with tab2:
        role_for_new = "player" if coach_exists else "coach"
        role_text = "لاعب" if coach_exists else "كابتن"
        st.markdown(f'<div class="info-box"><p>👋 سيتم تسجيلك كـ <strong>{role_text}</strong>.</p></div>', unsafe_allow_html=True)
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
                success, msg = add_user(new_user, new_pass, role_for_new)
                if success:
                    st.success(msg)
                    st.toast("✅ تم إنشاء الحساب بنجاح!", icon="🎉")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(msg)
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# الدالة الرئيسية
# =============================================================================
def main():
    init_session()
    if not st.session_state.sheets_initialized:
        if init_sheets():
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
