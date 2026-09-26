"use client";

import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { type ReactElement, useEffect, useState } from "react";

import { ManualDocumentCompletionPanel } from "./ManualDocumentCompletionPanel";
import { AssociationControls } from "./AssociationControls";

type EventSummary = { id: string; title: string; status: string; confidence: number };
type Graph = { nodes: Array<{ id: string; type: string; label: string; status: string }>; edges: Array<{ id: string; source: string; target: string; type: string; confidence: number; evidence: string[]; conflicts: string[] }> };
type Evaluation = { category: string; status: string; documentation_complete: boolean; documented_amount: string; estimated_eligible_amount: string; estimate_basis: string; evidence: string[]; missing_documents: string[]; warnings: string[] };
type Review = { id: string; type: string; entity_id: string; context: Record<string, unknown>; priority: number };
type DocumentSummary = { id: string; logical_name: string | null; original_filename: string; document_type: string; patient_name: string | null; document_date: string | null; total_amount: string | null; extraction: Record<string, unknown> | null };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function EventWorkspace({ onOpenDocument }: { onOpenDocument: (documentId: string) => void }): ReactElement {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [approvedEvents, setApprovedEvents] = useState<EventSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [graph, setGraph] = useState<Graph>();
  const [evaluation, setEvaluation] = useState<Evaluation>();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);

  useEffect(() => { void Promise.all([fetch(`${API}/api/v1/medical-events?status=PROPOSED`), fetch(`${API}/api/v1/medical-events?status=CONFIRMED`)]).then(async ([proposedResponse, approvedResponse]) => { if (proposedResponse.ok) { const value = await proposedResponse.json() as EventSummary[]; setEvents(value); setSelectedId(value[0]?.id); } if (approvedResponse.ok) setApprovedEvents(await approvedResponse.json() as EventSummary[]); }); void fetch(`${API}/api/v1/review-tasks`).then(async r => { if (r.ok) setReviews(await r.json() as Review[]); }); void fetch(`${API}/api/v1/documents`).then(async r => { if (r.ok) setDocuments(await r.json() as DocumentSummary[]); }); }, []);
  useEffect(() => { if (!selectedId) return; void Promise.all([fetch(`${API}/api/v1/medical-events/${selectedId}/graph`), fetch(`${API}/api/v1/medical-events/${selectedId}/insurance-evaluation`)]).then(async ([graphResponse, evaluationResponse]) => { if (graphResponse.ok) setGraph(await graphResponse.json() as Graph); if (evaluationResponse.ok) setEvaluation(await evaluationResponse.json() as Evaluation); }); }, [selectedId]);

  async function resolve(review: Review, action: string): Promise<void> {
    const response = await fetch(`${API}/api/v1/review-tasks/${review.id}/resolve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resolution: { action } }) });
    if (response.ok) setReviews(current => current.filter(item => item.id !== review.id));
  }

  async function retry(review: Review): Promise<void> {
    const response = await fetch(`${API}/api/v1/review-tasks/${review.id}/retry`, { method: "POST" });
    if (response.ok) setReviews(current => current.filter(item => item.id !== review.id));
  }

  function documentLabel(id: string): string { const document = documents.find(item => item.id === id); return document ? document.logical_name ?? document.original_filename : "Documento rimosso"; }
  function signalLabel(value: string): string { if (value === "same_patient") return "Stesso paziente"; if (value === "service_matches_prescription") return "Prestazione coerente"; if (value === "different_patient") return "Paziente diverso"; if (value === "invoice_before_prescription") return "Fattura precedente alla prescrizione"; const days = value.match(/^invoice_(\d+)_days_after_prescription$/); return days ? `Fattura ${days[1]} giorni dopo` : value; }
  function extractedText(value: unknown): string | undefined { return value && typeof value === "object" && "value" in value && typeof value.value === "string" ? value.value : undefined; }
  function extractedServices(document: DocumentSummary | undefined): string[] {
    if (!document?.extraction) return [];
    if (document.document_type === "PRESCRIPTION") return Array.isArray(document.extraction.requested_services) ? document.extraction.requested_services.map(extractedText).filter((value): value is string => Boolean(value)) : [];
    if (document.document_type === "INVOICE") return Array.isArray(document.extraction.services) ? document.extraction.services.map(service => extractedText(service && typeof service === "object" && "description" in service ? service.description : undefined)).filter((value): value is string => Boolean(value)) : [];
    return [];
  }
  function documentTypeLabel(document: DocumentSummary | undefined): string { if (document?.document_type === "PRESCRIPTION") return "Prescrizione"; if (document?.document_type === "INVOICE") return "Fattura"; return document?.document_type ?? "Documento"; }

  const nodes: Node[] = (graph?.nodes ?? []).map((node, index) => ({ id: node.id, position: { x: node.type === "medical_event" ? 280 : 40 + index * 260, y: node.type === "medical_event" ? 120 : 300 }, data: { label: `${node.label} · ${node.status}`, documentId: node.type === "document" ? node.id : undefined }, style: { border: "1px solid #93a7a0", borderRadius: 4, padding: 10, background: node.type === "medical_event" ? "#dce9df" : "#fffdf9", color: "#172335", cursor: node.type === "document" ? "pointer" : "default", fontFamily: "Baskerville, serif" } }));
  const edges: Edge[] = (graph?.edges ?? []).map(edge => ({ id: edge.id, source: edge.source, target: edge.target, label: `${Math.round(edge.confidence * 100)}%`, animated: edge.conflicts.length === 0 }));

  const selectedEvent = events.find(event => event.id === selectedId) ?? approvedEvents.find(event => event.id === selectedId);

  return <section className="panel">
    <div className="panel-title"><div><p className="eyebrow">RELAZIONI CLINICHE</p><h2>Medical Event workspace</h2></div><select aria-label="Seleziona evento" value={selectedId ?? ""} onChange={event => setSelectedId(event.target.value)}><option value="">Nessun evento</option>{events.map(event => <option key={event.id} value={event.id}>{event.title} · {Math.round(event.confidence * 100)}%</option>)}</select></div>
    <AssociationControls event={selectedEvent} onApproved={event => { setEvents(current => current.filter(item => item.id !== event.id)); setApprovedEvents(current => [event, ...current]); setSelectedId(undefined); setGraph(undefined); setEvaluation(undefined); }} onRejected={() => { setEvents(current => current.filter(event => event.id !== selectedId)); setSelectedId(undefined); setGraph(undefined); setEvaluation(undefined); }} onRebuilt={() => window.location.reload()} />
    <section className="approved-relations" aria-label="Relazioni approvate"><div><p className="eyebrow">ARCHIVIO CONFERMATO</p><h3>Relazioni approvate</h3></div>{approvedEvents.length === 0 ? <p className="muted">Nessuna relazione approvata.</p> : <ul>{approvedEvents.map(event => <li key={event.id}><button className="approved-relation" onClick={() => setSelectedId(event.id)} type="button"><span>{event.title}</span><small>{Math.round(event.confidence * 100)}% · Apri grafo</small></button></li>)}</ul>}</section>
    {!selectedId ? <p className="muted">Un evento compare qui dopo un collegamento verificato tra prescrizione e fattura.</p> : <div className="workspace-grid">
      <aside className="workspace-aside"><strong>Documenti</strong><p>Le relazioni sono create solo con evidenze e senza conflitti maggiori.</p></aside>
      <div className="flow-canvas"><ReactFlow nodes={nodes} edges={edges} fitView onNodeClick={(_, node) => { const documentId = node.data.documentId; if (typeof documentId === "string") onOpenDocument(documentId); }}><Background /><Controls /></ReactFlow></div>
      <aside className="workspace-aside"><strong>Assicurazione</strong>{evaluation && <><p>{evaluation.status === "candidate" ? "Candidata al rimborso" : "Da verificare"}</p><p>Documentazione {evaluation.documentation_complete ? "apparentemente completa" : "incompleta"}</p><p>Spesa documentata: € {evaluation.documented_amount}</p><p>Rimborso stimato: {evaluation.warnings.some(item => item.includes("Invoice total is unavailable")) ? "non disponibile" : `€ ${evaluation.estimated_eligible_amount}`}</p><p className="muted">{evaluation.estimate_basis}</p>{evaluation.missing_documents.map(item => <p key={item}>Manca: {item}</p>)}{evaluation.warnings.map(item => <p className="muted" key={item}>{item}</p>)}</>}</aside>
    </div>}
    <ManualDocumentCompletionPanel reviews={reviews} documents={documents} onOpenDocument={onOpenDocument} onCompleted={reviewId => setReviews(current => current.filter(review => review.id !== reviewId))} />
    <section className="review-queue"><strong>Review queue</strong>{reviews.length === 0 ? <p className="muted">Nessuna revisione aperta.</p> : reviews.map(review => { const candidateId = typeof review.context.candidate_document_id === "string" ? review.context.candidate_document_id : ""; const evidence = Array.isArray(review.context.evidence) ? review.context.evidence.filter((item): item is string => typeof item === "string") : []; const conflicts = Array.isArray(review.context.conflicts) ? review.context.conflicts.filter((item): item is string => typeof item === "string") : []; const identityEvidence = Array.isArray(review.context.resolution_evidence) ? review.context.resolution_evidence.filter((item): item is string => typeof item === "string") : []; const score = typeof review.context.score === "number" ? review.context.score : 0; const sourceAvailable = documents.some(document => document.id === review.entity_id); const candidateAvailable = documents.some(document => document.id === candidateId); const isIdentityConflict = review.type === "PATIENT_CONFLICT"; const isLinkReview = review.type === "LINK_AMBIGUOUS"; const isClassificationReview = review.type === "DOCUMENT_TYPE_UNCERTAIN"; const canResolveLink = sourceAvailable && candidateAvailable; return <div key={review.id} className="review-item"><div className="review-copy"><strong>{isIdentityConflict ? "Identità paziente da verificare" : isClassificationReview ? "Classificazione da completare" : "Collegamento proposto"}</strong>{isIdentityConflict ? <><p><button className="review-document-link" disabled={!sourceAvailable} onClick={() => onOpenDocument(review.entity_id)}>{documentLabel(review.entity_id)}</button></p><p>Il nome ha un solo riscontro in famiglia, ma il codice fiscale stampato non coincide.</p><div className="review-signals">{identityEvidence.map(item => <span className={`review-signal${item === "unmatched_fiscal_code" ? " conflict" : ""}`} key={item}>{item === "reversed_full_name" ? "Nome e cognome invertiti" : item === "unmatched_fiscal_code" ? "Codice fiscale discordante" : item}</span>)}</div></> : isClassificationReview ? <><p><button className="review-document-link" disabled={!sourceAvailable} onClick={() => onOpenDocument(review.entity_id)}>{documentLabel(review.entity_id)}</button></p><p>L'estrazione locale non ha prodotto una classificazione utilizzabile. Apri l'originale, quindi riprova l'elaborazione locale.</p></> : <><p><button className="review-document-link" disabled={!sourceAvailable} onClick={() => onOpenDocument(review.entity_id)}>{documentLabel(review.entity_id)}</button> ↔ <button className="review-document-link" disabled={!candidateAvailable} onClick={() => onOpenDocument(candidateId)}>{documentLabel(candidateId)}</button></p><p>Apri entrambi i documenti e verifica le evidenze prima di decidere.</p><p>Confidenza {Math.round(score * 100)}% · priorità {review.priority}</p><div className="review-signals">{evidence.map(item => <span className="review-signal" key={item}>{signalLabel(item)}</span>)}{conflicts.map(item => <span className="review-signal conflict" key={item}>{signalLabel(item)}</span>)}</div></>}</div><div className="review-actions">{isClassificationReview ? <button className="text-button" disabled={!sourceAvailable} onClick={() => void retry(review)}>Riprova elaborazione</button> : isLinkReview ? <><button className="text-button" disabled={!canResolveLink} onClick={() => { if (window.confirm("Creare un episodio di cura con questi due documenti?")) void resolve(review, "confirmed_related"); }}>Crea episodio</button><button className="text-button reject" disabled={!canResolveLink} onClick={() => void resolve(review, "rejected_unrelated")}>Non sono collegati</button></> : <button className="text-button" onClick={() => void resolve(review, "acknowledged_identity_conflict")}>Conferma identità</button>}</div></div>; })}</section>
    <section className="review-explanations" aria-label="Dettaglio dei collegamenti proposti">
      {reviews.filter(review => review.type === "LINK_AMBIGUOUS").map(review => {
        const candidateId = typeof review.context.candidate_document_id === "string" ? review.context.candidate_document_id : "";
        const source = documents.find(document => document.id === review.entity_id);
        const candidate = documents.find(document => document.id === candidateId);
        const prescription = source?.document_type === "PRESCRIPTION" ? source : candidate?.document_type === "PRESCRIPTION" ? candidate : undefined;
        const invoice = source?.document_type === "INVOICE" ? source : candidate?.document_type === "INVOICE" ? candidate : undefined;
        const evidence = Array.isArray(review.context.evidence) ? review.context.evidence.filter((item): item is string => typeof item === "string") : [];
        const prescriptionServices = extractedServices(prescription);
        const invoiceServices = extractedServices(invoice);
        return <article key={`detail-${review.id}`} className="review-explanation">
          <header><p className="eyebrow">COLLEGAMENTO DA VERIFICARE</p><h3>Prestazione e basi del match</h3></header>
          <div className="review-document-details">
            {[prescription, invoice].map(document => document && <div className="review-document-detail" key={document.id}>
              <span className="review-detail-type">{documentTypeLabel(document)}</span>
              <button className="review-document-link" onClick={() => onOpenDocument(document.id)}>{document.logical_name ?? document.original_filename}</button>
              <dl><div><dt>Data</dt><dd>{document.document_date ?? "Non estratta"}</dd></div><div><dt>Paziente</dt><dd>{document.patient_name ?? "Non estratto"}</dd></div>{document.total_amount && <div><dt>Importo</dt><dd>€ {document.total_amount}</dd></div>}</dl>
              <p><span>Prestazione {document.document_type === "PRESCRIPTION" ? "prescritta" : "fatturata"}</span>{(document.document_type === "PRESCRIPTION" ? prescriptionServices : invoiceServices).join(" · ") || "Non estratta"}</p>
            </div>)}
          </div>
          <div className="review-match-details"><strong>Dati che fanno corrispondere il legame</strong><div className="review-signals">{evidence.map(item => <span className="review-signal" key={item}>{signalLabel(item)}</span>)}</div></div>
          <div className="review-destinations"><div><strong>Assicurazione</strong><span>Non proposta: sarà valutata solo dopo la creazione dell’episodio.</span></div><div><strong>730</strong><span>Non proposta: la fattura sarà valutata nel flusso fiscale dopo la verifica.</span></div></div>
        </article>;
      })}
    </section>
  </section>;
}
