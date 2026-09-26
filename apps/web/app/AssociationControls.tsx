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
    if (!window.confirm("Eliminare tutte le relazioni e ricostruirle dagli estratti già completati? I documenti non verranno rianalizzati.")) return;
    setWorking(true);
    const response = await fetch(`${API}/api/v1/medical-events/rebuild-associations`, { method: "POST" });
    setWorking(false);
    if (!response.ok) { setMessage("Impossibile ricostruire le associazioni."); return; }
    const result = await response.json() as { documents_rebuilt: number; relationships_created: number; review_tasks_created: number };
    setMessage(result.relationships_created || result.review_tasks_created
      ? `Ricostruite ${result.relationships_created} relazioni e create ${result.review_tasks_created} proposte di revisione da ${result.documents_rebuilt} estratti già presenti.`
      : `Nessuna relazione sicura tra i ${result.documents_rebuilt} estratti già presenti: i documenti non sono stati modificati né rianalizzati.`);
    onRebuilt();
  }

  return <section className="association-controls" aria-label="Decisioni associazione">
    <div><p className="eyebrow">CONTROLLO ASSOCIAZIONI</p><h3>Verifica la proposta corrente</h3><p>{event ? `${event.title} · ${Math.round(event.confidence * 100)}% · ${event.status}` : "Seleziona un episodio per approvare o rifiutare la sua associazione."}</p></div>
    <div className="association-actions"><button className="text-button" disabled={working} onClick={() => void rebuild()} type="button">Rifai le relazioni da zero</button>{event && event.status === "PROPOSED" && <><button className="action-button" disabled={working} onClick={() => void decide("approve")} type="button">Approva associazione</button><label>Motivo del rifiuto<textarea disabled={working} value={reason} onChange={item => setReason(item.target.value)} placeholder="Es. prestazione diversa, paziente errato, documento non pertinente" rows={2} /></label><button className="text-button reject" disabled={working || !reason.trim()} onClick={() => void decide("reject")} type="button">Rifiuta associazione</button></>}</div>
    <p aria-live="polite" className="association-feedback">{message}</p>
  </section>;
}
