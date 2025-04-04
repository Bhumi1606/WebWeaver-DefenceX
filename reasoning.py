import ollama

# Model name
model_name = "aisingapore/llama3-8b-cpt-sea-lionv2.1-instruct"

def analyze_call(transcript, classification):
    # Determine classification label
    label = "Suspicious" if classification == 1 else "Not Suspicious"

    # Prompt for Ollama
    prompt = f"""
    A phone call conversation is provided below along with its classification.
    - Call Transcript: {transcript}
    - Classification: {label}

    Your task:
    1. First, output exactly '{label}'.
    2. On the next line, briefly explain why this classification is reasonable.

    Output format:
    {label}
    [short reasoning]
    """

    # Get response from Ollama
    response = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}])

    return response['message']['content']

# Example usage
call_transcript = "Caller: Hello, your bank account has been compromised. Please provide your card details immediately. \nReceiver: What? How do I verify this?"
classification = 1  # 1 for spam/fraudulent, 0 for non-spam

result = analyze_call(call_transcript, classification)
print(result)
