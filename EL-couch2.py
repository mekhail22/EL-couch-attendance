"""
🏆 الكوتش أكاديمي - نظام إدارة الحضور والاشتراكات
برنامج كامل في ملف واحد
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import re
import json

# ============ إعدادات Streamlit ============
st.set_page_config(
    page_title="الكوتش أكاديمي",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# إخفاء عناصر Streamlit الافتراضية
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# CSS مخصص
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@200;300;400;500;600;700;800;900&display=swap');
    
    * {
        font-family: 'Cairo', sans-serif !important;
    }
    
    body {
        direction: rtl;
    }
    
    .stApp {
        direction: rtl;
    }
    
    [data-testid="stSidebar"] {
        background-color: #1e88e5;
        color: white;
    }
    
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1e88e5;
    }
    
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 1em;
        width: 100%;
    }
    
    .stSelectbox, .stTextInput, .stNumberInput {
        direction: rtl;
    }
    
    h1, h2, h3 {
        color: #1e88e5;
        text-align: right;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ============ إعدادات عامة ============
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"
CREDENTIALS_PATH = "credentials.json"

SHEET_USERS = "Users"
SHEET_ATTENDANCE = "Attendance"
SHEET_SUBSCRIPTIONS = "Subscriptions"
SHEET_PAYMENTS = "Payments"

PAYMENT_METHODS = ["💵 نقدي", "📱 InstaPay", "📱 Vodafone Cash", "🏦 تحويل بنكي", "📌 آخر"]

# ============ فئة إدارة البيانات ============
class GoogleSheetsManager:
    def __init__(self):
        try:
            SCOPES = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            self.credentials = Credentials.from_service_account_file(
                CREDENTIALS_PATH, 
                scopes=SCOPES
            )
            self.client = gspread.authorize(self.credentials)
            self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
        except Exception as e:
            st.error(f"❌ خطأ في الاتصال: {str(e)}")
            st.info("📌 تأكد من وضع credentials.json وتحديث SPREADSHEET_ID")
            st.stop()
    
    def get_sheet(self, sheet_name):
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except:
            return None
    
    def get_all_users(self):
        try:
            sheet = self.get_sheet(SHEET_USERS)
            return sheet.get_all_records() if sheet else []
        except:
            return []
    
    def user_exists(self, username):
        users = self.get_all_users()
        return any(user.get("username", "").strip() == username.strip() for user in users)
    
    def add_user(self, username, password, role):
        try:
            sheet = self.get_sheet(SHEET_USERS)
            if sheet:
                sheet.append_row([username, password, role])
                return True
        except:
            pass
        return False
    
    def verify_user(self, username, password):
        users = self.get_all_users()
        for user in users:
            if (user.get("username", "").strip() == username.strip() and 
                user.get("password", "") == password):
                return user
        return None
    
    def get_user_role(self, username):
        users = self.get_all_users()
        for user in users:
            if user.get("username", "").strip() == username.strip():
                return user.get("role", "player")
        return None
    
    # ====== الحضور ======
    def get_attendance_records(self, player_name=None):
        try:
            sheet = self.get_sheet(SHEET_ATTENDANCE)
            if not sheet:
                return []
            data = sheet.get_all_records()
            if player_name:
                data = [r for r in data if r.get("player_name", "").strip() == player_name.strip()]
            return data
        except:
            return []
    
    def add_attendance(self, player_name, date, status, recorded_by):
        try:
            sheet = self.get_sheet(SHEET_ATTENDANCE)
            if sheet:
                sheet.append_row([player_name, date, status, recorded_by])
                return True
        except:
            pass
        return False
    
    def add_multiple_attendance(self, players_list, date, status, recorded_by):
        try:
            sheet = self.get_sheet(SHEET_ATTENDANCE)
            if not sheet:
                return False, 0
            success_count = 0
            for player in players_list:
                try:
                    sheet.append_row([player, date, status, recorded_by])
                    success_count += 1
                except:
                    pass
            return True, success_count
        except:
            return False, 0
    
    def calculate_attendance_rate(self, player_name):
        records = self.get_attendance_records(player_name)
        if not records:
            return 0
        present = sum(1 for r in records if r.get("status", "").strip() == "حاضر ✓")
        total = len(records)
        return round((present / total) * 100, 2) if total > 0 else 0
    
    # ====== الاشتراكات ======
    def get_subscriptions(self, player_name=None):
        try:
            sheet = self.get_sheet(SHEET_SUBSCRIPTIONS)
            if not sheet:
                return []
            data = sheet.get_all_records()
            if player_name:
                data = [r for r in data if r.get("player_name", "").strip() == player_name.strip()]
            return data
        except:
            return []
    
    def get_player_subscription(self, player_name):
        subs = self.get_subscriptions(player_name)
        return subs[-1] if subs else None
    
    def add_subscription(self, player_name, monthly_fee, start_date, end_date, status="نشط"):
        try:
            sheet = self.get_sheet(SHEET_SUBSCRIPTIONS)
            if sheet:
                sheet.append_row([player_name, monthly_fee, start_date, end_date, status])
                return True
        except:
            pass
        return False
    
    def update_subscription(self, player_name, monthly_fee, end_date, status):
        try:
            sheet = self.get_sheet(SHEET_SUBSCRIPTIONS)
            if not sheet:
                return False
            all_data = sheet.get_all_records()
            for idx, record in enumerate(all_data, start=2):
                if record.get("player_name", "").strip() == player_name.strip():
                    sheet.update_cell(idx, 2, monthly_fee)
                    sheet.update_cell(idx, 4, end_date)
                    sheet.update_cell(idx, 5, status)
                    return True
        except:
            pass
        return False
    
    # ====== المدفوعات ======
    def get_payments(self, player_name=None):
        try:
            sheet = self.get_sheet(SHEET_PAYMENTS)
            if not sheet:
                return []
            data = sheet.get_all_records()
            if player_name:
                data = [r for r in data if r.get("player_name", "").strip() == player_name.strip()]
            return data
        except:
            return []
    
    def add_payment(self, player_name, amount, payment_method, payment_date, notes=""):
        try:
            sheet = self.get_sheet(SHEET_PAYMENTS)
            if sheet:
                sheet.append_row([player_name, amount, payment_method, payment_date, notes])
                return True
        except:
            pass
        return False
    
    def calculate_total_paid(self, player_name):
        payments = self.get_payments(player_name)
        total = 0
        for payment in payments:
            try:
                amount = float(str(payment.get("amount", 0)).replace(",", ""))
                total += amount
            except:
                pass
        return total
    
    def calculate_remaining(self, player_name):
        subscription = self.get_player_subscription(player_name)
        if not subscription:
            return 0
        try:
            fee = float(str(subscription.get("monthly_fee", 0)).replace(",", ""))
            paid = self.calculate_total_paid(player_name)
            remaining = fee - paid
            return max(0, remaining)
        except:
            return 0

# ============ دوال المصادقة ============
def validate_trilateral_name(name):
    """التحقق من الاسم الثلاثي"""
    name = name.strip()
    if not re.match(r'^[\u0621-\u064Aa-zA-Z\s]+$', name):
        return False
    words = name.split()
    if len(words) != 3:
        return False
    for word in words:
        if len(word) < 2:
            return False
    return True

def validate_password(password):
    """التحقق من قوة كلمة المرور"""
    if len(password) < 6:
        return False, "🔐 كلمة المرور يجب أن تكون 6 أحرف على الأقل"
    return True, "✅ كلمة المرور قوية"

@st.cache_resource
def get_gs_manager():
    return GoogleSheetsManager()

# ============ الصفحة الرئيسية ============
def main():
    # تهيئة الجلسة
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
    
    # إذا لم يكن مسجلاً
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

# ============ صفحة تسجيل الدخول ============
def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #1E88E5;'>🏆 الكوتش أكاديمي</h1>", 
                   unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #666;'>نظام إدارة الحضور والاشتراكات</h3>", 
                   unsafe_allow_html=True)
        
        st.markdown("---")
        
        login_type = st.radio(
            "**نوع الدخول:**",
            ["🎯 تسجيل دخول", "📝 إنشاء حساب جديد"],
            horizontal=True
        )
        
        st.markdown("---")
        
        if login_type == "🎯 تسجيل دخول":
            handle_login()
        else:
            handle_registration()

def handle_login():
    gs = get_gs_manager()
    
    username = st.text_input("**الاسم الثلاثي**", placeholder="مثال: أحمد محمد علي")
    password = st.text_input("**كلمة المرور**", type="password", placeholder="أدخل كلمة المرور")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🔓 دخول", use_container_width=True, type="primary"):
            if not username or not password:
                st.error("⚠️ يجب إدخال الاسم وكلمة المرور")
                return
            
            if not validate_trilateral_name(username):
                st.error("❌ الاسم يجب أن يكون ثلاثياً (مثال: أحمد محمد علي)")
                return
            
            user = gs.verify_user(username, password)
            
            if user:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_role = user.get("role", "player")
                st.success("✅ تم تسجيل الدخول بنجاح")
                st.balloons()
                st.rerun()
            else:
                st.error("❌ بيانات الدخول غير صحيحة")

def handle_registration():
    gs = get_gs_manager()
    
    st.info("📝 املأ البيانات التالية لإنشاء حساب جديد")
    
    username = st.text_input("**الاسم الثلاثي**", placeholder="مثال: أحمد محمد علي")
    password = st.text_input("**كلمة المرور**", type="password", placeholder="6 أحرف على الأقل")
    password_confirm = st.text_input("**تأكيد كلمة المرور**", type="password")
    role = st.selectbox("**نوع الحساب**", ["لاعب 👤", "كابتن 🎯"], index=0)
    
    role_value = "player" if role.startswith("لاعب") else "coach"
    
    if st.button("✅ إنشاء الحساب", use_container_width=True, type="primary"):
        if not username or not password:
            st.error("⚠️ يجب إدخال جميع البيانات")
            return
        
        if password != password_confirm:
            st.error("❌ كلمات المرور غير متطابقة")
            return
        
        if not validate_trilateral_name(username):
            st.error("❌ الاسم يجب أن يكون ثلاثياً (مثال: أحمد محمد علي)")
            st.info("💡 مثال: أحمد محمد علي (ثلاث كلمات منفصلة)")
            return
        
        is_valid, msg = validate_password(password)
        if not is_valid:
            st.error(f"❌ {msg}")
            return
        
        if gs.user_exists(username):
            st.error("⚠️ اسم المستخدم موجود بالفعل")
            return
        
        if gs.add_user(username, password, role_value):
            st.success("✅ تم إنشاء الحساب بنجاح!")
            st.info("👈 الآن يمكنك تسجيل الدخول")
            st.rerun()
        else:
            st.error("❌ حدث خطأ أثناء إنشاء الحساب")

# ============ التطبيق الرئيسي ============
def show_main_app():
    gs = get_gs_manager()
    
    # القائمة الجانبية
    with st.sidebar:
        st.markdown(f"<h3 style='color: white;'>👤 {st.session_state.username}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: white;'>🎯 {st.session_state.user_role}</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        if st.session_state.user_role == "coach":
            menu = st.radio(
                "**القائمة الرئيسية:**",
                ["📋 الحضور", "💳 الاشتراكات والمدفوعات", "📊 الإحصائيات", "⚙️ الإعدادات"],
                index=0
            )
        else:
            menu = st.radio(
                "**قائمتي:**",
                ["📋 سجلي", "📊 إحصائياتي", "💳 اشتراكي"],
                index=0
            )
        
        st.markdown("---")
        if st.button("🚪 خروج", use_container_width=True, type="secondary"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.success("👋 تم تسجيل الخروج")
            st.rerun()
    
    # المحتوى حسب الدور والقائمة
    if st.session_state.user_role == "coach":
        if menu == "📋 الحضور":
            coach_attendance(gs)
        elif menu == "💳 الاشتراكات والمدفوعات":
            coach_subscriptions_payments(gs)
        elif menu == "📊 الإحصائيات":
            coach_statistics(gs)
        elif menu == "⚙️ الإعدادات":
            coach_settings(gs)
    else:
        if menu == "📋 سجلي":
            player_attendance(gs)
        elif menu == "📊 إحصائياتي":
            player_statistics(gs)
        elif menu == "💳 اشتراكي":
            player_subscription(gs)

# ============ صفحات الكابتن ============
def coach_attendance(gs):
    st.markdown("# 📋 تسجيل الحضور والغياب")
    
    all_users = gs.get_all_users()
    players = [user["username"] for user in all_users if user.get("role") == "player"]
    
    if not players:
        st.warning("⚠️ لا توجد لاعبين مسجلين بعد")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        date = st.date_input("📅 التاريخ", value=datetime.now())
    
    with col2:
        status = st.selectbox("✓/✗ الحالة", ["حاضر ✓", "غائب ✗"])
    
    st.markdown("---")
    st.markdown("**🎯 اختر اللاعبين (Multi-Select):**")
    
    selected_players = st.multiselect("اختر من القائمة:", players, key="attendance_select")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("✅ تسجيل", use_container_width=True, type="primary"):
            if not selected_players:
                st.error("⚠️ اختر لاعب واحد على الأقل")
            else:
                success, count = gs.add_multiple_attendance(
                    selected_players,
                    str(date),
                    status,
                    st.session_state.username
                )
                
                if success:
                    st.success(f"✅ تم تسجيل حضور {count} لاعب")
                    st.balloons()
                else:
                    st.error("❌ حدث خطأ في التسجيل")
    
    st.markdown("---")
    st.markdown("### 📊 آخر التسجيلات")
    
    attendance_records = gs.get_attendance_records()
    
    if attendance_records:
        df = pd.DataFrame(attendance_records).tail(20)
        st.dataframe(
            df,
            use_container_width=True,
            height=300,
            column_config={
                "player_name": st.column_config.TextColumn("👤 اسم اللاعب"),
                "date": st.column_config.TextColumn("📅 التاريخ"),
                "status": st.column_config.TextColumn("📊 الحالة"),
                "recorded_by": st.column_config.TextColumn("📝 مسجل من"),
            }
        )
    else:
        st.info("لا توجد سجلات حضور بعد")

def coach_subscriptions_payments(gs):
    st.markdown("# 💳 الاشتراكات والمدفوعات")
    
    all_users = gs.get_all_users()
    players = [user["username"] for user in all_users if user.get("role") == "player"]
    
    if not players:
        st.warning("⚠️ لا توجد لاعبين مسجلين بعد")
        return
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### ➕ إضافة اشتراك جديد")
        
        player1 = st.selectbox("👤 اختر لاعب:", players, key="new_sub")
        monthly_fee = st.number_input("💰 الرسم الشهري:", min_value=0, value=100, key="fee1")
        start_date = st.date_input("📅 تاريخ البداية:", key="start1")
        end_date = st.date_input("📅 تاريخ النهاية:", key="end1")
        
        if st.button("✅ إضافة اشتراك", use_container_width=True, type="primary"):
            if monthly_fee <= 0:
                st.error("⚠️ الرسم يجب أن يكون أكبر من 0")
            elif start_date > end_date:
                st.error("⚠️ تاريخ البداية يجب أن يكون قبل تاريخ النهاية")
            else:
                if gs.add_subscription(player1, monthly_fee, str(start_date), str(end_date)):
                    st.success(f"✅ تم إضافة اشتراك {player1}")
                    st.rerun()
                else:
                    st.error("❌ حدث خطأ")
    
    with col2:
        st.markdown("#### 💵 تسجيل دفعة")
        
        player2 = st.selectbox("👤 اختر لاعب:", players, key="payment")
        amount = st.number_input("💰 المبلغ:", min_value=0, value=100, key="amount")
        payment_method = st.selectbox("💳 طريقة الدفع:", PAYMENT_METHODS)
        payment_date = st.date_input("📅 تاريخ الدفع:", key="date")
        notes = st.text_area("📝 ملاحظات:", height=60, key="notes")
        
        if st.button("✅ تسجيل دفعة", use_container_width=True, type="primary"):
            if amount <= 0:
                st.error("⚠️ المبلغ يجب أن يكون أكبر من 0")
            else:
                if gs.add_payment(player2, amount, payment_method, str(payment_date), notes):
                    st.success(f"✅ تم تسجيل دفعة {player2}")
                    st.rerun()
                else:
                    st.error("❌ حدث خطأ")
    
    st.markdown("---")
    st.markdown("#### 📊 جدول الاشتراكات والمدفوعات")
    
    selected_player = st.selectbox("اختر لاعب لعرض التفاصيل:", players, key="view_player")
    
    if selected_player:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**📋 بيانات الاشتراك:**")
            subscription = gs.get_player_subscription(selected_player)
            
            if subscription:
                sub_df = pd.DataFrame([subscription])
                st.dataframe(
                    sub_df,
                    use_container_width=True,
                    column_config={
                        "player_name": "👤 اللاعب",
                        "monthly_fee": "💰 الرسم الشهري",
                        "start_date": "📅 البداية",
                        "end_date": "📅 النهاية",
                        "subscription_status": "📊 الحالة"
                    }
                )
                
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    st.metric("💰 المدفوع", f"{gs.calculate_total_paid(selected_player):.2f}")
                with col_b:
                    st.metric("📊 المتبقي", f"{gs.calculate_remaining(selected_player):.2f}")
            else:
                st.info("لا يوجد اشتراك لهذا اللاعب")
        
        with col2:
            st.markdown("**💳 سجل المدفوعات:**")
            payments = gs.get_payments(selected_player)
            
            if payments:
                payment_df = pd.DataFrame(payments)
                st.dataframe(
                    payment_df,
                    use_container_width=True,
                    column_config={
                        "player_name": "👤 اللاعب",
                        "amount": "💰 المبلغ",
                        "payment_method": "💳 الطريقة",
                        "payment_date": "📅 التاريخ",
                        "notes": "📝 ملاحظات"
                    }
                )
            else:
                st.info("لا توجد مدفوعات")

def coach_statistics(gs):
    st.markdown("# 📊 الإحصائيات")
    
    all_users = gs.get_all_users()
    players = [user["username"] for user in all_users if user.get("role") == "player"]
    
    if not players:
        st.warning("⚠️ لا توجد لاعبين مسجلين بعد")
        return
    
    selected_players = st.multiselect(
        "اختر اللاعبين لعرض إحصائياتهم:",
        players,
        default=players[:5] if len(players) > 5 else players
    )
    
    if selected_players:
        st.markdown("---")
        
        stats_data = []
        
        for player in selected_players:
            attendance_records = gs.get_attendance_records(player)
            
            if attendance_records:
                present = sum(1 for r in attendance_records if r.get("status") == "حاضر ✓")
                absent = sum(1 for r in attendance_records if r.get("status") == "غائب ✗")
                total = len(attendance_records)
                rate = round((present / total) * 100, 1) if total > 0 else 0
                
                stats_data.append({
                    "👤 اسم اللاعب": player,
                    "✓ حاضر": present,
                    "✗ غائب": absent,
                    "📊 إجمالي": total,
                    "📈 نسبة الحضور %": f"{rate}%"
                })
        
        if stats_data:
            df = pd.DataFrame(stats_data)
            st.dataframe(df, use_container_width=True, height=400)
            
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 تحميل الإحصائيات (CSV)",
                data=csv,
                file_name=f"statistics_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

def coach_settings(gs):
    st.markdown("# ⚙️ الإعدادات والمعلومات")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 👥 معلومات الحساب")
        st.info(f"""
        **👤 اسم المستخدم:** {st.session_state.username}
        **🎯 الدور:** كابتن
        **⏰ وقت الدخول:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """)
    
    with col2:
        st.markdown("#### 📊 إحصائيات عامة")
        
        all_users = gs.get_all_users()
        players_count = sum(1 for u in all_users if u.get("role") == "player")
        coaches_count = sum(1 for u in all_users if u.get("role") == "coach")
        
        st.metric("👤 عدد اللاعبين", players_count)
        st.metric("🎯 عدد الكابتنين", coaches_count)

# ============ صفحات اللاعب ============
def player_attendance(gs):
    st.markdown("# 📋 سجل الحضور والغياب")
    
    attendance_records = gs.get_attendance_records(st.session_state.username)
    
    if not attendance_records:
        st.info("لا توجد سجلات حضور بعد")
        return
    
    df = pd.DataFrame(attendance_records)
    
    try:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=False)
    except:
        pass
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.dataframe(
            df[['date', 'status', 'recorded_by']],
            use_container_width=True,
            height=400,
            column_config={
                "date": st.column_config.TextColumn("📅 التاريخ"),
                "status": st.column_config.TextColumn("📊 الحالة"),
                "recorded_by": st.column_config.TextColumn("📝 مسجل من"),
            }
        )
    
    with col2:
        st.markdown("**📊 ملخص سريع:**")
        
        present = sum(1 for r in attendance_records if r.get("status") == "حاضر ✓")
        absent = sum(1 for r in attendance_records if r.get("status") == "غائب ✗")
        total = len(attendance_records)
        
        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.metric("✓ حاضر", present)
        with col_b:
            st.metric("✗ غائب", absent)
        
        st.metric("📊 إجمالي", total)

def player_statistics(gs):
    st.markdown("# 📊 إحصائيات الحضور")
    
    attendance_records = gs.get_attendance_records(st.session_state.username)
    
    if not attendance_records:
        st.info("لا توجد سجلات حضور بعد")
        return
    
    present = sum(1 for r in attendance_records if r.get("status") == "حاضر ✓")
    absent = sum(1 for r in attendance_records if r.get("status") == "غائب ✗")
    total = len(attendance_records)
    attendance_rate = gs.calculate_attendance_rate(st.session_state.username)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("✓ حاضر", f"{present}")
    
    with col2:
        st.metric("✗ غائب", f"{absent}")
    
    with col3:
        st.metric("📊 إجمالي", f"{total}")
    
    with col4:
        if attendance_rate >= 80:
            color = "🟢"
        elif attendance_rate >= 60:
            color = "🟡"
        else:
            color = "🔴"
        st.metric("📈 النسبة", f"{color} {attendance_rate}%")
    
    st.markdown("---")
    
    chart_data = pd.DataFrame({
        'الحالة': ['حاضر ✓', 'غائب ✗'],
        'عدد الجلسات': [present, absent]
    })
    
    st.bar_chart(chart_data.set_index('الحالة'))
    
    st.markdown("---")
    st.markdown("### 🎯 تقييمك:")
    
    if attendance_rate >= 90:
        st.success("🌟 ممتاز! حضورك رائع جداً")
    elif attendance_rate >= 80:
        st.info("👍 جيد جداً! استمر على هذا النحو")
    elif attendance_rate >= 60:
        st.warning("⚠️ متوسط، حاول تحسين حضورك")
    else:
        st.error("❌ حضورك منخفض جداً، يرجى التحسن")

def player_subscription(gs):
    st.markdown("# 💳 الاشتراك والمدفوعات")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📋 بيانات الاشتراك الحالي")
        
        subscription = gs.get_player_subscription(st.session_state.username)
        
        if subscription:
            st.success("✅ لديك اشتراك نشط")
            
            sub_info = f"""
            **💰 الرسم الشهري:** {subscription.get('monthly_fee')} ج.م
            **📅 تاريخ البداية:** {subscription.get('start_date')}
            **📅 تاريخ النهاية:** {subscription.get('end_date')}
            **📊 الحالة:** {subscription.get('subscription_status')}
            """
            
            st.info(sub_info)
        else:
            st.warning("⚠️ لا يوجد اشتراك نشط حالياً")
    
    with col2:
        st.markdown("#### 💵 الملخص المالي")
        
        total_paid = gs.calculate_total_paid(st.session_state.username)
        remaining = gs.calculate_remaining(st.session_state.username)
        
        col_a, col_b = st.columns([1, 1])
        
        with col_a:
            st.metric("💰 المدفوع", f"{total_paid:.2f}")
        
        with col_b:
            if remaining <= 0:
                st.metric("✅ المتبقي", "مدفوع ✓")
            else:
                st.metric("📊 المتبقي", f"{remaining:.2f}")
    
    st.markdown("---")
    st.markdown("#### 💳 سجل المدفوعات")
    
    payments = gs.get_payments(st.session_state.username)
    
    if payments:
        payment_df = pd.DataFrame(payments)
        
        try:
            payment_df['payment_date'] = pd.to_datetime(payment_df['payment_date'])
            payment_df = payment_df.sort_values('payment_date', ascending=False)
        except:
            pass
        
        st.dataframe(
            payment_df[['amount', 'payment_method', 'payment_date', 'notes']],
            use_container_width=True,
            height=300,
            column_config={
                "amount": st.column_config.NumberColumn("💰 المبلغ"),
                "payment_method": st.column_config.TextColumn("💳 الطريقة"),
                "payment_date": st.column_config.TextColumn("📅 التاريخ"),
                "notes": st.column_config.TextColumn("📝 ملاحظات"),
            }
        )
    else:
        st.info("لا توجد مدفوعات مسجلة بعد")

# ============ تشغيل التطبيق ============
if __name__ == "__main__":
    main()
