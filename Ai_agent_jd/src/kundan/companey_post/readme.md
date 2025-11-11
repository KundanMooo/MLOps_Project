# LinkedIn API Helper

A simple Python module to post text to LinkedIn organization pages using the Voyager GraphQL endpoint.

---

## Usage

1. **Install dependency:**

   ```bash
   pip install requests
   ```

2. **Set up files:**

   ```
   project/
   ├── linkedin_post.py   # contains linked_post() function
   └── main.py           # script to call it
   ```

3. **Example (main.py):**

   ```python
   from linkedin_post import linked_post_fun

   text = "Hello from my modular LinkedIn script!"


   response = linked_post_fun(text)
   print(response)
   
   ```

4. **Run:**

   ```bash
   python main.py
   ```

---