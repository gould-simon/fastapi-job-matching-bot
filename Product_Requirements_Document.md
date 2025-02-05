# 📌 Product Requirements Document (PRD)
## AI-Powered Job Matching Bot for Accounting Professionals

---

## 1. Introduction

Accounting professionals often struggle to find relevant jobs on generic job boards. There’s a gap for a specialized system that uses **AI** to understand a candidate’s resume (or input) and then **surface matching roles** in the accounting industry—particularly from specialized databases like [accountingfirmjobs.com](https://accountingfirmjobs.com/).

This bot is built using **FastAPI** (Python) on the backend, a **PostgreSQL** database (on Render), and a **Telegram** interface for chat-based interactions. Its main purpose is to:
1. Automate job discovery.
2. Provide relevant, accounting-focused job matches.
3. Improve the user experience for both job seekers and recruiters at accounting firms.

---

## 2. Objectives & Goals

### For Job Seekers
- **AI job search**: Provide quick, chat-based job searches via Telegram (`/search_jobs`).
- **CV parsing & recommendations**: Extract key skills from uploaded CVs (`/upload_cv`) and suggest suitable roles.
- **Personalized experience**: Remember user preferences and serve relevant suggestions.

### For Employers & Recruiters
- **Targeted candidate matching**: Ensure posted jobs reach active candidates who match the required skill set.
- **High-quality applicant flow**: Reduce noise from irrelevant applicants.

### For Platform Growth & Monetization
- Build a **talent database** of accounting professionals (using user-submitted data).
- Provide potential for **premium job postings** or **AI-driven resume alerts** in the future.

---

## 3. Target Users & Roles

| **User Type**                    | **Actions & Responsibilities**                                    |
|----------------------------------|--------------------------------------------------------------------|
| **Job Seekers (Telegram users)** | - Search jobs, set alerts, upload CVs. <br> - Provide job preferences (role, location, seniority).  |
| **Accounting Firms & Recruiters**| - Post jobs in accountingfirmjobs.com (already integrated). <br> - Potential future: sponsor postings, access matched leads. |
| **Admin (Internal)**             | - Monitor usage stats and logs via Streamlit admin dashboard. <br> - Verify DB health and fix search logic issues. |

---

## 4. Core Features (Current MVP)

1. **Telegram Bot**  
   - **Search-based conversation** (`/search_jobs`): The user is prompted to specify role, location, and experience level.  
   - **CV Upload** (`/upload_cv`): The system extracts text from PDF or Word documents using `pdfplumber` or `python-docx`, then uses OpenAI’s API to generate a summary and potential matching roles.  
   - **Free-form Chat**: The bot can provide basic Q&A or fallback to an AI-driven response using `get_ai_response`.

2. **AI Preference Extraction**  
   - The bot calls `extract_job_preferences` (in `ai_handler.py`) to parse user queries like “audit technology roles in new york for manager or director level.”  
   - GPT-based logic transforms queries into JSON with fields like **role**, **location**, **experience**, and **salary**.  
   - Some **standardization** is attempted (e.g. “NY,” “NYC” → “new york”), though it’s still evolving.

3. **Database Integration**  
   - The bot queries a **PostgreSQL** database referencing tables from [accountingfirmjobs.com](https://accountingfirmjobs.com/).  
   - **Tables**:  
     - `users` (tracks Telegram users + their preferences)  
     - `JobsApp_job` (contains job posts: title, location, service line, seniority, etc.)  
     - `JobsApp_accountingfirm` (firms that post jobs)  
     - `user_searches` (logs the user’s search queries & extracted preferences)

4. **Basic Job Matching (SQL + LIKE)**  
   - Currently, the code mostly uses `LOWER(...) LIKE '%pattern%'` queries over `job_title`, `service`, and optionally `description`.  
   - If no matches are found, the bot attempts a broader fallback (though the fallback logic is not fully refined).

5. **Admin Dashboard**  
   - Implemented with **Streamlit** (`admin_dashboard.py`).  
   - Provides:  
     - **User metrics** (total users, recently active)  
     - **Job search counts**  
     - **Log viewer** (from SQLite plus conversation logs)  
     - **DB connection checks** and error reports

---

## 5. Data Models

### 5.1 `users` Table

    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        username TEXT NULL,
        first_name TEXT NULL,
        last_name TEXT NULL,
        job_preferences TEXT NULL,
        subscribed_to_alerts BOOLEAN DEFAULT FALSE,
        messages_sent INTEGER DEFAULT 0,
        last_active TIMESTAMP DEFAULT NOW(),
        created_at DATE NULL,
        career_level TEXT NULL,
        job_type_preferences TEXT NULL,
        industry_preferences TEXT NULL,
        certifications TEXT NULL,
        skills TEXT NULL,
        salary_expectation TEXT NULL,
        career_goals TEXT NULL
    );

- Tracks each Telegram user’s basic info and their preferences.
- The code primarily uses `telegram_id`, `username`, and `job_preferences`.

### 5.2 `user_searches` Table

    CREATE TABLE user_searches (
        id SERIAL PRIMARY KEY,
        telegram_id INTEGER,
        search_query TEXT NOT NULL,
        structured_preferences JSON NULL,
        created_at TIMESTAMP NULL
    );

- Logs each search the user makes (e.g. “audit manager in new york”).
- `structured_preferences` often stores the GPT-extracted JSON.

### 5.3 `JobsApp_accountingfirm` and `JobsApp_job`

    JobsApp_accountingfirm(
        id SERIAL PRIMARY KEY,
        name TEXT,
        ...
    );

    JobsApp_job(
        id SERIAL PRIMARY KEY,
        firm_id INT REFERENCES "JobsApp_accountingfirm"(id),
        job_title TEXT,
        seniority TEXT,
        service TEXT,
        industry TEXT,
        location TEXT,
        employment TEXT,
        salary TEXT,
        description TEXT,
        link TEXT,
        date_published TEXT,
        ...
    );

- **`JobsApp_job`** is the core source for actual job listings.
- The code uses `job_title`, `service`, `location`, `seniority`, and `description` when matching queries.

---

## 6. AI Job Matching Architecture

1. **Prompt-based Preference Extraction**  
   - The user’s free-text search is parsed by GPT (via `extract_job_preferences`), returning a JSON with role, location, experience, etc.

2. **SQL Query**  
   - The bot runs `LIKE`-based queries. Example logic:
    
        SELECT *
        FROM "JobsApp_job"
        WHERE LOWER(job_title) LIKE '%{role}%'
          OR LOWER(service) LIKE '%{role}%'
          AND LOWER(location) LIKE '%{location}%'
          AND LOWER(seniority) LIKE '%{experience}%';
    
   - A fallback search is triggered if no direct matches are found, but this is still fairly simple (no OR queries for multiple seniorities, etc.).

3. **CV Embedding (Partially Implemented)**  
   - `job_matching.py` has a function to get an **OpenAI embedding** for the CV.
   - The code is not fully integrated into the job match queries yet, but the foundation is in place to do vector similarity (likely with `pgvector`).

---

## Embedding-Based Matching (Planned Enhancement)

Instead of manually parsing user queries with SQL LIKE filters, we plan to leverage OpenAI embeddings to handle free-text job searches. The core steps:

1. **Precompute and store embeddings** for each job (job_title + description + relevant metadata).
2. **On user queries**, generate an embedding of the user’s search text.
3. **Perform vector similarity** (e.g., cosine similarity) between the query embedding and job embeddings to find the top matches.
4. (Optionally) filter out results that do not meet strict constraints like location or salary.

We will use `text-embedding-ada-002` from OpenAI, which is cost-effective for up to tens of thousands of jobs. This approach reduces the complexity of manual search logic and better captures the semantic meaning of user queries.


## 7. Admin Dashboard Requirements

- **Streamlit** app in `admin_dashboard.py`:
  - **Metrics**: total users, active users, job searches in last 7 days.
  - **User activity**: recent interactions (username, last active time, messages sent).
  - **Logging**: real-time log viewer from SQLite and conversation logs.
  - **Database checks**: tests connections, shows errors, can export logs as JSON.

---

## 8. Logging & Monitoring

- **Structured Logging** via `python-json-logger` and custom `APILoggingMiddleware`.
- Logs stored in `logs/` plus a SQLite DB for the dashboard.
- Telegram interactions appended to `logs/conversations.log`.

---

## 9. Known Gaps & Future Scope

1. **More Advanced Matching**  
   - The current `LIKE`-based approach struggles with combined inputs like “manager or director.”
   - Future improvements might use embeddings (or trigram indexes) for more robust text matching.

2. **Better Fallback Logic**  
   - Need a progressive approach to relax constraints. Currently, fallback discards some filters completely.

3. **Additional Bot Integrations**  
   - Potential for a WhatsApp interface or other chat platforms.
   - Expand AI features for resume feedback and salary insights.

4. **Employer/Recruiter Monetization**  
   - Paid job listings, targeted candidate outreach, and sponsor-based alerts could be revenue sources in future.

---

## 10. Deployment & Environment

- **FastAPI** app on **Fly.io** using `fly.toml`.
- **PostgreSQL** database on **Render** using `DATABASE_URL`.
- **Telegram Bot** via `python-telegram-bot`.
- **Environment Variables** from `.env`:
  - `TELEGRAM_BOT_TOKEN`
  - `OPENAI_API_KEY`
  - `DATABASE_URL`
  - Plus optional admin IDs, etc.

---

## 11. Success Metrics (Short-Term)

- **User Engagement**  
  - At least 100 weekly active job seekers.
  - A majority able to complete `/search_jobs` or CV upload flows.

- **Match Relevance**  
  - Subjective measure: job listings must align well with user queries.

- **System Stability**  
  - Minimal downtime.
  - Adequate logging/error handling for quick fixes.
