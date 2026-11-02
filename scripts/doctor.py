#!/usr/bin/env python3
"""VALENCE Environment Readiness Doctor (Member B).

Performs comprehensive read-only checks to verify that the environment is
ready for air-gapped, offline execution with zero remote downloads.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from config import is_loopback_url, load_config
from backend.diagnostics import run_diagnostics


def main() -> int:
    print("\n" + "=" * 65)
    print("      VALENCE OFFLINE RUNTIME READINESS DOCTOR")
    print("=" * 65)

    all_ready = True

    # 1. Platform & Python Version
    print("\n[1] Platform & Compute Architecture")
    py_ver = platform.python_version()
    machine = platform.machine()
    system = platform.system()
    print(f"    - OS: {system} ({platform.version()[:30]})")
    print(f"    - Hardware Architecture: {machine} (Apple Silicon)")
    print(f"    - Python Interpreter: {py_ver} ({sys.executable})")

    if sys.version_info < (3, 9):
        print("    ❌ Python 3.9+ is required.")
        all_ready = False
    else:
        print("    ✅ Python version satisfies requirement (>= 3.9).")

    # 2. Configuration & Air-Gap Constraint Check
    print("\n[2] Air-Gap Endpoint Audit")
    cfg = load_config()
    is_loopback = is_loopback_url(cfg.ollama_base_url)
    print(f"    - Configured Ollama Endpoint: '{cfg.ollama_base_url}'")
    print(f"    - Text Model: '{cfg.llm_model}'")
    print(f"    - Vision Model: '{cfg.vlm_model}'")
    print(f"    - Mock Mode: {cfg.mock_mode}")

    if not is_loopback:
        print("    ❌ Non-loopback endpoint detected! Air-gap constraint violated.")
        all_ready = False
    else:
        print("    ✅ Endpoint strictly confined to local loopback (localhost/127.0.0.1).")

    # 3. Telemetry Check
    print("\n[3] Telemetry & Remote Call Audit")
    st_cfg = ROOT_DIR / ".streamlit" / "config.toml"
    if st_cfg.exists():
        content = st_cfg.read_text(encoding="utf-8")
        if "gatherUsageStats = false" in content:
            print("    ✅ Streamlit analytics telemetry explicitly disabled.")
        else:
            print("    ⚠️ Streamlit gatherUsageStats not explicitly disabled in .streamlit/config.toml.")
    else:
        print("    ⚠️ .streamlit/config.toml not found.")

    # 4. Local Storage & File Directories
    print("\n[4] Local Storage & Data Directories")
    storage_dir = ROOT_DIR / cfg.index_dir
    synthetic_dir = ROOT_DIR / "data" / "synthetic"
    models_dir = ROOT_DIR / cfg.embedding_model_dir

    print(f"    - Vector Storage Path: '{storage_dir}' (Exists: {storage_dir.exists()})")
    print(f"    - Synthetic Documents: '{synthetic_dir}' (Exists: {synthetic_dir.exists()})")
    print(f"    - Local Weights Dir:   '{models_dir}' (Exists: {models_dir.exists()})")

    # 5. Installed Python Dependencies
    print("\n[5] Key Dependency Audit")
    dependencies = [
        ("pypdf", "PDF text extraction"),
        ("streamlit", "User interface"),
        ("qdrant_client", "Vector database client (optional on-disk fallback available)"),
        ("fastembed", "Local embedding engine (optional deterministic fallback available)"),
    ]
    for pkg, purpose in dependencies:
        try:
            __import__(pkg)
            print(f"    ✅ '{pkg}': Installed ({purpose})")
        except ImportError:
            print(f"    ⚠️ '{pkg}': Not installed ({purpose})")

    # 6. Detailed Diagnostics Report
    print("\n[6] Component Diagnostics Summary")
    report = run_diagnostics(cfg)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        glyph = "✅" if check.passed else "❌"
        print(f"    {glyph} [{status}] {check.name}: {check.message}")
        if not check.passed and check.actionable_fix:
            print(f"         -> Fix: {check.actionable_fix}")

    print("\n" + "=" * 65)
    if report.all_passed and all_ready:
        print("  RESULT: Environment is 100% READY for offline execution.")
        print("=" * 65 + "\n")
        return 0
    else:
        print("  RESULT: Readiness gaps detected. Review remediation steps above.")
        print("  (Note: Mock mode remains functional for isolated offline testing.)")
        print("=" * 65 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

