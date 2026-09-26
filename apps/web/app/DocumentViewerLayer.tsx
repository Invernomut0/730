"use client";

import { type PointerEvent, type ReactElement, useRef, useState } from "react";

type Document = { id: string; original_filename: string; logical_name: string | null; extraction: Record<string, unknown> | null };
type WordBox = { text: string; left: number; top: number; width: number; height: number };
type DocumentPage = { page_number: number; text: string; blocks: { coordinate_space?: string; words?: WordBox[] } | null };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function DocumentViewerLayer({ document, pages, onClose }: { document: Document | undefined; pages: DocumentPage[]; onClose: () => void }): ReactElement | null {
  const [position, setPosition] = useState({ x: 28, y: 82 });
  const [selectedWord, setSelectedWord] = useState<WordBox>();
  const dragOffset = useRef<{ x: number; y: number } | undefined>(undefined);

  if (!document) return null;

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

  return <aside aria-label="Dettaglio documento" className="document-viewer-layer" role="dialog" style={{ left: position.x, top: position.y }}>
    <div className="document-viewer-drag-handle" onPointerDown={beginDrag} onPointerMove={drag} onPointerUp={endDrag} onPointerCancel={endDrag}>
      <div><p className="eyebrow">DOCUMENTO ORIGINALE</p><h3>{document.logical_name ?? document.original_filename}</h3></div>
      <button aria-label="Chiudi dettaglio documento" className="viewer-close" onClick={onClose} type="button">Chiudi</button>
    </div>
    <div className="document-viewer-layer-content">
      <div><div className="viewer-preview-wrap"><img className="viewer-preview" alt={`Anteprima di ${document.logical_name ?? document.original_filename}`} src={`${API}/api/v1/documents/${document.id}/thumbnail`} />{(pages[0]?.blocks?.words ?? []).map((word, index) => <button aria-label={`Mostra dettaglio parola ${word.text}`} className={`word-box${selectedWord === word ? " selected" : ""}`} key={`${word.text}-${index}`} onClick={() => setSelectedWord(word)} style={{ left: `${word.left * 100}%`, top: `${word.top * 100}%`, width: `${word.width * 100}%`, height: `${word.height * 100}%` }} title={word.text} type="button" />)}</div></div>
      <div className="viewer-copy"><h3>{document.extraction ? "Campi estratti o inseriti" : "Testo estratto"}</h3><p>{pages[0]?.blocks?.words?.length ? `${pages[0].blocks.words.length} parole mappate sull'anteprima.` : "Coordinate delle parole non ancora disponibili."}</p>{selectedWord && <div className="word-detail"><strong>{selectedWord.text}</strong><span>Pagina 1 · x {Math.round(selectedWord.left * 100)}% · y {Math.round(selectedWord.top * 100)}%</span></div>}<pre>{document.extraction ? JSON.stringify(document.extraction, null, 2) : pages.map(page => page.text).join("\n\n") || "Testo in attesa di estrazione."}</pre></div>
    </div>
  </aside>;
}
