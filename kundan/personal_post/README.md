
# **Personal Post Feature**



## 🚀 How to Run

Follow the steps below to set up and run this feature locally:

### 1️⃣ Navigate to the project folder
```bash
cd kundan/personal_post
````

### 2️⃣ Sync the environment (if `uv.lock` file exists)

If you're using `uv` for dependency management, run:

```bash
uv sync
```

This will automatically install all required dependencies in a `.venv` environment.

---

### 3️⃣ Activate the virtual environment

On **Windows (PowerShell)**:

```bash
.venv\Scripts\Activate.ps1
```

---

### 4️⃣ Run the FastAPI application

```bash
python app.py
```

You should see output like:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

### 5️⃣ Access the API

Once the server is running, open your browser and visit:

* **API Root:** [http://localhost:8000](http://localhost:8000)

