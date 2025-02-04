# 📌 Product Requirements Document (PRD)
## AI-Powered Job Matching Bot for Accounting Professionals

---

## 1️⃣ Introduction
### 🔹 Problem Statement
Accounting professionals often struggle to find the right job opportunities. **Traditional job boards are inefficient**, requiring manual searches, irrelevant job alerts, and generic application processes. **Firms also struggle to reach the right talent**, leading to wasted time and resources.

### 🔹 Product Vision
The AI-powered job-matching bot **automates and personalizes the job search experience** for accountants. By integrating **AI-powered resume analysis, job matching, and career guidance**, it will provide **instant job recommendations**, **custom job alerts**, and **salary insights**. Over time, it will build a **high-value talent database**, enabling **better hiring decisions and monetization opportunities**.

---

## 2️⃣ Objectives & Goals
✅ **For Job Seekers**:  
- Automate **job discovery** using AI-powered CV matching.  
- Provide **personalized job alerts & recommendations**.  
- Offer **career insights** (salary benchmarking, career guidance).  

✅ **For Employers & Recruiters**:  
- Connect **top-matched candidates** with relevant job openings.  
- Allow **targeted outreach** to passive & active job seekers.  
- Create a **data-driven hiring experience**.  

✅ **For Platform Growth & Monetization**:  
- Build a **detailed accounting talent database**.  
- Enable **sponsored job alerts** & **premium career services**.  
- Offer **recruiter access** to AI-matched talent.  

---

## 3️⃣ Target Users & Roles
| **User Type** | **Role & Actions** |
|--------------|----------------- |
| 👩‍💼 **Job Seekers** | Upload CV, search jobs, subscribe to alerts, receive AI career insights |
| 🏢 **Accounting Firms & Recruiters** | Post jobs, access premium talent profiles, sponsor job alerts |
| 👨‍💻 **Admin (Dudley)** | Monitor engagement, track user growth, adjust AI matching logic |

---

## 4️⃣ Core Features for MVP (Minimum Viable Product)
### 🔹 Telegram Bot
✅ **Chat-based job search** (`/search_jobs`) – Users find jobs by role, location, salary.  
✅ **AI-powered job matching** (`/upload_cv`) – Users upload CVs → AI recommends best-fit jobs.  
✅ **Personalized job alerts** (`/set_alerts`) – Users get notified when relevant jobs appear.  

### 🔹 AI Job Matching Engine
✅ **Extract CV data** – AI reads resumes to understand experience & skills.  
✅ **Match CVs to jobs** – Uses AI embeddings to recommend the best roles.  

### 🔹 User Profile & Database
✅ **Auto-register users** when they interact with the bot.  
✅ **Store job preferences, skills, certifications** in PostgreSQL.  
✅ **Track engagement metrics** (messages sent, job searches, applications).  

### 🔹 Admin Dashboard (Fly.io)
✅ **Track user growth, engagement, job alert subscriptions.**  
✅ **View job search trends & AI job match performance.**  

### 🔹 Deployment & Integration
✅ **FastAPI backend (Fly.io) connected to PostgreSQL (Render).**  
✅ **Secure environment variable handling for API keys & DB credentials.**  
✅ **Seamless integration with accountingfirmjobs.com database.**  

---

## 5️⃣ Future Scope (Beyond MVP)
### 🔹 Phase 2: Advanced AI & User Experience
☑️ **Salary Insights** – AI predicts expected salary based on CV data.  
☑️ **Resume Feedback** – AI suggests improvements for a stronger CV.  
☑️ **Career Growth Tracking** – Alerts users when they should consider job changes.  
☑️ **Interview Prep Module** – AI generates mock interview questions.  

### 🔹 Phase 3: WhatsApp Bot Integration
☑️ **Launch WhatsApp bot (Meta Cloud API or Twilio).**  
☑️ **Sync user profiles between Telegram & WhatsApp.**  
☑️ **Enable opt-in job alerts via WhatsApp.**  

### 🔹 Phase 4: Recruiter & Firm Monetization
☑️ **Sponsored Job Alerts** – Employers pay to reach high-quality candidates.  
☑️ **Premium Talent Access** – Recruiters pay for access to AI-matched talent.  
☑️ **Employer Branding** – Firms can promote themselves inside the bot.  

---

## 6️⃣ User Journey
### 🔹 Job Seeker Flow
1. **User clicks Telegram link** → Bot registers them in the database.  
2. **User searches for jobs** (`/search_jobs`) → FastAPI fetches jobs from PostgreSQL.  
3. **User uploads CV** (`/upload_cv`) → AI extracts skills & experience.  
4. **Bot recommends best-matching jobs** using AI embeddings.  
5. **User subscribes to job alerts** (`/set_alerts`).  
6. **Bot sends job notifications based on preferences.**  

### 🔹 Admin Flow
1. **Admin logs into the Streamlit dashboard.**  
2. **Sees total users, active users, and job search trends.**  
3. **Adjusts AI job-matching logic if needed.**  
4. **Monitors engagement & subscription rates.**  

---

## 7️⃣ Tech Stack
| **Component** | **Technology** | **Hosting** |
|--------------|--------------|--------------|
| **Backend** | FastAPI (Python) | Fly.io |
| **Database** | PostgreSQL | Render |
| **AI Processing** | OpenAI API | N/A |
| **Bot API** | `python-telegram-bot` | Telegram |
| **Admin Dashboard** | Streamlit | Fly.io |
| **Future WhatsApp API** | Twilio / Meta Cloud API | WhatsApp |

---

## 8️⃣ Data Models
### 🔹 `users` Table (Tracks Users & Preferences)
```sql
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
    career_level TEXT NULL,
    job_type_preferences TEXT NULL,
    industry_preferences TEXT NULL,
    certifications TEXT NULL,
    skills TEXT NULL,
    salary_expectation TEXT NULL,
    career_goals TEXT NULL
);
```

### 🔹 `jobs` Table (Fetched from accountingfirmjobs.com)
```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    firm TEXT,
    job_title TEXT,
    seniority TEXT,
    service TEXT,
    industry TEXT,
    location TEXT,
    employment TEXT,
    salary TEXT,
    description TEXT,
    link TEXT,
    date_published TIMESTAMP,
    is_indexed BOOLEAN DEFAULT FALSE
);
```

---

## 9️⃣ Admin Dashboard Requirements
### 🔹 Core Metrics Display
- Total users count
- Active users in last 7 days
- Job search metrics
- User engagement statistics

### 🔹 Logging System
- Real-time log viewing
- Log level filtering
- Log export functionality
- Error tracking and monitoring

### 🔹 Database Management
- Connection pool monitoring
- Database URL validation
- Connection status checks
- Error rate monitoring

### 🔹 Error Handling & Recovery
- Automatic connection retry
- Graceful error handling
- User-friendly error messages
- Error notification system

---

## 📌 Next Steps
1️⃣ **Build & Deploy the Telegram bot with basic job search.**  
2️⃣ **Implement AI-powered job matching from CV uploads.**  
3️⃣ **Enhance user database to store detailed career insights.**  
4️⃣ **Launch the Streamlit admin dashboard for user monitoring.**  
5️⃣ **Expand to WhatsApp & explore monetization.**  
