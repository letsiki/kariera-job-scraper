CREATE TABLE IF NOT EXISTS "job_ads" (
	"id" serial NOT NULL UNIQUE,
	"role" varchar(255) NOT NULL,
	"company" varchar(255) NOT NULL,
	"location" varchar(255) NOT NULL,
	"min_experience" varchar(255),
	"employment_type" varchar(255) NOT NULL,
	"category" varchar(255) NOT NULL,
	"remote" varchar(255),
	"details" TEXT[] NOT NULL,
	"tags" TEXT[] NOT NULL,
	"ad_link" varchar(255) NOT NULL,
	"days_old" SMALLINT DEFAULT 0,
	"created_at" TIMESTAMP DEFAULT NOW(),
	PRIMARY KEY ("id")
);

drop table IF EXISTS "job_ads";





