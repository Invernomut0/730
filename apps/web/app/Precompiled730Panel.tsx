"use client";

import { type ChangeEvent, type ReactElement, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
type Row = { id: string; amount: string; description: string; status: string };

export function Precompiled730Panel(): ReactElement {
  const [year, setYear] = useState("2026");
  const [rows, setRows] = useState<Row[]>([]);
  const [message, setMessage] = useState("Importa un CSV locale della precompilata.");
  async function refresh(): Promise<void> {
    const response = await fetch(`${API}/api/v1/tax/${year}/reconciliation`);
    if (response.ok) setRows(await response.json() as Row[]);
  }
  async function upload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0]; if (!file) return;
    const form = new FormData(); form.append("file", file);
    const imported = await fetch(`${API}/api/v1/tax/${year}/precompiled/import`, { method: "POST", body: form });
    if (!imported.ok) { setMessage("Importazione non riuscita."); return; }
    await fetch(`${API}/api/v1/tax/${year}/precompiled/reconcile`, { method: "POST" });
    setMessage("Import completato; sono mostrate solo le discrepanze."); await refresh();
  }
  return <section className="panel">
    <div className="panel-title"><div><p className="eyebrow">FISCO</p><h2>Precompilata 730</h2></div><p className="muted">Confronto locale, senza accesso a SPID o CIE.</p></div>
    <div className="tax-controls"><label>Anno<br /><input value={year} onChange={event => setYear(event.target.value)} inputMode="numeric" /></label><input aria-label="Importa CSV precompilata" type="file" accept="text/csv,.csv" onChange={upload} /><button className="action-button" onClick={() => void refresh()}>Aggiorna discrepanze</button></div><p className="feedback" aria-live="polite">{message}</p>
    {rows.length > 0 && <ul className="tax-list">{rows.map(row => <li key={row.id}><strong>€ {row.amount}</strong><span>{row.description}</span><em>{row.status}</em></li>)}</ul>}
  </section>;
}
