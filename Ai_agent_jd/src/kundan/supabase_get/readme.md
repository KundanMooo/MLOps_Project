
## How to Run

### 1️ Install Requirements

Make sure you have Python 3.8+ installed, then run:

```bash
pip install -r requirements.txt
```

---

### 2️ Run the Script

If you want to call the `main()` function from **another Python file**, you can do it in two ways:

#### Import Using Module Path

Run your code from the project’s root folder (where `kundan/` exists):

```bash
cd "D:\MTech DS\MLOps\MLOps_Project"
python your_script.py
```

Inside `your_script.py`:

```python
from kundan.supabase_get.app import main

main()
```
