"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, Mic, Volume2, Globe, Shield, CheckCircle2, Eye, EyeOff, Bot, Loader2, Link2, RefreshCw, HardDrive } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useSettingsStore } from "@/store/settingsStore";
import { useWSStore } from "@/hooks/useWebSocket";
import { api, getResolvedBaseUrl, resolvedBackendPort } from "@/lib/api";
import { invoke } from "@tauri-apps/api/core";

const card = { background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" };
const hdr = { padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.75rem", background: "rgba(255,255,255,0.02)" };
const body = { padding: "1.5rem", display: "flex", flexDirection: "column" as const, gap: "1.5rem" };
const lbl = { fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.375rem" } as React.CSSProperties;
const sub = { fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.25rem" };
const inp = { width: "100%", background: "var(--input)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.625rem 0.875rem", fontSize: "0.875rem", color: "var(--foreground)", fontFamily: "var(--font-mono)", outline: "none", transition: "border-color 0.2s" } as React.CSSProperties;
const btnA = { padding: "0.5rem 1rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer", border: "1px solid var(--ring)", background: "var(--primary)", color: "var(--primary-foreground)", transition: "all 0.15s", boxShadow: "0 2px 4px rgba(0,0,0,0.1)" } as React.CSSProperties;
const btnI = { padding: "0.5rem 1rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 500, cursor: "pointer", border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--muted-foreground)", transition: "all 0.15s" } as React.CSSProperties;

const Toggle = ({ checked, onChange }: { checked: boolean, onChange: () => void }) => (
  <button onClick={onChange}
    style={{
      width: "2.75rem", height: "1.5rem", borderRadius: "9999px",
      background: checked ? "var(--primary)" : "var(--border)",
      border: "none", position: "relative", flexShrink: 0, cursor: "pointer",
      transition: "background 0.3s ease",
    }}>
    <span style={{
      position: "absolute", top: "0.15rem", left: "0.15rem",
      width: "1.2rem", height: "1.2rem",
      background: "var(--background)", borderRadius: "50%",
      transition: "transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1)",
      transform: checked ? "translateX(1.25rem)" : "translateX(0)",
      boxShadow: "0 2px 4px rgba(0,0,0,0.2)"
    }} />
  </button>
);

const TABS = [
  { id: "voice", label: "Voice Recognition", icon: Mic },
  { id: "tts", label: "Text-to-Speech", icon: Volume2 },
  { id: "ai", label: "AI Assistant", icon: Bot },
  { id: "browser", label: "Browser Automation", icon: Globe },
  { id: "system", label: "System Preferences", icon: Shield }
];

export default function SettingsPage() {
  const settings = useSettingsStore();
  const { connected, scanLastAt, scanAppCount } = useWSStore();
  const [activeTab, setActiveTab] = useState("voice");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);

  // LLM State
  const [providers, setProviders] = useState<{ id: string; name: string; models: string[] }[]>([]);
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // STT Tester State
  const [sttTestActive, setSttTestActive] = useState(false);
  const [sttTestText, setSttTestText] = useState("");
  const [sttTestDuration, setSttTestDuration] = useState<number | null>(null);
  const sttWsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const isTestingRef = useRef(false);

  // TTS State
  const [testTtsText, setTestTtsText] = useState("Hello, I am your desktop assistant.");
  const [testingTts, setTestingTts] = useState(false);

  // Scan State
  const [scanning, setScanning] = useState(false);

  // Clear spinner when backend broadcasts scan_complete
  useEffect(() => {
    if (scanLastAt) setScanning(false);
  }, [scanLastAt]);

  useEffect(() => {
    api.getLLMProviders().then((data: any) => setProviders(data)).catch(err => console.error(err));
    api.getSettings().then((data: any) => {
      settings.update({
        wakeWord: data.wake_word, sttProvider: data.stt_provider, sttNoiseCancellation: data.stt_noise_cancellation,
        whisperModel: data.whisper_model, ttsProvider: data.tts_provider, piperVoice: data.piper_voice,
        activeModeTimeout: data.active_mode_timeout, requireWakeWordAlways: data.require_wake_word_always,
        browserType: data.browser_type, startupOnBoot: data.startup_on_boot, minimizeToTray: data.minimize_to_tray,
        theme: data.theme, browserAnimationsEnabled: data.browser_animations_enabled, enableDesktopOverlay: data.enable_desktop_overlay,
        crmUrl: data.crm_url, crmKeywords: data.crm_keywords,
        crmSites: (() => {
          try { return JSON.parse(data.crm_sites || "[]") || []; } catch { return []; }
        })(),
        llmEnabled: data.llm_enabled, llmProvider: data.llm_provider, llmModel: data.llm_model,
        llmMode: data.llm_mode, llmTemperature: data.llm_temperature,
        scanMode: (data.scan_mode as "auto" | "manual") || "manual",
      });
      setInitialLoaded(true);
    }).catch(err => console.error(err));
  }, []);

  useEffect(() => {
    if (!initialLoaded) return;

    // Sync the Start on Boot setting with the OS registry
    if (typeof window !== 'undefined' && '__TAURI_IPC__' in window) {
      invoke(settings.startupOnBoot ? "enable_autostart" : "disable_autostart").catch(err => console.error("Autostart sync failed:", err));
    }

    const timer = setTimeout(() => handleSave(), 500);
    return () => clearTimeout(timer);
  }, [
    initialLoaded,
    settings.wakeWord, settings.sttProvider, settings.sttNoiseCancellation, settings.whisperModel,
    settings.ttsProvider, settings.piperVoice, settings.theme, settings.browserType,
    settings.startupOnBoot, settings.minimizeToTray, settings.browserAnimationsEnabled, settings.enableDesktopOverlay,
    settings.activeModeTimeout, settings.requireWakeWordAlways,
    settings.crmUrl, settings.crmKeywords, JSON.stringify(settings.crmSites),
    settings.llmEnabled, settings.llmProvider, settings.llmModel, settings.llmMode,
    settings.llmTemperature, settings.llmApiKey, settings.scanMode
  ]);

  const handleTestLlm = async () => {
    setTestingLlm(true); setTestResult(null);
    try {
      await handleSave();
      const res: any = await api.testLLM();
      if (res.ok) setTestResult({ ok: true, msg: `Success! Model replied: ${res.reply}` });
      else setTestResult({ ok: false, msg: res.error || "Connection failed" });
    } catch (err: any) { setTestResult({ ok: false, msg: err.message || "Request failed" }); }
    finally { setTestingLlm(false); }
  };

  const handleTestTts = async () => {
    if (!testTtsText.trim()) return;
    setTestingTts(true);
    try {
      const base = await getResolvedBaseUrl();
      const response = await fetch(`${base}/voice/test-tts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: testTtsText, provider: settings.ttsProvider, piper_voice: settings.piperVoice }),
      });
      if (!response.ok) throw new Error("TTS request failed");
      const blob = await response.blob();
      const audio = new Audio(URL.createObjectURL(blob));
      audio.play();
    } catch (err) { console.error("Test TTS failed:", err); }
    finally { setTestingTts(false); }
  };

  const startSttTest = async () => {
    if (isTestingRef.current) return;
    isTestingRef.current = true;
    setSttTestActive(true);
    try {
      setSttTestText("Connecting to microphone...");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          noiseSuppression: true,
          echoCancellation: true,
          autoGainControl: true
        }
      });
      if (!isTestingRef.current) {
        stream.getTracks().forEach(t => t.stop());
        return;
      }
      mediaStreamRef.current = stream;

      await getResolvedBaseUrl();
      const host = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.host.split(":")[0];
      const wsUrl = (window.location.protocol === "https:" ? "wss://" : "ws://") + host + ":" + resolvedBackendPort + "/api/voice/ws-test-stt";
      const ws = new WebSocket(wsUrl);
      sttWsRef.current = ws;

      ws.onopen = () => {
        setSttTestText("Listening... Speak now.");

        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
        audioContextRef.current = audioContext;
        const source = audioContext.createMediaStreamSource(stream);

        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const inputData = e.inputBuffer.getChannelData(0);
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            let s = Math.max(-1, Math.min(1, inputData[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          ws.send(pcm16.buffer);
        };

        source.connect(processor);
        processor.connect(audioContext.destination);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.text) setSttTestText(data.text);
          if (data.duration_ms) setSttTestDuration(data.duration_ms);
        } catch (err) { }
      };

      ws.onclose = () => { stopSttTest(); };
    } catch (err) {
      console.error(err);
      setSttTestText("Failed to access microphone.");
      setSttTestActive(false);
      isTestingRef.current = false;
    }
  };

  const stopSttTest = () => {
    isTestingRef.current = false;
    setSttTestActive(false);
    setSttTestDuration(null);
    setSttTestText("");
    if (processorRef.current && audioContextRef.current) processorRef.current.disconnect();
    if (audioContextRef.current) { audioContextRef.current.close().catch(() => { }); audioContextRef.current = null; }
    if (mediaStreamRef.current) { mediaStreamRef.current.getTracks().forEach(t => t.stop()); mediaStreamRef.current = null; }
    if (sttWsRef.current) {
      if (sttWsRef.current.readyState === WebSocket.OPEN) sttWsRef.current.send(JSON.stringify({ type: "stop" }));
      setTimeout(() => {
        if (sttWsRef.current) sttWsRef.current.close();
        sttWsRef.current = null;
      }, 500);
    }
  };

  const handleToggleSttTest = () => {
    if (sttTestActive) stopSttTest();
    else startSttTest();
  };

  useEffect(() => {
    return () => { stopSttTest(); };
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const patch: Record<string, unknown> = {
        wake_word: settings.wakeWord, stt_provider: settings.sttProvider, stt_noise_cancellation: settings.sttNoiseCancellation,
        whisper_model: settings.whisperModel, tts_provider: settings.ttsProvider, piper_voice: settings.piperVoice,
        active_mode_timeout: settings.activeModeTimeout, require_wake_word_always: settings.requireWakeWordAlways,
        browser_type: settings.browserType, startup_on_boot: settings.startupOnBoot, minimize_to_tray: settings.minimizeToTray,
        theme: settings.theme, browser_animations_enabled: settings.browserAnimationsEnabled, enable_desktop_overlay: settings.enableDesktopOverlay,
        crm_url: settings.crmUrl, crm_keywords: settings.crmKeywords,
        crm_sites: JSON.stringify(settings.crmSites),
        llm_enabled: settings.llmEnabled, llm_provider: settings.llmProvider, llm_model: settings.llmModel,
        llm_mode: settings.llmMode, llm_temperature: settings.llmTemperature,
        scan_mode: settings.scanMode,
      };
      if (settings.llmApiKey) patch.llm_api_key = settings.llmApiKey;
      await api.updateSettings(patch);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "voice":
        return (
          <section style={card}>
            <div style={hdr}>
              <Mic style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
              <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Voice Recognition</span>
            </div>
            <div style={body}>
              <div>
                <p style={lbl}>Wake Word</p>
                <select style={inp} value={settings.wakeWord}
                  onChange={(e) => settings.update({ wakeWord: e.target.value })}>
                  <option value="alexa">Alexa</option>
                  <option value="hey_jarvis">Hey Jarvis</option>
                  <option value="hey_mycroft">Hey Mycroft</option>
                  <option value="hey_rhasspy">Hey Rhasspy</option>
                </select>
                <p style={sub}>Currently: <span style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>&quot;{settings.wakeWord}&quot;</span></p>
              </div>
              <div>
                <p style={lbl}>STT Provider</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
                  {[
                    { key: "whisper", label: "Whisper", desc: "Private, works offline" },
                    // { key: "gstt", label: "Google STT", desc: "Highly accurate, requires internet" },
                  ].map(({ key, label, desc }) => {
                    const active = settings.sttProvider === key;
                    return (
                      <button key={key} onClick={() => settings.update({ sttProvider: key as "whisper" | "gstt" })}
                        style={{ textAlign: "left", padding: "1.25rem", borderRadius: "0.75rem", cursor: "pointer", transition: "all 0.2s ease", background: active ? "var(--secondary)" : "transparent", border: active ? "2px solid var(--primary)" : "1px solid var(--border)", boxShadow: active ? "0 4px 12px rgba(0,0,0,0.05)" : "none" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                          <span style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</span>
                        </div>
                        <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>{desc}</p>
                        {active && <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--primary)", fontSize: "0.75rem", fontWeight: 600 }}><CheckCircle2 style={{ width: "0.875rem", height: "0.875rem" }} /> Selected</div>}
                      </button>
                    );
                  })}
                </div>
              </div>

              {settings.sttProvider === "whisper" && (
                <div>
                  <p style={lbl}>Whisper Model</p>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {(["tiny", "base", "small", "medium"] as const).map((m) => (
                      <button key={m} onClick={() => settings.update({ whisperModel: m })} style={settings.whisperModel === m ? btnA : btnI}>
                        {m.charAt(0).toUpperCase() + m.slice(1)}
                      </button>
                    ))}
                  </div>
                  <p style={sub}>Tiny = fastest · Medium = highly accurate</p>
                </div>
              )}

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem" }}>
                <div>
                  <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>Noise Cancellation</p>
                  <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>Aggressively filter background noise using VAD</p>
                </div>
                <Toggle checked={settings.sttNoiseCancellation} onChange={() => settings.update({ sttNoiseCancellation: !settings.sttNoiseCancellation })} />
              </div>

              <div>
                <p style={lbl}>Interaction Mode</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  {[
                    { key: "require", label: "Require Wake Word", desc: "Say the wake word for every task" },
                    { key: "continuous", label: "Continuous Listening", desc: "Stay awake for follow-up commands" },
                  ].map(({ key, label, desc }) => {
                    const active = (key === "require" && settings.requireWakeWordAlways) || (key === "continuous" && !settings.requireWakeWordAlways);
                    return (
                      <button key={key} onClick={() => settings.update({ requireWakeWordAlways: key === "require" })}
                        style={{ textAlign: "left", padding: "1.25rem", borderRadius: "0.75rem", cursor: "pointer", transition: "all 0.2s ease", background: active ? "var(--secondary)" : "transparent", border: active ? "2px solid var(--primary)" : "1px solid var(--border)", boxShadow: active ? "0 4px 12px rgba(0,0,0,0.05)" : "none" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                          <span style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</span>
                        </div>
                        <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>{desc}</p>
                        {active && <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--primary)", fontSize: "0.75rem", fontWeight: 600 }}><CheckCircle2 style={{ width: "0.875rem", height: "0.875rem" }} /> Selected</div>}
                      </button>
                    );
                  })}
                </div>
              </div>

              {!settings.requireWakeWordAlways && (
                <div style={{ marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem", border: "1px solid var(--border)" }}>
                  <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "1rem" }}>Active Mode Timeout (Seconds)</p>
                  <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <input
                      type="range"
                      min="10"
                      max="600"
                      step="10"
                      value={settings.activeModeTimeout || 120}
                      onChange={(e) => settings.update({ activeModeTimeout: parseInt(e.target.value) })}
                      style={{ flex: 1, accentColor: "var(--primary)" }}
                    />
                    <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)", minWidth: "3rem", textAlign: "right" }}>
                      {settings.activeModeTimeout || 120}s
                    </span>
                  </div>
                  <p style={sub}>How long the assistant stays awake listening for follow-up commands without the wake word.</p>
                </div>
              )}

              <div style={{ marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem", border: "1px solid var(--border)" }}>
                <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "1rem" }}>Global Keyboard Shortcuts</p>

                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.25rem" }}>Toggle Desktop Overlay</p>
                    <input
                      type="text"
                      value={settings.overlayShortcut}
                      onChange={(e) => settings.update({ overlayShortcut: e.target.value })}
                      placeholder="e.g. Alt+A"
                      style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", fontSize: "0.875rem", outline: "none" }}
                    />
                  </div>

                  <div>
                    <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.25rem" }}>Skip Wake Word (Trigger Listen)</p>
                    <input
                      type="text"
                      value={settings.listenShortcut}
                      onChange={(e) => settings.update({ listenShortcut: e.target.value })}
                      placeholder="e.g. Alt+S"
                      style={{ width: "100%", padding: "0.5rem 0.75rem", borderRadius: "0.5rem", border: "1px solid var(--border)", background: "var(--background)", color: "var(--foreground)", fontSize: "0.875rem", outline: "none" }}
                    />
                  </div>
                </div>
                <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.75rem" }}>Use modifiers like <code>CommandOrControl</code>, <code>Alt</code>, <code>Shift</code>, <code>Super</code> + Letter (e.g. <code>Alt+A</code>). Applies system-wide while ACE is running.</p>
              </div>

              <div style={{ marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem", border: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                  <div>
                    <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>Live STT Tester</p>
                    <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>Speak into your microphone to instantly test transcription speed and accuracy. No commands will be executed.</p>
                  </div>
                  <button onClick={handleToggleSttTest} style={{ flexShrink: 0, padding: "0.5rem 1.25rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", background: sttTestActive ? "rgba(239,68,68,0.1)" : "var(--background)", border: `1px solid ${sttTestActive ? "#ef444430" : "var(--border)"}`, color: sttTestActive ? "#dc2626" : "var(--foreground)", display: "flex", alignItems: "center", gap: "0.5rem", boxShadow: "0 1px 2px rgba(0,0,0,0.05)", transition: "all 0.2s" }}>
                    {sttTestActive ? <Loader2 size={16} className="animate-spin" /> : <Mic size={16} />}
                    {sttTestActive ? "Stop Test" : "Start Test"}
                  </button>
                </div>
                <div style={{ background: "var(--background)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "1rem", minHeight: "6rem", fontSize: "0.875rem", color: sttTestText ? "var(--foreground)" : "var(--muted-foreground)", fontFamily: "var(--font-mono)", display: "flex", flexDirection: "column", alignItems: "flex-start", justifyContent: "flex-start", textAlign: "left" }}>
                  <div style={{ flex: 1, whiteSpace: "pre-wrap" }}>{sttTestText || "Click 'Start Test' and begin speaking..."}</div>
                  {sttTestDuration !== null && sttTestText && (
                    <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "var(--muted-foreground)" }}>
                      Transcription took {sttTestDuration}ms
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        );

      case "tts":
        return (
          <section style={card}>
            <div style={hdr}>
              <Volume2 style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
              <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Text-to-Speech Engine</span>
            </div>
            <div style={body}>
              <div>
                <p style={lbl}>TTS Provider</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  {[
                    { key: "piper", label: "Piper TTS", desc: "Fully offline · Fast" },
                    { key: "gtts", label: "Google TTS", desc: "High quality · Requires internet" },
                  ].map(({ key, label, desc }) => {
                    const active = settings.ttsProvider === key;
                    return (
                      <button key={key} onClick={() => settings.setTtsProvider(key as "piper" | "gtts")}
                        style={{ textAlign: "left", padding: "1.25rem", borderRadius: "0.75rem", cursor: "pointer", transition: "all 0.2s", background: active ? "var(--secondary)" : "transparent", border: active ? "2px solid var(--primary)" : "1px solid var(--border)", boxShadow: active ? "0 4px 12px rgba(0,0,0,0.05)" : "none" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                          <span style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</span>
                        </div>
                        <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>{desc}</p>
                        {active && <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--primary)", fontSize: "0.75rem", fontWeight: 600 }}><CheckCircle2 style={{ width: "0.875rem", height: "0.875rem" }} /> Selected</div>}
                      </button>
                    );
                  })}
                </div>
              </div>

              {settings.ttsProvider === "piper" && (
                <div>
                  <p style={lbl}>Piper Voice</p>
                  <select style={{ ...inp, maxWidth: "24rem" }} value={settings.piperVoice} onChange={(e) => settings.update({ piperVoice: e.target.value })}>
                    <option value="en_US-lessac-medium">Lessac (Female)</option>
                    <option value="en_US-ryan-medium">Ryan (Male)</option>
                    <option value="en_US-hfc_female-medium">HFC Female (Female)</option>
                  </select>
                </div>
              )}

              <div style={{ marginTop: "1.5rem", padding: "1.5rem", background: "var(--secondary)", borderRadius: "0.75rem", border: "1px solid var(--border)" }}>
                <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.25rem" }}>Test Voice Output</p>
                <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginBottom: "1.25rem" }}>Listen to how the assistant will sound</p>

                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <input style={{ ...inp, flex: 1 }} value={testTtsText} onChange={(e) => setTestTtsText(e.target.value)} placeholder="Enter text to synthesize..." />
                  <button onClick={handleTestTts} disabled={testingTts}
                    style={{ padding: "0.5rem 1.5rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", background: "var(--primary)", color: "var(--primary-foreground)", border: "none", display: "flex", alignItems: "center", gap: "0.5rem", opacity: testingTts ? 0.7 : 1 }}>
                    {testingTts ? <Loader2 size={18} className="animate-spin" /> : <Volume2 size={18} />}
                    Play
                  </button>
                </div>
              </div>
            </div>
          </section>
        );

      case "ai":
        return (
          <section style={card}>
            <div style={{ ...hdr, justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <Bot style={{ width: "1.25rem", height: "1.25rem", color: "var(--primary)" }} />
                <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>AI Assistant</span>
              </div>
              <Toggle checked={settings.llmEnabled} onChange={() => settings.update({ llmEnabled: !settings.llmEnabled })} />
            </div>

            {settings.llmEnabled && (() => {
              const getBillingLink = (p: string) => p === "openai" ? "https://platform.openai.com/account/billing" : p === "groq" ? "https://console.groq.com/settings/billing" : p === "claude" ? "https://console.anthropic.com/settings/billing" : p === "gemini" ? "https://aistudio.google.com/app/billing" : p === "deepseek" ? "https://platform.deepseek.com/usage" : null;
              return (
                <div style={body}>
                  {settings.llmSystemError && (
                    <div style={{ padding: "1rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 500, background: "rgba(239,68,68,0.1)", color: "#dc2626", border: "1px solid #ef444430", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span>⚠️ {settings.llmSystemError}</span>
                      <button onClick={() => settings.update({ llmSystemError: null })} style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", fontWeight: 600, padding: "0 0.5rem" }}>×</button>
                    </div>
                  )}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                    <div>
                      <p style={lbl}>Provider</p>
                      <select style={inp} value={settings.llmProvider || ""}
                        onChange={(e) => {
                          const prov = e.target.value;
                          if (!prov) return settings.update({ llmProvider: "", llmModel: "" });
                          const pObj = providers.find(p => p.id === prov);
                          settings.update({ llmProvider: prov, llmModel: pObj?.models[0] || "" });
                        }}>
                        <option value="">None</option>
                        {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                      {settings.llmProvider && getBillingLink(settings.llmProvider) && (
                        <a href={getBillingLink(settings.llmProvider)!} target="_blank" rel="noreferrer" style={{ fontSize: "0.75rem", color: "var(--primary)", marginTop: "0.5rem", display: "inline-block", textDecoration: "underline" }}>Manage Billing & Quota ↗</a>
                      )}
                    </div>
                    <div>
                      <p style={lbl}>Model</p>
                      <select style={inp} value={settings.llmModel || ""} onChange={(e) => settings.update({ llmModel: e.target.value })}>
                        <option value="">None</option>
                        {providers.find(p => p.id === settings.llmProvider)?.models.map(m => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </div>
                  </div>

                  <div>
                    <p style={lbl}>API Key</p>
                    <div style={{ position: "relative" }}>
                      <input type={showApiKey ? "text" : "password"} style={{ ...inp, paddingRight: "3.5rem" }}
                        placeholder="••••••••••••••••••••••••" value={settings.llmApiKey} onChange={(e) => settings.update({ llmApiKey: e.target.value })} />
                      <button onClick={() => setShowApiKey(!showApiKey)}
                        style={{ position: "absolute", right: "1rem", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)" }}>
                        {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                    <p style={sub}>Only required if changing. Saved securely in the database.</p>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                    <div>
                      <p style={lbl}>Processing Mode</p>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button onClick={() => settings.update({ llmMode: "fallback" })} style={settings.llmMode === "fallback" ? btnA : btnI}>Fallback</button>
                        <button onClick={() => settings.update({ llmMode: "always_on" })} style={settings.llmMode === "always_on" ? btnA : btnI}>Always-On</button>
                      </div>
                      <p style={sub}>{settings.llmMode === "fallback" ? "Low Token Usage: Calls AI only if intent matches fail" : "High Token Usage: Routes every command to AI"}</p>
                    </div>
                    <div>
                      <p style={lbl}>Temperature: {settings.llmTemperature}</p>
                      <input type="range" min="0" max="1" step="0.1" value={settings.llmTemperature} onChange={(e) => settings.update({ llmTemperature: parseFloat(e.target.value) })} style={{ width: "100%", marginTop: "0.5rem", accentColor: "var(--primary)" }} />
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.25rem", fontWeight: 500 }}>
                        <span>Precise</span><span>Creative</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                      <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>Test Connection</p>
                      <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>Verify your API key and model</p>
                    </div>
                    <button onClick={handleTestLlm} disabled={testingLlm}
                      style={{ padding: "0.5rem 1.25rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 600, cursor: "pointer", background: "var(--background)", border: "1px solid var(--border)", color: "var(--foreground)", display: "flex", alignItems: "center", gap: "0.5rem", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
                      {testingLlm ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
                      Test API
                    </button>
                  </div>
                  {testResult && (
                    <div style={{ padding: "1rem", borderRadius: "0.5rem", fontSize: "0.875rem", fontWeight: 500, background: testResult.ok ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)", color: testResult.ok ? "#16a34a" : "#dc2626", border: `1px solid ${testResult.ok ? "#22c55e30" : "#ef444430"}` }}>
                      {testResult.msg}
                    </div>
                  )}
                </div>
              );
            })()}
          </section>
        );

      case "browser":
        return (
          <section style={card}>
            <div style={hdr}>
              <Globe style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
              <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Browser Automation</span>
            </div>
            <div style={body}>
              <div>
                <p style={lbl}>Browser Engine</p>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  {(["chromium", "firefox", "webkit"] as const).map((b) => (
                    <button key={b} onClick={() => settings.update({ browserType: b })} style={settings.browserType === b ? btnA : btnI}>
                      {b.charAt(0).toUpperCase() + b.slice(1)}
                    </button>
                  ))}
                </div>
                <p style={sub}>Chromium is highly recommended for stability.</p>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem" }}>
                <div>
                  <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>Browser Animations</p>
                  <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>Show visual feedback (animated cursor, element highlights) during automation</p>
                </div>
                <Toggle checked={settings.browserAnimationsEnabled} onChange={() => settings.update({ browserAnimationsEnabled: !settings.browserAnimationsEnabled })} />
              </div>

              {/* ── Website Shortcuts ── */}
              <div style={{ marginTop: "1rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <div>
                    <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>Website Shortcuts</p>
                    <p style={{ fontSize: "0.8rem", color: "var(--muted-foreground)", marginTop: "0.2rem" }}>Say a keyword to instantly open any website — CRM, dashboards, tools, anything.</p>
                  </div>
                  <button
                    id="add-website-shortcut-btn"
                    onClick={() => settings.update({ crmSites: [...settings.crmSites, { url: "", keywords: "" }] })}
                    style={{ display: "flex", alignItems: "center", gap: "0.375rem", padding: "0.375rem 0.875rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer", background: "var(--primary)", color: "var(--primary-foreground, #fff)", border: "none", flexShrink: 0 }}>
                    + Add Website
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
                  {settings.crmSites.map((site, idx) => (
                    <div key={idx} style={{ background: "var(--secondary)", borderRadius: "0.75rem", padding: "1rem", border: "1px solid var(--border)" }}>
                      {/* Site header */}
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--muted-foreground)" }}>Website {idx + 1}</span>
                        {settings.crmSites.length > 1 && (
                          <button
                            onClick={() => {
                              const updated = settings.crmSites.filter((_, i) => i !== idx);
                              settings.update({ crmSites: updated, crmUrl: updated[0]?.url || "", crmKeywords: updated[0]?.keywords || "" });
                            }}
                            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", fontSize: "1rem", padding: "0 0.25rem", lineHeight: 1 }}
                            title="Remove this website">
                            ✕
                          </button>
                        )}
                      </div>

                      {/* URL row */}
                      <div style={{ marginBottom: "0.625rem" }}>
                        <p style={{ ...lbl, marginBottom: "0.375rem" }}>Website URL</p>
                        <input
                          style={inp}
                          value={site.url}
                          placeholder="https://example.com/"
                          onChange={(e) => {
                            const updated = settings.crmSites.map((s, i) => i === idx ? { ...s, url: e.target.value } : s);
                            settings.update({ crmSites: updated, ...(idx === 0 ? { crmUrl: e.target.value } : {}) });
                          }}
                        />
                      </div>

                      {/* Keywords row */}
                      <div>
                        <p style={{ ...lbl, marginBottom: "0.375rem" }}>Voice Keywords <span style={{ fontWeight: 400, color: "var(--muted-foreground)" }}>(comma separated)</span></p>
                        <input
                          style={inp}
                          value={site.keywords}
                          placeholder="open my dashboard, open analytics"
                          onChange={(e) => {
                            const updated = settings.crmSites.map((s, i) => i === idx ? { ...s, keywords: e.target.value } : s);
                            settings.update({ crmSites: updated, ...(idx === 0 ? { crmKeywords: e.target.value } : {}) });
                          }}
                        />
                        <p style={sub}>Say any of these phrases to instantly open this website.</p>
                      </div>
                    </div>
                  ))}

                  {settings.crmSites.length === 0 && (
                    <p style={{ fontSize: "0.875rem", color: "var(--muted-foreground)", textAlign: "center", padding: "1rem" }}>
                      No websites configured. Click <strong>+ Add Website</strong> to add your first shortcut.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </section>
        );

      case "system":
        return (
          <section style={card}>
            <div style={hdr}>
              <Shield style={{ width: "1.25rem", height: "1.25rem", color: "var(--muted-foreground)" }} />
              <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)" }}>System Preferences</span>
            </div>
            <div style={body}>
              <div>
                <p style={lbl}>Theme</p>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  {(["dark", "light"] as const).map((t) => (
                    <button key={t} onClick={() => settings.update({ theme: t })} style={settings.theme === t ? btnA : btnI}>
                      {t.charAt(0).toUpperCase() + t.slice(1)} Mode
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
                {[
                  { key: "enableDesktopOverlay", label: "Desktop Overlay", desc: "Show floating pill for quick access to Mic and AI" },
                  { key: "startupOnBoot", label: "Start on boot", desc: "Launch ACE automatically when Windows starts" },
                  { key: "minimizeToTray", label: "Minimize to tray", desc: "Keep ACE running in the background when closed" },
                ].map(({ key, label, desc }) => {
                  const val = settings[key as "startupOnBoot" | "minimizeToTray" | "enableDesktopOverlay"];
                  return (
                    <div key={key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem" }}>
                      <div>
                        <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</p>
                        <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>{desc}</p>
                      </div>
                      <Toggle checked={val} onChange={() => settings.update({ [key]: !val })} />
                    </div>
                  );
                })}
              </div>

              {/* ── App & File Scanning ── */}
              <div style={{ marginTop: "1.5rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "1rem" }}>
                  <HardDrive style={{ width: "1.125rem", height: "1.125rem", color: "var(--primary)" }} />
                  <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>App &amp; File Scanning</p>
                </div>

                {/* Mode selector */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
                  {([
                    { key: "auto", label: "Auto", desc: "Scan on startup and refresh automatically", icon: "🔄" },
                    { key: "manual", label: "Manual", desc: "Only scan when you click the button below", icon: "🖐" },
                  ] as const).map(({ key, label, desc, icon }) => {
                    const active = settings.scanMode === key;
                    return (
                      <button key={key} onClick={() => settings.update({ scanMode: key })}
                        style={{
                          textAlign: "left", padding: "1.125rem", borderRadius: "0.75rem",
                          cursor: "pointer", transition: "all 0.2s ease",
                          background: active ? "var(--secondary)" : "transparent",
                          border: active ? "2px solid var(--primary)" : "1px solid var(--border)",
                          boxShadow: active ? "0 4px 12px rgba(0,0,0,0.05)" : "none",
                        }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.375rem" }}>
                          <span style={{ fontSize: "1.1rem" }}>{icon}</span>
                          <span style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</span>
                        </div>
                        <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>{desc}</p>
                        {active && (
                          <div style={{ marginTop: "0.625rem", display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--primary)", fontSize: "0.75rem", fontWeight: 600 }}>
                            <CheckCircle2 style={{ width: "0.875rem", height: "0.875rem" }} /> Selected
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Scan Now row */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1rem 1.25rem", background: "var(--secondary)", borderRadius: "0.75rem", border: "1px solid var(--border)" }}>
                  <div>
                    <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>Scan Now</p>
                    <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>
                      {scanLastAt
                        ? `Last scanned: ${new Date(scanLastAt).toLocaleTimeString()} · ${scanAppCount ?? "?"} apps found`
                        : "Not scanned yet this session"}
                    </p>
                  </div>
                  <button
                    id="scan-now-btn"
                    onClick={async () => {
                      if (scanning) return;
                      setScanning(true);
                      try { await api.triggerScan(); } catch (e) { console.error(e); setScanning(false); }
                    }}
                    disabled={scanning}
                    style={{
                      display: "flex", alignItems: "center", gap: "0.5rem",
                      padding: "0.5rem 1.25rem", borderRadius: "0.5rem",
                      fontSize: "0.875rem", fontWeight: 600, cursor: scanning ? "not-allowed" : "pointer",
                      background: "var(--background)", border: "1px solid var(--border)",
                      color: "var(--foreground)", opacity: scanning ? 0.7 : 1,
                      boxShadow: "0 1px 2px rgba(0,0,0,0.05)", transition: "all 0.2s",
                    }}>
                    {scanning
                      ? <><Loader2 size={15} className="animate-spin" /> Scanning...</>
                      : <><RefreshCw size={15} /> Scan Now</>}
                  </button>
                </div>
              </div>
            </div>
          </section>
        );
      default: return null;
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "2.5rem" }}>

          <div style={{ width: "100%", display: "flex", gap: "4rem", position: "relative" }}>

            {/* Left Navigation Sidebar */}
            <nav style={{ width: "240px", flexShrink: 0, position: "sticky", top: 0, display: "flex", flexDirection: "column", gap: "0.375rem" }}>
              <div style={{ marginBottom: "2rem" }}>
                <h1 style={{ fontSize: "1.75rem", fontWeight: 600, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
                  <Settings style={{ width: "1.75rem", height: "1.75rem", color: "var(--primary)" }} /> Settings
                </h1>
              </div>

              {TABS.map((tab) => {
                const isActive = activeTab === tab.id;
                const Icon = tab.icon;
                return (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                    style={{
                      display: "flex", alignItems: "center", gap: "0.875rem",
                      width: "100%", padding: "0.875rem 1rem", borderRadius: "0.5rem",
                      border: "none", background: isActive ? "var(--secondary)" : "transparent",
                      color: isActive ? "var(--foreground)" : "var(--muted-foreground)",
                      fontWeight: isActive ? 600 : 500, fontSize: "0.9375rem",
                      cursor: "pointer", transition: "all 0.2s ease", textAlign: "left",
                    }}>
                    <Icon size={18} style={{ color: isActive ? "var(--primary)" : "inherit" }} />
                    {tab.label}
                  </button>
                );
              })}

              <div style={{ marginTop: "2rem", paddingTop: "2rem", borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "var(--muted-foreground)", fontSize: "0.875rem" }}>
                  <div style={{ width: "0.5rem", height: "0.5rem", borderRadius: "50%", background: saved ? "var(--primary)" : "var(--muted-foreground)", opacity: saving ? 0.5 : 1, transition: "background 0.3s" }} />
                  {saving ? "Saving changes..." : saved ? "All changes saved" : "Auto-saving is active"}
                </div>
              </div>
            </nav>

            {/* Main Content Area */}
            <div style={{ flex: 1, minWidth: 0, paddingBottom: "4rem" }}>
              {!connected && (
                <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", padding: "1rem", borderRadius: "0.75rem", marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.75rem", fontWeight: 500, fontSize: "0.875rem" }}>
                  Server is currently offline. Settings cannot be modified.
                </div>
              )}
              <div style={{ opacity: !connected ? 0.5 : 1, pointerEvents: !connected ? "none" : "auto", transition: "all 0.2s" }}>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -15 }}
                    transition={{ duration: 0.2, ease: "easeOut" }}
                  >
                    {renderTabContent()}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>

          </div>
        </main>
      </div>
    </div>
  );
}