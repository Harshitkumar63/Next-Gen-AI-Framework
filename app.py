"""
=============================================================================
 STREAMLIT DUAL-PANEL FRONTEND — D2C Operations Dashboard
=============================================================================
 Panel A (Left): Customer Simulator — submit tickets, view agent responses
 Panel B (Right): Operations & HITL Control Center — approve/reject, view traces

 Run:  streamlit run app.py
 Requires: backend.py running on port 8000
=============================================================================
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
import streamlit as st
from langgraph.types import Command

# ── Must be FIRST Streamlit call ─────────────────────────────────────────────
st.set_page_config(
    page_title="D2C Operations Agent — Command Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Import agent graph AFTER page config
from agents import build_graph

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("frontend")

BACKEND_URL = "http://localhost:8000"

# =============================================================================
#  SESSION STATE INITIALIZATION
# =============================================================================


def init_session_state():
    """Initialize all session state variables on first run."""
    defaults = {
        "messages": [],  # Chat history: [{"role": "user"|"assistant", "content": str}]
        "active_tickets": {},  # Tickets awaiting HITL: {thread_id: {...}}
        "completed_tickets": [],  # Resolved tickets
        "thread_counter": 0,  # Incrementing thread ID
        "graph": None,  # Compiled LangGraph instance
        "checkpointer": None,  # MemorySaver instance
        "processing": False,  # Prevent double-submit
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Build graph once per session
    if st.session_state.graph is None:
        g, cp = build_graph()
        st.session_state.graph = g
        st.session_state.checkpointer = cp


init_session_state()


# =============================================================================
#  HELPER FUNCTIONS (must be defined before UI code calls them)
# =============================================================================


def _handle_completed_ticket(result: dict, thread_id: str, complaint: str, channel: str):
    """Process a completed graph result into chat messages and logs."""
    response = result.get("final_draft_response", "No response generated.")

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
    })

    # Store in completed tickets with full trace
    st.session_state.completed_tickets.append({
        "thread_id": thread_id,
        "complaint": complaint,
        "channel": channel,
        "result": result,
        "resolved_at": datetime.now(tz=timezone.utc).strftime("%H:%M:%S"),
    })

    logger.info(f"[Frontend] ✅ Ticket {thread_id} resolved")


def _resume_graph(thread_id: str, decision: str):
    """
    Resumes a paused LangGraph execution with the manager's decision.
    Uses Command(resume=...) to pass the decision back to the interrupt() call.
    """
    ticket = st.session_state.active_tickets.get(thread_id)
    if not ticket:
        st.error(f"Ticket {thread_id} not found!")
        return

    config = ticket["config"]
    logger.info(f"[Frontend] ▶️ Resuming ticket {thread_id} with decision: {decision}")

    try:
        with st.spinner(f"Processing {decision} decision..."):
            result = st.session_state.graph.invoke(
                Command(resume=decision),
                config=config,
            )

        # Move from active to completed
        response = result.get("final_draft_response", "Decision processed.")

        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"{'✅' if decision == 'approved' else '❌'} "
                f"**Manager Decision: {decision.upper()}**\n\n{response}"
            ),
        })

        st.session_state.completed_tickets.append({
            "thread_id": thread_id,
            "complaint": ticket["complaint"],
            "channel": ticket["channel"],
            "result": result,
            "resolved_at": datetime.now(tz=timezone.utc).strftime("%H:%M:%S"),
            "hitl_decision": decision,
        })

        del st.session_state.active_tickets[thread_id]

        logger.info(f"[Frontend] ✅ Ticket {thread_id} resolved after HITL {decision}")
        st.rerun()

    except Exception as e:
        logger.error(f"[Frontend] ❌ Resume error: {e}")
        st.error(f"Error resuming graph: {str(e)}")


# =============================================================================
#  CUSTOM CSS — Premium Dark Theme
# =============================================================================

st.markdown("""
<style>
    /* ── Import Google Font ──────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Global Overrides ────────────────────────────────────────────── */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ── Header Banner ───────────────────────────────────────────────── */
    .header-banner {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .header-banner h1 {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .header-banner p {
        color: rgba(255, 255, 255, 0.65);
        font-size: 0.9rem;
        margin: 0.3rem 0 0 0;
    }

    /* ── Panel Headers ───────────────────────────────────────────────── */
    .panel-header {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
        padding: 1rem 1.25rem;
        border-radius: 12px;
        border-left: 4px solid #6366f1;
        margin-bottom: 1rem;
    }
    .panel-header h2 {
        color: #e2e8f0;
        font-size: 1.15rem;
        font-weight: 600;
        margin: 0;
    }
    .panel-header p {
        color: rgba(255, 255, 255, 0.5);
        font-size: 0.8rem;
        margin: 0.2rem 0 0 0;
    }

    /* ── Ticket Cards ────────────────────────────────────────────────── */
    .ticket-card {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(220, 38, 38, 0.04));
        border: 1px solid rgba(239, 68, 68, 0.25);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .ticket-card:hover {
        border-color: rgba(239, 68, 68, 0.5);
        box-shadow: 0 4px 20px rgba(239, 68, 68, 0.15);
    }
    .ticket-card h4 {
        color: #fca5a5;
        margin: 0 0 0.5rem 0;
        font-size: 0.95rem;
    }
    .ticket-card p {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.82rem;
        margin: 0.2rem 0;
    }

    /* ── Step Timeline ───────────────────────────────────────────────── */
    .step-item {
        background: rgba(255, 255, 255, 0.03);
        border-left: 3px solid #6366f1;
        padding: 0.6rem 1rem;
        margin-bottom: 0.4rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.78rem;
        color: rgba(255, 255, 255, 0.8);
        font-family: 'Inter', monospace;
        transition: all 0.2s ease;
    }
    .step-item:hover {
        background: rgba(99, 102, 241, 0.08);
        border-left-color: #818cf8;
    }

    /* ── Status Badges ───────────────────────────────────────────────── */
    .badge-high {
        background: linear-gradient(135deg, #dc2626, #b91c1c);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-low {
        background: linear-gradient(135deg, #16a34a, #15803d);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-pending {
        background: linear-gradient(135deg, #d97706, #b45309);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ── Scenario Buttons ────────────────────────────────────────────── */
    .scenario-btn {
        background: rgba(99, 102, 241, 0.1);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .scenario-btn:hover {
        background: rgba(99, 102, 241, 0.2);
        border-color: rgba(99, 102, 241, 0.5);
    }

    /* ── Metrics Row ─────────────────────────────────────────────────── */
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .metric-card h3 {
        color: #6366f1;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }
    .metric-card p {
        color: rgba(255, 255, 255, 0.5);
        font-size: 0.75rem;
        margin: 0.3rem 0 0 0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ── Divider ─────────────────────────────────────────────────────── */
    .divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.3), transparent);
        margin: 1.5rem 0;
    }

    /* ── Hide Streamlit branding ─────────────────────────────────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# =============================================================================
#  HEADER
# =============================================================================

st.markdown("""
<div class="header-banner">
    <h1>🤖 Autonomous D2C Operations & Resolution Agent</h1>
    <p>Enterprise-Grade Multi-Agent System • LangGraph • Human-in-the-Loop Guardrails</p>
</div>
""", unsafe_allow_html=True)

# ── Metrics Row ──────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <h3>{len(st.session_state.completed_tickets)}</h3>
        <p>Tickets Resolved</p>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <h3>{len(st.session_state.active_tickets)}</h3>
        <p>Awaiting Approval</p>
    </div>
    """, unsafe_allow_html=True)

with m3:
    # Fetch dispute count from backend
    try:
        disputes = httpx.get(f"{BACKEND_URL}/api/admin/disputes", timeout=3).json()
        dispute_count = disputes.get("total", 0)
    except Exception:
        dispute_count = 0
    st.markdown(f"""
    <div class="metric-card">
        <h3>{dispute_count}</h3>
        <p>Disputes Filed</p>
    </div>
    """, unsafe_allow_html=True)

with m4:
    try:
        refunds = httpx.get(f"{BACKEND_URL}/api/admin/refunds", timeout=3).json()
        refund_count = refunds.get("total", 0)
    except Exception:
        refund_count = 0
    st.markdown(f"""
    <div class="metric-card">
        <h3>{refund_count}</h3>
        <p>Refunds Processed</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)


# =============================================================================
#  DUAL-PANEL LAYOUT
# =============================================================================

panel_a, spacer, panel_b = st.columns([55, 2, 43])


# ─────────────────────────────────────────────────────────────────────────────
#  PANEL A: CUSTOMER SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────

with panel_a:
    st.markdown("""
    <div class="panel-header">
        <h2>🎧 Panel A — Customer Simulator</h2>
        <p>Submit support tickets and view agent responses</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Channel Selection ─────────────────────────────────────────────────
    channel = st.selectbox(
        "📱 Communication Channel",
        ["Web Chat", "Email", "WhatsApp"],
        key="channel_select",
        help="Select the customer's contact channel. Affects response tone and format.",
    )

    # ── Quick Scenarios ───────────────────────────────────────────────────
    st.markdown("**⚡ Quick Test Scenarios:**")

    scenarios = {
        "🚫 Delivered Not Received (Order #1004)": (
            "My order #1004 says delivered but I haven't received it! "
            "I've checked everywhere and nothing. I want my money back immediately! "
            "This is unacceptable!"
        ),
        "🔴 High-Risk Refund Request (Order #1002)": (
            "I want a full refund for order #1002. The product is not what I expected "
            "and I demand my money back right now. This is ridiculous!"
        ),
        "⏳ Delayed Shipment (Order #1005)": (
            "Where is my order #1005?! It's been delayed for weeks and I'm still "
            "waiting. This is very frustrating. Can someone please help?"
        ),
        "💸 High-Value Order Concern (Order #1003)": (
            "I need to return order #1003. The headphones are not working properly. "
            "I paid $250 for this and I expect a full refund. Please process this."
        ),
        "🔄 RTO / Failed Delivery (Order #1006)": (
            "I see my order #1006 has been returned to sender? I never refused any "
            "delivery! What is going on? I want my keyboard delivered or refunded."
        ),
        "😊 Polite General Inquiry (Order #1001)": (
            "Hi, I just received my order #1001 and everything looks great! "
            "I was just wondering about your warranty policy. Thanks!"
        ),
    }

    scenario_cols = st.columns(2)
    selected_scenario = None

    for idx, (label, complaint) in enumerate(scenarios.items()):
        col = scenario_cols[idx % 2]
        with col:
            if st.button(label, key=f"scenario_{idx}", use_container_width=True):
                selected_scenario = complaint

    # ── Custom Complaint Input ────────────────────────────────────────────
    st.markdown("**✍️ Or write a custom complaint:**")
    complaint_input = st.text_area(
        "Customer Message",
        value=selected_scenario or "",
        height=120,
        placeholder=(
            "e.g., 'My order #1004 says delivered but I haven't received it! "
            "I want my money back immediately!'"
        ),
        key="complaint_area",
        label_visibility="collapsed",
    )

    # ── Submit Button ─────────────────────────────────────────────────────
    submit_clicked = st.button(
        "🚀 Submit Ticket",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.processing,
    )

    if submit_clicked and complaint_input.strip():
        st.session_state.processing = True

        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": f"**[{channel}]** {complaint_input}",
        })

        # Generate unique thread ID
        st.session_state.thread_counter += 1
        thread_id = f"ticket-{st.session_state.thread_counter}-{uuid.uuid4().hex[:6]}"

        # Build initial state
        initial_state = {
            "original_complaint": complaint_input,
            "channel": channel,
            "customer_id": "",
            "order_id": "",
            "tracking_id": "",
            "customer_email": "",
            "customer_sentiment": "",
            "issue_type": "",
            "risk_score": "",
            "risk_reasons": [],
            "approval_required": False,
            "approval_status": "not_required",
            "order_details": {},
            "tracking_details": {},
            "policy": {},
            "refund_amount": 0.0,
            "dispute_filed": False,
            "steps_taken": [],
            "internal_notes": [],
            "final_draft_response": "",
            "error": "",
        }

        config = {"configurable": {"thread_id": thread_id}}

        # Run the graph
        with st.spinner("🤖 Agent processing your ticket..."):
            try:
                result = st.session_state.graph.invoke(initial_state, config=config)

                # Check if graph completed or paused (HITL)
                if result.get("approval_status") == "pending" or result.get("approval_required"):
                    # Graph hit the HITL interrupt — check graph state
                    graph_state = st.session_state.graph.get_state(config)

                    if graph_state.next:
                        # Graph is paused — add to active tickets
                        st.session_state.active_tickets[thread_id] = {
                            "thread_id": thread_id,
                            "config": config,
                            "state": result,
                            "complaint": complaint_input,
                            "channel": channel,
                            "submitted_at": datetime.now(tz=timezone.utc).strftime("%H:%M:%S"),
                        }

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": (
                                f"⏸️ **Ticket Escalated for Review**\n\n"
                                f"Your ticket has been received and analyzed. Due to our "
                                f"risk assessment protocols, this case requires manager approval "
                                f"before we can proceed.\n\n"
                                f"**Risk Score:** {result.get('risk_score', 'N/A')}\n"
                                f"**Reasons:** {', '.join(result.get('risk_reasons', ['Under review']))}\n\n"
                                f"A manager will review your case shortly. Please check the "
                                f"Operations Panel for updates."
                            ),
                        })

                        logger.info(f"[Frontend] ⏸️ Ticket {thread_id} paused for HITL approval")
                    else:
                        # Graph completed normally despite approval flags
                        _handle_completed_ticket(result, thread_id, complaint_input, channel)
                else:
                    # Graph completed normally
                    _handle_completed_ticket(result, thread_id, complaint_input, channel)

            except Exception as e:
                logger.error(f"[Frontend] ❌ Graph execution error: {e}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": (
                        f"❌ **Error Processing Ticket**\n\n"
                        f"An error occurred while processing your request: `{str(e)}`\n\n"
                        f"Please ensure the backend API server is running "
                        f"(`python backend.py`) and try again."
                    ),
                })

        st.session_state.processing = False
        st.rerun()

    elif submit_clicked and not complaint_input.strip():
        st.warning("⚠️ Please enter a complaint message before submitting.")

    # ── Chat History Display ──────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("**💬 Conversation History:**")

    if not st.session_state.messages:
        st.info("👆 Submit a ticket above to see the agent's response here.")
    else:
        chat_container = st.container(height=450)
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"], avatar="😤" if msg["role"] == "user" else "🤖"):
                    st.markdown(msg["content"])





# ─────────────────────────────────────────────────────────────────────────────
#  PANEL B: OPERATIONS & HITL CONTROL CENTER
# ─────────────────────────────────────────────────────────────────────────────

with panel_b:
    st.markdown("""
    <div class="panel-header">
        <h2>🏢 Panel B — Operations & HITL Control Center</h2>
        <p>Manager approval queue • Agent trace logs • System activity</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Tab Layout ────────────────────────────────────────────────────────
    tab_queue, tab_trace, tab_logs = st.tabs([
        "🔴 Approval Queue",
        "🧠 Agent Trace",
        "📊 System Logs",
    ])

    # ── TAB 1: HITL Approval Queue ────────────────────────────────────────
    with tab_queue:
        if not st.session_state.active_tickets:
            st.info("✅ No tickets awaiting approval. All clear!")
        else:
            for tid, ticket in list(st.session_state.active_tickets.items()):
                ticket_state = ticket["state"]
                order_id = ticket_state.get("order_id", "N/A")
                customer_id = ticket_state.get("customer_id", "N/A")
                risk_score = ticket_state.get("risk_score", "N/A")
                risk_reasons = ticket_state.get("risk_reasons", [])
                order_amount = ticket_state.get("order_details", {}).get("total_amount", 0)
                issue_type = ticket_state.get("issue_type", "N/A")
                dispute_filed = ticket_state.get("dispute_filed", False)

                risk_badge = "badge-high" if risk_score == "HIGH" else "badge-low"

                st.markdown(f"""
                <div class="ticket-card">
                    <h4>🎫 Order #{order_id} — <span class="{risk_badge}">{risk_score} RISK</span></h4>
                    <p>👤 Customer: {customer_id} &nbsp;|&nbsp; 💰 Amount: ${order_amount:.2f} &nbsp;|&nbsp; 📋 Issue: {issue_type}</p>
                    <p>🚩 Flags: {', '.join(risk_reasons) if risk_reasons else 'None'}</p>
                    <p>{'🚨 Carrier dispute filed' if dispute_filed else ''}</p>
                    <p>🕐 Submitted: {ticket.get('submitted_at', 'N/A')}</p>
                </div>
                """, unsafe_allow_html=True)

                # Action buttons
                btn_col1, btn_col2 = st.columns(2)

                with btn_col1:
                    if st.button(
                        "✅ Approve Action",
                        key=f"approve_{tid}",
                        type="primary",
                        use_container_width=True,
                    ):
                        _resume_graph(tid, "approved")

                with btn_col2:
                    if st.button(
                        "❌ Reject / Override",
                        key=f"reject_{tid}",
                        use_container_width=True,
                    ):
                        _resume_graph(tid, "rejected")

                st.markdown("---")

    # ── TAB 2: Agent Thought Process Timeline ─────────────────────────────
    with tab_trace:
        # Show traces from all tickets (completed + active)
        all_traces = []

        for ticket in st.session_state.completed_tickets:
            all_traces.append({
                "label": f"✅ Order #{ticket['result'].get('order_id', '?')} (Resolved)",
                "steps": ticket["result"].get("steps_taken", []),
                "notes": ticket["result"].get("internal_notes", []),
            })

        for tid, ticket in st.session_state.active_tickets.items():
            all_traces.append({
                "label": f"⏸️ Order #{ticket['state'].get('order_id', '?')} (Awaiting Approval)",
                "steps": ticket["state"].get("steps_taken", []),
                "notes": ticket["state"].get("internal_notes", []),
            })

        if not all_traces:
            st.info("No agent activity yet. Submit a ticket to see the thought process.")
        else:
            for trace in reversed(all_traces):
                with st.expander(trace["label"], expanded=True):
                    st.markdown("**🧠 Agent Thought Process Timeline:**")
                    for step in trace["steps"]:
                        st.markdown(f'<div class="step-item">{step}</div>', unsafe_allow_html=True)

                    if trace["notes"]:
                        st.markdown("**📝 Internal Notes:**")
                        for note in trace["notes"]:
                            st.caption(f"💡 {note}")

    # ── TAB 3: System Logs (Disputes + Refunds) ──────────────────────────
    with tab_logs:
        log_sub1, log_sub2 = st.tabs(["🚨 Carrier Disputes", "💰 Refund Log"])

        with log_sub1:
            try:
                resp = httpx.get(f"{BACKEND_URL}/api/admin/disputes", timeout=5)
                data = resp.json()
                if data.get("disputes"):
                    for d in data["disputes"]:
                        st.markdown(f"""
                        **{d.get('dispute_id', 'N/A')}** — Order #{d.get('order_id', '?')}
                        - Priority: `{d.get('priority', 'N/A')}`
                        - Reason: {d.get('reason', 'N/A')}
                        - GPS Requested: {'✅' if d.get('gps_requested') else '❌'}
                        - Filed: {d.get('filed_at', 'N/A')}
                        - Carrier Response Deadline: {d.get('carrier_response_deadline', 'N/A')}
                        ---
                        """)
                else:
                    st.info("No disputes filed yet.")
            except Exception:
                st.warning("⚠️ Could not connect to backend. Is `backend.py` running?")

        with log_sub2:
            try:
                resp = httpx.get(f"{BACKEND_URL}/api/admin/refunds", timeout=5)
                data = resp.json()
                if data.get("refunds"):
                    for r in data["refunds"]:
                        st.markdown(f"""
                        **{r.get('refund_id', 'N/A')}** — Order #{r.get('order_id', '?')}
                        - Amount: **${r.get('amount', 0):.2f}**
                        - Approved By: `{r.get('approved_by', 'N/A')}`
                        - Items Restocked: {', '.join(r.get('items_restocked', []))}
                        - Processed: {r.get('processed_at', 'N/A')}
                        ---
                        """)
                else:
                    st.info("No refunds processed yet.")
            except Exception:
                st.warning("⚠️ Could not connect to backend. Is `backend.py` running?")





# =============================================================================
#  SIDEBAR — System Info
# =============================================================================

with st.sidebar:
    st.markdown("### 🔧 System Info")
    st.markdown(f"**Backend:** `{BACKEND_URL}`")
    st.markdown(f"**Thread Counter:** {st.session_state.thread_counter}")

    # Backend health check
    try:
        health = httpx.get(f"{BACKEND_URL}/health", timeout=3).json()
        st.success(f"✅ Backend Online")
        st.json(health.get("data_stats", {}))
    except Exception:
        st.error("❌ Backend Offline — Run `python backend.py`")

    st.markdown("---")
    st.markdown("### 📖 Architecture")
    st.markdown("""
    ```
    Customer → Triage → Logistics
                  ↓         ↓
              Fraud/Risk ←──┘
                  ↓
            HITL Gate (if HIGH RISK)
                  ↓
          Financial Adjuster → Response
    ```
    """)

    st.markdown("---")
    if st.button("🗑️ Clear All Data", use_container_width=True):
        for key in ["messages", "active_tickets", "completed_tickets"]:
            st.session_state[key] = [] if key != "active_tickets" else {}
        st.rerun()
