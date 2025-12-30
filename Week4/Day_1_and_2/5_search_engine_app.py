"""
Vector Database Search Engine - Streamlit App

This app demonstrates semantic search using vector databases (FAISS and LanceDB).
It provides search results with source citations including file names, page numbers, and chunk numbers.
"""

import streamlit as st
import numpy as np
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import time
from mistralai import Mistral
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Vector databases
import faiss
import lancedb

# Constants
VECTOR_DB_PATH = Path("vector_dbs")
FAISS_INDEX_PATH = VECTOR_DB_PATH / "faiss_index.bin"
FAISS_METADATA_PATH = VECTOR_DB_PATH / "faiss_metadata.json"
LANCEDB_PATH = VECTOR_DB_PATH / "lancedb"
EMBEDDING_MODEL = "mistral-embed"
CHAT_MODEL = "mistral-small-latest"

# Configuration
st.set_page_config(
    page_title="Vector DB Search Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .search-result {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #1f77b4;
    }
    .result-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: #0e4c92;
        margin-bottom: 0.5rem;
    }
    .citation {
        font-size: 0.9rem;
        color: #666;
        font-style: italic;
        margin-bottom: 0.5rem;
    }
    .score-badge {
        background-color: #28a745;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .metric-card {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_mistral_client() -> Mistral:
    """Initialize and return Mistral client."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        st.error("Please set MISTRAL_API_KEY environment variable")
        st.stop()
    return Mistral(api_key=api_key)


@st.cache_resource
def load_faiss() -> Tuple[Optional[faiss.Index], Optional[List[Dict]], bool]:
    """Load FAISS index and metadata, auto-detecting normalization."""
    try:
        if not FAISS_INDEX_PATH.exists():
            st.warning(f"FAISS index not found at {FAISS_INDEX_PATH}")
            return None, None, False

        # Load FAISS index
        index = faiss.read_index(str(FAISS_INDEX_PATH))

        # Load metadata
        metadata = None
        if FAISS_METADATA_PATH.exists():
            with open(FAISS_METADATA_PATH, 'r') as f:
                metadata = json.load(f)

        # Auto-detect normalization
        uses_normalization = False
        if index.ntotal > 0:
            try:
                vec = index.reconstruct(0)
                norm = np.linalg.norm(vec)
                uses_normalization = abs(norm - 1.0) < 0.01
            except Exception:
                uses_normalization = False

        st.success(f"✓ Loaded FAISS index with {index.ntotal} vectors")
        return index, metadata, uses_normalization

    except Exception as e:
        st.error(f"Error loading FAISS: {e}")
        return None, None, False


@st.cache_resource
def load_lancedb() -> Optional[Any]:
    """Load LanceDB table."""
    try:
        if not LANCEDB_PATH.exists():
            st.warning(f"LanceDB not found at {LANCEDB_PATH}")
            return None

        db = lancedb.connect(str(LANCEDB_PATH))
        tables = db.table_names()

        if not tables:
            st.warning("No tables found in LanceDB")
            return None

        table = db.open_table(tables[0])
        st.success(f"✓ Loaded LanceDB table: {tables[0]}")
        return table

    except Exception as e:
        st.error(f"Error loading LanceDB: {e}")
        return None


def get_embedding(client: Mistral, text: str) -> Optional[np.ndarray]:
    """Get embedding for text using Mistral."""
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            inputs=[text]
        )
        return np.array(response.data[0].embedding, dtype='float32')
    except Exception as e:
        st.error(f"Error getting embedding: {e}")
        return None


def search_faiss(
    client: Mistral,
    index: faiss.Index,
    metadata: List[Dict],
    use_normalization: bool,
    query: str,
    top_k: int = 5
) -> List[Dict]:
    """Search FAISS for relevant documents using Mistral embeddings."""
    try:
        # Get query embedding
        query_embedding = get_embedding(client, query)
        if query_embedding is None:
            return []

        # Convert to proper FAISS format
        query_embedding = query_embedding.reshape(1, -1)
        query_embedding = np.ascontiguousarray(query_embedding)

        # Normalize if needed
        if use_normalization:
            faiss.normalize_L2(query_embedding)

        # Search
        distances, indices = index.search(query_embedding, top_k)

        # Format results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(metadata):
                result = metadata[idx].copy()
                result['distance'] = float(dist)
                result['similarity_score'] = 1 / (1 + dist)
                results.append(result)

        return results

    except Exception as e:
        st.error(f"Error searching FAISS: {e}")
        return []


def search_lancedb(
    client: Mistral,
    table: Any,
    query: str,
    top_k: int = 5
) -> List[Dict]:
    """Search LanceDB for relevant documents using Mistral embeddings."""
    try:
        # Get query embedding
        query_embedding = get_embedding(client, query)
        if query_embedding is None:
            return []

        # Search the table
        results = table.search(query_embedding.tolist()).limit(top_k).to_list()

        # Format results
        documents = []
        for result in results:
            doc = {
                'text': result.get('text', result.get('content', str(result))),
                'distance': result.get('_distance', 0),
                'similarity_score': 1 / (1 + result.get('_distance', 0)),
                'file_name': result.get('file_name', 'Unknown'),
                'page_number': result.get('page_number', 0),
                'chunk_number': result.get('chunk_number', 0),
                'chunk_id': result.get('chunk_id', 'N/A'),
                'char_count': result.get('char_count', 0)
            }
            documents.append(doc)

        return documents

    except Exception as e:
        st.error(f"Error searching LanceDB: {e}")
        return []


def keyword_search(query: str, metadata: List[Dict], k: int = 5) -> List[Dict]:
    """Perform keyword search."""
    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []
    for chunk in metadata:
        text_lower = chunk.get('text', '').lower()

        # Count term matches
        matches = sum(1 for term in query_terms if term in text_lower)

        if matches > 0:
            score = matches / len(query_terms)
            result = chunk.copy()
            result['keyword_score'] = score
            result['matched_terms'] = matches
            results.append(result)

    # Sort by score
    results.sort(key=lambda x: x['keyword_score'], reverse=True)
    return results[:k]


def hybrid_search(
    query: str,
    client: Mistral,
    index: faiss.Index,
    metadata: List[Dict],
    use_normalization: bool,
    k: int = 5,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7
) -> List[Dict]:
    """Combine keyword and semantic search."""
    try:
        # Get both types of results
        keyword_results = keyword_search(query, metadata, k=k*2)
        semantic_results = search_faiss(client, index, metadata, use_normalization, query, top_k=k*2)

        # Create score dictionary
        hybrid_scores = {}

        # Add keyword scores
        for result in keyword_results:
            chunk_id = result.get('chunk_id', id(result))
            hybrid_scores[chunk_id] = {
                'chunk': result,
                'keyword_score': result['keyword_score'],
                'semantic_score': 0.0
            }

        # Add/update with semantic scores
        for result in semantic_results:
            chunk_id = result.get('chunk_id', id(result))
            if chunk_id in hybrid_scores:
                hybrid_scores[chunk_id]['semantic_score'] = result['similarity_score']
            else:
                hybrid_scores[chunk_id] = {
                    'chunk': result,
                    'keyword_score': 0.0,
                    'semantic_score': result['similarity_score']
                }

        # Calculate hybrid scores
        final_results = []
        for chunk_id, scores in hybrid_scores.items():
            chunk = scores['chunk'].copy()
            hybrid_score = (keyword_weight * scores['keyword_score'] +
                          semantic_weight * scores['semantic_score'])

            chunk['hybrid_score'] = hybrid_score
            chunk['keyword_score'] = scores['keyword_score']
            chunk['semantic_score'] = scores['semantic_score']
            final_results.append(chunk)

        # Sort by hybrid score
        final_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        return final_results[:k]

    except Exception as e:
        st.error(f"Error in hybrid search: {e}")
        return []


def display_result(result: Dict, rank: int, search_type: str):
    """Display a single search result with formatting."""
    st.markdown(f"""
    <div class="search-result">
        <div class="result-title">🔹 Result #{rank}</div>
    """, unsafe_allow_html=True)

    # Score display
    if search_type == "Semantic":
        score = result.get('similarity_score', 0)
        score_label = "Similarity"
    elif search_type == "Keyword":
        score = result.get('keyword_score', 0)
        score_label = "Keyword Match"
    else:  # Hybrid
        score = result.get('hybrid_score', 0)
        score_label = "Hybrid Score"

    col1, col2 = st.columns([3, 1])

    with col1:
        file_name = result.get('file_name', 'Unknown')
        page_num = result.get('page_number', 'N/A')
        chunk_num = result.get('chunk_number', 'N/A')
        st.markdown(f"<div class='citation'>📄 <b>{file_name}</b> | Page {page_num} | Chunk {chunk_num}</div>",
                   unsafe_allow_html=True)

    with col2:
        st.markdown(f"<span class='score-badge'>{score_label}: {score:.3f}</span>",
                   unsafe_allow_html=True)

    # Text content
    st.markdown("**Content:**")
    st.write(result.get('text', 'No text available'))

    # Additional details in expander
    with st.expander("📊 Details"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Characters", result.get('char_count', 'N/A'))
        col2.metric("Chunk ID", result.get('chunk_id', 'N/A'))

        if search_type == "Hybrid":
            col3.metric("Keyword", f"{result.get('keyword_score', 0):.3f}")
            st.metric("Semantic", f"{result.get('semantic_score', 0):.3f}")

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    """Main application."""

    # Header
    st.markdown('<h1 class="main-header">🔍 Vector Database Search Engine</h1>',
                unsafe_allow_html=True)

    st.markdown("""
    <p style='text-align: center; color: #666; margin-bottom: 2rem;'>
    Powered by semantic search using vector embeddings and similarity matching
    </p>
    """, unsafe_allow_html=True)

    # Load resources
    client = get_mistral_client()
    faiss_index, faiss_metadata, use_normalization = load_faiss()
    lance_table = load_lancedb()

    # Check if databases are loaded
    databases_available = []
    if faiss_index is not None:
        databases_available.append("FAISS")
    if lance_table is not None:
        databases_available.append("LanceDB")

    if not databases_available:
        st.error("⚠️ No vector databases found! Please run the vector database notebook first to create indexes.")
        st.info("""
        **Steps to set up:**
        1. Run the `vector_databases_intro.ipynb` notebook
        2. This will create the vector databases in the `vector_dbs/` directory
        3. Then return to this search engine
        """)
        return

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Database selection
        st.subheader("Database")
        db_choice = st.selectbox(
            "Select Vector Database:",
            databases_available,
            help="Choose which vector database to use for search"
        )

        # Search type
        st.subheader("Search Method")
        search_type = st.radio(
            "Select search type:",
            ["Semantic", "Keyword", "Hybrid"],
            help="""
            - **Semantic**: Uses AI to understand meaning
            - **Keyword**: Traditional text matching
            - **Hybrid**: Combines both methods
            """
        )

        # Number of results
        st.subheader("Results")
        num_results = st.slider(
            "Number of results:",
            min_value=1,
            max_value=20,
            value=5,
            help="How many search results to display"
        )

        # Hybrid weights
        keyword_weight = 0.3
        semantic_weight = 0.7
        if search_type == "Hybrid":
            st.subheader("Hybrid Weights")
            keyword_weight = st.slider(
                "Keyword weight:",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1
            )
            semantic_weight = 1.0 - keyword_weight
            st.info(f"Semantic weight: {semantic_weight:.1f}")

        # Info
        st.markdown("---")
        st.subheader("ℹ️ About")
        doc_count = len(faiss_metadata) if faiss_metadata else 0
        st.info(f"""
        **Database:** {db_choice}

        **Documents:** {doc_count} chunks

        **Model:** Mistral Embed

        **API:** Mistral AI
        """)

    # Main search area
    st.header("🔎 Search")

    # Search input
    query = st.text_input(
        "Enter your search query:",
        placeholder="e.g., How does machine learning work?",
        help="Type your question or keywords to search"
    )

    # Search button
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    with col2:
        if st.button("🔄 Clear", use_container_width=True):
            st.rerun()

    # Perform search
    if search_button and query:
        with st.spinner(f"Searching using {search_type} search..."):
            start_time = time.time()

            # Perform search based on type and database
            if db_choice == "FAISS":
                if search_type == "Semantic":
                    results = search_faiss(client, faiss_index, faiss_metadata,
                                         use_normalization, query, top_k=num_results)
                elif search_type == "Keyword":
                    results = keyword_search(query, faiss_metadata, k=num_results)
                else:  # Hybrid
                    results = hybrid_search(query, client, faiss_index, faiss_metadata,
                                          use_normalization, k=num_results,
                                          keyword_weight=keyword_weight,
                                          semantic_weight=semantic_weight)
            else:  # LanceDB
                if search_type == "Semantic":
                    results = search_lancedb(client, lance_table, query, top_k=num_results)
                elif search_type == "Keyword":
                    all_data = lance_table.to_pandas().to_dict('records')
                    results = keyword_search(query, all_data, k=num_results)
                else:  # Hybrid
                    all_data = lance_table.to_pandas().to_dict('records')
                    keyword_results = keyword_search(query, all_data, k=num_results*2)
                    semantic_results = search_lancedb(client, lance_table, query, top_k=num_results*2)

                    # Simple hybrid combination for LanceDB
                    hybrid_scores = {}
                    for res in keyword_results:
                        chunk_id = res.get('chunk_id', id(res))
                        hybrid_scores[chunk_id] = {
                            'chunk': res,
                            'keyword_score': res['keyword_score'],
                            'semantic_score': 0.0
                        }

                    for res in semantic_results:
                        chunk_id = res.get('chunk_id', id(res))
                        if chunk_id in hybrid_scores:
                            hybrid_scores[chunk_id]['semantic_score'] = res['similarity_score']
                        else:
                            hybrid_scores[chunk_id] = {
                                'chunk': res,
                                'keyword_score': 0.0,
                                'semantic_score': res['similarity_score']
                            }

                    results = []
                    for scores in hybrid_scores.values():
                        chunk = scores['chunk'].copy()
                        chunk['hybrid_score'] = (keyword_weight * scores['keyword_score'] +
                                                semantic_weight * scores['semantic_score'])
                        chunk['keyword_score'] = scores['keyword_score']
                        chunk['semantic_score'] = scores['semantic_score']
                        results.append(chunk)

                    results.sort(key=lambda x: x['hybrid_score'], reverse=True)
                    results = results[:num_results]

            search_time = time.time() - start_time

        # Display results
        st.markdown("---")
        st.header("📊 Results")

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>{len(results)}</h3>
                <p>Results Found</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>{search_time:.3f}s</h3>
                <p>Search Time</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3>{search_type}</h3>
                <p>Search Method</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Display results
        if results:
            for rank, result in enumerate(results, 1):
                display_result(result, rank, search_type)
        else:
            st.warning("No results found. Try a different query or search method.")

    elif query and not search_button:
        st.info("👆 Click the Search button to start searching!")

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p><b>Vector Database Search Engine</b></p>
        <p>Built with Streamlit, FAISS, LanceDB, and Mistral AI</p>
        <p>🔍 Semantic Search | 📊 Source Citations | ⚡ Fast Retrieval</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()