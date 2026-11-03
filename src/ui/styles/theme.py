"""CSS styling and theme definitions for the modern VALENCE frontend."""

CUSTOM_CSS = """
<style>
    /* Global Typography & Background adjustments */
    .stApp {
        background-color: #0b0f17;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Top Navbar styling */
    .valence-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.85rem 1.5rem;
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid rgba(51, 65, 85, 0.7);
        border-radius: 14px;
        margin-bottom: 1.25rem;
        box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.35);
    }
    .valence-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 1.3rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.02em;
    }
    .valence-brand span.tag {
        font-size: 0.75rem;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        font-weight: 600;
        letter-spacing: 0.05em;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        border: 1px solid transparent;
        transition: all 0.2s ease;
    }
    .status-pill.mock {
        background: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
        border-color: rgba(245, 158, 11, 0.35);
    }
    .status-pill.live {
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border-color: rgba(16, 185, 129, 0.35);
    }
    .status-pill.docs {
        background: rgba(59, 130, 246, 0.12);
        color: #60a5fa;
        border-color: rgba(59, 130, 246, 0.35);
    }

    /* KPI Metrics Card */
    .kpi-card {
        background: linear-gradient(145deg, #1e293b 0%, #111827 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #38bdf8, #3b82f6);
    }
    .kpi-val {
        font-size: 1.85rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.82rem;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-top: 0.2rem;
    }
    .kpi-sub {
        font-size: 0.75rem;
        color: #38bdf8;
        margin-top: 0.25rem;
    }

    /* Factory Floor Voice Pill */
    .voice-banner {
        background: linear-gradient(90deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-left: 4px solid #38bdf8;
        padding: 0.6rem 1rem;
        border-radius: 8px;
        font-size: 0.85rem;
        color: #cbd5e1;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }

    /* Evidence card styling */
    .evidence-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-left: 3px solid #3b82f6;
        padding: 0.85rem 1.1rem;
        border-radius: 8px;
        margin-bottom: 0.75rem;
    }

    /* Observations panel */
    .observation-item {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        padding: 0.45rem 0;
        font-size: 0.9rem;
    }

    /* Enhanced Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: #0f172a;
        padding: 0.4rem 0.5rem;
        border-radius: 12px;
        border: 1px solid #1e293b;
    }
    .stTabs [data-baseweb="tab"] {
        height: 2.4rem;
        padding: 0 1rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.88rem;
        color: #94a3b8;
        border: none;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        background: #1e293b !important;
        color: #38bdf8 !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
    }
</style>
"""


def apply_theme() -> None:
    """Injects custom CSS theme into the Streamlit session."""
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
