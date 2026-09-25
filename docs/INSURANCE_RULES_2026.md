# Insurance Rules 2026

Basis: uploaded **Piano Sanitario 2026.pdf**. This design transcription does not replace contract/policy conditions; the manual itself says it is informational.

## Event model
The plan describes one request per event/cycle of care relating to the same illness/injury, including all associated expenses. Model as `MedicalEvent -> InsuranceClaim`.

## Key categories captured for implementation
### Hospitalization / surgery
Annual household maximum EUR 300,000. General 15% coinsurance with stated cap; outpatient surgery and direct-network paths have specific handling. Ticket reimbursement 100%. Pre/post hospitalization related-care windows must be category rules.

### High diagnostics
Annual maximum EUR 10,000. In-network EUR 20; out-of-network 20% with minimum EUR 35; ticket 100%.

### Specialist visits / diagnostics / outpatient
Annual maximum EUR 3,000. In-network EUR 15; out-of-network and medicines 20% with minimum EUR 35; ticket 100%.

### Physiotherapy / rehabilitation
Requires medical prescription and diagnosis/clinical justification. Multiple sessions/fattures may belong to one MedicalEvent.

### Pharmaceuticals
Prescription should identify patient/requester and diagnosis; fiscal receipt must identify purchased product corresponding to prescription. Non-covered insurance product types include OTC without prescription, para-pharmacy, medical devices, hygiene/diet products, supplements and cosmetics.

### Dental
Annual maximum EUR 2,600; in-network EUR 50; out-of-network 25% with minimum EUR 103. Treatment description required.

### Preventive medicine
Dedicated category with listed services/frequency conditions; not governed solely by diagnosis.

### Corrective lenses
Requires first prescription or certified change of visus, with category-specific limit/rules.

## Documentation model
Specialist/diagnostic: diagnosis or suspected diagnosis, prescription where applicable, valid expense document.
Physiotherapy: valid invoice + diagnosis + prescription.
Pharmaceutical: prescription + diagnosis + product-level fiscal receipt.
Ticket: prescription with diagnosis + valid expense documentation.
Dental: description of work.
Hospitalization: full clinical documentation according to process.

## Important implementation rule
Never reduce eligibility to "diagnosis present => insurance". Dental, preventive medicine, lenses and other categories need dedicated logic.

Executable draft: `rules/insurance/2026.yml`. Every active rule must preserve source provenance and human approval.
