"use client";

import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { type ReactElement, useEffect, useState } from "react";

type EventSummary = { id: string; title: string; status: string; confidence: number };
type Graph = { nodes: Array<{ id: string; type: string; label: string; status: string }>; edges: Array<{ id: string; source: string; target: string; type: string; confidence: number; evidence: string[]; conflicts: string[] }> };
type Evaluation = { category: string; status: string; documentation_complete: boolean; estimated_eligible_amount: string; evidence: string[]; missing_documents: string[]; warnings: string[] };
type Review = { id: string; type: string; context: Record<string, unknown>; priority: number };

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function EventWorkspace(): ReactElement {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [graph, setGraph] = useState<Graph>();
  const [evaluation, setEvaluation] = useState<Evaluation>();
  const [reviews, setReviews] = useState<Review[]>([]);

  useEffect(() => { void fetch(`${API}/api/v1/medical-events`).then(async r => { if (r.ok) { const value = await r.json() as EventSummary[]; setEvents(value); setSelectedId(value[0]?.id); } }); void fetch(`${API}/api/v1/review-tasks`).then(async r => { if (r.ok) setReviews(await r.json() as Review[]); }); }, []);
  useEffect(() => { if (!selectedId) return; void Promise.all([fetch(`${API}/api/v1/medical-events/${selectedId}/graph`), fetch(`${API}/api/v1/medical-events/${selectedId}/insurance-evaluation`)]).then(async ([graphResponse, evaluationResponse]) => { if (graphResponse.ok) setGraph(await graphResponse.json() as Graph); if (evaluationResponse.ok) setEvaluation(await evaluationResponse.json() as Evaluation); }); }, [selectedId]);

  async function resolve(review: Review): Promise<void> {
    const response = await fetch(`${API}/api/v1/review-tasks/${review.id}/resolve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resolution: { action: "acknowledged_in_workspace" } }) });
    if (response.ok) setReviews(current => current.filter(item => item.id !== review.id));
  }

  const nodes: Node[] = (graph?.nodes ?? []).map((node, index) => ({ id: node.id, position: { x: node.type === "medical_event" ? 280 : 40 + index * 260, y: node.type === "medical_event" ? 120 : 300 }, data: { label: `${node.label} · ${node.status}` }, style: { border: "1px solid #93a7a0", borderRadius: 4, padding: 10, background: node.type === "medical_event" ? "#dce9df" : "#fffdf9", color: "#172335", fontFamily: "Baskerville, serif" } }));
  const edges: Edge[] = (graph?.edges ?? []).map(edge => ({ id: edge.id, source: edge.source, target: edge.target, label: `${Math.round(edge.confidence * 100)}%`, animated: edge.conflicts.length === 0 }));

  return <section className="panel">
    <div className="panel-title"><div><p className="eyebrow">RELAZIONI CLINICHE</p><h2>Medical Event workspace</h2></div><select aria-label="Seleziona evento" value={selectedId ?? ""} onChange={event => setSelectedId(event.target.value)}><option value="">Nessun evento</option>{events.map(event => <option key={event.id} value={event.id}>{event.title} · {Math.round(event.confidence * 100)}%</option>)}</select></div>
    {!selectedId ? <p className="muted">Un evento compare qui dopo un collegamento verificato tra prescrizione e fattura.</p> : <div className="workspace-grid">
      <aside className="workspace-aside"><strong>Documenti</strong><p>Le relazioni sono create solo con evidenze e senza conflitti maggiori.</p></aside>
      <div className="flow-canvas"><ReactFlow nodes={nodes} edges={edges} fitView><Background /><Controls /></ReactFlow></div>
      <aside className="workspace-aside"><strong>Assicurazione</strong>{evaluation && <><p>{evaluation.status === "candidate" ? "Candidata al rimborso" : "Da verificare"}</p><p>Documentazione {evaluation.documentation_complete ? "apparentemente completa" : "incompleta"}</p><p>Stima: € {evaluation.estimated_eligible_amount}</p>{evaluation.missing_documents.map(item => <p key={item}>Manca: {item}</p>)}</>}</aside>
    </div>}
    <section className="review-queue"><strong>Review queue</strong>{reviews.length === 0 ? <p className="muted">Nessuna revisione aperta.</p> : reviews.map(review => <div key={review.id} className="review-item"><span>{review.type} · priorità {review.priority}</span><button className="text-button" onClick={() => void resolve(review)}>Segna come risolta</button></div>)}</section>
  </section>;
}
