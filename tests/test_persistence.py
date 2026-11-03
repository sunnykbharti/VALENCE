"""Unit tests for SQLite persistence layer."""

import os
import tempfile
import unittest
from pathlib import Path

from contracts import Answer, Chunk, Evidence
from src.ui.persistence import (
    clear_chat_history,
    delete_indexed_document,
    init_db,
    load_chat_history,
    load_indexed_documents,
    load_user_session_state,
    save_chat_message,
    save_indexed_document,
    save_user_session_state,
)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_operator_42"
        init_db()

    def tearDown(self):
        clear_chat_history(self.session_id)

    def test_save_and_load_chat_history(self):
        # 1. User message
        user_msg = {"role": "user", "content": "What is normal operating pressure?", "image_name": None}
        save_chat_message(self.session_id, user_msg)

        # 2. Assistant message with evidence
        c = Chunk(
            chunk_id="chunk_test_01",
            document_id="doc_press_01",
            filename="pressure_sop.pdf",
            page=2,
            text="Operating pressure must not exceed 250 bar.",
            equipment_model="A10VSO",
        )
        ev = Evidence(source_id="doc_press_01#p2#c0", chunk=c)
        ans = Answer(
            text="Normal pressure is 250 bar [doc_press_01#p2#c0].",
            evidence=[ev],
            insufficient_evidence=False,
            observations=["Gauge nominal"],
        )
        asst_msg = {"role": "assistant", "answer": ans, "image_name": None}
        save_chat_message(self.session_id, asst_msg)

        # 3. Load
        loaded = load_chat_history(self.session_id)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["role"], "user")
        self.assertEqual(loaded[0]["content"], "What is normal operating pressure?")

        self.assertEqual(loaded[1]["role"], "assistant")
        loaded_ans = loaded[1]["answer"]
        self.assertEqual(loaded_ans.text, ans.text)
        self.assertEqual(len(loaded_ans.evidence), 1)
        self.assertEqual(loaded_ans.evidence[0].source_id, "doc_press_01#p2#c0")
        self.assertEqual(loaded_ans.evidence[0].chunk.page, 2)
        self.assertEqual(loaded_ans.observations, ["Gauge nominal"])

    def test_clear_chat_history(self):
        user_msg = {"role": "user", "content": "Temporary message", "image_name": None}
        save_chat_message(self.session_id, user_msg)
        self.assertTrue(len(load_chat_history(self.session_id)) > 0)

        clear_chat_history(self.session_id)
        self.assertEqual(len(load_chat_history(self.session_id)), 0)

    def test_save_and_load_indexed_documents(self):
        doc_id = "doc_test_101"
        meta = {
            "filename": "turbine_manual.pdf",
            "page_count": 15,
            "equipment_model": "Turbine-X",
            "synthetic": False,
        }
        chunk = Chunk(
            chunk_id="chunk_turb_1",
            document_id=doc_id,
            filename="turbine_manual.pdf",
            page=1,
            text="Turbine startup sequence step 1.",
            equipment_model="Turbine-X",
        )
        save_indexed_document(self.session_id, doc_id, meta, [chunk])

        docs, chunks = load_indexed_documents(self.session_id)
        self.assertIn("turbine_manual.pdf", docs)
        self.assertEqual(docs["turbine_manual.pdf"]["document_id"], doc_id)
        self.assertEqual(docs["turbine_manual.pdf"]["chunk_count"], 1)
        self.assertEqual(docs["turbine_manual.pdf"]["chunks_count"], 1)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "chunk_turb_1")

        # Delete document
        delete_indexed_document(self.session_id, "turbine_manual.pdf")
        docs_after, chunks_after = load_indexed_documents(self.session_id)
        self.assertNotIn("turbine_manual.pdf", docs_after)
        self.assertEqual(len(chunks_after), 0)

    def test_save_and_load_session_state(self):
        save_user_session_state(
            session_id=self.session_id,
            active_incident_id="INC-2026-999",
            use_mock=False,
            vision_image_name="gauge.png",
            vision_image_path="/tmp/gauge.png",
            vision_mode_active=True,
        )
        st_data = load_user_session_state(self.session_id)
        self.assertIsNotNone(st_data)
        self.assertEqual(st_data["active_incident_id"], "INC-2026-999")
        self.assertFalse(st_data["use_mock"])
        self.assertEqual(st_data["vision_image_name"], "gauge.png")


if __name__ == "__main__":
    unittest.main()

