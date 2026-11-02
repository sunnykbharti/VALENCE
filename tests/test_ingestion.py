"""Unit tests for document ingestion, page extraction, chunking, and validation."""

import tempfile
import unittest
from pathlib import Path

from contracts import Chunk, DocumentIngestionProtocol
from src.ingestion.extractor import extract_pages
from src.ingestion.ingestor import PDFIngestor
from src.ingestion.mock import MockPDFIngestor
from src.services import create_ingestor


class TestDocumentIngestion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiny_fixture = Path("tests/fixtures/tiny_sample.pdf")
        cls.blank_fixture = Path("tests/fixtures/blank_sample.pdf")
        cls.synthetic_pdf = Path("data/synthetic/01_Standard_Operating_Procedure.pdf")

    def setUp(self):
        self.ingestor = PDFIngestor(chunk_size=500, chunk_overlap=50)

    def test_multipage_fixture_page_numbering(self):
        """Verify multi-page PDF extracts text page-by-page preserving 1-based original positions."""
        chunks = self.ingestor.ingest_pdf(self.tiny_fixture)

        # Page 1 and Page 3 have content; Page 2 is blank and omitted
        self.assertEqual(len(chunks), 2)

        chunk_p1 = chunks[0]
        self.assertEqual(chunk_p1.page, 1)
        self.assertIn("Primary Infeed Calibration Step 1", chunk_p1.text)
        self.assertTrue(chunk_p1.chunk_id.endswith("#p1#c0"))

        chunk_p3 = chunks[1]
        self.assertEqual(chunk_p3.page, 3)
        self.assertIn("Safety Interlock Isolation Step 3", chunk_p3.text)
        self.assertTrue(chunk_p3.chunk_id.endswith("#p3#c0"))

    def test_blank_page_warning_logged(self):
        """Verify pages with no extractable text are omitted and logged as warnings."""
        with self.assertLogs("src.ingestion.chunker", level="WARNING") as log_ctx:
            chunks = self.ingestor.ingest_pdf(self.tiny_fixture)

        # Verify page 2 is reported in the log output
        self.assertTrue(any("Page 2 has no extractable text" in msg for msg in log_ctx.output))
        # Ensure no chunk has page == 2
        self.assertNotIn(2, [c.page for c in chunks])

    def test_reprocessing_unchanged_content_stable_identifiers(self):
        """Reprocessing identical content must produce strictly identical document and chunk IDs."""
        run1 = self.ingestor.ingest_pdf(self.tiny_fixture)
        run2 = self.ingestor.ingest_pdf(self.tiny_fixture)

        self.assertEqual(len(run1), len(run2))
        for c1, c2 in zip(run1, run2):
            self.assertEqual(c1.document_id, c2.document_id)
            self.assertEqual(c1.chunk_id, c2.chunk_id)
            self.assertEqual(c1.page, c2.page)
            self.assertEqual(c1.text, c2.text)

    def test_equipment_model_and_synthetic_flags_preserved(self):
        """Ensure supplied equipment_model and synthetic flags propagate to each chunk."""
        chunks = self.ingestor.ingest_pdf(
            self.tiny_fixture,
            equipment_model="Compressor-XYZ-100",
            synthetic=True,
        )
        self.assertTrue(len(chunks) > 0)
        for chunk in chunks:
            self.assertEqual(chunk.equipment_model, "Compressor-XYZ-100")
            self.assertTrue(chunk.synthetic)

        # Test defaults
        chunks_default = self.ingestor.ingest_pdf(self.tiny_fixture)
        for chunk in chunks_default:
            self.assertIsNone(chunk.equipment_model)
            self.assertFalse(chunk.synthetic)

    def test_nonexistent_file_raises_filenotfound(self):
        """Nonexistent PDF file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.ingestor.ingest_pdf("nonexistent_manual_12345.pdf")

    def test_empty_file_raises_valueerror(self):
        """Empty 0-byte file raises ValueError."""
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.flush()
            with self.assertRaises(ValueError):
                self.ingestor.ingest_pdf(tmp.name)

    def test_invalid_pdf_raises_valueerror(self):
        """File lacking PDF structure raises ValueError."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", mode="w") as tmp:
            tmp.write("This is a plain text file pretending to be a PDF.")
            tmp.flush()
            with self.assertRaises(ValueError):
                self.ingestor.ingest_pdf(tmp.name)

    def test_completely_blank_pdf_raises_valueerror(self):
        """PDF containing no extractable text on any page raises ValueError."""
        with self.assertRaises(ValueError):
            self.ingestor.ingest_pdf(self.blank_fixture)

    def test_chunk_size_and_overlap_segmentation(self):
        """Long text segments into multiple indexed chunks per page."""
        small_chunker = PDFIngestor(chunk_size=35, chunk_overlap=10)
        chunks = small_chunker.ingest_pdf(self.tiny_fixture)

        # With 35 character limit, the ~60 char lines must split into multiple chunks
        page1_chunks = [c for c in chunks if c.page == 1]
        self.assertGreater(len(page1_chunks), 1)

        # Ensure indices #c0, #c1 are sequential
        self.assertTrue(page1_chunks[0].chunk_id.endswith("#p1#c0"))
        self.assertTrue(page1_chunks[1].chunk_id.endswith("#p1#c1"))

    def test_synthetic_docs_ingest_successfully(self):
        """Verify extraction and chunking against actual repo synthetic documents."""
        if not self.synthetic_pdf.exists():
            self.skipTest("Synthetic PDF fixture not present in data/synthetic/")

        chunks = self.ingestor.ingest_pdf(
            self.synthetic_pdf,
            equipment_model="S7-1200",
            synthetic=True,
        )
        self.assertGreater(len(chunks), 0)
        # Check that expected SOP content is present
        combined_text = " ".join(c.text for c in chunks)
        self.assertIn("Standard Operating Procedure", combined_text)
        self.assertIn("PLC", combined_text)
        for chunk in chunks:
            self.assertGreaterEqual(chunk.page, 1)
            self.assertTrue(chunk.synthetic)
            self.assertEqual(chunk.equipment_model, "S7-1200")

    def test_create_ingestor_factory(self):
        """Verify services.create_ingestor returns conforming implementations."""
        real_ingestor = create_ingestor(mock=False)
        self.assertIsInstance(real_ingestor, PDFIngestor)

        mock_ingestor = create_ingestor(mock=True)
        self.assertIsInstance(mock_ingestor, MockPDFIngestor)

        mock_chunks = mock_ingestor.ingest_pdf(
            "mock_sop.pdf",
            equipment_model="MOCK-VALVE-01",
            synthetic=True,
        )
        self.assertGreater(len(mock_chunks), 0)
        self.assertEqual(mock_chunks[0].equipment_model, "MOCK-VALVE-01")
        self.assertTrue(mock_chunks[0].synthetic)
        self.assertTrue(all(isinstance(c, Chunk) for c in mock_chunks))


if __name__ == "__main__":
    unittest.main()

