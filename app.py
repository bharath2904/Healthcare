from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
from PIL import Image # Import Pillow for image processing
import io # For handling image bytes

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is not set. Please ensure it's in your .env file and python-dotenv is installed."
    )

genai.configure(api_key=GEMINI_API_KEY)

# Initialize models
text_only_model = None
vision_model = None

try:
    # Attempt to load a multimodal model first for image/text capabilities
    vision_model = genai.GenerativeModel("gemini-2.5-flash") # Or "gemini-pro-vision"
    print("Multimodal model 'gemini-1.5-flash' loaded successfully.")
except Exception as e:
    print(
        f"Warning: 'gemini-1.5-flash' failed to load ({e}). Trying 'gemini-pro-vision'..."
    )
    try:
        vision_model = genai.GenerativeModel("gemini-2.5-flash")
        print("Multimodal model 'gemini-pro-vision' loaded successfully.")
    except Exception as e:
        print(f"Warning: No multimodal model could be loaded. Image input will not work. Error: {e}")

try:
    # Always try to load a text-only model as a fallback or for text-only inputs
    text_only_model = genai.GenerativeModel("gemini-2.5-flash")
    print("Text-only model 'gemini-pro' loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: Failed to initialize 'gemini-pro' for text-only input. Error: {e}")
    # If text-only model fails, and no vision model, then no AI will work.
    if vision_model is None:
        raise ValueError("No generative AI model could be initialized. Please check your API key and model availability.")


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/diagnose", methods=["POST"])
def diagnose():
    user_problem = request.form.get("problem", "") # Use request.form for multipart
    uploaded_file = request.files.get("image")

    # Determine which model to use
    current_model = None
    model_name_used = "N/A" # For logging

    if uploaded_file and vision_model:
        current_model = vision_model
        model_name_used = vision_model.model_name
    elif text_only_model:
        current_model = text_only_model
        model_name_used = text_only_model.model_name
    else:
        return jsonify({
            'severity': 'Error',
            'advice': 'No suitable AI model could be loaded on the server. Please contact support.',
            'disclaimer': 'Disclaimer: This AI advice is for informational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of a qualified healthcare provider for any medical concerns.',
        }), 500


    if not user_problem and not uploaded_file:
        return (
            jsonify(
                {
                    "severity": "Error",
                    "advice": "Please describe your health problem or upload an image.",
                    "disclaimer": "Disclaimer: This AI advice is for informational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of a qualified healthcare provider for any medical concerns.",
                }
            ),
            400,
        )
    
    # --- AI Integration with Gemini API ---
    # Construct a comprehensive prompt to guide the AI's response.
    prompt_parts = []
    
    prompt = f"""
    You are an AI health assistant named HealGenie. Your primary goal is to provide preliminary, general health advice based on the user's described symptoms and/or provided image, and to guide them on the appropriate course of action.

    Categorize the problem into one of three severities:
    1.  **Basic/Minor:** Can be managed with home remedies or self-care.
    2.  **Moderate:** Requires consulting a general practitioner or clinic.
    3.  **Severe/Emergency:** Requires immediate professional medical attention (e.g., emergency room, calling emergency services).

    Follow these rules strictly:
    -   **Always start your response with "Severity: [Basic/Moderate/Severe]" on a new line.**
    -   **Then, provide "Advice:" on a new line, followed by detailed, structured advice.**
    -   Use Markdown for formatting the advice (e.g., bullet points for lists, bold for emphasis, headings for sections).
    -   For Basic problems, suggest clear, actionable home care tips, over-the-counter remedies, or general wellness advice. Include practical steps.
    -   For Moderate problems, advise seeking a doctor, and suggest what specific information to gather (e.g., symptom history, duration, associated factors, current medications). Recommend specific next steps.
    -   For Severe problems, issue a strong, urgent warning for immediate medical attention (e.g., call emergency services, go to an ER). Emphasize *not to delay* and why.
    -   **Be cautious.** If in doubt about severity or if the image/description is unclear, err on the side of caution and recommend professional medical consultation.
    -   **Do NOT provide a diagnosis.** Your role is advisory on the *next steps* for care.
    -   **Do NOT provide specific dosages for prescription medications.**
    -   Keep the advice concise but informative, using clear, simple language.
    -   **If an image is provided, incorporate insights from the image into your advice.** If no image, state "Based on your description..."

    ---
    Example of desired output format:
    Severity: Basic
    Advice:
    Based on your description of a common cold:
    *   **Rest:** Get plenty of sleep to help your body recover.
    *   **Fluids:** Drink lots of water, herbal teas, and broths to stay hydrated.
    *   **Over-the-Counter:** Consider decongestants or pain relievers for symptom relief.
    *   **When to See a Doctor:** If symptoms worsen or persist for more than a week, consult a general practitioner.

    User's Health Problem Description: "{user_problem}"
    """
    
    prompt_parts.append(prompt)

    if uploaded_file and vision_model:
        # Read the image file into a BytesIO object
        image_stream = io.BytesIO(uploaded_file.read())
        # Open the image using Pillow
        img = Image.open(image_stream)
        prompt_parts.append(img)
        print(f"Processing request with image (using {model_name_used}).")
    elif uploaded_file and not vision_model:
        # This case should ideally be caught by the model initialization check,
        # but as a safeguard, if image uploaded but vision_model is None.
        return jsonify({
            'severity': 'Error',
            'advice': 'Image upload is not supported because the multimodal AI model failed to load. Please try again with text only.',
            'disclaimer': 'Disclaimer: This AI advice is for informational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of a qualified healthcare provider for any medical concerns.',
        }), 500
    else:
        print(f"Processing request with text only (using {model_name_used}).")


    try:
        response = current_model.generate_content(prompt_parts)
        ai_response_text = response.text

        severity = "Unknown"
        advice = "Could not parse AI advice. Please consult a medical professional."

        # Improved parsing logic for structured markdown output
        if "Severity:" in ai_response_text and "Advice:" in ai_response_text:
            try:
                # Find positions
                severity_start_idx = ai_response_text.find("Severity:")
                advice_start_idx = ai_response_text.find("Advice:")

                # Extract severity
                if severity_start_idx != -1:
                    severity_line_end_idx = ai_response_text.find("\n", severity_start_idx)
                    severity = ai_response_text[severity_start_idx + len("Severity:"):severity_line_end_idx].strip()

                # Extract advice
                if advice_start_idx != -1:
                    advice = ai_response_text[advice_start_idx + len("Advice:"):].strip()
                    # Clean up any potential extra "Severity:" if AI generated it again
                    if "Severity:" in advice:
                        advice = advice.split("Severity:", 1)[0].strip()

            except Exception as parse_e:
                print(f"Error parsing structured AI response: {parse_e}")
                print(f"Full AI response was: \n{ai_response_text}")
                # Fallback to full text if structured parsing fails
                severity = "Unknown"
                advice = ai_response_text
        else:
            # If the expected keywords are not found, use the full text as advice
            # and try to infer severity
            if (
                "severe" in ai_response_text.lower()
                or "emergency" in ai_response_text.lower()
            ):
                severity = "Severe"
            elif (
                "doctor" in ai_response_text.lower()
                or "medical professional" in ai_response_text.lower()
            ):
                severity = "Moderate"
            else:
                severity = "Basic"
            advice = ai_response_text # Use the full AI response as advice if parsing failed

    except genai.types.BlockedPromptException as block_e:
        print(f"Gemini API blocked prompt: {block_e}")
        severity = "Blocked"
        advice = "Your input was blocked by the safety filters. Please rephrase or provide different information. We cannot provide advice for potentially sensitive content."
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        severity = "Error"
        advice = "An error occurred while connecting to the AI. Please try again later. Ensure your API key is correct and you have an active internet connection."

    final_disclaimer = "Disclaimer: This AI advice is for informational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of a qualified healthcare provider for any medical concerns."

    return jsonify(
        {"severity": severity, "advice": advice, "disclaimer": final_disclaimer}
    )

if __name__ == "__main__":
    app.run()