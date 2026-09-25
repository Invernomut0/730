"use client";

import { ChangeEvent, useEffect, useState } from "react";

import { EventWorkspace } from "./EventWorkspace";
import { FamilyPanel } from "./FamilyPanel";
import { Precompiled730Panel } from "./Precompiled730Panel";

type Document = {
  id: string;
  original_filename: string;
  logical_name: string | null;
  mime_type: string;
  byte_size: number;
  state: string;
  document_type: string;
  duplicate_of_id: string | null;
  patient_name: string | null;
  document_date: string | null;
  total_amount: string | null;
  extraction: Record<string, unknown> | null;
};
type DocumentPage = { page_number: number; text: string; blocks: { words?: { text: string }[] } | null };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>();
  const [message, setMessage] = useState("Carica una prescrizione o fattura per iniziare.");
  const [uploading, setUploading] = useState(false);
  const [pages, setPages] = useState<DocumentPage[]>([]);

  async function refresh(): Promise<void> {
    const response = await fetch(`${API}/api/v1/documents`);
    if (response.ok) setDocuments(await response.json() as Document[]);
  }
  useEffect(() => { void refresh(); }, []);

  async function upload(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage("Upload e verifica dell'originale immutabile…");
    const form = new FormData(); form.append("file", file);
    const response = await fetch(`${API}/api/v1/documents`, { method: "POST", body: form });
    setUploading(false);
    if (!response.ok) { setMessage(`Upload non riuscito: ${(await response.json()).detail}`); return; }
    setMessage("Documento memorizzato e inviato alla pipeline locale.");
    await refresh();
  }
  async function selectDocument(id: string): Promise<void> {
    setSelectedDocumentId(id);
    const response = await fetch(`${API}/api/v1/documents/${id}/pages`);
    setPages(response.ok ? await response.json() as DocumentPage[] : []);
  }

  return <main className="app-shell">
    <header className="masthead">
      <div className="monogram" aria-hidden="true">730</div>
      <div><p className="eyebrow">HEALTHDOCS · ARCHIVIO LOCALE</p><h1>Inbox documenti</h1><p className="masthead-subtitle">Originali immutabili. Decisioni spiegabili. Una storia clinica leggibile.</p></div>
      <nav aria-label="Navigazione principale" className="top-nav">Inbox · Medical Events · Insurance · 730 · Review · Family · Settings</nav>
    </header>
    <section className="upload-card">
      <div><p className="eyebrow">NUOVO DOCUMENTO</p><h2>Aggiungi al dossier</h2><p>{message}</p></div>
      <label className="upload-action" aria-busy={uploading}>
        {uploading ? "Caricamento…" : "Scegli documento"}<input aria-label="Carica documento" type="file" accept="application/pdf,image/png,image/jpeg,image/tiff,image/heic" onChange={upload} disabled={uploading} hidden />
      </label>
    </section>
    <section><div className="section-heading"><h2>Documenti elaborati</h2><p className="section-kicker">{documents.length} nel dossier</p></div>
      <div className="document-list">
        {documents.length === 0 ? <p className="empty-state">Nessun documento caricato.</p> : documents.map((document) => <article key={document.id} className="document-row">
          <button onClick={() => void selectDocument(document.id)} className="document-name"><strong>{document.logical_name ?? document.original_filename}{document.duplicate_of_id ? " · duplicato rilevato" : ""}</strong><small>{document.patient_name ?? "Paziente da risolvere"} · {document.document_date ?? "Data da estrarre"}</small></button><span className="document-meta">{document.document_type}</span><span className="document-meta document-state">{document.state}</span><span className="document-meta">{document.total_amount ? `€ ${document.total_amount}` : `${Math.ceil(document.byte_size / 1024)} KB`}</span>
        </article>)}
      </div>
      {documents.find(item => item.id === selectedDocumentId) && <section className="panel viewer"><div><h3>Anteprima originale</h3><img className="viewer-preview" alt="Anteprima documento" src={`${API}/api/v1/documents/${selectedDocumentId}/thumbnail`} /></div><div className="viewer-copy"><h3>Campi estratti</h3><p>{pages.flatMap(page => page.blocks?.words ?? []).map(word => word.text).join(" · ") || "Bounding box OCR non ancora disponibili."}</p><pre>{JSON.stringify(documents.find(item => item.id === selectedDocumentId)?.extraction ?? { status: "In attesa di estrazione strutturata" }, null, 2)}</pre></div></section>}
    </section>
    <FamilyPanel />
    <Precompiled730Panel />
    <EventWorkspace />
  </main>;
}
