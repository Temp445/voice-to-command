"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings, Mic, Volume2, Globe, Shield, CheckCircle2, Eye, EyeOff, Bot, Loader2, Link2 } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useSettingsStore } from "@/store/settingsStore";
import { api } from "@/lib/api";

const card    = { background: "var(--card)", border: "1px solid var(--border)", borderRadius: "1rem", overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" };
const hdr     = { padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.75rem", background: "rgba(255,255,255,0.02)" };
const body    = { padding: "1.5rem", display: "flex", flexDirection: "column" as const, gap: "1.5rem" };
const lbl     = { fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.375rem" } as React.CSSProperties;
const sub     = { fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.25rem" };
const inp     = { width: "100%", background: "var(--input)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.625rem 0.875rem", fontSize: "0.875rem", color: "var(--foreground)", fontFamily: "var(--font-mono)", outline: "none", transition: "border-color 0.2s" } as React.CSSProperties;
const btnA    = { padding: "0.5rem 1rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer", border: "1px solid var(--ring)", background: "var(--primary)", color: "var(--primary-foreground)", transition: "all 0.15s", boxShadow: "0 2px 4px rgba(0,0,0,0.1)" } as React.CSSProperties;
const btnI    = { padding: "0.5rem 1rem", borderRadius: "0.5rem", fontSize: "0.8125rem", fontWeight: 500, cursor: "pointer", border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--muted-foreground)", transition: "all 0.15s" } as React.CSSProperties;

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
  const [activeTab, setActiveTab] = useState("voice");
  const [saving,  setSaving]  = useState(false);
  const [saved,   setSaved]   = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  
  // LLM State
  const [providers, setProviders] = useState<{ id: string; name: string; models: string[] }[]>([]);
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // TTS State
  const [testTtsText, setTestTtsText] = useState("Hello, I am your desktop assistant.");
  const [testingTts, setTestingTts] = useState(false);

  useEffect(() => {
    api.getLLMProviders().then((data: any) => setProviders(data)).catch(err => console.error(err));
    api.getSettings().then((data: any) => {
      settings.update({
        wakeWord: data.wake_word, sttProvider: data.stt_provider, sttNoiseCancellation: data.stt_noise_cancellation,
        whisperModel: data.whisper_model, ttsProvider: data.tts_provider, piperVoice: data.piper_voice,
        browserType: data.browser_type, startupOnBoot: data.startup_on_boot, minimizeToTray: data.minimize_to_tray,
        theme: data.theme, browserAnimationsEnabled: data.browser_animations_enabled, enableDesktopOverlay: data.enable_desktop_overlay,
        crmUrl: data.crm_url, crmKeywords: data.crm_keywords,
        llmEnabled: data.llm_enabled, llmProvider: data.llm_provider, llmModel: data.llm_model,
        llmMode: data.llm_mode, llmTemperature: data.llm_temperature,
      });
      // removed undefined setGttsApiKey call
      setInitialLoaded(true);
    }).catch(err => console.error(err));
  }, []);

  useEffect(() => {
    if (!initialLoaded) return;
    const timer = setTimeout(() => handleSave(), 500);
    return () => clearTimeout(timer);
  }, [
    initialLoaded,
    settings.wakeWord, settings.sttProvider, settings.sttNoiseCancellation, settings.whisperModel,
    settings.ttsProvider, settings.piperVoice, settings.theme, settings.browserType,
    settings.startupOnBoot, settings.minimizeToTray, settings.browserAnimationsEnabled, settings.enableDesktopOverlay,
    settings.crmUrl, settings.crmKeywords,
    settings.llmEnabled, settings.llmProvider, settings.llmModel, settings.llmMode,
    settings.llmTemperature, settings.llmApiKey
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
      const response = await fetch("http://localhost:8000/api/voice/test-tts", {
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

  const handleSave = async () => {
    setSaving(true);
    try {
      const patch: Record<string, unknown> = {
        wake_word: settings.wakeWord, stt_provider: settings.sttProvider, stt_noise_cancellation: settings.sttNoiseCancellation,
        whisper_model: settings.whisperModel, tts_provider: settings.ttsProvider, piper_voice: settings.piperVoice,
        browser_type: settings.browserType, startup_on_boot: settings.startupOnBoot, minimize_to_tray: settings.minimizeToTray,
        theme: settings.theme, browser_animations_enabled: settings.browserAnimationsEnabled, enable_desktop_overlay: settings.enableDesktopOverlay,
        crm_url: settings.crmUrl, crm_keywords: settings.crmKeywords,
        llm_enabled: settings.llmEnabled, llm_provider: settings.llmProvider, llm_model: settings.llmModel,
        llm_mode: settings.llmMode, llm_temperature: settings.llmTemperature,
      };
      if (settings.ttsProvider === "gtts") { patch.gtts_api_key = ""; }
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
                <input style={inp} value={settings.wakeWord}
                  onChange={(e) => settings.update({ wakeWord: e.target.value })}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--ring)"; }}
                  onBlur={(e)  => { (e.target as HTMLInputElement).style.borderColor  = "var(--border)"; }}
                />
                <p style={sub}>Currently: <span style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>&quot;{settings.wakeWord}&quot;</span></p>
              </div>
              <div>
                <p style={lbl}>STT Provider</p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
                  {[
                    { key: "whisper", label: "Whisper", desc: "Private, works offline" },
                    { key: "gstt",  label: "Google STT", desc: "Highly accurate, requires internet" },
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
                    {(["tiny", "base", "small", "large-v2", "large-v3"] as const).map((m) => (
                      <button key={m} onClick={() => settings.update({ whisperModel: m })} style={settings.whisperModel === m ? btnA : btnI}>
                        {m.charAt(0).toUpperCase() + m.slice(1)}
                      </button>
                    ))}
                  </div>
                  <p style={sub}>Tiny = fastest · Small = accurate · Large = highly accurate but slow</p>
                </div>
              )}
              
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "1rem", padding: "1.25rem", background: "var(--secondary)", borderRadius: "0.75rem" }}>
                <div>
                  <p style={{ fontSize: "0.9375rem", fontWeight: 600, color: "var(--foreground)" }}>Noise Cancellation</p>
                  <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>Aggressively filter background noise using VAD</p>
                </div>
                <Toggle checked={settings.sttNoiseCancellation} onChange={() => settings.update({ sttNoiseCancellation: !settings.sttNoiseCancellation })} />
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
                    { key: "gtts",  label: "Google TTS", desc: "High quality · Requires internet" },
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
                    <option value="en_US-hfc_male-medium">HFC Male (Male)</option>
                    <option value="en_US-hfc_female-medium">HFC Female (Female)</option>
                    <option value="en_US-libritts_r-medium">LibriTTS (Multi-speaker)</option>
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
              const getBillingLink = (p: string) => p==="openai" ? "https://platform.openai.com/account/billing" : p==="groq" ? "https://console.groq.com/settings/billing" : p==="claude" ? "https://console.anthropic.com/settings/billing" : p==="gemini" ? "https://aistudio.google.com/app/billing" : p==="deepseek" ? "https://platform.deepseek.com/usage" : null;
              return (
              <div style={body}>
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
                    <p style={sub}>{settings.llmMode === "fallback" ? "Fast & cheap: Calls AI only if intent matches fail" : "Smarter: Routes every command to AI"}</p>
                  </div>
                  <div>
                    <p style={lbl}>Temperature: {settings.llmTemperature}</p>
                    <input type="range" min="0" max="1" step="0.1" value={settings.llmTemperature} onChange={(e) => settings.update({ llmTemperature: parseFloat(e.target.value) })} style={{ width: "100%", marginTop: "0.5rem" }} />
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

              <div style={{ marginTop: "1rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)" }}>
                <p style={{ fontSize: "1rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "1rem" }}>CRM Integration</p>
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  <div>
                    <p style={lbl}>CRM Base URL</p>
                    <input style={inp} value={settings.crmUrl} onChange={(e) => settings.update({ crmUrl: e.target.value })} placeholder="https://crm.acesoftcloud.in/" />
                    <p style={sub}>The landing page or base URL of your CRM system.</p>
                  </div>
                  <div>
                    <p style={lbl}>Trigger Keywords (comma separated)</p>
                    <input style={inp} value={settings.crmKeywords} onChange={(e) => settings.update({ crmKeywords: e.target.value })} placeholder="open crm, open my crm" />
                    <p style={sub}>Voice phrases that will trigger the browser to navigate to your CRM.</p>
                  </div>
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
                <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
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
        </main>
      </div>
    </div>
  );
}