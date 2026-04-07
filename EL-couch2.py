import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, date
import re
from copy import deepcopy

# ========== تهيئة الصفحة ==========
st.set_page_config(page_title="الكوتش أكاديمي", layout="wide", initial_sidebar_state="auto")

# إضافة تنسيق RTL بسيط
st.markdown("""
    <style>
        body, .stApp, .stMarkdown, .stTextInput, .stSelectbox, .stButton button {
            text-align: right;
            direction: rtl;
        }
        .stSidebar .sidebar-content {
            direction: rtl;
        }
        .stDataFrame {
            direction: ltr;
        }
    </style>
""", unsafe_allow_html=True)

# ========== الاتصال بـ Google Sheets ==========
@st.cache_resource
def init_google_sheets():
    """إنشاء اتصال باستخدام service account من secrets"""
    creds_dict = dict(st.secrets["google"]["service_account"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(st.secrets["google"]["spreadsheet_id"])
    return spreadsheet

def load_sheet(sheet_name):
    """قراءة ورقة كاملة وإرجاع DataFrame"""
    spreadsheet = init_google_sheets()
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except gspread.WorksheetNotFound:
        return pd.DataFrame()

def save_sheet(sheet_name, df):
    """استبدال محتويات الورقة بالكامل بـ DataFrame"""
    spreadsheet = init_google_sheets()
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    else:
        worksheet.update([["لا توجد بيانات"]])

def append_row(sheet_name, row_data):
    """إضافة صف جديد إلى ورقة (للعمليات السريعة مثل المدفوعات)"""
    spreadsheet = init_google_sheets()
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.append_row(row_data)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
        worksheet.append_row(row_data)

# ========== دوال مساعدة للبيانات ==========
def is_three_part_name(name):
    """التحقق من أن الاسم ثلاثي (على الأقل مسافتان)"""
    parts = name.strip().split()
    return len(parts) == 3

def get_players_list():
    """إرجاع قائمة بأسماء اللاعبين (الدور = player)"""
    users = load_sheet("Users")
    if users.empty:
        return []
    players = users[users["role"] == "player"]["username"].tolist()
    return players

def get_player_subscription(player_name):
    """استرجاع اشتراك لاعب (افتراضي)"""
    subs = load_sheet("Subscriptions")
    if subs.empty:
        return None
    player_subs = subs[subs["player_name"] == player_name]
    if player_subs.empty:
        return None
    return player_subs.iloc[0].to_dict()

def update_subscription(player_name, monthly_fee, start_date, end_date, status):
    """تحديث أو إضافة اشتراك لاعب"""
    subs = load_sheet("Subscriptions")
    if subs.empty:
        new_row = pd.DataFrame([{
            "player_name": player_name,
            "monthly_fee": monthly_fee,
            "start_date": start_date,
            "end_date": end_date,
            "subscription_status": status
        }])
        subs = new_row
    else:
        if player_name in subs["player_name"].values:
            subs.loc[subs["player_name"] == player_name, "monthly_fee"] = monthly_fee
            subs.loc[subs["player_name"] == player_name, "start_date"] = start_date
            subs.loc[subs["player_name"] == player_name, "end_date"] = end_date
            subs.loc[subs["player_name"] == player_name, "subscription_status"] = status
        else:
            new_row = pd.DataFrame([{
                "player_name": player_name,
                "monthly_fee": monthly_fee,
                "start_date": start_date,
                "end_date": end_date,
                "subscription_status": status
            }])
            subs = pd.concat([subs, new_row], ignore_index=True)
    save_sheet("Subscriptions", subs)

def get_player_payments(player_name):
    """إرجاع جميع دفعات لاعب معين"""
    payments = load_sheet("Payments")
    if payments.empty:
        return pd.DataFrame()
    return payments[payments["player_name"] == player_name]

def add_payment(player_name, amount, method, notes):
    """إضافة دفعة جديدة"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_row("Payments", [player_name, amount, method, now, notes])

def record_attendance(player_name, status, recorded_by):
    """تسجيل حضور/غياب لليوم (تحديث إن وجد)"""
    att = load_sheet("Attendance")
    today_str = date.today().isoformat()
    if att.empty:
        new_row = pd.DataFrame([{
            "player_name": player_name,
            "date": today_str,
            "status": status,
            "recorded_by": recorded_by
        }])
        att = new_row
    else:
        existing = att[(att["player_name"] == player_name) & (att["date"] == today_str)]
        if not existing.empty:
            att.loc[(att["player_name"] == player_name) & (att["date"] == today_str), "status"] = status
            att.loc[(att["player_name"] == player_name) & (att["date"] == today_str), "recorded_by"] = recorded_by
        else:
            new_row = pd.DataFrame([{
                "player_name": player_name,
                "date": today_str,
                "status": status,
                "recorded_by": recorded_by
            }])
            att = pd.concat([att, new_row], ignore_index=True)
    save_sheet("Attendance", att)

def get_attendance_percentage(player_name):
    """حساب نسبة الحضور للاعب"""
    att = load_sheet("Attendance")
    if att.empty:
        return 0.0
    player_att = att[att["player_name"] == player_name]
    if player_att.empty:
        return 0.0
    total = len(player_att)
    present = len(player_att[player_att["status"] == "Present"])
    return (present / total * 100) if total > 0 else 0.0

def get_total_paid(player_name):
    """إجمالي المدفوع للاعب"""
    payments = get_player_payments(player_name)
    if payments.empty:
        return 0.0
    return payments["amount"].astype(float).sum()

def calculate_remaining(player_name):
    """حساب المتبقي = إجمالي الاشتراك المستحق - المدفوع"""
    sub = get_player_subscription(player_name)
    if not sub:
        return 0.0
    try:
        start = datetime.strptime(sub["start_date"], "%Y-%m-%d").date()
        end = datetime.strptime(sub["end_date"], "%Y-%m-%d").date()
        months = (end.year - start.year) * 12 + (end.month - start.month) + 1
        total_due = months * float(sub["monthly_fee"])
        paid = get_total_paid(player_name)
        return max(total_due - paid, 0.0)
    except:
        return 0.0

# ========== صفحات النظام ==========
def login_page():
    st.title("🏆 الكوتش أكاديمي - تسجيل الدخول")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول")
        if submitted:
            if not is_three_part_name(username):
                st.error("⚠️ اسم المستخدم يجب أن يكون ثلاثياً (ثلاثة أجزاء) مثال: أحمد محمد علي")
                return
            users = load_sheet("Users")
            if users.empty:
                st.error("لا يوجد مستخدمون في قاعدة البيانات")
                return
            user_row = users[(users["username"] == username) & (users["password"] == password)]
            if not user_row.empty:
                role = user_row.iloc[0]["role"]
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

def coach_dashboard():
    st.title("👨‍🏫 لوحة تحكم الكابتن")
    st.sidebar.markdown(f"**مرحباً كابتن {st.session_state['username']}**")
    if st.sidebar.button("🚪 تسجيل خروج"):
        logout()
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 الحضور والغياب", "💰 الاشتراكات والدفعات", "👥 إدارة اللاعبين", "📊 إحصائيات"])
    
    # ---------- تبويب الحضور ----------
    with tab1:
        players = get_players_list()
        if not players:
            st.info("لا يوجد لاعبون مسجلون")
        else:
            st.subheader("تسجيل الحضور والغياب (اختيار متعدد)")
            selected_players = st.multiselect("اختر اللاعبين", players)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ تسجيل حضور للمختارين"):
                    for p in selected_players:
                        record_attendance(p, "Present", st.session_state["username"])
                    st.success("تم تسجيل الحضور بنجاح")
                    st.rerun()
            with col2:
                if st.button("❌ تسجيل غياب للمختارين"):
                    for p in selected_players:
                        record_attendance(p, "Absent", st.session_state["username"])
                    st.success("تم تسجيل الغياب بنجاح")
                    st.rerun()
            
            st.subheader("حضور اليوم")
            today = date.today().isoformat()
            att = load_sheet("Attendance")
            if not att.empty:
                today_att = att[att["date"] == today]
                if not today_att.empty:
                    st.dataframe(today_att[["player_name", "status"]])
                else:
                    st.info("لم يتم تسجيل أي حضور/غياب اليوم")
    
    # ---------- تبويب الاشتراكات والدفعات ----------
    with tab2:
        players = get_players_list()
        if players:
            selected_player = st.selectbox("اختر لاعباً", players, key="sub_player")
            sub = get_player_subscription(selected_player)
            st.subheader("بيانات الاشتراك")
            with st.form("edit_subscription"):
                monthly_fee = st.number_input("القيمة الشهرية (جنيه)", value=float(sub["monthly_fee"]) if sub else 100.0, step=10.0)
                start_date = st.date_input("تاريخ البدء", value=datetime.strptime(sub["start_date"], "%Y-%m-%d").date() if sub and "start_date" in sub else date.today())
                end_date = st.date_input("تاريخ الانتهاء", value=datetime.strptime(sub["end_date"], "%Y-%m-%d").date() if sub and "end_date" in sub else date.today())
                status = st.selectbox("حالة الاشتراك", ["فعال", "منتهي", "ملغي"], index=0 if not sub or sub.get("subscription_status")=="فعال" else 1)
                if st.form_submit_button("تحديث الاشتراك"):
                    update_subscription(selected_player, monthly_fee, start_date.isoformat(), end_date.isoformat(), status)
                    st.success("تم تحديث الاشتراك")
                    st.rerun()
            
            st.subheader("تسجيل دفعة جديدة")
            with st.form("add_payment"):
                amount = st.number_input("المبلغ", min_value=0.0, step=10.0)
                method = st.selectbox("طريقة الدفع", ["Cash", "InstaPay", "Vodafone Cash", "Bank Transfer", "Other"])
                notes = st.text_area("ملاحظات")
                if st.form_submit_button("إضافة دفعة"):
                    add_payment(selected_player, amount, method, notes)
                    st.success("تم تسجيل الدفعة")
                    st.rerun()
            
            st.subheader("سجل الدفعات")
            payments = get_player_payments(selected_player)
            if not payments.empty:
                st.dataframe(payments[["amount", "payment_method", "payment_date", "notes"]])
            else:
                st.info("لا توجد دفعات مسجلة")
    
    # ---------- تبويب إدارة اللاعبين ----------
    with tab3:
        st.subheader("إضافة لاعب جديد")
        with st.form("add_player"):
            new_username = st.text_input("الاسم الثلاثي")
            new_password = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("إضافة لاعب"):
                if not is_three_part_name(new_username):
                    st.error("الاسم يجب أن يكون ثلاثياً")
                else:
                    users = load_sheet("Users")
                    if new_username in users["username"].values:
                        st.error("اسم المستخدم موجود مسبقاً")
                    else:
                        new_row = pd.DataFrame([{
                            "username": new_username,
                            "password": new_password,
                            "role": "player"
                        }])
                        users = pd.concat([users, new_row], ignore_index=True)
                        save_sheet("Users", users)
                        st.success("تمت إضافة اللاعب")
                        st.rerun()
        
        st.subheader("قائمة اللاعبين")
        users = load_sheet("Users")
        players_list = users[users["role"] == "player"]
        if not players_list.empty:
            st.dataframe(players_list[["username"]])
    
    # ---------- تبويب الإحصائيات ----------
    with tab4:
        st.subheader("إحصائيات الغياب والحضور")
        players = get_players_list()
        if players:
            stats = []
            for p in players:
                percent = get_attendance_percentage(p)
                att = load_sheet("Attendance")
                player_att = att[att["player_name"] == p]
                absent_count = len(player_att[player_att["status"] == "Absent"])
                stats.append({"اللاعب": p, "نسبة الحضور %": round(percent, 1), "عدد مرات الغياب": absent_count})
            st.dataframe(pd.DataFrame(stats))

def player_dashboard():
    player_name = st.session_state["username"]
    st.title(f"⚽ مرحباً {player_name}")
    st.sidebar.markdown(f"**اللاعب: {player_name}**")
    if st.sidebar.button("🚪 تسجيل خروج"):
        logout()
    
    # عرض الإحصائيات الشخصية
    col1, col2 = st.columns(2)
    with col1:
        percent = get_attendance_percentage(player_name)
        st.metric("نسبة الحضور", f"{percent:.1f}%")
    with col2:
        paid = get_total_paid(player_name)
        remaining = calculate_remaining(player_name)
        st.metric("إجمالي المدفوع", f"{paid:.2f} جنيه")
        st.metric("المتبقي", f"{remaining:.2f} جنيه")
    
    # الاشتراك الحالي
    sub = get_player_subscription(player_name)
    if sub:
        st.subheader("الاشتراك الحالي")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**القيمة الشهرية:** {sub['monthly_fee']} جنيه")
            st.write(f"**الحالة:** {sub['subscription_status']}")
        with col_b:
            st.write(f"**من:** {sub['start_date']}")
            st.write(f"**إلى:** {sub['end_date']}")
    else:
        st.warning("لا يوجد اشتراك مسجل لهذا اللاعب")
    
    # سجل الحضور والغياب
    st.subheader("سجل الحضور والغياب")
    att = load_sheet("Attendance")
    if not att.empty:
        player_att = att[att["player_name"] == player_name][["date", "status"]].sort_values("date", ascending=False)
        st.dataframe(player_att)
    else:
        st.info("لا توجد سجلات حضور")
    
    # سجل المدفوعات
    st.subheader("سجل المدفوعات")
    payments = get_player_payments(player_name)
    if not payments.empty:
        st.dataframe(payments[["amount", "payment_method", "payment_date", "notes"]])
    else:
        st.info("لا توجد مدفوعات مسجلة")

def logout():
    for key in ["logged_in", "username", "role"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ========== تشغيل التطبيق ==========
def main():
    if "logged_in" not in st.session_state:
        login_page()
    else:
        if st.session_state["role"] == "coach":
            coach_dashboard()
        elif st.session_state["role"] == "player":
            player_dashboard()
        else:
            st.error("دور غير معروف")
            logout()

if __name__ == "__main__":
    main()
