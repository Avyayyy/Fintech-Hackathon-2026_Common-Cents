# Pinnacle — Wealth Wellness Hub
> FinTech Innovators Hackathon 2026 | Team Common Cents

---

## 📖 About

Pinnacle is a Wealth Wellness Hub built for the FinTech Innovators Hackathon 2026 by team Common Cents.

Investors today manage wealth across fragmented ecosystems—bank deposits, investment portfolios, real estate, and digital assets—with no unified view of their overall financial health. Pinnacle solves this by aggregating all asset classes into a single, intelligent Wealth Wallet.

The platform delivers four key capabilities: **Unify** — consolidate traditional and digital assets into one dashboard; **Analyse** — score financial wellness across diversification, liquidity, volatility, and behavioural resilience; **Visualise** — track wealth composition and health trends over time; and **Recommend** — run AI-powered stress tests and receive personalised, actionable insights.

Built with a Flask backend (PostgreSQL on Render) and a responsive vanilla JS frontend (GitHub Pages), Pinnacle works fully offline as a fallback, ensuring reliability for any user. A live demo account is available for judges to explore immediately.

Pinnacle empowers both retail investors and financial advisers to assess opportunities, identify risks, and build long-term financial resilience—all through a single intuitive interface.

---

## 🚀 Live Demo

- **Frontend:** https://avyayyy.github.io/FinTech-Innovators-Hackathon-2026_Common-Cents/
- **Backend API:** https://fintech-hackathon-2026-common-cents.onrender.com

### 🔑 Judge Demo Account
| Field | Value |
|-------|-------|
| Email | alex@gmail.com |
| Password | alex12345 |

Use the demo account to explore a pre-populated portfolio with 3 years of historical assets and wealth data, showcasing the full range of Pinnacle's dashboard, wellness scoring, and scenario simulation features. Alternatively, create a new account to experience the onboarding questionnaire and set up a portfolio from scratch. 

---

## 🗂️ Project Structure

```
├── index.html          ← Frontend (GitHub Pages)
├── app.py              ← Flask backend (Render)
├── requirements.txt    ← Python dependencies
├── render.yaml         ← Render auto-deploy config
├── Procfile            ← Gunicorn start command
└── README.md
```

---

## 🛠️ Technologies Used

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, Vanilla JavaScript |
| Backend | Python, Flask, Flask-CORS |
| Database | SQLite (local), PostgreSQL (production) |
| Hosting | GitHub Pages (frontend), Render (backend) |
| Fonts | Sora, IBM Plex Mono (Google Fonts) |
| Auth | HMAC-SHA256 token-based authentication |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Liveness check |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user data |
| POST | `/api/auth/save` | Save portfolio changes |
| POST | `/api/wellness` | Calculate wellness scores |
| POST | `/api/scenario` | Run stress-test simulation |
| GET/POST | `/api/seed-demo` | Seed judge demo account |

---

## ⚙️ Run Locally

```bash
pip install -r requirements.txt
python app.py
# then open index.html in your browser
```

---

## 🧑‍⚖️ For Judges
Visit the live frontend link above—no installation required. Log in with the demo account credentials to explore a pre-populated portfolio. The backend is kept alive via a cron job, so there should be no cold start delay.
