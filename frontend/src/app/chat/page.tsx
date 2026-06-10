"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { Bot, User, Send, Trash2, Loader2, MessageSquare } from "lucide-react";
import { useLLMChat } from "@/hooks/useLLMChat";
import { useWSStore } from "@/hooks/useWebSocket";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { format } from "date-fns";

export default function ChatPage() {
  const { messages, isTyping, sendMessage, clearChat } = useLLMChat();
  const { connected } = useWSStore();
  const [input, setInput] = useState("");
  const [mounted, setMounted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    setMounted(true);
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping || !connected) return;
    sendMessage(input);
    setInput("");
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        
        <main style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1.75rem", maxWidth: "900px", margin: "0 auto", width: "100%", height: "100%" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
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
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "1rem", paddingRight: "0.5rem", paddingBottom: "1rem" }}>
            {!mounted ? (
              <div style={{ display: "flex", flex: 1 }} />
            ) : messages.length === 0 ? (
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
                    
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem", alignItems: msg.role === "user" ? "flex-end" : "flex-start", maxWidth: "calc(100% - 3rem)" }}>
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
                      
                      <div style={{ 
                        fontSize: "0.6875rem", 
                        color: "var(--muted-foreground)", 
                        fontFamily: "var(--font-mono)",
                        paddingLeft: msg.role === "user" ? "0" : "0.5rem",
                        paddingRight: msg.role === "user" ? "0.5rem" : "0"
                      }}>
                        {msg.timestamp ? format(new Date(msg.timestamp), "MMM d, h:mm a") : ""}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSubmit} style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", background: "var(--card)", padding: "0.75rem", borderRadius: "1rem", border: "1px solid var(--border)", boxShadow: "0 4px 12px rgba(0,0,0,0.05)", opacity: !connected ? 0.6 : 1 }}>
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!connected}
              placeholder={connected ? "Ask anything..." : "Server is offline..."}
              style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--foreground)", padding: "0.5rem", fontSize: "0.9375rem", cursor: !connected ? "not-allowed" : "text" }}
            />
            <button 
              type="submit"
              disabled={!input.trim() || isTyping || !connected}
              style={{ width: "2.75rem", height: "2.75rem", borderRadius: "0.75rem", border: "none", background: (!input.trim() || isTyping || !connected) ? "var(--secondary)" : "var(--primary)", color: (!input.trim() || isTyping || !connected) ? "var(--muted-foreground)" : "var(--primary-foreground)", display: "flex", alignItems: "center", justifyContent: "center", cursor: (!input.trim() || isTyping || !connected) ? "not-allowed" : "pointer", transition: "all 0.2s" }}
            >
              {isTyping ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} style={{ transform: "translateX(-1px)" }} />}
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
