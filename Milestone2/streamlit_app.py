import os
import sys
import json
import logging
from typing import List, Dict, Any
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

# Page configuration
st.set_page_config(
    page_title="Mutual Fund FAQ Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0D0D0D;
    }
    .stChatMessage {
        background-color: #1A1A1A;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .user-message {
        background-color: #2A2A2A;
        border-left: 4px solid #00D09C;
    }
    .assistant-message {
        background-color: #151515;
        border-left: 4px solid #6366f1;
    }
    .main-header {
        color: #00D09C;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .sub-header {
        color: #ffffff;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'orchestrator' not in st.session_state:
    with st.spinner("Initializing RAG system..."):
        try:
            # Load schemes
            chunked_data_path = os.path.join(BASE, 'data', 'processed', 'chunked_data_phase1.4.json')
            if os.path.exists(chunked_data_path):
                with open(chunked_data_path, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)
                scheme_names_list = sorted(list(set(c['scheme_name'] for c in chunks)))
            else:
                scheme_names_list = []
                st.warning("Data file not found. Please run the ingestion pipeline first.")

            # Initialize orchestrator
            persist_dir = os.path.join(BASE, 'data', 'indexed')
            st.session_state.orchestrator = RAGOrchestrator(
                persist_directory=persist_dir,
                scheme_names=scheme_names_list
            )
            st.session_state.schemes = scheme_names_list
            logger.info("Orchestrator initialized successfully")
        except Exception as e:
            st.error(f"Error initializing RAG system: {str(e)}")
            st.session_state.orchestrator = None
            st.session_state.schemes = []

# Header
st.markdown('<div class="main-header">Mutual Fund FAQ Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Ask factual questions about HDFC Mutual Fund schemes</div>', unsafe_allow_html=True)

# Disclaimer
st.warning("⚠️ **Disclaimer**: Facts-only. No investment advice.")

# Sidebar
with st.sidebar:
    st.header("📊 Available Schemes")
    if st.session_state.get('schemes'):
        for scheme in st.session_state.schemes:
            st.write(f"• {scheme}")
    else:
        st.write("No schemes loaded")
    
    st.divider()
    
    st.header("ℹ️ About")
    st.write("""
    This AI-powered assistant answers factual questions about Mutual Fund schemes using:
    
    - **RAG Engine**: Retrieves relevant information from official documents
    - **Vector Search**: Uses semantic similarity to find accurate answers
    - **LLM Integration**: Generates natural language responses
    """)
    
    st.divider()
    
    st.header("🔧 System Status")
    if st.session_state.get('orchestrator'):
        st.success("✅ RAG System Ready")
        st.write(f"**Schemes Loaded**: {len(st.session_state.get('schemes', []))}")
    else:
        st.error("❌ RAG System Not Ready")

# Chat interface
st.divider()

# Initialize chat history
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(f'<div class="stChatMessage user-message">{message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="stChatMessage assistant-message">{message["content"]}</div>', unsafe_allow_html=True)
            # Display source information for history
            if 'source' in message or 'source_link' in message or 'last_updated' in message:
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    if message.get('source_link'):
                        st.markdown(f"📄 **Source**: [Link]({message['source_link']})")
                    elif message.get('source'):
                        st.markdown(f"📄 **Source**: {message['source']}")
                with col2:
                    if message.get('last_updated'):
                        st.markdown(f"🕐 **Last Updated**: {message['last_updated']}")

# Chat input
if prompt := st.chat_input("Ask a question about HDFC Mutual Fund schemes..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(f'<div class="stChatMessage user-message">{prompt}</div>', unsafe_allow_html=True)
    
    # Generate response
    if st.session_state.get('orchestrator'):
        with st.chat_message("assistant"):
            with st.spinner("Searching and generating answer..."):
                try:
                    response = st.session_state.orchestrator.answer_query(prompt)
                    
                    if response and response.get('answer'):
                        answer = response['answer']
                        source = response.get('source', '')
                        source_link = response.get('source_link', '')
                        last_updated = response.get('last_updated', '')
                        
                        # Display answer
                        st.markdown(f'<div class="stChatMessage assistant-message">{answer}</div>', unsafe_allow_html=True)
                        
                        # Display source information
                        if source or source_link or last_updated:
                            st.divider()
                            col1, col2 = st.columns(2)
                            with col1:
                                if source_link:
                                    st.markdown(f"📄 **Source**: [Link]({source_link})")
                                elif source:
                                    st.markdown(f"📄 **Source**: {source}")
                            with col2:
                                if last_updated:
                                    st.markdown(f"🕐 **Last Updated**: {last_updated}")
                        
                        # Add to chat history
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "source": source,
                            "source_link": source_link,
                            "last_updated": last_updated
                        })
                    else:
                        st.markdown('<div class="stChatMessage assistant-message">Sorry, I could not find an answer to your question. Please try rephrasing it or ask about a specific HDFC Mutual Fund scheme.</div>', unsafe_allow_html=True)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "Sorry, I could not find an answer to your question. Please try rephrasing it or ask about a specific HDFC Mutual Fund scheme."
                        })
                except Exception as e:
                    error_msg = f"Error processing your question: {str(e)}"
                    st.markdown(f'<div class="stChatMessage assistant-message">{error_msg}</div>', unsafe_allow_html=True)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                    logger.exception("Error during chat processing")
    else:
        with st.chat_message("assistant"):
            st.markdown('<div class="stChatMessage assistant-message">RAG system is not initialized. Please check the data files and try again.</div>', unsafe_allow_html=True)
            st.session_state.messages.append({
                "role": "assistant",
                "content": "RAG system is not initialized. Please check the data files and try again."
            })

# Clear chat button
if st.button("Clear Chat", key="clear_chat"):
    st.session_state.messages = []
    st.rerun()
