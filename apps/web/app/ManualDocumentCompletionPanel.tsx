"use client";

import { type FormEvent, type ReactElement, useState } from "react";

type Review = { id: string; type: string; entity_id: string };
type DocumentSummary = { id: string; logical_name: string | null; original_filename: string; document_type: string; document_date: string | null; patient_name: string | null; total_amount: string | null; extraction: Record<string, unknown> | null };
type Draft = { document_type: "PRESCRIPTION" | "INVOICE" | "MEDICAL_REPORT"; document_date: string; patient_name: string; service_description: string; total_amount: string; provider_name: string };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const emptyDraft: Draft = { document_type: "MEDICAL_REPORT", document_date: "", patient_name: "", service_description: "", total_amount: "", provider_name: "" };

export function ManualDocumentCompletionPanel({ reviews, documents, onOpenDocument, onCompleted }: { reviews: Review[]; documents: DocumentSummary[]; onOpenDocument: (documentId: string) => void; onCompleted: (reviewId: string) => void }): ReactElement | null {
  const [selectedId, setSelectedId] = useState<string>();
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [message, setMessage] = useState("");
  const manualReviews = reviews.filter(review => review.type === "DOCUMENT_TYPE_UNCERTAIN");
  const selected = manualReviews.find(review => review.id === selectedId);
  const document = selected ? documents.find(item => item.id === selected.entity_id) : undefined;

  if (manualReviews.length === 0) return null;

  function begin(review: Review): void {
    const source = documents.find(item => item.id === review.entity_id);
    setSelectedId(review.id);
    setDraft({
      document_type: source?.document_type === "INVOICE" || source?.document_type === "PRESCRIPTION" || source?.document_type === "MEDICAL_REPORT" ? source.document_type : "MEDICAL_REPORT",
      document_date: source?.document_date ?? "",
      patient_name: source?.patient_name ?? "",
      service_description: "",
      total_amount: source?.total_amount ?? "",
      provider_name: "",
    });
    setMessage("");
    onOpenDocument(review.entity_id);
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selected) return;
    setMessage("Salvataggio dei dati verificati…");
    const payload = { ...draft, total_amount: draft.document_type === "INVOICE" && draft.total_amount ? draft.total_amount : null, provider_name: draft.provider_name || null };
    const response = await fetch(`${API}/api/v1/review-tasks/${selected.id}/complete-manually`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) {
      const body = await response.json() as { detail?: string };
      setMessage(body.detail ?? "Impossibile salvare i dati manuali.");
      return;
    }
    onCompleted(selected.id);
    setSelectedId(undefined);
    setMessage("Dati manuali salvati. Il documento è stato riclassificato.");
  }

  return <section className="manual-completion" aria-label="Completamento manuale documenti">
    <header><p className="eyebrow">ALTERNATIVA ALLA RIELABORAZIONE</p><h3>Completa i dati dal documento originale</h3><p>Usa questa procedura quando l’estrazione locale non riesce: l’originale si apre nell’anteprima e i dati inseriti restano tracciati come inserimento manuale.</p></header>
    <div className="manual-review-list">{manualReviews.map(review => <button className={`manual-review-select${selectedId === review.id ? " selected" : ""}`} key={review.id} onClick={() => begin(review)} type="button">{documents.find(item => item.id === review.entity_id)?.logical_name ?? documents.find(item => item.id === review.entity_id)?.original_filename ?? "Documento rimosso"}<span>Apri originale e completa manualmente</span></button>)}</div>
    {selected && document && <form className="manual-form" onSubmit={event => void submit(event)}>
      <div className="manual-source"><strong>Documento aperto</strong><button className="review-document-link" type="button" onClick={() => onOpenDocument(document.id)}>{document.logical_name ?? document.original_filename}</button><small>Dati disponibili: tipo {document.document_type} · data {document.document_date ?? "non estratta"} · paziente {document.patient_name ?? "non estratto"} · importo {document.total_amount ? `€ ${document.total_amount}` : "non estratto"}</small></div>
      <label>Tipo documento<select value={draft.document_type} onChange={event => setDraft(current => ({ ...current, document_type: event.target.value as Draft["document_type"] }))}><option value="MEDICAL_REPORT">Referto medico</option><option value="PRESCRIPTION">Prescrizione</option><option value="INVOICE">Fattura</option></select></label>
      <label>Data documento<input required type="date" value={draft.document_date} onChange={event => setDraft(current => ({ ...current, document_date: event.target.value }))} /></label>
      <label>Paziente<input required value={draft.patient_name} onChange={event => setDraft(current => ({ ...current, patient_name: event.target.value }))} placeholder="Nome e cognome" /></label>
      <label>Prestazione o contenuto clinico<input required value={draft.service_description} onChange={event => setDraft(current => ({ ...current, service_description: event.target.value }))} placeholder="Es. visita cardiologica" /></label>
      <label>Struttura o professionista<input value={draft.provider_name} onChange={event => setDraft(current => ({ ...current, provider_name: event.target.value }))} placeholder="Opzionale" /></label>
      {draft.document_type === "INVOICE" && <label>Importo totale (€)<input required min="0" step="0.01" type="number" value={draft.total_amount} onChange={event => setDraft(current => ({ ...current, total_amount: event.target.value }))} /></label>}
      <div className="manual-form-actions"><button className="action-button" type="submit">Salva dati manuali</button><p aria-live="polite">{message}</p></div>
    </form>}
  </section>;
}
