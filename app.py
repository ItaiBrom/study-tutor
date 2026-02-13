import streamlit as st
import fitz  # PyMuPDF
from google import genai
from PIL import Image
import random
import os

# --- CONFIGURATION ---
DEFAULT_PDF_NAME = "beckmann_and_lings_obstetrics_and_gynecology_9th_edition.pdf"
CHOSEN_MODEL = 'gemini-2.5-flash'

# --- HELPER FUNCTIONS ---
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)

def get_page_image(doc, page_num):
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img

def get_random_chapter_page(doc):
    toc = doc.get_toc()
    if not toc:
        return random.randint(0, len(doc) - 1), "Unknown Chapter (No ToC)"
    
    chapters = [item for item in toc if item[0] <= 2]
    if not chapters:
        return random.randint(0, len(doc) - 1), "Random Page"

    idx = random.randint(0, len(chapters) - 1)
    title = chapters[idx][1]
    start = chapters[idx][2] - 1
    
    if idx < len(chapters) - 1:
        end = chapters[idx + 1][2] - 2
    else:
        end = len(doc) - 1
        
    if end < start: end = start
    return random.randint(start, end), title

# --- UI SETUP ---
st.set_page_config(page_title="AI Tutor", layout="wide")
st.markdown("""
<style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)

st.title("AI Tutor")

# --- 1. LOAD PDF LOGIC ---
doc = None
if os.path.exists(DEFAULT_PDF_NAME):
    st.success(f"✅ Found local file: {DEFAULT_PDF_NAME}")
    doc = fitz.open(DEFAULT_PDF_NAME)
else:
    st.warning(f"⚠️ Could not find '{DEFAULT_PDF_NAME}'")
    uploaded = st.file_uploader("Upload PDF manually", type=["pdf"])
    if uploaded:
        doc = fitz.open(stream=uploaded.read(), filetype="pdf")

# --- 2. SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    user_key = st.text_input("API Key", type="password")
    
    if st.button("Reset App"):
        st.session_state.clear()
        st.rerun()

# --- 3. MAIN APP LOGIC ---
if doc and user_key:
    client = get_gemini_client(user_key)
    
    if st.button("🎲 Generate Random Question", type="primary"):
        st.session_state.feedback = None
        st.session_state.current_question = None
        
        # 1. Select Page & Chapter
        page, chapter = get_random_chapter_page(doc)
        st.session_state.page = page
        st.session_state.chapter = chapter
        st.session_state.img = get_page_image(doc, page)

        # 2. Select Question Type
        q_types = ["Multiple Choice", "Fill-in-the-Blank", "Open-Ended"]
        selected_type = random.choice(q_types)
        st.session_state.q_type = selected_type
        
        with st.spinner(f"Generating {selected_type} Question from '{chapter}'..."):
            
            # --- DYNAMIC PROMPTS ---
            base_prompt = f"""
            You are a Gynecology Professor. 
            Topic: {chapter}.
            Language: Hebrew. Make sure you translate the medical terms correctly, including inferring the correct medical practice terms.
            Based EXCLUSIVELY on the provided image:
            """

            if selected_type == "Multiple Choice":
                specific_instruction = """
                Create a challenging Multiple Choice Question (MCQ).
                1. Provide the question stem.
                2. Provide 4 distinct options labeled A, B, C, D.
                3. Do NOT reveal the correct answer yet.
                4. Ensure the options are plausible, and provide enough context.
                """
            elif selected_type == "Fill-in-the-Blank":
                specific_instruction = """
                Create a 'Fill-in-the-Blank' sentence.
                1. Take a key clinical sentence from the text.
                2. Replace the most critical medical term (e.g., drug name, diagnosis, statistic) with '_______'.
                3. Do NOT reveal the missing term.
                """
            else: # Open-Ended
                specific_instruction = """
                Create a short, difficult Open-Ended question.
                1. Ask for a diagnosis, a list of symptoms, or an explanation of a mechanism shown in the text.
                2. If there is a table, ask about an item from the table. Provide the column and row headers regarding the question.
                3. If there is a graph, ask to interpret the data.
                4. If tere are both table and graph, choose one about which you form the question.
                """

            full_prompt = base_prompt + specific_instruction

            res = client.models.generate_content(
                model=CHOSEN_MODEL,
                contents=[full_prompt, st.session_state.img]
            )
            st.session_state.current_question = res.text

    # Show Question (RTL)
    if 'current_question' in st.session_state and st.session_state.current_question:
        
        # Display the Type badge
        st.caption(f"Question Type: **{st.session_state.q_type}**")

        st.markdown(f"""
        <div style="direction: rtl; text-align: right; background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-right: 5px solid #ff4b4b;">
            <p style="font-weight: bold; color: #555;">נושא: {st.session_state.chapter}</p>
            <div style="font-size: 1.1em; white-space: pre-wrap;">{st.session_state.current_question}</div>
        </div>
        """, unsafe_allow_html=True)
        
        ans = st.text_area("Your Answer:", height=100)
        
        if st.button("Check Answer"):
            with st.spinner("Grading..."):
                grade_prompt = f"""
                You are grading a student's answer.
                
                Question Type: {st.session_state.q_type}
                Question: {st.session_state.current_question}
                Student Answer: {ans}
                
                Task:
                1. Verify the answer against the image provided.
                2. If it is Multiple Choice, check if they selected the correct option letter or text.
                3. If it is Fill-in-the-Blank, check if they found the exact missing term.
                4. Provide the correct answer and a brief explanation.
                
                Output Language: Hebrew.
                Use bold text for the final verdict (Correct/Incorrect).
                """
                res = client.models.generate_content(
                    model=CHOSEN_MODEL,
                    contents=[grade_prompt, st.session_state.img]
                )
                st.session_state.feedback = res.text

    # Show Feedback (RTL)
    if 'feedback' in st.session_state and st.session_state.feedback:
        st.markdown("### משוב:")
        st.markdown(f"""
        <div style="direction: rtl; text-align: right; background-color: #d4edda; padding: 20px; border-radius: 10px; border-right: 5px solid #28a745; color: #155724;">
            {st.session_state.feedback.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)
        
        st.image(st.session_state.img, caption="Source Page", use_container_width=True)

elif not doc:
    st.error(f"Please put '{DEFAULT_PDF_NAME}' in the app folder.")
elif not user_key:
    st.warning("Please enter API Key in sidebar.")