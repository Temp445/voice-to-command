"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, Mic, Volume2, Globe, Shield, CheckCircle2, Eye, EyeOff, Bot, Loader2, Link2, RefreshCw, HardDrive, Lock } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useSettingsStore } from "@/store/settingsStore";
import { useWSStore } from "@/hooks/useWebSocket";
import { api, getResolvedBaseUrl, resolvedBackendPort, isTauri } from "@/lib/api";
import { invoke } from "@tauri-apps/api/core";

// Tailwind Class mappings for reuse in the switches
const cardClass = "bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-md";
const hdrClass = "px-6 py-5 border-b border-[var(--border)] flex items-center gap-3 bg-white/[0.02]";
const bodyClass = "p-6 flex flex-col gap-6";
const lblClass = "text-[13px] font-semibold text-[var(--foreground)] mb-1.5";
const subClass = "text-xs text-zinc-500 mt-1";
const inpClass = "w-full bg-[var(--input)] border border-[var(--border)] rounded-lg px-3.5 py-2.5 text-sm text-[var(--foreground)] font-mono outline-none transition-colors duration-200 focus:border-[var(--ring)]";
const btnAClass = "px-4 py-2 rounded-lg text-[13px] font-semibold cursor-pointer border border-[var(--ring)] bg-[var(--primary)] text-[var(--primary-foreground)] transition-all duration-150 shadow-sm flex items-center justify-center gap-2 hover:opacity-90 active:scale-95";
const btnIClass = "px-4 py-2 rounded-lg text-[13px] font-medium cursor-pointer border border-[var(--border)] bg-[var(--secondary)] text-zinc-500 transition-all duration-150 flex items-center justify-center gap-2 hover:bg-[var(--secondary)]/80 active:scale-95";

const Toggle = ({ checked, onChange, disabled }: { checked: boolean, onChange: () => void, disabled?: boolean }) => (
  <button 
    onClick={disabled ? undefined : onChange}
    className={`w-11 h-6 rounded-full relative shrink-0 transition-colors duration-300 border-none ${checked ? "bg-[var(--primary)]" : "bg-[var(--border)]"} ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer opacity-100"}`}
  >
    <span 
      className={`absolute top-[2.4px] left-[2.4px] w-[19.2px] h-[19.2px] bg-[var(--background)] rounded-full transition-transform duration-300 shadow-sm ${checked ? "translate-x-5" : "translate-x-0"}`} 
    />
  </button>
);

const TABS = [
  { id: "voice", label: "Voice Recognition", icon: Mic },
  { id: "tts", label: "Text-to-Speech", icon: Volume2 },
  { id: "ai", label: "AI Assistant", icon: Bot },
  { id: "browser", label: "Browser Automation", icon: Globe },
  { id: "system", label: "System Preferences", icon: Shield }
];

const PERMISSION_FIELDS = [
  {
    category: "Page Tabs (Visibility only)",
    items: [
      { key: "tab_voice", label: "Voice Recognition Tab", hideMutable: true },
      { key: "tab_tts", label: "Text-to-Speech Tab", hideMutable: true },
      { key: "tab_ai", label: "AI Assistant Tab", hideMutable: true },
      { key: "tab_browser", label: "Browser Automation Tab", hideMutable: true },
      { key: "tab_system", label: "System Preferences Tab", hideMutable: true },
    ]
  },
  {
    category: "Voice Recognition Settings",
    items: [
      { key: "wake_word", label: "Wake Word Selection" },
      { key: "stt_provider", label: "STT Provider Selection" },
      { key: "elevenlabs_api_key", label: "ElevenLabs API Key" },
      { key: "deepgram_api_key", label: "Deepgram API Key" },
      { key: "whisper_model", label: "Whisper Model Selection" },
      { key: "stt_noise_cancellation", label: "STT Noise Cancellation Toggle" },
      { key: "require_wake_word_always", label: "Interaction Mode (Always Wake Word)" },
      { key: "active_mode_timeout", label: "Active Mode Timeout Slider" },
      { key: "overlay_shortcut", label: "Overlay Shortcut Key Input" },
      { key: "listen_shortcut", label: "Listen Shortcut Key Input" },
    ]
  },
  {
    category: "Text-to-Speech Settings",
    items: [
      { key: "tts_provider", label: "TTS Provider Selection" },
      { key: "piper_voice", label: "Piper Voice Model Selection" },
      { key: "reply_sound", label: "Reply Sound Toggle" },
      { key: "speech_rate", label: "Speech Speed Select" },
    ]
  },
  {
    category: "AI Assistant Settings",
    items: [
      { key: "llm_enabled", label: "AI Assistant Enabled Toggle" },
      { key: "llm_provider", label: "LLM Provider Selection" },
      { key: "llm_model", label: "LLM Model Selection" },
      { key: "llm_api_key_encrypted", label: "LLM API Key Input" },
      { key: "llm_mode", label: "Processing Mode Selection" },
      { key: "llm_temperature", label: "Temperature Slider" },
    ]
  },
  {
    category: "Browser Automation Settings",
    items: [
      { key: "browser_type", label: "Browser Engine Selection" },
      { key: "browser_animations_enabled", label: "Browser Animations Toggle" },
      { key: "restrict_browser_automation", label: "Restrict Website Automation Toggle" },
      { key: "crm_sites", label: "Website Shortcuts List" },
      { key: "global_website_shortcuts", label: "Global Website Shortcuts" },
    ]
  },
  {
    category: "System Preferences Settings",
    items: [
      { key: "theme", label: "Theme Mode Selection" },
      { key: "enable_desktop_overlay", label: "Desktop Overlay Toggle" },
      { key: "startup_on_boot", label: "Start on Boot Toggle" },
      { key: "minimize_to_tray", label: "Minimize to Tray Toggle" },
      { key: "scan_mode", label: "App & File Scan Mode Selector" },
    ]
  }
];

export default function SettingsPage() {
  const settings = useSettingsStore();

  const isVisible = (key: string) => {
    if (settings.role === "admin") return true;
    return settings.permissions[key]?.visible !== false;
  };

  const isMutable = (key: string) => {
    if (settings.role === "admin") return true;
    return settings.permissions[key]?.mutable !== false;
  };

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

  // Admin Panel State
  const [usersPolicies, setUsersPolicies] = useState<any[]>([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);
  const [adminSavingUser, setAdminSavingUser] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminSuccess, setAdminSuccess] = useState<string | null>(null);

  // Global Website Shortcuts State
  const [globalShortcuts, setGlobalShortcuts] = useState<any[]>([]);
  const [loadingGlobalShortcuts, setLoadingGlobalShortcuts] = useState(false);
  const [globalShortcutsError, setGlobalShortcutsError] = useState<string | null>(null);
  const [globalShortcutsSuccess, setGlobalShortcutsSuccess] = useState<string | null>(null);

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
      const role = data.role || "user";
      const permissions = data.permissions || {};
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
        restrictBrowserAutomation: data.restrict_browser_automation || false,
        llmEnabled: data.llm_enabled, llmProvider: data.llm_provider, llmModel: data.llm_model,
        llmMode: data.llm_mode, llmTemperature: data.llm_temperature,
        scanMode: (data.scan_mode as "auto" | "manual") || "manual",
        elevenlabsConfigured: data.elevenlabs_configured || false,
        deepgramConfigured: data.deepgram_configured || false,
        replySound: data.reply_sound !== undefined ? data.reply_sound : true,
        speechRate: data.speech_rate !== undefined ? data.speech_rate : 1.0,
        screenSettingsVisibleToUsers: data.screen_settings_visible_to_users !== undefined ? data.screen_settings_visible_to_users : true,
        role: role,
        permissions: permissions,
      });
      setInitialLoaded(true);

      if (role !== "admin") {
        const currentTabVisible = permissions[`tab_voice`]?.visible !== false;
        if (!currentTabVisible) {
          const firstVisible = TABS.find(tab => permissions[`tab_${tab.id}`]?.visible !== false);
          if (firstVisible) {
            setActiveTab(firstVisible.id);
          }
        }
      }
    }).catch(err => console.error(err));
  }, []);

  // Fetch Global Website Shortcuts
  useEffect(() => {
    setLoadingGlobalShortcuts(true);
    api.listGlobalShortcuts()
      .then((data: any[]) => setGlobalShortcuts(data || []))
      .catch(err => console.error("Failed to load global shortcuts:", err))
      .finally(() => setLoadingGlobalShortcuts(false));
  }, []);

  const handleAddGlobalShortcut = async (url: string, keywords: string) => {
    setGlobalShortcutsError(null);
    setGlobalShortcutsSuccess(null);
    try {
      const newShortcut = await api.createGlobalShortcut(url, keywords);
      setGlobalShortcuts(prev => [...prev, newShortcut]);
      setGlobalShortcutsSuccess("Global website shortcut added successfully!");
      setTimeout(() => setGlobalShortcutsSuccess(null), 3000);
    } catch (err: any) {
      setGlobalShortcutsError(err.message || "Failed to add global shortcut. Check permissions.");
      setTimeout(() => setGlobalShortcutsError(null), 3000);
    }
  };

  const handleDeleteGlobalShortcut = async (id: string) => {
    setGlobalShortcutsError(null);
    setGlobalShortcutsSuccess(null);
    try {
      await api.deleteGlobalShortcut(id);
      setGlobalShortcuts(prev => prev.filter(item => item.id !== id));
      setGlobalShortcutsSuccess("Global website shortcut deleted successfully!");
      setTimeout(() => setGlobalShortcutsSuccess(null), 3000);
    } catch (err: any) {
      setGlobalShortcutsError(err.message || "Failed to delete global shortcut. Check permissions.");
      setTimeout(() => setGlobalShortcutsError(null), 3000);
    }
  };

  useEffect(() => {
    if (!initialLoaded) return;
    if (settings.role !== "admin") {
      const currentTabVisible = settings.permissions[`tab_${activeTab}`]?.visible !== false;
      if (!currentTabVisible) {
        const firstVisible = TABS.find(tab => settings.permissions[`tab_${tab.id}`]?.visible !== false);
        if (firstVisible) {
          setActiveTab(firstVisible.id);
        }
      }
    }
  }, [settings.permissions, settings.role, activeTab, initialLoaded]);

  useEffect(() => {
    if (!initialLoaded) return;
    if (settings.role !== "admin") {
      if (settings.sttProvider === "elevenlabs" && !isVisible("elevenlabs_api_key")) {
        settings.update({ sttProvider: "whisper" });
      }
      if (settings.sttProvider === "deepgram" && !isVisible("deepgram_api_key")) {
        settings.update({ sttProvider: "whisper" });
      }
    }
  }, [settings.permissions, settings.role, settings.sttProvider, initialLoaded]);

  useEffect(() => {
    if (!initialLoaded) return;

    // Sync the Start on Boot setting with the OS registry
    if (isTauri) {
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
    settings.crmUrl, settings.crmKeywords, JSON.stringify(settings.crmSites), settings.restrictBrowserAutomation,
    settings.llmEnabled, settings.llmProvider, settings.llmModel, settings.llmMode,
    settings.llmTemperature, settings.llmApiKey, settings.scanMode, settings.elevenlabsApiKey, settings.deepgramApiKey,
    settings.replySound, settings.speechRate, settings.screenSettingsVisibleToUsers
  ]);

  useEffect(() => {
    if (activeTab === "admin" && settings.role === "admin") {
      setLoadingPolicies(true);
      api.listPolicies()
        .then((data: any[]) => {
          const allKeys = PERMISSION_FIELDS.flatMap(group => group.items.map(item => item.key));
          const normalized = data.map((u) => {
            const perms = { ...u.permissions };
            allKeys.forEach((k) => {
              if (!perms[k]) {
                perms[k] = k === "global_website_shortcuts" ? { visible: true, mutable: false } : { visible: true, mutable: true };
              }
            });
            return { ...u, permissions: perms };
          });
          setUsersPolicies(normalized);
        })
        .catch(err => {
          console.error(err);
          setAdminError("Failed to load user policies.");
        })
        .finally(() => setLoadingPolicies(false));
    }
  }, [activeTab, settings.role]);

  const handleUpdatePolicy = async (userId: string, permissions: any, screenVisible: boolean) => {
    setAdminSavingUser(userId);
    setAdminError(null);
    setAdminSuccess(null);
    try {
      await api.updateUserPolicy(userId, permissions, screenVisible);
      setAdminSuccess("User policy updated successfully!");
      setUsersPolicies(prev => prev.map(u => u.user_id === userId ? { ...u, permissions, screen_settings_visible_to_users: screenVisible } : u));
      setTimeout(() => setAdminSuccess(null), 3000);
    } catch (err: any) {
      setAdminError(err.message || "Failed to update user policy.");
    } finally {
      setAdminSavingUser(null);
    }
  };

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

      const baseUrl = await getResolvedBaseUrl();
      const wsUrl = (baseUrl + "/voice/ws-test-stt").replace(/^http/, "ws");
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
        restrict_browser_automation: settings.restrictBrowserAutomation,
        llm_enabled: settings.llmEnabled, llm_provider: settings.llmProvider, llm_model: settings.llmModel,
        llm_mode: settings.llmMode, llm_temperature: settings.llmTemperature,
        scan_mode: settings.scanMode,
        reply_sound: settings.replySound,
        speech_rate: settings.speechRate,
        screen_settings_visible_to_users: settings.screenSettingsVisibleToUsers,
      };
      if (settings.llmApiKey) patch.llm_api_key = settings.llmApiKey;
      if (settings.elevenlabsApiKey) patch.elevenlabs_api_key = settings.elevenlabsApiKey;
      if (settings.deepgramApiKey) patch.deepgram_api_key = settings.deepgramApiKey;
      await api.updateSettings(patch);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  };

  const renderTabContent = () => {
    if (settings.role !== "admin" && settings.permissions[`tab_${activeTab}`]?.visible === false) {
      return (
        <section className={cardClass}>
          <div className={bodyClass}>
            <p className="text-zinc-500 text-center p-8 text-[15px] font-medium">
              <span className="flex items-center justify-center gap-2"><Lock className="w-4 h-4 text-zinc-500" /> This tab has been disabled by your administrator.</span>
            </p>
          </div>
        </section>
      );
    }

    switch (activeTab) {
      case "voice":
        return (
          <section className={cardClass}>
            <div className={hdrClass}>
              <Mic className="w-5 h-5 text-zinc-500" />
              <span className="text-base font-semibold text-[var(--foreground)]">Voice Recognition</span>
            </div>
            <div className={bodyClass}>
              {isVisible("wake_word") && (
                <div className={isMutable("wake_word") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Wake Word
                    {!isMutable("wake_word") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <select 
                    className={inpClass} 
                    value={settings.wakeWord} 
                    disabled={!isMutable("wake_word")}
                    onChange={(e) => settings.update({ wakeWord: e.target.value })}
                  >
                    <option value="alexa">Alexa</option>
                    <option value="hey_jarvis">Hey Jarvis</option>
                    <option value="hey_mycroft">Hey Mycroft</option>
                    <option value="hey_rhasspy">Hey Rhasspy</option>
                  </select>
                  <p className={subClass}>Currently: <span className="text-[var(--foreground)] font-mono">&quot;{settings.wakeWord}&quot;</span></p>
                </div>
              )}

              {isVisible("stt_provider") && (
                <div className={isMutable("stt_provider") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    STT Provider
                    {!isMutable("stt_provider") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 mb-6">
                    {[
                      { key: "whisper", label: "Whisper", desc: "Private, works offline" },
                      { key: "elevenlabs", label: "ElevenLabs STT", desc: "Scribe v2 cloud, highly accurate" },
                      { key: "deepgram", label: "Deepgram STT", desc: "Nova-3 cloud, blazing fast" },
                    ].filter(({ key }) => {
                      if (key === "elevenlabs") return isVisible("elevenlabs_api_key");
                      if (key === "deepgram") return isVisible("deepgram_api_key");
                      return true;
                    }).map(({ key, label, desc }) => {
                      const active = settings.sttProvider === key;
                      return (
                        <button 
                          key={key}
                          disabled={!isMutable("stt_provider")}
                          onClick={() => settings.update({ sttProvider: key as "whisper" | "elevenlabs" | "deepgram" })}
                          className={`text-left p-5 rounded-xl transition-all duration-200 ${!isMutable("stt_provider") ? "cursor-not-allowed" : "cursor-pointer"} ${active ? "bg-[var(--secondary)] border-2 border-[var(--primary)] shadow-md" : "bg-transparent border border-[var(--border)] shadow-none"}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[15px] font-semibold text-[var(--foreground)]">{label}</span>
                          </div>
                          <p className="text-[13px] text-zinc-500">{desc}</p>
                          {active && (
                            <div className="mt-3 flex items-center gap-1 text-[var(--primary)] text-xs font-semibold">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Selected
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {settings.sttProvider === "elevenlabs" && isVisible("elevenlabs_api_key") && (
                <div className={`mb-6 ${isMutable("elevenlabs_api_key") ? "opacity-100" : "opacity-60"}`}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    ElevenLabs API Key
                    {!isMutable("elevenlabs_api_key") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="relative max-w-96">
                    <input
                      type={showApiKey ? "text" : "password"}
                      disabled={!isMutable("elevenlabs_api_key")}
                      className={`${inpClass} pr-14`}
                      placeholder={settings.elevenlabsConfigured ? "••••••••••••••••••••••••" : "Enter ElevenLabs API Key"}
                      value={settings.elevenlabsApiKey}
                      onChange={(e) => settings.update({ elevenlabsApiKey: e.target.value })}
                    />
                    <button
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-zinc-500"
                    >
                      {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <p className={subClass}>API key is required to use ElevenLabs STT. Saved securely in the database.</p>
                </div>
              )}

              {settings.sttProvider === "deepgram" && isVisible("deepgram_api_key") && (
                <div className={`mb-6 ${isMutable("deepgram_api_key") ? "opacity-100" : "opacity-60"}`}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Deepgram API Key
                    {!isMutable("deepgram_api_key") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="relative max-w-96">
                    <input
                      type={showApiKey ? "text" : "password"}
                      disabled={!isMutable("deepgram_api_key")}
                      className={`${inpClass} pr-14`}
                      placeholder={settings.deepgramConfigured ? "••••••••••••••••••••••••" : "Enter Deepgram API Key"}
                      value={settings.deepgramApiKey}
                      onChange={(e) => settings.update({ deepgramApiKey: e.target.value })}
                    />
                    <button
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-zinc-500"
                    >
                      {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <p className={subClass}>API key is required to use Deepgram STT. Saved securely in the database.</p>
                </div>
              )}

              {settings.sttProvider === "whisper" && isVisible("whisper_model") && (
                <div className={isMutable("whisper_model") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Whisper Model
                    {!isMutable("whisper_model") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="flex gap-2 flex-wrap">
                    {(["tiny", "base", "small", "medium"] as const).map((m) => (
                      <button 
                        key={m}
                        disabled={!isMutable("whisper_model")}
                        onClick={() => settings.update({ whisperModel: m })}
                        className={settings.whisperModel === m ? btnAClass : btnIClass}
                      >
                        {m.charAt(0).toUpperCase() + m.slice(1)}
                      </button>
                    ))}
                  </div>
                  <p className={subClass}>Tiny = fastest · Medium = highly accurate</p>
                </div>
              )}

              {isVisible("stt_noise_cancellation") && (
                <div className={`flex items-center justify-between mt-4 p-5 bg-[var(--secondary)] rounded-xl ${isMutable("stt_noise_cancellation") ? "opacity-100" : "opacity-60"}`}>
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                      Noise Cancellation
                      {!isMutable("stt_noise_cancellation") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                    </p>
                    <p className="text-[13px] text-zinc-500 mt-1">Aggressively filter background noise using VAD</p>
                  </div>
                  <Toggle checked={settings.sttNoiseCancellation} disabled={!isMutable("stt_noise_cancellation")} onChange={() => settings.update({ sttNoiseCancellation: !settings.sttNoiseCancellation })} />
                </div>
              )}

              {isVisible("require_wake_word_always") && (
                <div className={isMutable("require_wake_word_always") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Interaction Mode
                    {!isMutable("require_wake_word_always") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { key: "require", label: "Require Wake Word", desc: "Say the wake word for every task" },
                      { key: "continuous", label: "Continuous Listening", desc: "Stay awake for follow-up commands" },
                    ].map(({ key, label, desc }) => {
                      const active = (key === "require" && settings.requireWakeWordAlways) || (key === "continuous" && !settings.requireWakeWordAlways);
                      return (
                        <button 
                          key={key}
                          disabled={!isMutable("require_wake_word_always")}
                          onClick={() => settings.update({ requireWakeWordAlways: key === "require" })}
                          className={`text-left p-5 rounded-xl transition-all duration-200 ${!isMutable("require_wake_word_always") ? "cursor-not-allowed" : "cursor-pointer"} ${active ? "bg-[var(--secondary)] border-2 border-[var(--primary)] shadow-md" : "bg-transparent border border-[var(--border)] shadow-none"}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[15px] font-semibold text-[var(--foreground)]">{label}</span>
                          </div>
                          <p className="text-[13px] text-zinc-500">{desc}</p>
                          {active && (
                            <div className="mt-3 flex items-center gap-1 text-[var(--primary)] text-xs font-semibold">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Selected
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {!settings.requireWakeWordAlways && isVisible("active_mode_timeout") && (
                <div className={`mt-4 p-5 bg-[var(--secondary)] rounded-xl border border-[var(--border)] ${isMutable("active_mode_timeout") ? "opacity-100" : "opacity-60"}`}>
                  <p className="text-[15px] font-semibold text-[var(--foreground)] mb-4 flex items-center gap-1.5">
                    Active Mode Timeout (Seconds)
                    {!isMutable("active_mode_timeout") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="10"
                      max="600"
                      step="10"
                      disabled={!isMutable("active_mode_timeout")}
                      value={settings.activeModeTimeout || 120}
                      onChange={(e) => settings.update({ activeModeTimeout: parseInt(e.target.value) })}
                      className="flex-1 accent-[var(--primary)]"
                    />
                    <span className="text-sm font-semibold text-[var(--foreground)] min-w-12 text-right">
                      {settings.activeModeTimeout || 120}s
                    </span>
                  </div>
                  <p className={subClass}>How long the assistant stays awake listening for follow-up commands without the wake word.</p>
                </div>
              )}

              {(isVisible("overlay_shortcut") || isVisible("listen_shortcut")) && (
                <div className="mt-4 p-5 bg-[var(--secondary)] rounded-xl border border-[var(--border)]">
                  <p className="text-[15px] font-semibold text-[var(--foreground)] mb-4">Global Keyboard Shortcuts</p>

                  <div className="flex flex-col gap-4">
                    {isVisible("overlay_shortcut") && (
                      <div>
                        <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1 flex items-center gap-1.5">
                          Toggle Desktop Overlay
                          {!isMutable("overlay_shortcut") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <input
                          type="text"
                          disabled={!isMutable("overlay_shortcut")}
                          value={settings.overlayShortcut}
                          onChange={(e) => settings.update({ overlayShortcut: e.target.value })}
                          placeholder="e.g. Alt+A"
                          className={`w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm outline-none ${isMutable("overlay_shortcut") ? "opacity-100" : "opacity-60"}`}
                        />
                      </div>
                    )}

                    {isVisible("listen_shortcut") && (
                      <div>
                        <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1 flex items-center gap-1.5">
                          Skip Wake Word (Trigger Listen)
                          {!isMutable("listen_shortcut") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <input
                          type="text"
                          disabled={!isMutable("listen_shortcut")}
                          value={settings.listenShortcut}
                          onChange={(e) => settings.update({ listenShortcut: e.target.value })}
                          placeholder="e.g. Alt+S"
                          className={`w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm outline-none ${isMutable("listen_shortcut") ? "opacity-100" : "opacity-60"}`}
                        />
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-zinc-500 mt-3">Use modifiers like <code>CommandOrControl</code>, <code>Alt</code>, <code>Shift</code>, <code>Super</code> + Letter (e.g. <code>Alt+A</code>). Applies system-wide while ACE is running.</p>
                </div>
              )}

              <div className="mt-4 p-5 bg-[var(--secondary)] rounded-xl border border-[var(--border)]">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--foreground)]">Live STT Tester</p>
                    <p className="text-[13px] text-zinc-500">Speak into your microphone to instantly test transcription speed and accuracy. No commands will be executed.</p>
                  </div>
                  <button 
                    onClick={handleToggleSttTest} 
                    className={`shrink-0 px-5 py-2 rounded-lg text-sm font-semibold cursor-pointer flex items-center gap-2 shadow-sm transition-all duration-200 border ${sttTestActive ? "bg-red-500/10 border-red-500/20 text-red-500" : "bg-[var(--background)] border-[var(--border)] text-[var(--foreground)]"}`}
                  >
                    {sttTestActive ? <Loader2 size={16} className="animate-spin" /> : <Mic size={16} />}
                    {sttTestActive ? "Stop Test" : "Start Test"}
                  </button>
                </div>
                <div className={`bg-[var(--background)] border border-[var(--border)] rounded-lg p-4 min-h-24 text-sm font-mono flex flex-col items-start justify-start text-left ${sttTestText ? "text-[var(--foreground)]" : "text-zinc-500"}`}>
                  <div className="flex-1 whitespace-pre-wrap">{sttTestText || "Click 'Start Test' and begin speaking..."}</div>
                  {sttTestDuration !== null && sttTestText && (
                    <div className="mt-2 text-xs text-zinc-500">
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
          <section className={cardClass}>
            <div className={hdrClass}>
              <Volume2 className="w-5 h-5 text-zinc-500" />
              <span className="text-base font-semibold text-[var(--foreground)]">Text-to-Speech Engine</span>
            </div>
            <div className={bodyClass}>
              {isVisible("tts_provider") && (
                <div className={isMutable("tts_provider") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    TTS Provider
                    {!isMutable("tts_provider") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { key: "piper", label: "Piper TTS", desc: "Fully offline · Fast" },
                      { key: "gtts", label: "Google TTS", desc: "High quality · Requires internet" },
                    ].map(({ key, label, desc }) => {
                      const active = settings.ttsProvider === key;
                      return (
                        <button 
                          key={key}
                          disabled={!isMutable("tts_provider")}
                          onClick={() => settings.setTtsProvider(key as "piper" | "gtts")}
                          className={`text-left p-5 rounded-xl transition-all duration-200 ${!isMutable("tts_provider") ? "cursor-not-allowed" : "cursor-pointer"} ${active ? "bg-[var(--secondary)] border-2 border-[var(--primary)] shadow-md" : "bg-transparent border border-[var(--border)] shadow-none"}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[15px] font-semibold text-[var(--foreground)]">{label}</span>
                          </div>
                          <p className="text-[13px] text-zinc-500">{desc}</p>
                          {active && (
                            <div className="mt-3 flex items-center gap-1 text-[var(--primary)] text-xs font-semibold">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Selected
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {settings.ttsProvider === "piper" && isVisible("piper_voice") && (
                <div className={isMutable("piper_voice") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Piper Voice
                    {!isMutable("piper_voice") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <select 
                    className={`${inpClass} max-w-96`}
                    value={settings.piperVoice} 
                    disabled={!isMutable("piper_voice")}
                    onChange={(e) => settings.update({ piperVoice: e.target.value })}
                  >
                    <option value="en_US-lessac-medium">Lessac (Female)</option>
                    <option value="en_US-ryan-medium">Ryan (Male)</option>
                    <option value="en_US-hfc_female-medium">HFC Female (Female)</option>
                  </select>
                </div>
              )}

              {isVisible("reply_sound") && (
                <div className={`flex items-center justify-between mt-6 p-5 bg-[var(--secondary)] rounded-xl ${isMutable("reply_sound") ? "opacity-100" : "opacity-60"}`}>
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                      Reply Sound
                      {!isMutable("reply_sound") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                    </p>
                    <p className="text-[13px] text-zinc-500 mt-1">Play audio response voice when executing commands</p>
                  </div>
                  <Toggle checked={settings.replySound} disabled={!isMutable("reply_sound")} onChange={() => settings.update({ replySound: !settings.replySound })} />
                </div>
              )}

              {isVisible("speech_rate") && (
                <div className={`mt-6 ${isMutable("speech_rate") ? "opacity-100" : "opacity-60"}`}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Speech Speed
                    {!isMutable("speech_rate") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <select 
                    className={`${inpClass} max-w-96`}
                    value={settings.speechRate} 
                    disabled={!isMutable("speech_rate")}
                    onChange={(e) => settings.update({ speechRate: parseFloat(e.target.value) })}
                  >
                    <option value={0.5}>0.5x (Slow)</option>
                    <option value={1.0}>1x (Normal)</option>
                    <option value={1.5}>1.5x (Fast)</option>
                    <option value={2.0}>2x (Double)</option>
                  </select>
                  <p className={subClass}>Adjust the speed rate of voice speech responses.</p>
                </div>
              )}

              <div className="mt-6 p-6 bg-[var(--secondary)] rounded-xl border border-[var(--border)]">
                <p className="text-[15px] font-semibold text-[var(--foreground)] mb-1">Test Voice Output</p>
                <p className="text-[13px] text-zinc-500 mb-5">Listen to how the assistant will sound</p>

                <div className="flex gap-3">
                  <input 
                    className={`${inpClass} flex-1`}
                    value={testTtsText} 
                    onChange={(e) => setTestTtsText(e.target.value)} 
                    placeholder="Enter text to synthesize..." 
                  />
                  <button 
                    onClick={handleTestTts} 
                    disabled={testingTts}
                    className={`px-6 py-2 rounded-lg text-sm font-semibold cursor-pointer border-none flex items-center gap-2 bg-[var(--primary)] text-[var(--primary-foreground)] ${testingTts ? "opacity-70 cursor-not-allowed" : "opacity-100 hover:opacity-90 active:scale-95"}`}
                  >
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
          <section className={cardClass}>
            {isVisible("llm_enabled") && (
              <div className={`px-6 py-5 border-b border-[var(--border)] flex items-center justify-between bg-white/[0.02] ${isMutable("llm_enabled") ? "opacity-100" : "opacity-60"}`}>
                <div className="flex items-center gap-3">
                  <Bot className="w-5 h-5 text-zinc-500" />
                  <span className="text-base font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                    AI Assistant
                    {!isMutable("llm_enabled") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </span>
                </div>
                <Toggle checked={settings.llmEnabled} disabled={!isMutable("llm_enabled")} onChange={() => settings.update({ llmEnabled: !settings.llmEnabled })} />
              </div>
            )}

            {settings.llmEnabled && (() => {
              const getBillingLink = (p: string) => p === "openai" ? "https://platform.openai.com/account/billing" : p === "groq" ? "https://console.groq.com/settings/billing" : p === "claude" ? "https://console.anthropic.com/settings/billing" : p === "gemini" ? "https://aistudio.google.com/app/billing" : p === "deepseek" ? "https://platform.deepseek.com/usage" : null;
              return (
                <div className={bodyClass}>
                  {settings.llmSystemError && (
                    <div className="p-4 rounded-lg text-sm font-medium bg-red-500/10 text-red-600 border border-red-500/20 flex items-center justify-between">
                      <span>⚠️ {settings.llmSystemError}</span>
                      <button onClick={() => settings.update({ llmSystemError: null })} className="bg-transparent border-none text-red-600 cursor-pointer font-bold px-2">×</button>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-6">
                    {isVisible("llm_provider") && (
                      <div className={isMutable("llm_provider") ? "opacity-100" : "opacity-60"}>
                        <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                          Provider
                          {!isMutable("llm_provider") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <select 
                          className={inpClass} 
                          value={settings.llmProvider || ""} 
                          disabled={!isMutable("llm_provider")}
                          onChange={(e) => {
                            const prov = e.target.value;
                            if (!prov) return settings.update({ llmProvider: "", llmModel: "" });
                            const pObj = providers.find(p => p.id === prov);
                            settings.update({ llmProvider: prov, llmModel: pObj?.models[0] || "" });
                          }}
                        >
                          <option value="">None</option>
                          {providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </select>
                        {settings.llmProvider && getBillingLink(settings.llmProvider) && (
                          <a href={getBillingLink(settings.llmProvider)!} target="_blank" rel="noreferrer" className="text-xs text-[var(--primary)] mt-2 inline-block underline">Manage Billing & Quota ↗</a>
                        )}
                      </div>
                    )}
                    {isVisible("llm_model") && (
                      <div className={isMutable("llm_model") ? "opacity-100" : "opacity-60"}>
                        <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                          Model
                          {!isMutable("llm_model") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <select 
                          className={inpClass} 
                          value={settings.llmModel || ""} 
                          disabled={!isMutable("llm_model")}
                          onChange={(e) => settings.update({ llmModel: e.target.value })}
                        >
                          <option value="">None</option>
                          {providers.find(p => p.id === settings.llmProvider)?.models.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                      </div>
                    )}
                  </div>

                  {isVisible("llm_api_key_encrypted") && (
                    <div className={isMutable("llm_api_key_encrypted") ? "opacity-100" : "opacity-60"}>
                      <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                        API Key
                        {!isMutable("llm_api_key_encrypted") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                      </p>
                      <div className="relative">
                        <input 
                          type={showApiKey ? "text" : "password"} 
                          className={`${inpClass} pr-14`}
                          disabled={!isMutable("llm_api_key_encrypted")}
                          placeholder="••••••••••••••••••••••••" 
                          value={settings.llmApiKey} 
                          onChange={(e) => settings.update({ llmApiKey: e.target.value })} 
                        />
                        <button 
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="absolute right-4 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-zinc-500"
                        >
                          {showApiKey ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                      </div>
                      <p className={subClass}>Only required if changing. Saved securely in the database.</p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-6">
                    {isVisible("llm_mode") && (
                      <div className={isMutable("llm_mode") ? "opacity-100" : "opacity-60"}>
                        <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                          Processing Mode
                          {!isMutable("llm_mode") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <div className="flex gap-2">
                          <button disabled={!isMutable("llm_mode")} onClick={() => settings.update({ llmMode: "fallback" })} className={settings.llmMode === "fallback" ? btnAClass : btnIClass}>Fallback</button>
                          <button disabled={!isMutable("llm_mode")} onClick={() => settings.update({ llmMode: "always_on" })} className={settings.llmMode === "always_on" ? btnAClass : btnIClass}>Always-On</button>
                        </div>
                        <p className={subClass}>{settings.llmMode === "fallback" ? "Low Token Usage: Calls AI only if intent matches fail" : "High Token Usage: Routes every command to AI"}</p>
                      </div>
                    )}
                    {isVisible("llm_temperature") && (
                      <div className={isMutable("llm_temperature") ? "opacity-100" : "opacity-60"}>
                        <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                          Temperature: {settings.llmTemperature}
                          {!isMutable("llm_temperature") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <input 
                          type="range" 
                          min="0" 
                          max="1" 
                          step="0.1" 
                          value={settings.llmTemperature} 
                          disabled={!isMutable("llm_temperature")} 
                          onChange={(e) => settings.update({ llmTemperature: parseFloat(e.target.value) })} 
                          className="w-full mt-2 accent-[var(--primary)]" 
                        />
                        <div className="flex justify-between text-xs text-zinc-500 mt-1 font-medium">
                          <span>Precise</span><span>Creative</span>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="mt-4 p-5 bg-[var(--secondary)] rounded-xl border border-[var(--border)] flex items-center justify-between">
                    <div>
                      <p className="text-[15px] font-semibold text-[var(--foreground)]">Test Connection</p>
                      <p className="text-[13px] text-zinc-500">Verify your API key and model</p>
                    </div>
                    <button 
                      onClick={handleTestLlm} 
                      disabled={testingLlm}
                      className="px-5 py-2 rounded-lg text-sm font-semibold cursor-pointer bg-[var(--background)] border border-[var(--border)] text-[var(--foreground)] flex items-center gap-2 shadow-sm hover:bg-[var(--secondary)] transition-all duration-150"
                    >
                      {testingLlm ? <Loader2 size={16} className="animate-spin" /> : <Link2 size={16} />}
                      Test API
                    </button>
                  </div>
                  {testResult && (
                    <div className={`p-4 rounded-lg text-sm font-medium border ${testResult.ok ? "bg-green-500/10 text-green-600 border-green-500/20" : "bg-red-500/10 text-red-600 border-red-500/20"}`}>
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
          <section className={cardClass}>
            <div className={hdrClass}>
              <Globe className="w-5 h-5 text-zinc-500" />
              <span className="text-base font-semibold text-[var(--foreground)]">Browser Automation</span>
            </div>
            <div className={bodyClass}>
              {isVisible("browser_type") && (
                <div className={isMutable("browser_type") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Browser Engine
                    {!isMutable("browser_type") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="flex gap-3">
                    {(["chromium", "firefox", "webkit"] as const).map((b) => (
                      <button 
                        key={b} 
                        disabled={!isMutable("browser_type")} 
                        onClick={() => settings.update({ browserType: b })} 
                        className={settings.browserType === b ? btnAClass : btnIClass}
                      >
                        {b.charAt(0).toUpperCase() + b.slice(1)}
                      </button>
                    ))}
                  </div>
                  <p className={subClass}>Chromium is highly recommended for stability.</p>
                </div>
              )}

              {isVisible("browser_animations_enabled") && (
                <div className={`flex items-center justify-between mt-4 p-5 bg-[var(--secondary)] rounded-xl ${isMutable("browser_animations_enabled") ? "opacity-100" : "opacity-60"}`}>
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                      Browser Animations
                      {!isMutable("browser_animations_enabled") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                    </p>
                    <p className="text-[13px] text-zinc-500 mt-1">Show visual feedback (animated cursor, element highlights) during automation</p>
                  </div>
                  <Toggle checked={settings.browserAnimationsEnabled} disabled={!isMutable("browser_animations_enabled")} onChange={() => settings.update({ browserAnimationsEnabled: !settings.browserAnimationsEnabled })} />
                </div>
              )}

              {isVisible("restrict_browser_automation") && (
                <div className={`flex items-center justify-between mt-4 p-5 bg-[var(--secondary)] rounded-xl ${isMutable("restrict_browser_automation") ? "opacity-100" : "opacity-60"}`}>
                  <div>
                    <p className="text-[15px] font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                      Restrict Website Automation
                      {!isMutable("restrict_browser_automation") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                    </p>
                    <p className="text-[13px] text-zinc-500 mt-1">Only allow browser automation on sites added to Website Shortcuts</p>
                  </div>
                  <Toggle checked={settings.restrictBrowserAutomation} disabled={!isMutable("restrict_browser_automation")} onChange={() => settings.update({ restrictBrowserAutomation: !settings.restrictBrowserAutomation })} />
                </div>
              )}

              {/* ── Website Shortcuts ── */}
              {isVisible("crm_sites") && (
                <div className={`mt-4 pt-6 border-t border-[var(--border)] ${isMutable("crm_sites") ? "opacity-100" : "opacity-60"}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="text-base font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                        Website Shortcuts
                        {!isMutable("crm_sites") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                      </p>
                      <p className="text-xs text-zinc-500 mt-1">Say a keyword to instantly open any website — CRM, dashboards, tools, anything.</p>
                    </div>
                    {isMutable("crm_sites") && (
                      <button
                        id="add-website-shortcut-btn"
                        onClick={() => settings.update({ crmSites: [...settings.crmSites, { url: "", keywords: "" }] })}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[13px] font-semibold cursor-pointer bg-[var(--primary)] text-[var(--primary-foreground)] border-none shrink-0 hover:opacity-90 active:scale-95 transition-all duration-150"
                      >
                        + Add Website
                      </button>
                    )}
                  </div>

                  <div className="flex flex-col gap-3.5">
                    {settings.crmSites.map((site, idx) => (
                      <div key={idx} className="bg-[var(--secondary)] rounded-xl p-4 border border-[var(--border)]">
                        {/* Site header */}
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-[13px] font-semibold text-zinc-500">Website {idx + 1}</span>
                          {settings.crmSites.length > 1 && isMutable("crm_sites") && (
                            <button
                              onClick={() => {
                                const updated = settings.crmSites.filter((_, i) => i !== idx);
                                settings.update({ crmSites: updated, crmUrl: updated[0]?.url || "", crmKeywords: updated[0]?.keywords || "" });
                              }}
                              className="bg-transparent border-none cursor-pointer text-zinc-500 text-base px-1 leading-none hover:text-red-500 active:scale-90 transition-colors"
                              title="Remove this website"
                            >
                              ✕
                            </button>
                          )}
                        </div>

                        {/* URL row */}
                        <div className="mb-2.5">
                          <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5">Website URL</p>
                          <input
                            className={inpClass}
                            disabled={!isMutable("crm_sites")}
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
                          <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5">Voice Keywords <span className="font-normal text-zinc-500">(comma separated)</span></p>
                          <input
                            className={inpClass}
                            disabled={!isMutable("crm_sites")}
                            value={site.keywords}
                            placeholder="open my dashboard, open analytics"
                            onChange={(e) => {
                              const updated = settings.crmSites.map((s, i) => i === idx ? { ...s, keywords: e.target.value } : s);
                              settings.update({ crmSites: updated, ...(idx === 0 ? { crmKeywords: e.target.value } : {}) });
                            }}
                          />
                          <p className={subClass}>Say any of these phrases to instantly open this website.</p>
                        </div>
                      </div>
                    ))}

                    {settings.crmSites.length === 0 && (
                      <p className="text-sm text-zinc-500 text-center p-4">
                        No websites configured.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Global Website Shortcuts ── */}
              {isVisible("global_website_shortcuts") && (
                <div className={`mt-6 pt-6 border-t border-[var(--border)] ${isMutable("global_website_shortcuts") ? "opacity-100" : "opacity-60"}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="text-base font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                        Global Website Shortcuts
                        {!isMutable("global_website_shortcuts") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                      </p>
                      <p className="text-xs text-zinc-500 mt-1">
                        Centralized shortcuts visible to all users.
                      </p>
                    </div>
                  </div>

                  {globalShortcutsError && (
                    <div className="p-3 mb-3 rounded-lg bg-red-500/10 text-red-500 border border-red-500/20 text-xs font-medium">
                      {globalShortcutsError}
                    </div>
                  )}
                  {globalShortcutsSuccess && (
                    <div className="p-3 mb-3 rounded-lg bg-green-500/10 text-green-600 border border-green-500/20 text-xs font-medium">
                      {globalShortcutsSuccess}
                    </div>
                  )}

                  {/* Add form — only visible if mutable */}
                  {isMutable("global_website_shortcuts") && (
                    <form 
                      onSubmit={(e) => {
                        e.preventDefault();
                        const formData = new FormData(e.currentTarget);
                        const url = formData.get("url") as string;
                        const keywords = formData.get("keywords") as string;
                        if (!url || !keywords) return;
                        handleAddGlobalShortcut(url, keywords);
                        e.currentTarget.reset();
                      }}
                      className="bg-[var(--secondary)] rounded-xl p-4 border border-[var(--border)] mb-4 flex flex-col gap-3"
                    >
                      <p className="text-sm font-semibold text-[var(--foreground)]">Add Global Shortcut</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-zinc-400 block mb-1">Website URL</label>
                          <input 
                            name="url"
                            required
                            placeholder="https://example.com"
                            className={inpClass}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-zinc-400 block mb-1">Voice Keywords (comma separated)</label>
                          <input 
                            name="keywords"
                            required
                            placeholder="open example, go to example"
                            className={inpClass}
                          />
                        </div>
                      </div>
                      <button
                        type="submit"
                        className="self-end px-4 py-2 rounded-lg text-[13px] font-semibold bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 active:scale-95 transition-all duration-150 border-none cursor-pointer"
                      >
                        + Add Global Shortcut
                      </button>
                    </form>
                  )}

                  {/* List of shortcuts */}
                  <div className="flex flex-col gap-3">
                    {loadingGlobalShortcuts ? (
                      <div className="flex items-center gap-2 py-4 justify-center text-zinc-500">
                        <Loader2 className="animate-spin" size={16} />
                        <span className="text-sm">Loading global shortcuts...</span>
                      </div>
                    ) : (
                      globalShortcuts.map((site) => (
                        <div key={site.id} className="bg-[var(--secondary)] rounded-xl p-4 border border-[var(--border)] flex items-center justify-between">
                          <div className="flex-1 min-w-0 pr-4">
                            <p className="text-sm font-semibold text-[var(--foreground)] truncate">{site.url}</p>
                            <p className="text-xs text-zinc-500 mt-0.5">Keywords: <span className="font-mono text-zinc-400">{site.keywords}</span></p>
                          </div>
                          {isMutable("global_website_shortcuts") && (
                            <button
                              onClick={() => handleDeleteGlobalShortcut(site.id)}
                              className="bg-transparent border-none cursor-pointer text-zinc-500 hover:text-red-500 active:scale-90 transition-colors p-1"
                              title="Delete global shortcut"
                            >
                              ✕
                            </button>
                          )}
                        </div>
                      ))
                    )}

                    {!loadingGlobalShortcuts && globalShortcuts.length === 0 && (
                      <p className="text-sm text-zinc-500 text-center p-4">
                        No global shortcuts configured.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>
        );

      case "system":
        return (
          <section className={cardClass}>
            <div className={hdrClass}>
              <Shield className="w-5 h-5 text-zinc-500" />
              <span className="text-base font-semibold text-[var(--foreground)]">System Preferences</span>
            </div>
            <div className={bodyClass}>
              {isVisible("theme") && (
                <div className={isMutable("theme") ? "opacity-100" : "opacity-60"}>
                  <p className="text-[13px] font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1.5">
                    Theme
                    {!isMutable("theme") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                  </p>
                  <div className="flex gap-3">
                    {(["dark", "light"] as const).map((t) => (
                      <button 
                        key={t} 
                        disabled={!isMutable("theme")} 
                        onClick={() => settings.update({ theme: t })} 
                        className={settings.theme === t ? btnAClass : btnIClass}
                      >
                        {t.charAt(0).toUpperCase() + t.slice(1)} Mode
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-col gap-4 mt-4">
                {[
                  { key: "enableDesktopOverlay", label: "Desktop Overlay", desc: "Show floating pill for quick access to Mic and AI" },
                  { key: "startupOnBoot", label: "Start on boot", desc: "Launch ACE automatically when Windows starts" },
                  { key: "minimizeToTray", label: "Minimize to tray", desc: "Keep ACE running in the background when closed" },
                ].map(({ key, label, desc }) => {
                  const dbKey = key === "enableDesktopOverlay" ? "enable_desktop_overlay" :
                    key === "startupOnBoot" ? "startup_on_boot" : "minimize_to_tray";
                  if (!isVisible(dbKey)) return null;
                  const val = settings[key as "startupOnBoot" | "minimizeToTray" | "enableDesktopOverlay"];
                  const disabled = !isMutable(dbKey);
                  return (
                    <div key={key} className={`flex items-center justify-between p-5 bg-[var(--secondary)] rounded-xl ${disabled ? "opacity-60" : "opacity-100"}`}>
                      <div>
                        <p className="text-[15px] font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                          {label}
                          {disabled && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                        </p>
                        <p className="text-[13px] text-zinc-500 mt-1">{desc}</p>
                      </div>
                      <Toggle checked={val} disabled={disabled} onChange={() => settings.update({ [key]: !val })} />
                    </div>
                  );
                })}
              </div>

              {/* ── App & File Scanning ── */}
              {isVisible("scan_mode") && (
                <div className={`mt-6 pt-6 border-t border-[var(--border)] ${isMutable("scan_mode") ? "opacity-100" : "opacity-60"}`}>
                  <div className="flex items-center gap-2.5 mb-4">
                    <HardDrive className="w-[18px] h-[18px] text-[var(--primary)]" />
                    <p className="text-[15px] font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                      App &amp; File Scanning
                      {!isMutable("scan_mode") && <span title="Locked by Administrator" className="inline-flex items-center ml-1.5"><Lock className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-500 shrink-0" /></span>}
                    </p>
                  </div>

                  {/* Mode selector */}
                  <div className="grid grid-cols-2 gap-4 mb-5">
                    {([
                      { key: "auto", label: "Auto", desc: "Scan on startup and refresh automatically", icon: "🔄" },
                      { key: "manual", label: "Manual", desc: "Only scan when you click the button below", icon: "🖐" },
                    ] as const).map(({ key, label, desc, icon }) => {
                      const active = settings.scanMode === key;
                      return (
                        <button 
                          key={key} 
                          disabled={!isMutable("scan_mode")} 
                          onClick={() => settings.update({ scanMode: key })}
                          className={`text-left p-4.5 rounded-xl transition-all duration-200 ${!isMutable("scan_mode") ? "cursor-not-allowed" : "cursor-pointer"} ${active ? "bg-[var(--secondary)] border-2 border-[var(--primary)] shadow-md" : "bg-transparent border border-[var(--border)] shadow-none"}`}
                        >
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="text-[17.6px]">{icon}</span>
                            <span className="text-[15px] font-semibold text-[var(--foreground)]">{label}</span>
                          </div>
                          <p className="text-[13px] text-zinc-500">{desc}</p>
                          {active && (
                            <div className="mt-2.5 flex items-center gap-1 text-[var(--primary)] text-xs font-semibold">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Selected
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {/* Scan Now row */}
                  <div className="flex items-center justify-between p-4 bg-[var(--secondary)] rounded-xl border border-[var(--border)]">
                    <div>
                      <p className="text-sm font-semibold text-[var(--foreground)]">Scan Now</p>
                      <p className="text-xs text-zinc-500 mt-1">
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
                      className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold border shadow-sm transition-all duration-200 ${scanning ? "cursor-not-allowed opacity-70 bg-[var(--background)] border-[var(--border)] text-[var(--foreground)]" : "cursor-pointer bg-[var(--background)] border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--secondary)] active:scale-95"}`}
                    >
                      {scanning
                        ? <><Loader2 size={15} className="animate-spin" /> Scanning...</>
                        : <><RefreshCw size={15} /> Scan Now</>}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        );
      case "admin":
        return (
          <section className={cardClass}>
            <div className={hdrClass}>
              <Shield className="w-5 h-5 text-[var(--primary)]" />
              <span className="text-base font-semibold text-[var(--foreground)]">Policy Administration</span>
            </div>
            <div className={bodyClass}>
              <p className="text-sm text-zinc-500 mb-6">
                Configure screen settings visibility and modify fine-grained permissions for each user.
              </p>

              {adminError && (
                <div className="p-4 rounded-lg bg-red-500/10 text-red-500 border border-red-500/20 text-sm font-medium mb-4">
                  {adminError}
                </div>
              )}

              {adminSuccess && (
                <div className="p-4 rounded-lg bg-green-500/10 text-green-600 border border-green-500/20 text-sm font-medium mb-4">
                  {adminSuccess}
                </div>
              )}

              {loadingPolicies ? (
                <div className="flex items-center justify-center min-h-[10rem] gap-2 text-zinc-500">
                  <Loader2 size={20} className="animate-spin" />
                  <span>Loading user policies...</span>
                </div>
              ) : (
                <div className="flex flex-col gap-6">
                  {usersPolicies.filter((user) => user.role !== "admin").map((user) => (
                    <div key={user.user_id} className="p-6 bg-[var(--secondary)] rounded-xl border border-[var(--border)]">

                      {/* User Header Info */}
                      <div className="flex items-center justify-between border-b border-[var(--border)] pb-4 mb-4">
                        <div>
                          <p className="text-base font-semibold text-[var(--foreground)]">{user.display_name || "Unnamed User"}</p>
                          <p className="text-[13px] text-zinc-500">{user.email} (Role: <span className="text-[var(--primary)] font-semibold">{user.role}</span>)</p>
                        </div>

                        {/* Save Action for this user */}
                        <button
                          onClick={() => handleUpdatePolicy(user.user_id, user.permissions, user.screen_settings_visible_to_users)}
                          disabled={adminSavingUser === user.user_id}
                          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-semibold border-none ${adminSavingUser === user.user_id ? "cursor-not-allowed bg-[var(--primary)]/60 text-[var(--primary-foreground)]/60" : "cursor-pointer bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 active:scale-95 transition-all"}`}
                        >
                          {adminSavingUser === user.user_id ? (
                            <><Loader2 size={14} className="animate-spin" /> Saving...</>
                          ) : "Save Changes"}
                        </button>
                      </div>

                      {/* Fine-grained permissions controls */}
                      <div>
                        <p className="text-sm font-semibold text-[var(--foreground)] mb-3">Setting Permissions Matrix</p>

                        <div className="flex flex-col gap-4">
                          {PERMISSION_FIELDS.map((group) => (
                            <div key={group.category} className="border border-[var(--border)] rounded-xl p-4 bg-[var(--background)]">
                              <p className="text-[13px] font-bold text-[var(--primary)] uppercase tracking-wider mb-3">{group.category}</p>
                              <div className="flex flex-col gap-2">
                                {group.items.map((field) => {
                                  const perm = user.permissions[field.key] || (field.key === "global_website_shortcuts" ? { visible: true, mutable: false } : { visible: true, mutable: true });
                                  return (
                                    <div key={field.key} className="grid grid-cols-[1.5fr_1fr_1fr] items-center px-3.5 py-2.5 bg-[var(--secondary)] rounded-lg border border-[var(--border)]">
                                      <span className="text-[13px] font-medium text-[var(--foreground)]">{field.label}</span>

                                      {/* Visible Option toggle */}
                                      <div className="flex items-center gap-1.5">
                                        <span className="text-xs text-zinc-500">Visible:</span>
                                        <Toggle
                                          checked={perm.visible}
                                          onChange={() => {
                                            const updatedPerms = {
                                              ...user.permissions,
                                              [field.key]: { ...perm, visible: !perm.visible }
                                            };
                                            setUsersPolicies(usersPolicies.map(u => u.user_id === user.user_id ? { ...u, permissions: updatedPerms } : u));
                                            handleUpdatePolicy(user.user_id, updatedPerms, user.screen_settings_visible_to_users);
                                          }}
                                        />
                                      </div>

                                      {/* Mutable Option toggle */}
                                      <div className="flex items-center gap-1.5">
                                        {!(field as any).hideMutable ? (
                                          <>
                                            <span className="text-xs text-zinc-500">Editable:</span>
                                            <Toggle
                                              checked={perm.mutable}
                                              onChange={() => {
                                                const updatedPerms = {
                                                  ...user.permissions,
                                                  [field.key]: { ...perm, mutable: !perm.mutable }
                                                };
                                                setUsersPolicies(usersPolicies.map(u => u.user_id === user.user_id ? { ...u, permissions: updatedPerms } : u));
                                                handleUpdatePolicy(user.user_id, updatedPerms, user.screen_settings_visible_to_users);
                                              }}
                                            />
                                          </>
                                        ) : (
                                          <span className="text-xs text-zinc-500 italic">N/A</span>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                    </div>
                  ))}

                  {usersPolicies.filter((user) => user.role !== "admin").length === 0 && (
                    <p className="text-center text-zinc-500 text-sm p-8">
                      No users found.
                    </p>
                  )}
                </div>
              )}
            </div>
          </section>
        );
      default: return null;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-10">

          <div className="w-full flex gap-16 relative">

            {/* Left Navigation Sidebar */}
            <nav className="w-[240px] shrink-0 sticky top-0 flex flex-col gap-1.5">
              <div className="mb-8">
                <h1 className="text-3xl font-semibold text-[var(--foreground)] tracking-tight flex items-center gap-2.5">
                  <Settings className="w-7 h-7 text-[var(--primary)]" /> Settings
                </h1>
              </div>

              {(() => {
                let visibleTabs = TABS;
                if (settings.role !== "admin") {
                  visibleTabs = TABS.filter((tab) => {
                    const perm = settings.permissions[`tab_${tab.id}`];
                    return perm?.visible !== false;
                  });
                } else {
                  visibleTabs = [...TABS, { id: "admin", label: "Admin Panel", icon: Shield }];
                }
                return visibleTabs.map((tab) => {
                  const isActive = activeTab === tab.id;
                  const Icon = tab.icon;
                  return (
                    <button 
                      key={tab.id} 
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-3.5 w-full px-4 py-3.5 rounded-lg border-none cursor-pointer transition-all duration-200 text-left ${isActive ? "bg-[var(--secondary)] text-[var(--foreground)] font-semibold" : "bg-transparent text-zinc-500 font-medium"}`}
                    >
                      <Icon size={18} className={isActive ? "text-[var(--primary)]" : "text-inherit"} />
                      {tab.label}
                    </button>
                  );
                });
              })()}

              <div className="mt-8 pt-8 border-t border-[var(--border)] flex flex-col gap-4">
                <div className="flex items-center gap-3 text-zinc-500 text-sm">
                  <div className={`w-2 h-2 rounded-full transition-colors duration-300 ${saved ? "bg-[var(--primary)]" : "bg-zinc-500"} ${saving ? "opacity-50" : "opacity-100"}`} />
                  {saving ? "Saving changes..." : saved ? "All changes saved" : "Auto-saving is active"}
                </div>
              </div>
            </nav>

            {/* Main Content Area */}
            <div className="flex-1 min-w-0 pb-16">
              {!connected && (
                <div className="bg-red-500/10 border border-red-500/30 text-red-500 p-4 rounded-xl mb-6 flex items-center gap-3 font-medium text-sm">
                  Server is currently offline. Settings cannot be modified.
                </div>
              )}
              <div className={`transition-all duration-200 ${!connected ? "opacity-50 pointer-events-none" : "opacity-100 pointer-events-auto"}`}>
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