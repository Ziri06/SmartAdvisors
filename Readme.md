# Smart Advisors

A UTA course recommendation app that helps students plan their degree. Upload a transcript PDF, select your major, set preferences, and get personalized professor and course recommendations.

## Supported Majors
- Computer Science and Engineering (CSE)
- Civil Engineering (CE)
- Electrical Engineering (EE)
- Mechanical/Aerospace Engineering (MAE)
- Industrial Engineering (IE)

---

## Project Structure

```
SmartAdvisors/
├── client/                          # React/TypeScript frontend (Vite)
│   ├── src/
│   │   ├── App.tsx                  # Main app orchestrator (step flow)
│   │   └── components/
│   │       ├── WelcomePage.tsx       # Landing page
│   │       ├── UploadScreen.tsx      # Transcript upload + major selection
│   │       ├── PreferenceForm.tsx    # Student preference sliders
│   │       ├── TranscriptReview.tsx  # Review parsed courses
│   │       └── RecommendationDashboard.tsx  # Results display
│   ├── package.json
│   └── vite.config.ts
│
├── server/                          # Flask/Python backend
│   ├── run.py                       # Entry point — starts Flask on port 8000
│   ├── app/
│   │   ├── __init__.py              # Flask app factory
│   │   ├── routes.py                # API endpoints (/api/parse-transcript, /api/recommendations)
│   │   ├── config.py                # Flask configuration
│   │   ├── models.py                # SQLAlchemy models (professors.db)
│   │   └── scripts/
│   │       ├── parse_transcript.py          # PDF transcript parser
│   │       ├── recommendation_engine.py     # Core algorithm (prereq expansion, eligibility, professor matching)
│   │       ├── load_degree_plan.py          # Loads CSV degree plans into classes.db
│   │       └── scrape_uta_catalog.py        # Tool to generate CSVs from UTA catalog
│   └── data/
│       ├── classes.db               # Degree plan tables (ClassesForCE, ClassesForCSE, etc.)
│       ├── grades.sqlite            # UTA grade distribution data
│       ├── professors.db            # RateMyProfessors data
│       ├── CE Degree Plan CSV.csv   # Degree plan CSVs (one per major)
│       ├── CSE Degree Plan CSV.csv
│       ├── EE Degree Plan CSV.csv
│       ├── MAE Degree Plan CSV.csv
│       └── IE Degree Plan CSV.csv
│
├── requirements.txt                 # Python dependencies
└── .env.example                     # Environment variable template
```

---

## Getting Started

### Prerequisites
- **Git**
- **Node.js 18+** and npm
- **Python 3.10+**

### Clone the Repo

```bash
git clone https://github.com/acmuta/SmartAdvisors.git
cd SmartAdvisors
```

### Frontend Setup

```bash
cd client
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**

### Backend Setup

```bash
cd server
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r ../requirements.txt
python3 run.py
```

Backend runs at **http://127.0.0.1:8000**

### Environment Variables

You do **not** need a `.env` file to run locally. The backend auto-detects database paths. If you want to customize, copy the example:

```bash
cp .env.example .env
```

---

## How It Works

1. **Upload Transcript** — Student uploads a UTA transcript PDF
2. **Select Major** — Choose from CE, CSE, EE, MAE, or IE
3. **Set Preferences** — Toggle preferences like extra credit, clear grading, etc.
4. **Get Recommendations** — App shows eligible courses split into:
   - **Required Courses** (blue) — courses you still need for your degree
   - **Elective Options** (orange) — electives you're eligible to take
5. Each course card shows:
   - Credit hours
   - Corequisites (if any)
   - Top professors ranked by match score, rating, and difficulty
   - Grade distributions and RateMyProfessors tags

### Algorithm Overview
- Parses transcript to extract completed courses
- Expands completed set with transitive prerequisites (e.g., if you took Calc II, infers Calc I)
- Filters degree plan to find courses where all prerequisites are satisfied
- Looks up professors from grade distribution and RateMyProfessors data
- Scores and ranks professors based on student preferences

---

## Databases

All databases are included in the repo under `server/data/`. No external database setup required.

| Database | Contents |
|---|---|
| `classes.db` | Degree plan tables for each major (courses, prerequisites, corequisites, credit hours) |
| `grades.sqlite` | UTA grade distribution data (course offerings, GPAs, instructor names) |
| `professors.db` | RateMyProfessors data (ratings, difficulty, tags) |

### Updating Degree Plans

Degree plans are defined in CSV files (`server/data/`). To reload after editing a CSV:

```bash
cd server
source venv/bin/activate
python3 -c "from app.scripts.load_degree_plan import load_all; load_all()"
```

CSV format:
```
Formal Name,Course Name,Prerequisites,Corequisites,Requirement
CSE 1310,Introduction to Computers and Programming,[None],[None],required
CSE 4303,Computer Graphics,"CSE 3380, CSE 3318, MATH 3330",[None],elective
```

---

## API Endpoints

### POST `/api/parse-transcript`
Upload a transcript PDF to extract completed courses.

**Request:** `multipart/form-data` with `file` field

**Response:**
```json
{
  "success": true,
  "courses": ["CSE 1310", "CSE 1320", "MATH 1426", ...]
}
```

### POST `/api/recommendations`
Get course and professor recommendations.

**Request:**
```json
{
  "completedCourses": ["CSE 1310", "CSE 1320"],
  "department": "CSE",
  "preferences": { "extraCredit": true, "clearGrading": true, ... }
}
```

**Response:**
```json
{
  "success": true,
  "recommendations": [...],
  "electiveRecommendations": [...],
  "stats": {
    "totalRequiredCourses": 30,
    "totalRequiredHours": 95,
    "completedRequiredCourses": 12,
    "completedRequiredHours": 38,
    "totalElectiveSlots": 7,
    "totalElectiveHours": 21,
    "completedElectives": 0,
    "completedElectiveHours": 0,
    "remainingElectiveSlots": 7
  }
}
```

---

## Repo Conventions

### Commits
Use Conventional Commits:
- `feat(ui): add dark mode toggle`
- `fix(api): handle null user_id on login`
- `docs(readme): clarify quickstart`

### Pull Requests
- Small, focused PRs preferred
- Link issues with `Fixes #123`
- Include testing steps and screenshots for UI changes

### Secrets
- Never commit `.env` or credentials
- Use `.env` locally; keep `.env.example` updated

---

## Status & Links
- **Phase:** In Development
- **Communication:** Discord #smart-advisors
- **Open issues:** Use repo Issues tab

## Maintainers
- Kanishkar Manoj ([@kanishkarmanoj](https://github.com/kanishkarmanoj))
- Directors / Contacts: Tobi and Prajit Viswanadha — DM on Discord
