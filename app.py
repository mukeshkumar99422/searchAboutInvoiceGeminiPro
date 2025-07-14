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

# ✅ Gemini client setup (picks key from .env via GEMINI_API_KEY)
client = genai.Client()
model = "gemini-2.5-pro"

# ✅ Page configuration and app heading
st.set_page_config(page_title="Multilanguage Invoice Extractor", page_icon="🔍")
st.title("Multilanguage Invoice Extractor")
# ✅ Upload image
uploaded_file = st.file_uploader("📤 Upload an invoice image", type=["jpg", "jpeg", "png"])

# ✅ Display image if uploaded
image_data = None
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="🖼️ Uploaded Invoice", use_container_width =True)

# ✅ Ask question only after image upload
input_question = st.text_input("💬 What do you want to ask about this invoice?")

# ✅ Static prompt
input_prompt = """
You are an expert in understanding invoices. 
An image of an invoice will be uploaded,
It may be in any language,
and you will have to answer any question based on the uploaded image.
Avoid using based on the image/invoice provided
"""

# ✅ Submit button
submit = st.button("Tell me about the invoice...")

# ✅ image data extraction
def input_image_data(uploaded_file):
    if uploaded_file is not None:
        bytes_data=uploaded_file.getvalue()
        return bytes_data
    else:
        raise FileNotFoundError("No file uploaded!")


# ✅ Run Gemini only if submit clicked

# if (uploaded_file is not None and input_question) and (submit or not submit):
if submit or (uploaded_file is not None and input_question):
    if(uploaded_file is None):
        st.info("👆 Please upload an invoice image to begin.")
    elif not input_question:
        st.warning("❗ Please enter a question about the invoice.")
    else:
        image_data = input_image_data(uploaded_file)
        file_type = uploaded_file.type
        thinking_config = ThinkingConfig(thinking_budget=128)

        response = client.models.generate_content(
            model=model,
            config=GenerateContentConfig(thinking_config=thinking_config),
            contents=[
                input_prompt,
                Part.from_bytes(data=image_data, mime_type=file_type),
                input_question,
            ]
        )

        st.markdown(response.text if hasattr(response, "text") else str(response))
elif uploaded_file is None:
    st.info("👆 Please upload an invoice image to begin.")
elif submit and input_question is not None:
    st.warning("❗ Please enter a question about the invoice.")
