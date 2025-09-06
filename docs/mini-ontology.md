# Mini‑Ontology for Regulatory Topics

## Top-Level Topics
- **flammable_liquids** — storage, handling, transfer, dispensing, cabinets, control areas.
- **portable_containers** — can types, limits, labeling, grounding/bonding.
- **secondary_containment** — spill control, diking, sump capacity, drainage.
- **tanks** — aboveground/underground, venting, overfill, emergency relief.
- **dispensing** — fueling operations, distances, ignition source controls.
- **permits_inspections** — operational permits, plan review, inspection cadence.
- **signage_labeling** — placarding, NFPA 704, GHS labels, hazard communication.
- **housekeeping** — spill cleanup materials, incompatible separation, ventilation.
- **electrical_classification** — classified locations, bonding/grounding.
- **adoption_versions** — edition adopted, effective dates, local amendments.

## Synonyms & Normalization
- secondary containment ↔ bunding, spill berms, diking, spill control
- safety cabinet ↔ flammable storage cabinet
- Class I liquid ↔ Class I (IA/IB/IC)
- can ↔ portable container, safety can, jerrican
- AHJ ↔ authority having jurisdiction, fire marshal

## Entities
- **Standards:** IFC, NFPA 30
- **Jurisdictions:** US states/territories; use ISO‑like two-letter (CO, TX, CA, …)
- **Doc types:** statute, rule, code adoption, notice, bulletin, guidance

## Metadata Tags (use as filters)
- `standard:[IFC|NFPA30]`
- `jurisdiction:[CO|TX|…]`
- `topic:[flammable_liquids|secondary_containment|…]`
- `doc_type:[adoption|amendment|notice|rule]`

## Retrieval Hints
- Prioritize chunks with `section_path` matching explicit user mentions (e.g., "5704" or "9.5").
- Boost recent `published_date` for change queries.
````
