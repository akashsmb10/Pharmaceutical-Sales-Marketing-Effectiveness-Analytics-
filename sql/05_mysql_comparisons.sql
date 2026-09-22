-- Synthetic analytics; run after 04_mysql_analytics_views.sql.
-- This file is not yet execution-verified on MySQL.
USE pharma_sales_marketing_synthetic;

-- Rank rounded annual revenue consistently with the tested SQLite definition.
-- Include ties in the first three rank positions at each end.
WITH ranked AS (
  SELECT territory_id, territory_name, revenue_usd,
         RANK() OVER (ORDER BY revenue_usd DESC) AS top_rank,
         RANK() OVER (ORDER BY revenue_usd ASC) AS bottom_rank,
         ROUND(100.0 * revenue_usd / NULLIF(SUM(revenue_usd) OVER (),0),2)
           AS revenue_contribution_pct
  FROM v_territory_performance
)
SELECT 'Top revenue ranks' AS comparison_group, ranked.*
FROM ranked WHERE top_rank <= 3
UNION ALL
SELECT 'Bottom revenue ranks' AS comparison_group, ranked.*
FROM ranked WHERE bottom_rank <= 3;

-- Never interpret uncontacted physician-months as response failures.
-- The composite-key join preserves the original physician-month grain.
SELECT f.month_start,
       CASE WHEN o.physician_id IS NULL THEN 'No contact recorded'
            ELSE 'Contact recorded' END AS exposure_group,
       COUNT(*) AS physician_months,
       SUM(f.prescriptions) AS prescriptions,
       ROUND(SUM(f.revenue_usd),2) AS revenue_usd,
       ROUND(AVG(f.prescriptions),2) AS rx_per_physician_month,
       COUNT(o.physician_id) AS contacts,
       SUM(o.responded) AS responses,
       ROUND(100.0*SUM(o.responded)/NULLIF(COUNT(o.physician_id),0),2)
         AS response_rate_pct
FROM prescription_month f
LEFT JOIN outreach o ON o.physician_id=f.physician_id
                   AND o.month_start=f.month_start
GROUP BY f.month_start, exposure_group
ORDER BY f.month_start, exposure_group;

-- Response rates among contacted physicians, by retrospective segment.
SELECT c.channel, s.segment, COUNT(*) AS contacts,
       SUM(o.responded) AS responses,
       ROUND(100.0*SUM(o.responded)/COUNT(*),2) AS response_rate_pct
FROM outreach o
JOIN campaign c ON c.campaign_id=o.campaign_id
JOIN v_physician_segments s ON s.physician_id=o.physician_id
GROUP BY c.channel, s.segment
ORDER BY c.channel, s.segment;
