from flask import Flask, request, render_template
from google.cloud import speech_v1p1beta1 as speech, storage
from pydub import AudioSegment
import os
import ollama

app = Flask(__name__)

# Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\krish\OneDrive\Desktop\Credenz\fluent-fortress-432709-p3-f4e48f54942a.json"

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

BUCKET_NAME = "webweaver"

def convert_audio(file_path):
    """Convert audio to WAV format with 16kHz sample rate."""
    audio = AudioSegment.from_file(file_path)
    wav_path = file_path.rsplit(".", 1)[0] + "_converted.wav"
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(wav_path, format="wav")
    return wav_path

def get_audio_duration(file_path):
    """Get the duration of the audio file in seconds."""
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000  # Convert ms to sec

def upload_to_gcs(file_path):
    """Upload audio file to Google Cloud Storage and return its GCS URI."""
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob_name = os.path.basename(file_path)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(file_path)
    return f"gs://{BUCKET_NAME}/{blob_name}"

def transcribe_audio(file_path, language):
    """Transcribe audio using Google Speech-to-Text."""
    client = speech.SpeechClient()
    duration = get_audio_duration(file_path)

    if duration >= 60:
        gcs_uri = upload_to_gcs(file_path)
        audio = speech.RecognitionAudio(uri=gcs_uri)
        operation = client.long_running_recognize(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language,
                enable_automatic_punctuation=True,
            ),
            audio=audio,
        )
        response = operation.result(timeout=600)
    else:
        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        response = client.recognize(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language,
                enable_automatic_punctuation=True,
            ),
            audio=audio,
        )

    transcript = " ".join([result.alternatives[0].transcript for result in response.results if result.alternatives])
    return transcript

# LLM analysis function using the ollama library with updated prompt
model_name = "aisingapore/llama3-8b-cpt-sea-lionv2.1-instruct"

def analyze_call(transcript):
    prompt = f"""
Analyze the following phone call transcript.

⚠ Important: Ignore meaningless repetitions or joke conversations. If keywords like 'OTP' or 'scam' appear in a random, non-persuasive way (e.g., "scam scam scam OTP OTP"), consider the conversation as Not Suspicious.

Determine whether the call is Suspicious or Not Suspicious with certainty. Do not express any uncertainty in your decision. If the call is suspicious, provide a brief reason highlighting the red flags.

A call should be considered Suspicious if it contains attempts to extract sensitive information such as OTPs, CVVs, banking details, or passwords. If a speaker urges the other person to install remote access applications like AnyDesk or TeamViewer, or applies pressure tactics such as urgency, threats, or emotional manipulation, the call is also suspicious. Requests for financial transactions, unusual payment methods, or impersonation of trusted entities (banks, government, tech support) are additional red flags.

If none of these signs are present, classify the call as Not Suspicious.

Evaluate based on:
Genuine scam attempts → Have persuasion, urgency, impersonation.
Timepass calls → Lack logical flow, persuasion, or pressure tactics.

Few-shot examples:
Joke Call:
"Scam scam scam OTP OTP hahaha" →  Not Suspicious

Real Scam Attempt:
"I am calling from XYZ Bank. Your account has been compromised. Share your OTP now." →  Suspicious

Your response should follow this format strictly:
⚠ Suspicious / ✅ Not Suspicious  
Reason: <Brief explanation of red flags if suspicious, or confirmation that no issues were found>

Transcript:
{transcript}
"""
    response = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
    # Split response into decision and explanation lines
    lines = response['message']['content'].split("\n", 1)
    decision = lines[0].strip() if len(lines) > 0 else "Decision not found"
    reason = lines[1].strip() if len(lines) > 1 else "No explanation provided"
    return decision, reason

@app.route('/', methods=['GET', 'POST'])
def home():
    decision = None
    reason = None

    if request.method == 'POST':
        # Retrieve file and language from the form
        audio_file = request.files['file']
        language = request.form['language']

        file_path = os.path.join(UPLOAD_FOLDER, audio_file.filename)
        audio_file.save(file_path)

        # Convert and transcribe the audio
        converted_file = convert_audio(file_path)
        transcript = transcribe_audio(converted_file, language)

        # Analyze the transcript with the LLM using the updated prompt
        decision, reason = analyze_call(transcript)

    # Pass the decision and reason to the template for display
    return render_template('index.html', decision=decision, reason=reason)

if __name__ == '__main__':
    app.run(debug=True)
