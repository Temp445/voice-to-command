"use client";

import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import { api } from "@/lib/api";
import { useToastStore } from "@/store/toastStore";

// Extracted types for SpeechRecognition since TypeScript doesn't include them by default
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export default function MobileRemote() {
  const [isListening, setIsListening] = useState(false);
  const [text, setText] = useState("");
  const [status, setStatus] = useState("Ready");
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // Initialize speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onstart = () => {
        setIsListening(true);
        setStatus("Listening...");
      };

      recognition.onresult = (event: any) => {
        const current = event.resultIndex;
        const transcript = event.results[current][0].transcript;
        setText(transcript);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setStatus(`Error: ${event.error}`);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        setStatus("Processing...");
      };

      recognitionRef.current = recognition;
    } else {
      setStatus("Speech recognition not supported in this browser");
    }
  }, []);

  // Handle auto-submit when listening stops
  useEffect(() => {
    if (!isListening && text && status === "Processing...") {
      sendCommand(text);
      setStatus("Ready");
    }
  }, [isListening, status, text]);

  const toggleListen = () => {
    if (!recognitionRef.current) return;
    
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      setText("");
      recognitionRef.current.start();
    }
  };

  const sendCommand = async (commandText: string) => {
    if (!commandText.trim()) return;
    
    setStatus("Sending...");
    try {
      const res = await api.executeCommand(commandText, "mobile-remote");
      if (res.status !== "success") {
        useToastStore.getState().toast({
          type: "error",
          title: "Command Failed",
          description: res.result,
        });
      } else {
        useToastStore.getState().toast({
          type: "success",
          title: "Command Executed",
          description: res.result,
        });
      }
      setText("");
      setStatus("Ready");
    } catch (err: any) {
      useToastStore.getState().toast({
        type: "error",
        title: "Connection Error",
        description: err.message || "Failed to send command",
      });
      setStatus("Ready");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background p-6 text-center">
      <h1 className="text-3xl font-bold mb-2">ACE Remote</h1>
      <p className="text-muted-foreground mb-12">{status}</p>

      <button
        onClick={toggleListen}
        className={`w-40 h-40 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl mb-12 ${
          isListening 
            ? "bg-red-500 hover:bg-red-600 animate-pulse scale-110" 
            : "bg-primary hover:bg-primary/90"
        }`}
      >
        {isListening ? (
          <MicOff className="w-16 h-16 text-white" />
        ) : (
          <Mic className="w-16 h-16 text-primary-foreground" />
        )}
      </button>

      <div className="w-full max-w-md relative flex items-center">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendCommand(text)}
          placeholder="Or type a command..."
          className="w-full p-4 rounded-xl border border-input bg-background/50 backdrop-blur pr-14 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button 
          onClick={() => sendCommand(text)}
          className="absolute right-2 p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
