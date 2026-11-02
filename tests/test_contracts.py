"""Unit tests for shared data contracts, validation rules, and invariants."""

import unittest
from contracts import Answer, Chunk, Evidence, IndexingSummary


class TestChunkContract(unittest.TestCase):
    def test_valid_chunk(self):
        chunk = Chunk(
            chunk_id="chunk_001",
            document_id="doc_sop_101",
            filename="sop_compressor.pdf",
            page=1,
            text="Check pressure gauge prior to activating valve A.",
            equipment_model="Compressor-X1",
            synthetic=False,
        )
        self.assertEqual(chunk.page, 1)
        self.assertEqual(chunk.chunk_id, "chunk_001")
        self.assertEqual(chunk.equipment_model, "Compressor-X1")
        self.assertFalse(chunk.synthetic)

    def test_page_number_below_one_rejected(self):
        with self.assertRaises(ValueError):
            Chunk(
                chunk_id="chunk_001",
                document_id="doc_sop_101",
                filename="sop.pdf",
                page=0,
                text="Some text",
            )

    def test_empty_or_whitespace_text_rejected(self):
        with self.assertRaises(ValueError):
            Chunk(
                chunk_id="c1",
                document_id="d1",
                filename="doc.pdf",
                page=1,
                text="   \n\t  ",
            )
        with self.assertRaises(ValueError):
            Chunk(
                chunk_id="c1",
                document_id="d1",
                filename="doc.pdf",
                page=1,
                text="",
            )

    def test_empty_identifiers_rejected(self):
        with self.assertRaises(ValueError):
            Chunk(chunk_id="", document_id="d1", filename="doc.pdf", page=1, text="ok")
        with self.assertRaises(ValueError):
            Chunk(chunk_id="  ", document_id="d1", filename="doc.pdf", page=1, text="ok")
        with self.assertRaises(ValueError):
            Chunk(chunk_id="c1", document_id="", filename="doc.pdf", page=1, text="ok")
        with self.assertRaises(ValueError):
            Chunk(chunk_id="c1", document_id="d1", filename="", page=1, text="ok")


class TestEvidenceContract(unittest.TestCase):
    def setUp(self):
        self.chunk = Chunk(
            chunk_id="c1",
            document_id="d1",
            filename="sop.pdf",
            page=3,
            text="Normal operating temperature is 65-80 C.",
        )

    def test_valid_evidence(self):
        evidence = Evidence(source_id="d1#p3#c1", chunk=self.chunk)
        self.assertEqual(evidence.source_id, "d1#p3#c1")
        self.assertEqual(evidence.chunk, self.chunk)

    def test_empty_source_id_rejected(self):
        with self.assertRaises(ValueError):
            Evidence(source_id="", chunk=self.chunk)
        with self.assertRaises(ValueError):
            Evidence(source_id="   ", chunk=self.chunk)


class TestIndexingSummaryContract(unittest.TestCase):
    def test_valid_invariant(self):
        summary = IndexingSummary(
            total_chunks_received=10,
            chunks_indexed=7,
            chunks_skipped=2,
            chunks_failed=1,
            collection_name="test_col",
            errors=["Page 4 chunk failed embedding"],
        )
        self.assertEqual(summary.total_chunks_received, 10)
        self.assertEqual(summary.chunks_indexed, 7)
        self.assertEqual(summary.chunks_skipped, 2)
        self.assertEqual(summary.chunks_failed, 1)

    def test_invariant_violation_raises(self):
        with self.assertRaises(ValueError):
            IndexingSummary(
                total_chunks_received=10,
                chunks_indexed=5,
                chunks_skipped=2,
                chunks_failed=1,  # 5 + 2 + 1 = 8 != 10
                collection_name="test_col",
            )

    def test_negative_counts_rejected(self):
        with self.assertRaises(ValueError):
            IndexingSummary(
                total_chunks_received=-1,
                chunks_indexed=0,
                chunks_skipped=0,
                chunks_failed=-1,
                collection_name="test_col",
            )


class TestAnswerContract(unittest.TestCase):
    def setUp(self):
        chunk1 = Chunk(
            chunk_id="c1",
            document_id="d1",
            filename="sop.pdf",
            page=2,
            text="Turn valve clockwise.",
        )
        self.ev1 = Evidence(source_id="d1#p2#c1", chunk=chunk1)

    def test_valid_citations(self):
        ans = Answer(
            text="According to [d1#p2#c1], turn valve clockwise.",
            evidence=[self.ev1],
            insufficient_evidence=False,
            observations=[],
        )
        self.assertTrue(ans.validate_citations())

    def test_missing_citation_fails_validation(self):
        ans = Answer(
            text="According to [d1#p2#c1] and [non_existent_ref], turn valve clockwise.",
            evidence=[self.ev1],
            insufficient_evidence=False,
            observations=[],
        )
        self.assertFalse(ans.validate_citations())

    def test_insufficient_evidence_flag(self):
        ans = Answer(
            text="Retrieved SOP does not mention torque specifications.",
            evidence=[],
            insufficient_evidence=True,
            observations=[],
        )
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)


if __name__ == "__main__":
    unittest.main()

