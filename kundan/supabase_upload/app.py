import streamlit as st
from supabase import create_client, Client
import os
from datetime import datetime
import time
from dotenv import load_dotenv
# Page configuration
st.set_page_config(
    page_title="File Upload Form",
    page_icon="📄",
    layout="centered"
)
load_dotenv()
# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Initialize Supabase client
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# Custom CSS for better UI
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .stApp {
        background: transparent;
    }
    div.block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .upload-container {
        background: rgba(255, 255, 255, 0.95);
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        padding: 0.75rem 2rem;
        border-radius: 10px;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #c3e6cb;
        text-align: center;
        font-weight: 600;
        margin: 1rem 0;
    }
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #f5c6cb;
        text-align: center;
        font-weight: 600;
        margin: 1rem 0;
    }
    .form-header {
        text-align: center;
        color: #333;
        margin-bottom: 2rem;
    }
    .stTextInput>div>div>input, .stFileUploader>div>div>div>div {
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'show_success' not in st.session_state:
    st.session_state.show_success = False
if 'show_error' not in st.session_state:
    st.session_state.show_error = False
if 'error_message' not in st.session_state:
    st.session_state.error_message = ""

# Function to upload file to Supabase Storage
def upload_file_to_storage(file, filename):
    try:
        file_path = f"allpdfs/{filename}"
        file_bytes = file.getvalue()
        
        # Upload to Supabase Storage
        response = supabase.storage.from_("Pdfs_").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": file.type}
        )
        
        return file_path
    except Exception as e:
        raise Exception(f"Storage upload failed: {str(e)}")

# Function to insert data into Supabase table
def insert_data_to_table(name, email, phone, file_path):
    try:
        data = {
            "Name": name,
            "Email_id": email,
            "Mobile_No.": phone,
            "Resume": file_path,
            
        }
        
        response = supabase.table("Data_Storage").insert(data).execute()
        return True
    except Exception as e:
        raise Exception(f"Database insert failed: {str(e)}")

# Main App
def main():
    st.markdown('<div class="upload-container">', unsafe_allow_html=True)
    
    # Header
    st.markdown('<h1 class="form-header">📄 Resume Upload Form(MLOps Project)</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">Please fill in all the details below</p>', unsafe_allow_html=True)
    
    # Show success message
    if st.session_state.show_success:
        st.markdown('<div class="success-message">✅ Form submitted successfully!</div>', unsafe_allow_html=True)
        time.sleep(2)
        st.session_state.show_success = False
        st.rerun()
    
    # Show error message
    if st.session_state.show_error:
        st.markdown(f'<div class="error-message">❌ {st.session_state.error_message}</div>', unsafe_allow_html=True)
        st.session_state.show_error = False
    
    # Form
    with st.form("upload_form", clear_on_submit=True):
        st.markdown("### Personal Information")
        
        # Name field
        name = st.text_input(
            "Full Name *",
            placeholder="Enter your full name",
            help="Please enter your complete name"
        )
        
        # Email field
        email = st.text_input(
            "Email Address *",
            placeholder="example@email.com",
            help="We'll never share your email with anyone"
        )
        
        # Phone number field
        phone = st.text_input(
            "Phone Number *",
            placeholder="+91 XXXXXXXXXX",
            help="Include country code"
        )
        
        st.markdown("### Document Upload")
        
        # File upload field
        uploaded_file = st.file_uploader(
            "Upload PDF Document *",
            type=['pdf'],
            help="Maximum file size: 200MB"
        )
        
        # Submit button
        st.markdown("<br>", unsafe_allow_html=True)
        submit_button = st.form_submit_button("Submit Form")
        
        if submit_button:
            # Validation
            if not name or not email or not phone or not uploaded_file:
                st.session_state.show_error = True
                st.session_state.error_message = "All fields are required!"
                st.rerun()
            elif "@" not in email or "." not in email:
                st.session_state.show_error = True
                st.session_state.error_message = "Please enter a valid email address!"
                st.rerun()
            elif len(phone) < 10:
                st.session_state.show_error = True
                st.session_state.error_message = "Please enter a valid phone number!"
                st.rerun()
            else:
                try:
                    with st.spinner("Uploading file and saving data..."):
                        # Generate unique filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{timestamp}_{uploaded_file.name}"
                        
                        # Upload file to storage
                        file_path = upload_file_to_storage(uploaded_file, filename)
                        
                        # Insert data into table
                        insert_data_to_table(name, email, phone, file_path)
                        
                        # Show success message
                        st.session_state.show_success = True
                        st.rerun()
                        
                except Exception as e:
                    st.session_state.show_error = True
                    st.session_state.error_message = str(e)
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("<br><p style='text-align: center; color: #999; font-size: 0.9rem;'>Powered by Supabase & Streamlit</p>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
