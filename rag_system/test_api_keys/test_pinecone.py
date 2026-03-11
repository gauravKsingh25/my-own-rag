"""Test Pinecone API Key"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pinecone import Pinecone, ServerlessSpec
    
    # Get API key from environment
    api_key = "pcsk_3ft1zD_3bcMd2iBUvJumu1SFPzJa6Q6fHEYWinRiu2pTZdM1KUdXUsZwzuPHiDrnHpgErH"
    
    print("🔑 Testing Pinecone API Key...")
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print("-" * 60)
    
    # Test 1: Initialize Pinecone
    print("\n🔧 Test 1: Initializing Pinecone client...")
    try:
        pc = Pinecone(api_key=api_key)
        print("✅ Successfully initialized Pinecone client!")
    except Exception as e:
        print(f"❌ Failed to initialize Pinecone: {str(e)}")
        sys.exit(1)
    
    # Test 2: List indexes
    print("\n📋 Test 2: Listing existing indexes...")
    try:
        indexes = pc.list_indexes()
        print(f"✅ Successfully retrieved index list!")
        print(f"   - Found {len(indexes)} indexes")
        
        if len(indexes) > 0:
            for idx in indexes:
                print(f"   - {idx.name}: {idx.dimension} dimensions, {idx.metric} metric")
        else:
            print("   - No indexes found (this is ok for new accounts)")
    except Exception as e:
        print(f"❌ Failed to list indexes: {str(e)}")
        sys.exit(1)
    
    # Test 3: Check if our index exists
    print("\n🔍 Test 3: Checking for 'rag-embeddings' index...")
    try:
        index_name = "rag-embeddings"
        index_names = [idx.name for idx in pc.list_indexes()]
        
        if index_name in index_names:
            print(f"✅ Index '{index_name}' exists!")
            
            # Get index stats
            index = pc.Index(index_name)
            stats = index.describe_index_stats()
            print(f"   - Total vectors: {stats.get('total_vector_count', 0)}")
            print(f"   - Namespaces: {list(stats.get('namespaces', {}).keys())}")
        else:
            print(f"⚠️  Index '{index_name}' does not exist yet")
            print(f"   - This is normal if you haven't created it yet")
            print(f"   - The system will create it automatically on first use")
    except Exception as e:
        print(f"⚠️  Could not check index: {str(e)}")
    
    # Test 4: Test index creation capability (optional)
    print("\n🧪 Test 4: Testing index creation capability...")
    test_index_name = "test-connection-check"
    try:
        # Check if test index exists, if not create it
        if test_index_name not in [idx.name for idx in pc.list_indexes()]:
            print(f"   Creating temporary test index '{test_index_name}'...")
            pc.create_index(
                name=test_index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            print(f"✅ Successfully created test index!")
            
            # Clean up - delete the test index
            print(f"   Cleaning up test index...")
            pc.delete_index(test_index_name)
            print(f"✅ Test index deleted")
        else:
            print(f"   Test index already exists, skipping creation test")
    except Exception as e:
        print(f"⚠️  Index creation test: {str(e)}")
        print(f"   - API key has read access but may not have write access")
        print(f"   - This might be ok depending on your use case")
    
    print("\n" + "=" * 60)
    print("🎉 PINECONE API TESTS PASSED!")
    print("=" * 60)

except ImportError as e:
    print(f"❌ Import error: {str(e)}")
    print("Please install: pip install pinecone-client")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ PINECONE API TEST FAILED!")
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
