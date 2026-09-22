-- MySQL 8.0.16+ schema. All loaded records are synthetic/simulated.
CREATE DATABASE IF NOT EXISTS pharma_sales_marketing_synthetic CHARACTER SET utf8mb4;
USE pharma_sales_marketing_synthetic;

CREATE TABLE territory (
  territory_id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
  territory_name VARCHAR(80) NOT NULL UNIQUE
) ENGINE=InnoDB;
CREATE TABLE physician (
  physician_id INT UNSIGNED NOT NULL PRIMARY KEY,
  territory_id TINYINT UNSIGNED NOT NULL,
  specialty VARCHAR(80) NOT NULL,
  KEY ix_physician_territory (territory_id),
  CONSTRAINT fk_physician_territory FOREIGN KEY (territory_id) REFERENCES territory (territory_id)
) ENGINE=InnoDB;
CREATE TABLE campaign (
  campaign_id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
  campaign_name VARCHAR(100) NOT NULL UNIQUE,
  channel VARCHAR(40) NOT NULL
) ENGINE=InnoDB;
-- Grain: one simulated physician-month record, including zero prescriptions.
CREATE TABLE prescription_month (
  physician_id INT UNSIGNED NOT NULL,
  month_start DATE NOT NULL,
  prescriptions INT UNSIGNED NOT NULL,
  revenue_usd DECIMAL(14,2) NOT NULL,
  target_rx INT UNSIGNED NOT NULL,
  PRIMARY KEY (physician_id, month_start), KEY ix_prescription_month (month_start),
  CONSTRAINT ck_prescription_nonnegative CHECK (prescriptions >= 0),
  CONSTRAINT ck_revenue_nonnegative CHECK (revenue_usd >= 0),
  CONSTRAINT ck_target_positive CHECK (target_rx > 0),
  CONSTRAINT fk_prescription_physician FOREIGN KEY (physician_id) REFERENCES physician (physician_id)
) ENGINE=InnoDB;
-- Grain: at most one simulated outreach contact per physician-month.
CREATE TABLE outreach (
  physician_id INT UNSIGNED NOT NULL,
  month_start DATE NOT NULL,
  campaign_id TINYINT UNSIGNED NOT NULL,
  responded TINYINT UNSIGNED NOT NULL,
  cost_usd DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (physician_id, month_start), KEY ix_outreach_campaign (campaign_id),
  CONSTRAINT ck_response_binary CHECK (responded IN (0,1)),
  CONSTRAINT ck_cost_nonnegative CHECK (cost_usd >= 0),
  CONSTRAINT fk_outreach_physician FOREIGN KEY (physician_id) REFERENCES physician (physician_id),
  CONSTRAINT fk_outreach_campaign FOREIGN KEY (campaign_id) REFERENCES campaign (campaign_id)
) ENGINE=InnoDB;
