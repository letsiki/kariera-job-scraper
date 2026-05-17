-- Idempotent schema. install.sh re-applies this on every run, so every
-- statement here must be safe to repeat against an already-populated DB.
-- DO NOT add `DROP TABLE` — it would wipe accumulated scrape history.

CREATE TABLE IF NOT EXISTS "job_ads" (
	"role" varchar(255) NOT NULL,
	"company" varchar(255) NOT NULL,
	"location" varchar(255) NOT NULL,
	"min_experience" varchar(255),
	"employment_type" varchar(255) NOT NULL,
	"category" varchar(255) NOT NULL,
	"remote" varchar(255),
	"details" TEXT [] NOT NULL,
	"tags" TEXT [] NOT NULL,
	"ad_link" varchar(255) NOT NULL UNIQUE,
	"date_posted" TIMESTAMPTZ NOT NULL,
	"date_updated" TIMESTAMPTZ NOT NULL,
	"report" BOOLEAN DEFAULT FALSE,
	"renewals" SMALLINT DEFAULT 0,
	PRIMARY KEY ("ad_link")
);

CREATE INDEX IF NOT EXISTS idx_job_ads_date_updated ON job_ads (date_updated);
CREATE INDEX IF NOT EXISTS idx_job_ads_report_false ON job_ads (report) WHERE report = false;

-- Belt-and-suspenders for older DBs that may have been created without
-- the renewals column (now folded into the main CREATE above).
ALTER TABLE job_ads ADD COLUMN IF NOT EXISTS renewals SMALLINT DEFAULT 0;
