-- =====================================================================
-- IIVAS — Section 3: indexing strategy
-- The fact table is queried by (investor, year), by category via the
-- proposals join, and by company/industry. Indexes target those paths.
-- =====================================================================

-- votes: the hot table. Composite indexes for the common filters.
CREATE INDEX IF NOT EXISTS idx_votes_investor_year   ON votes (investor_id, vote_year);
CREATE INDEX IF NOT EXISTS idx_votes_company         ON votes (company_id);
CREATE INDEX IF NOT EXISTS idx_votes_proposal        ON votes (proposal_id);
CREATE INDEX IF NOT EXISTS idx_votes_support         ON votes (support_management);

-- proposals: filtered/grouped by category and year constantly.
CREATE INDEX IF NOT EXISTS idx_proposals_category    ON proposals (category);
CREATE INDEX IF NOT EXISTS idx_proposals_year        ON proposals (proposal_year);
CREATE INDEX IF NOT EXISTS idx_proposals_company     ON proposals (company_id);
-- Full-text index to support the classification QA / search workflow.
CREATE INDEX IF NOT EXISTS idx_proposals_text_fts
    ON proposals USING GIN (to_tsvector('english', proposal_text));

-- companies: joined to industries; filtered by market-cap bucket.
CREATE INDEX IF NOT EXISTS idx_companies_industry    ON companies (industry_id);
CREATE INDEX IF NOT EXISTS idx_companies_bucket      ON companies (market_cap_bucket);

-- yearly_statistics: small, but dashboards read by investor/year.
CREATE INDEX IF NOT EXISTS idx_ystats_investor_year  ON yearly_statistics (investor_id, stat_year);
