""")
st.stop()

# ============================================
# إعدادات الصفحة الأساسية
# ============================================
st.set_page_config(
page_title="الكوتش أكاديمي - نظام إدارة الأكاديمية",
page_icon="⚽",
layout="wide",
initial_sidebar_state="expanded"
)

# ============================================
# تحميل الأنماط المخصصة (CSS) لدعم RTL وتحسين المظهر
# ============================================
st.markdown("""
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
/* تنسيق الجداول */
.stDataFrame {
    direction: ltr;
}
/* تنسيق الأزرار */
.stButton button {
    width: 100%;
    border-radius: 8px;
    font-weight: bold;
}
/* تنسيق القوائم الجانبية */
.sidebar .sidebar-content {
    direction: rtl;
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
/* تحسين عرض الأخطاء والنجاح */
.stAlert {
    border-radius: 8px;
}
/* تنسيق حقول الإدخال */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    border-radius: 8px;
}
/* تنسيق رأس الصفحة */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Tahoma', 'Arial', sans-serif;
}
/* تنسيق الشريط الجانبي */
[data-testid="stSidebar"] {
    background-color: #f0f2f6;
    padding: 1rem;
}
/* تنسيق معلومات المستخدم في الشريط الجانبي */
.user-info {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    margin-bottom: 1rem;
    text-align: center;
}
.logout-btn {
    margin-top: 2rem;
}
/* تنسيق الإشعارات */
.notification-badge {
    background-color: #ff4757;
    color: white;
    border-radius: 20px;
    padding: 2px 8px;
    font-size: 0.7rem;
    margin-right: 5px;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# دوال الاتصال بـ Google Sheets
# ============================================

@st.cache_resource(ttl=3600)
def get_google_sheets_client():
"""
إنشاء عميل Google Sheets باستخدام بيانات Service Account من secrets.toml
يتم تخزين العميل في الكاش لتحسين الأداء
"""
try:
    # التحقق من وجود secrets
    if "google" not in st.secrets:
        st.error("""
        ❌ خطأ: لم يتم العثور على إعدادات Google في secrets.
        
        تأكد من وجود ملف `.streamlit/secrets.toml` بالمحتوى الصحيح.
        """)
        st.stop()
    
    if "service_account" not in st.secrets["google"]:
        st.error("""
        ❌ خطأ: لم يتم العثور على service_account في secrets.google.
        
        تأكد من أن ملف secrets.toml يحتوي على القسم [google.service_account]
        """)
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
    if "google" not in st.secrets or "spreadsheet_id" not in st.secrets["google"]:
        st.error("❌ لم يتم العثور على spreadsheet_id في secrets.google")
        st.stop()
    spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet
except Exception as e:
    st.error(f"⚠️ لا يمكن الوصول إلى جدول البيانات: {str(e)}")
    st.stop()

def load_dataframe(sheet_name: str) -> pd.DataFrame:
"""
تحميل ورقة كاملة وتحويلها إلى DataFrame
إذا لم تكن الورقة موجودة، يتم إنشاؤها وإرجاع DataFrame فارغ
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
        "Users": ["username", "password", "role"],
        "Attendance": ["player_name", "date", "status", "recorded_by"],
        "Subscriptions": ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status"],
        "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes"]
    }
    if sheet_name in headers_map:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.append_row(headers_map[sheet_name])
    return pd.DataFrame()

def save_dataframe(sheet_name: str, df: pd.DataFrame):
"""
حفظ DataFrame بالكامل في ورقة (استبدال المحتوى)
"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    worksheet.clear()
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")

if not df.empty:
    # تحويل DataFrame إلى قوائم للتحديث
    headers = df.columns.tolist()
    values = df.values.tolist()
    # تحديث البيانات
    worksheet.update([headers] + values)
else:
    # إذا كان DataFrame فارغاً، نضيف صفاً فارغاً مع الأعمدة الأساسية
    headers_map = {
        "Users": ["username", "password", "role"],
        "Attendance": ["player_name", "date", "status", "recorded_by"],
        "Subscriptions": ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status"],
        "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes"]
    }
    if sheet_name in headers_map:
        worksheet.update([headers_map[sheet_name]])

def append_row(sheet_name: str, row_data: List[Any]):
"""
إضافة صف جديد إلى نهاية الورقة
"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    worksheet.append_row(row_data)
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    worksheet.append_row(row_data)

def update_cell(sheet_name: str, row: int, col: int, value: Any):
"""
تحديث خلية محددة (يستخدم في التعديلات الجزئية)
"""
spreadsheet = get_spreadsheet()
worksheet = spreadsheet.worksheet(sheet_name)
worksheet.update_cell(row, col, value)

# ============================================
# دوال التحقق من صحة البيانات
# ============================================

def is_valid_three_part_name(name: str) -> bool:
"""
التحقق من أن الاسم ثلاثي (ثلاثة أجزاء مفصولة بمسافات)
"""
if not name or not isinstance(name, str):
    return False
parts = name.strip().split()
return len(parts) == 3 and all(len(part) > 0 for part in parts)

def is_username_unique(username: str) -> bool:
"""
التحقق من عدم تكرار اسم المستخدم في قاعدة بيانات المستخدمين
"""
users_df = load_dataframe("Users")
if users_df.empty:
    return True
return username not in users_df["username"].values

def validate_date_format(date_str: str) -> bool:
"""
التحقق من صحة تنسيق التاريخ YYYY-MM-DD
"""
try:
    datetime.strptime(date_str, "%Y-%m-%d")
    return True
except ValueError:
    return False

def hash_password(password: str) -> str:
"""
تشفير كلمة المرور
"""
return hashlib.sha256(password.encode()).hexdigest()

# ============================================
# دوال إدارة المستخدمين والجلسات
# ============================================

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[str]]:
"""
التحقق من بيانات المستخدم وإرجاع الدور إذا كان صحيحاً
"""
users_df = load_dataframe("Users")
if users_df.empty:
    return False, None

user_row = users_df[(users_df["username"] == username) & (users_df["password"] == password)]
if not user_row.empty:
    role = user_row.iloc[0]["role"]
    return True, role
return False, None

def add_new_user(username: str, password: str, role: str) -> Tuple[bool, str]:
"""
إضافة مستخدم جديد (لاعب فقط - الكابتن يضاف يدوياً)
"""
if not is_valid_three_part_name(username):
    return False, "الاسم يجب أن يكون ثلاثياً (ثلاثة أجزاء)"

if not is_username_unique(username):
    return False, "اسم المستخدم موجود مسبقاً"

users_df = load_dataframe("Users")
new_row = pd.DataFrame([{
    "username": username,
    "password": password,
    "role": role
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
            "subscription_status": "فعال"
        }])
        if subs_df.empty:
            subs_df = default_sub
        else:
            subs_df = pd.concat([subs_df, default_sub], ignore_index=True)
        save_dataframe("Subscriptions", subs_df)

return True, "تمت إضافة المستخدم بنجاح"

def get_all_players() -> List[str]:
"""
إرجاع قائمة بجميع أسماء اللاعبين
"""
users_df = load_dataframe("Users")
if users_df.empty:
    return []
return users_df[users_df["role"] == "player"]["username"].tolist()

def get_coach_username() -> Optional[str]:
"""
إرجاع اسم مستخدم الكابتن
"""
users_df = load_dataframe("Users")
if users_df.empty:
    return None
coach_row = users_df[users_df["role"] == "coach"]
if not coach_row.empty:
    return coach_row.iloc[0]["username"]
return None

# ============================================
# دوال إدارة الحضور والغياب
# ============================================

def record_attendance_multi(players: List[str], status: str, recorded_by: str) -> int:
"""
تسجيل حضور/غياب لمجموعة من اللاعبين لتاريخ اليوم
"""
if not players:
    return 0

today_str = date.today().isoformat()
attendance_df = load_dataframe("Attendance")

count = 0
for player in players:
    if attendance_df.empty:
        new_row = pd.DataFrame([{
            "player_name": player,
            "date": today_str,
            "status": status,
            "recorded_by": recorded_by
        }])
        attendance_df = new_row
    else:
        existing_idx = attendance_df[(attendance_df["player_name"] == player) & 
                                      (attendance_df["date"] == today_str)].index
        if len(existing_idx) > 0:
            attendance_df.loc[existing_idx, "status"] = status
            attendance_df.loc[existing_idx, "recorded_by"] = recorded_by
        else:
            new_row = pd.DataFrame([{
                "player_name": player,
                "date": today_str,
                "status": status,
                "recorded_by": recorded_by
            }])
            attendance_df = pd.concat([attendance_df, new_row], ignore_index=True)
    count += 1

save_dataframe("Attendance", attendance_df)
return count

def get_player_attendance_history(player_name: str) -> pd.DataFrame:
"""
استرجاع سجل الحضور والغياب للاعب معين
"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
player_att = attendance_df[attendance_df["player_name"] == player_name].copy()
if not player_att.empty:
    player_att["date"] = pd.to_datetime(player_att["date"])
    player_att = player_att.sort_values("date", ascending=False)
return player_att

def get_attendance_percentage(player_name: str) -> float:
"""
حساب نسبة الحضور للاعب
"""
player_att = get_player_attendance_history(player_name)
if player_att.empty:
    return 0.0
total = len(player_att)
present = len(player_att[player_att["status"] == "Present"])
return (present / total * 100) if total > 0 else 0.0

def get_absence_count(player_name: str) -> int:
"""
حساب عدد مرات الغياب للاعب
"""
player_att = get_player_attendance_history(player_name)
if player_att.empty:
    return 0
return len(player_att[player_att["status"] == "Absent"])

def get_today_attendance() -> pd.DataFrame:
"""
الحصول على حالة الحضور والغياب ليوم اليوم
"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
today_str = date.today().isoformat()
today_att = attendance_df[attendance_df["date"] == today_str].copy()
return today_att

def get_attendance_summary(start_date: date = None, end_date: date = None) -> pd.DataFrame:
"""
الحصول على ملخص الحضور لكل لاعب خلال فترة زمنية محددة
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

# ============================================
# دوال إدارة الاشتراكات والمدفوعات
# ============================================

def get_player_subscription(player_name: str) -> Optional[Dict]:
"""
استرجاع بيانات اشتراك لاعب معين
"""
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
status: str
) -> bool:
"""
تحديث أو إضافة اشتراك لاعب
"""
subs_df = load_dataframe("Subscriptions")

if subs_df.empty:
    new_row = pd.DataFrame([{
        "player_name": player_name,
        "monthly_fee": monthly_fee,
        "start_date": start_date,
        "end_date": end_date,
        "subscription_status": status
    }])
    subs_df = new_row
else:
    if player_name in subs_df["player_name"].values:
        subs_df.loc[subs_df["player_name"] == player_name, "monthly_fee"] = monthly_fee
        subs_df.loc[subs_df["player_name"] == player_name, "start_date"] = start_date
        subs_df.loc[subs_df["player_name"] == player_name, "end_date"] = end_date
        subs_df.loc[subs_df["player_name"] == player_name, "subscription_status"] = status
    else:
        new_row = pd.DataFrame([{
            "player_name": player_name,
            "monthly_fee": monthly_fee,
            "start_date": start_date,
            "end_date": end_date,
            "subscription_status": status
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
تسجيل دفعة جديدة للاعب
"""
payment_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
append_row("Payments", [player_name, amount, payment_method, payment_date, notes])
return True

def get_player_payments(player_name: str) -> pd.DataFrame:
"""
استرجاع جميع دفعات لاعب معين
"""
payments_df = load_dataframe("Payments")
if payments_df.empty:
    return pd.DataFrame()
player_payments = payments_df[payments_df["player_name"] == player_name].copy()
if not player_payments.empty:
    player_payments["amount"] = pd.to_numeric(player_payments["amount"], errors='coerce')
return player_payments

def get_total_paid(player_name: str) -> float:
"""
حساب إجمالي المبلغ المدفوع للاعب
"""
payments = get_player_payments(player_name)
if payments.empty:
    return 0.0
return payments["amount"].sum()

def calculate_total_due(player_name: str) -> float:
"""
حساب إجمالي المبلغ المستحق على اللاعب
"""
sub = get_player_subscription(player_name)
if not sub:
    return 0.0

try:
    start = datetime.strptime(sub["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(sub["end_date"], "%Y-%m-%d").date()
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    if months <= 0:
        months = 1
    monthly_fee = float(sub["monthly_fee"])
    return months * monthly_fee
except Exception:
    return 0.0

def calculate_remaining_amount(player_name: str) -> float:
"""
حساب المبلغ المتبقي على اللاعب
"""
total_due = calculate_total_due(player_name)
total_paid = get_total_paid(player_name)
return max(total_due - total_paid, 0.0)

def get_subscription_status_summary() -> pd.DataFrame:
"""
الحصول على ملخص حالة الاشتراكات لجميع اللاعبين
"""
subs_df = load_dataframe("Subscriptions")
if subs_df.empty:
    return pd.DataFrame()

summary = []
for _, row in subs_df.iterrows():
    player = row["player_name"]
    remaining = calculate_remaining_amount(player)
    summary.append({
        "اللاعب": player,
        "القيمة الشهرية": row["monthly_fee"],
        "تاريخ البداية": row["start_date"],
        "تاريخ النهاية": row["end_date"],
        "الحالة": row["subscription_status"],
        "المتبقي": remaining
    })
return pd.DataFrame(summary)

# ============================================
# دوال التقارير والإحصائيات المتقدمة
# ============================================

def get_financial_summary() -> Dict:
"""
الحصول على ملخص مالي عام للأكاديمية
"""
payments_df = load_dataframe("Payments")
subs_df = load_dataframe("Subscriptions")

total_collected = 0.0
if not payments_df.empty:
    payments_df["amount"] = pd.to_numeric(payments_df["amount"], errors='coerce')
    total_collected = payments_df["amount"].sum()

total_expected = 0.0
if not subs_df.empty:
    for _, row in subs_df.iterrows():
        try:
            start = datetime.strptime(row["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(row["end_date"], "%Y-%m-%d").date()
            months = (end.year - start.year) * 12 + (end.month - start.month) + 1
            total_expected += months * float(row["monthly_fee"])
        except:
            pass

return {
    "total_collected": total_collected,
    "total_expected": total_expected,
    "outstanding": max(total_expected - total_collected, 0.0)
}

def get_monthly_collection() -> pd.DataFrame:
"""
تحليل المدفوعات الشهرية
"""
payments_df = load_dataframe("Payments")
if payments_df.empty:
    return pd.DataFrame()

payments_df["payment_date"] = pd.to_datetime(payments_df["payment_date"])
payments_df["month"] = payments_df["payment_date"].dt.strftime("%Y-%m")
monthly = payments_df.groupby("month")["amount"].sum().reset_index()
monthly = monthly.sort_values("month")
return monthly

def get_attendance_trend(player_name: str = None) -> pd.DataFrame:
"""
تحليل اتجاه الحضور عبر الزمن
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

# ============================================
# دوال واجهة المستخدم (UI Components)
# ============================================

def display_header(title: str, subtitle: str = ""):
"""
عرض رأس الصفحة
"""
st.markdown(f"""
<div class="main-header">
    <h1>⚽ {title}</h1>
    <p>{subtitle}</p>
</div>
""", unsafe_allow_html=True)

def display_metric_card(label: str, value: str, icon: str = "📊"):
"""
عرض بطاقة مقياس
"""
st.markdown(f"""
<div class="metric-card">
    <div style="font-size: 2rem;">{icon}</div>
    <div class="metric-value">{value}</div>
    <div class="metric-label">{label}</div>
</div>
""", unsafe_allow_html=True)

def show_sidebar_user_info():
"""
عرض معلومات المستخدم في الشريط الجانبي
"""
if "username" in st.session_state:
    role_icon = "👨‍🏫" if st.session_state["role"] == "coach" else "⚽"
    role_name = "كابتن" if st.session_state["role"] == "coach" else "لاعب"
    st.sidebar.markdown(f"""
    <div class="user-info">
        <div style="font-size: 2rem;">{role_icon}</div>
        <div style="font-weight: bold;">{st.session_state['username']}</div>
        <div style="font-size: 0.8rem; opacity: 0.9;">{role_name}</div>
    </div>
    """, unsafe_allow_html=True)

def logout_button():
"""
زر تسجيل الخروج
"""
if st.sidebar.button("🚪 تسجيل خروج", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ============================================
# صفحة تسجيل الدخول
# ============================================

def login_page():
"""
عرض صفحة تسجيل الدخول
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
    </div>
    """, unsafe_allow_html=True)

# ============================================
# لوحة تحكم الكابتن
# ============================================

def coach_dashboard():
"""
عرض لوحة تحكم الكابتن
"""
display_header("لوحة تحكم الكابتن", "إدارة الحضور، الاشتراكات، والمدفوعات")

show_sidebar_user_info()
logout_button()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 إحصائيات سريعة")
players_count = len(get_all_players())
st.sidebar.metric("عدد اللاعبين", players_count)

today_att = get_today_attendance()
if not today_att.empty:
    present_today = len(today_att[today_att["status"] == "Present"])
    st.sidebar.metric("الحضور اليوم", f"{present_today} / {players_count}")

financial = get_financial_summary()
st.sidebar.metric("إجمالي التحصيل", f"{financial['total_collected']:.0f} جنيه")

tabs = st.tabs([
    "📋 الحضور والغياب",
    "💰 الاشتراكات والدفعات",
    "👥 إدارة اللاعبين",
    "📊 التقارير والإحصائيات"
])

# تبويب الحضور والغياب
with tabs[0]:
    st.subheader("تسجيل الحضور والغياب")
    
    players = get_all_players()
    if not players:
        st.warning("⚠️ لا يوجد لاعبون مسجلون. قم بإضافة لاعبين من تبويب إدارة اللاعبين.")
    else:
        selected_players = st.multiselect(
            "اختر اللاعبين",
            players,
            help="يمكنك اختيار أكثر من لاعب لتسجيل الحضور أو الغياب دفعة واحدة"
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ تسجيل حضور", use_container_width=True):
                if selected_players:
                    count = record_attendance_multi(selected_players, "Present", st.session_state["username"])
                    st.success(f"✓ تم تسجيل حضور {count} لاعب")
                    st.rerun()
                else:
                    st.warning("⚠️ الرجاء اختيار لاعبين أولاً")
        with col2:
            if st.button("❌ تسجيل غياب", use_container_width=True):
                if selected_players:
                    count = record_attendance_multi(selected_players, "Absent", st.session_state["username"])
                    st.success(f"✓ تم تسجيل غياب {count} لاعب")
                    st.rerun()
                else:
                    st.warning("⚠️ الرجاء اختيار لاعبين أولاً")
        
        st.markdown("---")
        st.subheader("حالة الحضور والغياب اليوم")
        today_attendance = get_today_attendance()
        if not today_attendance.empty:
            all_players_set = set(players)
            recorded_players = set(today_attendance["player_name"].tolist())
            missing_players = all_players_set - recorded_players
            
            display_df = today_attendance[["player_name", "status"]].copy()
            display_df.columns = ["اللاعب", "الحالة"]
            st.dataframe(display_df, use_container_width=True)
            
            if missing_players:
                st.info(f"📌 لم يتم تسجيل {len(missing_players)} لاعب بعد: {', '.join(missing_players)}")
        else:
            st.info("📌 لم يتم تسجيل أي حضور أو غياب اليوم")
        
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

# تبويب الاشتراكات والدفعات
with tabs[1]:
    st.subheader("إدارة الاشتراكات والمدفوعات")
    
    players = get_all_players()
    if not players:
        st.warning("⚠️ لا يوجد لاعبون مسجلون")
    else:
        selected_player = st.selectbox("اختر لاعباً", players, key="sub_select")
        
        if selected_player:
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
                    
                    if st.form_submit_button("💾 تحديث الاشتراك", use_container_width=True):
                        update_player_subscription(
                            selected_player,
                            monthly_fee,
                            start_date.isoformat(),
                            end_date.isoformat(),
                            status
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
            
            st.markdown("#### 📜 سجل المدفوعات")
            payments = get_player_payments(selected_player)
            if not payments.empty:
                display_payments = payments[["amount", "payment_method", "payment_date", "notes"]].copy()
                display_payments.columns = ["المبلغ", "طريقة الدفع", "تاريخ الدفع", "ملاحظات"]
                st.dataframe(display_payments, use_container_width=True)
            else:
                st.info("لا توجد مدفوعات مسجلة لهذا اللاعب")

# تبويب إدارة اللاعبين
with tabs[2]:
    st.subheader("إدارة اللاعبين")
    
    st.markdown("#### ➕ إضافة لاعب جديد")
    with st.form("add_player_form"):
        new_username = st.text_input("الاسم الثلاثي", placeholder="مثال: عمر خالد محمود")
        new_password = st.text_input("كلمة المرور", type="password", placeholder="كلمة مرور مؤقتة")
        if st.form_submit_button("إضافة لاعب", use_container_width=True):
            if not new_username or not new_password:
                st.error("⚠️ الرجاء إدخال الاسم الثلاثي وكلمة المرور")
            else:
                success, message = add_new_user(new_username, new_password, "player")
                if success:
                    st.success(f"✓ {message}")
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    
    st.markdown("---")
    st.markdown("#### 📋 قائمة اللاعبين")
    players_list = get_all_players()
    if players_list:
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
        
        with st.expander("⚠️ حذف لاعب (عملية لا ترجع)"):
            player_to_delete = st.selectbox("اختر لاعباً للحذف", players_list, key="delete_select")
            if st.button("🗑️ حذف اللاعب", use_container_width=True):
                st.warning("هذه العملية نهائية. هل أنت متأكد؟")
                confirm = st.checkbox("نعم، أنا متأكد من حذف هذا اللاعب")
                if confirm:
                    users_df = load_dataframe("Users")
                    users_df = users_df[users_df["username"] != player_to_delete]
                    save_dataframe("Users", users_df)
                    
                    att_df = load_dataframe("Attendance")
                    if not att_df.empty:
                        att_df = att_df[att_df["player_name"] != player_to_delete]
                        save_dataframe("Attendance", att_df)
                    
                    subs_df = load_dataframe("Subscriptions")
                    if not subs_df.empty:
                        subs_df = subs_df[subs_df["player_name"] != player_to_delete]
                        save_dataframe("Subscriptions", subs_df)
                    
                    pay_df = load_dataframe("Payments")
                    if not pay_df.empty:
                        pay_df = pay_df[pay_df["player_name"] != player_to_delete]
                        save_dataframe("Payments", pay_df)
                    
                    st.success(f"✓ تم حذف اللاعب {player_to_delete}")
                    st.rerun()
    else:
        st.info("لا يوجد لاعبون مسجلون حالياً")

# تبويب التقارير والإحصائيات
with tabs[3]:
    st.subheader("التقارير والإحصائيات")
    
    report_tabs = st.tabs(["📈 إحصائيات الحضور", "💰 تقارير مالية", "📊 تحليلات"])
    
    with report_tabs[0]:
        st.markdown("#### ملخص الحضور لجميع اللاعبين")
        summary = get_attendance_summary()
        if not summary.empty:
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
            
            display_summary = summary[["player_name", "total_sessions", "present", "absent", "attendance_percentage"]].copy()
            display_summary.columns = ["اللاعب", "عدد الجلسات", "حاضر", "غائب", "نسبة الحضور %"]
            st.dataframe(display_summary, use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور كافية لعرض الإحصائيات")
        
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
        financial = get_financial_summary()
        col1, col2, col3 = st.columns(3)
        with col1:
            display_metric_card("إجمالي التحصيل", f"{financial['total_collected']:.0f} جنيه", "💰")
        with col2:
            display_metric_card("المتوقع تحصيله", f"{financial['total_expected']:.0f} جنيه", "📋")
        with col3:
            display_metric_card("المتأخرات", f"{financial['outstanding']:.0f} جنيه", "⚠️")
        
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
    
    with report_tabs[2]:
        st.markdown("#### تحليل أداء اللاعبين")
        if not summary.empty:
            top_players = summary.nlargest(5, "attendance_percentage")[["player_name", "attendance_percentage"]]
            st.markdown("**🏆 أفضل 5 لاعبين من حيث الحضور**")
            for i, row in top_players.iterrows():
                st.write(f"{i+1}. {row['player_name']}: {row['attendance_percentage']:.1f}%")
            
            bottom_players = summary.nsmallest(5, "attendance_percentage")[["player_name", "attendance_percentage"]]
            st.markdown("**⚠️ أسوأ 5 لاعبين من حيث الحضور**")
            for i, row in bottom_players.iterrows():
                st.write(f"{i+1}. {row['player_name']}: {row['attendance_percentage']:.1f}%")
        else:
            st.info("لا توجد بيانات كافية")

# ============================================
# صفحة اللاعب
# ============================================

def player_dashboard():
"""
عرض لوحة معلومات اللاعب
"""
player_name = st.session_state["username"]
display_header(f"مرحباً {player_name}", "لوحة معلومات اللاعب")

show_sidebar_user_info()
logout_button()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📈 إحصائياتي")
percentage = get_attendance_percentage(player_name)
st.sidebar.metric("نسبة الحضور", f"{percentage:.1f}%")

total_paid = get_total_paid(player_name)
remaining = calculate_remaining_amount(player_name)
st.sidebar.metric("إجمالي المدفوع", f"{total_paid:.2f} جنيه")
st.sidebar.metric("المتبقي", f"{remaining:.2f} جنيه")

col1, col2, col3 = st.columns(3)
with col1:
    display_metric_card("نسبة الحضور", f"{percentage:.1f}%", "📊")
with col2:
    display_metric_card("إجمالي المدفوع", f"{total_paid:.2f} جنيه", "💰")
with col3:
    display_metric_card("المتبقي", f"{remaining:.2f} جنيه", "📌")

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
else:
    st.warning("لا يوجد اشتراك مسجل لك. الرجاء التواصل مع الكابتن.")

st.markdown("## 📋 سجل الحضور والغياب")
attendance_history = get_player_attendance_history(player_name)
if not attendance_history.empty:
    attendance_history["month"] = attendance_history["date"].dt.strftime("%Y-%m")
    monthly_counts = attendance_history.groupby(["month", "status"]).size().unstack(fill_value=0)
    if "Present" in monthly_counts.columns and "Absent" in monthly_counts.columns:
        fig = go.Figure(data=[
            go.Bar(name="حاضر", x=monthly_counts.index, y=monthly_counts["Present"], marker_color="green"),
            go.Bar(name="غائب", x=monthly_counts.index, y=monthly_counts["Absent"], marker_color="red")
        ])
        fig.update_layout(barmode="group", title="الحضور والغياب شهرياً", xaxis_title="الشهر", yaxis_title="عدد المرات")
        st.plotly_chart(fig, use_container_width=True)
    
    display_att = attendance_history[["date", "status"]].copy()
    display_att["date"] = display_att["date"].dt.strftime("%Y-%m-%d")
    display_att.columns = ["التاريخ", "الحالة"]
    st.dataframe(display_att, use_container_width=True)
else:
    st.info("لا توجد سجلات حضور لك بعد")

st.markdown("## 💳 سجل مدفوعاتي")
payments = get_player_payments(player_name)
if not payments.empty:
    display_pay = payments[["amount", "payment_method", "payment_date", "notes"]].copy()
    display_pay.columns = ["المبلغ", "طريقة الدفع", "تاريخ الدفع", "ملاحظات"]
    st.dataframe(display_pay, use_container_width=True)
else:
    st.info("لا توجد مدفوعات مسجلة لك بعد")

# ============================================
# التطبيق الرئيسي
# ============================================

def main():
"""
الدالة الرئيسية لتشغيل التطبيق
"""
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

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

if __name__ == "__main__":
main()
