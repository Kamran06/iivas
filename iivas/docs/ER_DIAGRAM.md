# IIVAS — Entity-Relationship Design (Section 3)

## Narrative

The schema is normalized to third normal form with the `votes` table as the
central fact and four dimension tables, plus one pre-aggregated reporting
table. This is a star-leaning layout: it keeps the fact table narrow and
join-friendly while pushing descriptive attributes (issuer, sector, proposal
text, manager identity) into dimensions so they are stored once and updated in
one place.

## Cardinalities

- `industries (1) ──< companies (many)` — a sector contains many issuers; each company has at most one sector.
- `companies (1) ──< proposals (many)` — an issuer puts many proposals to a vote across years.
- `companies (1) ──< votes (many)` and `proposals (1) ──< votes (many)` — each vote references exactly one company and one proposal.
- `investors (1) ──< votes (many)` — each filer casts many votes.
- `investors (1) ──< yearly_statistics (many)` — one aggregate row per investor per year.

A vote is uniquely identified in business terms by `(investor_id, proposal_id, accession)`; the `uq_vote` constraint enforces this and is the deduplication backstop for re-filed amendments.

## Text diagram

```
            ┌──────────────┐
            │ industries   │
            │  PK industry │
            └──────┬───────┘
                   │ 1
                   │
                   ▼ many
            ┌──────────────┐         1        many ┌──────────────┐
            │ companies    │──────────────────────▶│ proposals    │
            │ PK company   │                        │ PK proposal  │
            │ FK industry  │                        │ FK company   │
            └──────┬───────┘                        └──────┬───────┘
                   │ 1                                      │ 1
                   │ many                                   │ many
                   ▼                                        ▼
            ┌───────────────────────────────────────────────────┐
            │                     votes  (FACT)                   │
            │ PK vote_id                                          │
            │ FK investor_id, FK company_id, FK proposal_id       │
            │ vote_year, vote_cast, support_management (target)   │
            └───────────────────────────────────────────────────┘
                   ▲ many                                  ▲ many
                   │ 1                                     │
            ┌──────┴───────┐                       (aggregated into)
            │ investors    │ 1 ──< many ┌────────────────────────┐
            │ PK investor  │───────────▶│ yearly_statistics       │
            └──────────────┘            │ PK stat_id, FK investor │
                                        │ IIVAS components/year   │
                                        └────────────────────────┘
```

## Keys & integrity summary

| Table | Primary key | Foreign keys | Notable constraints |
|---|---|---|---|
| industries | industry_id | — | UNIQUE(industry_name) |
| investors | investor_id | — | UNIQUE(cik) |
| companies | company_id | industry_id → industries | UNIQUE(company_name, cusip) |
| proposals | proposal_id | company_id → companies | category CHECK in 5-value taxonomy |
| votes | vote_id | investor_id, company_id, proposal_id | UNIQUE(investor_id, proposal_id, accession); support_management ∈ {0,1,NULL} |
| yearly_statistics | stat_id | investor_id → investors | UNIQUE(investor_id, stat_year) |

## Indexing rationale

The fact table is filtered most often by `(investor_id, vote_year)` and joined to `proposals` for category cuts, so those get composite/single B-tree indexes. A GIN full-text index on `proposals.proposal_text` supports the classification QA workflow (searching for keyword patterns). The aggregate table is tiny and indexed on its natural reporting key. Full DDL in `sql/02_indexes.sql`.
