# =========================
# 📌 EoHealth Egypt App (Fixed Version)
# د. سها ناصر — الكارت الموحد للطفل
# =========================

import streamlit as st
import pandas as pd
import qrcode
from io import BytesIO
import sqlite3                  # ✅ قاعدة البيانات
from datetime import datetime, date
from pathlib import Path
import io, base64
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# =======================
# 🧠 الإعدادات الأساسية
# =======================

# 🗂️ إنشاء قاعدة البيانات ومجلد الملفات إن لم يكونا موجودين
DB_PATH = "eohealth.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# 🖋️ دالة لتحديد الخط المستخدم في الشهادات أو الصور
def choose_font(size=20):
    try:
        return ImageFont.truetype("Amiri-Regular.ttf", size)
    except:
        return ImageFont.load_default()

# ✅ اختبار الاتصال بقاعدة البيانات (إنشاء ملف القاعدة في أول تشغيل)
try:
    conn_test = sqlite3.connect(DB_PATH)
    conn_test.close()
except Exception as e:
    st.error(f"⚠️ خطأ في إنشاء قاعدة البيانات: {e}")

# ----------------------------
# واجهة المستخدم التجريبية
# ----------------------------
st.title("🧒 واجهة المستخدم - خدمات الكارت الموحد للطفل")

# الخطوة 1: إدخال أو رفع QR Code
st.subheader("🔍 مسح الكود أو إدخال رقم الكارت الذكي")
qr_code = st.text_input("أدخل رقم الكارت أو امسح QR Code:")

if qr_code:
    # الخطوة 2: عرض بيانات الطفل (افتراضية للتجريب)
    child_data = {
        "الاسم": "محمد أحمد علي",
        "تاريخ الميلاد": "2024-03-12",
        "الرقم القومي": "30210142301124",
        "المنطقة الصحية": "شمال الجيزة",
        "الحالة الصحية": "جيدة"
    }
    st.success("✅ تم قراءة بيانات الطفل بنجاح")
    st.table(pd.DataFrame([child_data]))

    # الخطوة 3: اختيار الخدمة
    st.subheader("🎯 اختر الخدمة المطلوبة:")
    service = st.selectbox(
        "الخدمات المتاحة:",
        ["اختيار...", "تسجيل مولود جديد", "حجز تطعيم", "حجز كشف طبي", "استخراج شهادة ميلاد", "شكاوى ومقترحات", "استفسار عن الخدمات"]
    )

    # الخطوة 4: النماذج التفاعلية
    if service == "تسجيل مولود جديد":
        st.text_input("اسم المولود")
        st.date_input("تاريخ الميلاد")
        st.file_uploader("تحميل شهادة الميلاد من المستشفى")
        if st.button("تأكيد التسجيل"):
            st.success("✅ تم تسجيل المولود بنجاح")

    elif service == "حجز تطعيم":
        vaccine = st.selectbox("اختيار نوع التطعيم:", ["الدرن", "شلل الأطفال", "الثلاثي", "الكبد"])
        date_pick = st.date_input("تاريخ الموعد المطلوب")
        if st.button("تأكيد الحجز"):
            st.success(f"💉 تم حجز تطعيم ({vaccine}) بتاريخ {date_pick}")

    elif service == "حجز كشف طبي":
        dept = st.selectbox("اختيار العيادة:", ["الأطفال", "الأسنان", "الأنف والأذن", "باطنة"])
        date_pick = st.date_input("تاريخ الموعد")
        if st.button("تأكيد الحجز"):
            st.success(f"🏥 تم حجز الكشف في عيادة {dept} بتاريخ {date_pick}")

    elif service == "استخراج شهادة ميلاد":
        st.text_input("الرقم القومي لولي الأمر")
        st.text_input("رقم ملف الطفل")
        if st.button("طلب استخراج الشهادة"):
            st.success("📜 تم تقديم الطلب بنجاح – رقم الطلب: #BIRTH-2025-001")

    elif service == "شكاوى ومقترحات":
        st.text_area("اكتب الشكوى أو المقترح")
        if st.button("إرسال"):
            st.success("📬 تم إرسال الشكوى بنجاح، وسيتم الرد خلال 48 ساعة")

    elif service == "استفسار عن الخدمات":
        st.write("""
        🍼 تسجيل مولود جديد  
        💉 حجز التطعيمات  
        🏥 الكشف الطبي  
        📜 استخراج الشهادات  
        💬 تقديم الشكاوى
        """)

else:
    st.info("📷 برجاء إدخال أو مسح كود الكارت الذكي لبدء الخدمة.")

# ====================================================
# 🗃️ قاعدة البيانات والتوابع الخاصة بها
# ====================================================

def get_conn():
    """إنشاء اتصال بقاعدة البيانات المحلية"""
    try:
        return sqlite3.connect(DB_PATH, check_same_thread=False)
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None


def init_db():
    """تهيئة الجداول الأساسية عند أول تشغيل"""
    conn = get_conn()
    if conn is None:
        return
    c = conn.cursor()

    # جدول الأطفال
    c.execute("""
    CREATE TABLE IF NOT EXISTS children (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        national_id TEXT,
        smart_id TEXT,
        birth_date TEXT,
        gender TEXT,
        mother_id TEXT,
        father_id TEXT,
        governorate TEXT,
        created_at TEXT
    )
    """)

    # جدول الملفات الطبية
    c.execute("""
    CREATE TABLE IF NOT EXISTS medical_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_id INTEGER,
        record_date TEXT,
        weight REAL,
        height REAL,
        bmi REAL,
        vaccinations TEXT,
        diagnoses TEXT,
        medications TEXT,
        notes TEXT,
        files TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()
    st.sidebar.success("✅ قاعدة البيانات جاهزة")  # رسالة جانبية للتأكيد

# 🚀 تشغيل التهيئة مرة واحدة عند بدء التطبيق
init_db()


# ====================================================
# ✳️ دوال مساعدة إضافية (QR + PDF + Arabic Text)
# ====================================================

def gen_smart_id(rec_id: int) -> str:
    """توليد رقم الهوية الذكية"""
    today = datetime.utcnow().strftime("%Y%m%d")
    return f"EOH-{today}-{rec_id:06d}"


def generate_qr_bytes(data_str: str) -> BytesIO:
    """توليد كود QR لبيانات الطفل"""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def make_download_link_bytes(data_bytes, filename, label="Download") -> str:
    """توليد رابط تحميل ملف (QR أو PDF)"""
    b64 = base64.b64encode(data_bytes).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href


def shape_arabic(text: str) -> str:
    """تحسين عرض النص العربي داخل الصور أو الـ PDF"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        return bidi_text
    except Exception:
        return text
# ====================================================
# 🗃️ Data Access Layer (SQLite + Streamlit Cache)
# ====================================================

@st.cache_data(show_spinner=False)
def fetch_children_df():
    """قراءة جميع الأطفال من قاعدة البيانات"""
    try:
        conn = get_conn()
        df = pd.read_sql_query("SELECT * FROM children ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"⚠️ خطأ في تحميل بيانات الأطفال: {e}")
        return pd.DataFrame()  # لو في خطأ يرجع جدول فاضي


@st.cache_data(show_spinner=False)
def fetch_medical_df(child_id: int):
    """قراءة الملف الطبي لطفل معين"""
    try:
        conn = get_conn()
        df = pd.read_sql_query(
            "SELECT * FROM medical_files WHERE child_id=? ORDER BY id DESC",
            conn, params=(child_id,)
        )
        conn.close()
        return df
    except Exception as e:
        st.error(f"⚠️ خطأ في قراءة السجلات الطبية: {e}")
        return pd.DataFrame()


def insert_child_record(rec: dict) -> int:
    """إضافة سجل جديد لطفل في جدول الأطفال"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO children 
            (full_name, national_id, smart_id, birth_date, gender, mother_id, father_id, governorate, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec["full_name"], rec["national_id"], rec["smart_id"], rec["birth_date"],
            rec["gender"], rec["mother_id"], rec["father_id"], rec["governorate"],
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        rec_id = c.lastrowid
        conn.close()
        fetch_children_df.clear()  # تحديث الكاش
        return rec_id
    except Exception as e:
        st.error(f"⚠️ لم يتم حفظ الطفل: {e}")
        return -1


def insert_medical(child_id: int, data: dict) -> int:
    """إضافة سجل طبي جديد لطفل"""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO medical_files
            (child_id, record_date, weight, height, bmi, vaccinations, diagnoses, medications, notes, files, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            child_id, data.get("record_date"), data.get("weight"), data.get("height"), data.get("bmi"),
            data.get("vaccinations", ""), data.get("diagnoses", ""), data.get("medications", ""),
            data.get("notes", ""), ",".join(data.get("files", [])), datetime.utcnow().isoformat()
        ))
        conn.commit()
        rec_id = c.lastrowid
        conn.close()
        fetch_medical_df.clear()  # تحديث الكاش
        return rec_id
    except Exception as e:
        st.error(f"⚠️ لم يتم حفظ السجل الطبي: {e}")
        return -1


def estimate_environmental_savings(total_records: int, papers_per_record=5):
    """تقدير عدد الأوراق وثاني أكسيد الكربون الذي تم توفيره"""
    sheets_saved = int(total_records * papers_per_record)
    paper_kg = sheets_saved * 0.0045
    co2_kg = paper_kg * 1.3
    return sheets_saved, round(paper_kg, 3), round(co2_kg, 3)


# ====================================================
# 📜 توليد شهادة الميلاد الرقمية (PDF + Arabic)
# ====================================================

def create_birth_certificate_image(child_rec: dict):
    """إنشاء صورة شهادة الميلاد بالعربية"""
    W, H = 1240, 1754  # حجم صفحة A4
    img = Image.new("RGB", (W, H), color="white")
    draw = ImageDraw.Draw(img)
    title_font = choose_font(40)
    header_font = choose_font(28)
    body_font = choose_font(20)

    # العنوان الرئيسي
    title_text = "Birth Certificate (Digital) — شهادة الميلاد الرقمية"
    draw.text((W // 2, 60), title_text, fill="black", anchor="ms", font=title_font)

    # البيانات
    lines = [
        ("اسم الطفل / Child Name:", child_rec.get("full_name", "")),
        ("الرقم القومي / National ID:", child_rec.get("national_id", "")),
        ("تاريخ الميلاد / Birth Date:", child_rec.get("birth_date", "")),
        ("النوع / Gender:", child_rec.get("gender", "")),
        ("المحافظة / Governorate:", child_rec.get("governorate", "")),
        ("الهوية الصحية الذكية / Smart Health ID:", child_rec.get("smart_id", "")),
    ]

    start_y = 160
    gap = 70
    for i, (label, value) in enumerate(lines):
        y = start_y + i * gap
        draw.text((60, y), label, fill="black", font=body_font)
        display_value = shape_arabic(value)
        draw.text((W - 60, y), display_value, fill="black", anchor="ra", font=body_font)

    # QR في الأسفل
    qr_buf = generate_qr_bytes(f"{child_rec.get('smart_id')}|{child_rec.get('national_id')}")
    qr_img = Image.open(qr_buf).convert("RGB").resize((220, 220))
    img.paste(qr_img, (60, H - 300))

    # تذييل الصفحة
    footer_text = "Issued by: EoHealth Egypt — Electronic Office for Health (Prototype)"
    draw.text((W // 2, H - 80), footer_text, fill="black", anchor="ms", font=header_font)

    return img


def create_birth_certificate_pdf(child_rec: dict, output_path: Path):
    """توليد ملف PDF من الشهادة"""
    img = create_birth_certificate_image(child_rec)
    img.save(output_path, "PDF", resolution=150)
    return output_path

# ====================================================
# 🩺 Health Record Page
# ====================================================
elif page == "Health Record":
    st.header(t("health_record"))
    df = fetch_children_df()

    if df.empty:
        st.info("No children yet." if st.session_state.lang == "en" else "لا يوجد أطفال بعد.")
    else:
        sid = st.number_input("Enter child ID / أدخل رقم الطفل", min_value=1, step=1)
        if st.button("Load Record / تحميل السجل"):
            try:
                conn = get_conn()
                rec = conn.cursor().execute("SELECT * FROM children WHERE id=?", (sid,)).fetchone()
                conn.close()
            except Exception as e:
                st.error(f"⚠️ Database error: {e}")
                rec = None

            if rec:
                st.subheader(f"{rec[1]} — Smart ID: {rec[3]}")
                st.write("Birth Date:", rec[4], "Governorate:", rec[8])

                med_df = fetch_medical_df(sid)
                if med_df.empty:
                    st.info("No medical records yet. Add one below." if st.session_state.lang == "en" else "لا توجد سجلات طبية بعد. أضف سجلًا جديدًا أدناه.")
                else:
                    st.subheader("Medical History / السجل الطبي")
                    st.dataframe(
                        med_df[["id", "record_date", "weight", "height", "bmi", "vaccinations", "diagnoses", "medications", "notes", "files"]],
                        height=250
                    )

                st.markdown("### ➕ Add / Upload Medical Record")
                with st.form("add_med", clear_on_submit=True):
                    rec_date = st.date_input("Record Date / تاريخ الفحص", value=date.today())
                    weight = st.number_input("Weight (kg) / الوزن (كجم)", min_value=0.0, format="%.1f")
                    height = st.number_input("Height (cm) / الطول (سم)", min_value=0.0, format="%.1f")
                    bmi = round(weight / ((height / 100) ** 2), 2) if (height and weight) else None
                    vaccinations = st.text_area("Vaccinations / التطعيمات (dates & notes)")
                    diagnoses = st.text_area("Diagnoses / التشخيصات")
                    medications = st.text_area("Medications / الأدوية")
                    notes = st.text_area("Notes / ملاحظات")
                    uploaded = st.file_uploader("Upload files (PDF / image) / رفع ملفات", accept_multiple_files=True)
                    submitted = st.form_submit_button("Save Medical Record / حفظ السجل")

                    if submitted:
                        try:
                            files_saved = []
                            for f in uploaded:
                                fname = f"{sid}_{int(datetime.utcnow().timestamp())}_{f.name}"
                                out_path = UPLOAD_DIR / fname
                                with open(out_path, "wb") as of:
                                    of.write(f.getbuffer())
                                files_saved.append(str(out_path))

                            data = {
                                "record_date": rec_date.isoformat(),
                                "weight": weight if weight > 0 else None,
                                "height": height if height > 0 else None,
                                "bmi": bmi,
                                "vaccinations": vaccinations,
                                "diagnoses": diagnoses,
                                "medications": medications,
                                "notes": notes,
                                "files": files_saved,
                            }
                            new_id = insert_medical(sid, data)
                            if new_id > 0:
                                st.success("✅ Medical record added successfully." if st.session_state.lang == "en" else "✅ تم حفظ السجل الطبي بنجاح.")
                            else:
                                st.warning("⚠️ لم يتم الحفظ.")
                        except Exception as e:
                            st.error(f"⚠️ خطأ أثناء حفظ الملف: {e}")


# ====================================================
# 🤖 AI Insights Page
# ====================================================
elif page == "AI Insights":
    st.header(t("ai_insights"))
    st.markdown(
        "This is a demo placeholder with rule-based checks; replace later with AI model."
        if st.session_state.lang == "en"
        else "هذا نموذج تجريبي للتحليل بناءً على قواعد بسيطة — يمكن استبداله بنموذج ذكاء اصطناعي لاحقاً."
    )

    df = fetch_children_df()
    if df.empty:
        st.info("No data yet." if st.session_state.lang == "en" else "لا توجد بيانات بعد.")
    else:
        st.subheader("Rule-based analysis / التحليل التجريبي")
        alerts = []
        for _, r in df.iterrows():
            try:
                child_id = r["id"]
                dob = r["birth_date"]
                age_days = (date.today() - date.fromisoformat(dob)).days
                med = fetch_medical_df(child_id)
                has_vacc = (not med.empty) and (med["vaccinations"].astype(str).str.len().sum() > 0)
                if age_days > 60 and not has_vacc:
                    alerts.append((child_id, r["full_name"], "Missing vaccinations / لم يتم تسجيل التطعيمات"))
            except Exception:
                continue

        if alerts:
            for a in alerts:
                st.warning(f"⚠️ ID {a[0]} — {a[1]}: {a[2]}")
        else:
            st.success("✅ No immediate issues detected." if st.session_state.lang == "en" else "✅ لا توجد تنبيهات في الوقت الحالي.")


# ====================================================
# 🌱 Eco Dashboard Page
# ====================================================
elif page == "Eco Dashboard":
    st.header(t("eco_dashboard"))
    total = fetch_children_df().shape[0]
    sheets, paper_kg, co2_kg = estimate_environmental_savings(total)
    st.metric("Registered children", total)
    st.metric("Paper sheets saved", sheets)
    st.metric("Paper mass saved (kg)", paper_kg)
    st.metric("CO₂ reduction (kg)", co2_kg)
    st.info("🌿 Each digital record saves ~5 sheets of paper on average.")


# ====================================================
# 🪪 Digital Health Card Page
# ====================================================
elif page == "Digital Card":
    st.header(t("digital_card"))
    sid = st.number_input("Enter child ID / أدخل رقم الطفل", min_value=1, step=1)

    if st.button("Load Digital Card / عرض البطاقة الصحية"):
        try:
            conn = get_conn()
            rec = conn.cursor().execute("SELECT * FROM children WHERE id=?", (sid,)).fetchone()
            conn.close()
        except Exception as e:
            st.error(f"⚠️ خطأ في قاعدة البيانات: {e}")
            rec = None

        if not rec:
            st.warning("Child not found / الطفل غير موجود")
        else:
            child = {
                "full_name": rec[1],
                "national_id": rec[2],
                "smart_id": rec[3],
                "birth_date": rec[4],
                "governorate": rec[8],
            }

            # QR Code
            qr_buf = generate_qr_bytes(f"{child['smart_id']}|{child['national_id']}")
            st.image(qr_buf)
            st.write("👶 Name:", child["full_name"])
            st.write("🆔 Smart ID:", child["smart_id"])
            st.write("🎂 Birth Date:", child["birth_date"])
            st.write("🏙️ Governorate:", child["governorate"])

            # تحميل شهادة الميلاد PDF
            pdf_path = UPLOAD_DIR / f"birth_certificate_{sid}.pdf"
            try:
                if not pdf_path.exists():
                    create_birth_certificate_pdf(child, pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.markdown(make_download_link_bytes(pdf_bytes, pdf_path.name, t("download_pdf")), unsafe_allow_html=True)
                st.success("📜 Digital birth certificate ready for download.")
            except Exception as e:
                st.error(f"⚠️ Error creating or loading PDF: {e}")

# ====================================================
# ⚙️ Admin Page
# ====================================================
elif page == "Admin":
    st.header(t("admin"))
    df = fetch_children_df()

    # عرض قاعدة البيانات الحالية
    if df.empty:
        st.info("No data available." if st.session_state.lang == "en" else "لا توجد بيانات حالياً.")
    else:
        st.subheader("📋 Children Table / جدول الأطفال")
        st.dataframe(df, height=300)

        # ---------------- Export CSV ----------------
        try:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.markdown(make_download_link_bytes(csv_bytes, "children.csv", "📥 Download CSV"), unsafe_allow_html=True)
        except Exception as e:
            st.error(f"⚠️ CSV export failed: {e}")

        # ---------------- Export Excel ----------------
        try:
            to_excel = io.BytesIO()
            with pd.ExcelWriter(to_excel, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="children")
            st.markdown(make_download_link_bytes(to_excel.getvalue(), "children.xlsx", t("export_excel")), unsafe_allow_html=True)
        except Exception as e:
            st.error(f"⚠️ Excel export failed: {e}")

    # ---------------- Clear Database ----------------
    st.markdown("---")
    if st.button("🗑️ Clear Demo Database / مسح قاعدة البيانات التجريبية"):
        if st.warning("⚠️ سيتم حذف جميع البيانات التجريبية نهائيًا. تأكد قبل المتابعة.") or True:
            try:
                conn = get_conn()
                c = conn.cursor()
                c.execute("DELETE FROM medical_files")
                c.execute("DELETE FROM children")
                conn.commit()
                conn.close()
                fetch_children_df.clear()
                fetch_medical_df.clear()
                st.success("✅ Demo DB cleared successfully." if st.session_state.lang == "en" else "✅ تم مسح قاعدة البيانات التجريبية بنجاح.")
            except Exception as e:
                st.error(f"⚠️ Error while clearing DB: {e}")

    # ---------------- Import Excel ----------------
    st.markdown("---")
    st.subheader("📤 Import Children from Excel / استيراد بيانات من ملف إكسل")
    uploaded_excel = st.file_uploader("Upload .xlsx file", type=["xlsx"])

    if uploaded_excel:
        try:
            df_in = pd.read_excel(uploaded_excel)
            expected_cols = ["full_name", "national_id", "birth_date", "gender", "mother_id", "father_id", "governorate"]
            missing = [c for c in expected_cols if c not in df_in.columns]
            if missing:
                st.error(f"❌ Missing columns: {', '.join(missing)}")
            else:
                inserted = 0
                for _, row in df_in.iterrows():
                    if pd.isna(row.get("full_name")) or pd.isna(row.get("national_id")):
                        continue
                    rec = {
                        "full_name": str(row.get("full_name")),
                        "national_id": str(row.get("national_id")),
                        "smart_id": "",
                        "birth_date": str(row.get("birth_date")) if not pd.isna(row.get("birth_date")) else date.today().isoformat(),
                        "gender": str(row.get("gender")) if not pd.isna(row.get("gender")) else "",
                        "mother_id": str(row.get("mother_id")) if not pd.isna(row.get("mother_id")) else "",
                        "father_id": str(row.get("father_id")) if not pd.isna(row.get("father_id")) else "",
                        "governorate": str(row.get("governorate")) if not pd.isna(row.get("governorate")) else "",
                    }
                    new_id = insert_child_record(rec)
                    conn = get_conn()
                    conn.cursor().execute("UPDATE children SET smart_id=? WHERE id=?", (gen_smart_id(new_id), new_id))
                    conn.commit()
                    conn.close()
                    inserted += 1
                fetch_children_df.clear()
                st.success(f"✅ Imported {inserted} records successfully." if st.session_state.lang == "en" else f"✅ تم استيراد {inserted} سجلات بنجاح.")
        except Exception as e:
            st.error("❌ Failed to import Excel file: " + str(e))

    # ---------------- Insert Demo Data ----------------
    st.markdown("---")
    st.subheader("📦 Insert Demo Data / إدخال بيانات تجريبية")
    if st.button("Insert 10 Demo Records / إدخال 10 سجلات تجريبية"):
        try:
            demo = [
                {"full_name": "أحمد علي", "national_id": "T10000001", "birth_date": "2024-01-10", "gender": "Male / ذكر", "mother_id": "M1001", "father_id": "F1001", "governorate": "Cairo"},
                {"full_name": "مريم حسن", "national_id": "T10000002", "birth_date": "2023-05-05", "gender": "Female / أنثى", "mother_id": "M1002", "father_id": "F1002", "governorate": "Giza"},
                {"full_name": "يوسف سعيد", "national_id": "T10000003", "birth_date": "2022-11-20", "gender": "Male / ذكر", "mother_id": "M1003", "father_id": "F1003", "governorate": "Alexandria"},
                {"full_name": "سارة محمد", "national_id": "T10000004", "birth_date": "2021-07-15", "gender": "Female / أنثى", "mother_id": "M1004", "father_id": "F1004", "governorate": "Cairo"},
                {"full_name": "آدم خالد", "national_id": "T10000005", "birth_date": "2020-03-02", "gender": "Male / ذكر", "mother_id": "M1005", "father_id": "F1005", "governorate": "Dakahliya"},
                {"full_name": "لين محمود", "national_id": "T10000006", "birth_date": "2019-08-12", "gender": "Female / أنثى", "mother_id": "M1006", "father_id": "F1006", "governorate": "Aswan"},
                {"full_name": "عمر نبيل", "national_id": "T10000007", "birth_date": "2018-12-01", "gender": "Male / ذكر", "mother_id": "M1007", "father_id": "F1007", "governorate": "Luxor"},
                {"full_name": "نور سامي", "national_id": "T10000008", "birth_date": "2017-02-25", "gender": "Female / أنثى", "mother_id": "M1008", "father_id": "F1008", "governorate": "Ismailia"},
                {"full_name": "ريان مصطفى", "national_id": "T10000009", "birth_date": "2016-09-09", "gender": "Male / ذكر", "mother_id": "M1009", "father_id": "F1009", "governorate": "Suez"},
                {"full_name": "هنا نبيل", "national_id": "T10000010", "birth_date": "2015-06-18", "gender": "Female / أنثى", "mother_id": "M1010", "father_id": "F1010", "governorate": "Gharbia"},
            ]
            inserted = 0
            for d in demo:
                new_id = insert_child_record({
                    "full_name": d["full_name"], "national_id": d["national_id"], "smart_id": "",
                    "birth_date": d["birth_date"], "gender": d["gender"], "mother_id": d["mother_id"],
                    "father_id": d["father_id"], "governorate": d["governorate"]
                })
                conn = get_conn()
                conn.cursor().execute("UPDATE children SET smart_id=? WHERE id=?", (gen_smart_id(new_id), new_id))
                conn.commit()
                conn.close()
                inserted += 1
            fetch_children_df.clear()
            st.success(f"✅ {inserted} demo records inserted successfully." if st.session_state.lang == "en" else f"✅ تم إدخال {inserted} سجلات تجريبية بنجاح.")
        except Exception as e:
            st.error(f"⚠️ Error inserting demo data: {e}")

# ------------- End of Application -------------
st.success("🎉 Application loaded successfully — EoHealth Egypt Prototype Ready!")
