"""
Vector Database Search Engine - Streamlit App

This app demonstrates semantic search using vector databases (FAISS and LanceDB).
It provides search results with source citations including file names, page numbers, and chunk numbers.
"""

import streamlit as st
import numpy as np
import json
from pathlib import Path
from typing import List, Dict
import time

# Vector databases
import faiss
import lancedb

# Embeddings
from sentence_transformers import SentenceTransformer

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


def load_embedding_model():
    """Load the sentence transformer model."""
    # if 'embedding_model' not in st.session_state:
    if st.session_state.embedding_model is None:
        with st.spinner("Loading embedding model..."):
            st.session_state.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded.")
    return st.session_state.embedding_model


def load_faiss_index():
    """Load FAISS index and metadata."""

    # if 'faiss_index' not in st.session_state or 'faiss_metadata' not in st.session_state:
    if st.session_state.faiss_index is None or st.session_state.faiss_metadata is None:
        print("Loading FAISS index...")
        try:
            index_path = Path('vector_dbs/faiss_index.bin')
            metadata_path = Path('vector_dbs/faiss_metadata.json')
            print(index_path.exists(), metadata_path.exists())
            if not index_path.exists() or not metadata_path.exists():
                st.session_state.faiss_index = None
                st.session_state.faiss_metadata = None
                return None, None

            st.session_state.faiss_index = faiss.read_index(str(index_path))

            with open(metadata_path, 'r') as f:
                st.session_state.faiss_metadata = json.load(f)


        except Exception as e:
            st.error(f"Error loading FAISS: {e}")
            st.session_state.faiss_index = None
            st.session_state.faiss_metadata = None
            return None, None

    return st.session_state.faiss_index, st.session_state.faiss_metadata


def load_lancedb():
    """Load LanceDB connection."""
    # if 'lance_db' not in st.session_state or 'lance_table' not in st.session_state:
    if st.session_state.lance_db is None or st.session_state.lance_table is None:
        try:
            db_path = Path('vector_dbs/lancedb')

            if not db_path.exists():
                st.session_state.lance_db = None
                st.session_state.lance_table = None
                return None, None

            st.session_state.lance_db = lancedb.connect(str(db_path))
            st.session_state.lance_table = st.session_state.lance_db.open_table('document_chunks')

        except Exception as e:
            st.error(f"Error loading LanceDB: {e}")
            st.session_state.lance_db = None
            st.session_state.lance_table = None
            return None, None

    return st.session_state.lance_db, st.session_state.lance_table


def semantic_search_faiss(query: str, model, index, metadata, k: int = 5) -> List[Dict]:
    """Perform semantic search using FAISS."""
    if index is None or metadata is None:
        return []

    # Generate query embedding
    query_embedding = model.encode([query])[0].astype('float32')
    query_embedding = np.array([query_embedding])

    # Search
    distances, indices = index.search(query_embedding, k)

    # Prepare results
    results = []
    for idx, distance in zip(indices[0], distances[0]):
        if idx < len(metadata):
            result = metadata[idx].copy()
            result['distance'] = float(distance)
            result['similarity_score'] = 1 / (1 + distance)
            results.append(result)

    return results


def semantic_search_lancedb(query: str, model, table, k: int = 5) -> List[Dict]:
    """Perform semantic search using LanceDB."""
    if table is None:
        return []

    # Generate query embedding
    query_embedding = model.encode([query])[0]

    # Search
    results = table.search(query_embedding).limit(k).to_list()

    # Format results
    formatted_results = []
    for result in results:
        formatted_result = {
            'chunk_id': result['chunk_id'],
            'text': result['text'],
            'file_name': result['file_name'],
            'page_number': result['page_number'],
            'chunk_number': result['chunk_number'],
            'char_count': result['char_count'],
            'distance': result['_distance'],
            'similarity_score': 1 / (1 + result['_distance'])
        }
        formatted_results.append(formatted_result)

    return formatted_results


def keyword_search(query: str, metadata: List[Dict], k: int = 5) -> List[Dict]:
    """Perform keyword search."""
    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []
    for chunk in metadata:
        text_lower = chunk['text'].lower()

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


def hybrid_search(query: str, model, index, metadata, k: int = 5,
                 keyword_weight: float = 0.3, semantic_weight: float = 0.7) -> List[Dict]:
    """Combine keyword and semantic search."""
    # Get both types of results
    keyword_results = keyword_search(query, metadata, k=k*2)
    semantic_results = semantic_search_faiss(query, model, index, metadata, k=k*2)

    # Create score dictionary
    hybrid_scores = {}

    # Add keyword scores
    for result in keyword_results:
        chunk_id = result['chunk_id']
        hybrid_scores[chunk_id] = {
            'chunk': result,
            'keyword_score': result['keyword_score'],
            'semantic_score': 0.0
        }

    # Add/update with semantic scores
    for result in semantic_results:
        chunk_id = result['chunk_id']
        if chunk_id in hybrid_scores:
            hybrid_scores[chunk_id]['semantic_score'] = result['similarity_score']
        else:
            hybrid_scores[chunk_id] = {
                'chunk': result,
                'keyword_score': 0.0,
                'semantic_score': result['similarity_score']
            }

    # Calculate hybrid scores
    results = []
    for chunk_id, scores in hybrid_scores.items():
        hybrid_score = (keyword_weight * scores['keyword_score'] +
                       semantic_weight * scores['semantic_score'])

        result = scores['chunk'].copy()
        result['keyword_score'] = scores['keyword_score']
        result['semantic_score'] = scores['semantic_score']
        result['hybrid_score'] = hybrid_score
        results.append(result)

    # Sort by hybrid score
    results.sort(key=lambda x: x['hybrid_score'], reverse=True)

    return results[:k]


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
        st.markdown(f"<div class='citation'>📄 <b>{result['file_name']}</b> | Page {result['page_number']} | Chunk {result['chunk_number']}</div>",
                   unsafe_allow_html=True)

    with col2:
        st.markdown(f"<span class='score-badge'>{score_label}: {score:.3f}</span>",
                   unsafe_allow_html=True)

    # Text content
    st.markdown("**Content:**")
    st.write(result['text'])

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

    # Initialize session state
    if 'embedding_model' not in st.session_state:
        st.session_state.embedding_model = None
    if 'faiss_index' not in st.session_state:
        st.session_state.faiss_index = None
    if 'faiss_metadata' not in st.session_state:
        st.session_state.faiss_metadata = None
    if 'lance_db' not in st.session_state:
        st.session_state.lance_db = None
    if 'lance_table' not in st.session_state:
        st.session_state.lance_table = None

    # Header
    st.markdown('<h1 class="main-header">🔍 Vector Database Search Engine</h1>',
                unsafe_allow_html=True)

    st.markdown("""
    <p style='text-align: center; color: #666; margin-bottom: 2rem;'>
    Powered by semantic search using vector embeddings and similarity matching
    </p>
    """, unsafe_allow_html=True)
    print("Loading models...")
    # Load resources
    model = load_embedding_model()
    faiss_index, faiss_metadata = load_faiss_index()
    lance_db, lance_table = load_lancedb()

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

        # Hybrid weights (only show for hybrid search)
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
        st.info(f"""
        **Database:** {db_choice}

        **Documents:** {len(faiss_metadata) if faiss_metadata else 0} chunks

        **Model:** all-MiniLM-L6-v2

        **Embedding Dim:** 384
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
                    results = semantic_search_faiss(query, model, faiss_index,
                                                   faiss_metadata, k=num_results)
                elif search_type == "Keyword":
                    results = keyword_search(query, faiss_metadata, k=num_results)
                else:  # Hybrid
                    results = hybrid_search(query, model, faiss_index, faiss_metadata,
                                          k=num_results, keyword_weight=keyword_weight,
                                          semantic_weight=semantic_weight)
            else:  # LanceDB
                if search_type == "Semantic":
                    results = semantic_search_lancedb(query, model, lance_table,
                                                     k=num_results)
                elif search_type == "Keyword":
                    # For LanceDB, we'll convert to pandas and use keyword search
                    all_data = lance_table.to_pandas().to_dict('records')
                    results = keyword_search(query, all_data, k=num_results)
                else:  # Hybrid
                    # Get data for keyword search
                    all_data = lance_table.to_pandas().to_dict('records')
                    keyword_results = keyword_search(query, all_data, k=num_results*2)
                    semantic_results = semantic_search_lancedb(query, model,
                                                              lance_table, k=num_results*2)

                    # Combine (simplified hybrid for LanceDB)
                    results = semantic_results[:num_results]

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
        <p>Built with Streamlit, FAISS, LanceDB, and Sentence Transformers</p>
        <p>🔍 Semantic Search | 📊 Source Citations | ⚡ Fast Retrieval</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()