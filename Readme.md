# 🧠 Kariera Job Scraper

A Python-based job scraping tool that automatically fetches job listings from [kariera.gr](https://www.kariera.gr) on a daily basis. Built with Selenium and scheduled using `crontab`, it avoids duplicates, performs automated cleaning, and exports the results for easy querying and analysis.

## 🚀 Features

- 🔍 **Automated Job Scraping** from kariera.gr with multiple keyword searches
- 🔁 **Daily Execution** using `crontab`
- 🧹 **Data Cleaning Pipeline** to filter out irrelevant or duplicate entries
- 📦 **Data Export** in both `.csv` and `.pkl` formats
- 🧾 **Robust Logging** of runs and errors with the `logging` module
- 🛡️ Duplicate-checking logic for efficiency

## 🛠️ Tech Stack

- **Python**
- **Selenium**
- **Pandas**
- **crontab** (for scheduling)
- **logging** (for monitoring)

## 📁 Folder Structure
```bash
├── data
├── log
│   └── error
├── logging_setup.py
├── main.py
├── notebook.ipynb
└── Readme.md
```