-- Prerequisite: mysql --local-infile=1. Replace the placeholder path locally;
-- never commit a machine-specific path. Run Python generation before loading.
USE pharma_sales_marketing_synthetic;
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE outreach; TRUNCATE TABLE prescription_month; TRUNCATE TABLE physician;
TRUNCATE TABLE campaign; TRUNCATE TABLE product; TRUNCATE TABLE calendar; TRUNCATE TABLE territory;
SET FOREIGN_KEY_CHECKS = 1;

LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/territory.csv' INTO TABLE territory FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/physician.csv' INTO TABLE physician FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/campaign.csv' INTO TABLE campaign FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/product.csv' INTO TABLE product FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/calendar.csv' INTO TABLE calendar FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES (@month_key,@month_start,quarter_label,calendar_year) SET month_key=@month_key, month_start=STR_TO_DATE(@month_start,'%Y-%m-%d');
LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/prescription_month.csv' INTO TABLE prescription_month FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES (physician_id,product_id,@month_text,prescriptions,revenue_usd,target_rx) SET month_start=STR_TO_DATE(CONCAT(@month_text,'-01'),'%Y-%m-%d');
LOAD DATA LOCAL INFILE 'C:/REPLACE_WITH_PROJECT_PATH/data/outreach.csv' INTO TABLE outreach FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 LINES (physician_id,@month_text,campaign_id,responded,cost_usd) SET month_start=STR_TO_DATE(CONCAT(@month_text,'-01'),'%Y-%m-%d');
