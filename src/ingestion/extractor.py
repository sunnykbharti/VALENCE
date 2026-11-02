"""PDF text extraction engine with pure-Python parsing and optional pypdf acceleration.

Supports offline, air-gapped PDF page extraction, preserves 1-based original page positions,
and decodes text streams without external dependencies.
"""

from __future__ import annotations

import binascii
import hashlib
import logging
import re
import zlib
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Check for optional pypdf acceleration
try:
    import pypdf
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False


def _unescape_pdf_literal_string(s: bytes) -> str:
    """Decodes escaped characters in PDF literal string bytes (...) to string."""
    res: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i:i + 1] == b"\\" and i + 1 < n:
            nxt = s[i + 1:i + 2]
            if nxt == b"n":
                res.append("\n")
                i += 2
            elif nxt == b"r":
                res.append("\r")
                i += 2
            elif nxt == b"t":
                res.append("\t")
                i += 2
            elif nxt == b"b":
                res.append("\b")
                i += 2
            elif nxt == b"f":
                res.append("\f")
                i += 2
            elif nxt in (b"(", b")", b"\\"):
                res.append(chr(nxt[0]))
                i += 2
            elif nxt.isdigit():
                oct_bytes = s[i + 1:i + 4]
                oct_m = re.match(rb"^[0-7]{1,3}", oct_bytes)
                if oct_m:
                    res.append(chr(int(oct_m.group(0), 8)))
                    i += 1 + len(oct_m.group(0))
                else:
                    res.append(chr(nxt[0]))
                    i += 2
            else:
                res.append(chr(nxt[0]))
                i += 2
        else:
            res.append(chr(s[i]))
            i += 1
    return "".join(res)


def _decode_pdf_hex_string(hex_bytes: bytes) -> str:
    """Decodes PDF hex strings <...> to unicode text."""
    cleaned = re.sub(rb"\s+", b"", hex_bytes)
    if len(cleaned) % 2 != 0:
        cleaned += b"0"
    try:
        raw = binascii.unhexlify(cleaned)
        if raw.startswith(b"\xfe\xff"):
            return raw[2:].decode("utf-16-be", errors="replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin1", errors="replace")
    except Exception:
        return ""


def _extract_text_from_content_stream(stream_bytes: bytes) -> str:
    """Extracts text tokens from a decrypted/decompressed PDF content stream."""
    text_pieces: list[str] = []
    for bt_match in re.finditer(rb"\bBT\b(.*?)\bET\b", stream_bytes, re.DOTALL):
        block = bt_match.group(1)

        # 1. Array text showing: [(str1) -10 (str2)] TJ
        for tj_match in re.finditer(rb"\[(.*?)\]\s*TJ", block, re.DOTALL):
            inner = tj_match.group(1)
            parts = re.findall(rb"\(((?:[^()\\]|\\.)*)\)|<([0-9a-fA-F\s]+)>", inner)
            line_parts: list[str] = []
            for lit_str, hex_str in parts:
                if lit_str:
                    line_parts.append(_unescape_pdf_literal_string(lit_str))
                elif hex_str:
                    line_parts.append(_decode_pdf_hex_string(hex_str))
            line = "".join(line_parts).strip()
            if line:
                text_pieces.append(line)

        # 2. Single text showing: (str) Tj or (str) ' or (str) "
        for tj_match in re.finditer(rb"\(((?:[^()\\]|\\.)*)\)\s*(?:Tj|\'|\")", block):
            raw_s = tj_match.group(1)
            line = _unescape_pdf_literal_string(raw_s).strip()
            if line:
                text_pieces.append(line)

        # 3. Single hex text showing: <hex> Tj
        for hex_match in re.finditer(rb"<([0-9a-fA-F\s]+)>\s*(?:Tj|\'|\")", block):
            raw_hex = hex_match.group(1)
            line = _decode_pdf_hex_string(raw_hex).strip()
            if line:
                text_pieces.append(line)

    return "\n".join(text_pieces)


def _decompress_flate(data: bytes) -> bytes:
    """Attempts flate/deflate decompression with zlib, raw deflate, and gzip formats."""
    try:
        return zlib.decompress(data)
    except Exception:
        pass
    try:
        return zlib.decompress(data, -15)
    except Exception:
        pass
    try:
        return zlib.decompress(data, 16 + zlib.MAX_WBITS)
    except Exception:
        return data


def _decode_stream_data(stream_body: bytes, obj_dict_header: bytes) -> bytes:
    """Applies PDF stream filters (ASCII85, Flate, ASCIIHex) in sequence."""
    filter_m = re.search(rb"/Filter\s*(?:\[(.*?)\]|/([A-Za-z0-9_]+))", obj_dict_header, re.DOTALL)
    if not filter_m:
        return stream_body

    filters: list[bytes] = []
    if filter_m.group(1):
        filters = re.findall(rb"/([A-Za-z0-9_]+)", filter_m.group(1))
    elif filter_m.group(2):
        filters = [filter_m.group(2)]

    cur = stream_body
    for filt in filters:
        if filt in (b"ASCII85Decode", b"A85"):
            import base64
            try:
                raw = cur.strip()
                if not raw.endswith(b"~>"):
                    raw += b"~>"
                cur = base64.a85decode(raw, adobe=True)
            except Exception as e:
                logger.debug("ASCII85 decoding error: %s", e)
        elif filt in (b"FlateDecode", b"Fl"):
            cur = _decompress_flate(cur)
        elif filt in (b"ASCIIHexDecode", b"AHx"):
            cleaned = re.sub(rb"\s+", b"", cur)
            if cleaned.endswith(b">"):
                cleaned = cleaned[:-1]
            if len(cleaned) % 2 != 0:
                cleaned += b"0"
            try:
                cur = binascii.unhexlify(cleaned)
            except Exception as e:
                logger.debug("ASCIIHex decoding error: %s", e)
    return cur


def _parse_pdf_pure_python(data: bytes) -> dict[int, str]:
    """Pure-Python fallback PDF parser that traverses the page tree."""
    objs: dict[int, bytes] = {}
    for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", data, re.DOTALL):
        objs[int(m.group(1))] = m.group(3)

    if not objs:
        raise ValueError("No valid PDF objects found in file")

    # Locate Catalog
    catalog_id: Optional[int] = None
    for oid, body in objs.items():
        if re.search(rb"/Type\s*/Catalog\b", body):
            catalog_id = oid
            break

    # If Catalog not labeled directly, check trailer for /Root ref
    if catalog_id is None:
        root_m = re.search(rb"/Root\s+(\d+)\s+\d+\s+R", data)
        if root_m:
            catalog_id = int(root_m.group(1))

    page_obj_ids: list[int] = []

    def traverse_pages(node_id: int, visited: set[int]) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = objs.get(node_id)
        if not node:
            return
        if re.search(rb"/Type\s*/Pages\b", node):
            kids_m = re.search(rb"/Kids\s*\[(.*?)\]", node, re.DOTALL)
            if kids_m:
                kid_refs = re.findall(rb"(\d+)\s+\d+\s+R", kids_m.group(1))
                for k in kid_refs:
                    traverse_pages(int(k), visited)
        elif re.search(rb"/Type\s*/Page(?![a-zA-Z])", node):
            page_obj_ids.append(node_id)

    if catalog_id and catalog_id in objs:
        pages_ref_m = re.search(rb"/Pages\s+(\d+)\s+\d+\s+R", objs[catalog_id])
        if pages_ref_m:
            traverse_pages(int(pages_ref_m.group(1)), set())

    # Fallback to scanning all objects labeled /Type /Page if tree traversal was empty
    if not page_obj_ids:
        for oid, body in sorted(objs.items()):
            if re.search(rb"/Type\s*/Page(?![a-zA-Z])", body):
                page_obj_ids.append(oid)

    if not page_obj_ids:
        raise ValueError("PDF contains no page objects")

    pages_text: dict[int, str] = {}
    for page_num, pid in enumerate(page_obj_ids, start=1):
        page_body = objs[pid]
        contents_m = re.search(rb"/Contents\s+(?:\[(.*?)\]|(\d+)\s+\d+\s+R)", page_body, re.DOTALL)
        content_stream_bytes = b""
        if contents_m:
            if contents_m.group(1):
                c_refs = re.findall(rb"(\d+)\s+\d+\s+R", contents_m.group(1))
                for cref in c_refs:
                    cbody = objs.get(int(cref), b"")
                    s_m = re.search(rb"stream\r?\n(.*?)\r?\nendstream", cbody, re.DOTALL)
                    if s_m:
                        content_stream_bytes += _decode_stream_data(s_m.group(1), cbody) + b"\n"
            elif contents_m.group(2):
                cref = int(contents_m.group(2))
                cbody = objs.get(cref, b"")
                s_m = re.search(rb"stream\r?\n(.*?)\r?\nendstream", cbody, re.DOTALL)
                if s_m:
                    content_stream_bytes = _decode_stream_data(s_m.group(1), cbody)

        text = _extract_text_from_content_stream(content_stream_bytes).strip()
        pages_text[page_num] = text

    return pages_text


def extract_pages(file_path: Union[str, Path]) -> tuple[dict[int, str], str]:
    """Extracts text page by page from a PDF file.

    Args:
        file_path: Path to the target PDF file.

    Returns:
        A tuple of (pages_dict, document_id) where:
            pages_dict: Mapping of 1-based page numbers to extracted text.
            document_id: Deterministic document hash identifier.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty, corrupted, or an invalid PDF.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found at '{path}'")

    file_size = path.stat().st_size
    if file_size == 0:
        raise ValueError(f"PDF file at '{path}' is empty (0 bytes)")

    try:
        raw_bytes = path.read_bytes()
    except Exception as e:
        raise ValueError(f"Failed to read PDF file at '{path}': {e}") from e

    # Check for PDF magic header in first 1024 bytes
    if b"%PDF" not in raw_bytes[:1024]:
        raise ValueError(f"File at '{path}' is not a valid PDF (missing %PDF header)")

    # Compute deterministic document identifier
    doc_hash = hashlib.sha256(raw_bytes).hexdigest()[:12]
    document_id = f"doc_{doc_hash}"

    # Try pypdf if installed, otherwise use pure-Python parser
    pages_text: dict[int, str] = {}
    if _HAS_PYPDF:
        try:
            reader = pypdf.PdfReader(path)
            for idx, page in enumerate(reader.pages, start=1):
                txt = page.extract_text() or ""
                pages_text[idx] = txt.strip()
        except Exception as e:
            logger.debug("pypdf parsing failed (%s), falling back to pure-Python parser", e)
            pages_text = {}

    if not pages_text:
        try:
            pages_text = _parse_pdf_pure_python(raw_bytes)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF at '{path}': {e}") from e

    return pages_text, document_id

