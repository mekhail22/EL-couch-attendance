import streamlit as st
from sheets_manager import SheetsManager
from auth import init_session_state, login, logout, is_logged_in, get_current_role
from coach_dashboard import show_coach_dashboard
from player_dashboard import show_player_dashboard

# إعداد الصفحة
st.set_page_config(
    page_title="الكوتش أكاديمي - نظام إدارة الأكاديمية",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="auto"
)

# تهيئة الجلسة
init_session_state()

# تهيئة مدير Google Sheets
# يجب وضع ملف service_account.json في نفس المجلد
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_NAME = "الكوتش أكاديمي"

@st.cache_resource
def init_sheets():
    """تهيئة اتصال Google Sheets (يتم مرة واحدة)"""
    mgr = SheetsManager(SERVICE_ACCOUNT_FILE)
    mgr.setup_spreadsheet(SPREADSHEET_NAME)
    # إضافة مستخدم coach افتراضي إذا لم يكن موجوداً
    if not mgr.username_exists("كابتن الأكاديمية"):
        mgr.add_user("كابتن الأكاديمية", "coach123", "coach")
    return mgr

# تحميل مدير الشيتات
try:
    sheets_mgr = init_sheets()
except Exception as e:
    st.error(f"حدث خطأ في الاتصال بـ Google Sheets: {e}")
    st.info("تأكد من وجود ملف service_account.json في المسار الصحيح ومن مشاركة الجدول مع البريد الإلكتروني لحساب الخدمة.")
    st.stop()

# شريط جانبي (Sidebar)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/35/35290.png", width=80)  # شعار مؤقت
    st.title("⚽ الكوتش أكاديمي")
    
    if is_logged_in():
        st.write(f"مرحباً: **{st.session_state.username}**")
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout()
            st.rerun()
    else:
        st.subheader("تسجيل الدخول")

# المحتوى الرئيسي
if not is_logged_in():
    # صفحة تسجيل الدخول
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 دخول إلى النظام")
        username = st.text_input("اسم المستخدم (الاسم الثلاثي)")
        password = st.text_input("كلمة المرور", type="password")
        
        if st.button("تسجيل الدخول", use_container_width=True):
            if not username or not password:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
            else:
                # التحقق من أن الاسم ثلاثي (اختياري، لكن قاعدة البيانات تمنع غير الثلاثي)
                from auth import validate_three_part_name
                if not validate_three_part_name(username):
                    st.warning("اسم المستخدم يجب أن يكون ثلاثياً (مثال: أحمد محمد علي)")
                else:
                    if login(username, password, sheets_mgr):
                        st.success("تم تسجيل الدخول بنجاح")
                        st.rerun()
                    else:
                        st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
        
        st.markdown("---")
        st.markdown("### 🧑‍🏫 دخول الكابتن")
        st.caption("اسم المستخدم: كابتن الأكاديمية\nكلمة المرور: coach123")
        st.markdown("### 🧑‍🎓 دخول لاعب تجريبي")
        st.caption("يمكنك تسجيل لاعب جديد من لوحة الكابتن بعد الدخول.")

else:
    # عرض اللوحة حسب الدور
    role = get_current_role()
    if role == "coach":
        show_coach_dashboard(sheets_mgr)
    elif role == "player":
        show_player_dashboard(sheets_mgr)
    else:
        st.error("دور غير معروف")
        logout()