import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import date, datetime, timedelta
import re

# -------------------- إعداد الصفحة --------------------
st.set_page_config(page_title="الكوتش أكاديمي", page_icon="⚽", layout="wide")

# -------------------- دالة الاتصال بـ Google Sheets --------------------
@st.cache_resource
def get_gsheet_client():
    """إنشاء عميل gspread باستخدام بيانات الاعتماد من secrets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # تجميع بيانات service account من secrets
    service_account_info = st.secrets["google"]["service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)
    return client

def get_spreadsheet():
    """فتح جدول البيانات الرئيسي."""
    client = get_gsheet_client()
    sheet_id = st.secrets["google"]["spreadsheet_id"]
    return client.open_by_key(sheet_id)

def init_sheets():
    """تهيئة الأوراق المطلوبة إذا لم تكن موجودة."""
    sh = get_spreadsheet()
    existing_titles = [ws.title for ws in sh.worksheets()]
    
    if "Users" not in existing_titles:
        ws = sh.add_worksheet("Users", rows=100, cols=10)
        ws.append_row(["username", "password", "role"])  # role: coach أو player
        # إضافة كابتن افتراضي (اختياري)
        ws.append_row(["أحمد محمد علي", "coach123", "coach"])
    
    if "Attendance" not in existing_titles:
        ws = sh.add_worksheet("Attendance", rows=1000, cols=10)
        ws.append_row(["player_name", "date", "status", "recorded_by"])
    
    if "Subscriptions" not in existing_titles:
        ws = sh.add_worksheet("Subscriptions", rows=100, cols=10)
        ws.append_row(["player_name", "monthly_fee", "start_date", "end_date", "subscription_status"])
    
    if "Payments" not in existing_titles:
        ws = sh.add_worksheet("Payments", rows=1000, cols=10)
        ws.append_row(["player_name", "amount", "payment_method", "payment_date", "notes"])

# -------------------- دوال قراءة/كتابة البيانات --------------------
def load_users():
    sh = get_spreadsheet()
    ws = sh.worksheet("Users")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_user(username, password, role="player"):
    sh = get_spreadsheet()
    ws = sh.worksheet("Users")
    ws.append_row([username, password, role])
    # مسح الكاش لتحديث البيانات
    st.cache_data.clear()

def load_attendance():
    sh = get_spreadsheet()
    ws = sh.worksheet("Attendance")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_attendance(player_name, date_str, status, recorded_by):
    sh = get_spreadsheet()
    ws = sh.worksheet("Attendance")
    ws.append_row([player_name, date_str, status, recorded_by])
    st.cache_data.clear()

def load_subscriptions():
    sh = get_spreadsheet()
    ws = sh.worksheet("Subscriptions")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_subscription(player_name, monthly_fee, start_date, end_date, status):
    sh = get_spreadsheet()
    ws = sh.worksheet("Subscriptions")
    ws.append_row([player_name, monthly_fee, start_date, end_date, status])
    st.cache_data.clear()

def update_subscription(player_name, monthly_fee, start_date, end_date, status):
    """تحديث آخر اشتراك نشط للاعب (أو إنشاء جديد). في هذا التطبيق المبسط، سنضيف صفًا جديدًا دائمًا، ولكن يمكن تعديله حسب الحاجة."""
    save_subscription(player_name, monthly_fee, start_date, end_date, status)

def load_payments():
    sh = get_spreadsheet()
    ws = sh.worksheet("Payments")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_payment(player_name, amount, method, pay_date, notes):
    sh = get_spreadsheet()
    ws = sh.worksheet("Payments")
    ws.append_row([player_name, amount, method, pay_date, notes])
    st.cache_data.clear()

# -------------------- دوال مساعدة للتحقق من الأسماء --------------------
def is_valid_arabic_name(name):
    """التحقق من أن الاسم يتكون من ثلاث كلمات على الأقل (يمكن أن تحتوي على عربي/إنجليزي)"""
    parts = name.strip().split()
    return len(parts) >= 3

def username_exists(username):
    df = load_users()
    return username in df['username'].values

def authenticate(username, password):
    df = load_users()
    user_row = df[(df['username'] == username) & (df['password'] == password)]
    if not user_row.empty:
        return user_row.iloc[0]['role']
    return None

# -------------------- دوال الحسابات المالية --------------------
def get_player_subscription(player_name):
    """استرجاع آخر اشتراك نشط للاعب."""
    df = load_subscriptions()
    if df.empty:
        return None
    player_subs = df[df['player_name'] == player_name]
    if player_subs.empty:
        return None
    # ترتيب تنازلي حسب تاريخ البداية (أحدث اشتراك)
    player_subs = player_subs.sort_values('start_date', ascending=False)
    return player_subs.iloc[0].to_dict()

def calculate_total_due(subscription, as_of_date=None):
    """حساب المبلغ المستحق من بداية الاشتراك حتى تاريخ محدد (اليوم افتراضيًا)."""
    if as_of_date is None:
        as_of_date = date.today()
    start = datetime.strptime(subscription['start_date'], "%Y-%m-%d").date()
    monthly_fee = float(subscription['monthly_fee'])
    # حساب عدد الأشهر (تقريبي)
    months_passed = (as_of_date.year - start.year) * 12 + (as_of_date.month - start.month)
    if as_of_date.day >= start.day:
        months_passed += 1
    if months_passed < 0:
        months_passed = 0
    return months_passed * monthly_fee

def get_player_payments(player_name):
    df = load_payments()
    if df.empty:
        return pd.DataFrame()
    return df[df['player_name'] == player_name]

# -------------------- واجهة تسجيل الدخول --------------------
def login_page():
    st.title("⚽ الكوتش أكاديمي - تسجيل الدخول")
    
    tab1, tab2 = st.tabs(["تسجيل الدخول", "إنشاء حساب لاعب جديد"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("الاسم الثلاثي (اسم المستخدم)")
            password = st.text_input("كلمة المرور", type="password")
            submitted = st.form_submit_button("دخول")
            if submitted:
                if not is_valid_arabic_name(username):
                    st.error("يجب إدخال الاسم الثلاثي كاملاً.")
                else:
                    role = authenticate(username, password)
                    if role:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.success("تم تسجيل الدخول بنجاح!")
                        st.rerun()
                    else:
                        st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")
    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("الاسم الثلاثي (سيستخدم كاسم مستخدم)")
            new_password = st.text_input("كلمة المرور", type="password")
            confirm_password = st.text_input("تأكيد كلمة المرور", type="password")
            submitted = st.form_submit_button("إنشاء حساب")
            if submitted:
                if not is_valid_arabic_name(new_username):
                    st.error("يجب أن يكون الاسم ثلاثيًا (ثلاث كلمات على الأقل).")
                elif new_password != confirm_password:
                    st.error("كلمتا المرور غير متطابقتين.")
                elif username_exists(new_username):
                    st.error("هذا الاسم مستخدم بالفعل.")
                else:
                    save_user(new_username, new_password, "player")
                    st.success("تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
                    st.balloons()

# -------------------- الشريط الجانبي المشترك --------------------
def sidebar():
    with st.sidebar:
        st.markdown("## ⚽ الكوتش أكاديمي")
        st.write(f"مرحباً، {st.session_state.username} ({st.session_state.role})")
        if st.button("تسجيل الخروج"):
            for key in ['logged_in', 'username', 'role']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# -------------------- لوحة الكابتن --------------------
def coach_dashboard():
    st.title("📋 لوحة تحكم الكابتن")
    menu = st.selectbox("القائمة", ["تسجيل الحضور", "إحصائيات الغياب", "إدارة الاشتراكات", "تسجيل دفعة", "عرض المدفوعات"])
    
    if menu == "تسجيل الحضور":
        st.header("تسجيل حضور وغياب اللاعبين")
        # جلب قائمة اللاعبين
        users_df = load_users()
        players = users_df[users_df['role'] == 'player']['username'].tolist()
        if not players:
            st.warning("لا يوجد لاعبون مسجلون بعد.")
            return
        
        today = date.today().isoformat()
        st.subheader(f"تاريخ اليوم: {today}")
        
        # تحميل سجلات الحضور لهذا اليوم
        att_df = load_attendance()
        today_records = att_df[att_df['date'] == today] if not att_df.empty else pd.DataFrame()
        present_players = today_records[today_records['status'] == 'Present']['player_name'].tolist() if not today_records.empty else []
        
        # عرض خيارات متعددة لتحديد الغياب
        absent_choices = st.multiselect(
            "اختر اللاعبين الغائبين (سيتم اعتبار الباقين حاضرين)",
            options=players,
            default=[p for p in players if p not in present_players]  # افتراضيًا كل من لم يسجل حضورًا اليوم
        )
        
        if st.button("💾 تسجيل الحضور والغياب"):
            recorded_by = st.session_state.username
            # حذف سجلات اليوم السابقة لتجنب التكرار (اختياري)
            sh = get_spreadsheet()
            ws = sh.worksheet("Attendance")
            # البحث عن صفوف اليوم وحذفها
            if not att_df.empty:
                rows_to_delete = []
                for idx, row in att_df.iterrows():
                    if row['date'] == today:
                        # نعرف رقم الصف في الشيت (مع الأخذ بعين الاعتبار صف العنوان)
                        rows_to_delete.append(idx + 2)
                if rows_to_delete:
                    # حذف من الأسفل للأعلى
                    for row_num in sorted(rows_to_delete, reverse=True):
                        ws.delete_rows(row_num)
            
            # إضافة سجلات جديدة
            for player in players:
                status = "Absent" if player in absent_choices else "Present"
                save_attendance(player, today, status, recorded_by)
            st.success("تم تسجيل الحضور بنجاح!")
            st.rerun()
        
        # عرض سجل اليوم
        st.subheader("سجل الحضور اليوم")
        today_att = load_attendance()
        if not today_att.empty:
            today_att = today_att[today_att['date'] == today][['player_name', 'status']]
            st.dataframe(today_att, use_container_width=True)
    
    elif menu == "إحصائيات الغياب":
        st.header("إحصائيات الغياب والحضور")
        att_df = load_attendance()
        if att_df.empty:
            st.info("لا توجد سجلات حضور بعد.")
            return
        
        # حساب عدد أيام الغياب لكل لاعب
        absence_counts = att_df[att_df['status'] == 'Absent'].groupby('player_name').size().reset_index(name='أيام الغياب')
        total_days = att_df['player_name'].value_counts().reset_index()
        total_days.columns = ['player_name', 'إجمالي الأيام']
        
        stats = pd.merge(total_days, absence_counts, on='player_name', how='left').fillna(0)
        stats['أيام الغياب'] = stats['أيام الغياب'].astype(int)
        stats['نسبة الحضور %'] = ((stats['إجمالي الأيام'] - stats['أيام الغياب']) / stats['إجمالي الأيام'] * 100).round(1)
        
        st.dataframe(stats.sort_values('نسبة الحضور %', ascending=False), use_container_width=True)
    
    elif menu == "إدارة الاشتراكات":
        st.header("إدارة اشتراكات اللاعبين")
        users_df = load_users()
        players = users_df[users_df['role'] == 'player']['username'].tolist()
        if not players:
            st.warning("لا يوجد لاعبون.")
            return
        
        # عرض الاشتراكات الحالية
        subs_df = load_subscriptions()
        if not subs_df.empty:
            st.subheader("الاشتراكات المسجلة")
            st.dataframe(subs_df, use_container_width=True)
        
        st.subheader("إضافة / تعديل اشتراك")
        with st.form("subscription_form"):
            player = st.selectbox("اختر اللاعب", players)
            monthly_fee = st.number_input("الرسوم الشهرية (جنيه)", min_value=0.0, step=50.0)
            start_date = st.date_input("تاريخ البداية", value=date.today())
            end_date = st.date_input("تاريخ النهاية", value=date.today() + timedelta(days=30))
            status = st.selectbox("حالة الاشتراك", ["نشط", "منتهي", "متوقف"])
            submitted = st.form_submit_button("حفظ الاشتراك")
            if submitted:
                update_subscription(player, monthly_fee, start_date.isoformat(), end_date.isoformat(), status)
                st.success("تم حفظ الاشتراك بنجاح!")
                st.rerun()
    
    elif menu == "تسجيل دفعة":
        st.header("تسجيل دفعة مالية")
        users_df = load_users()
        players = users_df[users_df['role'] == 'player']['username'].tolist()
        if not players:
            st.warning("لا يوجد لاعبون.")
            return
        
        with st.form("payment_form"):
            player = st.selectbox("اختر اللاعب", players)
            amount = st.number_input("المبلغ", min_value=0.0, step=50.0)
            method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
            pay_date = st.date_input("تاريخ الدفع", value=date.today())
            notes = st.text_area("ملاحظات")
            submitted = st.form_submit_button("تسجيل الدفعة")
            if submitted:
                save_payment(player, amount, method, pay_date.isoformat(), notes)
                st.success("تم تسجيل الدفعة!")
                st.rerun()
    
    elif menu == "عرض المدفوعات":
        st.header("سجل المدفوعات")
        payments_df = load_payments()
        if payments_df.empty:
            st.info("لا توجد مدفوعات مسجلة.")
        else:
            st.dataframe(payments_df, use_container_width=True)

# -------------------- صفحة اللاعب --------------------
def player_dashboard():
    st.title(f"👤 مرحباً {st.session_state.username}")
    player_name = st.session_state.username
    
    # تحميل البيانات
    att_df = load_attendance()
    subs_df = load_subscriptions()
    payments_df = load_payments()
    
    # سجل الغياب
    st.header("📅 سجل الغياب")
    if not att_df.empty:
        player_att = att_df[att_df['player_name'] == player_name][['date', 'status']].sort_values('date', ascending=False)
        if not player_att.empty:
            st.dataframe(player_att, use_container_width=True)
        else:
            st.info("لا توجد سجلات حضور بعد.")
    else:
        st.info("لا توجد سجلات حضور بعد.")
    
    # نسبة الحضور
    st.header("📊 نسبة الحضور")
    if not att_df.empty:
        total = len(att_df[att_df['player_name'] == player_name])
        absent = len(att_df[(att_df['player_name'] == player_name) & (att_df['status'] == 'Absent')])
        if total > 0:
            attendance_pct = ((total - absent) / total) * 100
            st.metric("نسبة الحضور", f"{attendance_pct:.1f}%")
            st.progress(attendance_pct / 100)
        else:
            st.info("لا توجد بيانات كافية.")
    
    # الاشتراك الحالي
    st.header("💳 الاشتراك الحالي")
    subscription = get_player_subscription(player_name)
    if subscription:
        st.write(f"**الرسوم الشهرية:** {subscription['monthly_fee']} جنيه")
        st.write(f"**تاريخ البداية:** {subscription['start_date']}")
        st.write(f"**تاريخ النهاية:** {subscription['end_date']}")
        st.write(f"**الحالة:** {subscription['subscription_status']}")
    else:
        st.warning("لا يوجد اشتراك مسجل لك.")
    
    # المدفوعات والمتبقي
    st.header("💰 المدفوعات والمستحقات")
    if subscription:
        total_due = calculate_total_due(subscription)
        player_payments = payments_df[payments_df['player_name'] == player_name] if not payments_df.empty else pd.DataFrame()
        total_paid = player_payments['amount'].sum() if not player_payments.empty else 0.0
        remaining = total_due - total_paid
        
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي المستحق", f"{total_due:.2f} ج")
        col2.metric("إجمالي المدفوع", f"{total_paid:.2f} ج")
        col3.metric("المتبقي", f"{remaining:.2f} ج")
    else:
        st.info("لا يوجد اشتراك لحساب المستحقات.")
    
    # سجل المدفوعات
    st.header("🧾 سجل المدفوعات")
    if not payments_df.empty:
        player_payments = payments_df[payments_df['player_name'] == player_name]
        if not player_payments.empty:
            st.dataframe(player_payments[['amount', 'payment_method', 'payment_date', 'notes']], use_container_width=True)
        else:
            st.info("لا توجد مدفوعات مسجلة.")
    else:
        st.info("لا توجد مدفوعات مسجلة.")

# -------------------- نقطة الدخول الرئيسية --------------------
def main():
    # تهيئة الأوراق عند أول تشغيل
    init_sheets()
    
    # التحقق من حالة تسجيل الدخول
    if 'logged_in' not in st.session_state or not st.session_state.logged_in:
        login_page()
        return
    
    # عرض الشريط الجانبي
    sidebar()
    
    # توجيه المستخدم حسب الدور
    if st.session_state.role == 'coach':
        coach_dashboard()
    else:
        player_dashboard()

if __name__ == "__main__":
    main()
