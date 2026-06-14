# 🤖 Autonomous D2C Operations & Resolution Agent

> **Enterprise-grade back-office automation engine** that handles complex operational logistics and customer disputes autonomously using multi-agent orchestration.

Built with **LangGraph** (stateful agent orchestration), **FastAPI** (simulated enterprise backend), and **Streamlit** (dual-panel operations dashboard).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT FRONTEND                        │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  Panel A: Customer   │  │  Panel B: Ops & HITL Center  │ │
│  │  Simulator           │  │  • Approval Queue            │ │
│  │  • Channel Select    │  │  • Agent Trace Timeline      │ │
│  │  • Complaint Input   │  │  • Approve/Reject Buttons    │ │
│  │  • Chat History      │  │  • Dispute & Refund Logs     │ │
│  └──────────┬───────────┘  └──────────────┬───────────────┘ │
└─────────────┼──────────────────────────────┼────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   LANGGRAPH AGENT ENGINE                     │
│                                                             │
│  ┌─────────┐   ┌───────────┐   ┌────────────┐   ┌────────┐│
│  │ Triage  │──▶│ Logistics │──▶│ Fraud/Risk │──▶│ HITL   ││
│  │ Agent   │   │ Agent     │   │ Agent      │   │ Gate   ││
│  └────┬────┘   └───────────┘   └──────┬─────┘   └───┬────┘│
│       │                               │             │      │
│       └──── (general) ────────────────▶├─── (low) ──▶│      │
│                                       │             ▼      │
│                                  ┌────┴─────────────────┐  │
│                                  │ Financial Adjuster & │  │
│                                  │ Communication Engine │  │
│                                  └──────────────────────┘  │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                  FASTAPI MOCK BACKEND                        │
│  GET  /api/shopify/order/{id}    — Order details            │
│  GET  /api/logistics/track/{id}  — Tracking status          │
│  POST /api/logistics/dispute     — File carrier dispute     │
│  POST /api/shopify/refund        — Process refund           │
│  GET  /api/admin/disputes        — All disputes (ops view)  │
│  GET  /api/admin/refunds         — All refunds (ops view)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Create & Activate Virtual Environment

```bash
cd "c:\Users\harsh\Desktop\Autonomous system"
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Backend (Terminal 1)

```bash
python backend.py
```
> Backend runs on `http://localhost:8000` — Swagger docs at `/docs`

### 4. Start the Frontend (Terminal 2)

```bash
streamlit run app.py
```
> Dashboard opens at `http://localhost:8501`

---

## 🧪 Test Scenarios

| Scenario | Order | What Happens |
|---|---|---|
| **Delivered Not Received** | #1004 | Courier dispute auto-filed, GPS demanded, refund processed |
| **High-Risk Refund** | #1002 | 45% return rate → HIGH RISK → HITL gate → manager approval |
| **Delayed Shipment** | #1005 | Stuck-Delayed status detected, shipping credit applied |
| **High-Value Return** | #1003 | $249.99 exceeds auto-refund cap → HITL approval required |
| **RTO / Failed Delivery** | #1006 | Return-to-Origin detected, reship or refund offered |
| **General Inquiry** | #1001 | Low risk, informational response, no financial action |

---

## 🧠 Agent Nodes

### 1. Triage & Intent Orchestrator
- Extracts order/tracking IDs via regex
- Classifies customer sentiment (angry, frustrated, neutral, polite)
- Determines issue type (delivery, damage, return, delay, general)
- Fetches company policy via dynamic Policy Engine

### 2. Logistics Investigator
- Queries carrier tracking APIs
- Detects delivery anomalies (delivered vs. not received)
- Auto-files carrier disputes demanding GPS coordinates

### 3. Fraud & Risk Agent
- Evaluates lifetime return rate (threshold: 40%)
- Checks order amount against auto-refund limits
- Reviews historical risk tags
- Flags HIGH RISK → triggers HITL approval gate

### 4. Financial Adjuster & Communication Engine
- Processes refunds within policy limits
- Generates empathetic, channel-aware responses
- Adapts tone to customer sentiment

---

## 🔐 Human-in-the-Loop (HITL)

The system uses LangGraph's `interrupt()` / `Command(resume=...)` pattern:

1. **Fraud Agent flags HIGH RISK** → sets `approval_required = True`
2. **HITL Gate node calls `interrupt()`** → graph execution **pauses**
3. **Ops Panel shows ticket** in approval queue with risk details
4. **Manager clicks Approve/Reject** → frontend calls `Command(resume="approved"|"rejected")`
5. **Graph resumes** → Financial Adjuster processes accordingly

---

## 📁 Project Structure

```
Autonomous system/
├── backend.py          # FastAPI mock API server (port 8000)
├── agents.py           # LangGraph multi-agent engine
├── policy_engine.py    # Dynamic company policy lookup
├── app.py              # Streamlit dual-panel frontend (port 8501)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Agent Orchestration | LangGraph | Stateful graph with conditional routing & HITL |
| Backend API | FastAPI + Uvicorn | Mock enterprise endpoints |
| Frontend | Streamlit | Dual-panel operations dashboard |
| HTTP Client | httpx | Agent-to-backend communication |
| State Persistence | MemorySaver | In-memory checkpointing for HITL |

---

## 📝 License

Built for Amazon internship project demonstration purposes.
