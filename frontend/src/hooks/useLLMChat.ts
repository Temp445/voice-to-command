import { useState, useRef, useCallback } from "react";

import { useChatStore } from "@/store/chatStore";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export function useLLMChat() {
  const { messages, setMessages, clear } = useChatStore();
  const [isTyping, setIsTyping] = useState(false);
  
  // This uses the browser's native fetch API to read the stream token by token
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;
    
    const userMsg: ChatMessage = {
      id: Math.random().toString(36).substring(7),
      role: "user",
      content: text,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    const assistantId = Math.random().toString(36).substring(7);
    setMessages(prev => [...prev, { id: assistantId, role: "assistant", content: "", timestamp: new Date() }]);

    try {
      const BASE = typeof window !== 'undefined' && window.location.hostname.includes("devtunnels.ms") 
        ? window.location.origin.replace("-3000", "-8000") + "/api"
        : "http://127.0.0.1:8000/api";
        
      const response = await fetch(`${BASE}/llm/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, stream: true }),
      });

      if (!response.ok) throw new Error("Network response was not ok");
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        setMessages(prev => 
          prev.map(msg => 
            msg.id === assistantId ? { ...msg, content: msg.content + chunk } : msg
          )
        );
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages(prev => 
        prev.map(msg => 
          msg.id === assistantId ? { ...msg, content: "⚠️ Error connecting to AI assistant. Check settings." } : msg
        )
      );
    } finally {
      setIsTyping(false);
    }
  }, []);

  const clearChat = useCallback(async () => {
    clear();
    try {
      const BASE = typeof window !== 'undefined' && window.location.hostname.includes("devtunnels.ms") 
        ? window.location.origin.replace("-3000", "-8000") + "/api"
        : "http://127.0.0.1:8000/api";
      await fetch(`${BASE}/llm/history`, { method: "DELETE" });
    } catch (e) {
      console.error("Failed to clear history on backend");
    }
  }, []);

  return { messages, isTyping, sendMessage, clearChat };
}
