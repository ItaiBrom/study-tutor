import streamlit as st
import fitz  # PyMuPDF
from google import genai # The new library
from PIL import Image
import random
import os

# --- Configuration ---
API_KEY = None 

# chosen_model = 'gemini-2.0-flash-lite'
chosen_model = 'gemini-2.5-flash'

# --- Helper Functions ---
def get_gemini_client(api_key):
    """Initializes the new GenAI client"""
    return genai.Client(api_key=api_key)

def load_pdf(uploaded_file):
    """Loads the PDF file into memory (RAM only)"""
    if uploaded_file is not None:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        return doc
    return None

def get_page_image(doc, page_num):
    """Converts a specific PDF page into an Image object"""
    page = doc.load_page(page_num)
    # Matrix(2, 2) doubles resolution for clearer text/graphs
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img

# --- Streamlit UI Layout ---
st.set_page_config(page_title="Gynecology AI Tutor", layout="wide")

st.title("AI Tutor")
st.markdown("""
**Status:** Using updated `google-genai` SDK.
This tool runs locally. Only the specific page being tested is sent to the AI for analysis.
""")

# Sidebar
with st.sidebar:
    st.header("Settings")
    user_api_key = st.text_input("Enter Google AI Studio API Key", type="password")
    if user_api_key:
        API_KEY = user_api_key
    
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

# Main Logic
if uploaded_file and API_KEY:
    doc = load_pdf(uploaded_file)
    client = get_gemini_client(API_KEY)
    
    if st.button("🎲 Generate New Random Question", type="primary"):
        st.session_state.feedback = None
        st.session_state.current_question = None
        
        # 1. Random Page
        total_pages = len(doc)
        random_page_num = random.randint(0, total_pages - 1)
        st.session_state.current_page_num = random_page_num
        
        # 2. Image Conversion
        img = get_page_image(doc, random_page_num)
        st.session_state.page_image = img
        
        # 3. Generate Question (New SDK Syntax)
        with st.spinner(f'Analyzing page {random_page_num + 1}...'):
            # prompt = """
            # You are a strict Gynecology Professor. 
            # Analyze the provided textbook page image.
            
            # Task:
            # 1. Formulate a challenging OPEN-ENDED question based EXCLUSIVELY on this page.
            # 2. If there are graphs/tables, ask about the data.
            
            # Output Language: English.
            # """

            prompt = """
            You are a strict Gynecology Professor. 
            Analyze the provided textbook page image.
            
            Task:
            1. Formulate a short question based EXCLUSIVELY on this page. You can give a multiple choice question or open-ended question.
            2. If there are graphs/tables, ask about the data.
            
            Output Language: Hebrew.
            """
            
            # The new SDK call structure
            response = client.models.generate_content(
                model=chosen_model,
                contents=[prompt, img]
            )
            st.session_state.current_question = response.text

    # Display Question
    if st.session_state.current_question:
        st.info(f"**Question (Page {st.session_state.current_page_num + 1}):**\n\n{st.session_state.current_question}")
        
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
    st.info("👈 Upload PDF in sidebar.")