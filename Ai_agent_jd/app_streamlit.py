import streamlit as st
import requests
from datetime import date, datetime, timedelta

# -------------------------------
# API URLs
# -------------------------------
JD_API_URL = "http://localhost:8000/predict"        # First endpoint
OFFER_API_URL = "http://localhost:8000/send_offer"  # Second endpoint

st.set_page_config(page_title="AI Hiring Assistant", layout="centered")

st.title("🤖 AI-Powered Hiring Workflow Dashboard")
st.caption("End-to-end automation: Job Description → CV Filtering → Offer Letter Workflow")
st.markdown("---")

# ============================================================
# 🧩 STEP 1: Job Description Generation
# ============================================================
st.header("📋 Step 1: Generate AI Job Description")

# Initialize session state
if "selected_candidates" not in st.session_state:
    st.session_state.selected_candidates = []
if "topic" not in st.session_state:
    st.session_state.topic = ""           # Full descriptive JD
if "role_offered" not in st.session_state:
    st.session_state.role_offered = ""    # Clean role name
if "company_name" not in st.session_state:
    st.session_state.company_name = ""

with st.form("jd_form"):
    st.subheader("🏢 Company Information")
    company_name = st.text_input("Company Name", placeholder="e.g. Company-A")

    st.subheader("🧠 Job Details")
    topic = st.text_input("Job Title / Role", placeholder="e.g. Data Scientist")
    department = st.selectbox(
        "Department / Domain",
        ["Computer Science", "Electronics (ECE)", "Mechanical", "Civil", "Electrical", "Finance", "Marketing", "Other"]
    )
    qualification = st.selectbox("Minimum Qualification", ["Graduate", "Postgraduate", "PhD", "Any"])
    experience = st.slider("Experience required (in years)", 0, 15, 1)
    job_type = st.radio("Job Type", ["Full-time", "Internship", "Part-time", "Remote"])
    location = st.text_input("Job Location", placeholder="e.g. Kolkata / Remote")
    salary_range = st.text_input("Salary Range", placeholder="e.g. 10–15 LPA / ₹40,000 per month")

    st.subheader("🔑 Skill Requirements")
    skills = st.multiselect(
        "Select key skills (or type your own)",
        ["Python", "SQL", "Machine Learning", "Deep Learning", "Data Analysis",
         "Communication", "Java", "C++", "Cloud Computing", "NLP", "Computer Vision"],
        default=["Python", "SQL"]
    )
    custom_skills = st.text_input("Add additional skills (comma-separated)", placeholder="e.g. Leadership, Excel")

    st.subheader("📅 Recruitment Details")
    min_no_cv = st.number_input("Minimum number of CVs", min_value=1, value=5)
    interview_date = st.date_input("Interview Date", value=date.today())
    interview_time = st.time_input("Interview Time", value=datetime.now().time().replace(second=0, microsecond=0))
    no_of_students = st.number_input("Number of students to interview", min_value=1, value=2)

    st.subheader("🗒️ Additional Notes (Optional)")
    notes = st.text_area("Extra requirements or comments")

    jd_submit = st.form_submit_button("✨ Generate Job Description")

if jd_submit:
    # Combine skills
    skills_combined = skills + [s.strip() for s in custom_skills.split(",") if s.strip()]

    # Full descriptive JD
    topic_1 = (
        f"We need a {topic or 'professional'} in the {department} domain "
        f"with a minimum qualification of {qualification} and {experience} year(s) experience. "
        f"Job Type: {job_type}, Location: {location or 'Not specified'}, "
        f"Salary Range: {salary_range or 'Not specified'}. "
        f"Required skills: {', '.join(skills_combined) or 'Not specified'}. "
        f"Additional notes: {notes or 'None'}. (Company: {company_name or 'Unknown Company'})"
    )

    payload = {
        "topic": topic_1,
        "iteration": 0,
        "max_iteration": 5,
        "retry_cv": 0,
        "max_retry_cv": 3,
        "min_no_cv_you_want": int(min_no_cv),
        "interview_date": interview_date.isoformat(),
        "interview_time": interview_time.strftime("%H:%M"),
        "min_no_days_you_want_to_collect_cv": 5,
        "no_of_student_you_want_for_interview": int(no_of_students),
        "company_name": company_name,
    }

    st.markdown("### 📤 Final Input Sent to Backend:")
    st.code(topic_1, language="text")

    with st.spinner("🚀 Generating Job Description..."):
        try:
            response = requests.post(JD_API_URL, json=payload, timeout=3600)
            if response.status_code == 200:
                result = response.json()
                st.success("✅ Job Description Generated Successfully!")

                st.session_state.topic = result.get("topic", topic_1)
                st.session_state.role_offered = topic  # Store clean role title separately
                st.session_state.selected_candidates = result.get("selected_students", [])
                st.session_state.company_name = company_name

                st.markdown("### 🧾 Selected Students for Interview:")
                st.json(st.session_state.selected_candidates)
            else:
                st.error(f"❌ Backend error: {response.status_code} — {response.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

st.markdown("---")

# ============================================================
# 💌 STEP 2: Offer Letter Workflow
# ============================================================
st.header("💌 Step 2: Send Offer Letters")

candidate_names = [c["name"] for c in st.session_state.selected_candidates]
candidate_emails = [c["email"] for c in st.session_state.selected_candidates]

with st.form("offer_form"):
    st.subheader("👥 Candidate Information")

    if candidate_names:
        selected_names = st.multiselect("Select Candidate Name(s)", options=candidate_names)
        selected_emails = st.multiselect("Select Candidate Email(s)", options=candidate_emails)
    else:
        st.info("⚠️ No shortlisted candidates yet. Please run Step 1 first.")
        selected_names, selected_emails = [], []

    st.subheader("💼 Offer Details")
    role = st.text_input(
        "Role Offered",
        value=st.session_state.role_offered or "",
        placeholder="e.g. Data Scientist"
    )
    salary = st.text_input("Salary Offered", placeholder="e.g. ₹10 LPA or ₹50,000 per month")

    offer_submit = st.form_submit_button("📨 Send Offer Letters")

if offer_submit:
    start_date = (datetime.now() + timedelta(days=14)).date().isoformat()  # 2 weeks from today

    # Create candidates payload with personalized offer_text
    candidates = []
    for name, email in zip(selected_names, selected_emails):
        if name and email:
            offer_text = (
                f"Dear {name},\n\n"
                f"We are pleased to inform you that you have been selected for the position of {role} at {st.session_state.company_name}.\n"
                f"Your compensation will be {salary}, and your start date is {start_date}.\n\n"
                f"Please reply to this email with 'I accept' to confirm your acceptance.\n\n"
                f"Regards,\n{st.session_state.company_name} HR"
            )
            candidates.append({"name": name, "email": email, "offer_text": offer_text})

    offer_payload = {
        "candidate": candidates,
        "role": role,
        "salary": salary,
        "company_name": st.session_state.company_name
    }

    st.markdown("### 📤 Payload Sent to Offer Workflow:")
    st.json(offer_payload)

    if not candidates:
        st.warning("⚠️ Please select at least one candidate with name and email.")
    else:
        with st.spinner("✉️ Sending offer letters..."):
            try:
                response = requests.post(OFFER_API_URL, json=offer_payload, timeout=600)
                if response.status_code == 200:
                    result = response.json()
                    st.success("✅ Offer Letters Sent Successfully!")
                    st.json(result)
                else:
                    st.error(f"❌ Backend error: {response.status_code} — {response.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")
