"""Compress a PDF: re-encode images as JPEG, dedup fonts added by insertion,
strip metadata, subset fonts, save with garbage collection.

CLI: ``python lib/compress_pdf.py <in> [<out>] [--quality 80]``
If ``<out>`` is omitted the input is replaced in place (via a temp file,
because PyMuPDF cannot save over an open document).
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import tempfile

import fitz

logger = logging.getLogger(__name__)


def _dedup_fonts(doc):
    """Share byte-identical embedded font streams between FontDescriptors.

    The TextWriter path in pdf_utils re-embeds the font it extracted from the
    template, so the inserted FontFile stream is a byte-for-byte copy of an
    existing one. Group descriptors by stream hash and point every duplicate
    at the first stream; ``save(garbage=4)`` then drops the orphans. Streams
    are never cleared, so no descriptor is left pointing at an invalid font.
    Returns the number of bytes made redundant.
    """
    first_by_hash = {}  # md5 -> stream xref
    removed = 0
    for xref in range(1, doc.xref_length()):
        obj = doc.xref_object(xref)
        if not obj or '/FontFile' not in obj:
            continue
        for key in ('FontFile2', 'FontFile3', 'FontFile'):
            m = re.search(r'/%s\s+(\d+)\s+0\s+R' % key, obj)
            if not m:
                continue
            ff_xref = int(m.group(1))
            stream = doc.xref_stream(ff_xref)
            if not stream:
                continue
            digest = hashlib.md5(stream).hexdigest()
            keep = first_by_hash.setdefault(digest, ff_xref)
            if keep != ff_xref:
                doc.xref_set_key(xref, key, f"{keep} 0 R")
                removed += len(stream)
                fn = re.search(r'/FontName\s+/(\S+)', obj)
                logger.info("Dedup: font stream xref %d (%dKB, '%s') -> shared xref %d",
                            ff_xref, len(stream) // 1024, fn.group(1) if fn else "?", keep)
    return removed


def compress_pdf(input_path: str, output_path: str | None = None, quality: int = 80) -> str:
    """Compress ``input_path``. ``output_path`` None → replace the input in
    place. Returns the path written."""
    in_place = output_path is None
    if in_place:
        fd, output_path = tempfile.mkstemp(
            suffix=".pdf", dir=os.path.dirname(os.path.abspath(input_path))
        )
        os.close(fd)

    doc = fitz.open(input_path)
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            img_bytes = pix.tobytes("jpeg", jpg_quality=quality)
            doc.update_stream(xref, img_bytes)

    # Deduplicate font embeddings
    _dedup_fonts(doc)

    # Strip metadata
    doc.set_metadata({})
    doc.del_xml_metadata()

    try:
        # subset_fonts() warns about cleared streams — these are harmless
        fitz.TOOLS.mupdf_warnings(reset=True)
        doc.subset_fonts()
        fitz.TOOLS.mupdf_warnings(reset=True)  # discard warnings
        doc.save(output_path, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

    orig_size = os.path.getsize(input_path)
    comp_size = os.path.getsize(output_path)
    reduction = (1 - comp_size / orig_size) * 100 if orig_size > 0 else 0
    logger.info(
        "Compression: %.1fKB -> %.1fKB (%.1f%% reduction)",
        orig_size / 1024, comp_size / 1024, reduction,
    )

    if in_place:
        os.replace(output_path, input_path)
        output_path = input_path
    return output_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input")
    parser.add_argument("output", nargs="?", default=None,
                        help="omit to replace the input in place")
    parser.add_argument("--quality", type=int, default=80, help="JPEG quality (default 80)")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.input):
        logger.error("Input not found: %s", args.input)
        return 2
    out = compress_pdf(args.input, args.output, quality=args.quality)
    logger.info("Written: %s (%.1f KB)", out, os.path.getsize(out) / 1024)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
