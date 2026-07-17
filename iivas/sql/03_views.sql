-- =====================================================================
-- IIVAS — Section 3: analytical views consumed by EDA + dashboards
-- =====================================================================

-- Denormalized fact for ad-hoc analysis / Power BI direct query.
CREATE OR REPLACE VIEW v_votes_enriched AS
SELECT
    v.vote_id,
    i.investor_name,
    c.company_name,
    c.market_cap_bucket,
    ind.gics_sector,
    p.category,
    p.proposal_sponsor,
    p.management_recommendation,
    v.vote_year,
    v.vote_cast,
    v.support_management
FROM votes v
JOIN investors  i  ON i.investor_id = v.investor_id
JOIN companies  c  ON c.company_id  = v.company_id
JOIN proposals  p  ON p.proposal_id = v.proposal_id
LEFT JOIN industries ind ON ind.industry_id = c.industry_id;

-- Support rate by investor and proposal category (RQ1-3).
CREATE OR REPLACE VIEW v_support_by_category AS
SELECT
    investor_name,
    category,
    COUNT(*)                                   AS n_votes,
    ROUND(AVG(support_management)::numeric, 4)  AS support_rate
FROM v_votes_enriched
WHERE support_management IS NOT NULL
GROUP BY investor_name, category;

-- Support rate by investor and year (RQ6 time trend).
CREATE OR REPLACE VIEW v_support_by_year AS
SELECT
    investor_name,
    vote_year,
    COUNT(*)                                   AS n_votes,
    ROUND(AVG(support_management)::numeric, 4)  AS support_rate
FROM v_votes_enriched
WHERE support_management IS NOT NULL
GROUP BY investor_name, vote_year;

-- Support rate by investor and sector (RQ4 industry variation).
CREATE OR REPLACE VIEW v_support_by_sector AS
SELECT
    investor_name,
    gics_sector,
    COUNT(*)                                   AS n_votes,
    ROUND(AVG(support_management)::numeric, 4)  AS support_rate
FROM v_votes_enriched
WHERE support_management IS NOT NULL AND gics_sector IS NOT NULL
GROUP BY investor_name, gics_sector;
