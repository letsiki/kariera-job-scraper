drop table IF EXISTS "job_ads";
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
	PRIMARY KEY ("ad_link")
);
CREATE INDEX idx_job_ads_date_updated ON job_ads (date_updated);
CREATE INDEX idx_job_ads_report_false ON job_ads (report)
WHERE report = false;
