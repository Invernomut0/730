"use client";

import { type PointerEvent, type ReactElement, useRef, useState } from "react";

type Document = { id: string; original_filename: string; logical_name: string | null; document_type: string; extraction: Record<string, unknown> | null };
type WordBox = { text: string; left: number; top: number; width: number; height: number };
type DocumentPage = { page_number: number; text: string; blocks: { coordinate_space?: string; words?: WordBox[] } | null };
type Evidence = { value?: unknown };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function evidenceValue(value: unknown): string | undefined {
  if (typeof value === "object" && value !== null) {
    const evidence = (value as Evidence).value;
    if (typeof evidence === "string") return evidence;
  }
  return typeof value === "string" ? value : undefined;
}

function evidenceList(value: unknown, nestedKey?: string): string | undefined {
  if (!Array.isArray(value)) return undefined;
  const values = value.map(item => {
    const nested = nestedKey && typeof item === "object" && item !== null ? (item as Record<string, unknown>)[nestedKey] : item;
    return evidenceValue(nested);
  }).filter((item): item is string => Boolean(item));
  return values.length ? values.join(" · ") : undefined;
}

function laboratoryResultsSummary(value: unknown): string | undefined {
  if (!Array.isArray(value) || value.length === 0) return undefined;
  const entries = value.map(item => {
    if (typeof item !== "object" || item === null) return undefined;
    const result = item as Record<string, unknown>;
    const analyte = evidenceValue(result.analyte);
    const measured = evidenceValue(result.result);
    const unit = evidenceValue(result.unit);
    return analyte ? `${analyte}${measured ? `: ${measured}${unit ? ` ${unit}` : ""}` : ""}` : undefined;
  }).filter((item): item is string => Boolean(item));
  if (!entries.length) return undefined;
  const visible = entries.slice(0, 6);
  return `${visible.join(" · ")}${entries.length > visible.length ? ` · +${entries.length - visible.length} altri` : ""}`;
}

function extractedSummary(document: Document): Array<[string, string]> {
  const extraction = document.extraction;
  if (!extraction) return [["Stato", "Analisi in corso"]];
  const diagnosis = Array.isArray(extraction.diagnosis_evidence)
    ? extraction.diagnosis_evidence.map(item => {
      const entry = item as Record<string, unknown>;
      return entry.kind === "DIAGNOSTIC_QUESTION" ? evidenceValue(entry.evidence) : undefined;
    }).find(Boolean) ?? evidenceList(extraction.diagnosis_evidence, "evidence")
    : evidenceValue(extraction.summary) ?? evidenceList(extraction.clinical_findings);
  const service = evidenceList(extraction.requested_services)
    ?? evidenceList(extraction.requested_visits, "evidence")
    ?? evidenceList(extraction.services, "description")
    ?? evidenceList(extraction.services)
    ?? evidenceList(extraction.laboratory_tests)
    ?? evidenceList(extraction.medications);
  const laboratoryResults = laboratoryResultsSummary(extraction.laboratory_results);
  const reportKind = extraction.report_kind === "LABORATORY_RESULTS" ? "Esami di laboratorio" : undefined;
  const prescribedDrugs = evidenceList(extraction.prescribed_drugs);
  const documentedServices = evidenceList(extraction.documented_services);
  const requestedLabTests = evidenceList(extraction.requested_lab_tests);
  return [
    ["Nome", evidenceValue(extraction.patient) ?? evidenceValue(extraction.patient_name) ?? "Non rilevato"],
    ["Data", String(extraction.document_date ?? extraction.invoice_date ?? extraction.report_date ?? "Non rilevata")],
    ["Quesito diagnostico", diagnosis ?? "Non rilevato"],
    ["Tipologia", document.document_type.replaceAll("_", " ")],
    ...(reportKind ? [["Categoria referto", reportKind] as [string, string]] : []),
    ["Dottore", evidenceValue(extraction.doctor) ?? evidenceValue(extraction.provider) ?? evidenceValue(extraction.provider_name) ?? "Non rilevato"],
    [documentedServices ? "Prestazione documentata" : "Servizio richiesto", documentedServices ?? service ?? (requestedLabTests ? "Esami di laboratorio" : prescribedDrugs ? "Farmaci prescritti" : "Non rilevato")],
    ...(prescribedDrugs ? [["Farmaci prescritti", prescribedDrugs] as [string, string]] : []),
    ...(requestedLabTests ? [["Esami richiesti", requestedLabTests] as [string, string]] : []),
    ...(laboratoryResults ? [["Risultati laboratorio", laboratoryResults] as [string, string]] : []),
  ];
}

export function DocumentViewerLayer({ document, pages, onClose, onDocumentUpdated }: { document: Document | undefined; pages: DocumentPage[]; onClose: () => void; onDocumentUpdated: (document: Document) => void }): ReactElement | null {
  const [position, setPosition] = useState({ x: 28, y: 82 });
  const [selectedWord, setSelectedWord] = useState<WordBox>();
  const [serviceDescription, setServiceDescription] = useState("");
  const [serviceAmount, setServiceAmount] = useState("");
  const [serviceMessage, setServiceMessage] = useState("");
  const [savingService, setSavingService] = useState(false);
  const dragOffset = useRef<{ x: number; y: number } | undefined>(undefined);

  if (!document) return null;
  const documentId = document.id;

  function beginDrag(event: PointerEvent<HTMLDivElement>): void {
    if ((event.target as HTMLElement).closest("button")) return;
    dragOffset.current = { x: event.clientX - position.x, y: event.clientY - position.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function drag(event: PointerEvent<HTMLDivElement>): void {
    if (!dragOffset.current) return;
    setPosition({ x: Math.max(12, event.clientX - dragOffset.current.x), y: Math.max(12, event.clientY - dragOffset.current.y) });
  }

  function endDrag(): void { dragOffset.current = undefined; }

  async function addInvoiceService(): Promise<void> {
    if (!serviceDescription.trim()) return;
    setSavingService(true);
    setServiceMessage("");
    const amount = serviceAmount.trim() ? Number(serviceAmount.replace(",", ".")) : undefined;
    if (amount !== undefined && (!Number.isFinite(amount) || amount < 0)) {
      setSavingService(false);
      setServiceMessage("Inserisci un importo valido oppure lascialo vuoto.");
      return;
    }
    const response = await fetch(`${API}/api/v1/documents/${documentId}/invoice-services`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service_description: serviceDescription.trim(), amount }),
    });
    setSavingService(false);
    if (!response.ok) {
      const body = await response.json() as { detail?: string };
      setServiceMessage(body.detail ?? "Impossibile salvare la prestazione.");
      return;
    }
    onDocumentUpdated(await response.json() as Document);
    setServiceDescription("");
    setServiceAmount("");
    setServiceMessage("Prestazione aggiunta e collegamenti della fattura ricalcolati.");
  }

  return <aside aria-label="Dettaglio documento" className="document-viewer-layer" role="dialog" style={{ left: position.x, top: position.y }}>
    <div className="document-viewer-drag-handle" onPointerDown={beginDrag} onPointerMove={drag} onPointerUp={endDrag} onPointerCancel={endDrag}>
      <div><p className="eyebrow">DOCUMENTO ORIGINALE</p><h3>{document.logical_name ?? document.original_filename}</h3></div>
      <button aria-label="Chiudi dettaglio documento" className="viewer-close" onClick={onClose} type="button">Chiudi</button>
    </div>
    <div className="document-viewer-layer-content">
      <div><div className="viewer-preview-wrap"><img className="viewer-preview" alt={`Anteprima di ${document.logical_name ?? document.original_filename}`} src={`${API}/api/v1/documents/${document.id}/thumbnail`} />{(pages[0]?.blocks?.words ?? []).map((word, index) => <button aria-label={`Mostra dettaglio parola ${word.text}`} className={`word-box${selectedWord === word ? " selected" : ""}`} key={`${word.text}-${index}`} onClick={() => setSelectedWord(word)} style={{ left: `${word.left * 100}%`, top: `${word.top * 100}%`, width: `${word.width * 100}%`, height: `${word.height * 100}%` }} title={word.text} type="button" />)}</div></div>
      <div className="viewer-copy extracted-summary"><header><p className="eyebrow">SINTESI ESTRATTA</p><h3>Dati principali</h3></header><dl>{extractedSummary(document).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{document.document_type === "INVOICE" && <form className="invoice-service-form" onSubmit={event => { event.preventDefault(); void addInvoiceService(); }}><div><p className="eyebrow">CORREZIONE OPERATORE</p><h4>Aggiungi prestazione fattura</h4><p>Usala solo se la prestazione non è stata rilevata o è incompleta.</p></div><label>Prestazione<input aria-label="Prestazione fattura" disabled={savingService} onChange={event => setServiceDescription(event.target.value)} placeholder="Es. visita gastroenterologica" value={serviceDescription} /></label><label>Importo opzionale<input aria-label="Importo prestazione" disabled={savingService} inputMode="decimal" onChange={event => setServiceAmount(event.target.value)} placeholder="0,00" value={serviceAmount} /></label><button className="text-button" disabled={savingService || !serviceDescription.trim()} type="submit">{savingService ? "Salvataggio…" : "Aggiungi prestazione"}</button>{serviceMessage && <p aria-live="polite" className="invoice-service-feedback">{serviceMessage}</p>}</form>}{selectedWord && <div className="word-detail"><strong>{selectedWord.text}</strong><span>Pagina 1 · x {Math.round(selectedWord.left * 100)}% · y {Math.round(selectedWord.top * 100)}%</span></div>}<details><summary>Dettaglio tecnico estrazione</summary><pre>{document.extraction ? JSON.stringify(document.extraction, null, 2) : pages.map(page => page.text).join("\n\n") || "Testo in attesa di estrazione."}</pre></details></div>
    </div>
  </aside>;
}
