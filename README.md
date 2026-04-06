# Predictive Deployment Control Using User Confusion Signals

**The idea:** Instead of waiting for server errors after a bad deploy, this system
watches how users behave and rolls back automatically — before any crash happens.

---

## Two VMs Setup

| VM | Role | Runs |
|---|---|---|
| VM1 (jenkins-server) | CI/CD brain | Jenkins + Maven + Ansible |
| VM2 (app-server) | App | FastAPI + Streamlit + Demo pages |

---

## Port Reference

| Port | What | VM |
|---|---|---|
| 8080 | Jenkins UI | VM1 |
| 8000 | FastAPI backend + live app | VM2 |
| 8501 | Streamlit dashboard | VM2 |
| 5000 | Frontend demo trigger page | VM2 |

---

## Quick Start (Local)

```bash
# Install Python deps
pip install -r requirements.txt

# Start backend (terminal 1)
cd backend
python -m uvicorn main:app --reload --port 8000

# Start dashboard (terminal 2)
streamlit run dashboard/app.py

# Start frontend (terminal 3)
cd frontend
python -m http.server 5000
```

Open:
- `http://localhost:8000/app` → v2 broken app
- `http://localhost:8501` → dashboard
- `http://localhost:5000` → demo trigger page

---

## Quick Start (Azure — Docker)

```bash
docker compose up
```

---

## Install Maven + Ansible on VM1 (while Jenkins is running)

```bash
sudo apt update
sudo apt install -y maven ansible python3 python3-pip
pip3 install --break-system-packages fastapi uvicorn pymongo pytest httpx requests pydantic
```

No restart needed for the installation. Restart Jenkins once after to pick up the tools.

---

## Pipeline Stages

1. **Checkout** — pull code from GitHub
2. **Maven + Java Tests** — JUnit tests calling FastAPI endpoints
3. **Python Tests** — pytest on confusion engine and pattern analyzer
4. **Ansible Deploy** — copy files to VM2, start all services (v2 goes live)
5. **Behavioral Gate** — query /score/latest; if ≥ 70 → Ansible rollback to v1

---

## The Two App Versions

**v2 (broken)** — dark purple/black QuikShop — 4 payment buttons, all fail with different errors

**v1 (stable)** — clean white/blue NovaBuy — 1 payment button, instant confirmation

Rollback switches `frontend/active_version.txt` from `v2` to `v1`.
FastAPI reads that file on every `/app` request — change is instant.

---

## Demo in 3 Steps

```bash
# 1. Reset to broken state
curl -X POST http://VM2-IP:8000/reset-version

# 2. Open broken app and interact (or force trigger)
open http://VM2-IP:8000/app

# 3. Watch Jenkins rollback, then refresh
open http://VM2-IP:8501
```

---

## See PROJECT_INFO.md for:
- All questions answered (Maven role, Ansible role, 2 VMs reason, port meanings)
- Step-by-step next steps from "Jenkins installed" state
- Every file and function explained
- Full demo script
- Patent claim text
