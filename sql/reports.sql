-- SQLite 3.25+; fact grain is one physician-month, including zero volume.
CREATE VIEW monthly_performance AS
WITH totals AS (
 SELECT f.month, p.territory_id, t.territory_name,
        COUNT(*) AS physicians, SUM(f.prescriptions) AS prescriptions,
        SUM(f.revenue_usd) AS revenue_usd,
        SUM(CASE WHEN f.prescriptions > 0 THEN 1 ELSE 0 END) AS active_physicians
 FROM prescription_month f
 JOIN physician p USING(physician_id)
 JOIN territory t USING(territory_id)
 GROUP BY f.month, p.territory_id, t.territory_name
), history AS (
 SELECT *, LAG(prescriptions) OVER (PARTITION BY territory_id ORDER BY month) AS previous_month_rx
 FROM totals
)
SELECT *, ROUND(100.0 * (prescriptions-previous_month_rx) / NULLIF(previous_month_rx,0),2) AS rx_growth_pct
FROM history;

CREATE VIEW territory_performance AS
SELECT p.territory_id, t.territory_name, COUNT(DISTINCT p.physician_id) AS physicians,
       SUM(f.prescriptions) AS prescriptions, ROUND(SUM(f.revenue_usd),2) AS revenue_usd,
       ROUND(1.0*SUM(f.prescriptions)/COUNT(DISTINCT p.physician_id),2) AS rx_per_physician,
       SUM(f.target_rx) AS target_rx,
       ROUND(100.0*SUM(f.prescriptions)/SUM(f.target_rx),2) AS target_attainment_pct
FROM prescription_month f JOIN physician p USING(physician_id) JOIN territory t USING(territory_id)
GROUP BY p.territory_id, t.territory_name;

-- Activity-based segments are descriptive, not clinical or prescribing recommendations.
CREATE VIEW physician_segments AS
WITH profile AS (
 SELECT p.physician_id, p.territory_id, p.specialty,
        SUM(f.prescriptions) AS annual_rx,
        SUM(CASE WHEN f.prescriptions > 0 THEN 1 ELSE 0 END) AS active_months,
        COALESCE(MIN(CASE WHEN f.prescriptions > 0 THEN 12-CAST(SUBSTR(f.month,6,2) AS INTEGER) END),12) AS months_since_activity
 FROM physician p JOIN prescription_month f USING(physician_id)
 GROUP BY p.physician_id, p.territory_id, p.specialty
), ranked AS (
 SELECT *, NTILE(4) OVER(ORDER BY annual_rx, physician_id) AS volume_quartile FROM profile
)
SELECT *, CASE WHEN months_since_activity >= 3 THEN 'Lapsed'
               WHEN volume_quartile=4 AND active_months >= 9 THEN 'High activity'
               WHEN volume_quartile>=3 THEN 'Established'
               ELSE 'Low activity' END AS segment
FROM ranked;

-- Responses are recorded only for contacted physicians. Do not call this uplift or ROI.
CREATE VIEW campaign_performance AS
SELECT c.campaign_id, c.campaign_name, c.channel, COUNT(*) AS contacts,
       SUM(o.responded) AS responses, ROUND(100.0*SUM(o.responded)/COUNT(*),2) AS response_rate_pct,
       ROUND(SUM(o.cost_usd),2) AS contact_cost_usd,
       ROUND(SUM(o.cost_usd)/NULLIF(SUM(o.responded),0),2) AS cost_per_response_usd
FROM outreach o JOIN campaign c USING(campaign_id)
GROUP BY c.campaign_id,c.campaign_name,c.channel;

CREATE VIEW campaign_segment_response AS
SELECT c.channel, s.segment, COUNT(*) AS contacts, SUM(o.responded) AS responses,
       ROUND(100.0*SUM(o.responded)/COUNT(*),2) AS response_rate_pct
FROM outreach o JOIN campaign c USING(campaign_id) JOIN physician_segments s USING(physician_id)
GROUP BY c.channel,s.segment;

-- Rank annual synthetic revenue. Equal rounded revenue receives the same rank;
-- physician counts and target attainment are separate measures of performance.
CREATE VIEW territory_ranking AS
SELECT *,
       RANK() OVER (ORDER BY revenue_usd DESC) AS revenue_rank,
       RANK() OVER (ORDER BY revenue_usd ASC) AS bottom_revenue_rank,
       ROUND(100.0 * revenue_usd / NULLIF(SUM(revenue_usd) OVER (),0),2)
         AS revenue_contribution_pct
FROM territory_performance;

-- Three rank positions, including ties; a territory may occur in both groups
-- in a small sample. UNION ALL preserves those two distinct memberships.
CREATE VIEW territory_extremes AS
SELECT 'Top revenue ranks' AS comparison_group, *
FROM territory_ranking WHERE revenue_rank <= 3
UNION ALL
SELECT 'Bottom revenue ranks' AS comparison_group, *
FROM territory_ranking WHERE bottom_revenue_rank <= 3;

-- Both tables are unique by physician-month. Joining only on physician would
-- multiply rows. Missing outreach means no recorded contact, not response=0.
-- Same-month activity has no before/after ordering and is not causal uplift.
CREATE VIEW exposure_comparison AS
SELECT f.month,
       CASE WHEN o.physician_id IS NULL THEN 'No contact recorded'
            ELSE 'Contact recorded' END AS exposure_group,
       COUNT(*) AS physician_months,
       SUM(f.prescriptions) AS prescriptions,
       ROUND(SUM(f.revenue_usd),2) AS revenue_usd,
       ROUND(AVG(f.prescriptions),2) AS rx_per_physician_month,
       COUNT(o.physician_id) AS contacts,
       SUM(o.responded) AS responses,
       ROUND(100.0 * SUM(o.responded) / NULLIF(COUNT(o.physician_id),0),2)
         AS response_rate_pct
FROM prescription_month f
LEFT JOIN outreach o ON o.physician_id=f.physician_id AND o.month=f.month
GROUP BY f.month, exposure_group;
