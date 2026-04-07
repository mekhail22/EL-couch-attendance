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
# تحميل الأنماط المخصصة (CSS) - نسخة آمنة
# ============================================
st.markdown(
"""
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
.stButton button {
    width: 100%;
    border-radius: 8px;
    font-weight: bold;
}
.user-info {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    margin-bottom: 1rem;
    text-align: center;
}
</style>
""",
unsafe_allow_html=True
)

# ============================================
# دوال الاتصال بـ Google Sheets
# ============================================

@st.cache_resource(ttl=3600)
def get_google_sheets_client():
"""إنشاء عميل Google Sheets من secrets"""
try:
    if "google" not in st.secrets:
        st.error("❌ لم يتم العثور على إعدادات Google في secrets.")
        st.stop()
    if "service_account" not in st.secrets["google"]:
        st.error("❌ لم يتم العثور على service_account في secrets.google.")
        st.stop()
    
    service_account_info = dict(st.secrets["google"]["service_account"])
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    return gspread.authorize(credentials)
except Exception as e:
    st.error(f"⚠️ خطأ في الاتصال بـ Google Sheets: {str(e)}")
    st.stop()

def get_spreadsheet():
"""الحصول على كائن جدول البيانات"""
client = get_google_sheets_client()
try:
    spreadsheet_id = st.secrets["google"]["spreadsheet_id"]
    return client.open_by_key(spreadsheet_id)
except Exception as e:
    st.error(f"⚠️ لا يمكن الوصول إلى جدول البيانات: {str(e)}")
    st.stop()

def load_dataframe(sheet_name: str) -> pd.DataFrame:
"""تحميل ورقة كاملة إلى DataFrame"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # تحويل الأعمدة الرقمية
        for col in ['amount', 'monthly_fee']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    else:
        return pd.DataFrame()
except gspread.WorksheetNotFound:
    spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    # إضافة رؤوس الأعمدة
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
"""حفظ DataFrame بالكامل في ورقة"""
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
        "Users": ["username", "password", "role"],
        "Attendance": ["player_name", "date", "status", "recorded_by"],
        "Subscriptions": ["player_name", "monthly_fee", "start_date", "end_date", "subscription_status"],
        "Payments": ["player_name", "amount", "payment_method", "payment_date", "notes"]
    }
    if sheet_name in headers_map:
        worksheet.update([headers_map[sheet_name]])

def append_row(sheet_name: str, row_data: List[Any]):
"""إضافة صف جديد إلى الورقة"""
spreadsheet = get_spreadsheet()
try:
    worksheet = spreadsheet.worksheet(sheet_name)
    worksheet.append_row(row_data)
except gspread.WorksheetNotFound:
    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    worksheet.append_row(row_data)

# ============================================
# دوال التحقق من صحة البيانات
# ============================================

def is_valid_three_part_name(name: str) -> bool:
"""التحقق من أن الاسم ثلاثي (ثلاثة أجزاء)"""
if not name or not isinstance(name, str):
    return False
parts = name.strip().split()
return len(parts) == 3 and all(len(part) > 0 for part in parts)

def is_username_unique(username: str) -> bool:
"""التحقق من عدم تكرار اسم المستخدم"""
users_df = load_dataframe("Users")
if users_df.empty:
    return True
return username not in users_df["username"].values

# ============================================
# دوال إدارة المستخدمين
# ============================================

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[str]]:
"""التحقق من بيانات المستخدم"""
users_df = load_dataframe("Users")
if users_df.empty:
    return False, None
user_row = users_df[(users_df["username"] == username) & (users_df["password"] == password)]
if not user_row.empty:
    return True, user_row.iloc[0]["role"]
return False, None

def add_new_user(username: str, password: str, role: str) -> Tuple[bool, str]:
"""إضافة مستخدم جديد"""
if not is_valid_three_part_name(username):
    return False, "الاسم يجب أن يكون ثلاثياً (ثلاثة أجزاء)"
if not is_username_unique(username):
    return False, "اسم المستخدم موجود مسبقاً"

users_df = load_dataframe("Users")
new_row = pd.DataFrame([{"username": username, "password": password, "role": role}])
users_df = pd.concat([users_df, new_row], ignore_index=True)
save_dataframe("Users", users_df)

# إنشاء اشتراك افتراضي للاعب
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
"""قائمة بأسماء اللاعبين"""
users_df = load_dataframe("Users")
if users_df.empty:
    return []
return users_df[users_df["role"] == "player"]["username"].tolist()

# ============================================
# دوال الحضور والغياب
# ============================================

def record_attendance_multi(players: List[str], status: str, recorded_by: str) -> int:
"""تسجيل حضور/غياب لعدة لاعبين"""
if not players:
    return 0
today_str = date.today().isoformat()
attendance_df = load_dataframe("Attendance")
count = 0
for player in players:
    if attendance_df.empty:
        new_row = pd.DataFrame([{"player_name": player, "date": today_str, "status": status, "recorded_by": recorded_by}])
        attendance_df = new_row
    else:
        existing = attendance_df[(attendance_df["player_name"] == player) & (attendance_df["date"] == today_str)]
        if not existing.empty:
            attendance_df.loc[(attendance_df["player_name"] == player) & (attendance_df["date"] == today_str), "status"] = status
            attendance_df.loc[(attendance_df["player_name"] == player) & (attendance_df["date"] == today_str), "recorded_by"] = recorded_by
        else:
            new_row = pd.DataFrame([{"player_name": player, "date": today_str, "status": status, "recorded_by": recorded_by}])
            attendance_df = pd.concat([attendance_df, new_row], ignore_index=True)
    count += 1
save_dataframe("Attendance", attendance_df)
return count

def get_player_attendance_history(player_name: str) -> pd.DataFrame:
"""سجل حضور لاعب"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
player_att = attendance_df[attendance_df["player_name"] == player_name].copy()
if not player_att.empty:
    player_att["date"] = pd.to_datetime(player_att["date"])
    player_att = player_att.sort_values("date", ascending=False)
return player_att

def get_attendance_percentage(player_name: str) -> float:
"""نسبة الحضور"""
player_att = get_player_attendance_history(player_name)
if player_att.empty:
    return 0.0
total = len(player_att)
present = len(player_att[player_att["status"] == "Present"])
return (present / total * 100) if total > 0 else 0.0

def get_absence_count(player_name: str) -> int:
"""عدد مرات الغياب"""
player_att = get_player_attendance_history(player_name)
if player_att.empty:
    return 0
return len(player_att[player_att["status"] == "Absent"])

def get_today_attendance() -> pd.DataFrame:
"""حضور اليوم"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
today_str = date.today().isoformat()
return attendance_df[attendance_df["date"] == today_str].copy()

def get_attendance_summary() -> pd.DataFrame:
"""ملخص الحضور لكل اللاعبين"""
attendance_df = load_dataframe("Attendance")
if attendance_df.empty:
    return pd.DataFrame()
summary = attendance_df.groupby("player_name").agg(
    total_sessions=("status", "count"),
    present=("status", lambda x: (x == "Present").sum()),
    absent=("status", lambda x: (x == "Absent").sum())
).reset_index()
summary["attendance_percentage"] = (summary["present"] / summary["total_sessions"] * 100).round(1)
return summary.sort_values("attendance_percentage", ascending=False)

# ============================================
# دوال الاشتراكات والمدفوعات
# ============================================

def get_player_subscription(player_name: str) -> Optional[Dict]:
"""بيانات اشتراك لاعب"""
subs_df = load_dataframe("Subscriptions")
if subs_df.empty:
    return None
player_sub = subs_df[subs_df["player_name"] == player_name]
if player_sub.empty:
    return None
return player_sub.iloc[0].to_dict()

def update_player_subscription(player_name: str, monthly_fee: float, start_date: str, end_date: str, status: str) -> bool:
"""تحديث اشتراك لاعب"""
subs_df = load_dataframe("Subscriptions")
if subs_df.empty:
    subs_df = pd.DataFrame([{"player_name": player_name, "monthly_fee": monthly_fee, "start_date": start_date, "end_date": end_date, "subscription_status": status}])
else:
    if player_name in subs_df["player_name"].values:
        subs_df.loc[subs_df["player_name"] == player_name, "monthly_fee"] = monthly_fee
        subs_df.loc[subs_df["player_name"] == player_name, "start_date"] = start_date
        subs_df.loc[subs_df["player_name"] == player_name, "end_date"] = end_date
        subs_df.loc[subs_df["player_name"] == player_name, "subscription_status"] = status
    else:
        new_row = pd.DataFrame([{"player_name": player_name, "monthly_fee": monthly_fee, "start_date": start_date, "end_date": end_date, "subscription_status": status}])
        subs_df = pd.concat([subs_df, new_row], ignore_index=True)
save_dataframe("Subscriptions", subs_df)
return True

def add_payment(player_name: str, amount: float, payment_method: str, notes: str = "") -> bool:
"""تسجيل دفعة جديدة"""
payment_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
append_row("Payments", [player_name, amount, payment_method, payment_date, notes])
return True

def get_player_payments(player_name: str) -> pd.DataFrame:
"""سجل مدفوعات لاعب"""
payments_df = load_dataframe("Payments")
if payments_df.empty:
    return pd.DataFrame()
player_payments = payments_df[payments_df["player_name"] == player_name].copy()
if not player_payments.empty:
    player_payments["amount"] = pd.to_numeric(player_payments["amount"], errors='coerce')
return player_payments

def get_total_paid(player_name: str) -> float:
"""إجمالي المدفوع"""
payments = get_player_payments(player_name)
if payments.empty:
    return 0.0
return payments["amount"].sum()

def calculate_total_due(player_name: str) -> float:
"""إجمالي المستحق"""
sub = get_player_subscription(player_name)
if not sub:
    return 0.0
try:
    start = datetime.strptime(sub["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(sub["end_date"], "%Y-%m-%d").date()
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    if months <= 0:
        months = 1
    return months * float(sub["monthly_fee"])
except:
    return 0.0

def calculate_remaining_amount(player_name: str) -> float:
"""المتبقي"""
total_due = calculate_total_due(player_name)
total_paid = get_total_paid(player_name)
return max(total_due - total_paid, 0.0)

def get_financial_summary() -> Dict:
"""ملخص مالي عام"""
payments_df = load_dataframe("Payments")
subs_df = load_dataframe("Subscriptions")
total_collected = payments_df["amount"].sum() if not payments_df.empty else 0.0
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
return {"total_collected": total_collected, "total_expected": total_expected, "outstanding": max(total_expected - total_collected, 0.0)}

# ============================================
# دوال واجهة المستخدم
# ============================================

def display_header(title: str, subtitle: str = ""):
st.markdown(f"""
<div class="main-header">
    <h1>⚽ {title}</h1>
    <p>{subtitle}</p>
</div>
""", unsafe_allow_html=True)

def display_metric_card(label: str, value: str, icon: str = "📊"):
st.markdown(f"""
<div class="metric-card">
    <div style="font-size: 2rem;">{icon}</div>
    <div class="metric-value">{value}</div>
    <div class="metric-label">{label}</div>
</div>
""", unsafe_allow_html=True)

def show_sidebar_user_info():
if "username" in st.session_state:
    role_icon = "👨‍🏫" if st.session_state["role"] == "coach" else "⚽"
    role_name = "كابتن" if st.session_state["role"] == "coach" else "لاعب"
    st.sidebar.markdown(f"""
    <div class="user-info">
        <div style="font-size: 2rem;">{role_icon}</div>
        <div style="font-weight: bold;">{st.session_state['username']}</div>
        <div style="font-size: 0.8rem;">{role_name}</div>
    </div>
    """, unsafe_allow_html=True)

def logout_button():
if st.sidebar.button("🚪 تسجيل خروج", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ============================================
# صفحة تسجيل الدخول
# ============================================

def login_page():
display_header("الكوتش أكاديمي", "نظام إدارة الحضور والاشتراكات")
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("### 🔐 تسجيل الدخول")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)", placeholder="مثال: أحمد محمد علي")
        password = st.text_input("كلمة المرور", type="password")
        if st.form_submit_button("دخول", use_container_width=True):
            if not username or not password:
                st.error("⚠️ الرجاء إدخال اسم المستخدم وكلمة المرور")
            elif not is_valid_three_part_name(username):
                st.error("⚠️ اسم المستخدم يجب أن يكون ثلاثياً مثل: أحمد محمد علي")
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

# ============================================
# لوحة تحكم الكابتن
# ============================================

def coach_dashboard():
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

tabs = st.tabs(["📋 الحضور والغياب", "💰 الاشتراكات والدفعات", "👥 إدارة اللاعبين", "📊 التقارير والإحصائيات"])

# تبويب الحضور
with tabs[0]:
    st.subheader("تسجيل الحضور والغياب")
    players = get_all_players()
    if not players:
        st.warning("⚠️ لا يوجد لاعبون مسجلون. قم بإضافة لاعبين من تبويب إدارة اللاعبين.")
    else:
        selected = st.multiselect("اختر اللاعبين", players, help="يمكنك اختيار أكثر من لاعب")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ تسجيل حضور", use_container_width=True):
                if selected:
                    cnt = record_attendance_multi(selected, "Present", st.session_state["username"])
                    st.success(f"✓ تم تسجيل حضور {cnt} لاعب")
                    st.rerun()
                else:
                    st.warning("⚠️ اختر لاعبين أولاً")
        with col2:
            if st.button("❌ تسجيل غياب", use_container_width=True):
                if selected:
                    cnt = record_attendance_multi(selected, "Absent", st.session_state["username"])
                    st.success(f"✓ تم تسجيل غياب {cnt} لاعب")
                    st.rerun()
                else:
                    st.warning("⚠️ اختر لاعبين أولاً")
        
        st.markdown("---")
        st.subheader("حالة الحضور اليوم")
        today_attendance = get_today_attendance()
        if not today_attendance.empty:
            display_df = today_attendance[["player_name", "status"]].copy()
            display_df.columns = ["اللاعب", "الحالة"]
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("لم يتم تسجيل أي حضور أو غياب اليوم")
        
        st.subheader("إحصائيات الغياب")
        stats = []
        for p in players:
            stats.append({"اللاعب": p, "عدد مرات الغياب": get_absence_count(p), "نسبة الحضور": f"{get_attendance_percentage(p):.1f}%"})
        st.dataframe(pd.DataFrame(stats), use_container_width=True)

# تبويب الاشتراكات والدفعات
with tabs[1]:
    players = get_all_players()
    if not players:
        st.warning("⚠️ لا يوجد لاعبون")
    else:
        selected_player = st.selectbox("اختر لاعباً", players, key="sub_select")
        if selected_player:
            sub = get_player_subscription(selected_player)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📝 بيانات الاشتراك")
                with st.form("edit_sub"):
                    monthly = st.number_input("القيمة الشهرية (جنيه)", value=float(sub["monthly_fee"]) if sub else 200.0, step=50.0)
                    start = st.date_input("تاريخ البدء", value=datetime.strptime(sub["start_date"], "%Y-%m-%d").date() if sub else date.today())
                    end = st.date_input("تاريخ الانتهاء", value=datetime.strptime(sub["end_date"], "%Y-%m-%d").date() if sub else date.today() + timedelta(days=30))
                    status = st.selectbox("الحالة", ["فعال", "منتهي", "ملغي"], index=0 if not sub or sub.get("subscription_status")=="فعال" else 1)
                    if st.form_submit_button("تحديث الاشتراك"):
                        update_player_subscription(selected_player, monthly, start.isoformat(), end.isoformat(), status)
                        st.success("✓ تم التحديث")
                        st.rerun()
            with col2:
                st.markdown("#### 💰 ملخص مالي")
                st.metric("إجمالي المدفوع", f"{get_total_paid(selected_player):.2f} جنيه")
                st.metric("المستحق", f"{calculate_total_due(selected_player):.2f} جنيه")
                st.metric("المتبقي", f"{calculate_remaining_amount(selected_player):.2f} جنيه")
            
            st.markdown("#### 💵 تسجيل دفعة جديدة")
            with st.form("add_pay"):
                amt = st.number_input("المبلغ", min_value=0.0, step=10.0)
                method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("إضافة دفعة"):
                    if amt > 0:
                        add_payment(selected_player, amt, method, notes)
                        st.success("✓ تم إضافة الدفعة")
                        st.rerun()
                    else:
                        st.error("المبلغ يجب أن يكون أكبر من صفر")
            
            st.markdown("#### 📜 سجل المدفوعات")
            payments = get_player_payments(selected_player)
            if not payments.empty:
                st.dataframe(payments[["amount", "payment_method", "payment_date", "notes"]].rename(columns={"amount":"المبلغ","payment_method":"الطريقة","payment_date":"التاريخ","notes":"ملاحظات"}), use_container_width=True)
            else:
                st.info("لا توجد مدفوعات")

# تبويب إدارة اللاعبين
with tabs[2]:
    st.subheader("إضافة لاعب جديد")
    with st.form("add_player"):
        new_name = st.text_input("الاسم الثلاثي")
        new_pass = st.text_input("كلمة المرور", type="password")
        if st.form_submit_button("إضافة لاعب"):
            if not new_name or not new_pass:
                st.error("الرجاء ملء جميع الحقول")
            else:
                success, msg = add_new_user(new_name, new_pass, "player")
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    st.markdown("---")
    st.markdown("#### قائمة اللاعبين")
    players_list = get_all_players()
    if players_list:
        data = []
        for p in players_list:
            sub = get_player_subscription(p)
            data.append({"الاسم": p, "الاشتراك الشهري": f"{sub['monthly_fee']} جنيه" if sub else "غير محدد", "الحالة": sub['subscription_status'] if sub else "غير محدد", "المتبقي": f"{calculate_remaining_amount(p):.2f} جنيه"})
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("لا يوجد لاعبون")

# تبويب التقارير
with tabs[3]:
    st.subheader("إحصائيات الحضور")
    summary = get_attendance_summary()
    if not summary.empty:
        fig = px.bar(summary, x="player_name", y="attendance_percentage", title="نسبة الحضور لكل لاعب", labels={"player_name":"اللاعب","attendance_percentage":"النسبة (%)"}, color="attendance_percentage")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(summary[["player_name","total_sessions","present","absent","attendance_percentage"]].rename(columns={"player_name":"اللاعب","total_sessions":"عدد الجلسات","present":"حاضر","absent":"غائب","attendance_percentage":"نسبة الحضور %"}), use_container_width=True)
    else:
        st.info("لا توجد بيانات حضور")
    
    st.subheader("ملخص مالي")
    fin = get_financial_summary()
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي التحصيل", f"{fin['total_collected']:.0f} جنيه")
    col2.metric("المتوقع", f"{fin['total_expected']:.0f} جنيه")
    col3.metric("المتأخرات", f"{fin['outstanding']:.0f} جنيه")

# ============================================
# صفحة اللاعب
# ============================================

def player_dashboard():
player_name = st.session_state["username"]
display_header(f"مرحباً {player_name}", "لوحة معلومات اللاعب")
show_sidebar_user_info()
logout_button()

st.sidebar.markdown("---")
st.sidebar.markdown("### إحصائياتي")
perc = get_attendance_percentage(player_name)
st.sidebar.metric("نسبة الحضور", f"{perc:.1f}%")
total_paid = get_total_paid(player_name)
remaining = calculate_remaining_amount(player_name)
st.sidebar.metric("إجمالي المدفوع", f"{total_paid:.2f} جنيه")
st.sidebar.metric("المتبقي", f"{remaining:.2f} جنيه")

col1, col2, col3 = st.columns(3)
with col1:
    display_metric_card("نسبة الحضور", f"{perc:.1f}%", "📊")
with col2:
    display_metric_card("إجمالي المدفوع", f"{total_paid:.2f} جنيه", "💰")
with col3:
    display_metric_card("المتبقي", f"{remaining:.2f} جنيه", "📌")

st.markdown("## اشتراكي الحالي")
sub = get_player_subscription(player_name)
if sub:
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("القيمة الشهرية", f"{sub['monthly_fee']} جنيه")
    col_b.metric("تاريخ البدء", sub['start_date'])
    col_c.metric("تاريخ الانتهاء", sub['end_date'])
    status_color = "green" if sub['subscription_status'] == "فعال" else "red"
    st.markdown(f"**الحالة:** <span style='color:{status_color}'>{sub['subscription_status']}</span>", unsafe_allow_html=True)
else:
    st.warning("لا يوجد اشتراك مسجل")

st.markdown("## سجل الحضور والغياب")
att_history = get_player_attendance_history(player_name)
if not att_history.empty:
    att_history["month"] = att_history["date"].dt.strftime("%Y-%m")
    monthly = att_history.groupby(["month", "status"]).size().unstack(fill_value=0)
    if "Present" in monthly.columns and "Absent" in monthly.columns:
        fig = go.Figure(data=[
            go.Bar(name="حاضر", x=monthly.index, y=monthly["Present"], marker_color="green"),
            go.Bar(name="غائب", x=monthly.index, y=monthly["Absent"], marker_color="red")
        ])
        fig.update_layout(barmode="group", title="الحضور والغياب شهرياً")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(att_history[["date","status"]].rename(columns={"date":"التاريخ","status":"الحالة"}), use_container_width=True)
else:
    st.info("لا توجد سجلات حضور")

st.markdown("## سجل مدفوعاتي")
payments = get_player_payments(player_name)
if not payments.empty:
    st.dataframe(payments[["amount","payment_method","payment_date","notes"]].rename(columns={"amount":"المبلغ","payment_method":"طريقة الدفع","payment_date":"تاريخ الدفع","notes":"ملاحظات"}), use_container_width=True)
else:
    st.info("لا توجد مدفوعات مسجلة")

# ============================================
# التشغيل الرئيسي
# ============================================

def main():
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
        st.error("دور غير معروف")
        if st.button("تسجيل خروج"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
main()
