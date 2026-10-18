import os
import io
import streamlit as st
import docx
import pypdf
from fpdf import FPDF
from google import genai
from google.genai import types

# Auto-load .env file if present
if os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass

# Set page configuration
st.set_page_config(
    page_title="Student Note Maker",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="auto"
)

# Custom styling for clean, student-friendly interface
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding-bottom: 1.5rem;
    }
    .main-header h1 {
        color: #1E3A8A;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }
    .main-header p {
        color: #4B5563;
        font-size: 1.05rem;
    }
    .status-badge {
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .stDownloadButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# --- State Initialization ---
if "has_generated" not in st.session_state:
    st.session_state.has_generated = False
if "pdf_downloaded" not in st.session_state:
    st.session_state.pdf_downloaded = False
if "generated_notes" not in st.session_state:
    st.session_state.generated_notes = ""
if "docx_bytes" not in st.session_state:
    st.session_state.docx_bytes = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "subject_used" not in st.session_state:
    st.session_state.subject_used = ""


def unlock_after_pdf_download():
    """Callback when the student downloads the PDF."""
    st.session_state.pdf_downloaded = True


def reset_app_state():
    """Reset the app state for a new document."""
    st.session_state.has_generated = False
    st.session_state.pdf_downloaded = False
    st.session_state.generated_notes = ""
    st.session_state.docx_bytes = None
    st.session_state.pdf_bytes = None
    st.session_state.subject_used = ""


# --- Helper: Build Word Document ---
def build_docx(markdown_text: str, subject: str) -> bytes:
    doc = docx.Document()
    
    # Title
    doc.add_heading(f"Study Notes & Test Prep: {subject}", level=0)
    doc.add_paragraph("Generated automatically for student exam preparation.")
    doc.add_paragraph("—" * 25)

    for line in markdown_text.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith("### "):
            doc.add_heading(line_clean[4:], level=3)
        elif line_clean.startswith("## "):
            doc.add_heading(line_clean[3:], level=2)
        elif line_clean.startswith("# "):
            doc.add_heading(line_clean[2:], level=1)
        elif line_clean.startswith("- ") or line_clean.startswith("* "):
            doc.add_paragraph(line_clean[2:], style="List Bullet")
        else:
            doc.add_paragraph(line_clean)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- Helper: Build PDF Document ---
def build_pdf(markdown_text: str, subject: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Font setup with Unicode fallback
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    font_bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    
    font_name = "ArialFont" if os.path.exists(font_path) else "Helvetica"
    if os.path.exists(font_path):
        pdf.add_font(font_name, "", font_path)
    if os.path.exists(font_bold_path):
        pdf.add_font(font_name, "B", font_bold_path)

    # Document Header
    pdf.set_font(font_name, "B" if os.path.exists(font_bold_path) else "", size=16)
    pdf.cell(w=pdf.epw, h=10, text=f"Study Notes & Test Prep: {subject}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_name, size=9)
    pdf.cell(w=pdf.epw, h=6, text="Generated for student study & exam preparation", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Content
    for line in markdown_text.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            pdf.ln(2)
            continue
        if line_clean.startswith("### "):
            pdf.set_font(font_name, "B" if os.path.exists(font_bold_path) else "", size=12)
            pdf.ln(2)
            pdf.multi_cell(w=pdf.epw, h=6, text=line_clean[4:])
            pdf.ln(1)
        elif line_clean.startswith("## "):
            pdf.set_font(font_name, "B" if os.path.exists(font_bold_path) else "", size=13)
            pdf.ln(3)
            pdf.multi_cell(w=pdf.epw, h=7, text=line_clean[3:])
            pdf.ln(1)
        elif line_clean.startswith("# "):
            pdf.set_font(font_name, "B" if os.path.exists(font_bold_path) else "", size=15)
            pdf.ln(4)
            pdf.multi_cell(w=pdf.epw, h=8, text=line_clean[2:])
            pdf.ln(2)
        elif line_clean.startswith("- ") or line_clean.startswith("* "):
            pdf.set_font(font_name, size=10)
            pdf.multi_cell(w=pdf.epw, h=5, text="  •  " + line_clean[2:])
        else:
            pdf.set_font(font_name, size=10)
            pdf.multi_cell(w=pdf.epw, h=5, text=line_clean)

    return bytes(pdf.output())


# --- UI: Sidebar Settings ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key detection / input
    env_api_key = os.environ.get("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "Gemini API Key",
        value=env_api_key,
        type="password",
        help="Get your key at aistudio.google.com (usually starts with AIzaSy...)"
    )

    clean_key_check = api_key_input.strip().strip("'\"")
    if clean_key_check:
        if not clean_key_check.isascii():
            st.error("⚠️ The key entered has invalid/non-ASCII characters (e.g. copied emoji like ❌ or error text). Please paste only your clean API key.")
        elif not clean_key_check.startswith("AIza"):
            st.info("ℹ️ Google API keys typically begin with `AIza...`. Make sure you didn't paste an error message.")
        else:
            st.success("✅ Key format valid")

    model_choice = st.selectbox(
        "Gemini Model",
        options=["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        index=0,
        help="Recommended: gemini-3.8-flash"
    )
    
    st.divider()
    st.markdown("""
    **How it works:**
    1. Enter your subject (e.g. Biology, History)
    2. Upload your lecture notes or document
    3. Click **Generate Notes & Test Facts**
    4. Download the **PDF** to unlock the generate button
    """)
    
    if st.session_state.has_generated:
        st.divider()
        if st.button("🔄 Start Fresh / Reset", on_click=reset_app_state):
            st.rerun()


# --- Main UI Area ---
st.markdown("""
<div class="main-header">
    <h1>🎓 Student Note & Test Fact Maker</h1>
    <p>Upload any study material to turn it into concise notes and test-ready facts.</p>
</div>
""", unsafe_allow_html=True)

# Subject Input
subject = st.text_input(
    "1. Enter Subject / Topic",
    placeholder="e.g., Biology, World History, Calculus, Economics",
    help="This tells Gemini what kind of teacher to act as."
)

# Document Upload Area
uploaded_file = st.file_uploader(
    "2. Upload Your Document",
    type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
    help="Supports PDF, Word (.docx), Plain Text (.txt), or image notes."
)

# Determine button disabled state
# Requirement: Click the button -> won't click until the student downloads the PDF (greyed out)
is_locked = st.session_state.has_generated and (not st.session_state.pdf_downloaded)

if is_locked:
    st.warning("🔒 **Generate button is locked.** Please download your PDF notes below to re-enable it.")

# Generate Button
generate_clicked = st.button(
    "🚀 Generate Notes & Test Facts",
    disabled=is_locked,
    type="primary",
    use_container_width=True
)

# --- Generation Logic ---
if generate_clicked:
    # Validation checks
    active_api_key = (api_key_input or env_api_key).strip().strip("'\"")
    if not active_api_key:
        st.error("⚠️ Please provide a Gemini API Key in the sidebar to continue.")
    elif not active_api_key.isascii():
        st.error("⚠️ The API Key contains invalid characters (such as emojis or copied error text). Please enter only your clean Gemini API key starting with 'AIza...'.")
    elif not subject.strip():
        st.error("⚠️ Please enter a subject before generating notes.")
    elif not uploaded_file:
        st.error("⚠️ Please upload a document to analyze.")
    else:
        with st.spinner(f"Analyzing document as a {subject} teacher..."):
            try:
                # Initialize Gemini Client
                client = genai.Client(api_key=active_api_key)

                # Prompt as requested
                prompt_text = (
                    f"You are a {subject.strip()} teacher. "
                    f"Make notes in whatever language this document is and analyze what facts can be in the test."
                )

                file_bytes = uploaded_file.getvalue()
                file_name = uploaded_file.name.lower()

                # Prepare contents for Gemini based on file type
                if file_name.endswith(".pdf"):
                    pdf_part = types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")
                    contents = [pdf_part, prompt_text]
                elif file_name.endswith(".docx"):
                    doc = docx.Document(io.BytesIO(file_bytes))
                    doc_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                    contents = [f"Document Content:\n{doc_text}\n\nTask:\n{prompt_text}"]
                elif file_name.endswith((".png", ".jpg", ".jpeg")):
                    mime = "image/png" if file_name.endswith(".png") else "image/jpeg"
                    img_part = types.Part.from_bytes(data=file_bytes, mime_type=mime)
                    contents = [img_part, prompt_text]
                else:
                    # Plain text
                    text_content = file_bytes.decode("utf-8", errors="ignore")
                    contents = [f"Document Content:\n{text_content}\n\nTask:\n{prompt_text}"]

                # Call Gemini Flash
                response = client.models.generate_content(
                    model=model_choice,
                    contents=contents
                )

                generated_text = response.text or "No response received."

                # Create exportable documents
                docx_data = build_docx(generated_text, subject.strip())
                pdf_data = build_pdf(generated_text, subject.strip())

                # Save to session state
                st.session_state.has_generated = True
                st.session_state.pdf_downloaded = False
                st.session_state.generated_notes = generated_text
                st.session_state.docx_bytes = docx_data
                st.session_state.pdf_bytes = pdf_data
                st.session_state.subject_used = subject.strip()

                st.rerun()

            except Exception as e:
                st.error(f"❌ Error communicating with Gemini API: {str(e)}")


# --- Display Generated Results & Downloads ---
if st.session_state.has_generated and st.session_state.generated_notes:
    st.divider()
    st.subheader(f"📝 Study Notes & Test Facts: {st.session_state.subject_used}")

    # Download buttons section
    st.markdown("### 📥 Download Your Notes")
    col1, col2 = st.columns(2)

    with col1:
        # PDF Download Button - Clicking this unlocks the Generate button
        st.download_button(
            label="📄 Download PDF Document",
            data=st.session_state.pdf_bytes,
            file_name=f"{st.session_state.subject_used.lower().replace(' ', '_')}_notes.pdf",
            mime="application/pdf",
            on_click=unlock_after_pdf_download,
            help="Clicking this will download the PDF and re-enable the Generate button."
        )

    with col2:
        # Word Download Button
        st.download_button(
            label="📝 Download Word Document (.docx)",
            data=st.session_state.docx_bytes,
            file_name=f"{st.session_state.subject_used.lower().replace(' ', '_')}_notes.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    if st.session_state.pdf_downloaded:
        st.success("✅ PDF downloaded! The Generate button has been unlocked.")

    st.markdown("---")
    st.markdown("#### 📖 Preview Notes Online:")
    st.markdown(st.session_state.generated_notes)
