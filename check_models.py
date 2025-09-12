import os
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    # Initialize the Groq client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env file.")
    
    client = Groq(api_key=api_key)

    print("Fetching available models from Groq...")
    model_list = client.models.list()

    print("\n✅ Here are the models currently available to you:\n")
    
    large_model_candidate = ""
    fast_model_candidate = ""

    # Sort to make the list predictable
    sorted_models = sorted(model_list.data, key=lambda m: m.id)

    for model in sorted_models:
        # Filter out non-language models
        if 'whisper' not in model.id and 'guard' not in model.id:
            print(f"  - Model ID: {model.id}")
            # Heuristics to find candidates
            if '70b' in model.id or 'gemma2' in model.id:
                large_model_candidate = model.id
            if '8b' in model.id or 'gemma-7b' in model.id:
                fast_model_candidate = model.id

    print("\n---")
    print("RECOMMENDATION:")
    if fast_model_candidate:
        print(f"For GROQ_MODEL_FAST, use: \"{fast_model_candidate}\"")
    else:
        print("Could not automatically determine a fast model. Please choose one from the list.")
    
    if large_model_candidate:
        print(f"For GROQ_MODEL_LARGE, use: \"{large_model_candidate}\"")
    else:
        print("Could not automatically determine a large model. Please choose one from the list.")
    print("---\n")


except Exception as e:
    print(f"\n❌ An error occurred: {e}")
    print("Please ensure your GROQ_API_KEY is set correctly in the .env file.")