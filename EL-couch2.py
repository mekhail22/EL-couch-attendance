"""
نظام الكوتش أكاديمي - إدارة الحضور والاشتراكات الموسمية
=====================================================
- حضور/غياب حسب 3 فئات عمرية ثابتة (بنات، بنين ابتدائي، بنين إعدادي)
- حماية إدارة اللاعبين والتقارير المالية بكلمة مرور واحدة
- إحصائيات عامة وإحصائيات لكل فئة في سجل الحضور
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
import random
import string
from functools import wraps

# =============================================================================
# إعدادات الصفحة
# =============================================================================
st.set_page_config(page_title="الكوتش أكاديمي", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

# =============================================================================
# الشعار / الأيقونة
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
# أدوات مساعدة
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

def generate_random_password(length=6):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

# =============================================================================
# الفئات العمرية الثلاث
# =============================================================================
AGE_CATEGORIES = [
    "🏃‍♀️ بنات (جميع الأعمار)",
    "🏃 بنين (الصف الأول - الخامس الابتدائي)",
    "🏃 بنين (الصف السادس - الثاني الإعدادي)"
]

def normalize_age_group(age_str: str) -> str:
    """محاولة مطابقة النص القادم من الملف الخارجي مع إحدى الفئات الثلاث"""
    if not age_str:
        return None
    age_str = age_str.strip()
    for cat in AGE_CATEGORIES:
        if age_str == cat:
            return cat
    # إذا لم يتطابق، نحاول تصنيف تقريبي (اختياري)
    if "بنات" in age_str:
        return AGE_CATEGORIES[0]
    if "ابتدائي" in age_str or "الصف الأول" in age_str:
        return AGE_CATEGORIES[1]
    if "إعدادي" in age_str or "السادس" in age_str:
        return AGE_CATEGORIES[2]
    return None

# =============================================================================
# الاتصال بملفات Google Sheets
# =============================================================================
@st.cache_resource
def get_google_sheets_client():
    try:
        cred = st.secrets["google"]["service_account"]
        cred_dict = {
            "type": cred["type"], "project_id": cred["project_id"],
            "private_key_id": cred["private_key_id"],
            "private_key": cred["private_key"].replace("\\n", "\n"),
            "client_email": cred["client_email"], "client_id": cred["client_id"],
            "auth_uri": cred["auth_uri"], "token_uri": cred["token_uri"],
            "auth_provider_x509_cert_url": cred["auth_provider_x509_cert_url"],
            "client_x509_cert_url": cred["client_x509_cert_url"],
            "universe_domain": cred.get("universe_domain", "googleapis.com")
        }
        sid = st.secrets["google"]["spreadsheet_id"]
    except Exception as e:
        st.error(f"❌ إعدادات الملف الأساسي: {e}")
        return None, None
    try:
        credentials = Credentials.from_service_account_info(cred_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(credentials), sid
    except Exception as e:
        st.error(f"❌ اتصال الملف الأساسي: {e}")
        return None, None

@st.cache_resource
def get_external_sheets_client():
    try:
        _ = st.secrets["external_sheet"]
    except KeyError:
        return None, None
    try:
        cred = st.secrets["external_sheet"]["service_account"]
        cred_dict = {
            "type": cred["type"], "project_id": cred["project_id"],
            "private_key_id": cred["private_key_id"],
            "private_key": cred["private_key"].replace("\\n", "\n"),
            "client_email": cred["client_email"], "client_id": cred["client_id"],
            "auth_uri": cred["auth_uri"], "token_uri": cred["token_uri"],
            "auth_provider_x509_cert_url": cred["auth_provider_x509_cert_url"],
            "client_x509_cert_url": cred["client_x509_cert_url"],
            "universe_domain": cred.get("universe_domain", "googleapis.com")
        }
        sid = st.secrets["external_sheet"]["spreadsheet_id"]
    except Exception as e:
        st.error(f"❌ إعدادات الملف الخارجي: {e}")
        return None, None
    try:
        credentials = Credentials.from_service_account_info(cred_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(credentials), sid
    except Exception as e:
        st.error(f"❌ اتصال الملف الخارجي: {e}")
        return None, None

@st.cache_resource
def get_workbook():
    client, sid = get_google_sheets_client()
    if client and sid:
        try:
            return client.open_by_key(sid)
        except Exception as e:
            st.error(f"❌ فتح الملف الأساسي: {e}")
    return None

@st.cache_resource
def get_external_workbook():
    client, sid = get_external_sheets_client()
    if client and sid:
        try:
            return client.open_by_key(sid)
        except Exception as e:
            st.error(f"❌ فتح الملف الخارجي: {e}")
    return None

@st.cache_resource
def get_worksheet(sheet_name, external=False):
    wb = get_external_workbook() if external else get_workbook()
    if wb:
        try:
            return wb.worksheet(sheet_name)
        except Exception:
            return None
    return None

def init_sheets():
    wb = get_workbook()
    if not wb:
        return False
    required = {
        "Users": ("Users", ["username","password","role","age_group","created_at"], 1000),
        "Attendance": ("Attendance", ["player_name","date","status","recorded_by","created_at"], 50000),
        "Finance": ("Finance", ["player_name","season_fee","start_date","end_date",
                                "subscription_status","total_paid","last_payment_date","updated_at"], 1000),
        "Payments": ("Payments", ["player_name","amount","payment_method","payment_date",
                                  "notes","recorded_by","created_at"], 1000)
    }
    existing = {s.title: s for s in wb.worksheets()}
    for key, (title, headers, rows) in required.items():
        if key not in existing:
            sheet = wb.add_worksheet(title=title, rows=str(rows), cols=str(len(headers)))
            sheet.append_row(headers)
        else:
            sheet = existing[key]
            if set(sheet.row_values(1)) != set(headers):
                sheet.update('A1', [headers])
            if sheet.row_count < rows:
                sheet.add_rows(rows - sheet.row_count)
    get_worksheet.clear()
    return True

# =============================================================================
# قراءة البيانات
# =============================================================================
@retry_on_quota
def _get_all_records_safe(sheet_name, external=False):
    sheet = get_worksheet(sheet_name, external)
    if sheet:
        try:
            return sheet.get_all_records()
        except Exception as e:
            st.error(f"⚠️ قراءة {sheet_name}: {e}")
            return []
    return []

@st.cache_data(ttl=60)
def get_users_sheet_data(): return _get_all_records_safe("Users")
@st.cache_data(ttl=60)
def get_attendance_sheet_data(): return _get_all_records_safe("Attendance")
@st.cache_data(ttl=60)
def get_finance_sheet_data(): return _get_all_records_safe("Finance")
@st.cache_data(ttl=60)
def get_payments_sheet_data(): return _get_all_records_safe("Payments")

def clean_records(records):
    return [{k: v.strip() if isinstance(v, str) else v for k, v in row.items()} for row in records]

def get_all_users(): return clean_records(get_users_sheet_data())
def get_all_attendance(): return clean_records(get_attendance_sheet_data())
def get_all_finance(): return clean_records(get_finance_sheet_data())
def get_all_payments(): return clean_records(get_payments_sheet_data())

# =============================================================================
# استيراد من الملف الخارجي
# =============================================================================
def import_players_from_external():
    try:
        _ = st.secrets["external_sheet"]
    except KeyError:
        return False, "قسم [external_sheet] غير موجود في secrets.toml"
    try:
        cfg = st.secrets["external_sheet"]
        sheet_name = cfg.get("worksheet_name", "Players")
        name_col = cfg.get("name_column", "الاسم")
        group_col = cfg.get("group_column", "الفئة العمرية")
    except Exception as e:
        return False, f"خطأ في إعدادات الملف الخارجي: {e}"

    data = _get_all_records_safe(sheet_name, external=True)
    if not data:
        return False, "لا توجد بيانات في الملف الخارجي"
    current_users = {u["username"] for u in get_all_users()}
    added = 0
    for row in data:
        name = row.get(name_col, "").strip()
        age_raw = row.get(group_col, "").strip()
        age_cat = normalize_age_group(age_raw)
        if not name or name in current_users:
            continue
        pwd = generate_random_password()
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if append_row_to_sheet("Users", [name, pwd, "player", age_cat or age_raw, created]):
            added += 1
    return True, f"تم استيراد {added} لاعب جديد"

# =============================================================================
# دوال الكتابة
# =============================================================================
@retry_on_quota
def append_row_to_sheet(sheet_name, row_data):
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        init_sheets(); sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.append_row(row_data); st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ إضافة صف {sheet_name}: {e}")
            return False
    return False

@retry_on_quota
def append_rows_to_sheet(sheet_name, rows_data):
    if not rows_data: return True
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        init_sheets(); sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.append_rows(rows_data); st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ إضافة متعددة {sheet_name}: {e}")
            return False
    return False

@retry_on_quota
def update_cell_in_sheet(sheet_name, row, col, value):
    sheet = get_worksheet(sheet_name)
    if sheet is None:
        init_sheets(); sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.update_cell(row, col, value); st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ تحديث خلية: {e}")
            return False
    return False

@retry_on_quota
def delete_row_from_sheet(sheet_name, row_index):
    sheet = get_worksheet(sheet_name)
    if sheet:
        try:
            sheet.delete_rows(row_index); st.cache_data.clear()
            return True
        except Exception as e:
            st.error(f"❌ حذف صف: {e}")
            return False
    return False

# =============================================================================
# دوال المستخدمين
# =============================================================================
def get_user(username: str):
    for u in get_all_users():
        if u.get("username","").strip() == username.strip():
            return u
    return None

def check_coach_exists():
    return any(u.get("role","")=="coach" for u in get_all_users())

def add_user(username, password, role="player", age_group=""):
    if get_user(username): return False, "اسم المستخدم موجود"
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return append_row_to_sheet("Users", [username.strip(), password, role, age_group.strip(), created]), \
           "تمت الإضافة" if True else "خطأ"

def validate_triple_name(name):
    if not name: return False
    parts = name.strip().split()
    return len(parts)==3 and all(len(p)>=2 and re.match(r'^[\u0600-\u06FF]+$', p) for p in parts)

# =============================================================================
# الحضور والغياب
# =============================================================================
def is_attendance_recorded_today(name):
    today = datetime.now().strftime("%Y-%m-%d")
    return any(r["player_name"].strip()==name.strip() and r["date"]==today for r in get_all_attendance())

def record_attendance(name, status, recorded_by):
    if is_attendance_recorded_today(name):
        return False, f"{name} مسجل اليوم"
    today = datetime.now().strftime("%Y-%m-%d")
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return append_row_to_sheet("Attendance", [name.strip(), today, status, recorded_by.strip(), created]), \
           f"تم {'الحضور' if status=='Present' else 'الغياب'}"

def record_multiple_attendance(names, status, recorded_by):
    today = datetime.now().strftime("%Y-%m-%d")
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recorded_today = {r["player_name"].strip() for r in get_all_attendance() if r.get("date")==today}
    rows, skipped, cnt = [], [], 0
    for n in names:
        if n.strip() in recorded_today:
            skipped.append(n); continue
        rows.append([n.strip(), today, status, recorded_by.strip(), created])
        cnt += 1
    if rows and not append_rows_to_sheet("Attendance", rows):
        return False, "فشل التسجيل الجماعي"
    msg = f"✅ تم تسجيل {cnt} من {len(names)}"
    if skipped:
        msg += f" (تخطي {len(skipped)})"
    return True, msg

def get_player_attendance(name):
    return [r for r in get_all_attendance() if r["player_name"].strip()==name.strip()]

def get_attendance_stats(name):
    recs = get_player_attendance(name)
    if not recs: return {"total":0,"present":0,"absent":0,"percentage":0}
    total = len(recs)
    present = sum(1 for r in recs if r["status"]=="Present")
    return {"total":total,"present":present,"absent":total-present,"percentage":round(present/total*100,1) if total else 0}

def get_today_attendance():
    today = datetime.now().strftime("%Y-%m-%d")
    return [r for r in get_all_attendance() if r.get("date")==today]

# =============================================================================
# المالية
# =============================================================================
def get_player_finance(name):
    for r in get_all_finance():
        if r["player_name"].strip()==name.strip(): return r
    return None

def calculate_total_paid(name):
    return sum(float(p.get("amount",0)) for p in get_all_payments() if p["player_name"].strip()==name.strip())

def sync_total_paid(name):
    fin = get_player_finance(name)
    if not fin: return
    correct = calculate_total_paid(name)
    all_fin = get_all_finance()
    for i, r in enumerate(all_fin, start=2):
        if r["player_name"].strip()==name.strip():
            update_cell_in_sheet("Finance", i, 6, correct)
            payments = [p for p in get_all_payments() if p["player_name"].strip()==name.strip()]
            if payments:
                latest = max(p["payment_date"] for p in payments)
                update_cell_in_sheet("Finance", i, 7, latest)
            break

def get_payment_summary(name):
    fin = get_player_finance(name)
    if not fin: return {"season_fee":0,"total_paid":0,"remaining":0,"status":"No Subscription"}
    fee = float(fin.get("season_fee",0))
    paid = calculate_total_paid(name)
    return {"season_fee":fee,"total_paid":paid,"remaining":max(0,fee-paid),"status":fin.get("subscription_status","Unknown")}

def get_player_payment_status(name):
    s = get_payment_summary(name)
    if s["status"]=="No Subscription": return "لا يوجد اشتراك"
    if s["remaining"]<=0: return "مدفوع بالكامل"
    return "مدفوع جزئيًا" if s["total_paid"]>0 else "غير مدفوع"

def add_or_update_finance_record(name, fee, start, end, status, amt=0, method="", pdate="", notes=""):
    wb = get_workbook()
    if not wb: return False, "لا اتصال"
    sheet = get_worksheet("Finance") or (init_sheets(), get_worksheet("Finance"))[1]
    if not sheet: return False, "لا وصول للمالية"
    updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_fin = get_all_finance()
    row = None
    for i, r in enumerate(all_fin, start=2):
        if r["player_name"].strip()==name.strip():
            row = i; break
    if row:
        update_cell_in_sheet("Finance", row, 2, fee)
        update_cell_in_sheet("Finance", row, 3, start)
        update_cell_in_sheet("Finance", row, 4, end)
        update_cell_in_sheet("Finance", row, 5, status)
        update_cell_in_sheet("Finance", row, 8, updated)
        act = "تحديث"
    else:
        if not append_row_to_sheet("Finance", [name.strip(), fee, start, end, status, 0, "", updated]):
            return False, "فشل الإضافة"
        act = "إضافة"
    if amt>0:
        if not record_payment(name, amt, method, pdate, notes, st.session_state.username):
            return False, "تم الاشتراك لكن فشلت الدفعة"
        sync_total_paid(name)
    return True, f"تم {act} الاشتراك"

def delete_finance_record(name):
    all_fin = get_all_finance()
    for i, r in enumerate(all_fin, start=2):
        if r["player_name"].strip()==name.strip():
            return delete_row_from_sheet("Finance", i)
    return False

def record_payment(name, amount, method, pdate, notes="", recorded_by=""):
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if append_row_to_sheet("Payments", [name.strip(), amount, method, pdate, notes, recorded_by.strip(), created]):
        sync_total_paid(name)
        return True
    return False

def update_payment_record(row_idx, name, old_amt, new_amt, method, pdate, notes=""):
    sheet = get_worksheet("Payments")
    if sheet:
        update_cell_in_sheet("Payments", row_idx, 2, new_amt)
        update_cell_in_sheet("Payments", row_idx, 3, method)
        update_cell_in_sheet("Payments", row_idx, 4, pdate)
        update_cell_in_sheet("Payments", row_idx, 5, notes)
        sync_total_paid(name)
        return True
    return False

def delete_payment_record(row_idx, name):
    if get_worksheet("Payments") and delete_row_from_sheet("Payments", row_idx):
        sync_total_paid(name)
        return True
    return False

# =============================================================================
# الجلسة
# =============================================================================
def init_session():
    for k, v in {"logged_in":False,"username":None,"role":None,"current_page":"dashboard",
                 "finance_authenticated":False,"players_authenticated":False,"sheets_initialized":False}.items():
        if k not in st.session_state: st.session_state[k]=v

def login(u, p):
    user = get_user(u.strip())
    if user and user.get("password","").strip()==p.strip():
        st.session_state.logged_in = True
        st.session_state.username = u.strip()
        st.session_state.role = user.get("role","player").strip()
        st.session_state.current_page = "dashboard"
        st.session_state.finance_authenticated = False
        st.session_state.players_authenticated = False
        return True, "تم الدخول"
    return False, "بيانات خاطئة"

def logout():
    for k in ["logged_in","username","role","current_page","finance_authenticated","players_authenticated"]:
        st.session_state[k] = False if k=="logged_in" else (None if k in ["username","role"] else "login" if k=="current_page" else False)
    st.rerun()

def navigate_to(page):
    st.session_state.current_page = page
    st.rerun()

# =============================================================================
# CSS
# =============================================================================
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
*{font-family:'Cairo',sans-serif!important}.main{direction:rtl}
.stApp{background:radial-gradient(circle at top left,#0a1c14,#030a07)}
[data-testid="stSidebar"]{display:none!important}header[data-testid="stHeader"]{display:none!important}
.stDeployButton,.stActionButton,#MainMenu,footer,div[data-testid="stToolbar"],div[data-testid="stDecoration"],div[data-testid="stStatusWidget"]{display:none!important}
.nav-container{background:rgba(20,50,40,0.7);backdrop-filter:blur(12px);border-radius:50px;padding:10px 20px;margin:20px 0;box-shadow:0 8px 25px rgba(0,0,0,0.6);border:1px solid rgba(80,180,140,0.3)}
.nav-container .stButton>button{background:rgba(0,0,0,0.25)!important;color:#e0f0e8!important;border:1px solid #2a7a5f!important;border-radius:30px!important;padding:10px 15px!important;font-size:16px!important;font-weight:600!important;width:100%!important}
.nav-container .stButton>button:hover{background:#1f6e54!important;color:#fff!important;border-color:#4ecb9c!important}
.login-container{max-width:480px;margin:40px auto;padding:40px 35px;background:rgba(10,30,25,0.9);backdrop-filter:blur(10px);border-radius:30px;box-shadow:0 25px 50px rgba(0,0,0,0.7);text-align:center;border:1px solid #2c7a60}
.login-icon{margin-bottom:20px;display:flex;justify-content:center}
.login-title{color:#c0f0d0!important;font-size:42px!important;font-weight:800!important;margin-bottom:8px;text-shadow:0 4px 12px #0f2f22}
.login-subtitle{color:#a0d0b8!important;font-size:20px!important;font-weight:500!important;margin-bottom:30px}
.stat-card{background:linear-gradient(145deg,#15382b,#0c231a);color:#fff;border-radius:20px;padding:20px 10px;text-align:center;box-shadow:0 10px 20px rgba(0,0,0,0.5);border:1px solid #2f7a5a}
.stat-number{font-size:40px;font-weight:800;color:#b0f0c0;margin-bottom:5px}
.stat-label{font-size:15px;font-weight:500;color:#c0e0d0}
.welcome-box{background:linear-gradient(145deg,#1a5a44,#0e3628);color:#fff;padding:20px;border-radius:20px;margin-bottom:20px;text-align:center;box-shadow:0 8px 20px rgba(0,0,0,0.4);border:1px solid #3fa07c}
.info-box{background:#163f31;border-right:6px solid #40c090;padding:15px 20px;border-radius:16px;margin-bottom:20px;color:#e0f5e8!important;font-weight:500}
.stButton>button{background:linear-gradient(145deg,#1f6e54,#144d3a);color:#fff;border:none;border-radius:14px;padding:12px 25px;font-size:16px;font-weight:600;width:100%;box-shadow:0 6px 15px rgba(0,20,0,0.5);border:1px solid #3da07a}
.stButton>button:hover{background:#2a8f6a;transform:translateY(-2px);box-shadow:0 10px 25px rgba(40,180,120,0.4)}
.stTextInput>div>div>input{border-radius:14px;border:1.5px solid #2e7a5c;padding:12px 15px;text-align:right;background:#0f2b20;color:#f0faf0}
.stTabs [data-baseweb="tab-list"]{gap:8px}
.stTabs [data-baseweb="tab"]{background:#13382a;border-radius:16px 16px 0 0;padding:10px 22px;color:#c8e8d8;border:1px solid #2f785a;border-bottom:none;font-weight:600}
.stTabs [aria-selected="true"]{background:#1f6e54!important;color:#fff!important;border-color:#50c898}
.user-info{color:#e0f0e4;font-size:16px;font-weight:600;padding:10px 0;text-align:center;background:rgba(20,60,45,0.6);border-radius:30px;border:1px solid #3d8e6e}
.stDataFrame{border-radius:18px;border:1px solid #2f785a;overflow:hidden;background:#0a1f16}
h1,h2,h3,h4,h5,h6{color:#c0f0d0!important}p,span,div{color:#d0e8dc}
</style>""", unsafe_allow_html=True)

# =============================================================================
# شريط التنقل
# =============================================================================
def navigation_bar():
    col_logo, col_title, col_user = st.columns([0.7, 2.5, 1.2])
    with col_logo: st.markdown(get_logo_html(50), unsafe_allow_html=True)
    with col_title: st.markdown('<h2 style="color:#c0f0d0; margin:0; font-size:26px; text-align:right; padding-right:10px;">⚽ الكوتش أكاديمي</h2>', unsafe_allow_html=True)
    with col_user:
        icon = "👨‍🏫" if st.session_state.role=="coach" else "👤"
        txt = "كابتن" if st.session_state.role=="coach" else "لاعب"
        st.markdown(f'<div class="user-info">{icon} {st.session_state.username} ({txt})</div>', unsafe_allow_html=True)

    if st.session_state.role=="coach":
        pages = {
            "dashboard":"📊 لوحة التحكم",
            "attendance":"✅ تسجيل الحضور",
            "attendance_history":"📋 سجل الحضور",
            "subscriptions_payments":"💳 الاشتراكات والمدفوعات",
            "players":"👥 إدارة اللاعبين",
            "finance_reports":"🔒 التقارير المالية"
        }
    else:
        pages = {"dashboard":"📊 ملخصي","my_attendance":"📋 سجل الحضور","my_subscription":"💳 اشتراكي ومدفوعاتي"}

    with st.container():
        st.markdown('<div class="nav-container">', unsafe_allow_html=True)
        cols = st.columns(len(pages)+1)
        for i, (k, lbl) in enumerate(pages.items()):
            with cols[i]:
                active = st.session_state.current_page==k
                if st.button(lbl, key=f"nav_{k}", use_container_width=True, type="primary" if active else "secondary"):
                    navigate_to(k)
        with cols[-1]:
            if st.button("🚪 تسجيل الخروج", key="nav_logout", use_container_width=True): logout()
        st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# جدار المصادقة (كلمة مرور واحدة للاعبين والمالية)
# =============================================================================
def auth_wall(page_type="finance"):
    if page_type=="finance":
        st.markdown("## 🔐 التقارير المالية")
    else:
        st.markdown("## 🔐 إدارة اللاعبين")
    st.markdown("أدخل كلمة المرور للمتابعة")
    pwd = st.text_input("كلمة المرور", type="password", key=f"auth_{page_type}")
    if st.button("تحقق", key=f"btn_auth_{page_type}"):
        secret = st.secrets.get("app",{}).get("finance_password","")
        if pwd == secret:
            if page_type=="finance":
                st.session_state.finance_authenticated = True
            else:
                st.session_state.players_authenticated = True
            st.rerun()
        else:
            st.error("❌ كلمة مرور غير صحيحة")
    st.stop()

# =============================================================================
# صفحات الكابتن
# =============================================================================
def coach_dashboard_page():
    st.markdown("# 📊 لوحة التحكم")
    st.markdown(f"مرحباً، **{st.session_state.username}** 👋")
    users = get_all_users()
    players = [u for u in users if u.get("role")=="player"]
    today_att = get_today_attendance()
    # إحصائيات عامة
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-number">{len(players)}</div><div class="stat-label">👥 إجمالي اللاعبين</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-number">{sum(1 for a in today_att if a["status"]=="Present")}</div><div class="stat-label">✅ الحضور اليوم</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-number">{sum(1 for a in today_att if a["status"]=="Absent")}</div><div class="stat-label">❌ الغياب اليوم</div></div>',unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="stat-card"><div class="stat-number">{max(0,len(players)-len(today_att))}</div><div class="stat-label">⏳ لم يُسجل</div></div>',unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 إحصائيات الفئات العمرية")
    # تجميع اللاعبين حسب category المعياري
    cat_players = {c:[] for c in AGE_CATEGORIES}
    for p in players:
        norm = normalize_age_group(p.get("age_group",""))
        if norm: cat_players[norm].append(p["username"].strip())
    cols = st.columns(len(AGE_CATEGORIES))
    for i, (cat, plist) in enumerate(cat_players.items()):
        with cols[i]:
            present = sum(1 for a in today_att if a["player_name"].strip() in plist and a["status"]=="Present")
            absent = sum(1 for a in today_att if a["player_name"].strip() in plist and a["status"]=="Absent")
            st.markdown(f'<div class="stat-card"><div style="font-size:20px;font-weight:700;">{cat}</div>'
                        f'<div style="font-size:16px;margin-top:10px;">👥 {len(plist)}</div>'
                        f'<div style="font-size:14px;">✅ {present} | ❌ {absent}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 آخر سجلات الحضور")
    att = get_all_attendance()
    if att:
        df = pd.DataFrame(att[-10:])
        df = df.rename(columns={"player_name":"اللاعب","date":"التاريخ","status":"الحالة","recorded_by":"سجل بواسطة"})
        df["الحالة"] = df["الحالة"].apply(lambda x:"✅ حاضر" if x=="Present" else "❌ غائب")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات")

def coach_attendance_page():
    st.markdown("# ✅ تسجيل الحضور والغياب (فئات عمرية)")
    users = get_all_users()
    # تجميع اللاعبين حسب الفئات المعيارية
    cat_players = {c:[] for c in AGE_CATEGORIES}
    for u in users:
        if u.get("role")!="player": continue
        norm = normalize_age_group(u.get("age_group",""))
        if norm: cat_players[norm].append(u["username"].strip())
    if not any(cat_players.values()):
        st.warning("لا يوجد لاعبون")
        return
    st.date_input("📅 تاريخ التسجيل", value=date.today())
    st.markdown("---")
    # اختيار الفئة
    selected_cat = st.selectbox("اختر الفئة العمرية", AGE_CATEGORIES)
    players = cat_players[selected_cat]
    if not players:
        st.info("لا يوجد لاعبون في هذه الفئة")
        return
    st.markdown(f"### 🏷️ {selected_cat} ({len(players)} لاعب)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"✅ حضور كل {selected_cat}", key=f"present_all_{selected_cat}"):
            ok, msg = record_multiple_attendance(players, "Present", st.session_state.username)
            if ok: st.success(msg); st.toast("✅ تم تسجيل الحضور"); time.sleep(2); st.rerun()
            else: st.error(msg)
    with col2:
        if st.button(f"❌ غياب كل {selected_cat}", key=f"absent_all_{selected_cat}"):
            ok, msg = record_multiple_attendance(players, "Absent", st.session_state.username)
            if ok: st.success(msg); st.toast("✅ تم تسجيل الغياب"); time.sleep(2); st.rerun()
            else: st.error(msg)
    # اختيار محددين
    present_sel = st.multiselect("اختر الحاضرين", players, key=f"present_{selected_cat}")
    if st.button("تسجيل حضور المحددين", key=f"btn_pres_{selected_cat}"):
        if present_sel:
            ok, msg = record_multiple_attendance(present_sel, "Present", st.session_state.username)
            if ok: st.success(msg); st.rerun()
            else: st.error(msg)
        else: st.warning("اختر لاعباً واحداً على الأقل")
    absent_sel = st.multiselect("اختر الغائبين", [p for p in players if p not in present_sel], key=f"absent_{selected_cat}")
    if st.button("تسجيل غياب المحددين", key=f"btn_abs_{selected_cat}"):
        if absent_sel:
            ok, msg = record_multiple_attendance(absent_sel, "Absent", st.session_state.username)
            if ok: st.success(msg); st.rerun()
            else: st.error(msg)

def coach_attendance_history_page():
    st.markdown("# 📋 سجل الحضور")
    users = get_all_users()
    players = ["الكل"] + [u["username"].strip() for u in users if u.get("role")=="player"]
    c1,c2,c3 = st.columns(3)
    with c1: fp = st.selectbox("اللاعب", players)
    with c2: fs = st.selectbox("الحالة", ["الكل","Present","Absent"], format_func=lambda x:"الكل" if x=="الكل" else ("✅ حاضر" if x=="Present" else "❌ غائب"))
    with c3: fd = st.date_input("التاريخ", value=None)
    records = get_all_attendance()
    if fp!="الكل": records = [r for r in records if r["player_name"].strip()==fp]
    if fs!="الكل": records = [r for r in records if r["status"]==fs]
    if fd: records = [r for r in records if r["date"]==fd.strftime("%Y-%m-%d")]
    if records:
        df = pd.DataFrame(records)
        df = df.rename(columns={"player_name":"اللاعب","date":"التاريخ","status":"الحالة"})
        df["الحالة"] = df["الحالة"].apply(lambda x:"✅ حاضر" if x=="Present" else "❌ غائب")
        st.dataframe(df.sort_values("التاريخ", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد سجلات")
    # إحصائيات عامة ولكل فئة
    st.markdown("---")
    st.markdown("## 📊 إحصائيات الحضور")
    all_att = get_all_attendance()
    total_sessions = len(all_att)
    overall_present = sum(1 for r in all_att if r["status"]=="Present")
    st.write(f"**إجمالي التسجيلات:** {total_sessions} | **حضور:** {overall_present} | **غياب:** {total_sessions-overall_present}")
    # لكل فئة
    cat_stats = {c:{"total":0,"present":0} for c in AGE_CATEGORIES}
    user_map = {u["username"].strip(): normalize_age_group(u.get("age_group","")) for u in users if u.get("role")=="player"}
    for r in all_att:
        cat = user_map.get(r["player_name"].strip())
        if cat:
            cat_stats[cat]["total"] += 1
            if r["status"]=="Present":
                cat_stats[cat]["present"] += 1
    st.markdown("### حسب الفئة العمرية")
    for cat, sts in cat_stats.items():
        t = sts["total"]
        p = sts["present"]
        a = t-p
        rate = f"{p/t*100:.1f}%" if t else "0%"
        st.write(f"{cat}: 👥 {t} | ✅ {p} | ❌ {a} | 📊 {rate}")

def coach_subscriptions_payments_page():
    st.markdown("# 💳 الاشتراكات والمدفوعات")
    tabs = st.tabs(["➕ تسجيل اشتراك جديد","✏️ تعديل اشتراك","💰 إدارة المدفوعات","📋 عرض الاشتراكات"])
    with tabs[0]:
        st.markdown("### تسجيل اشتراك (مع دفعة أولى)")
        users = get_all_users()
        existing = {f["player_name"] for f in get_all_finance()}
        players = [u["username"].strip() for u in users if u.get("role")=="player" and u["username"].strip() not in existing]
        if not players: st.info("جميع اللاعبين لديهم اشتراكات")
        else:
            sel = st.selectbox("اختر اللاعب", players, key="new_fin")
            c1,c2 = st.columns(2)
            with c1: fee = st.number_input("القيمة", min_value=0.0, step=50.0, key="nfee")
            with c2: status = st.selectbox("الحالة", ["Active","Expired","Suspended"], format_func=lambda x:"🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"), key="nstat")
            c3,c4 = st.columns(2)
            with c3: start = st.date_input("بداية الموسم", value=date.today(), key="nstart")
            with c4: end = st.date_input("نهاية الموسم", value=date.today()+timedelta(days=90), key="nend")
            st.markdown("---")
            st.markdown("#### الدفعة الأولى")
            p1,p2 = st.columns(2)
            with p1: amt = st.number_input("المبلغ", min_value=0.0, value=fee, step=50.0, key="namt")
            with p2: method = st.selectbox("طريقة الدفع", ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"], key="nmethod")
            pdate = st.date_input("تاريخ الدفع", value=date.today(), key="npdate")
            notes = st.text_area("ملاحظات", key="nnotes")
            if st.button("💾 حفظ", key="nbtn"):
                if fee<=0 or amt<=0: st.error("قيم غير صحيحة")
                else:
                    ok, msg = add_or_update_finance_record(sel, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status, amt, method, pdate.strftime("%Y-%m-%d"), notes)
                    if ok: st.success("✅ تم"); st.toast("اشتراك جديد"); time.sleep(2); st.rerun()
                    else: st.error(msg)
    with tabs[1]:
        st.markdown("### تعديل اشتراك")
        fin = get_all_finance()
        if not fin: st.info("لا توجد اشتراكات")
        else:
            all_players = [f["player_name"] for f in fin]
            filter_pay = st.selectbox("حالة الدفع", ["الكل","مدفوع بالكامل","مدفوع جزئيًا","غير مدفوع"], key="efilter")
            filtered = [p for p in all_players if filter_pay=="الكل" or get_player_payment_status(p)==filter_pay]
            if not filtered: st.info("لا يوجد")
            else:
                sel = st.selectbox("اختر اللاعب", filtered, key="eplayer")
                cur = next((f for f in fin if f["player_name"]==sel), None)
                if cur:
                    c1,c2 = st.columns(2)
                    with c1: fee = st.number_input("القيمة", value=float(cur.get("season_fee",0)), step=50.0, key="efee")
                    with c2: opts=["Active","Expired","Suspended"]; idx=opts.index(cur.get("subscription_status","Active")) if cur.get("subscription_status","Active") in opts else 0
                    status = st.selectbox("الحالة", opts, index=idx, format_func=lambda x:"🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"), key="estat")
                    c3,c4 = st.columns(2)
                    with c3: start = st.date_input("بداية", value=datetime.strptime(cur.get("start_date",date.today().strftime("%Y-%m-%d")),"%Y-%m-%d").date(), key="estart")
                    with c4: end = st.date_input("نهاية", value=datetime.strptime(cur.get("end_date",(date.today()+timedelta(days=90)).strftime("%Y-%m-%d")),"%Y-%m-%d").date(), key="eend")
                    col1,col2 = st.columns(2)
                    with col1:
                        if st.button("📝 تحديث", key="eupdate"):
                            ok, _ = add_or_update_finance_record(sel, fee, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), status)
                            if ok: st.success("✅ تم"); st.rerun()
                    with col2:
                        if st.button("🗑️ حذف الاشتراك", key="edel"):
                            if delete_finance_record(sel): st.success("✅ تم"); st.rerun()
    with tabs[2]:
        st.markdown("### إدارة المدفوعات")
        payments = get_all_payments()
        if not payments: st.info("لا مدفوعات")
        else:
            df = pd.DataFrame(payments); df["row_index"]=range(2,len(payments)+2)
            df["state"]=df["player_name"].apply(get_player_payment_status)
            disp = df.rename(columns={"player_name":"اللاعب","amount":"المبلغ","payment_method":"الطريقة","payment_date":"التاريخ","notes":"ملاحظات","state":"حالة الدفع"})
            fpay = st.selectbox("حالة الدفع", ["الكل","مدفوع بالكامل","مدفوع جزئيًا","غير مدفوع"], key="pfilt")
            if fpay!="الكل": disp=disp[disp["حالة الدفع"]==fpay]
            st.dataframe(disp[["row_index","اللاعب","المبلغ","الطريقة","التاريخ","ملاحظات","حالة الدفع"]], use_container_width=True, hide_index=True)
            row_num = st.number_input("رقم الصف للتعديل", min_value=2, step=1, key="erow")
            row = df[df["row_index"]==row_num]
            if not row.empty:
                r = row.iloc[0]
                st.write(f"اللاعب: {r['player_name']} | المبلغ: {r['amount']} | الحالة: {get_player_payment_status(r['player_name'])}")
                new_amt = st.number_input("المبلغ الجديد", value=float(r['amount']), step=50.0, key="eamt")
                new_meth = st.selectbox("الطريقة", ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"], index=["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"].index(r['payment_method']) if r['payment_method'] in ["Cash","InstaPay","Vodafone Cash","Bank Transfer","Other"] else 0, key="emeth")
                new_date = st.date_input("التاريخ", value=datetime.strptime(r['payment_date'],"%Y-%m-%d").date(), key="edate")
                new_notes = st.text_area("ملاحظات", value=r.get('notes',''), key="enotes")
                c1,c2 = st.columns(2)
                with c1:
                    if st.button("📝 تحديث الدفعة", key="updpay"):
                        if update_payment_record(row_num, r['player_name'], float(r['amount']), new_amt, new_meth, new_date.strftime("%Y-%m-%d"), new_notes):
                            st.success("✅ تم"); st.rerun()
                with c2:
                    if st.button("🗑️ حذف الدفعة", key="delpay"):
                        if delete_payment_record(row_num, r['player_name']): st.success("✅ تم"); st.rerun()
    with tabs[3]:
        st.markdown("### الاشتراكات المسجلة")
        finance = get_all_finance()
        if finance:
            df = pd.DataFrame(finance)
            df = df.rename(columns={"player_name":"اللاعب","season_fee":"القيمة","start_date":"بداية","end_date":"نهاية","subscription_status":"الحالة","total_paid":"المدفوع"})
            df["المدفوع"] = df["اللاعب"].apply(calculate_total_paid)
            df["المتبقي"] = df.apply(lambda r: max(0,float(r["القيمة"])-float(r["المدفوع"])), axis=1)
            df["حالة الدفع"] = df["اللاعب"].apply(get_player_payment_status)
            subf = st.selectbox("حالة الدفع", ["الكل","مدفوع بالكامل","مدفوع جزئيًا","غير مدفوع"], key="subf")
            if subf!="الكل": df=df[df["حالة الدفع"]==subf]
            df["الحالة"] = df["الحالة"].apply(lambda x:"🟢 نشط" if x=="Active" else ("🔴 منتهي" if x=="Expired" else "🟡 معلق"))
            st.dataframe(df[["اللاعب","القيمة","المدفوع","المتبقي","بداية","نهاية","الحالة","حالة الدفع"]], use_container_width=True, hide_index=True)
        else: st.info("لا توجد اشتراكات")

def coach_players_page():
    if not st.session_state.get("players_authenticated", False):
        auth_wall("players")
        return
    st.markdown("# 👥 إدارة اللاعبين (محمية)")
    if "external_sheet" in st.secrets:
        if st.button("🔄 مزامنة اللاعبين من الملف الخارجي", use_container_width=True):
            ok, msg = import_players_from_external()
            if ok: st.success(msg); st.toast("✅ مزامنة"); time.sleep(2); st.rerun()
            else: st.error(msg)
    users = get_all_users()
    players = [u for u in users if u.get("role")=="player"]
    if not players: st.info("لا لاعبين"); return
    sel = st.selectbox("اختر لاعب", [p["username"].strip() for p in players])
    if sel:
        pdata = next(p for p in players if p["username"].strip()==sel)
        c1,c2 = st.columns(2)
        with c1:
            st.write(f"**الاسم:** {pdata['username']}")
            st.write(f"**كلمة المرور:** {pdata['password']}")
            st.write(f"**الفئة:** {pdata.get('age_group','')}")
            st.write(f"**نسبة الحضور:** {get_attendance_stats(sel)['percentage']}%")
        with c2:
            sub = get_player_finance(sel)
            if sub:
                st.write(f"القيمة: {sub.get('season_fee')} | المدفوع: {sub.get('total_paid')} | المتبقي: {max(0,float(sub.get('season_fee',0))-float(sub.get('total_paid',0))):.0f}")
                st.write(f"الحالة: {'🟢' if sub.get('subscription_status')=='Active' else '🔴'}")
            else: st.write("لا اشتراك")
    st.markdown("---")
    st.dataframe(pd.DataFrame([{**p, 'نسبة الحضور': f"{get_attendance_stats(p['username'])['percentage']}%"} for p in players]).rename(columns={"username":"اللاعب","password":"كلمة المرور","age_group":"الفئة"})[["اللاعب","الفئة","كلمة المرور","نسبة الحضور"]], use_container_width=True, hide_index=True)

def coach_finance_reports_page():
    if not st.session_state.get("finance_authenticated", False):
        auth_wall("finance")
        return
    st.markdown("# 📊 التقارير المالية")
    fin = get_all_finance()
    if not fin: st.info("لا بيانات"); return
    df = pd.DataFrame(fin)
    df["season_fee"] = df["season_fee"].astype(float)
    df["total_paid"] = df["player_name"].apply(calculate_total_paid)
    df["remaining"] = df["season_fee"] - df["total_paid"]
    df["payment_status"] = df.apply(lambda r: "مدفوع بالكامل" if r["remaining"]<=0 else ("مدفوع جزئيًا" if r["total_paid"]>0 else "غير مدفوع"), axis=1)
    flt = st.selectbox("تصنيف", ["الكل","مدفوع بالكامل","مدفوع جزئيًا","غير مدفوع"])
    if flt!="الكل": df=df[df["payment_status"]==flt]
    total_fee = df["season_fee"].sum()
    total_paid = df["total_paid"].sum()
    total_rem = df["remaining"].sum()
    rate = (total_paid/total_fee*100) if total_fee else 0
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-number">{total_fee:,.0f}</div><div class="stat-label">💰 المستحق</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-number">{total_paid:,.0f}</div><div class="stat-label">💵 المدفوع</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-number">{total_rem:,.0f}</div><div class="stat-label">📉 المتبقي</div></div>',unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="stat-card"><div class="stat-number">{rate:.1f}%</div><div class="stat-label">📈 التحصيل</div></div>',unsafe_allow_html=True)
    st.dataframe(df[["player_name","season_fee","total_paid","remaining","payment_status","subscription_status"]].rename(columns={"player_name":"اللاعب","season_fee":"القيمة","total_paid":"المدفوع","remaining":"المتبقي","payment_status":"حالة الدفع","subscription_status":"الحالة"}), use_container_width=True, hide_index=True)

# =============================================================================
# صفحات اللاعب
# =============================================================================
def player_dashboard_page():
    st.markdown("# 📊 ملخصي")
    st.markdown(f"مرحباً **{st.session_state.username}** 👋")
    stats = get_attendance_stats(st.session_state.username)
    c1,c2,c3 = st.columns(3)
    with c1: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["percentage"]}%</div><div class="stat-label">نسبة الحضور</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["present"]}</div><div class="stat-label">الحضور</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="stat-card"><div class="stat-number">{stats["absent"]}</div><div class="stat-label">الغياب</div></div>',unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("## 💳 الاشتراك والمدفوعات")
    summ = get_payment_summary(st.session_state.username)
    sub = get_player_finance(st.session_state.username)
    if sub:
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.metric("القيمة", f"{summ['season_fee']:,.0f} جنيه")
        with c2: st.metric("المدفوع", f"{summ['total_paid']:,.0f} جنيه")
        with c3: st.metric("المتبقي", f"{summ['remaining']:,.0f} جنيه")
        with c4: st.metric("الحالة", "🟢 نشط" if summ['status']=="Active" else "🔴 غير نشط")
        st.write(f"الموسم: {sub.get('start_date')} - {sub.get('end_date')}")

def player_attendance_page():
    st.markdown("# 📋 سجل حضوري")
    recs = get_player_attendance(st.session_state.username)
    if recs:
        df = pd.DataFrame(recs)[["date","status"]].rename(columns={"date":"التاريخ","status":"الحالة"})
        df["الحالة"] = df["الحالة"].apply(lambda x:"✅ حاضر" if x=="Present" else "❌ غائب")
        st.dataframe(df.sort_values("التاريخ", ascending=False), hide_index=True)

def player_subscription_page():
    st.markdown("# 💳 اشتراكي ومدفوعاتي")
    summ = get_payment_summary(st.session_state.username)
    sub = get_player_finance(st.session_state.username)
    if sub:
        st.write(f"القيمة: {summ['season_fee']:,.0f} | المدفوع: {summ['total_paid']:,.0f} | المتبقي: {summ['remaining']:,.0f}")
        st.write(f"الموسم: {sub.get('start_date')} - {sub.get('end_date')}")
        st.write(f"الحالة: {'🟢 نشط' if sub.get('subscription_status')=='Active' else '🔴 غير نشط'}")

# =============================================================================
# صفحة تسجيل الدخول
# =============================================================================
def login_page():
    coach = check_coach_exists()
    st.markdown('<div class="login-container">',unsafe_allow_html=True)
    st.markdown(f'<div class="login-icon">{get_logo_html(120)}</div>',unsafe_allow_html=True)
    st.markdown('<div class="login-title">الكوتش أكاديمي</div>',unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">نظام إدارة الحضور والاشتراكات الموسمية</div>',unsafe_allow_html=True)
    if not coach:
        st.markdown('<div class="welcome-box"><h3>👋 مرحباً بك!</h3><p>سيتم تسجيلك كـ <strong>كابتن</strong>.</p></div>',unsafe_allow_html=True)
    else:
        st.markdown('<div class="welcome-box"><h3>👋 مرحباً بك!</h3><p>قم بتسجيل الدخول أو إنشاء حساب جديد.</p></div>',unsafe_allow_html=True)
    t1,t2 = st.tabs(["🔐 تسجيل الدخول","📝 حساب جديد"])
    with t1:
        u = st.text_input("اسم المستخدم (الاسم الثلاثي)", key="login_user")
        p = st.text_input("كلمة المرور", type="password", key="login_pass")
        if st.button("تسجيل الدخول"):
            if u and p:
                ok, msg = login(u, p)
                if ok: st.success(msg); st.toast("✅ تم الدخول"); time.sleep(2); st.rerun()
                else: st.error(msg)
            else: st.error("أكمل الحقول")
    with t2:
        role_new = "player" if coach else "coach"
        role_txt = "لاعب" if coach else "كابتن"
        st.markdown(f'<div class="info-box"><p>👋 سيتم تسجيلك كـ <strong>{role_txt}</strong>.</p></div>',unsafe_allow_html=True)
        nu = st.text_input("الاسم الثلاثي", key="reg_user")
        np = st.text_input("كلمة المرور", type="password", key="reg_pass")
        nc = st.text_input("تأكيد كلمة المرور", type="password", key="reg_confirm")
        if st.button("تسجيل حساب جديد"):
            if not nu or not np: st.error("أكمل الحقول")
            elif not validate_triple_name(nu): st.error("الاسم ثلاثي فقط")
            elif np!=nc: st.error("كلمتا المرور غير متطابقتين")
            elif len(np)<6: st.error("كلمة المرور 6 أحرف على الأقل")
            else:
                ok, msg = add_user(nu, np, role_new, "")
                if ok: st.success(msg); st.toast("✅ تم التسجيل"); time.sleep(2); st.rerun()
                else: st.error(msg)
    st.markdown('</div>',unsafe_allow_html=True)

# =============================================================================
# الدالة الرئيسية
# =============================================================================
def main():
    init_session()
    if not st.session_state.sheets_initialized:
        if init_sheets(): st.session_state.sheets_initialized = True
    if not st.session_state.logged_in:
        login_page()
    else:
        navigation_bar()
        page = st.session_state.current_page
        if st.session_state.role=="coach":
            if page=="dashboard": coach_dashboard_page()
            elif page=="attendance": coach_attendance_page()
            elif page=="attendance_history": coach_attendance_history_page()
            elif page=="subscriptions_payments": coach_subscriptions_payments_page()
            elif page=="players": coach_players_page()
            elif page=="finance_reports": coach_finance_reports_page()
            else: coach_dashboard_page()
        else:
            if page=="dashboard": player_dashboard_page()
            elif page=="my_attendance": player_attendance_page()
            elif page=="my_subscription": player_subscription_page()
            else: player_dashboard_page()

if __name__=="__main__":
    main()
