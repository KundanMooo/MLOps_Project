import streamlit as st
import requests
import re

st.set_page_config(page_title="Resume Upload", page_icon="📄")

# Simple styling
st.markdown("""
    <style>
    .main { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    </style>
""", unsafe_allow_html=True)

API_URL = "http://localhost:8000"

# Header
st.title("📄 Resume Upload Form")
st.write("MLOps School Project")

# API Status Check
try:
    requests.get(f"{API_URL}/", timeout=2)
    st.success("✅ API Connected")
except:
    st.error("❌ API Not Running - Start: uvicorn main:app --reload")

st.divider()

# Validation Functions
def validate_name(name):
    if len(name.strip()) < 2:
        return False, "Name must be at least 2 characters"
    if not re.match(r"^[a-zA-Z\s\-'\.]+$", name):
        return False, "Name can only contain letters"
    return True, ""

def validate_email(email):
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format"
    return True, ""

def validate_phone(phone):
    cleaned = re.sub(r'[\s\-+]', '', phone)
    cleaned = cleaned.replace('91', '', 1) if cleaned.startswith('91') else cleaned
    
    if not cleaned.isdigit() or len(cleaned) != 10:
        return False, "Phone must be 10 digits"
    if not cleaned.startswith(('6', '7', '8', '9')):
        return False, "Phone must start with 6, 7, 8, or 9"
    return True, cleaned

# Form
with st.form("upload_form", clear_on_submit=True):
    name = st.text_input("Full Name *", placeholder="John Doe")
    email = st.text_input("Email *", placeholder="john@example.com")
    phone = st.text_input("Phone *", placeholder="9876543210")
    uploaded_file = st.file_uploader("Resume (PDF) *", type=['pdf'])
    
    if uploaded_file:
        size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        st.info(f"📎 {uploaded_file.name} ({size_mb:.2f} MB)")
    
    submit = st.form_submit_button("Submit", use_container_width=True)
    
    if submit:
        errors = []
        
        # Validate all fields
        if not name:
            errors.append("Name is required")
        else:
            valid, msg = validate_name(name)
            if not valid:
                errors.append(msg)
        
        if not email:
            errors.append("Email is required")
        else:
            valid, msg = validate_email(email)
            if not valid:
                errors.append(msg)
        
        if not phone:
            errors.append("Phone is required")
        else:
            valid, phone_clean = validate_phone(phone)
            if not valid:
                errors.append(phone_clean)
            else:
                phone = phone_clean
        
        if not uploaded_file:
            errors.append("Resume PDF is required")
        elif len(uploaded_file.getvalue()) > 10 * 1024 * 1024:
            errors.append("File size must be under 10 MB")
        
        # Show errors or submit
        if errors:
            for error in errors:
                st.error(f"❌ {error}")
        else:
            with st.spinner("Uploading..."):
                try:
                    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), 'application/pdf')}
                    data = {'name': name.strip(), 'email': email.strip().lower(), 'phone': int(phone)}
                    
                    response = requests.post(f"{API_URL}/upload-resume", files=files, data=data, timeout=30)
                    
                    if response.status_code == 200:
                        st.success("✅ Resume uploaded successfully!")
                        result = response.json()
                        # with st.expander("View Details"):
                        #     st.json(result['data'])
                    else:
                        st.error(f"❌ {response.json().get('detail', 'Upload failed')}")
                
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to API!")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

st.divider()
st.caption("FastAPI + Streamlit + Supabase")