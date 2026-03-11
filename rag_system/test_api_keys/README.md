# API Key Testing Scripts

This folder contains test scripts to verify your Gemini and Pinecone API keys are working correctly.

## Test Scripts

1. **test_gemini.py** - Tests Google Gemini API key
   - Lists available models
   - Generates test embedding
   - Tests text generation

2. **test_pinecone.py** - Tests Pinecone API key
   - Initializes Pinecone client
   - Lists existing indexes
   - Checks for required index
   - Tests index creation capability

## How to Run

```powershell
# From the rag_system directory
cd "c:\Users\GAURAV SINGH\Favorites\my own rag\rag_system"

# Test Gemini API
python test_api_keys\test_gemini.py

# Test Pinecone API
python test_api_keys\test_pinecone.py
```

## Expected Results

Both scripts should print success messages if the API keys are valid. If there are any issues, detailed error messages will be displayed.
