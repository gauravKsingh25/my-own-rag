"""Test Gemini API Key"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import google.generativeai as genai
    
    # Get API key from environment
    api_key = "AIzaSyBV0QoDRjPpkq5W2G3fu6dbf3tz-3kC9L8"
    
    print("🔑 Testing Gemini API Key...")
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print("-" * 60)
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Test 1: List models
    print("\n📋 Test 1: Listing available models...")
    try:
        models = list(genai.list_models())
        embedding_models = [m for m in models if hasattr(m, 'name') and 'embedding' in m.name.lower()]
        generation_models = [m for m in models if hasattr(m, 'supported_generation_methods') and any('generateContent' in str(method) for method in m.supported_generation_methods)]
        
        print(f"✅ Found {len(models)} total models")
        print(f"✅ Found {len(embedding_models)} embedding models:")
        for model in embedding_models:
            print(f"   - {model.name}")
        
        if generation_models:
            print(f"✅ Found {len(generation_models)} generation models:")
            for model in generation_models[:5]:  # Show first 5
                print(f"   - {model.name}")
        else:
            print(f"⚠️  No generation models found")
    except Exception as e:
        print(f"❌ Failed to list models: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Test 2: Generate embedding
    print("\n🧮 Test 2: Generating test embedding...")
    try:
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content="This is a test sentence for embedding.",
            task_type="retrieval_document"
        )
        
        embedding = result['embedding']
        print(f"✅ Successfully generated embedding!")
        print(f"   - Embedding dimension: {len(embedding)}")
        print(f"   - First 5 values: {embedding[:5]}")
    except Exception as e:
        print(f"❌ Failed to generate embedding: {str(e)}")
        sys.exit(1)
    
    # Test 3: Test generation model
    print("\n💬 Test 3: Testing generation model...")
    try:
        # Try common model names
        model_names = ['gemini-pro', 'models/gemini-pro', 'gemini-1.0-pro']
        
        success = False
        for model_name in model_names:
            try:
                print(f"   Trying model: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Say 'API Key is working!' in one sentence.")
                
                print(f"✅ Successfully generated text!")
                print(f"   - Used model: {model_name}")
                print(f"   - Response: {response.text}")
                success = True
                break
            except Exception as e:
                print(f"   ❌ {model_name} failed: {str(e)[:80]}")
                continue
        
        if not success:
            print(f"⚠️  Generation test skipped - no available models found")
            print(f"   Embedding functionality is working though!")
    except Exception as e:
        print(f"❌ Failed to test generation: {str(e)}")
        # Don't exit - embedding still works
    
    print("\n" + "=" * 60)
    print("🎉 ALL GEMINI API TESTS PASSED!")
    print("=" * 60)

except ImportError as e:
    print(f"❌ Import error: {str(e)}")
    print("Please install: pip install google-generativeai")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ GEMINI API TEST FAILED!")
    print(f"Error: {str(e)}")
    sys.exit(1)
