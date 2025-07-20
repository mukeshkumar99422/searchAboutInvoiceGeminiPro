import streamlit as st
from dotenv import load_dotenv
load_dotenv()
import os

from PIL import Image
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    Part,
    ThinkingConfig,
)

import pandas as pd
import io

client = genai.Client()
model = "gemini-2.5-pro"

st.set_page_config(page_title="Multilanguage Invoice Chatot", page_icon="📊")
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

# --- Sidebar: Language & Chat History ---
with st.sidebar:
    # st.header("🌐 Language Settings")
    language = st.selectbox("🌐 Output Language:", ["English","Assamese", "Bengali", "Bhojpuri", "Gujarati", "Hindi", "Kannada", "Khortha", "Malayalam", "Marathi", "Odia", "Punjabi", "Rajasthani", "Tamil", "Telugu", "Urdu"], index=0)
    st.markdown("---")

# --- Hide Streamlit UI ---
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
section.main > div:first-child {
    padding-top: 0rem;
}
</style>
""", unsafe_allow_html=True)


# --- Upload Invoice Image ---
uploaded_file = st.file_uploader("📤 Upload an invoice image", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
    st.session_state.uploaded_file = uploaded_file
    st.session_state.last_image_data = uploaded_file.getvalue()

# --- Display Image ---
if st.session_state.uploaded_file is not None:
    with st.expander("📎 View Uploaded Invoice"):
        image = Image.open(st.session_state.uploaded_file)
        st.image(image, caption="🖼️ Uploaded Invoice", use_container_width=True)

# --- Extract Item Data from Invoice and Save to CSV ---
def extract_items_to_csv(image_data,file_type,client,model):
    extract_prompt = f"""
    You are an expert at reading invoices.
    From the uploaded image, extract the list of items in tabular form with these columns:
    Item Number, Item Name, Price.
    Also extract the Total Bill amount.
    Return the output strictly in this format:

    Item Number,Item Name,Price
    1,Paracetamol 500mg,50
    2,Aspirin 100mg,100
    ...
    ,Total,150

    items name should be in {language} language.

    Only return this structured CSV-style text. No explanation.
    """
    contents = [
        extract_prompt,
        Part.from_bytes(data=image_data, mime_type=file_type),
    ]
    response = client.models.generate_content(
        model=model,
        config=GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=128)),
        contents=contents
    )

    raw_text = response.text if hasattr(response, "text") else str(response)

    # Convert text to dataframe
    try:
        df = pd.read_csv(io.StringIO(raw_text))
        csv_data = df.to_csv(index=False).encode("utf-8")
        return csv_data
    except Exception as e:
        return f"Error processing invoice: {e}"


csv_file = None
if st.session_state.last_image_data and st.session_state.uploaded_file:
    csv_file = extract_items_to_csv(
        st.session_state.last_image_data,
        st.session_state.uploaded_file.type,
        client,
        model
    )

# -- add download button for CSV file ---
if csv_file:
    with st.sidebar:
        st.markdown("### Extracted Items")
        st.download_button(
            label="Download as CSV",
            data=csv_file,
            file_name="extracted_items.csv",
            mime="text/csv"
        )
        st.markdown("---")
                                                                                 
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
"""

# --- Build Translation Prompt ---
def build_translation_prompt(lang):
    return f"""
You are a professional translator.
Translate the response to {lang} language only. Keep numbers and technical terms (like GSTIN, PAN, amounts) unchanged.
Don't mention that this is a translation — give only the translated output.
"""

# --- Gemini Call for New Question ---
if submitted and user_input:
    if st.session_state.last_image_data is None:
        st.warning("Please upload an invoice image before starting the conversation.")
    else:
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

         # Display current question + answer below form
        st.success(response)

        st.session_state.chat_history.insert(0, {
            "user": user_input,
            "response": response,
        })
        st.session_state.prev_language = language

# --- Re-translate Chat History if Language Changed ---
if language != st.session_state.prev_language and st.session_state.chat_history:
    translation_prompt = build_translation_prompt(language)
    for msg in st.session_state.chat_history:
        translation_response = client.models.generate_content(
            model=model,
            config=GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=128)),
            contents=[translation_prompt, msg["response"]]
        )
        translated_answer = translation_response.text if hasattr(translation_response, "text") else str(translation_response)
        msg["response"] = translated_answer
    st.session_state.prev_language = language
    st.success(st.session_state.chat_history[0]["response"])

# --- Now render Chat History (after possible translation) ---
with st.sidebar:
    st.markdown("### Chat History")
    for msg in st.session_state.chat_history:
        with st.expander(f"{msg['user'][:30]}..."):
            st.markdown(f"**You:** {msg['user']}")
            st.markdown(f"**Bot:** {msg['response']}")





