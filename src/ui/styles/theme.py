"""CSS styling and theme definitions for the modern VALENCE frontend."""

CUSTOM_CSS = """
<style>
    /* Top Navbar styling */
    .valence-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1.25rem;
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .valence-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 1.25rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.02em;
    }
    .valence-brand span.tag {
        font-size: 0.75rem;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        background: #3b82f6;
        color: white;
        font-weight: 600;
    }
    .valence-badges {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid transparent;
    }
    .status-pill.mock {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border-color: rgba(245, 158, 11, 0.3);
    }
    .status-pill.live {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border-color: rgba(16, 185, 129, 0.3);
    }
    .status-pill.docs {
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border-color: rgba(59, 130, 246, 0.3);
    }

    /* Metric and control cards */
    .modern-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
    }

    /* Evidence card styling */
    .evidence-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-left: 3px solid #3b82f6;
        padding: 0.75rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.75rem;
    }

    /* Observations panel */
    .observation-item {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        padding: 0.4rem 0;
        font-size: 0.9rem;
    }
</style>
"""


def apply_theme() -> None:
    """Injects custom CSS theme into the Streamlit session."""
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

