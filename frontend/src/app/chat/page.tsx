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
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        
        <main className="flex-1 flex flex-col p-7 max-w-[900px] mx-auto w-full h-full">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-semibold text-[var(--foreground)] tracking-tight flex items-center gap-2.5">
                <Bot className="w-7 h-7 text-[var(--primary)]" /> AI Assistant
              </h1>
              <p className="text-zinc-500 text-sm mt-1">Chat with ACE</p>
            </div>
            
            <button 
              onClick={clearChat}
              title="Clear History"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--secondary)] text-zinc-500 hover:text-zinc-700 cursor-pointer text-[13px] font-semibold transition-all duration-200"
            >
              <Trash2 size={14} /> Clear
            </button>
          </div>

          {/* Chat Container */}
          <div className="flex-1 overflow-y-auto flex flex-col gap-4 pr-2 pb-4">
            {!mounted ? (
              <div className="flex flex-1" />
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-500 gap-4">
                <MessageSquare size={48} className="opacity-20" />
                <p>How can I help you today?</p>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div 
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex gap-4 max-w-[85%] ${msg.role === "user" ? "self-end flex-row-reverse" : "self-start flex-row"}`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${msg.role === "user" ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--secondary)] text-[var(--foreground)] border border-[var(--border)]"}`}>
                      {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
                    </div>
                    
                    <div className={`flex flex-col gap-1.5 max-w-[calc(100%-3rem)] ${msg.role === "user" ? "items-end" : "items-start"}`}>
                      <div className={`px-4.5 py-3.5 rounded-xl text-[15px] leading-relaxed shadow-sm ${msg.role === "user" ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] prose prose-invert max-w-none"}`}>
                        {msg.role === "user" ? (
                          msg.content
                        ) : (
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content || "..."}
                          </ReactMarkdown>
                        )}
                      </div>
                      
                      <div className={`text-[11px] text-zinc-500 font-mono ${msg.role === "user" ? "pr-2" : "pl-2"}`}>
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
          <form onSubmit={handleSubmit} className={`mt-4 flex gap-3 bg-[var(--card)] p-3 rounded-2xl border border-[var(--border)] shadow-md transition-opacity ${!connected ? "opacity-60" : "opacity-100"}`}>
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!connected}
              placeholder={connected ? "Ask anything..." : "Server is offline..."}
              className={`flex-1 bg-transparent border-none outline-none text-[var(--foreground)] p-2 text-[15px] ${!connected ? "cursor-not-allowed" : "cursor-text"}`}
            />
            <button 
              type="submit"
              disabled={!input.trim() || isTyping || !connected}
              className={`w-11 h-11 rounded-xl border-none flex items-center justify-center transition-all duration-200 ${(!input.trim() || isTyping || !connected) ? "bg-[var(--secondary)] text-zinc-500 cursor-not-allowed" : "bg-[var(--primary)] text-[var(--primary-foreground)] cursor-pointer active:scale-95 hover:opacity-90"}`}
            >
              {isTyping ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} className="-translate-x-[1px]" />}
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
