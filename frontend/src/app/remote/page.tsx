"use client";

import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Send, RefreshCw, Sun, Moon } from "lucide-react";
import { api } from "@/lib/api";
import { useToastStore } from "@/store/toastStore";
import { useSettingsStore } from "@/store/settingsStore";

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
  const { theme, update } = useSettingsStore();
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
    if (!isListening && status === "Processing...") {
      if (text.trim()) {
        sendCommand(text);
      } else {
        setStatus("Ready");
      }
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
    <div className="relative flex flex-col items-center min-h-[100dvh] bg-gradient-to-b from-background to-background/80 overflow-hidden text-center">
      {/* Dynamic Background Effects */}
      <div className={`absolute inset-0 bg-primary/5 transition-opacity duration-1000 ${isListening ? 'opacity-100' : 'opacity-0'}`} />
      {isListening && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary/20 rounded-full blur-[100px] animate-pulse pointer-events-none" />
      )}

      {/* Floating Controls */}
      <div className="absolute top-8 right-6 flex items-center gap-3 z-30">
        <button
          onClick={() => update({ theme: theme === "dark" ? "light" : "dark" })}
          className="p-3 rounded-full bg-muted/40 hover:bg-muted/80 backdrop-blur-md border border-white/10 shadow-sm transition-all"
          aria-label="Toggle Theme"
        >
          {theme === "dark" ? <Sun className="w-5 h-5 text-yellow-400" /> : <Moon className="w-5 h-5 text-indigo-500" />}
        </button>
        <button
          onClick={() => window.location.reload()}
          className="p-3 rounded-full bg-muted/40 hover:bg-muted/80 backdrop-blur-md border border-white/10 shadow-sm transition-all active:rotate-180 duration-500"
          aria-label="Refresh Page"
        >
          <RefreshCw className="w-5 h-5 text-foreground" />
        </button>
      </div>

      {/* Absolute Header & Live Transcript (doesn't push content down) */}
      <div className="absolute top-8 left-0 right-0 w-full z-10 px-6 flex flex-col items-center pointer-events-none">
        <h1 className="text-2xl font-bold tracking-tight text-foreground pointer-events-auto">
          ACE Remote
        </h1>

        {/* Big Live Transcript Display */}
        <div className="min-h-[5rem] mt-4 flex items-center justify-center max-w-sm mx-auto pointer-events-auto">
          {text ? (
            <p className="text-2xl font-semibold tracking-tight text-foreground/90 animate-in fade-in slide-in-from-bottom-2">
              "{text}"
            </p>
          ) : isListening ? (
            <div className="flex gap-1.5 items-center justify-center opacity-50">
              <div className="w-2 h-2 rounded-full bg-primary animate-bounce [animation-delay:-0.3s]" />
              <div className="w-2 h-2 rounded-full bg-primary animate-bounce [animation-delay:-0.15s]" />
              <div className="w-2 h-2 rounded-full bg-primary animate-bounce" />
            </div>
          ) : null}
        </div>
      </div>

      {/* Main Mic Button Area (Perfectly Centered) */}
      <div className="flex-1 flex flex-col items-center justify-center w-full z-10 -mt-10">
        <button
          onClick={toggleListen}
          className={`relative group flex items-center justify-center transition-all duration-500 shadow-xl ${
            isListening 
              ? "w-48 h-48 rounded-full bg-red-500 scale-105" 
              : "w-40 h-40 rounded-full border border-gray-400  dark:border-gray-100 bg-foreground text-background hover:scale-105"
          }`}
        >
          {isListening && (
            <>
              <div className="absolute inset-0 rounded-full border-4 border-red-500/50 animate-ping" />
              <div className="absolute inset-0 rounded-full border-2 border-red-500/30 animate-pulse delay-150" />
            </>
          )}
          {isListening ? (
            <MicOff className="w-16 h-16 text-white drop-shadow-md" />
          ) : (
            <Mic className="w-16 h-16 text-gray-400 dark:text-gray-500 drop-shadow-md" />
          )}
        </button>
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest absolute bottom-62">{status}</p>
      </div>

      {/* Floating Pill Command Bar */}
      <div className="fixed bottom-6 left-4 right-4 md:left-1/2 md:-translate-x-1/2 md:w-full md:max-w-lg md:bottom-10 z-20 pb-safe">
        <div className="w-full relative flex items-center p-2 h-16 rounded-full bg-background/80 backdrop-blur-3xl shadow-[0_8px_30px_rgb(0,0,0,0.12)] border border-foreground/10 ring-1 ring-black/5 dark:ring-white/5 transition-all duration-300 focus-within:ring-primary/50 focus-within:border-primary/50 focus-within:-translate-y-1">
          
          {/* Status Icon */}
          <div className="pl-4 pr-3 text-muted-foreground flex items-center justify-center">
            {isListening ? (
              <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse shadow-[0_0_10px_rgba(239,68,68,0.8)]" />
            ) : (
              <div className="w-3 h-3 rounded-full bg-foreground/20" />
            )}
          </div>

          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendCommand(text)}
            placeholder="Type or Speak..."
            className="flex-1 h-full bg-transparent focus:outline-none text-foreground placeholder:text-gray-500 dark:placeholder:text-gray-400 text-lg"
            autoComplete="off"
            spellCheck="false"
          />

          {/* Send Button */}
          <button 
            onClick={() => sendCommand(text)}
            disabled={!text.trim() || isListening}
            className="w-12 h-12 flex flex-none items-center justify-center rounded-full bg-foreground text-background disabled:bg-muted disabled:text-muted-foreground hover:opacity-90 transition-all duration-300 active:scale-90 group"
          >
            <Send className="w-5 h-5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          </button>
        </div>
      </div>
    </div>
  );
}
