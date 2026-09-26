"use client";

import { type ReactElement, useState } from "react";

type EventSummary = { id: string; title: string; status: string; confidence: number };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function AssociationControls({ event, onApproved, onRejected, onRebuilt }: { event: EventSummary | undefined; onApproved: (event: EventSummary) => void; onRejected: () => void; onRebuilt: () => void }): ReactElement {
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  async function decide(action: "approve" | "reject"): Promise<void> {
    if (!event) return;
    if (action === "reject" && !reason.trim()) { setMessage("Spiega perché l’associazione è errata prima di rifiutarla."); return; }
    setWorking(true);
    const response = await fetch(`${API}/api/v1/medical-events/${event.id}/association`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, reason: action === "reject" ? reason : null }) });
    setWorking(false);
    if (!response.ok) { const body = await response.json() as { detail?: string }; setMessage(body.detail ?? "Impossibile registrare la decisione."); return; }
    const result = await response.json() as EventSummary;
    setReason("");
    setMessage(action === "approve" ? "Associazione approvata e confermata." : "Associazione rifiutata. La coppia non sarà più proposta automaticamente.");
    if (action === "approve") onApproved(result); else onRejected();
  }

  async function rebuild(): Promise<void> {
    if (!window.confirm("Ricostruire da zero tutte le associazioni proposte? Le associazioni confermate e i rifiuti motivati resteranno invariati.")) return;
    setWorking(true);
    const response = await fetch(`${API}/api/v1/medical-events/rebuild-associations`, { method: "POST" });
    setWorking(false);
    if (!response.ok) { setMessage("Impossibile ricostruire le associazioni."); return; }
    setMessage("Proposte ricostruite dai documenti disponibili.");
    onRebuilt();
  }

  return <section className="association-controls" aria-label="Decisioni associazione">
    <div><p className="eyebrow">CONTROLLO ASSOCIAZIONI</p><h3>Verifica la proposta corrente</h3><p>{event ? `${event.title} · ${Math.round(event.confidence * 100)}% · ${event.status}` : "Seleziona un episodio per approvare o rifiutare la sua associazione."}</p></div>
    <div className="association-actions"><button className="text-button" disabled={working} onClick={() => void rebuild()} type="button">Rifai le proposte da zero</button>{event && event.status === "PROPOSED" && <><button className="action-button" disabled={working} onClick={() => void decide("approve")} type="button">Approva associazione</button><label>Motivo del rifiuto<textarea disabled={working} value={reason} onChange={item => setReason(item.target.value)} placeholder="Es. prestazione diversa, paziente errato, documento non pertinente" rows={2} /></label><button className="text-button reject" disabled={working || !reason.trim()} onClick={() => void decide("reject")} type="button">Rifiuta associazione</button></>}</div>
    <p aria-live="polite" className="association-feedback">{message}</p>
  </section>;
}
