# eohealth_app_main.py
# EoHealth Egypt - Prototype application (Streamlit)
# Updated: bilingual (AR/EN), RTL support, Arabic PDF certificate generation, demo data insertion,
# improved DB handling, caching, Digital Health Card, Excel import/export

import streamlit as st
import sqlite3, os, io, base64, sys
import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont
from datetime import date, datetime
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display

# ------------- Config -------------
st.set_page_config(page_title="EoHealth Egypt", layout="wide", initial_sidebar_state="expanded")
DB_PATH = "eohealth_main.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
FONTS_DIR = Path("fonts")
FONTS_DIR.mkdir(exist_ok=True)

# Try to find Amiri or fallback to DejaVuSans (cross-platform)
AMIRI_PATH = FONTS_DIR / "Amiri-Regular.ttf"
# common linux path
DEJAVU_LINUX = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
# common windows local fonts path fallback (user may place DejaVu here)
DEJAVU_WINDOWS = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts" / "DejaVuSans.ttf"
# if not found, set None
if DEJAVU_LINUX.exists():
    DEJAVU_PATH = DEJAVU_LINUX
elif DEJAVU_WINDOWS.exists():
    DEJAVU_PATH = DEJAVU_WINDOWS
else:
    DEJAVU_PATH = None

def choose_font(size=24):
    # Prefers Amiri if present, else DejaVu if available, else default pillow font
    try:
        if AMIRI_PATH.exists():
            return ImageFont.truetype(str(AMIRI_PATH), size=size)
        elif DEJAVU_PATH and Path(DEJAVU_PATH).exists():
            return ImageFont.truetype(str(DEJAVU_PATH), size=size)
        else:
            return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

# ------------- DB Utilities -------------
def get_conn():
    # Return a new connection (safer for concurrency in streamlit)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
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
    )""")
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
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------------- Utilities ----------------
def gen_smart_id(rec_id):
    today = datetime.utcnow().strftime("%Y%m%d")
    return f"EOH-{today}-{rec_id:06d}"

def generate_qr_bytes(data_str):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def make_download_link_bytes(data_bytes, filename, label="Download"):
    b64 = base64.b64encode(data_bytes).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# Arabic shaping helper
def shape_arabic(text):
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        return bidi_text
    except Exception:
        return text

# ---------------- Data access (with caching) ----------------
@st.cache_data
def fetch_children_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM children ORDER BY id DESC", conn)
    conn.close()
    return df

@st.cache_data
def fetch_medical_df(child_id):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM medical_files WHERE child_id=? ORDER BY id DESC", conn, params=(child_id,))
    conn.close()
    return df

def insert_child_record(rec):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    INSERT INTO children (full_name,national_id,smart_id,birth_date,gender,mother_id,father_id,governorate,created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        rec["full_name"], rec["national_id"], rec["smart_id"], rec["birth_date"],
        rec["gender"], rec["mother_id"], rec["father_id"], rec["governorate"],
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    rec_id = c.lastrowid
    conn.close()
    # clear cache so UI shows new data
    fetch_children_df.clear()
    return rec_id

def insert_medical(child_id, data):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    INSERT INTO medical_files
    (child_id, record_date, weight, height, bmi, vaccinations, diagnoses, medications, notes, files, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        child_id, data["record_date"], data.get("weight"), data.get("height"), data.get("bmi"),
        data.get("vaccinations",""), data.get("diagnoses",""), data.get("medications",""),
        data.get("notes",""), ",".join(data.get("files",[])), datetime.utcnow().isoformat()
    ))
    conn.commit()
    rec_id = c.lastrowid
    conn.close()
    fetch_medical_df.clear()
    return rec_id

def estimate_environmental_savings(total_records, papers_per_record=5):
    sheets_saved = int(total_records * papers_per_record)
    paper_kg = sheets_saved * 0.0045
    co2_kg = paper_kg * 1.3
    return sheets_saved, round(paper_kg,3), round(co2_kg,3)

# ---------------- PDF generation (Arabic) ----------------
def create_birth_certificate_image(child_rec):
    # Return PIL Image (A4-like) with Arabic support
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), color="white")
    draw = ImageDraw.Draw(img)
    title_font = choose_font(40)
    header_font = choose_font(28)
    body_font = choose_font(20)

    # Title (centered)
    title_en = "Birth Certificate (Digital) — شهادة الميلاد الرقمية"
    draw.text((W//2, 60), title_en, fill="black", anchor="ms", font=title_font)

    # Build Arabic lines (right aligned)
    lines = [
        ("اسم الطفل / Child Name:", child_rec.get("full_name","")),
        ("الرقم القومي / National ID:", child_rec.get("national_id","")),
        ("تاريخ الميلاد / Birth Date:", child_rec.get("birth_date","")),
        ("النوع / Gender:", child_rec.get("gender","")),
        ("المحافظة / Governorate:", child_rec.get("governorate","")),
        ("الهوية الصحية الذكية / Smart Health ID:", child_rec.get("smart_id",""))
    ]

    start_y = 160
    gap = 70
    for i, (label_en, value) in enumerate(lines):
        y = start_y + i*gap
        # left (English label)
        draw.text((60, y), label_en, fill="black", font=body_font)
        # right (Arabic / value)
        display_value = shape_arabic(value)
        draw.text((W-60, y), display_value, fill="black", anchor="ra", font=body_font)

    # QR at bottom-left
    qr_buf = generate_qr_bytes(f"{child_rec.get('smart_id')}|{child_rec.get('national_id')}")
    qr_img = Image.open(qr_buf).convert("RGB")
    qr_img = qr_img.resize((220,220))
    img.paste(qr_img, (60, H-300))

    # Footer
    footer_text = "Issued by: EoHealth Egypt — Electronic Office for Health (Prototype)"
    draw.text((W//2, H-80), footer_text, fill="black", anchor="ms", font=header_font)

    return img

def create_birth_certificate_pdf(child_rec, output_path: Path):
    img = create_birth_certificate_image(child_rec)
    img.save(output_path, "PDF", resolution=150)
    return output_path

# ----------------- Simple CSS for RTL and fonts (robust) -----------------
st.markdown(
    """
    <style>
    /* Force RTL for any direction-sensitive container */
    [dir="rtl"] * { text-align: right !important; }
    .streamlit-expanderHeader { direction: rtl; }
    body { direction: ltr; } /* Keep overall layout LTR; content blocks use dir=rtl */
    .arabic { font-family: AmiriLocal, "DejaVu Sans", sans-serif; }
    @font-face {
      font-family: 'AmiriLocal';
      src: local('Amiri'), url('/fonts/Amiri-Regular.ttf');
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------- i18n (simple) ----------------
# keys used in app
STRINGS = {
    "title": {"en":"EoHealth Egypt — Smart Health ID", "ar":"EoHealth Egypt — الهوية الصحية الذكية"},
    "home_welcome": {"en":"Welcome to the EoHealth Egypt demo platform", "ar":"مرحباً بك في النسخة التجريبية لمنصة EoHealth Egypt"},
    "register_birth": {"en":"Register Birth", "ar":"تسجيل مولود جديد"},
    "vaccination_tracker": {"en":"Vaccination Tracker", "ar":"متتبع التطعيمات"},
    "health_record": {"en":"Health Record", "ar":"الملف الطبي للطفل"},
    "ai_insights": {"en":"AI Insights", "ar":"تحليلات ذكية"},
    "eco_dashboard": {"en":"Eco Dashboard", "ar":"لوحة الاستدامة"},
    "admin": {"en":"Admin", "ar":"الإدارة"},
    "download_pdf": {"en":"Download Birth Certificate (PDF)", "ar":"حمل شهادة الميلاد"},
    "download_qr": {"en":"Download QR", "ar":"حمل QR"},
    "digital_card": {"en":"Digital Health Card", "ar":"البطاقة الصحية الرقمية"},
    "import_excel": {"en":"Import children from Excel (.xlsx)", "ar":"استيراد أطفال من إكسل (.xlsx)"},
    "export_excel": {"en":"Export children to Excel", "ar":"تصدير الأطفال إلى إكسل"},
}

def t(key):
    lang = st.session_state.get("lang", "ar")
    return STRINGS.get(key, {}).get(lang, STRINGS.get(key, {}).get("en", key))

# ---------------- Sidebar / Navigation ----------------
st.sidebar.title("EoHealth Egypt")
# language selector
if "lang" not in st.session_state:
    st.session_state.lang = "ar"
lang_choice = st.sidebar.selectbox("Language / اللغة", options=["ar","en"], format_func=lambda x: "العربية" if x=="ar" else "English")
st.session_state.lang = lang_choice

page = st.sidebar.radio(t("title") + " — " + ("Navigate" if st.session_state.lang=="en" else "تنقّل"),
                        ["Home", "Register Birth", "Vaccination Tracker", "Health Record", "AI Insights", "Eco Dashboard", "Digital Card", "Admin"])

# Helper to show RTL text when lang is Arabic
def rtl_md(text):
    if st.session_state.lang == "ar":
        return st.markdown(f'<div dir="rtl" class="arabic">{text}</div>', unsafe_allow_html=True)
    else:
        return st.markdown(text)

# ---------------- Pages ----------------
if page == "Home":
    st.title(t("title"))
    col1, col2 = st.columns([3,1])
    with col1:
        rtl_md(f"<h3>{t('home_welcome')}</h3>")
        if st.session_state.lang == "en":
            st.write("This prototype demonstrates Smart Health ID, full medical profile, QR-based ID, Arabic PDF certificate generation, and eco dashboard.")
            st.info("Data is stored locally in a SQLite database and files under uploads/ (demo).")
        else:
            st.write("يوضح هذا العرض التجريبي الهوية الصحية الذكية، الملف الطبي الكامل، رمز QR للهوية، توليد شهادة ميلاد بالعربية، ولوحة الاستدامة.")
            rtl_md("<b>ملاحظة:</b> لحفظ شهادة الميلاد بالعربي تأكد وجود خط Amiri في مجلد fonts/ أو املأه بخط DejaVu.")
    with col2:
        total = fetch_children_df().shape[0]
        st.metric("Registered Children (demo DB)", total)

# ---------------- Register Birth ----------------
elif page == "Register Birth":
    st.header(t("register_birth") + " / تسجيل مولود")
    rtl_md("املأ بيانات المولود. سيُنشأ Smart Health ID ويُولّد QR وشهادة ميلاد PDF بالعربية." if st.session_state.lang=="ar" else "Fill the newborn's data. A Smart Health ID, QR and Arabic PDF will be generated.")
    with st.form("reg_form", clear_on_submit=True):
        full_name = st.text_input("Full Name / الاسم الكامل")
        national_id = st.text_input("National ID (or temp) / الرقم القومي أو مؤقت")
        birth_date = st.date_input("Birth Date / تاريخ الميلاد", value=date.today())
        gender = st.selectbox("Gender / النوع", ["Male / ذكر","Female / أنثى"])
        mother_id = st.text_input("Mother National ID / رقم بطاقة الأم")
        father_id = st.text_input("Father National ID / رقم بطاقة الأب")
        governorate = st.text_input("Governorate / المحافظة")
        submitted = st.form_submit_button("Register & Generate Smart ID / تسجيل وإنشاء الهوية")
        if submitted:
            if not full_name or not national_id:
                st.error("Full name and National ID are required / الاسم والرقم مطلوبان")
            else:
                # insert base record then generate smart id
                rec = {"full_name": full_name, "national_id": national_id, "smart_id":"", "birth_date": birth_date.isoformat(),
                       "gender": gender, "mother_id": mother_id, "father_id": father_id, "governorate": governorate}
                rec_id = insert_child_record(rec)
                smart = gen_smart_id(rec_id)
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE children SET smart_id=? WHERE id=?", (smart, rec_id))
                conn.commit()
                conn.close()
                # clear cache
                fetch_children_df.clear()

                # generate QR
                qr_buf = generate_qr_bytes(f"{smart}|{full_name}|{national_id}")

                # create PDF certificate
                child_rec = {"full_name": full_name, "national_id": national_id,
                             "birth_date": birth_date.isoformat(), "gender": gender,
                             "governorate": governorate, "smart_id": smart}
                pdf_path = UPLOAD_DIR / f"birth_certificate_{rec_id}.pdf"
                create_birth_certificate_pdf(child_rec, pdf_path)

                st.success("Registered successfully / تم التسجيل")
                st.write("Child ID:", rec_id, "Smart ID:", smart)
                st.image(qr_buf)
                # download qr
                st.markdown(make_download_link_bytes(qr_buf.getvalue(), f"child_{rec_id}_qr.png", t("download_qr")), unsafe_allow_html=True)
                # download pdf
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.markdown(make_download_link_bytes(pdf_bytes, pdf_path.name, t("download_pdf")), unsafe_allow_html=True)

# ---------------- Vaccination Tracker ----------------
elif page == "Vaccination Tracker":
    st.header(t("vaccination_tracker") if st.session_state.lang=="en" else t("vaccination_tracker"))
    df = fetch_children_df()
    if df.empty:
        st.info("No children yet. Register a child first." if st.session_state.lang=="en" else "لا يوجد أطفال بعد. سجّل طفلًا أولاً.")
    else:
        q = st.text_input("Search by name or national ID / ابحث بالاسم أو الرقم")
        if q:
            filtered = df[df["full_name"].str.contains(q, case=False, na=False) | df["national_id"].astype(str).str.contains(q)]
        else:
            filtered = df
        st.dataframe(filtered[["id","full_name","national_id","smart_id","birth_date","governorate"]].rename(
            columns={"id":"ID","full_name":"Name","national_id":"National ID","smart_id":"Smart ID","birth_date":"Birth Date","governorate":"Governorate"}
        ), height=300)
        sel = st.number_input("Enter child ID to update vaccination / أدخل رقم الطفل", min_value=1, step=1)
        if st.button("Load child"):
            rec = get_conn().cursor().execute("SELECT * FROM children WHERE id=?", (sel,)).fetchone()
            if rec:
                st.write("Name:", rec[1], "Smart ID:", rec[3])
                med_df = fetch_medical_df(sel)
                if not med_df.empty:
                    st.subheader("Medical records (latest first)")
                    st.dataframe(med_df[["id","record_date","vaccinations","diagnoses"]])
                vacc = st.text_area("Vaccination notes / حالة التطعيم (dates / details)")
                if st.button("Save Vaccination"):
                    data = {"record_date": datetime.utcnow().date().isoformat(), "weight": None, "height": None, "bmi": None,
                            "vaccinations": vacc, "diagnoses":"", "medications":"", "notes":"", "files":[]}
                    insert_medical(sel, data)
                    st.success("Vaccination saved." if st.session_state.lang=="en" else "تم حفظ التطعيم.")

# ---------------- Health Record ----------------
elif page == "Health Record":
    st.header(t("health_record"))
    df = fetch_children_df()
    if df.empty:
        st.info("No children yet." if st.session_state.lang=="en" else "لا يوجد أطفال بعد.")
    else:
        sid = st.number_input("Enter child ID / أدخل رقم الطفل", min_value=1, step=1)
        if st.button("Load Record"):
            conn = get_conn()
            rec = conn.cursor().execute("SELECT * FROM children WHERE id=?", (sid,)).fetchone()
            conn.close()
            if rec:
                st.subheader(f"{rec[1]}  —  Smart ID: {rec[3]}")
                st.write("Birth Date:", rec[4], "Governorate:", rec[8])
                med_df = fetch_medical_df(sid)
                if med_df.empty:
                    st.info("No medical records yet. Add a new record below." if st.session_state.lang=="en" else "لا توجد سجلات طبية بعد. أضف سجلًا جديدًا أدناه.")
                else:
                    st.subheader("Medical History")
                    st.dataframe(med_df[["id","record_date","weight","height","bmi","vaccinations","diagnoses","medications","notes","files"]])
                st.markdown("### Add / Upload Medical Record")
                with st.form("add_med", clear_on_submit=True):
                    rec_date = st.date_input("Record Date / تاريخ الفحص", value=date.today())
                    weight = st.number_input("Weight (kg) / الوزن (كجم)", min_value=0.0, format="%.1f")
                    height = st.number_input("Height (cm) / الطول (سم)", min_value=0.0, format="%.1f")
                    bmi = (weight / ((height/100)**2)) if (height and weight) else None
                    vaccinations = st.text_area("Vaccinations / التطعيمات (dates & notes)")
                    diagnoses = st.text_area("Diagnoses / التشخيصات")
                    medications = st.text_area("Medications / الأدوية")
                    notes = st.text_area("Notes / ملاحظات")
                    uploaded = st.file_uploader("Upload files (PDF / image) / رفع ملفات", accept_multiple_files=True)
                    submit_med = st.form_submit_button("Save Medical Record / حفظ السجل")
                    if submit_med:
                        files_saved = []
                        for f in uploaded:
                            fname = f"{sid}_{int(datetime.utcnow().timestamp())}_{f.name}"
                            out_path = UPLOAD_DIR / fname
                            with open(out_path, "wb") as of:
                                of.write(f.getbuffer())
                            files_saved.append(str(out_path))
                        data = {"record_date": rec_date.isoformat(), "weight": weight if weight>0 else None,
                                "height": height if height>0 else None, "bmi": round(bmi,2) if bmi else None,
                                "vaccinations": vaccinations, "diagnoses": diagnoses, "medications": medications,
                                "notes": notes, "files": files_saved}
                        insert_medical(sid, data)
                        st.success("Medical record added and files uploaded." if st.session_state.lang=="en" else "تم إضافة السجل الطبي ورفع الملفات.")

# ---------------- AI Insights ----------------
elif page == "AI Insights":
    st.header(t("ai_insights"))
    st.markdown("This is a demo placeholder with simple rules; replace with ML after data collection." if st.session_state.lang=="en" else "هذا نموذج تجريبي بقواعد بسيطة؛ استبدليه بنموذج ML بعد جمع بيانات كافية.")
    df = fetch_children_df()
    if df.empty:
        st.info("No data yet." if st.session_state.lang=="en" else "لا توجد بيانات بعد.")
    else:
        sample = df.head(200)
        st.write("Sample rule-based checks:" if st.session_state.lang=="en" else "فحوصات تجريبية بناء على قواعد بسيطة:")
        alerts = []
        for _, r in sample.iterrows():
            try:
                child_id = r["id"]
                dob = r["birth_date"]
                age_days = (date.today() - date.fromisoformat(dob)).days
                med = fetch_medical_df(child_id)
                has_vacc = (not med.empty) and (med["vaccinations"].astype(str).str.len().sum() > 0)
                if age_days > 60 and not has_vacc:
                    alerts.append((child_id, r["full_name"], "Missing vaccinations"))
            except Exception:
                continue
        if alerts:
            for a in alerts:
                st.warning(f"ID {a[0]} — {a[1]}: {a[2]}")
        else:
            st.success("No immediate rule-based alerts in demo." if st.session_state.lang=="en" else "لا توجد تنبيهات فورية في هذا العرض التجريبي.")

# ---------------- Eco Dashboard ----------------
elif page == "Eco Dashboard":
    st.header(t("eco_dashboard"))
    total = fetch_children_df().shape[0]
    sheets, paper_kg, co2_kg = estimate_environmental_savings(total)
    st.metric("Registered children (demo)", total)
    st.metric("Estimated paper sheets saved", sheets)
    st.metric("Estimated paper mass (kg)", paper_kg)
    st.metric("Estimated CO2 reduced (kg)", co2_kg)
    st.markdown("Green Rewards example: each digital registration yields 1 Green Point to the local health office (demo).")

# ---------------- Digital Health Card ----------------
elif page == "Digital Card":
    st.header(t("digital_card"))
    sid = st.number_input("Enter child ID / أدخل رقم الطفل", min_value=1, step=1)
    if st.button("Load Card"):
        conn = get_conn()
        rec = conn.cursor().execute("SELECT * FROM children WHERE id=?", (sid,)).fetchone()
        conn.close()
        if not rec:
            st.error("Child not found / الطفل غير موجود")
        else:
            child = {"full_name": rec[1], "national_id": rec[2], "smart_id": rec[3], "birth_date": rec[4], "governorate": rec[8]}
            # show QR
            buf = generate_qr_bytes(f"{child['smart_id']}|{child['national_id']}")
            st.image(buf)
            st.write("Name:", child["full_name"])
            st.write("Smart ID:", child["smart_id"])
            st.write("Birth Date:", child["birth_date"])
            # allow download of PDF certificate if exists, else regenerate
            pdf_path = UPLOAD_DIR / f"birth_certificate_{sid}.pdf"
            if not pdf_path.exists():
                create_birth_certificate_pdf(child, pdf_path)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.markdown(make_download_link_bytes(pdf_bytes, pdf_path.name, t("download_pdf")), unsafe_allow_html=True)

# ---------------- Admin ----------------
elif page == "Admin":
    st.header(t("admin"))
    df = fetch_children_df()
    if df.empty:
        st.info("No data." if st.session_state.lang=="en" else "لا توجد بيانات.")
    else:
        st.dataframe(df, height=300)
        # export CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.markdown(make_download_link_bytes(csv, "children.csv", "Download children CSV"), unsafe_allow_html=True)
        # export Excel
        to_excel = io.BytesIO()
        with pd.ExcelWriter(to_excel, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="children")
        st.markdown(make_download_link_bytes(to_excel.getvalue(), "children.xlsx", t("export_excel")), unsafe_allow_html=True)

    if st.button("Clear demo DB (delete all)"):
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM medical_files")
        c.execute("DELETE FROM children")
        conn.commit()
        conn.close()
        fetch_children_df.clear()
        fetch_medical_df.clear()
        st.success("Demo DB cleared." if st.session_state.lang=="en" else "تم مسح قاعدة البيانات التجريبية.")

    st.markdown("---")
    st.markdown(t("import_excel"))
    uploaded_excel = st.file_uploader("Upload .xlsx to import children / ارفع ملف إكسل", type=["xlsx"])
    if uploaded_excel:
        try:
            df_in = pd.read_excel(uploaded_excel)
            # Expect columns: full_name, national_id, birth_date (ISO or yyyy-mm-dd), gender, mother_id, father_id, governorate
            inserted = 0
            for _, row in df_in.iterrows():
                # minimal validation
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
                    "governorate": str(row.get("governorate")) if not pd.isna(row.get("governorate")) else ""
                }
                new_id = insert_child_record(rec)
                conn = get_conn()
                conn.cursor().execute("UPDATE children SET smart_id=? WHERE id=?", (gen_smart_id(new_id), new_id))
                conn.commit()
                conn.close()
                inserted += 1
            fetch_children_df.clear()
            st.success(f"Imported {inserted} records." if st.session_state.lang=="en" else f"تم استيراد {inserted} سجلات.")
        except Exception as e:
            st.error("Failed to import Excel: " + str(e))

    st.markdown("---")
    if st.button("Insert Demo Data (10 sample children)"):
        demo = [
            {"full_name":"أحمد علي","national_id":"T10000001","birth_date":"2024-01-10","gender":"Male / ذكر","mother_id":"M1001","father_id":"F1001","governorate":"Cairo"},
            {"full_name":"مريم حسن","national_id":"T10000002","birth_date":"2023-05-05","gender":"Female / أنثى","mother_id":"M1002","father_id":"F1002","governorate":"Giza"},
            {"full_name":"يوسف سعيد","national_id":"T10000003","birth_date":"2022-11-20","gender":"Male / ذكر","mother_id":"M1003","father_id":"F1003","governorate":"Alexandria"},
            {"full_name":"سارة محمد","national_id":"T10000004","birth_date":"2021-07-15","gender":"Female / أنثى","mother_id":"M1004","father_id":"F1004","governorate":"Cairo"},
            {"full_name":"آدم خالد","national_id":"T10000005","birth_date":"2020-03-02","gender":"Male / ذكر","mother_id":"M1005","father_id":"F1005","governorate":"Dakahliya"},
            {"full_name":"لين محمود","national_id":"T10000006","birth_date":"2019-08-12","gender":"Female / أنثى","mother_id":"M1006","father_id":"F1006","governorate":"Aswan"},
            {"full_name":"عمر نبيل","national_id":"T10000007","birth_date":"2018-12-01","gender":"Male / ذكر","mother_id":"M1007","father_id":"F1007","governorate":"Luxor"},
            {"full_name":"نور سامي","national_id":"T10000008","birth_date":"2017-02-25","gender":"Female / أنثى","mother_id":"M1008","father_id":"F1008","governorate":"Ismailia"},
            {"full_name":"ريان مصطفى","national_id":"T10000009","birth_date":"2016-09-09","gender":"Male / ذكر","mother_id":"M1009","father_id":"F1009","governorate":"Suez"},
            {"full_name":"هنا نبيل","national_id":"T10000010","birth_date":"2015-06-18","gender":"Female / أنثى","mother_id":"M1010","father_id":"F1010","governorate":"Gharbia"},
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
        st.success("Demo data inserted. Refresh the page to see new records." if st.session_state.lang=="en" else "تم إضافة بيانات تجريبية. حدّث الصفحة لعرض السجلات.")

# ------------- End -------------
