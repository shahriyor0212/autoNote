# 🎓 Student Note & Test Fact Maker

A simple, reliable tool for students to upload study documents and receive structured study notes and test-ready facts powered by Gemini.

---

## 🚀 Quick Start

### 1. Set Up Your API Key
Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

You can either:
- Create a `.env` file in this directory:
  ```bash
  cp .env.example .env
  ```
  and add your key:
  ```env
  GEMINI_API_KEY=your_actual_key_here
  ```
- Or enter it directly in the app's sidebar.

---

### 2. Run the App
Activate the virtual environment and start Streamlit:

```bash
# If using the included virtual environment
.venv/bin/streamlit run app.py
```

Or standard command:
```bash
streamlit run app.py
```

The app will automatically open in your browser at `http://localhost:8501`.

---

## 📖 How to Use

1. **Enter Subject**: e.g., *Biology*, *World History*, *Calculus*, *Organic Chemistry*.
2. **Upload Document**: Upload your lecture PDF, Word document (`.docx`), plain text (`.txt`), or slide images (`.png`/`.jpg`).
3. **Generate**: Click **Generate Notes & Test Facts**.
   - Gemini analyzes the material as a teacher of that subject and creates comprehensive study notes and test-ready questions/facts.
   - Once generated, the button is **greyed out** to prevent accidental duplicate requests.
4. **Download**:
   - Click **Download PDF Document** to save your printable notes (this also re-enables the Generate button).
   - Click **Download Word Document (.docx)** if you want to edit your notes in Microsoft Word or Google Docs.
