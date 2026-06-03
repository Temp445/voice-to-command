"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { Bot, User, Send, Trash2, Loader2, MessageSquare } from "lucide-react";
import { useLLMChat } from "@/hooks/useLLMChat";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatPage() {
  const { messages, isTyping, sendMessage, clearChat } = useLLMChat();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    sendMessage(input);
    setInput("");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)] flex-col md:flex-row">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden relative">
        <TopBar />
        
        <main className="flex flex-col flex-1 p-4 md:p-7 max-w-4xl mx-auto w-full h-full">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <Bot style={{ width: "1.75rem", height: "1.75rem", color: "var(--primary)" }} /> AI Assistant
              </h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Chat with ACE</p>
            </div>
            
            <button 
              onClick={clearChat}
              title="Clear History"
              style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem 1rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--muted-foreground)", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 600, transition: "all 0.2s" }}
            >
              <Trash2 size={14} /> Clear
            </button>
          </div>

          {/* Chat Container */}
          <div className="flex-1 overflow-y-auto flex flex-col gap-4 pr-2 pb-4">
            {messages.length === 0 ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--muted-foreground)", gap: "1rem" }}>
                <MessageSquare size={48} style={{ opacity: 0.2 }} />
                <p>How can I help you today?</p>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div 
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ 
                      display: "flex", 
                      gap: "1rem", 
                      alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                      maxWidth: "85%",
                      flexDirection: msg.role === "user" ? "row-reverse" : "row"
                    }}
                  >
                    <div style={{ width: "2rem", height: "2rem", borderRadius: "0.5rem", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: msg.role === "user" ? "var(--primary)" : "var(--secondary)", color: msg.role === "user" ? "var(--primary-foreground)" : "var(--foreground)", border: msg.role === "assistant" ? "1px solid var(--border)" : "none" }}>
                      {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
                    </div>
                    
                    <div style={{ 
                      background: msg.role === "user" ? "var(--primary)" : "var(--card)", 
                      color: msg.role === "user" ? "var(--primary-foreground)" : "var(--foreground)", 
                      padding: "0.875rem 1.125rem", 
                      borderRadius: "0.75rem",
                      border: msg.role === "user" ? "none" : "1px solid var(--border)",
                      fontSize: "0.9375rem",
                      lineHeight: 1.6,
                      boxShadow: "0 2px 8px rgba(0,0,0,0.05)"
                    }} className={msg.role === "user" ? "" : "prose prose-invert max-w-none"}>
                      {msg.role === "user" ? (
                        msg.content
                      ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content || "..."}
                        </ReactMarkdown>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSubmit} className="mt-4 flex gap-3 bg-[var(--card)] p-3 rounded-2xl border border-[var(--border)] shadow-sm">
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything..."
              className="flex-1 bg-transparent border-none outline-none text-[var(--foreground)] p-2 text-[0.9375rem]"
            />
            <button 
              type="submit"
              disabled={!input.trim() || isTyping}
              style={{ width: "2.75rem", height: "2.75rem", borderRadius: "0.75rem", border: "none", background: !input.trim() || isTyping ? "var(--secondary)" : "var(--primary)", color: !input.trim() || isTyping ? "var(--muted-foreground)" : "var(--primary-foreground)", display: "flex", alignItems: "center", justifyContent: "center", cursor: !input.trim() || isTyping ? "not-allowed" : "pointer", transition: "all 0.2s" }}
            >
              {isTyping ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} style={{ transform: "translateX(-1px)" }} />}
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
