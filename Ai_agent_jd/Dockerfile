# =========================
# 1️⃣ Base Image
# =========================
FROM python:3.11-slim

# =========================
# 2️⃣ Set Work Directory
# =========================
WORKDIR /app

# =========================
# 3️⃣ Copy Project Files
# =========================
COPY . /app

# =========================
# 4️⃣ Install Dependencies from requirements.txt
# =========================
RUN pip install --no-cache-dir -r requirements.txt

# =========================
# 5️⃣ Expose Ports
# =========================
EXPOSE 8501
EXPOSE 8000

# =========================
# 6️⃣ Run both Backend and Frontend
# =========================
CMD bash -c "uvicorn app:app --host 0.0.0.0 --port 8000 & streamlit run app_streamlit.py --server.port 8501 --server.address 0.0.0.0"