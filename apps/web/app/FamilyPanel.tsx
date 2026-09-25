"use client";

import { type FormEvent, type ReactElement, useEffect, useState } from "react";

type Member = { id: string; first_name: string; last_name: string; fiscal_code: string | null; relationship_type: string | null };
type Household = { id: string; name: string; members: Member[] };
const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function FamilyPanel(): ReactElement {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [householdName, setHouseholdName] = useState("");
  const [member, setMember] = useState({ household_id: "", first_name: "", last_name: "", fiscal_code: "", relationship_type: "" });
  const [message, setMessage] = useState("");

  async function refresh(): Promise<void> { const response = await fetch(`${API}/api/v1/households`); if (response.ok) { const value = await response.json() as Household[]; setHouseholds(value); setMember(current => ({ ...current, household_id: current.household_id || value[0]?.id || "" })); } }
  useEffect(() => { void refresh(); }, []);

  async function createHousehold(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const response = await fetch(`${API}/api/v1/households`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: householdName }) });
    if (!response.ok) { setMessage("Impossibile creare la famiglia."); return; }
    setHouseholdName(""); setMessage("Famiglia creata."); await refresh();
  }
  async function createMember(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const response = await fetch(`${API}/api/v1/household-members`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...member, fiscal_code: member.fiscal_code || null, relationship_type: member.relationship_type || null }) });
    if (!response.ok) { const error = await response.json() as { detail?: string }; setMessage(error.detail ?? "Impossibile creare il membro."); return; }
    setMember(current => ({ ...current, first_name: "", last_name: "", fiscal_code: "", relationship_type: "" })); setMessage("Membro aggiunto."); await refresh();
  }

  return <section style={{ marginTop: 32, border: "1px solid #e4e8ef", borderRadius: 12, padding: 20 }}>
    <h2>Famiglia</h2><p style={{ color: "#5c6b82" }}>Paziente, pagatore e intestatario fiscale restano distinti.</p><p>{message}</p>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
      <form onSubmit={createHousehold}><label>Nome famiglia<br /><input value={householdName} onChange={event => setHouseholdName(event.target.value)} required /></label><button type="submit">Crea famiglia</button></form>
      <form onSubmit={createMember} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><select aria-label="Famiglia" value={member.household_id} onChange={event => setMember(current => ({ ...current, household_id: event.target.value }))} required><option value="">Scegli famiglia</option>{households.map(household => <option key={household.id} value={household.id}>{household.name}</option>)}</select><input placeholder="Nome" value={member.first_name} onChange={event => setMember(current => ({ ...current, first_name: event.target.value }))} required /><input placeholder="Cognome" value={member.last_name} onChange={event => setMember(current => ({ ...current, last_name: event.target.value }))} required /><input placeholder="Codice fiscale (opzionale)" value={member.fiscal_code} onChange={event => setMember(current => ({ ...current, fiscal_code: event.target.value }))} /><input placeholder="Relazione" value={member.relationship_type} onChange={event => setMember(current => ({ ...current, relationship_type: event.target.value }))} /><button type="submit">Aggiungi membro</button></form>
    </div>
    {households.map(household => <div key={household.id} style={{ marginTop: 16 }}><strong>{household.name}</strong>{household.members.length === 0 ? <p>Nessun membro.</p> : <ul>{household.members.map(item => <li key={item.id}>{item.first_name} {item.last_name} · {item.relationship_type ?? "relazione non indicata"}</li>)}</ul>}</div>)}
  </section>;
}
