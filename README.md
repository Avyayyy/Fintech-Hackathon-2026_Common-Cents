# Pinnacle — Wealth Wellness Hub
> FinTech Innovators Hackathon 2026

## 🚀 Live Demo
- **Frontend:** https://[your-team].github.io/[repo-name]
- **Backend API:** https://pinnacle-api.onrender.com

---

## 🗂️ Project Structure
```
├── index.html          ← Frontend (GitHub Pages)
├── app.py              ← Flask backend (Render)
├── requirements.txt    ← Python dependencies
├── render.yaml         ← Render auto-deploy config
└── README.md
```

---

## ⚙️ Deployment Guide

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 2 — Deploy Backend to Render (free)
1. Go to [render.com](https://render.com) and sign up (free, no credit card)
2. Click **New → Web Service**
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml` — just click **Deploy**
5. Wait ~2 minutes. Copy your service URL e.g. `https://pinnacle-api.onrender.com`

### Step 3 — Update Frontend with your Render URL
In `index.html`, find this line (~line 1295) and replace the URL:
```javascript
const API_BASE = 'https://pinnacle-api.onrender.com'; // ← paste your Render URL here
```
Commit and push:
```bash
git add index.html
git commit -m "Point frontend to live API"
git push
```

### Step 4 — Enable GitHub Pages
1. Go to your repo on GitHub
2. **Settings → Pages**
3. Source: **Deploy from a branch** → `main` → `/ (root)`
4. Click Save
5. Your site is live at `https://[username].github.io/[repo-name]`

---

## 🧑‍⚖️ For Judges
Just visit the GitHub Pages URL above — no installation needed.

The app works fully offline too (📴 badge) if the Render backend is sleeping.
Render's free tier sleeps after 15 min inactivity — first load may take ~30s to wake,
after which the ⚡ API badge will appear and all calculations run server-side.

---

## 🛠️ Run Locally
```bash
pip install -r requirements.txt
python app.py
# then open index.html in your browser
```

---

## 🔌 API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Liveness check |
| POST | `/api/wellness` | Calculate wellness scores |
| POST | `/api/scenario` | Run stress-test simulation |
