"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Settings, Mic, Volume2, Globe, Shield, CheckCircle2, Eye, EyeOff, Smartphone } from "lucide-react";
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

  useEffect(() => {
    setRemoteUrl(window.location.origin + "/remote");
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const patch: Record<string, unknown> = {
        wake_word: settings.wakeWord, whisper_model: settings.whisperModel,
        tts_provider: settings.ttsProvider, piper_voice: settings.piperVoice,
        browser_type: settings.browserType, startup_on_boot: settings.startupOnBoot,
        minimize_to_tray: settings.minimizeToTray, theme: settings.theme,
      };
      if (settings.ttsProvider === "gtts") { patch.gtts_api_key = ""; settings.setGttsApiKey(""); }
      await api.updateSettings(patch);
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
