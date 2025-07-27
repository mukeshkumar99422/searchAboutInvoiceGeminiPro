import streamlit as st
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import io

# --- import model ---
from google import genai
from google.genai.types import (
    GenerateContentConfig, 
    Part,
    ThinkingConfig,
)

# --- Initialize the Gemini client ---
@st.cache_resource
def get_gemini_client():
    return genai.Client()

client = get_gemini_client()
model = "gemini-2.5-pro"

# --- Load CSS ---
@st.cache_data
def load_custom_css():
    return """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Remove top padding of main body */
    .block-container {
        padding-top: 1rem !important;
    }
    </style>
    """
st.set_page_config(page_title="Multilanguage Invoice Chatot", page_icon="📊")
st.markdown(load_custom_css(), unsafe_allow_html=True)
st.markdown(
    """
    <h1 style='text-align: center;'>BillBot</h1>
    <p style='text-align: center; color: gray;'>Ask questions, get insights — in your language</p>
    """,
    unsafe_allow_html=True
)

# --- Session State Initialization ---
if "prev_language" not in st.session_state:
    st.session_state.prev_language = "English"
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "last_image_data" not in st.session_state:
    st.session_state.last_image_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "csv_file" not in st.session_state:
    st.session_state.csv_file = None
# if "invoice_text" not in st.session_state:
#     st.session_state.invoice_text = None

# --- Sidebar: Language & Chat History ---
with st.sidebar:
    # st.header("🌐 Language Settings")
    language = st.selectbox("🌐 Output Language:", ["English","Assamese", "Bengali", "Bhojpuri", "Gujarati", "Hindi", "Kannada", "Khortha", "Malayalam", "Marathi", "Odia", "Punjabi", "Rajasthani", "Tamil", "Telugu", "Urdu"], index=0)
    st.markdown("---")


# --- Upload Invoice Image ---
if st.session_state.last_image_data is None:
    st.session_state.uploaded_file = st.file_uploader("📤 Upload an invoice image", type=["jpg", "jpeg", "png"])

# --- data in session state ---
if st.session_state.uploaded_file is not None and st.session_state.last_image_data is None:
    st.session_state.last_image_data = st.session_state.uploaded_file.getvalue()
    st.toast("File uploaded successfully!", icon="📁")
    st.rerun()

# --- Extract Item Data from Invoice and Save to CSV ---
def extract_items_to_csv(image_data,file_type,client,model):
    extract_prompt = f"""
    You are an expert at reading invoices.
    From the uploaded image, extract the list of items in tabular form with these columns:
    Item Number, Item Name, Price.
    Also extract the Total Bill amount.
    Return the output strictly in this format:

    Item Number,Item Name,Item Price,Total Tax amount,Total Price
    1,Paracetamol 500mg,50,5,55
    2,Aspirin 100mg,100,10,110
    3,Ibuprofen 200mg,150,0,150
    ...
    ,Total,300,60,315

    Note that is there is no tax on amount then feild value should be 0.

    items name should be in {language} language.

    Only return this structured CSV-style text. No explanation.
    If there are no items, return only one thing that is: "0".
    If the image is not clear, return only one thing that is: "1"
    """
    contents = [
        extract_prompt,
        Part.from_bytes(data=image_data, mime_type=file_type),

    ]
    try:
        response = client.models.generate_content(
            model=model,
            config=GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=128)),
            contents=contents
        )
        raw_text = response.text if hasattr(response, "text") else str(response)

        try:
            if(raw_text.strip() == "0"):
                return "0"
            elif(raw_text.strip() == "1"):
                return "1"
            df = pd.read_csv(io.StringIO(raw_text))
            csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            return csv_data
        except Exception as e:
            return None

    except Exception as e:
        st.toast("Please try after some time.", icon="⌛")
        return None

if st.session_state.csv_file is None and st.session_state.last_image_data and st.session_state.uploaded_file:    
     with st.spinner("Extracting items from invoice... Please wait."):
        st.session_state.csv_file = extract_items_to_csv(
            st.session_state.last_image_data,
            st.session_state.uploaded_file.type,
            client,
            model
        )

# -- add download button for CSV file ---
with st.sidebar:
    st.markdown("## Extracted Items")
    if st.session_state.csv_file == "0":
        st.error("⚠️ No items found in the invoice. Please check the invoice.")
    elif st.session_state.csv_file == "1":
        st.error("⚠️ Items can not be extracted, please upload a clearer image.")
    elif st.session_state.csv_file:
        st.download_button(
            label="Download as CSV",
            data=st.session_state.csv_file,
            file_name="extracted_items.csv",
            mime="text/csv"
        )
    elif st.session_state.last_image_data:
        st.error("🔧 Items not extracted due to some technical issue.")
    else:
        st.error("Upload Invoice first",width=165)
    st.markdown("---")

# # --- Display Image ---
if st.session_state.uploaded_file is not None:
    with st.expander("📎 View Uploaded Invoice"):
        from PIL import Image
        image = Image.open(st.session_state.uploaded_file)
        st.image(image, caption="🖼️ Uploaded Invoice", use_container_width=True)
       
# --- Ask a Question ---
st.markdown("---")
with st.form("chat_form", clear_on_submit=False):
    user_input = st.text_input("Ask something about the invoice:")
    submitted = st.form_submit_button("Send")

# --- Build Prompt ---
def build_prompt():
    return f"""
You are an expert in understanding invoices. 
An image of an invoice will be uploaded,
It may be in any language,
and you will have to answer any question based on the uploaded image.
Avoid using based on the image/invoice provided

You are a professional translator also.
Give the whole answer in {language} language only. Keep technical terms (like numbers, tax IDs, currency) as they are.
Please don't show this is a translation. Just give the translated text.
Note that if image is not about any invoice, then return only one line: "Looks like this is not an invoice" in {language} language.
Also if query is out of context, to invoice , then return only one line: "Please ask about invoice" in {language} language.
"""

# --- Build Translation Prompt ---
def build_translation_prompt(lang):
    return f"""
You are a professional translator.
Translate the response to {lang} language only. Keep numbers and technical terms (like GSTIN, PAN, amounts) unchanged.
Don't mention that this is a translation — give only the translated output.
If the response is already in {lang}, return it as is.
all things should be in {lang} language, including names.
"""

# --- Gemini Call for New Question ---
if submitted and user_input:
    if st.session_state.last_image_data is None:
        st.warning("Please upload an invoice image before starting the conversation.")
    else:
        try:
            with st.spinner("Getting your response ready..."):
                prompt = build_prompt()
                contents = [
                    prompt,
                    Part.from_bytes(data=st.session_state.last_image_data, mime_type=st.session_state.uploaded_file.type),
                    f"User: {user_input}"
                ]
                response = client.models.generate_content(
                    model=model,
                    config=GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=128)),
                    contents=contents
                )
                response = response.text if hasattr(response, "text") else str(response)

                st.success(response)
                st.session_state.chat_history.insert(0, {
                    "user": user_input,
                    "response": response,
                })
                st.session_state.prev_language = language
        except Exception as e:
            st.error("Request limit exceeded. Please wait for a while.", icon="⌛")



# --- Re-translate Chat History if Language Changed ---
if language != st.session_state.prev_language and st.session_state.chat_history:
    translation_prompt = build_translation_prompt(language)
    with st.spinner("Translating..."):
        for msg in st.session_state.chat_history:
            try:
                translation_response = client.models.generate_content(
                    model=model,
                    config=GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=128)),
                    contents=[translation_prompt, msg["response"]]
                )
                translated_answer = translation_response.text if hasattr(translation_response, "text") else str(translation_response)
                msg["response"] = translated_answer
            except Exception as e:
                st.toast("limit exceeded. Please try again later.", icon="⚠️")
                break
    st.session_state.prev_language = language
    st.success(st.session_state.chat_history[0]["response"])


# --- Now render Chat History (after possible translation) ---
with st.sidebar:
    st.markdown("## Chat History")
    for i, msg in enumerate(st.session_state.chat_history):
        with st.expander(f"{msg['user'][:30]}...", expanded=(i == 0)):
            st.markdown(f"**You:** {msg['user']}  \n**Bot:** {msg['response']}")

# --- Reset Button (Bottom Right Corner) ---
reset_css = """
    <style>
    .stButton > button.reset-btn {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #e63946;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 25px;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        z-index: 9999;
        cursor: pointer;
    }
    </style>
"""
st.markdown(reset_css, unsafe_allow_html=True)

reset_placeholder = st.empty()
btn=st.button("Reset All", key="reset_button", help="Clear all data", type="primary")
with reset_placeholder.container():
    if btn:
        # Clear everything from session_state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        # Remove uploaded file and forcefully clear widgets
        reset_placeholder.empty()
        uploaded_file= None
        
        st.rerun()


