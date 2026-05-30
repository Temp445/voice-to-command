"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Settings, Mic, Volume2, Globe, Shield, CheckCircle2, Eye, EyeOff, Smartphone, Bot, Loader2, Link2 } from "lucide-react";
import QRCode from "react-qr-code";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useSettingsStore } from "@/store/settingsStore";
import { api } from "@/lib/api";

const card    = { background: "var(--card)",      border: "1px solid var(--border)", borderRadius: "0.75rem", overflow: "hidden" };
const hdr     = { padding: "1rem 1.25rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.5rem" };
const body    = { padding: "1.25rem", display: "flex", flexDirection: "column" as const, gap: "1.25rem" };
const lbl     = { fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", marginBottom: "0.375rem" } as React.CSSProperties;
const sub     = { fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.25rem" };
const inp     = { width: "100%", background: "var(--input)", border: "1px solid var(--border)", borderRadius: "0.5rem", padding: "0.625rem 0.875rem", fontSize: "0.875rem", color: "var(--foreground)", fontFamily: "var(--font-mono)", outline: "none" } as React.CSSProperties;
const btnA    = { padding: "0.4rem 1rem", borderRadius: "0.375rem", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer", border: "1px solid var(--ring)", background: "var(--primary)", color: "var(--primary-foreground)", transition: "opacity 0.15s" } as React.CSSProperties;
const btnI    = { padding: "0.4rem 1rem", borderRadius: "0.375rem", fontSize: "0.8125rem", fontWeight: 500, cursor: "pointer", border: "1px solid var(--border)", background: "var(--secondary)", color: "var(--muted-foreground)", transition: "background 0.15s" } as React.CSSProperties;

export default function SettingsPage() {
  const settings = useSettingsStore();
  const [saving,  setSaving]  = useState(false);
  const [saved,   setSaved]   = useState(false);
  const [remoteUrl, setRemoteUrl] = useState("");
  
  // LLM State
  const [providers, setProviders] = useState<{ id: string; name: string; models: string[] }[]>([]);
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingLlm, setTestingLlm] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    setRemoteUrl(window.location.origin + "/remote");
    
    // Fetch LLM Providers
    api.getLLMProviders().then((data: any) => {
      setProviders(data);
    }).catch(err => console.error("Failed to load providers", err));
    
    // Sync current settings from backend
    api.getSettings().then((data: any) => {
      settings.update({
        wakeWord: data.wake_word, whisperModel: data.whisper_model,
        ttsProvider: data.tts_provider, piperVoice: data.piper_voice,
        browserType: data.browser_type, startupOnBoot: data.startup_on_boot,
        minimizeToTray: data.minimize_to_tray, theme: data.theme,
        llmEnabled: data.llm_enabled, llmProvider: data.llm_provider,
        llmModel: data.llm_model, llmMode: data.llm_mode,
        llmTemperature: data.llm_temperature,
      });
      if (!data.gtts_configured) settings.setGttsApiKey("");
    }).catch(err => console.error("Failed to sync settings", err));
  }, []);

  const handleTestLlm = async () => {
    setTestingLlm(true);
    setTestResult(null);
    try {
      const res: any = await api.testLLM();
      if (res.ok) setTestResult({ ok: true, msg: `Success! Model replied: ${res.reply}` });
      else setTestResult({ ok: false, msg: res.error || "Connection failed" });
    } catch (err: any) {
      setTestResult({ ok: false, msg: err.message || "Request failed" });
    } finally {
      setTestingLlm(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const patch: Record<string, unknown> = {
        wake_word: settings.wakeWord, whisper_model: settings.whisperModel,
        tts_provider: settings.ttsProvider, piper_voice: settings.piperVoice,
        browser_type: settings.browserType, startup_on_boot: settings.startupOnBoot,
        minimize_to_tray: settings.minimizeToTray, theme: settings.theme,
        llm_enabled: settings.llmEnabled, llm_provider: settings.llmProvider,
        llm_model: settings.llmModel, llm_mode: settings.llmMode,
        llm_temperature: settings.llmTemperature,
      };
      if (settings.ttsProvider === "gtts") { patch.gtts_api_key = ""; settings.setGttsApiKey(""); }
      if (settings.llmApiKey) {
        patch.llm_api_key = settings.llmApiKey;
      }
      await api.updateSettings(patch);
      settings.update({ llmApiKey: "" }); // clear from UI after save
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "var(--background)" }}>
      <Sidebar />
      <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
        <TopBar />
        <main style={{ flex: 1, overflowY: "auto", padding: "1.75rem" }}>
          <div style={{ maxWidth: "720px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.25rem" }}>

            {/* Header */}
            <div>
              <h1 style={{ fontSize: "1.875rem", fontWeight: 800, color: "var(--foreground)", letterSpacing: "-0.02em", display: "flex", alignItems: "center", gap: "0.625rem" }}>
                <Settings style={{ width: "1.5rem", height: "1.5rem" }} /> Settings
              </h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.25rem" }}>Configure ACE Voice Controller</p>
            </div>

            {/* ── Voice Recognition ── */}
            <section style={card}>
              <div style={hdr}>
                <Mic style={{ width: "1rem", height: "1rem", color: "var(--muted-foreground)" }} />
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>Voice Recognition</span>
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
                  <p style={lbl}>Whisper Model</p>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    {(["tiny", "base", "small"] as const).map((m) => (
                      <button key={m} onClick={() => settings.update({ whisperModel: m })}
                        style={settings.whisperModel === m ? btnA : btnI}>
                        {m.charAt(0).toUpperCase() + m.slice(1)}
                      </button>
                    ))}
                  </div>
                  <p style={sub}>Tiny = fastest · Small = most accurate</p>
                </div>
              </div>
            </section>

            {/* ── TTS Engine ── */}
            <section style={card}>
              <div style={hdr}>
                <Volume2 style={{ width: "1rem", height: "1rem", color: "var(--muted-foreground)" }} />
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>Text-to-Speech Engine</span>
              </div>
              <div style={body}>
                <div>
                  <p style={lbl}>TTS Provider</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                    {[
                      { key: "piper", label: "Piper TTS",        badge: "Offline", badgeBg: "rgba(34,197,94,0.12)",  badgeColor: "#22c55e", desc: "Fully offline · No API key · Fast" },
                      { key: "gtts",  label: "Google TTS",  badge: "Cloud",   badgeBg: "rgba(59,130,246,0.12)", badgeColor: "#3b82f6", desc: "High quality · Requires internet" },
                    ].map(({ key, label, badge, badgeBg, badgeColor, desc }) => {
                      const active = settings.ttsProvider === key;
                      return (
                        <button key={key} onClick={() => settings.setTtsProvider(key as "piper" | "gtts")}
                          style={{ textAlign: "left", padding: "1rem", borderRadius: "0.625rem", cursor: "pointer", transition: "all 0.15s", background: active ? "var(--secondary)" : "transparent", border: active ? "1px solid var(--ring)" : "1px solid var(--border)" }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.375rem" }}>
                            <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>{label}</span>
                            <span style={{ fontSize: "0.7rem", padding: "0.1rem 0.5rem", borderRadius: "9999px", background: badgeBg, color: badgeColor, border: `1px solid ${badgeColor}30` }}>{badge}</span>
                          </div>
                          <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>{desc}</p>
                          {active && <div style={{ marginTop: "0.5rem", display: "flex", alignItems: "center", gap: "0.25rem", color: "var(--foreground)", fontSize: "0.75rem" }}><CheckCircle2 style={{ width: "0.75rem", height: "0.75rem" }} /> Selected</div>}
                        </button>
                      );
                    })}
                  </div>
                </div>



                {settings.ttsProvider === "piper" && (
                  <div>
                    <p style={lbl}>Piper Voice</p>
                    <input style={{ ...inp, maxWidth: "22rem" }} value={settings.piperVoice}
                      onChange={(e) => settings.update({ piperVoice: e.target.value })}
                      onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "var(--ring)"; }}
                      onBlur={(e)  => { (e.target as HTMLInputElement).style.borderColor  = "var(--border)"; }}
                    />
                  </div>
                )}
              </div>
            </section>

            {/* ── AI Assistant (LLM) ── */}
            <section style={card}>
              <div style={{ ...hdr, justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <Bot style={{ width: "1rem", height: "1rem", color: "var(--primary)" }} />
                  <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>AI Assistant</span>
                </div>
                <button onClick={() => settings.update({ llmEnabled: !settings.llmEnabled })}
                  style={{ width: "2.75rem", height: "1.5rem", borderRadius: "9999px", border: settings.llmEnabled ? "1px solid var(--ring)" : "1px solid var(--border)", background: settings.llmEnabled ? "var(--primary)" : "var(--secondary)", position: "relative", cursor: "pointer", transition: "all 0.2s" }}>
                  <span style={{ position: "absolute", top: "0.2rem", width: "1.1rem", height: "1.1rem", background: settings.llmEnabled ? "var(--primary-foreground)" : "var(--muted-foreground)", borderRadius: "9999px", transition: "transform 0.2s", transform: settings.llmEnabled ? "translateX(1.45rem)" : "translateX(0.2rem)" }} />
                </button>
              </div>
              
              {settings.llmEnabled && (
                <div style={body}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
                    <div>
                      <p style={lbl}>Provider</p>
                      <select style={inp} value={settings.llmProvider}
                        onChange={(e) => {
                          const prov = e.target.value;
                          const pObj = providers.find(p => p.id === prov);
                          settings.update({ llmProvider: prov, llmModel: pObj?.models[0] || "" });
                        }}>
                        {providers.map(p => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <p style={lbl}>Model</p>
                      <select style={inp} value={settings.llmModel} onChange={(e) => settings.update({ llmModel: e.target.value })}>
                        {providers.find(p => p.id === settings.llmProvider)?.models.map(m => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div>
                    <p style={lbl}>API Key</p>
                    <div style={{ position: "relative" }}>
                      <input type={showApiKey ? "text" : "password"} style={{ ...inp, paddingRight: "3rem" }}
                        placeholder="••••••••••••••••••••••••"
                        value={settings.llmApiKey}
                        onChange={(e) => settings.update({ llmApiKey: e.target.value })}
                      />
                      <button onClick={() => setShowApiKey(!showApiKey)}
                        style={{ position: "absolute", right: "0.75rem", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)" }}>
                        {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                    <p style={sub}>Only required if changing. Saved securely in the database.</p>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
                    <div>
                      <p style={lbl}>Processing Mode</p>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button onClick={() => settings.update({ llmMode: "fallback" })} style={settings.llmMode === "fallback" ? btnA : btnI}>Fallback</button>
                        <button onClick={() => settings.update({ llmMode: "always_on" })} style={settings.llmMode === "always_on" ? btnA : btnI}>Always-On</button>
                      </div>
                      <p style={sub}>{settings.llmMode === "fallback" ? "Only calls AI if command fails (fast, cheap)" : "Routes every command to AI (smarter, slower)"}</p>
                    </div>
                    <div>
                      <p style={lbl}>Temperature: {settings.llmTemperature}</p>
                      <input type="range" min="0" max="1" step="0.1"
                        value={settings.llmTemperature}
                        onChange={(e) => settings.update({ llmTemperature: parseFloat(e.target.value) })}
                        style={{ width: "100%", marginTop: "0.5rem" }}
                      />
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "var(--muted-foreground)", marginTop: "0.25rem" }}>
                        <span>Precise</span><span>Creative</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: "0.5rem", padding: "1rem", background: "var(--secondary)", borderRadius: "0.5rem", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                      <p style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)" }}>Test Connection</p>
                      <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>Verify your API key and model</p>
                    </div>
                    <button onClick={handleTestLlm} disabled={testingLlm}
                      style={{ padding: "0.5rem 1rem", borderRadius: "0.375rem", fontSize: "0.8125rem", fontWeight: 600, cursor: "pointer", background: "var(--background)", border: "1px solid var(--border)", color: "var(--foreground)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      {testingLlm ? <Loader2 size={14} className="animate-spin" /> : <Link2 size={14} />}
                      Test
                    </button>
                  </div>
                  {testResult && (
                    <div style={{ padding: "0.75rem", borderRadius: "0.375rem", fontSize: "0.8125rem", background: testResult.ok ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)", color: testResult.ok ? "#16a34a" : "#dc2626", border: `1px solid ${testResult.ok ? "#22c55e30" : "#ef444430"}` }}>
                      {testResult.msg}
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* ── Browser ── */}
            <section style={card}>
              <div style={hdr}>
                <Globe style={{ width: "1rem", height: "1rem", color: "var(--muted-foreground)" }} />
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>Browser Automation</span>
              </div>
              <div style={body}>
                <div>
                  <p style={lbl}>Browser</p>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    {(["chromium", "firefox", "webkit"] as const).map((b) => (
                      <button key={b} onClick={() => settings.update({ browserType: b })}
                        style={settings.browserType === b ? btnA : btnI}>
                        {b.charAt(0).toUpperCase() + b.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            {/* ── Mobile Remote ── */}
            <section style={card}>
              <div style={hdr}>
                <Smartphone style={{ width: "1rem", height: "1rem", color: "var(--muted-foreground)" }} />
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>Mobile Remote Controller</span>
              </div>
              <div style={body}>
                <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
                  <div style={{ background: "white", padding: "0.5rem", borderRadius: "0.5rem", flexShrink: 0 }}>
                    {remoteUrl ? (
                      <QRCode value={remoteUrl} size={120} />
                    ) : (
                      <div style={{ width: 120, height: 120, background: "#f0f0f0" }} />
                    )}
                  </div>
                  <div>
                    <p style={lbl}>Scan to control from your phone</p>
                    <p style={{ ...sub, lineHeight: 1.5 }}>
                      Use your smartphone's microphone to send voice commands to your PC. 
                      Ensure your phone is connected to the dev tunnel URL if you're testing remotely.
                    </p>
                    <p style={{ ...sub, marginTop: "0.5rem", fontFamily: "var(--font-mono)", color: "var(--primary)" }}>
                      {remoteUrl}
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* ── System ── */}
            <section style={card}>
              <div style={hdr}>
                <Shield style={{ width: "1rem", height: "1rem", color: "var(--muted-foreground)" }} />
                <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--foreground)" }}>System</span>
              </div>
              <div style={body}>
                <div>
                  <p style={lbl}>Theme</p>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    {(["dark", "light"] as const).map((t) => (
                      <button key={t} onClick={() => settings.update({ theme: t })}
                        style={settings.theme === t ? btnA : btnI}>
                        {t.charAt(0).toUpperCase() + t.slice(1)} Mode
                      </button>
                    ))}
                  </div>
                </div>
                {[
                  { key: "startupOnBoot", label: "Start on boot",   desc: "Launch ACE automatically when Windows starts" },
                  { key: "minimizeToTray",label: "Minimize to tray", desc: "Keep ACE running in the system tray when closed" },
                ].map(({ key, label, desc }) => {
                  const val = settings[key as "startupOnBoot" | "minimizeToTray"];
                  return (
                    <div key={key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div>
                        <p style={{ fontSize: "0.875rem", fontWeight: 500, color: "var(--foreground)" }}>{label}</p>
                        <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.125rem" }}>{desc}</p>
                      </div>
                      <button onClick={() => settings.update({ [key]: !val })}
                        style={{ width: "2.75rem", height: "1.5rem", borderRadius: "9999px", border: val ? "1px solid var(--ring)" : "1px solid var(--border)", background: val ? "var(--primary)" : "var(--secondary)", position: "relative", flexShrink: 0, cursor: "pointer", transition: "all 0.2s" }}>
                        <span style={{ position: "absolute", top: "0.2rem", width: "1.1rem", height: "1.1rem", background: val ? "var(--primary-foreground)" : "var(--muted-foreground)", borderRadius: "9999px", transition: "transform 0.2s", transform: val ? "translateX(1.45rem)" : "translateX(0.2rem)" }} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Save */}
            <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}
              onClick={handleSave} disabled={saving}
              style={{ width: "100%", padding: "0.875rem", borderRadius: "0.625rem", border: "1px solid var(--ring)", cursor: "pointer", background: saved ? "var(--secondary)" : "var(--primary)", color: saved ? "var(--foreground)" : "var(--primary-foreground)", fontSize: "0.9375rem", fontWeight: 700, transition: "all 0.2s", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem", opacity: saving ? 0.7 : 1 }}>
              {saved ? <><CheckCircle2 style={{ width: "1.1rem", height: "1.1rem" }} /> Saved!</> : saving ? "Saving…" : "Save Settings"}
            </motion.button>
          </div>
        </main>
      </div>
    </div>
  );
}
