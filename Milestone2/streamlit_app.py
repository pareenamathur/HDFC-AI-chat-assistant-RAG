"""
HDFC Mutual Fund Assistant - Streamlit Application
Modern UI with memory optimizations for production deployment
"""

import streamlit as st
import os
import sys
import json
import logging
from typing import Dict, Any, List
import time

# Add Phase 2 and Phase 3 src to path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for lazy loading
_orchestrator = None
_schemes = []
_initialized = False

def get_memory_usage():
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024  # Convert to MB
    except ImportError:
        return "Unknown (psutil not available)"

@st.cache_resource
def load_orchestrator():
    """Load RAG orchestrator with caching to prevent multiple instances."""
    global _orchestrator, _schemes, _initialized
    
    if _initialized and _orchestrator is not None:
        return _orchestrator
    
    logger.info("Loading RAG orchestrator...")
    before_memory = get_memory_usage()
    logger.info(f"Memory before orchestrator load: {before_memory} MB")
    
    try:
        # Lazy import to reduce startup memory
        from orchestrator import RAGOrchestrator
        
        # Use environment variables for paths
        data_path = os.getenv('DATA_PATH', os.path.join(BASE, 'data'))
        processed_data_path = os.getenv('PROCESSED_DATA_PATH', os.path.join(BASE, 'data', 'processed'))
        indexed_data_path = os.getenv('INDEXED_DATA_PATH', os.path.join(BASE, 'data', 'indexed'))
        
        # Load schemes from chunked data
        chunked_data_path = os.path.join(processed_data_path, 'chunked_data_phase1.4.json')
        if os.path.exists(chunked_data_path):
            with open(chunked_data_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            _schemes = sorted(list(set(c['scheme_name'] for c in chunks)))
            logger.info(f"Loaded {_schemes} schemes")
        else:
            logger.warning(f"Chunked data file not found at: {chunked_data_path}")
            _schemes = []
        
        # Initialize orchestrator with memory optimization
        persist_dir = indexed_data_path
        use_bm25 = False  # Disabled for memory savings
        use_reranker = False  # Disabled for memory savings
        
        logger.info(f"Initializing orchestrator with BM25: {use_bm25}, Reranker: {use_reranker}")
        logger.info(f"Using persist directory: {persist_dir}")
        
        _orchestrator = RAGOrchestrator(
            persist_directory=persist_dir,
            scheme_names=_schemes,
            use_bm25=use_bm25,
            use_reranker=use_reranker
        )
        
        _initialized = True
        after_memory = get_memory_usage()
        logger.info(f"Memory after orchestrator load: {after_memory} MB")
        logger.info("RAG orchestrator loaded successfully")
        
        return _orchestrator
        
    except Exception as e:
        logger.error(f"Error loading orchestrator: {str(e)}")
        st.error(f"Failed to initialize AI system: {str(e)}")
        return None

@st.cache_data
def get_available_schemes():
    """Get available mutual fund schemes with caching."""
    global _schemes
    if not _schemes:
        # Load schemes without initializing orchestrator
        data_path = os.getenv('PROCESSED_DATA_PATH', os.path.join(BASE, 'data', 'processed'))
        chunked_data_path = os.path.join(data_path, 'chunked_data_phase1.4.json')
        if os.path.exists(chunked_data_path):
            with open(chunked_data_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            _schemes = sorted(list(set(c['scheme_name'] for c in chunks)))
    return _schemes

def apply_custom_css():
    """Apply modern CSS styling for professional UI."""
    st.markdown("""
    <style>
    /* Professional theme with dark/light mode support */
    .main {
        padding-top: 2rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Header styling */
    .header-container {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
        text-align: center;
    }
    
    /* Card styling */
    .card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 2px solid #e0e0e0;
        padding: 0.75rem;
        transition: border-color 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #4ECDC4;
        box-shadow: 0 0 0 2px rgba(78, 205, 196, 0.2);
    }
    
    /* Chat message styling */
    .user-message {
        background: #4ECDC4;
        color: white;
        padding: 1rem;
        border-radius: 15px 15px 5px 15px;
        margin-bottom: 1rem;
        max-width: 80%;
        margin-left: auto;
    }
    
    .assistant-message {
        background: #f8f9fa;
        color: #333;
        padding: 1rem;
        border-radius: 15px 15px 15px 5px;
        margin-bottom: 1rem;
        max-width: 80%;
        margin-right: auto;
        border: 1px solid #e9ecef;
    }
    
    /* Loading spinner */
    .loading-spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 2rem;
    }
    
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background: white;
        border-radius: 0 15px 15px 0;
        box-shadow: 2px 0 4px rgba(0, 0, 0, 0.1);
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main {
            padding-top: 1rem;
        }
        
        .header-container {
            padding: 1rem;
        }
        
        .card {
            padding: 1rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

def render_header():
    """Render professional header."""
    st.markdown("""
    <div class="header-container">
        <h1 style="color: #2c3e50; margin-bottom: 0.5rem;">
            🏦 HDFC Mutual Fund Assistant
        </h1>
        <p style="color: #7f8c8d; margin: 0; font-size: 1.1rem;">
            Your intelligent guide to HDFC mutual fund information
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_memory_info():
    """Render memory usage information."""
    memory_usage = get_memory_usage()
    if isinstance(memory_usage, (int, float)):
        memory_color = "#27ae60" if memory_usage < 500 else "#e74c3c"
        st.markdown(f"""
        <div class="card">
            <h4 style="color: #2c3e50; margin-bottom: 0.5rem;">💾 Memory Usage</h4>
            <p style="color: {memory_color}; margin: 0; font-size: 1.2rem; font-weight: 600;">
                {memory_usage:.1f} MB
            </p>
        </div>
        """, unsafe_allow_html=True)

def render_query_interface():
    """Render modern query interface."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input(
            "💬 Ask about HDFC Mutual Funds",
            placeholder="e.g., What are the best equity funds for long-term investment?",
            key="query_input",
            help="Type your question about HDFC mutual funds here"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        query_button = st.button(
            "🔍 Search",
            type="primary",
            use_container_width=True,
            help="Click to search for information"
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return query, query_button

def render_chat_interface():
    """Render modern chat interface."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💬 Chat History")
    
    # Initialize chat history in session state
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat messages
    for message in st.session_state.chat_history:
        if message['role'] == 'user':
            st.markdown(f"""
            <div class="user-message">
                <strong>You:</strong> {message['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="assistant-message">
                <strong>Assistant:</strong> {message['content']}
            </div>
            """, unsafe_allow_html=True)
    
    # Chat input
    user_input = st.text_input(
        "Type your message...",
        key="chat_input",
        help="Type your message here"
    )
    
    if st.button("Send", key="send_button", help="Send your message"):
        if user_input.strip():
            st.session_state.chat_history.append({
                'role': 'user',
                'content': user_input.strip()
            })
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_schemes_info():
    """Render available schemes information."""
    schemes = get_available_schemes()
    if schemes:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Available Schemes")
        st.info(f"Found {len(schemes)} mutual fund schemes")
        
        # Display schemes in columns
        cols = st.columns(3)
        for i, scheme in enumerate(schemes[:9]):  # Show first 9 schemes
            with cols[i % 3]:
                st.markdown(f"• {scheme}")
        
        if len(schemes) > 9:
            st.info(f"... and {len(schemes) - 9} more schemes")
        
        st.markdown('</div>', unsafe_allow_html=True)

def process_query(query: str) -> Dict[str, Any]:
    """Process user query with error handling."""
    if not query or not query.strip():
        return {
            'answer': 'Please enter a valid question about HDFC mutual funds.',
            'status': 'error',
            'source': None
        }
    
    try:
        # Load orchestrator (cached)
        orchestrator = load_orchestrator()
        if orchestrator is None:
            return {
                'answer': 'Sorry, AI system is currently unavailable. Please try again later.',
                'status': 'error',
                'source': None
            }
        
        # Process query
        with st.spinner('🤔 Thinking...'):
            response = orchestrator.answer_query(query.strip())
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {
            'answer': f'Sorry, I encountered an error: {str(e)}',
            'status': 'error',
            'source': None
        }

def main():
    """Main Streamlit application."""
    # Apply custom CSS
    apply_custom_css()
    
    # Render header
    render_header()
    
    # Sidebar with additional info
    with st.sidebar:
        st.markdown("### 🛠️ System Info")
        render_memory_info()
        
        st.markdown("### 📋 Available Features")
        st.info("• 🏦 HDFC Mutual Fund Info\n• 💬 Interactive Chat\n• 📊 Scheme Details\n• 🔍 Smart Search")
        
        st.markdown("### ⚡ Performance")
        st.success("✅ Memory Optimized\n✅ Lazy Loading\n✅ Caching Enabled")
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["🔍 Search", "💬 Chat", "📊 Schemes"])
    
    with tab1:
        st.markdown("### 🔍 Search HDFC Mutual Funds")
        query, query_button = render_query_interface()
        
        if query_button and query:
            response = process_query(query)
            
            # Display response
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📝 Answer")
            
            if response['status'] == 'success':
                st.success(response['answer'])
                if response.get('source'):
                    st.info(f"📄 Source: {response['source']}")
            else:
                st.error(response['answer'])
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown("### 💬 Chat with Assistant")
        render_chat_interface()
    
    with tab3:
        st.markdown("### 📊 Available Schemes")
        render_schemes_info()
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; padding: 1rem; color: #7f8c8d;">
        <p>🏦 HDFC Mutual Fund Assistant | Powered by AI | Memory Optimized</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
