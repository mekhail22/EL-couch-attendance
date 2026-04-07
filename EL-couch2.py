""")
st.stop()

# ============================================================
# SECTION 2: إعدادات الصفحة والتنسيق
# ============================================================

st.set_page_config(
page_title="الكوتش أكاديمي - نظام إدارة الأكاديمية",
page_icon="⚽",
layout="wide",
initial_sidebar_state="expanded",
menu_items={
    'Get Help': 'https://www.example.com/help',
    'Report a bug': "https://www.example.com/bug",
    'About': "تطبيق إدارة أكاديمية الكوتش أكاديمي - الإصدار 2.0"
}
)

# ============================================================
# SECTION 3: تعريف CSS بشكل آمن (بدون أخطاء)
# ============================================================

# ملاحظة: تم وضع CSS داخل سلسلة نصية باستخدام triple quotes،
# ولا توجد أية أحرف # خارج السياق. هذا آمن تماماً في Python.

_css_styles = """
<style>
/* تنسيق عام للصفحة */
.main-header {
background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
padding: 1.5rem;
border-radius: 10px;
color: white;
text-align: center;
margin-bottom: 2rem;
}
.main-header h1 {
margin: 0;
font-size: 2.5rem;
}
.main-header p {
margin: 0.5rem 0 0;
opacity: 0.9;
}
/* تنسيق البطاقات */
.card {
background-color: #f8f9fa;
border-radius: 10px;
padding: 1.5rem;
box-shadow: 0 2px 4px rgba(0,0,0,0.1);
margin-bottom: 1rem;
border-right: 4px solid #2a5298;
}
.metric-card {
background: white;
border-radius: 10px;
padding: 1rem;
text-align: center;
box-shadow: 0 2px 8px rgba(0,0,0,0.1);
transition: transform 0.2s;
}
.metric-card:hover {
transform: translateY(-5px);
}
.metric-value {
font-size: 2rem;
font-weight: bold;
color: #1e3c72;
}
.metric-label {
font-size: 0.9rem;
color: #666;
}
/* تنسيق الأزرار */
.stButton button {
width: 100%;
border-radius: 8px;
font-weight: bold;
transition: all 0.3s;
}
.stButton button:hover {
transform: scale(1.02);
}
/* تنسيق الشريط الجانبي */
[data-testid="stSidebar"] {
background-color: #f0f2f6;
padding: 1rem;
}
.user-info {
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
padding: 1rem;
border-radius: 10px;
color: white;
margin-bottom: 1rem;
text-align: center;
}
/* تنسيق التبويبات */
.stTabs [data-baseweb="tab-list"] {
gap: 8px;
}
.stTabs [data-baseweb="tab"] {
border-radius: 8px;
padding: 8px 16px;
font-weight: bold;
}
/* تنسيق الجداول */
.stDataFrame {
direction: ltr;
}
/* تنسيق الإشعارات */
.stAlert {
border-radius: 8px;
}
/* تنسيق حقول الإدخال */
.stTextInput input, .stSelectbox select, .stNumberInput input {
border-radius: 8px;
}
/* تنسيق معلومات المستخدم */
h1, h2, h3, h4, h5, h6 {
font-family: 'Tahoma', 'Arial', sans-serif;
}
/* تنسيق شريط التقدم */
div[data-testid="stProgress"] {
direction: ltr;
}
</style>
"""

st.markdown(_css_styles, unsafe_allow_html=True)

# ============================================================
# SECTION 4: دوال الاتصال بـ Google Sheets (مُحسّنة)
# ============================================================

@st.cache_resource(ttl=3600, show_spinner=False)
def get_google_sheets_client():
"""
إنشاء عميل Google Sheets باستخدام بيانات Service Account من secrets.toml.
يتم تخزين العميل في الكاش لتحسين الأداء ولمدة ساعة.
"""
try:
    # التحقق من وجود secrets بشكل صحيح
    if "google" not in st.secrets:
        st.error("❌ خطأ: لم يتم العثور على إعدادات Google في secrets.toml.")
        st.stop()
    if "service_account" not in st.secrets["google"]:
        st.error("❌ خطأ: لم يتم العثور على service_account في secrets.google.")
        st.stop()
    if "spreadsheet_id" not in st.secrets["google"]:
        st.error("❌ خطأ: لم يتم العثور على spreadsheet_id في secrets.google.")
        st.stop()
    
    service_account_info = dict(st.secrets["google"]["service_account"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(credentials)
    return client
except Exception as e:
    st.error(f"⚠️ خطأ في الاتصال بـ Google Sheets: {str(e)}")
    st.stop()

def get_spreadsheet():
"""الحصول على كائن جدول البيانات باستخدام Spreadsheet ID"""
client = get_google_sheets_client()
try:
    spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
    return client.open_by_key(spreadsheet_id)
except Exception as e:
    st.error(f"⚠️ لا يمكن الوصول إلى جدول البيانات: {str(e)}")
    st.stop()

@st.cache_data(ttl=30, show_spinner=False)
def load_dataframe(sheet_name: str) -> pd.DataFrame:
"""
تحميل ورقة كاملة وتحويلها إلى DataFrame مع تخزين مؤقت لمدة 30 ثانية.
إذا لم تكن الورقة موجودة، يتم إنشاؤها تلقائياً مع الأعمدة المناسبة.
"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # تحويل الأعمدة الرقمية
        numeric_cols = ['amount', 'monthly_fee']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    else:
        return pd.DataFrame()
except gspread.WorksheetNotFound:
    # إنشاء الورقة إذا لم تكن موجودة
    spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    # إضافة رؤوس الأعمدة حسب نوع الورقة
    headers_map = {
        "Users": ["username", "password", "role", "created_at", "last_login"],
        "Attendance": ["player_name", "date", "status", "recorded_by", "timestamp"],
        "Subscriptions": ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status", "notes"],
        "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes", "receipt_id"]
    }
    if sheet_name in headers_map:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.append_row(headers_map[sheet_name])
    return pd.DataFrame()

def save_dataframe(sheet_name: str, df: pd.DataFrame):
"""حفظ DataFrame بالكامل في ورقة (استبدال المحتوى)"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    worksheet.clear()
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")

if not df.empty:
    worksheet.update([df.columns.tolist()] + df.values.tolist())
else:
    # وضع الرؤوس فقط
    headers_map = {
        "Users": ["username", "password", "role", "created_at", "last_login"],
        "Attendance": ["player_name", "date", "status", "recorded_by", "timestamp"],
        "Subscriptions": ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status", "notes"],
        "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes", "receipt_id"]
    }
    if sheet_name in headers_map:
        worksheet.update([headers_map[sheet_name]])

def append_row(sheet_name: str, row_data: List[Any]):
"""إضافة صف جديد إلى نهاية الورقة"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    worksheet.append_row(row_data)
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    worksheet.append_row(row_data)

def update_cell(sheet_name: str, row: int, col: int, value: Any):
"""تحديث خلية محددة"""
spreadsheet = get_spreadsheet()
worksheet = spreadsheet.worksheet(sheet_name)
worksheet.update_cell(row, col, value)

# ============================================================
# SECTION 5: دوال التحقق من صحة البيانات
# ============================================================

def is_valid_three_part_name(name: str) -> bool:
"""
التحقق من أن الاسم ثلاثي (ثلاثة أجزاء مفصولة بمسافات)
مثال: أحمد محمد علي -> صحيح
أحمد محمد -> خطأ (جزئين فقط)
"""
if not name or not isinstance(name, str):
    return False
name = name.strip()
if not name:
    return False
parts = name.split()
# يجب أن يكون بالضبط 3 أجزاء وكل جزء غير فارغ
if len(parts) != 3:
    return False
# التحقق من أن كل جزء يتكون من حروف عربية أو إنجليزية (اختياري)
for part in parts:
    if len(part) == 0:
        return False
return True

def is_username_unique(username: str) -> bool:
"""التحقق من عدم تكرار اسم المستخدم في قاعدة بيانات المستخدمين"""
users_df = load_dataframe("Users")
if users_df.empty:
    return True
return username not in users_df["username"].values

def validate_email(email: str) -> bool:
"""التحقق من صحة البريد الإلكتروني (اختياري، يمكن إضافته لاحقاً)"""
pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
return re.match(pattern, email) is not None

def validate_phone(phone: str) -> bool:
"""التحقق من صحة رقم الهاتف المصري (اختياري)"""
pattern = r'^(01)[0-9]{9}$'
return re.match(pattern, phone) is not None

def hash_password(password: str) -> str:
"""تشفير كلمة المرور باستخدام SHA-256"""
return hashlib.sha256(password.encode()).hexdigest()

# ============================================================
# SECTION 6: دوال إدارة المستخدمين والجلسات
# ============================================================

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[str]]:
"""
التحقق من بيانات المستخدم وإرجاع الدور إذا كان صحيحاً.
"""
users_df = load_dataframe("Users")
if users_df.empty:
    return False, None

# البحث عن المستخدم (بدون تشفير للتبسيط، يمكن إضافة التشفير لاحقاً)
user_row = users_df[(users_df["username"] == username) & (users_df["password"] == password)]
if not user_row.empty:
    role = user_row.iloc[0]["role"]
    # تحديث آخر تسجيل دخول
    try:
        last_login_col = users_df.columns.get_loc("last_login") if "last_login" in users_df.columns else None
        if last_login_col is not None:
            row_idx = user_row.index[0]
            users_df.iloc[row_idx, last_login_col] = datetime.now().isoformat()
            save_dataframe("Users", users_df)
    except:
        pass
    return True, role
return False, None

def add_new_user(username: str, password: str, role: str, email: str = "", phone: str = "") -> Tuple[bool, str]:
"""
إضافة مستخدم جديد (لاعب فقط - الكابتن يضاف يدوياً في Google Sheets)
"""
if not is_valid_three_part_name(username):
    return False, "⚠️ الاسم يجب أن يكون ثلاثياً (ثلاثة أجزاء) مثال: أحمد محمد علي"

if not is_username_unique(username):
    return False, "⚠️ اسم المستخدم موجود مسبقاً، الرجاء اختيار اسم آخر"

# التحقق من صحة البريد الإلكتروني إذا تم توفيره
if email and not validate_email(email):
    return False, "⚠️ البريد الإلكتروني غير صالح"

# التحقق من صحة رقم الهاتف إذا تم توفيره
if phone and not validate_phone(phone):
    return False, "⚠️ رقم الهاتف غير صالح (يجب أن يبدأ بـ 01 ويتبع بـ 9 أرقام)"

users_df = load_dataframe("Users")
new_row = pd.DataFrame([{
    "username": username,
    "password": password,
    "role": role,
    "created_at": datetime.now().isoformat(),
    "last_login": ""
}])
users_df = pd.concat([users_df, new_row], ignore_index=True)
save_dataframe("Users", users_df)

# إنشاء اشتراك افتراضي للاعب الجديد
if role == "player":
    subs_df = load_dataframe("Subscriptions")
    if subs_df.empty or username not in subs_df["player_name"].values:
        default_sub = pd.DataFrame([{
            "player_name": username,
            "monthly_fee": 200.0,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=30)).isoformat(),
            "subscription_status": "فعال",
            "notes": "اشتراك تلقائي عند التسجيل"
        }])
        if subs_df.empty:
            subs_df = default_sub
        else:
            subs_df = pd.concat([subs_df, default_sub], ignore_index=True)
        save_dataframe("Subscriptions", subs_df)

return True, "✅ تمت إضافة المستخدم بنجاح"

def get_all_players() -> List[str]:
"""إرجاع قائمة بجميع أسماء اللاعبين (الدور = player)"""
users_df = load_dataframe("Users")
if users_df.empty:
    return []
return users_df[users_df["role"] == "player"]["username"].tolist()

def get_coach_username() -> Optional[str]:
"""إرجاع اسم مستخدم الكابتن (يفترض وجود كابتن واحد على الأقل)"""
users_df = load_dataframe("Users")
if users_df.empty:
    return None
coach_row = users_df[users_df["role"] == "coach"]
if not coach_row.empty:
    return coach_row.iloc[0]["username"]
return None

def get_player_details(player_name: str) -> Optional[Dict]:
"""الحصول على تفاصيل لاعب معين (مثل البريد الإلكتروني، الهاتف)"""
users_df = load_dataframe("Users")
if users_df.empty:
    return None
player_row = users_df[users_df["username"] == player_name]
if player_row.empty:
    return None
return player_row.iloc[0].to_dict()

# ============================================================
# SECTION 7: دوال إدارة الحضور والغياب (محسنة)
# ============================================================

def record_attendance_multi(players: List[str], status: str, recorded_by: str) -> int:
"""
تسجيل حضور/غياب لمجموعة من اللاعبين لتاريخ اليوم.
إرجاع عدد اللاعبين الذين تم تسجيلهم بنجاح.
"""
if not players:
    return 0

today_str = date.today().isoformat()
timestamp = datetime.now().isoformat()
attendance_df = load_dataframe("Attendance")

count = 0
for player in players:
    if attendance_df.empty:
        new_row = pd.DataFrame([{
            "player_name": player,
            "date": today_str,
            "status": status,
            "recorded_by": recorded_by,
            "timestamp": timestamp
        }])
        attendance_df = new_row
    else:
        # التحقق من وجود سجل لليوم
        existing_idx = attendance_df[(attendance_df["player_name"] == player) & 
                                      (attendance_df["date"] == today_str)].index
        if len(existing_idx) > 0:
            # تحديث السجل الموجود
            attendance_df.loc[existing_idx, "status"] = status
            attendance_df.loc[existing_idx, "recorded_by"] = recorded_by
            attendance_df.loc[existing_idx, "timestamp"] = timestamp
        else:
            # إضافة سجل جديد
            new_row = pd.DataFrame([{
                "player_name": player,
                "date": today_str,
                "status": status,
                "recorded_by": recorded_by,
                "timestamp": timestamp
            }])
            attendance_df = pd.concat([attendance_df, new_row], ignore_index=True)
    count += 1

save_dataframe("Attendance", attendance_df)
return count

def get_player_attendance_history(player_name: str, limit: int = None) -> pd.DataFrame:
"""
استرجاع سجل الحضور والغياب للاعب معين، مع إمكانية تحديد عدد السجلات.
"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
player_att = attendance_df[attendance_df["player_name"] == player_name].copy()
if not player_att.empty:
    player_att["date"] = pd.to_datetime(player_att["date"])
    player_att = player_att.sort_values("date", ascending=False)
    if limit:
        player_att = player_att.head(limit)
return player_att

def get_attendance_percentage(player_name: str) -> float:
"""حساب نسبة الحضور للاعب"""
player_att = get_player_attendance_history(player_name)
if player_att.empty:
    return 0.0
total = len(player_att)
present = len(player_att[player_att["status"] == "Present"])
return (present / total * 100) if total > 0 else 0.0

def get_absence_count(player_name: str) -> int:
"""حساب عدد مرات الغياب للاعب"""
player_att = get_player_attendance_history(player_name)
if player_att.empty:
    return 0
return len(player_att[player_att["status"] == "Absent"])

def get_today_attendance() -> pd.DataFrame:
"""الحصول على حالة الحضور والغياب ليوم اليوم"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
today_str = date.today().isoformat()
today_att = attendance_df[attendance_df["date"] == today_str].copy()
return today_att

def get_attendance_summary(start_date: date = None, end_date: date = None) -> pd.DataFrame:
"""
الحصول على ملخص الحضور لكل لاعب خلال فترة زمنية محددة.
إذا لم يتم تحديد تواريخ، يتم حساب الإحصائيات على كل البيانات.
"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()

attendance_df["date"] = pd.to_datetime(attendance_df["date"])

if start_date:
    attendance_df = attendance_df[attendance_df["date"] >= pd.to_datetime(start_date)]
if end_date:
    attendance_df = attendance_df[attendance_df["date"] <= pd.to_datetime(end_date)]

if attendance_df.empty:
    return pd.DataFrame()

summary = attendance_df.groupby("player_name").agg(
    total_sessions=("status", "count"),
    present=("status", lambda x: (x == "Present").sum()),
    absent=("status", lambda x: (x == "Absent").sum())
).reset_index()

summary["attendance_percentage"] = (summary["present"] / summary["total_sessions"] * 100).round(1)
summary = summary.sort_values("attendance_percentage", ascending=False)
return summary

def get_weekly_attendance() -> pd.DataFrame:
"""
تحليل الحضور الأسبوعي (آخر 7 أيام)
"""
end_date = date.today()
start_date = end_date - timedelta(days=7)
summary = get_attendance_summary(start_date, end_date)
if not summary.empty:
    summary["week"] = f"{start_date.isoformat()} إلى {end_date.isoformat()}"
return summary

def get_monthly_attendance(year: int = None, month: int = None) -> pd.DataFrame:
"""
تحليل الحضور الشهري.
إذا لم يتم تحديد السنة والشهر، يتم استخدام الشهر الحالي.
"""
if year is None or month is None:
    today = date.today()
    year = today.year
    month = today.month
start_date = date(year, month, 1)
if month == 12:
    end_date = date(year + 1, 1, 1) - timedelta(days=1)
else:
    end_date = date(year, month + 1, 1) - timedelta(days=1)
return get_attendance_summary(start_date, end_date)

# ============================================================
# SECTION 8: دوال إدارة الاشتراكات والمدفوعات (محسنة)
# ============================================================

def get_player_subscription(player_name: str) -> Optional[Dict]:
"""استرجاع بيانات اشتراك لاعب معين"""
subs_df = load_dataframe("Subscriptions")
if subs_df.empty:
    return None
player_sub = subs_df[subs_df["player_name"] == player_name]
if player_sub.empty:
    return None
return player_sub.iloc[0].to_dict()

def update_player_subscription(
player_name: str,
monthly_fee: float,
start_date: str,
end_date: str,
status: str,
notes: str = ""
) -> bool:
"""تحديث أو إضافة اشتراك لاعب"""
subs_df = load_dataframe("Subscriptions")

if subs_df.empty:
    new_row = pd.DataFrame([{
        "player_name": player_name,
        "monthly_fee": monthly_fee,
        "start_date": start_date,
        "end_date": end_date,
        "subscription_status": status,
        "notes": notes
    }])
    subs_df = new_row
else:
    if player_name in subs_df["player_name"].values:
        # تحديث السجل الموجود
        subs_df.loc[subs_df["player_name"] == player_name, "monthly_fee"] = monthly_fee
        subs_df.loc[subs_df["player_name"] == player_name, "start_date"] = start_date
        subs_df.loc[subs_df["player_name"] == player_name, "end_date"] = end_date
        subs_df.loc[subs_df["player_name"] == player_name, "subscription_status"] = status
        if notes:
            subs_df.loc[subs_df["player_name"] == player_name, "notes"] = notes
    else:
        # إضافة سجل جديد
        new_row = pd.DataFrame([{
            "player_name": player_name,
            "monthly_fee": monthly_fee,
            "start_date": start_date,
            "end_date": end_date,
            "subscription_status": status,
            "notes": notes
        }])
        subs_df = pd.concat([subs_df, new_row], ignore_index=True)

save_dataframe("Subscriptions", subs_df)
return True

def add_payment(
player_name: str,
amount: float,
payment_method: str,
notes: str = ""
) -> bool:
"""
تسجيل دفعة جديدة للاعب مع إنشاء رقم إيصال فريد.
"""
payment_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# إنشاء رقم إيصال عشوائي
receipt_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
append_row("Payments", [player_name, amount, payment_method, payment_date, notes, receipt_id])
return True

def get_player_payments(player_name: str) -> pd.DataFrame:
"""استرجاع جميع دفعات لاعب معين"""
payments_df = load_dataframe("Payments")
if payments_df.empty:
    return pd.DataFrame()
player_payments = payments_df[payments_df["player_name"] == player_name].copy()
if not player_payments.empty:
    player_payments["amount"] = pd.to_numeric(player_payments["amount"], errors='coerce')
    player_payments["payment_date"] = pd.to_datetime(player_payments["payment_date"])
    player_payments = player_payments.sort_values("payment_date", ascending=False)
return player_payments

def get_total_paid(player_name: str) -> float:
"""حساب إجمالي المبلغ المدفوع للاعب"""
payments = get_player_payments(player_name)
if payments.empty:
    return 0.0
return payments["amount"].sum()

def calculate_total_due(player_name: str) -> float:
"""
حساب إجمالي المبلغ المستحق على اللاعب بناءً على مدة الاشتراك.
"""
sub = get_player_subscription(player_name)
if not sub:
    return 0.0

try:
    start = datetime.strptime(sub["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(sub["end_date"], "%Y-%m-%d").date()
    # حساب عدد الأشهر (شهر كامل لكل شهر يبدأ من start_date)
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    if months <= 0:
        months = 1
    monthly_fee = float(sub["monthly_fee"])
    return months * monthly_fee
except Exception as e:
    return 0.0

def calculate_remaining_amount(player_name: str) -> float:
"""حساب المبلغ المتبقي على اللاعب = المستحق - المدفوع"""
total_due = calculate_total_due(player_name)
total_paid = get_total_paid(player_name)
return max(total_due - total_paid, 0.0)

def get_all_subscriptions() -> pd.DataFrame:
"""الحصول على جميع الاشتراكات"""
return load_dataframe("Subscriptions")

def get_subscription_status_summary() -> pd.DataFrame:
"""الحصول على ملخص حالة الاشتراكات لجميع اللاعبين مع المبالغ المتبقية"""
subs_df = load_dataframe("Subscriptions")
if subs_df.empty:
    return pd.DataFrame()

summary = []
for _, row in subs_df.iterrows():
    player = row["player_name"]
    remaining = calculate_remaining_amount(player)
    summary.append({
        "اللاعب": player,
        "القيمة الشهرية (جنيه)": row["monthly_fee"],
        "تاريخ البداية": row["start_date"],
        "تاريخ النهاية": row["end_date"],
        "الحالة": row["subscription_status"],
        "المتبقي (جنيه)": round(remaining, 2)
    })
return pd.DataFrame(summary)

# ============================================================
# SECTION 9: دوال التقارير والإحصائيات المتقدمة
# ============================================================

def get_financial_summary() -> Dict:
"""
الحصول على ملخص مالي عام للأكاديمية:
- إجمالي التحصيل
- إجمالي المتوقع تحصيله
- إجمالي المتأخرات
- عدد الدفعات
- متوسط قيمة الدفعة
"""
payments_df = load_dataframe("Payments")
subs_df = load_dataframe("Subscriptions")

total_collected = 0.0
num_payments = 0
if not payments_df.empty:
    payments_df["amount"] = pd.to_numeric(payments_df["amount"], errors='coerce')
    total_collected = payments_df["amount"].sum()
    num_payments = len(payments_df)

avg_payment = total_collected / num_payments if num_payments > 0 else 0.0

total_expected = 0.0
if not subs_df.empty:
    for _, row in subs_df.iterrows():
        try:
            start = datetime.strptime(row["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(row["end_date"], "%Y-%m-%d").date()
            months = (end.year - start.year) * 12 + (end.month - start.month) + 1
            if months <= 0:
                months = 1
            total_expected += months * float(row["monthly_fee"])
        except:
            pass

return {
    "total_collected": total_collected,
    "total_expected": total_expected,
    "outstanding": max(total_expected - total_collected, 0.0),
    "num_payments": num_payments,
    "avg_payment": avg_payment
}

def get_monthly_collection(year: int = None) -> pd.DataFrame:
"""
تحليل المدفوعات الشهرية لسنة محددة.
إذا لم يتم تحديد السنة، يتم استخدام السنة الحالية.
"""
if year is None:
    year = date.today().year

payments_df = load_dataframe("Payments")
if payments_df.empty:
    return pd.DataFrame()

payments_df["payment_date"] = pd.to_datetime(payments_df["payment_date"])
payments_df = payments_df[payments_df["payment_date"].dt.year == year]
if payments_df.empty:
    return pd.DataFrame()

payments_df["month"] = payments_df["payment_date"].dt.strftime("%B")
# ترتيب الأشهر
month_order = ["January", "February", "March", "April", "May", "June", 
               "July", "August", "September", "October", "November", "December"]
monthly = payments_df.groupby("month")["amount"].sum().reset_index()
monthly["month"] = pd.Categorical(monthly["month"], categories=month_order, ordered=True)
monthly = monthly.sort_values("month").reset_index(drop=True)
return monthly

def get_payment_method_distribution() -> pd.DataFrame:
"""توزيع المدفوعات حسب طريقة الدفع"""
payments_df = load_dataframe("Payments")
if payments_df.empty:
    return pd.DataFrame()
distribution = payments_df.groupby("payment_method")["amount"].sum().reset_index()
distribution = distribution.sort_values("amount", ascending=False)
return distribution

def get_attendance_trend(player_name: str = None) -> pd.DataFrame:
"""
تحليل اتجاه الحضور عبر الزمن (شهرياً)
"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()

attendance_df["date"] = pd.to_datetime(attendance_df["date"])
attendance_df["month"] = attendance_df["date"].dt.strftime("%Y-%m")

if player_name:
    attendance_df = attendance_df[attendance_df["player_name"] == player_name]

if attendance_df.empty:
    return pd.DataFrame()

monthly_stats = attendance_df.groupby(["month", "status"]).size().unstack(fill_value=0)
if "Present" not in monthly_stats.columns:
    monthly_stats["Present"] = 0
if "Absent" not in monthly_stats.columns:
    monthly_stats["Absent"] = 0

monthly_stats["total"] = monthly_stats["Present"] + monthly_stats["Absent"]
monthly_stats["percentage"] = (monthly_stats["Present"] / monthly_stats["total"] * 100).round(1)
monthly_stats = monthly_stats.reset_index()
return monthly_stats

def get_top_attendance_players(limit: int = 5) -> pd.DataFrame:
"""أفضل اللاعبين من حيث نسبة الحضور"""
summary = get_attendance_summary()
if summary.empty:
    return pd.DataFrame()
return summary.nlargest(limit, "attendance_percentage")[["player_name", "attendance_percentage"]]

def get_bottom_attendance_players(limit: int = 5) -> pd.DataFrame:
"""أسوأ اللاعبين من حيث نسبة الحضور"""
summary = get_attendance_summary()
if summary.empty:
    return pd.DataFrame()
return summary.nsmallest(limit, "attendance_percentage")[["player_name", "attendance_percentage"]]

# ============================================================
# SECTION 10: دوال واجهة المستخدم (UI Components)
# ============================================================

def display_header(title: str, subtitle: str = ""):
"""عرض رأس الصفحة بتصميم موحد"""
st.markdown(f"""
<div class="main-header">
    <h1>⚽ {title}</h1>
    <p>{subtitle}</p>
</div>
""", unsafe_allow_html=True)

def display_metric_card(label: str, value: str, icon: str = "📊", delta: str = None):
"""عرض بطاقة مقياس مع إمكانية إضافة تغيير"""
delta_html = f'<div style="font-size:0.8rem; color:{ "green" if delta and "+" in delta else "red" if delta else "gray"};">{delta if delta else ""}</div>' if delta else ""
st.markdown(f"""
<div class="metric-card">
    <div style="font-size: 2rem;">{icon}</div>
    <div class="metric-value">{value}</div>
    <div class="metric-label">{label}</div>
    {delta_html}
</div>
""", unsafe_allow_html=True)

def show_sidebar_user_info():
"""عرض معلومات المستخدم في الشريط الجانبي"""
if "username" in st.session_state:
    role_icon = "👨‍🏫" if st.session_state["role"] == "coach" else "⚽"
    role_name = "كابتن" if st.session_state["role"] == "coach" else "لاعب"
    st.sidebar.markdown(f"""
    <div class="user-info">
        <div style="font-size: 2rem;">{role_icon}</div>
        <div style="font-weight: bold; font-size: 1.1rem;">{st.session_state['username']}</div>
        <div style="font-size: 0.8rem; opacity: 0.9;">{role_name}</div>
    </div>
    """, unsafe_allow_html=True)

def logout_button():
"""زر تسجيل الخروج مع تأكيد"""
if st.sidebar.button("🚪 تسجيل خروج", use_container_width=True):
    # مسح جميع مفاتيح الجلسة
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def show_notification(message: str, type: str = "success"):
"""عرض إشعار مؤقت"""
if type == "success":
    st.success(message)
elif type == "error":
    st.error(message)
elif type == "warning":
    st.warning(message)
elif type == "info":
    st.info(message)
time.sleep(1.5)
st.rerun()

# ============================================================
# SECTION 11: صفحة تسجيل الدخول (Login Page)
# ============================================================

def login_page():
"""
عرض صفحة تسجيل الدخول مع تصميم جذاب.
"""
display_header("الكوتش أكاديمي", "نظام إدارة الحضور والاشتراكات")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("### 🔐 تسجيل الدخول")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)", placeholder="مثال: أحمد محمد علي")
        password = st.text_input("كلمة المرور", type="password", placeholder="********")
        submitted = st.form_submit_button("دخول", use_container_width=True)
        
        if submitted:
            if not username or not password:
                st.error("⚠️ الرجاء إدخال اسم المستخدم وكلمة المرور")
            elif not is_valid_three_part_name(username):
                st.error("⚠️ اسم المستخدم يجب أن يكون ثلاثياً (ثلاثة أجزاء) مثل: أحمد محمد علي")
            else:
                success, role = authenticate_user(username, password)
                if success:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["role"] = role
                    st.success(f"✓ مرحباً {username}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.8rem;">
    <p>للتواصل مع الدعم الفني: support@elcoach.com</p>
    <p>نسخة التطبيق: 2.0.0</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# SECTION 12: لوحة تحكم الكابتن (Coach Dashboard)
# ============================================================

def coach_dashboard():
"""
عرض لوحة تحكم الكابتن بجميع التبويبات والميزات المتقدمة.
"""
display_header("لوحة تحكم الكابتن", "إدارة الحضور، الاشتراكات، والمدفوعات")

# عرض معلومات المستخدم في الشريط الجانبي
show_sidebar_user_info()
logout_button()

# إحصائيات سريعة في الشريط الجانبي
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 إحصائيات سريعة")
players_count = len(get_all_players())
st.sidebar.metric("عدد اللاعبين", players_count)

today_att = get_today_attendance()
if not today_att.empty:
    present_today = len(today_att[today_att["status"] == "Present"])
    st.sidebar.metric("الحضور اليوم", f"{present_today} / {players_count}")
else:
    st.sidebar.metric("الحضور اليوم", "0 / {}".format(players_count))

financial = get_financial_summary()
st.sidebar.metric("إجمالي التحصيل", f"{financial['total_collected']:.0f} جنيه")
st.sidebar.metric("المتأخرات", f"{financial['outstanding']:.0f} جنيه")

# إنشاء التبويبات الرئيسية
tabs = st.tabs([
    "📋 الحضور والغياب",
    "💰 الاشتراكات والدفعات",
    "👥 إدارة اللاعبين",
    "📊 التقارير والإحصائيات",
    "⚙️ إعدادات متقدمة"
])

# ========== التبويب الأول: الحضور والغياب ==========
with tabs[0]:
    st.subheader("تسجيل الحضور والغياب")
    
    players = get_all_players()
    if not players:
        st.warning("⚠️ لا يوجد لاعبون مسجلون. قم بإضافة لاعبين من تبويب إدارة اللاعبين.")
    else:
        # اختيار متعدد للاعبين
        selected_players = st.multiselect(
            "اختر اللاعبين",
            players,
            help="يمكنك اختيار أكثر من لاعب لتسجيل الحضور أو الغياب دفعة واحدة"
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ تسجيل حضور", use_container_width=True):
                if selected_players:
                    with st.spinner("جاري تسجيل الحضور..."):
                        count = record_attendance_multi(selected_players, "Present", st.session_state["username"])
                    st.success(f"✓ تم تسجيل حضور {count} لاعب")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("⚠️ الرجاء اختيار لاعبين أولاً")
        with col2:
            if st.button("❌ تسجيل غياب", use_container_width=True):
                if selected_players:
                    with st.spinner("جاري تسجيل الغياب..."):
                        count = record_attendance_multi(selected_players, "Absent", st.session_state["username"])
                    st.success(f"✓ تم تسجيل غياب {count} لاعب")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("⚠️ الرجاء اختيار لاعبين أولاً")
        
        st.markdown("---")
        
        # عرض حالة الحضور اليوم
        st.subheader("حالة الحضور والغياب اليوم")
        today_attendance = get_today_attendance()
        if not today_attendance.empty:
            # إضافة أسماء اللاعبين غير المسجلين
            all_players_set = set(players)
            recorded_players = set(today_attendance["player_name"].tolist())
            missing_players = all_players_set - recorded_players
            
            # عرض الجدول
            display_df = today_attendance[["player_name", "status"]].copy()
            display_df.columns = ["اللاعب", "الحالة"]
            st.dataframe(display_df, use_container_width=True)
            
            if missing_players:
                st.info(f"📌 لم يتم تسجيل {len(missing_players)} لاعب بعد: {', '.join(missing_players)}")
        else:
            st.info("📌 لم يتم تسجيل أي حضور أو غياب اليوم")
        
        # عرض إحصائيات الغياب
        st.subheader("إحصائيات الغياب للاعبين")
        absence_stats = []
        for player in players:
            absent_count = get_absence_count(player)
            percentage = get_attendance_percentage(player)
            absence_stats.append({
                "اللاعب": player,
                "عدد مرات الغياب": absent_count,
                "نسبة الحضور": f"{percentage:.1f}%"
            })
        if absence_stats:
            st.dataframe(pd.DataFrame(absence_stats), use_container_width=True)

# ========== التبويب الثاني: الاشتراكات والدفعات ==========
with tabs[1]:
    st.subheader("إدارة الاشتراكات والمدفوعات")
    
    players = get_all_players()
    if not players:
        st.warning("⚠️ لا يوجد لاعبون مسجلون")
    else:
        selected_player = st.selectbox("اختر لاعباً", players, key="sub_select")
        
        if selected_player:
            # عرض بيانات الاشتراك الحالية
            current_sub = get_player_subscription(selected_player)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📝 بيانات الاشتراك")
                with st.form("edit_subscription_form"):
                    monthly_fee = st.number_input(
                        "القيمة الشهرية (جنيه)",
                        min_value=0.0,
                        step=50.0,
                        value=float(current_sub["monthly_fee"]) if current_sub else 200.0
                    )
                    start_date = st.date_input(
                        "تاريخ البدء",
                        value=datetime.strptime(current_sub["start_date"], "%Y-%m-%d").date() if current_sub and "start_date" in current_sub else date.today()
                    )
                    end_date = st.date_input(
                        "تاريخ الانتهاء",
                        value=datetime.strptime(current_sub["end_date"], "%Y-%m-%d").date() if current_sub and "end_date" in current_sub else date.today() + timedelta(days=30)
                    )
                    status_options = ["فعال", "منتهي", "ملغي"]
                    current_status = current_sub["subscription_status"] if current_sub else "فعال"
                    status_index = status_options.index(current_status) if current_status in status_options else 0
                    status = st.selectbox("حالة الاشتراك", status_options, index=status_index)
                    notes = st.text_area("ملاحظات", value=current_sub.get("notes", "") if current_sub else "")
                    
                    if st.form_submit_button("💾 تحديث الاشتراك", use_container_width=True):
                        update_player_subscription(
                            selected_player,
                            monthly_fee,
                            start_date.isoformat(),
                            end_date.isoformat(),
                            status,
                            notes
                        )
                        st.success("✓ تم تحديث بيانات الاشتراك")
                        st.rerun()
            
            with col2:
                st.markdown("#### 💰 ملخص مالي")
                total_paid = get_total_paid(selected_player)
                total_due = calculate_total_due(selected_player)
                remaining = calculate_remaining_amount(selected_player)
                
                st.metric("إجمالي المدفوع", f"{total_paid:.2f} جنيه")
                st.metric("إجمالي المستحق", f"{total_due:.2f} جنيه")
                st.metric("المتبقي", f"{remaining:.2f} جنيه", delta=f"-{total_paid:.2f}" if total_paid > 0 else None)
            
            st.markdown("---")
            
            # تسجيل دفعة جديدة
            st.markdown("#### 💵 تسجيل دفعة جديدة")
            with st.form("add_payment_form"):
                col_a, col_b = st.columns(2)
                with col_a:
                    amount = st.number_input("المبلغ (جنيه)", min_value=0.0, step=10.0, key="payment_amount")
                    payment_method = st.selectbox(
                        "طريقة الدفع",
                        ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"],
                        key="payment_method"
                    )
                with col_b:
                    notes = st.text_area("ملاحظات (اختياري)", placeholder="رقم العملية، إيصال، ...")
                
                if st.form_submit_button("➕ إضافة دفعة", use_container_width=True):
                    if amount > 0:
                        add_payment(selected_player, amount, payment_method, notes)
                        st.success(f"✓ تم تسجيل دفعة بقيمة {amount} جنيه للاعب {selected_player}")
                        st.rerun()
                    else:
                        st.error("⚠️ الرجاء إدخال مبلغ صحيح")
            
            # عرض سجل الدفعات
            st.markdown("#### 📜 سجل المدفوعات")
            payments = get_player_payments(selected_player)
            if not payments.empty:
                display_payments = payments[["amount", "payment_method", "payment_date", "notes", "receipt_id"]].copy()
                display_payments.columns = ["المبلغ", "طريقة الدفع", "تاريخ الدفع", "ملاحظات", "رقم الإيصال"]
                st.dataframe(display_payments, use_container_width=True)
            else:
                st.info("لا توجد مدفوعات مسجلة لهذا اللاعب")

# ========== التبويب الثالث: إدارة اللاعبين ==========
with tabs[2]:
    st.subheader("إدارة اللاعبين")
    
    # إضافة لاعب جديد
    st.markdown("#### ➕ إضافة لاعب جديد")
    with st.form("add_player_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            new_username = st.text_input("الاسم الثلاثي", placeholder="مثال: عمر خالد محمود")
            new_password = st.text_input("كلمة المرور", type="password", placeholder="كلمة مرور مؤقتة")
        with col_b:
            new_email = st.text_input("البريد الإلكتروني (اختياري)", placeholder="example@email.com")
            new_phone = st.text_input("رقم الهاتف (اختياري)", placeholder="01234567890")
        
        if st.form_submit_button("إضافة لاعب", use_container_width=True):
            if not new_username or not new_password:
                st.error("⚠️ الرجاء إدخال الاسم الثلاثي وكلمة المرور")
            else:
                success, message = add_new_user(new_username, new_password, "player", new_email, new_phone)
                if success:
                    st.success(f"✓ {message}")
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    
    st.markdown("---")
    
    # قائمة اللاعبين الحاليين
    st.markdown("#### 📋 قائمة اللاعبين")
    players_list = get_all_players()
    if players_list:
        # عرض مع معلومات الاشتراك
        players_data = []
        for p in players_list:
            sub = get_player_subscription(p)
            remaining = calculate_remaining_amount(p)
            players_data.append({
                "اسم اللاعب": p,
                "الاشتراك الشهري": f"{sub['monthly_fee']} جنيه" if sub else "غير محدد",
                "حالة الاشتراك": sub["subscription_status"] if sub else "غير محدد",
                "المتبقي": f"{remaining:.2f} جنيه"
            })
        st.dataframe(pd.DataFrame(players_data), use_container_width=True)
        
        # خيار حذف لاعب (بحذر)
        with st.expander("⚠️ حذف لاعب (عملية لا ترجع)"):
            player_to_delete = st.selectbox("اختر لاعباً للحذف", players_list, key="delete_select")
            if st.button("🗑️ حذف اللاعب", use_container_width=True):
                st.warning("هذه العملية نهائية. هل أنت متأكد؟")
                confirm = st.checkbox("نعم، أنا متأكد من حذف هذا اللاعب")
                if confirm:
                    # حذف من Users
                    users_df = load_dataframe("Users")
                    users_df = users_df[users_df["username"] != player_to_delete]
                    save_dataframe("Users", users_df)
                    # حذف من Attendance
                    att_df = load_dataframe("Attendance")
                    if not att_df.empty:
                        att_df = att_df[att_df["player_name"] != player_to_delete]
                        save_dataframe("Attendance", att_df)
                    # حذف من Subscriptions
                    subs_df = load_dataframe("Subscriptions")
                    if not subs_df.empty:
                        subs_df = subs_df[subs_df["player_name"] != player_to_delete]
                        save_dataframe("Subscriptions", subs_df)
                    # حذف من Payments
                    pay_df = load_dataframe("Payments")
                    if not pay_df.empty:
                        pay_df = pay_df[pay_df["player_name"] != player_to_delete]
                        save_dataframe("Payments", pay_df)
                    st.success(f"✓ تم حذف اللاعب {player_to_delete}")
                    st.rerun()
    else:
        st.info("لا يوجد لاعبون مسجلون حالياً")

# ========== التبويب الرابع: التقارير والإحصائيات ==========
with tabs[3]:
    st.subheader("التقارير والإحصائيات")
    
    report_tabs = st.tabs(["📈 إحصائيات الحضور", "💰 تقارير مالية", "📊 تحليلات متقدمة"])
    
    with report_tabs[0]:
        # إحصائيات الحضور العامة
        st.markdown("#### ملخص الحضور لجميع اللاعبين")
        summary = get_attendance_summary()
        if not summary.empty:
            # رسم بياني
            fig = px.bar(
                summary,
                x="player_name",
                y="attendance_percentage",
                title="نسبة الحضور لكل لاعب",
                labels={"player_name": "اللاعب", "attendance_percentage": "نسبة الحضور (%)"},
                color="attendance_percentage",
                color_continuous_scale="Viridis"
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # جدول
            display_summary = summary[["player_name", "total_sessions", "present", "absent", "attendance_percentage"]].copy()
            display_summary.columns = ["اللاعب", "عدد الجلسات", "حاضر", "غائب", "نسبة الحضور %"]
            st.dataframe(display_summary, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور كافية لعرض الإحصائيات")
        
        # اتجاه الحضور الشهري
        st.markdown("#### اتجاه الحضور الشهري")
        monthly_trend = get_attendance_trend()
        if not monthly_trend.empty:
            fig2 = px.line(
                monthly_trend,
                x="month",
                y="percentage",
                title="نسبة الحضور الإجمالية شهرياً",
                labels={"month": "الشهر", "percentage": "نسبة الحضور (%)"},
                markers=True
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية لعرض الاتجاه الشهري")
    
    with report_tabs[1]:
        # التقارير المالية
        financial = get_financial_summary()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            display_metric_card("إجمالي التحصيل", f"{financial['total_collected']:.0f} جنيه", "💰")
        with col2:
            display_metric_card("المتوقع تحصيله", f"{financial['total_expected']:.0f} جنيه", "📋")
        with col3:
            display_metric_card("المتأخرات", f"{financial['outstanding']:.0f} جنيه", "⚠️")
        with col4:
            display_metric_card("عدد الدفعات", f"{financial['num_payments']}", "📄")
        
        st.markdown("#### ملخص الاشتراكات")
        subs_summary = get_subscription_status_summary()
        if not subs_summary.empty:
            st.dataframe(subs_summary, use_container_width=True)
        
        st.markdown("#### التحصيل الشهري")
        monthly_collection = get_monthly_collection()
        if not monthly_collection.empty:
            fig3 = px.bar(
                monthly_collection,
                x="month",
                y="amount",
                title="التحصيل الشهري",
                labels={"month": "الشهر", "amount": "المبلغ (جنيه)"},
                color="amount",
                color_continuous_scale="Blues"
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("لا توجد مدفوعات مسجلة")
        
        st.markdown("#### توزيع المدفوعات حسب طريقة الدفع")
        payment_dist = get_payment_method_distribution()
        if not payment_dist.empty:
            fig4 = px.pie(
                payment_dist,
                values="amount",
                names="payment_method",
                title="توزيع المدفوعات حسب طريقة الدفع"
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية")
    
    with report_tabs[2]:
        st.markdown("#### تحليل أداء اللاعبين")
        if not summary.empty:
            top_players = get_top_attendance_players(5)
            st.markdown("**🏆 أفضل 5 لاعبين من حيث الحضور**")
            for i, row in top_players.iterrows():
                st.write(f"{i+1}. {row['player_name']}: {row['attendance_percentage']:.1f}%")
            
            bottom_players = get_bottom_attendance_players(5)
            st.markdown("**⚠️ أسوأ 5 لاعبين من حيث الحضور**")
            for i, row in bottom_players.iterrows():
                st.write(f"{i+1}. {row['player_name']}: {row['attendance_percentage']:.1f}%")
        else:
            st.info("لا توجد بيانات كافية")
        
        st.markdown("#### إحصائيات متقدمة")
        players = get_all_players()
        if players:
            avg_attendance = summary["attendance_percentage"].mean() if not summary.empty else 0
            st.metric("متوسط نسبة الحضور لجميع اللاعبين", f"{avg_attendance:.1f}%")
            
            total_absences = sum(get_absence_count(p) for p in players)
            st.metric("إجمالي عدد مرات الغياب", total_absences)

# ========== التبويب الخامس: إعدادات متقدمة ==========
with tabs[4]:
    st.subheader("الإعدادات المتقدمة")
    
    st.markdown("#### نسخ احتياطي للبيانات")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 تصدير البيانات إلى CSV", use_container_width=True):
            # تصدير جميع البيانات
            users_df = load_dataframe("Users")
            att_df = load_dataframe("Attendance")
            subs_df = load_dataframe("Subscriptions")
            payments_df = load_dataframe("Payments")
            
            # تحويل إلى CSV
            csv_users = users_df.to_csv(index=False).encode('utf-8')
            csv_att = att_df.to_csv(index=False).encode('utf-8')
            csv_subs = subs_df.to_csv(index=False).encode('utf-8')
            csv_payments = payments_df.to_csv(index=False).encode('utf-8')
            
            st.download_button("تحميل بيانات المستخدمين", csv_users, "users.csv", "text/csv")
            st.download_button("تحميل بيانات الحضور", csv_att, "attendance.csv", "text/csv")
            st.download_button("تحميل بيانات الاشتراكات", csv_subs, "subscriptions.csv", "text/csv")
            st.download_button("تحميل بيانات المدفوعات", csv_payments, "payments.csv", "text/csv")
    
    with col2:
        st.markdown("#### إعادة تعيين البيانات (استخدام بحذر)")
        if st.button("⚠️ مسح جميع البيانات", use_container_width=True):
            st.error("هذه العملية ستحذف جميع البيانات. هل أنت متأكد؟")
            confirm = st.checkbox("نعم، أنا متأكد من مسح جميع البيانات")
            if confirm:
                # مسح البيانات
                save_dataframe("Users", pd.DataFrame())
                save_dataframe("Attendance", pd.DataFrame())
                save_dataframe("Subscriptions", pd.DataFrame())
                save_dataframe("Payments", pd.DataFrame())
                st.success("✓ تم مسح جميع البيانات")
                st.rerun()
    
    st.markdown("#### معلومات النظام")
    st.json({
        "إصدار التطبيق": "2.0.0",
        "عدد اللاعبين": len(get_all_players()),
        "آخر تحديث": datetime.now().isoformat(),
        "حالة الاتصال بـ Google Sheets": "متصل" if get_google_sheets_client() else "غير متصل"
    })

# ============================================================
# SECTION 13: صفحة اللاعب (Player Dashboard)
# ============================================================

def player_dashboard():
"""
عرض لوحة معلومات اللاعب مع جميع التفاصيل الخاصة به.
"""
player_name = st.session_state["username"]
display_header(f"مرحباً {player_name}", "لوحة معلومات اللاعب")

show_sidebar_user_info()
logout_button()

# إحصائيات سريعة في الشريط الجانبي
st.sidebar.markdown("---")
st.sidebar.markdown("### 📈 إحصائياتي")
percentage = get_attendance_percentage(player_name)
st.sidebar.metric("نسبة الحضور", f"{percentage:.1f}%")

total_paid = get_total_paid(player_name)
remaining = calculate_remaining_amount(player_name)
st.sidebar.metric("إجمالي المدفوع", f"{total_paid:.2f} جنيه")
st.sidebar.metric("المتبقي", f"{remaining:.2f} جنيه")

# البطاقات الرئيسية
col1, col2, col3 = st.columns(3)
with col1:
    display_metric_card("نسبة الحضور", f"{percentage:.1f}%", "📊")
with col2:
    display_metric_card("إجمالي المدفوع", f"{total_paid:.2f} جنيه", "💰")
with col3:
    display_metric_card("المتبقي", f"{remaining:.2f} جنيه", "📌")

# معلومات الاشتراك الحالي
st.markdown("## 📝 اشتراكي الحالي")
sub = get_player_subscription(player_name)
if sub:
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("القيمة الشهرية", f"{sub['monthly_fee']} جنيه")
    with col_b:
        st.metric("تاريخ البدء", sub['start_date'])
    with col_c:
        st.metric("تاريخ الانتهاء", sub['end_date'])
    
    status_color = "green" if sub['subscription_status'] == "فعال" else "red"
    st.markdown(f"**الحالة:** <span style='color:{status_color}'>{sub['subscription_status']}</span>", unsafe_allow_html=True)
    if sub.get('notes'):
        st.info(f"📝 ملاحظات: {sub['notes']}")
else:
    st.warning("لا يوجد اشتراك مسجل لك. الرجاء التواصل مع الكابتن.")

# سجل الحضور
st.markdown("## 📋 سجل الحضور والغياب")
attendance_history = get_player_attendance_history(player_name)
if not attendance_history.empty:
    # إضافة رسم بياني للحضور
    attendance_history["month"] = attendance_history["date"].dt.strftime("%Y-%m")
    monthly_counts = attendance_history.groupby(["month", "status"]).size().unstack(fill_value=0)
    if "Present" in monthly_counts.columns and "Absent" in monthly_counts.columns:
        fig = go.Figure(data=[
            go.Bar(name="حاضر", x=monthly_counts.index, y=monthly_counts["Present"], marker_color="green"),
            go.Bar(name="غائب", x=monthly_counts.index, y=monthly_counts["Absent"], marker_color="red")
        ])
        fig.update_layout(barmode="group", title="الحضور والغياب شهرياً", xaxis_title="الشهر", yaxis_title="عدد المرات")
        st.plotly_chart(fig, use_container_width=True)
    
    # عرض الجدول
    display_att = attendance_history[["date", "status"]].copy()
    display_att["date"] = display_att["date"].dt.strftime("%Y-%m-%d")
    display_att.columns = ["التاريخ", "الحالة"]
    st.dataframe(display_att, use_container_width=True)
else:
    st.info("لا توجد سجلات حضور لك بعد")

# سجل المدفوعات
st.markdown("## 💳 سجل مدفوعاتي")
payments = get_player_payments(player_name)
if not payments.empty:
    display_pay = payments[["amount", "payment_method", "payment_date", "notes", "receipt_id"]].copy()
    display_pay.columns = ["المبلغ", "طريقة الدفع", "تاريخ الدفع", "ملاحظات", "رقم الإيصال"]
    st.dataframe(display_pay, use_container_width=True)
else:
    st.info("لا توجد مدفوعات مسجلة لك بعد")

# ============================================================
# SECTION 14: التطبيق الرئيسي (Main)
# ============================================================

def main():
"""
الدالة الرئيسية لتشغيل التطبيق وإدارة الجلسات.
"""
# تهيئة حالة الجلسة إذا لزم الأمر
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# عرض الصفحة المناسبة
if not st.session_state["logged_in"]:
    login_page()
else:
    if st.session_state["role"] == "coach":
        coach_dashboard()
    elif st.session_state["role"] == "player":
        player_dashboard()
    else:
        st.error("⚠️ دور غير معروف")
        if st.button("تسجيل خروج"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ============================================================
# تشغيل التطبيق
# ============================================================
if __name__ == "__main__":
main()
