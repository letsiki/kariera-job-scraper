"""Remote-jobs ingestors that feed the same job_ads table as the
kariera.gr Playwright scraper. Each submodule exposes `fetch()` returning
an iterable of JobAd. `aggregator.py` is the runtime entry point."""
