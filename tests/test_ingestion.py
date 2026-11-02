"""Unit tests for Member A document ingestion pipeline."""

import unittest
from pathlib import Path

from contracts import Chunk, DocumentIngestionProtocol
from src.ingestion.ingestor import MockPDFIngestor, PDFIngestor
from src.services import create_ingestor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SYNTHETIC_DIR = Path(__file__).parents[1] / "data" / "synthetic"


class TestDocumentIngestion(unittest.TestCase):
    def setUp(self):
        self.sample_fixture = FIXTURES_DIR / "sample_fixture.txt"
        self.synthetic_sop = SYNTHETIC_DIR / "synthetic_sop.txt"

    def test_factory_creates_protocol_instance(self):
        ingestor = create_ingestor(mock=True)
        self.assertIsInstance(ingestor, MockPDFIngestor)
        self.assertTrue(callable(getattr(ingestor, "ingest_pdf", None)))

    def test_mock_ingestion_valid_chunks(self):
        ingestor = create_ingestor(mock=True, chunk_size=300, chunk_overlap=30)
        chunks = ingestor.ingest_pdf(
            self.synthetic_sop,
            equipment_model="Model-X",
            synthetic=True,
        )

        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertIsInstance(chunk, Chunk)
            self.assertGreaterEqual(chunk.page, 1)
            self.assertTrue(chunk.chunk_id)
            self.assertTrue(chunk.document_id)
            self.assertTrue(chunk.text.strip())
            self.assertEqual(chunk.equipment_model, "Model-X")
            self.assertTrue(chunk.synthetic)
            self.assertEqual(chunk.filename, "synthetic_sop.txt")

    def test_page_numbers_are_one_based_and_blank_page_skipped(self):
        ingestor = create_ingestor(mock=True)
        chunks = ingestor.ingest_pdf(self.sample_fixture, equipment_model="H-500", synthetic=True)

        pages = [c.page for c in chunks]
        self.assertIn(1, pages)
        self.assertIn(3, pages)
        # Page 2 in sample_fixture is whitespace-only, so it must be omitted
        self.assertNotIn(2, pages)
        for page in pages:
            self.assertGreaterEqual(page, 1)

    def test_deterministic_ids(self):
        ingestor = create_ingestor(mock=True)
        run1 = ingestor.ingest_pdf(self.synthetic_sop, equipment_model="Model-X")
        run2 = ingestor.ingest_pdf(self.synthetic_sop, equipment_model="Model-X")

        self.assertEqual(len(run1), len(run2))
        for c1, c2 in zip(run1, run2):
            self.assertEqual(c1.chunk_id, c2.chunk_id)
            self.assertEqual(c1.document_id, c2.document_id)
            self.assertEqual(c1.page, c2.page)
            self.assertEqual(c1.text, c2.text)

    def test_missing_file_raises_filenotfound(self):
        ingestor = create_ingestor(mock=True)
        with self.assertRaises(FileNotFoundError):
            ingestor.ingest_pdf("non_existent_document_12345.pdf")

    def test_empty_file_raises_valueerror(self):
        empty_file = FIXTURES_DIR / "empty.txt"
        empty_file.write_text("")
        try:
            ingestor = create_ingestor(mock=True)
            with self.assertRaises(ValueError):
                ingestor.ingest_pdf(empty_file)
        finally:
            if empty_file.exists():
                empty_file.unlink()

    def test_production_ingestor_reports_missing_dependency(self):
        """Validates that real PDF extraction clearly reports missing dependency."""
        ingestor = create_ingestor(mock=False)
        self.assertIsInstance(ingestor, PDFIngestor)

        # Non-pdf extension is rejected
        with self.assertRaises(ValueError):
            ingestor.ingest_pdf(self.synthetic_sop)

        # Testing with a fake .pdf file should report missing fitz/pypdf dependency
        fake_pdf = FIXTURES_DIR / "dummy.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n%EOF")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                ingestor.ingest_pdf(fake_pdf)
            self.assertIn("Approval from Member B is required", str(ctx.exception))
        finally:
            if fake_pdf.exists():
                fake_pdf.unlink()


if __name__ == "__main__":
    unittest.main()
