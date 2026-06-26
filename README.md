# 🤖 Next-Gen AI Framework — Autonomous D2C Operations & Resolution Agent

> **Enterprise-grade AI-powered customer support automation** that handles complex operational logistics and customer disputes autonomously using multi-agent orchestration with human oversight.

Built with **LangGraph** (stateful agent orchestration), **FastAPI** (simulated enterprise backend), and **Streamlit** (dual-panel operations dashboard).

---

## 💡 What Is This Project?

This is an **AI-powered customer support automation system** for e-commerce (D2C / Direct-to-Consumer) businesses. It automates the entire customer complaint lifecycle — from reading a complaint to processing refunds — in **under 5 seconds**, with built-in fraud detection and human oversight for risky cases.

### The Problem It Solves

E-commerce companies receive hundreds of customer complaints daily:
- *"My order says delivered but I never got it!"*
- *"I want a refund, the product is broken!"*
- *"My shipment has been stuck for 2 weeks!"*

Hiring humans to handle all of these is **expensive** ($1.3 trillion/year globally) and **slow** (24-hour average response time). This system automates 80% of tickets while ensuring risky cases still get human review.

### What the AI Does Automatically

1. **Reads the complaint** — understands intent, sentiment, and urgency
2. **Identifies the order** — extracts order/tracking IDs via regex pattern matching
3. **Checks courier tracking** — queries FedEx/DHL/UPS APIs for delivery status
4. **Detects delivery anomalies** — e.g., "tracking says Delivered but customer says not received"
5. **Auto-files carrier disputes** — demands GPS coordinates and delivery proof
6. **Evaluates fraud risk** — checks lifetime return rate, risk history tags, and order value
7. **Processes refunds** — within company policy limits (auto-refund cap)
8. **Escalates risky cases** — pauses execution and sends to a human manager for approval
9. **Writes a personalized reply** — adapts tone based on customer sentiment and communication channel

---

## 🌍 Real-World Applications

| Who Would Use This | How |
|---|---|
| **E-commerce startups** (Shopify/WooCommerce stores) | Automate 80% of customer support tickets without hiring agents |
| **Large retailers** (Amazon, Flipkart-scale companies) | Handle thousands of complaints per day with AI + human oversight |
| **Logistics companies** | Auto-detect delivery anomalies and file carrier disputes |
| **Fintech / Payment companies** | Auto-process refunds within policy limits, flag fraud |
| **Any company with a support team** | Reduce response time from 24 hours to 3 seconds |

### Industry Impact
- Companies spend **$1.3 trillion/year** on customer service globally
- AI automation reduces support costs by **30-50%**
- Average response time drops from **24 hours → under 5 seconds**

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
│       └──── (general) ───────────────▶├─── (low) ──▶│      │
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

## 🚀 How to Run

### Option A: Standalone HTML Prototype (Zero Setup — 1 Click!)

A fully interactive web prototype that runs the entire multi-agent logic in the browser with **zero dependencies, no server, no API keys**.

**Just double-click `prototype.html`** in your file explorer — it opens in Chrome/Edge/Firefox.

---

### Option B: Full Python Stack (Backend + Streamlit Dashboard)

#### Prerequisites
- **Python 3.10+** installed ([python.org](https://python.org))
- A terminal / command prompt

#### Step 1: Install Dependencies
```bash
cd "Autonomous system"
pip install -r requirements.txt
```

#### Step 2: Start the Backend API Server (Terminal 1)
```bash
python backend.py
```
> ✅ You should see: `Uvicorn running on http://0.0.0.0:8000`
> 📖 API docs available at: http://localhost:8000/docs

#### Step 3: Start the Streamlit Dashboard (Terminal 2)
```bash
python -m streamlit run app.py
```
> ✅ You should see: `You can now view your Streamlit app at http://localhost:8501`

#### Step 4: Open Your Browser
Go to **http://localhost:8501** — the dashboard loads automatically.

> ⚠️ **Important:** Always start `backend.py` FIRST, then `app.py`. The dashboard needs the backend API to be running.

#### Stopping the Servers
Press `Ctrl+C` in each terminal to stop. If port 8000 is busy from a previous run:
```bash
# Windows — kill the process using port 8000
taskkill /F /IM python.exe
```

---

## 🧪 How to Use — Quick Test Scenarios

Click any scenario button in the dashboard to instantly process a ticket:

| Scenario | Order | What Happens |
|---|---|---|
| **🚫 Delivered Not Received** | #1004 | Courier dispute auto-filed (GPS demanded), full refund processed |
| **🔴 High-Risk Refund Request** | #1002 | 45% return rate → **HIGH RISK** → pauses for manager approval (HITL) |
| **⏳ Delayed Shipment** | #1005 | Stuck-Delayed status detected, $25 shipping credit applied |
| **💸 High-Value Order Concern** | #1003 | $249.99 exceeds auto-refund cap → escalated for HITL approval |
| **📦 RTO / Failed Delivery** | #1006 | Return-to-Origin detected, reship or refund offered |
| **😊 Polite General Inquiry** | #1001 | Low risk, informational response, no financial action needed |

### How to Demo (5-Minute Script)
1. Click **"Delivered Not Received"** — watch the AI resolve it in ~3 seconds
2. Click **"Agent Trace"** tab (right panel) — see the AI's decision-making process
3. Click **"High-Risk Refund"** — watch it pause and show in the **Approval Queue**
4. Click **"✅ Approve"** or **"❌ Reject"** — watch the system resume based on your decision
5. Check **"System Logs"** tab — see all disputes filed and refunds processed

---

## 🧠 Agent Nodes (How the AI Thinks)

### 1. 🎯 Triage & Intent Orchestrator
- Extracts order/tracking IDs via regex pattern matching
- Classifies customer sentiment: `angry`, `frustrated`, `neutral`, `polite`
- Determines issue type: `delivery_not_received`, `damaged_item`, `wrong_item`, `late_delivery`, `return_request`, `general_inquiry`
- Fetches company policy via dynamic Policy Engine (simulated RAG)

### 2. 🚚 Logistics Investigator
- Queries carrier tracking APIs (FedEx, UPS, DHL, USPS)
- Detects delivery anomalies (e.g., carrier says "Delivered" but customer says "not received")
- Auto-files carrier disputes demanding GPS coordinates and delivery photos

### 3. 🛡️ Fraud & Risk Assessment Agent
- Evaluates **lifetime return rate** (threshold: 40%)
- Checks order amount against **auto-refund limits** ($75 standard, varies by policy)
- Reviews historical risk tags (`frequent_returner`, `chargeback_2024`, `address_mismatch`)
- Calculates composite risk score: `LOW`, `MEDIUM`, or `HIGH`
- Flags **HIGH RISK** → triggers Human-in-the-Loop (HITL) approval gate

### 4. 💰 Financial Adjuster & Communication Engine
- Processes refunds within company policy limits
- Issues shipping credits for late deliveries
- Generates empathetic, channel-aware customer responses
- Adapts tone to match customer sentiment (angry customers get more empathetic replies)

---

## 🔐 Human-in-the-Loop (HITL) — How It Works

The system uses LangGraph's `interrupt()` / `Command(resume=...)` pattern for human oversight:

```
1. Fraud Agent flags HIGH RISK  →  sets approval_required = True
2. HITL Gate node calls interrupt()  →  graph execution PAUSES
3. Ops Panel shows ticket in Approval Queue with risk details
4. Manager clicks ✅ Approve or ❌ Reject
5. Frontend calls Command(resume="approved" | "rejected")
6. Graph RESUMES  →  Financial Adjuster processes accordingly
```

**Why this matters:** Unlike fully automated systems, HITL ensures that no high-risk financial action (large refunds, suspicious returns) happens without human oversight. This prevents fraud and reduces financial losses.

---

## 📁 Project Structure

```
Autonomous system/
├── agents.py           # LangGraph multi-agent engine (4 AI agents + routing)
├── app.py              # Streamlit dual-panel dashboard (port 8501)
├── backend.py          # FastAPI mock API server (port 8000)
├── policy_engine.py    # Dynamic company policy lookup (simulated RAG)
├── prototype.html      # Standalone HTML/JS demo (no backend needed)
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Agent Orchestration | **LangGraph** | Stateful graph with conditional routing, HITL interrupts |
| Backend API | **FastAPI + Uvicorn** | Mock Shopify, logistics, and payment APIs |
| Frontend Dashboard | **Streamlit** | Dual-panel operations dashboard |
| HTTP Client | **httpx** | Async agent-to-backend API communication |
| State Persistence | **MemorySaver** | In-memory checkpointing for HITL pause/resume |
| Policy Engine | **Custom Python** | Simulated RAG vector-lookup for company policies |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| `[Errno 10048] address already in use` | Another backend is still running. Run `taskkill /F /IM python.exe` to kill all Python processes, then restart. |
| `streamlit: not recognized` | Use `python -m streamlit run app.py` instead of `streamlit run app.py` |
| IDE shows red errors on imports | Your IDE is using the wrong Python interpreter. Press `Ctrl+Shift+P` → "Python: Select Interpreter" → choose `C:\Python314\python.exe` |
| `Pydantic V1 compatibility warning` | Harmless warning with Python 3.14. Does not affect functionality. |
| Scenario buttons don't respond | Make sure the backend is running on port 8000 first. The Streamlit app needs the backend API to process tickets. |

---

## 🔑 Key Concepts for Interviews

| Concept | Explanation |
|---|---|
| **Multi-Agent Architecture** | Instead of one monolithic AI, we use 4 specialized agents (Triage, Logistics, Fraud, Financial) that collaborate through a state graph |
| **Human-in-the-Loop (HITL)** | AI doesn't blindly approve everything — risky cases pause for human review, balancing automation with safety |
| **Stateful Graph Execution** | LangGraph maintains state across node transitions, enabling complex workflows with conditional branching |
| **Policy-Driven Decisions** | All financial limits and risk thresholds come from a centralized Policy Engine (simulating RAG), not hardcoded values |
| **Channel-Aware Communication** | The AI adapts its response format based on channel (Email = formal, WhatsApp = casual, Web Chat = balanced) |

---

## 📝 License

Built for project demonstration purposes.
