-- Run after loading. The first four queries must return zero rows.
USE pharma_sales_marketing_synthetic;
SELECT 'duplicate_physician_product_month' AS check_name, physician_id, product_id, month_start, COUNT(*) AS n FROM prescription_month GROUP BY physician_id,product_id,month_start HAVING COUNT(*)>1;
SELECT 'duplicate_outreach_month' AS check_name, physician_id, month_start, COUNT(*) AS n FROM outreach GROUP BY physician_id,month_start HAVING COUNT(*)>1;
SELECT 'invalid_prescription_value' AS check_name, physician_id, product_id, month_start FROM prescription_month WHERE prescriptions<0 OR revenue_usd<0 OR target_rx<0 OR month_start IS NULL;
SELECT 'invalid_outreach_value' AS check_name, physician_id, month_start FROM outreach WHERE responded NOT IN (0,1) OR cost_usd<0 OR month_start IS NULL;
SELECT 'orphan_prescription_physician' AS check_name, f.physician_id,f.month_start FROM prescription_month f LEFT JOIN physician p ON p.physician_id=f.physician_id WHERE p.physician_id IS NULL;
SELECT 'orphan_outreach_campaign' AS check_name, o.physician_id,o.month_start FROM outreach o LEFT JOIN campaign c ON c.campaign_id=o.campaign_id WHERE c.campaign_id IS NULL;
SELECT 'incomplete_physician_coverage' AS check_name, physician_id,COUNT(*) AS months FROM prescription_month GROUP BY physician_id HAVING COUNT(*)<>12;
SELECT 'row_counts' AS check_name,(SELECT COUNT(*) FROM territory) territories,(SELECT COUNT(*) FROM physician) physicians,(SELECT COUNT(*) FROM campaign) campaigns,(SELECT COUNT(*) FROM product) products,(SELECT COUNT(*) FROM calendar) calendar_months,(SELECT COUNT(*) FROM prescription_month) physician_product_months,(SELECT COUNT(*) FROM outreach) contacts;
