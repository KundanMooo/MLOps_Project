import streamlit as st
import requests
from datetime import date, datetime

API_URL = "http://localhost:8000/predict"  # backend FastAPI endpoint

st.set_page_config(page_title="AI Job Description Generator", layout="centered")

st.title("🤖 AI-Powered Job Description Generator")
st.caption("Fill in your company’s requirements below — the AI agent will generate a professional Job Description!")

st.markdown("---")

with st.form("jd_form"):
    # --- Basic Job Info ---
    st.subheader("📋 Job Details")

    topic = st.text_input("Job Title / Role", placeholder="e.g. Software Engineer")
    department = st.selectbox(
        "Department / Domain",
        ["Computer Science", "Electronics (ECE)", "Mechanical", "Civil", "Electrical", "Finance", "Marketing", "Other"]
    )
    qualification = st.selectbox("Minimum Qualification", ["Graduate", "Postgraduate", "PhD", "Any"])
    experience = st.slider("Experience required (in years)", min_value=0, max_value=15, value=1)
    job_type = st.radio("Job Type", ["Full-time", "Internship", "Part-time", "Remote"])
    location = st.text_input("Job Location", placeholder="e.g. Kolkata / Remote")
    salary_range = st.text_input("Salary Range", placeholder="e.g. 10–15 LPA / ₹40,000 per month")

    # --- Skill Requirements ---
    st.subheader("🧠 Skill Requirements")
    skills = st.multiselect(
        "Select key skills (or type your own)",
        ["Python", "SQL", "Machine Learning", "Deep Learning", "Data Analysis",
         "Communication", "Java", "C++", "Cloud Computing", "NLP", "Computer Vision"],
        default=["Python", "SQL"]
    )
    custom_skills = st.text_input("Add any additional skills (comma-separated)", placeholder="e.g. Leadership, Excel")

    # --- CV and Interview Info ---
    st.subheader("🧾 Recruitment Details")
    min_no_cv = st.number_input("Minimum number of CVs you want", min_value=1, value=5)
    interview_date = st.date_input("Interview Date", value=date.today())
    interview_time = st.time_input("Interview Time", value=datetime.now().time().replace(second=0, microsecond=0))

    # --- Optional Notes ---
    st.subheader("🗒️ Additional Notes (Optional)")
    notes = st.text_area("Describe extra requirements or company info",
                         placeholder="e.g. Looking for strong analytical skills and familiarity with AWS...")

    submitted = st.form_submit_button("✨ Generate Job Description")

# --- When submitted ---
if submitted:
    # Combine all skills (from dropdown + text box)
    skills_combined = skills + [s.strip() for s in custom_skills.split(",") if s.strip()]

    # Create the topic_1 string (LLM input format)
    topic_1 = (
        f"We need a {topic or 'professional'} in the {department} domain "
        f"with a minimum qualification of {qualification} and {experience} year(s) experience. "
        f"Job Type: {job_type}, Location: {location or 'Not specified'}, "
        f"Salary Range: {salary_range or 'Not specified'}. "
        f"Required skills: {', '.join(skills_combined) or 'Not specified'}. "
        f"Additional notes: {notes or 'None'}."
    )

    # Build payload for FastAPI
    payload = {
        "topic": topic_1,
        "iteration": 0,
        "max_iteration": 5,
        "retry_cv": 0,
        "max_retry_cv": 3,
        "min_no_cv_you_want": int(min_no_cv),
        "interview_date": interview_date.isoformat(),
        "interview_time": interview_time.strftime("%H:%M")
    }

    st.markdown("### 📤 Final Input Sent to Backend (LLM-ready):")
    st.code(topic_1, language="text")

    st.markdown("### 🔧 API Payload:")
    st.json(payload)

    try:
        with st.spinner("🚀 Sending request to AI backend..."):
            response = requests.post(API_URL, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            st.success("✅ Job Description Generated Successfully!")
            st.subheader("📝 AI-Generated Job Description")
            jd_text = result.get("result", {}).get("jd_text") or result.get("result")
            st.markdown(jd_text or "**(No JD text returned)**")
            st.markdown("---")
            st.json(result)
        else:
            st.error(f"❌ Backend error: {response.status_code} — {response.text}")

    except Exception as e:
        st.error(f"Request failed: {e}")
