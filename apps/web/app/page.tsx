"use client";

import { ChangeEvent, useEffect, useState } from "react";

type Document = {
  id: string;
  original_filename: string;
  mime_type: string;
  byte_size: number;
  state: string;
  document_type: string;
  duplicate_of_id: string | null;
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [message, setMessage] = useState("Carica una prescrizione o fattura per iniziare.");
  const [uploading, setUploading] = useState(false);

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

  return <main style={{ fontFamily: "Inter, system-ui, sans-serif", maxWidth: 1180, margin: "0 auto", padding: 32, color: "#172033" }}>
    <header style={{ borderBottom: "1px solid #e4e8ef", paddingBottom: 24, display: "flex", justifyContent: "space-between" }}>
      <div><p style={{ color: "#5c6b82", letterSpacing: 1.5, fontSize: 12, fontWeight: 700 }}>HEALTHDOCS 730 · LOCAL-FIRST</p><h1 style={{ margin: "6px 0" }}>Inbox documenti</h1><p style={{ margin: 0, color: "#5c6b82" }}>Originali immutabili, decisioni spiegabili.</p></div>
      <nav aria-label="Navigazione principale" style={{ color: "#5c6b82", alignSelf: "center" }}>Inbox · Medical Events · Insurance · 730 · Review · Family · Settings</nav>
    </header>
    <section style={{ marginTop: 32, padding: 28, border: "1px dashed #97a6bd", borderRadius: 12, background: "#f8fafc" }}>
      <h2 style={{ marginTop: 0 }}>Aggiungi un documento</h2><p>{message}</p>
      <label style={{ display: "inline-block", background: "#155eef", color: "white", padding: "10px 16px", borderRadius: 8, cursor: uploading ? "wait" : "pointer" }}>
        {uploading ? "Caricamento…" : "Scegli PDF, PNG o JPEG"}<input aria-label="Carica documento" type="file" accept="application/pdf,image/png,image/jpeg" onChange={upload} disabled={uploading} hidden />
      </label>
    </section>
    <section style={{ marginTop: 32 }}><h2>Documenti elaborati</h2>
      <div style={{ border: "1px solid #e4e8ef", borderRadius: 12, overflow: "hidden" }}>
        {documents.length === 0 ? <p style={{ padding: 20, color: "#5c6b82" }}>Nessun documento caricato.</p> : documents.map((document) => <article key={document.id} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 16, padding: 18, borderBottom: "1px solid #e4e8ef" }}>
          <strong>{document.original_filename}{document.duplicate_of_id ? " · duplicato rilevato" : ""}</strong><span>{document.document_type}</span><span>{document.state}</span><span>{Math.ceil(document.byte_size / 1024)} KB</span>
        </article>)}
      </div>
    </section>
  </main>;
}
