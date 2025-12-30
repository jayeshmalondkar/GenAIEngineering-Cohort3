"""
Chat with Knowledge Base - Streamlit App

A conversational AI application that answers questions using RAG (Retrieval Augmented Generation)
with FAISS and LanceDB vector databases and Mistral AI.
"""

import streamlit as st
import os
from mistralai import Mistral
import numpy as np
import lancedb
import faiss
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Chat with Knowledge Base",
    page_icon="💬",
    layout="wide"
)

# Constants
VECTOR_DB_PATH = Path("vector_dbs")
FAISS_INDEX_PATH = VECTOR_DB_PATH / "faiss_index.bin"
FAISS_METADATA_PATH = VECTOR_DB_PATH / "faiss_metadata.json"
LANCEDB_PATH = VECTOR_DB_PATH / "lancedb"
EMBEDDING_MODEL = "mistral-embed"
CHAT_MODEL = "mistral-small-latest"

# ============================================================================
# RESOURCE LOADING FUNCTIONS
# ============================================================================

@st.cache_resource
def get_mistral_client() -> Mistral:
    """
    Initialize and return Mistral client.

    Returns:
        Mistral: Initialized Mistral client
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        st.error("Please set MISTRAL_API_KEY environment variable")
        st.stop()
    return Mistral(api_key=api_key)


@st.cache_resource
def load_lancedb() -> Optional[Any]:
    """
    Load LanceDB table.

    Returns:
        LanceDB table: The document chunks table (or None if loading fails)
    """
    try:
        if not LANCEDB_PATH.exists():
            st.warning(f"LanceDB not found at {LANCEDB_PATH}")
            return None

        db = lancedb.connect(str(LANCEDB_PATH))

        # Get table names
        tables = db.table_names()
        if not tables:
            st.warning("No tables found in LanceDB")
            return None

        # Open first table
        table = db.open_table(tables[0])
        st.success(f"✓ Loaded LanceDB table: {tables[0]}")
        return table

    except Exception as e:
        st.error(f"Error loading LanceDB: {e}")
        return None


@st.cache_resource
def load_faiss() -> Tuple[Optional[faiss.Index], Optional[List[Dict]], bool]:
    """
    Load FAISS index and metadata, auto-detecting normalization.

    Returns:
        Tuple containing:
        - faiss.Index: The FAISS index (or None)
        - List[Dict]: Metadata for vectors (or None)
        - bool: Whether index uses normalized vectors
    """
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


# ============================================================================
# EMBEDDING AND SEARCH FUNCTIONS
# ============================================================================

def get_embedding(client: Mistral, text: str) -> Optional[np.ndarray]:
    """
    Get embedding for text using Mistral.

    Args:
        client: Mistral client
        text: Text to embed

    Returns:
        numpy array of embedding or None if error
    """
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            inputs=[text]
        )
        return np.array(response.data[0].embedding)
    except Exception as e:
        st.error(f"Error getting embedding: {e}")
        return None


def search_lancedb(
    client: Mistral,
    table: Any,
    query: str,
    top_k: int = 3
) -> List[Dict]:
    """
    Search LanceDB for relevant documents.

    Args:
        client: Mistral client for embeddings
        table: LanceDB table to search
        query: Search query
        top_k: Number of results to return

    Returns:
        List of relevant documents with scores
    """
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
            documents.append({
                'text': result.get('text', result.get('content', str(result))),
                'score': result.get('_distance', 0),
                'metadata': {
                    k: v for k, v in result.items()
                    if k not in ['vector', '_distance', 'text', 'content']
                }
            })
        return documents

    except Exception as e:
        st.error(f"Error searching LanceDB: {e}")
        return []


def search_faiss(
    client: Mistral,
    index: faiss.Index,
    metadata: List[Dict],
    use_normalization: bool,
    query: str,
    top_k: int = 3
) -> List[Dict]:
    """
    Search FAISS for relevant documents.

    Args:
        client: Mistral client for embeddings
        index: FAISS index
        metadata: Metadata for vectors
        use_normalization: Whether to normalize query vectors
        query: Search query
        top_k: Number of results to return

    Returns:
        List of relevant documents with scores
    """
    try:
        # Get query embedding
        query_embedding = get_embedding(client, query)
        if query_embedding is None:
            return []

        # Convert to proper FAISS format
        query_embedding = np.array(query_embedding, dtype='float32')
        query_embedding = query_embedding.reshape(1, -1)
        query_embedding = np.ascontiguousarray(query_embedding)

        # Normalize only if needed
        if use_normalization:
            faiss.normalize_L2(query_embedding)

        # Search
        distances, indices = index.search(query_embedding, top_k)

        # Format results
        documents = []
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(metadata):
                doc_data = metadata[idx]
                documents.append({
                    'text': doc_data.get('text', doc_data.get('content', str(doc_data))),
                    'score': float(dist),
                    'metadata': doc_data.get('metadata', {})
                })
            else:
                documents.append({
                    'text': f"Document {idx}",
                    'score': float(dist),
                    'metadata': {}
                })
        return documents

    except Exception as e:
        st.error(f"Error searching FAISS: {e}")
        return []


# ============================================================================
# RESPONSE GENERATION
# ============================================================================

def generate_response(
    client: Mistral,
    query: str,
    context_docs: List[Dict],
    conversation_history: List[Dict]
) -> str:
    """
    Generate response using Mistral with RAG.

    Args:
        client: Mistral client
        query: User query
        context_docs: Retrieved documents for context
        conversation_history: Previous conversation messages

    Returns:
        Generated response text
    """
    try:
        # Build context from retrieved documents
        context_text = "\n\n".join([
            f"Document {i+1}:\n{doc['text']}"
            for i, doc in enumerate(context_docs)
        ])

        # Build conversation messages
        messages = []

        # System message with context
        system_message = f"""You are a helpful assistant that answers questions based on the provided context.
Use the following context to answer the user's question. If the answer is not in the context, say so clearly.

Context:
{context_text}
"""
        messages.append({
            "role": "system",
            "content": system_message
        })

        # Add conversation history (last 10 messages to manage context)
        for msg in conversation_history[-10:]:
            messages.append(msg)

        # Add current query
        messages.append({
            "role": "user",
            "content": query
        })

        # Get response from Mistral
        response = client.chat.complete(
            model=CHAT_MODEL,
            messages=messages
        )

        return response.choices[0].message.content

    except Exception as e:
        st.error(f"Error generating response: {e}")
        return "Sorry, I encountered an error generating a response."


# ============================================================================
# UI FUNCTIONS
# ============================================================================

def display_source_documents(documents: List[Dict]) -> None:
    """
    Display source documents in an expander.

    Args:
        documents: List of document dictionaries
    """
    with st.expander("📚 Source Documents"):
        for i, doc in enumerate(documents, 1):
            st.markdown(f"**Document {i}** (Score: {doc['score']:.4f})")

            # Display text (truncated if too long)
            text = doc['text']
            if len(text) > 300:
                st.text(text[:300] + "...")
            else:
                st.text(text)

            # Display metadata if available
            if doc['metadata']:
                st.json(doc['metadata'])

            if i < len(documents):  # Don't add divider after last document
                st.divider()


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application logic."""

    # Initialize session state
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []

    # Header
    st.title("💬 Chat with Your Knowledge Base")
    st.markdown("Ask questions and get AI-powered answers from your documents!")

    # Initialize Mistral client
    client = get_mistral_client()

    # ========================================================================
    # SIDEBAR
    # ========================================================================

    with st.sidebar:
        st.header("⚙️ Settings")

        # Database selection
        db_type = st.radio(
            "Select Vector Database:",
            ["LanceDB", "FAISS"],
            index=0,
            help="Choose which vector database to use for retrieval"
        )

        # Number of documents to retrieve
        top_k = st.slider(
            "Number of documents to retrieve:",
            min_value=1,
            max_value=10,
            value=3,
            help="More documents = more context but slower"
        )

        # Show retrieved documents
        show_sources = st.checkbox(
            "Show source documents",
            value=True,
            help="Display the documents used to generate answers"
        )

        st.divider()

        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_history = []
            st.rerun()

        st.divider()

        # Database info
        st.subheader("📊 Database Info")

        if db_type == "LanceDB":
            lance_table = load_lancedb()
            if lance_table:
                st.info(f"""
                **Table:** {lance_table.name}

                **Rows:** {lance_table.count_rows()}
                """)
        else:
            faiss_result = load_faiss()
            if faiss_result and len(faiss_result) == 3:
                faiss_index, _, use_normalization = faiss_result
                if faiss_index:
                    norm_status = "✓ Yes" if use_normalization else "✗ No"
                    st.info(f"""
                    **Vectors:** {faiss_index.ntotal}

                    **Dimensions:** {faiss_index.d}

                    **Normalized:** {norm_status}
                    """)

    # ========================================================================
    # LOAD DATABASES
    # ========================================================================

    if db_type == "LanceDB":
        lance_table = load_lancedb()
        if lance_table is None:
            st.error("❌ LanceDB not available. Please check the database path.")
            st.stop()
        faiss_index, faiss_metadata, use_normalization = None, None, False
    else:
        faiss_result = load_faiss()
        if faiss_result and len(faiss_result) == 3:
            faiss_index, faiss_metadata, use_normalization = faiss_result
        else:
            faiss_index, faiss_metadata, use_normalization = None, None, False

        if faiss_index is None:
            st.error("❌ FAISS not available. Please check the database path.")
            st.stop()
        lance_table = None

    # ========================================================================
    # DISPLAY CHAT HISTORY
    # ========================================================================

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Show sources if available
            if (message["role"] == "assistant" and
                "sources" in message and
                show_sources and
                message["sources"]):
                display_source_documents(message["sources"])

    # ========================================================================
    # CHAT INPUT AND PROCESSING
    # ========================================================================

    if prompt := st.chat_input("Ask a question about your knowledge base..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Retrieve relevant documents
        with st.spinner("🔍 Searching knowledge base..."):
            if db_type == "LanceDB":
                relevant_docs = search_lancedb(client, lance_table, prompt, top_k=top_k)
            else:
                relevant_docs = search_faiss(
                    client, faiss_index, faiss_metadata,
                    use_normalization, prompt, top_k=top_k
                )

        # Generate response
        with st.spinner("💭 Generating response..."):
            response = generate_response(
                client, prompt, relevant_docs,
                st.session_state.conversation_history
            )

        # Add assistant message to chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "sources": relevant_docs
        })

        # Update conversation history
        st.session_state.conversation_history.append({
            "role": "user",
            "content": prompt
        })
        st.session_state.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        # Display assistant message
        with st.chat_message("assistant"):
            st.markdown(response)

            # Show sources
            if show_sources and relevant_docs:
                display_source_documents(relevant_docs)

    # ========================================================================
    # FOOTER
    # ========================================================================

    st.divider()

    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"💾 Database: {db_type}")
    with col2:
        st.caption(f"💬 Messages: {len(st.session_state.messages)}")
    with col3:
        st.caption(f"📄 Context docs: {top_k}")


if __name__ == "__main__":
    main()