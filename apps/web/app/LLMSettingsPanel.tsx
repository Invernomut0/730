"use client";

import { type ReactElement, useEffect, useState } from "react";

type LLMSettings = {
  document_model: string;
  classification_model: string;
  fallback_model: string;
  relation_model: string;
  rizzo_flow_enabled: boolean;
  rizzo_flow_base_url: string | null;
};
type LLMSettingsResponse = LLMSettings & { jobs_paused: boolean };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function LLMSettingsPanel(): ReactElement {
  const [settings, setSettings] = useState<LLMSettings>();
  const [models, setModels] = useState<string[]>([]);
  const [paused, setPaused] = useState(false);
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const [settingsResponse, modelsResponse] = await Promise.all([fetch(`${API}/api/v1/settings/llm`), fetch(`${API}/api/v1/settings/models`)]);
        if (!settingsResponse.ok) throw new Error("settings_unavailable");
        const { jobs_paused, ...value } = await settingsResponse.json() as LLMSettingsResponse;
        setSettings(value); setPaused(jobs_paused);
        if (modelsResponse.ok) setModels((await modelsResponse.json() as { models: string[] }).models);
      } catch {
        setMessage("Impossibile caricare le impostazioni LLM locali.");
      }
    })();
  }, []);

  function update(field: keyof LLMSettings, value: string | boolean): void {
    setSettings(current => current ? { ...current, [field]: value } : current);
  }

  async function save(): Promise<void> {
    if (!settings) return;
    setWorking(true);
    try {
      const response = await fetch(`${API}/api/v1/settings/llm`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) });
      if (!response.ok) {
        const body = await response.json() as { detail?: string };
        setMessage(body.detail ?? "Impossibile salvare le impostazioni LLM.");
        return;
      }
      const { jobs_paused, ...value } = await response.json() as LLMSettingsResponse;
      setSettings(value); setPaused(jobs_paused);
      setMessage("Impostazioni LLM salvate: valgono per i prossimi job.");
    } catch {
      setMessage("Connessione non disponibile: le impostazioni non sono state salvate.");
    } finally {
      setWorking(false);
    }
  }

  async function controlJobs(action: "stop" | "resume"): Promise<void> {
    if (action === "stop" && !window.confirm("Interrompere i job in coda? Le richieste LLM già in corso termineranno in sicurezza.")) return;
    setWorking(true);
    const response = await fetch(`${API}/api/v1/settings/jobs/${action}`, { method: "POST" });
    setWorking(false);
    if (!response.ok) { setMessage("Impossibile aggiornare lo stato dei job."); return; }
    const result = await response.json() as { jobs_paused: boolean; queued_jobs_discarded: number };
    setPaused(result.jobs_paused);
    setMessage(action === "stop" ? `Job in pausa. Rimossi ${result.queued_jobs_discarded} elementi dalla coda.` : "Job ripresi: puoi avviare nuovamente l’analisi documenti.");
  }

  const options = (selected: string) => <>{selected && !models.includes(selected) && <option value={selected}>{selected}</option>}{models.map(model => <option key={model} value={model}>{model}</option>)}</>;
  if (!settings) return <section className="llm-settings panel"><p className="muted">Caricamento impostazioni LLM…</p></section>;

  return <section className="llm-settings panel" aria-label="Impostazioni LLM e job">
    <header><p className="eyebrow">CONTROLLO MODELLI</p><h2>LLM e job locali</h2><p>Le modifiche non includono chiavi o segreti e si applicano ai nuovi job.</p></header>
    <div className="llm-settings-grid">
      <label>Analisi documenti<select value={settings.document_model} onChange={event => update("document_model", event.target.value)}>{options(settings.document_model)}</select></label>
      <label>Classificazione incerta<select value={settings.classification_model} onChange={event => update("classification_model", event.target.value)}>{options(settings.classification_model)}</select></label>
      <label>Fallback estrazione<select value={settings.fallback_model} onChange={event => update("fallback_model", event.target.value)}>{options(settings.fallback_model)}</select></label>
      <label>Creazione relazioni<select value={settings.relation_model} onChange={event => update("relation_model", event.target.value)}>{options(settings.relation_model)}</select></label>
      <label className="llm-rizzo-toggle"><input checked={settings.rizzo_flow_enabled} onChange={event => update("rizzo_flow_enabled", event.target.checked)} type="checkbox" />Abilita Rizzo Flow locale</label>
      <label>Endpoint Rizzo Flow<input value={settings.rizzo_flow_base_url ?? ""} onChange={event => update("rizzo_flow_base_url", event.target.value)} placeholder="http://localhost:8788" /></label>
    </div>
    <div className="llm-settings-actions"><button className="action-button" disabled={working} onClick={() => void save()} type="button">Salva impostazioni LLM</button><button className="delete-button" disabled={working || paused} onClick={() => void controlJobs("stop")} type="button">Stop tutti i job</button><button className="text-button" disabled={working || !paused} onClick={() => void controlJobs("resume")} type="button">Riprendi job</button><span className={`job-state${paused ? " paused" : ""}`}>{paused ? "Job in pausa" : "Job attivi"}</span></div>
    <p className="feedback" aria-live="polite">{message}</p>
  </section>;
}
