'use client';

import { useState, useEffect } from 'react';
import { Send, Bot, User, ExternalLink, Clock, MessageSquare, Settings, Plus, Trash2, Menu } from 'lucide-react';
import axios from 'axios';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
}

interface ApiResponse {
  answer: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
  status: string;
}

const SUGGESTED_QUESTIONS = [
  "What is the expense ratio of HDFC Balanced Advantage Fund?",
  "How do I start an SIP in HDFC funds?",
  "What is the exit load for HDFC Flexi Cap Fund?",
  "Which is the best HDFC fund for beginners?",
  "How does NAV work in mutual funds?"
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatHistory, setChatHistory] = useState<string[]>([]);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8501';

  useEffect(() => {
    // Check backend health on mount
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      console.log('Backend health:', response.data);
    } catch (error) {
      console.error('Backend not available:', error);
    }
  };

  const handleSendMessage = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text) return;

    const userMessage: Message = { role: 'user', content: text };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setShowWelcome(false);
    setIsLoading(true);

    try {
      const response = await axios.post<ApiResponse>(`${API_BASE_URL}/query`, {
        query: text,
        chat_history: messages
      });

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.data.answer,
        source: response.data.source,
        source_link: response.data.source_link,
        last_updated: response.data.last_updated
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again later.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setShowWelcome(true);
  };

  const handleNewChat = () => {
    setMessages([]);
    setShowWelcome(true);
    setInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-white border-r border-gray-200 flex flex-col`}>
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-xl font-bold text-blue-600">HDFC Mutual Fund Assistant</h1>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors mb-4"
          >
            <Plus size={16} />
            New Chat
          </button>
          
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Chat History</h3>
            <div className="space-y-1">
              {chatHistory.length === 0 ? (
                <p className="text-sm text-gray-500">No previous chats</p>
              ) : (
                chatHistory.map((chat, index) => (
                  <div key={index} className="text-sm text-gray-600 hover:bg-gray-100 p-2 rounded cursor-pointer">
                    Chat {index + 1}
                  </div>
                ))
              )}
            </div>
          </div>
          
          <button
            onClick={handleClearChat}
            className="w-full flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <Trash2 size={16} />
            Clear Current Chat
          </button>
        </div>
        
        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Settings size={16} />
            Settings
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <Menu size={20} />
          </button>
          <h2 className="text-lg font-semibold text-gray-800">Mutual Fund Assistant</h2>
          <div className="w-10"></div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4">
          {showWelcome && messages.length === 0 ? (
            <div className="text-center py-12">
              <div className="mb-8">
                <Bot size={48} className="mx-auto text-blue-600 mb-4" />
                <h1 className="text-3xl font-bold text-gray-800 mb-2">Welcome to HDFC Mutual Fund Assistant</h1>
                <p className="text-gray-600 mb-8">Ask me anything about HDFC mutual funds</p>
              </div>

              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-8 text-left max-w-2xl mx-auto">
                <p className="text-sm text-yellow-800">
                  <strong>Disclaimer:</strong> This is an AI assistant providing information about HDFC mutual funds. 
                  Please consult with a financial advisor before making investment decisions.
                </p>
              </div>

              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-700 mb-4">Suggested Questions</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-4xl mx-auto">
                  {SUGGESTED_QUESTIONS.map((question, index) => (
                    <button
                      key={index}
                      onClick={() => handleSendMessage(question)}
                      className="p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-all text-left"
                    >
                      <p className="text-sm text-gray-700">{question}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-w-4xl mx-auto">
              {messages.map((message, index) => (
                <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-2xl ${message.role === 'user' ? 'order-2' : 'order-1'}`}>
                    <div className={`flex items-start gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                      <div className={`p-3 rounded-2xl ${
                        message.role === 'user' 
                          ? 'bg-blue-600 text-white' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      </div>
                      <div className={`mt-1 ${message.role === 'user' ? 'text-right' : ''}`}>
                        {message.role === 'user' ? (
                          <User size={16} className="text-blue-600" />
                        ) : (
                          <Bot size={16} className="text-gray-600" />
                        )}
                      </div>
                    </div>
                    
                    {message.role === 'assistant' && (message.source || message.source_link || message.last_updated) && (
                      <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          {message.source_link ? (
                            <a 
                              href={message.source_link} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
                            >
                              <ExternalLink size={14} />
                              {message.source}
                            </a>
                          ) : message.source ? (
                            <span className="flex items-center gap-1">
                              <MessageSquare size={14} />
                              {message.source}
                            </span>
                          ) : null}
                          
                          {message.last_updated && (
                            <span className="flex items-center gap-1">
                              <Clock size={14} />
                              {message.last_updated}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-3">
                    <Bot size={16} className="text-gray-600" />
                    <div className="p-3 rounded-2xl bg-gray-100">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 p-4 bg-white">
          <div className="max-w-4xl mx-auto flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about HDFC mutual funds..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              disabled={isLoading}
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={isLoading || !input.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Send size={16} />
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
