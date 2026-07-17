-- =====================================================================
-- IIVAS — Section 3: normalized PostgreSQL schema (3NF)
-- Central fact: votes. Dimensions: investors, companies, industries,
-- proposals. Aggregate: yearly_statistics.
-- Run order: this file, then 02_indexes.sql, then 03_views.sql.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- industries — sector lookup (referenced by companies)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS industries (
    industry_id     SERIAL PRIMARY KEY,
    sic_code        VARCHAR(8),
    gics_sector     VARCHAR(80),
    industry_name   VARCHAR(160) NOT NULL,
    UNIQUE (industry_name)
);

-- ---------------------------------------------------------------------
-- investors — the filing asset managers (the "Big Three")
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS investors (
    investor_id     SERIAL PRIMARY KEY,
    cik             VARCHAR(10) NOT NULL,
    investor_name   VARCHAR(160) NOT NULL,
    investor_type   VARCHAR(60) DEFAULT 'Asset Manager',
    UNIQUE (cik)
);

-- ---------------------------------------------------------------------
-- companies — issuers whose proposals are voted on
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    company_id      SERIAL PRIMARY KEY,
    cusip           VARCHAR(12),
    ticker          VARCHAR(16),
    company_name    VARCHAR(255) NOT NULL,
    industry_id     INTEGER REFERENCES industries (industry_id) ON DELETE SET NULL,
    market_cap_usd  NUMERIC(18,2),                  -- nullable; joined from external source
    market_cap_bucket VARCHAR(12),                  -- Mega/Large/Mid/Small/Micro
    UNIQUE (company_name, cusip)
);

-- ---------------------------------------------------------------------
-- proposals — one row per distinct proposal voted on
-- category constrained to the IIVAS taxonomy
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id         SERIAL PRIMARY KEY,
    company_id          INTEGER NOT NULL REFERENCES companies (company_id) ON DELETE CASCADE,
    proposal_year       SMALLINT NOT NULL,
    proposal_text       TEXT NOT NULL,
    proposal_sponsor    VARCHAR(20)                 -- 'Management' | 'Shareholder'
                        CHECK (proposal_sponsor IN ('Management','Shareholder') OR proposal_sponsor IS NULL),
    category            VARCHAR(40) NOT NULL DEFAULT 'Other'
                        CHECK (category IN ('ESG','Executive Compensation',
                                            'Board Governance','Shareholder Rights','Other')),
    classification_method VARCHAR(20),              -- 'rule' | 'ml' | 'manual'
    management_recommendation VARCHAR(12)           -- 'For' | 'Against' | 'None'
                        CHECK (management_recommendation IN ('For','Against','None') OR management_recommendation IS NULL)
);

-- ---------------------------------------------------------------------
-- votes — central fact table. One row per cast vote.
-- support_management is the supervised-learning target (1/0/NULL).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS votes (
    vote_id             BIGSERIAL PRIMARY KEY,
    investor_id         INTEGER NOT NULL REFERENCES investors (investor_id) ON DELETE CASCADE,
    company_id          INTEGER NOT NULL REFERENCES companies (company_id) ON DELETE CASCADE,
    proposal_id         INTEGER NOT NULL REFERENCES proposals (proposal_id) ON DELETE CASCADE,
    vote_year           SMALLINT NOT NULL,
    accession           VARCHAR(25),                -- source filing, for audit
    vote_cast           VARCHAR(12)                 -- normalized outcome
                        CHECK (vote_cast IN ('For','Against','Abstain','Withhold','Other') OR vote_cast IS NULL),
    shares_voted        NUMERIC(20,2),
    support_management  SMALLINT                    -- 1 = aligned, 0 = against, NULL = n/a
                        CHECK (support_management IN (0,1) OR support_management IS NULL),
    CONSTRAINT uq_vote UNIQUE (investor_id, proposal_id, accession)
);

-- ---------------------------------------------------------------------
-- yearly_statistics — pre-aggregated per investor/year for fast dashboards
-- Refreshed by src/metrics/iivas.py after scoring.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS yearly_statistics (
    stat_id                 SERIAL PRIMARY KEY,
    investor_id             INTEGER NOT NULL REFERENCES investors (investor_id) ON DELETE CASCADE,
    stat_year               SMALLINT NOT NULL,
    total_votes             INTEGER,
    governance_support_rate NUMERIC(6,4),
    compensation_support_rate NUMERIC(6,4),
    esg_support_rate        NUMERIC(6,4),
    management_alignment_rate NUMERIC(6,4),
    governance_score        NUMERIC(6,2),
    compensation_score      NUMERIC(6,2),
    esg_score               NUMERIC(6,2),
    management_alignment_score NUMERIC(6,2),
    iivas_composite         NUMERIC(6,2),
    UNIQUE (investor_id, stat_year)
);

COMMIT;
