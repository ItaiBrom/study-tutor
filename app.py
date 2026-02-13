import streamlit as st
import fitz  # PyMuPDF
from google import genai # The new library
from PIL import Image
import random
import os

# --- Configuration ---
API_KEY = None 

# --- DEBUG CONFIGURATION ---
# Put the name of your local PDF file here for rapid testing
DEBUG_PDF_PATH = "beckmann_and_lings_obstetrics_and_gynecology_9th_edition.pdf" 

chosen_model = 'gemini-2.5-flash'

# --- Helper Functions ---
def get_gemini_client(api_key):
    """Initializes the new GenAI client"""
    return genai.Client(api_key=api_key)

def load_pdf(file_stream):
    """Loads the PDF file into memory (RAM only)"""
    if file_stream is not None:
        # We read the stream bytes so PyMuPDF can handle both 
        # Streamlit UploadedFile and standard Python File Objects
        file_bytes = file_stream.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return doc
    return None

def get_page_image(doc, page_num):
    """Converts a specific PDF page into an Image object"""
    page = doc.load_page(page_num)
    # Matrix(2, 2) doubles resolution for clearer text/graphs
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img

def get_random_chapter_page(doc):
    """
    Tries to find the Table of Contents (ToC).
    Returns: (page_number, chapter_title)
    """
    toc = doc.get_toc()
    
    # If PDF has no ToC, fallback to completely random page
    if not toc:
        total_pages = len(doc)
        return random.randint(0, total_pages - 1), "Unknown Chapter (No ToC found)"
    
    # Filter ToC to keep only Level 1 or 2 headers (Chapters)
    # toc structure: [level, title, page_num]
    chapters = [item for item in toc if item[0] <= 2] 
    
    if not chapters:
        # Fallback if filtering failed
        return random.randint(0, len(doc) - 1), "Random Page"

    # 1. Pick a random chapter
    chapter_index = random.randint(0, len(chapters) - 1)
    selected_chapter = chapters[chapter_index]
    
    chapter_title = selected_chapter[1]
    start_page = selected_chapter[2] - 1 # PyMuPDF pages are 0-indexed
    
    # 2. Find the end page (it's the start of the next chapter)
    if chapter_index < len(chapters) - 1:
        end_page = chapters[chapter_index + 1][2] - 2
    else:
        end_page = len(doc) - 1
        
    # Validation to prevent errors if a chapter is just 1 page
    if end_page < start_page:
        end_page = start_page

    # 3. Pick a random page WITHIN this chapter
    random_page_num = random.randint(start_page, end_page)
    
    return random_page_num, chapter_title

# --- Streamlit UI Layout ---
st.set_page_config(page_title="AI Tutor", layout="wide")

st.title("AI Tutor")
st.caption(f"Model: {chosen_model}")

# Sidebar
with st.sidebar:
    st.header("Settings")
    user_api_key = st.text_input("Enter Google AI Studio API Key", type="password")
    if user_api_key:
        API_KEY = user_api_key
    
    # --- LOGIC CHANGE: Check for local debug file first ---
    uploaded_file = None
    
    if os.path.exists(DEBUG_PDF_PATH):
        st.success(f"🛠️ Debug Mode: Auto-loaded '{DEBUG_PDF_PATH}'")
        # Open the local file in binary read mode
        uploaded_file = open(DEBUG_PDF_PATH, "rb")
    else:
        # Fallback to standard uploader if debug file is missing
        uploaded_file = st.file_uploader("Upload Textbook (PDF)", type=["pdf"])
    
    st.divider()
    if st.button("Reset / Clear History"):
        st.session_state.clear()
        st.rerun()

# Session State
if 'current_page_num' not in st.session_state:
    st.session_state.current_page_num = None
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'page_image' not in st.session_state:
    st.session_state.page_image = None
if 'feedback' not in st.session_state:
    st.session_state.feedback = None
if 'current_chapter' not in st.session_state:
    st.session_state.current_chapter = None

# Main Logic
if uploaded_file and API_KEY:
    doc = load_pdf(uploaded_file)
    client = get_gemini_client(API_KEY)
    
    if st.button("🎲 Generate New Random Question", type="primary"):
        st.session_state.feedback = None
        st.session_state.current_question = None
        
        # 1. Get page from a specific chapter
        page_num, chapter_title = get_random_chapter_page(doc)
        st.session_state.current_page_num = page_num
        st.session_state.current_chapter = chapter_title
        
        # 2. Image Conversion
        img = get_page_image(doc, page_num)
        st.session_state.page_image = img
        
        # 3. Generate Question
        with st.spinner(f'Analyzing page {page_num + 1} ({chapter_title})...'):
            prompt = f"""
            You are a Gynecology Professor. 
            The student is being tested on the chapter: "{chapter_title}".
            Analyze the provided textbook page image.
            
            Task:
            1. Formulate a short question based EXCLUSIVELY on this page. You can give a multiple choice question or open-ended question.
            2. If there are graphs/tables, ask about the data.
            3. Context: The topic is {chapter_title}.

            Output Language: Hebrew.
            """
            
            response = client.models.generate_content(
                model=chosen_model,
                contents=[prompt, img]
            )
            st.session_state.current_question = response.text

    # Display Question
    if st.session_state.current_question:
        st.info(f"**Topic:** {st.session_state.current_chapter}\n\n**Question (Page {st.session_state.current_page_num + 1}):**\n\n{st.session_state.current_question}")
        
        user_answer = st.text_area("Your Answer:", height=150)
        
        if st.button("Submit & Grade"):
            if user_answer:
                with st.spinner('Grading...'):
                    grade_prompt = f"""
                    You are grading a resident's answer.
                    Question: {st.session_state.current_question}
                    Answer: {user_answer}
                    
                    Task:
                    Compare the answer to the image provided. Correct errors based ONLY on the image.
                    Output Language: Hebrew.
                    """
                    
                    response = client.models.generate_content(
                        model=chosen_model,
                        contents=[grade_prompt, st.session_state.page_image]
                    )
                    st.session_state.feedback = response.text
            else:
                st.warning("Please write an answer.")

    # Display Feedback
    if st.session_state.feedback:
        st.success("📝 Feedback:")
        st.markdown(st.session_state.feedback)
        st.image(st.session_state.page_image, caption=f"Source: Page {st.session_state.current_page_num + 1}", use_container_width=True)

elif not API_KEY:
    st.warning("👈 Enter API Key in sidebar.")
elif not uploaded_file:
    st.info(f"👈 Please place '{DEBUG_PDF_PATH}' in the folder OR upload a PDF in sidebar.")