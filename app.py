import os
import io
import streamlit as st
import streamlit.components.v1 as components
import docx
import pypdf
from fpdf import FPDF
from google import genai
from google.genai import types

# Declare browser localStorage custom component
_COMPONENT_PATH = os.path.join(os.path.dirname(__file__), "components", "local_storage")
local_storage_comp = components.declare_component("local_storage", path=_COMPONENT_PATH)

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
    
    # Handle browser localStorage communication
    if "ls_action" not in st.session_state:
        st.session_state.ls_action = "read"
    if "ls_key_value" not in st.session_state:
        st.session_state.ls_key_value = ""

    browser_stored_key = local_storage_comp(
        action=st.session_state.ls_action,
        key_value=st.session_state.ls_key_value,
        key="ls_component_widget"
    )

    # Reset action to "read" after save/clear
    if st.session_state.ls_action != "read":
        st.session_state.ls_action = "read"
        st.session_state.ls_key_value = ""

    env_api_key = os.environ.get("GEMINI_API_KEY", "")
    default_key_val = browser_stored_key or env_api_key or ""

    api_key_input = st.text_input(
        "Gemini API Key",
        value=default_key_val,
        type="password",
        help="Saved in your browser's localStorage for future sessions."
    )

    clean_key_check = api_key_input.strip().strip("'\"")

    col_ls1, col_ls2 = st.columns(2)
    with col_ls1:
        if st.button("💾 Save Key", help="Save key to browser's localStorage and local .env", use_container_width=True):
            if clean_key_check:
                st.session_state.ls_action = "save"
                st.session_state.ls_key_value = clean_key_check
                try:
                    with open(".env", "w", encoding="utf-8") as f:
                        f.write(f"GEMINI_API_KEY={clean_key_check}\n")
                except Exception:
                    pass
                st.rerun()

    with col_ls2:
        if st.button("🗑️ Forget", help="Clear key from browser's localStorage", use_container_width=True):
            st.session_state.ls_action = "clear"
            st.session_state.ls_key_value = ""
            try:
                if os.path.exists(".env"):
                    os.remove(".env")
            except Exception:
                pass
            st.rerun()

    if clean_key_check:
        if not clean_key_check.isascii():
            st.error("⚠️ Invalid characters detected. Please paste only your clean API key.")
        elif not clean_key_check.startswith("AIza"):
            st.info("ℹ️ Google API keys typically begin with `AIza...`.")
        else:
            st.success("✅ Key stored in browser (localStorage)")

    model_choice = st.selectbox(
        "Gemini Model",
        options=["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        index=0,
        help="Recommended: gemini-3.8-flash (auto-switches to 2.0-flash if busy)"
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

# Optional Page Selection for PDFs (Great for fast processing of large textbooks)
selected_page_range = None
if uploaded_file and uploaded_file.name.lower().endswith(".pdf"):
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(uploaded_file.getvalue()))
        total_pages = len(pdf_reader.pages)
        if total_pages > 1:
            col_p1, col_p2 = st.columns([1, 1])
            with col_p1:
                analyze_all = st.checkbox("Analyze all pages", value=(total_pages <= 10))
            with col_p2:
                st.caption(f"📄 Detected **{total_pages} pages** in document.")

            if not analyze_all:
                selected_page_range = st.slider(
                    "Select page range to analyze (⚡ much faster for textbooks):",
                    min_value=1,
                    max_value=total_pages,
                    value=(1, min(10, total_pages)),
                    help="For large textbooks (e.g. 100+ pages), picking the specific chapter or lesson generates notes in seconds."
                )
    except Exception:
        pass

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
                    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                    total_pdf_pages = len(reader.pages)

                    if selected_page_range:
                        pages_to_process = list(range(selected_page_range[0] - 1, selected_page_range[1]))
                    else:
                        pages_to_process = list(range(total_pdf_pages))

                    # 1. Try fast text extraction first (10x faster than sending raw visual pages)
                    extracted_text = ""
                    try:
                        text_pages = []
                        for idx in pages_to_process:
                            t = reader.pages[idx].extract_text()
                            if t and t.strip():
                                text_pages.append(f"--- Page {idx + 1} ---\n{t}")
                        extracted_text = "\n\n".join(text_pages).strip()
                    except Exception:
                        extracted_text = ""

                    if len(extracted_text) > 100:
                        # Digital PDF: Send pure text for near-instant processing
                        contents = [f"Document Content:\n{extracted_text}\n\nTask:\n{prompt_text}"]
                    else:
                        # Scanned PDF: Slice only the selected pages to save bandwidth & processing time
                        writer = pypdf.PdfWriter()
                        for idx in pages_to_process:
                            writer.add_page(reader.pages[idx])
                        buf = io.BytesIO()
                        writer.write(buf)
                        sliced_pdf_bytes = buf.getvalue()

                        pdf_part = types.Part.from_bytes(data=sliced_pdf_bytes, mime_type="application/pdf")
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

                # Auto-save valid key to browser localStorage and local .env
                if clean_key_check:
                    st.session_state.ls_action = "save"
                    st.session_state.ls_key_value = clean_key_check
                    try:
                        with open(".env", "w", encoding="utf-8") as f:
                            f.write(f"GEMINI_API_KEY={clean_key_check}\n")
                    except Exception:
                        pass

                # Models to try in order (if primary model suffers 503 high demand spike, auto-fallback)
                models_to_try = [model_choice]
                for fb in ["gemini-2.0-flash", "gemini-1.5-flash"]:
                    if fb not in models_to_try:
                        models_to_try.append(fb)

                stream_container = st.empty()
                status_box = st.empty()
                accumulated_text = []
                success = False
                last_error = None

                for current_model in models_to_try:
                    try:
                        if current_model != model_choice:
                            status_box.warning(
                                f"⚠️ `{model_choice}` is experiencing temporary high demand (503) on Google's servers. "
                                f"Automatically switching to `{current_model}`..."
                            )

                        gen_config = None
                        if "flash" in current_model.lower() and ("2.5" in current_model.lower() or "3.8" in current_model.lower()):
                            gen_config = types.GenerateContentConfig(
                                thinking_config=types.ThinkingConfig(thinking_budget=0)
                            )

                        accumulated_text = []
                        response_stream = client.models.generate_content_stream(
                            model=current_model,
                            contents=contents,
                            config=gen_config
                        )

                        for chunk in response_stream:
                            if chunk.text:
                                accumulated_text.append(chunk.text)
                                stream_container.markdown("".join(accumulated_text))

                        generated_text = "".join(accumulated_text).strip()
                        if generated_text:
                            success = True
                            if current_model != model_choice:
                                status_box.success(f"✅ Notes successfully generated using `{current_model}`!")
                            break

                    except Exception as err:
                        err_str = str(err)
                        last_error = err
                        # If 503 UNAVAILABLE or 429 high demand / capacity spike, fall back to next model
                        if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "high demand" in err_str.lower():
                            continue
                        else:
                            raise err

                if not success:
                    if last_error:
                        raise last_error
                    else:
                        raise RuntimeError("No response received from any model.")

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
