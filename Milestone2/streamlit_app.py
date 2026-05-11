import os
import sys
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

# Add Phase 2 and 3 src to path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

from orchestrator import RAGOrchestrator

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Streamlit_App")

# =============================================================================
# Configuration
# =============================================================================

def get_app_config():
    """Return app configuration constants."""
    return {
        "app_title": "HDFC Mutual Fund Assistant",
        "welcome_title": "Welcome to HDFC Mutual Fund Assistant",
        "welcome_subtitle": "Your AI-powered assistant for factual information about HDFC Mutual Fund schemes",
        "disclaimer": "Facts-only. No investment advice.",
        "suggested_questions": [
            "What is expense ratio?",
            "Explain SIP",
            "What is exit load?",
            "Best HDFC fund for beginners?",
            "How does NAV work?"
        ]
    }

# =============================================================================
# Custom CSS
# =============================================================================

def inject_custom_css():
    """Inject custom CSS for modern AI assistant UI with dark finance theme."""
    st.markdown("""
    <style>
        /* Global styles */
        .stApp {
            background-color: #0a0e27;
        }
        
        /* Sidebar styles */
        .css-1d391kg {
            background-color: #1a1f3a !important;
            border-right: 1px solid #2d3a5c !important;
        }
        
        /* Chat container */
        .chat-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* User message bubble */
        .user-message {
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            color: #ffffff;
            padding: 12px 16px;
            border-radius: 18px 18px 4px 18px;
            margin: 8px 0;
            max-width: 70%;
            margin-left: auto;
            box-shadow: 0 2px 8px rgba(0, 212, 170, 0.3);
            border: 1px solid #2d5a87;
        }
        
        /* Assistant message bubble */
        .assistant-message {
            background-color: #1f2937;
            color: #e5e7eb;
            padding: 12px 16px;
            border-radius: 18px 18px 18px 4px;
            margin: 8px 0;
            max-width: 70%;
            margin-right: auto;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            border: 1px solid #374151;
        }
        
        /* Welcome section */
        .welcome-section {
            text-align: center;
            padding: 40px 20px;
        }
        
        .welcome-title {
            font-size: 2.5rem;
            font-weight: 600;
            color: #00d4aa;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .welcome-subtitle {
            font-size: 1.1rem;
            color: #9ca3af;
            margin-bottom: 32px;
        }
        
        /* Suggestion pills */
        .suggestion-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin: 20px 0;
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .suggestion-pill {
            background-color: #1f2937;
            border: 1px solid #374151;
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: center;
        }
        
        .suggestion-pill:hover {
            background-color: #2d3a5c;
            border-color: #00d4aa;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 212, 170, 0.4);
        }
        
        .suggestion-text {
            color: #e5e7eb;
            font-size: 0.95rem;
            font-weight: 500;
        }
        
        /* Disclaimer */
        .disclaimer {
            background-color: rgba(245, 158, 11, 0.15);
            border-left: 4px solid #f59e0b;
            padding: 12px 16px;
            margin: 16px 0;
            border-radius: 4px;
            font-size: 0.9rem;
            color: #fbbf24;
        }
        
        /* Source information */
        .source-info {
            background-color: #1f2937;
            border-radius: 8px;
            padding: 12px;
            margin-top: 12px;
            font-size: 0.85rem;
            color: #9ca3af;
            border: 1px solid #374151;
        }
        
        .source-info a {
            color: #00d4aa;
            text-decoration: none;
        }
        
        .source-info a:hover {
            text-decoration: underline;
        }
        
        /* Sidebar buttons */
        .sidebar-button {
            width: 100%;
            padding: 10px 16px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s ease;
            margin-bottom: 8px;
        }
        
        /* Hide streamlit default elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        
        /* Chat input container */
        .chat-input-container {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #1a1f3a;
            padding: 16px;
            border-top: 1px solid #2d3a5c;
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.3);
        }
        
        /* Streamlit native elements dark theme */
        .stTextInput > div > div > input {
            background-color: #1f2937;
            color: #e5e7eb;
            border: 1px solid #374151;
        }
        
        .stButton > button {
            background-color: #1e3a5f;
            color: #ffffff;
            border: 1px solid #2d5a87;
        }
        
        .stButton > button:hover {
            background-color: #2d5a87;
            border-color: #00d4aa;
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# Session State Management
# =============================================================================

def initialize_session_state():
    """Initialize all session state variables."""
    config = get_app_config()
    
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None
        st.session_state.schemes = []
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = {}
    
    if 'current_chat_id' not in st.session_state:
        st.session_state.current_chat_id = None
    
    if 'show_welcome' not in st.session_state:
        st.session_state.show_welcome = True

@st.cache_data
def get_scheme_names():
    """Load scheme names from chunked data with caching."""
    chunked_data_path = os.path.join(BASE, 'data', 'processed', 'chunked_data_phase1.4.json')
    if os.path.exists(chunked_data_path):
        with open(chunked_data_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        scheme_names_list = sorted(list(set(c['scheme_name'] for c in chunks)))
        logger.info(f"Loaded {len(scheme_names_list)} schemes")
        return scheme_names_list
    return []

@st.cache_resource
def get_orchestrator(scheme_names):
    """Create and cache the RAG orchestrator with memory optimization."""
    persist_dir = os.path.join(BASE, 'data', 'indexed')
    
    # Use environment variables to control memory-intensive features
    use_bm25 = os.getenv('USE_BM25', 'false').lower() == 'true'
    use_reranker = os.getenv('USE_RERANKER', 'false').lower() == 'true'
    
    logger.info(f"Initializing orchestrator with BM25: {use_bm25}, Reranker: {use_reranker}")
    
    orch = RAGOrchestrator(
        persist_directory=persist_dir,
        scheme_names=scheme_names,
        use_bm25=use_bm25,
        use_reranker=use_reranker
    )
    logger.info("Orchestrator initialized and cached")
    return orch

def initialize_orchestrator():
    """Initialize the RAG orchestrator with error handling and caching."""
    if st.session_state.orchestrator is None:
        try:
            # Load schemes from cached function
            scheme_names_list = get_scheme_names()
            
            # Initialize orchestrator with caching
            st.session_state.orchestrator = get_orchestrator(scheme_names_list)
            st.session_state.schemes = scheme_names_list
            logger.info("Orchestrator initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing orchestrator: {str(e)}")
            st.session_state.orchestrator = None
            st.session_state.schemes = []
            return False
    return True

# =============================================================================
# Sidebar Components
# =============================================================================

def render_sidebar():
    """Render the left sidebar with title, new chat, history, and settings."""
    config = get_app_config()
    
    with st.sidebar:
        # App title
        st.markdown(f"""
        <div style="padding: 20px 0;">
            <h2 style="margin: 0; color: #1a1a1a; font-size: 1.5rem;">{config['app_title']}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # New Chat button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.session_state.show_welcome = True
            st.session_state.current_chat_id = None
            st.rerun()
        
        st.divider()
        
        # Chat History
        st.subheader("💬 Chat History")
        
        if st.session_state.chat_history:
            for chat_id, chat_title in st.session_state.chat_history.items():
                if st.button(f"💬 {chat_title[:30]}...", key=f"history_{chat_id}", use_container_width=True):
                    # Load chat history (simplified version)
                    st.session_state.current_chat_id = chat_id
                    st.rerun()
        else:
            st.caption("No chat history yet")
        
        st.divider()
        
        # Settings section
        st.subheader("⚙️ Settings")
        
        # Clear Chat button
        if st.button("🗑️ Clear Current Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.show_welcome = True
            st.rerun()
        
        # System status
        st.divider()
        st.subheader("🔧 System Status")
        if st.session_state.orchestrator:
            st.success("✅ RAG System Ready")
            st.caption(f"Schemes Loaded: {len(st.session_state.get('schemes', []))}")
        else:
            st.error("❌ RAG System Not Ready")
        
        # About
        st.divider()
        st.markdown("""
        **About**
        
        This AI-powered assistant answers factual questions about Mutual Fund schemes using RAG technology.
        """)

# =============================================================================
# Main Chat Area Components
# =============================================================================

def render_welcome_section():
    """Render the welcome section with title, subtitle, and suggested questions."""
    config = get_app_config()
    
    st.markdown(f"""
    <div class="welcome-section">
        <h1 class="welcome-title">{config['welcome_title']}</h1>
        <p class="welcome-subtitle">{config['welcome_subtitle']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Disclaimer
    st.markdown(f"""
    <div class="disclaimer">
        ⚠️ <strong>Disclaimer:</strong> {config['disclaimer']}
    </div>
    """, unsafe_allow_html=True)
    
    # Suggested questions
    st.markdown("<h3 style='text-align: center; color: #666; margin-bottom: 20px;'>Suggested Questions</h3>", unsafe_allow_html=True)
    
    cols = st.columns(3)
    for i, question in enumerate(config['suggested_questions']):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(question, key=f"suggestion_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": question})
                st.session_state.show_welcome = False
                st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)

def render_chat_message(message: Dict[str, Any]):
    """Render a single chat message with proper styling."""
    if message["role"] == "user":
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-end; margin: 12px 0;">
            <div class="user-message">
                {message['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Assistant message
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-start; margin: 12px 0;">
            <div class="assistant-message">
                {message['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Source information
        if 'source' in message or 'source_link' in message or 'last_updated' in message:
            source_parts = []
            if message.get('source_link'):
                source_parts.append(f"📄 <a href='{message['source_link']}' target='_blank'>Source</a>")
            elif message.get('source'):
                source_parts.append(f"📄 {message['source']}")
            if message.get('last_updated'):
                source_parts.append(f"🕐 {message['last_updated']}")
            
            if source_parts:
                st.markdown(f"""
                <div style="margin-left: 12px;">
                    <div class="source-info">
                        {' | '.join(source_parts)}
                    </div>
                </div>
                """, unsafe_allow_html=True)

def render_chat_history():
    """Render the chat conversation history."""
    for message in st.session_state.messages:
        render_chat_message(message)

def process_user_query(query: str):
    """Process user query and generate response using RAG orchestrator."""
    if not st.session_state.orchestrator:
        return {
            "role": "assistant",
            "content": "RAG system is not initialized. Please check the data files and try again."
        }
    
    try:
        response = st.session_state.orchestrator.answer_query(query)
        
        if response and response.get('answer'):
            return {
                "role": "assistant",
                "content": response['answer'],
                "source": response.get('source', ''),
                "source_link": response.get('source_link', ''),
                "last_updated": response.get('last_updated', '')
            }
        else:
            return {
                "role": "assistant",
                "content": "Sorry, I could not find an answer to your question. Please try rephrasing it or ask about a specific HDFC Mutual Fund scheme."
            }
    except Exception as e:
        logger.exception("Error during query processing")
        return {
            "role": "assistant",
            "content": f"Error processing your question: {str(e)}"
        }

def save_to_chat_history(query: str):
    """Save the current chat to history."""
    if not st.session_state.current_chat_id:
        chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_chat_id = chat_id
        st.session_state.chat_history[chat_id] = query[:50]

# =============================================================================
# Main Application
# =============================================================================

def main():
    """Main application function."""
    # Page configuration
    st.set_page_config(
        page_title="HDFC Mutual Fund Assistant",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inject custom CSS
    inject_custom_css()
    
    # Initialize session state
    initialize_session_state()
    
    # Initialize orchestrator
    with st.spinner("Initializing RAG system..."):
        if not initialize_orchestrator():
            st.error("Failed to initialize RAG system. Please check data files.")
    
    # Render sidebar
    render_sidebar()
    
    # Main content area
    config = get_app_config()
    
    # Show welcome section or chat history
    if st.session_state.show_welcome and not st.session_state.messages:
        render_welcome_section()
    else:
        # Render chat history
        render_chat_history()
    
    # Chat input
    if prompt := st.chat_input("Ask a question about HDFC Mutual Fund schemes..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.show_welcome = False
        
        # Save to chat history
        save_to_chat_history(prompt)
        
        # Process and display response
        with st.spinner("Searching and generating answer..."):
            response = process_user_query(prompt)
            st.session_state.messages.append(response)
        
        st.rerun()

if __name__ == "__main__":
    main()
