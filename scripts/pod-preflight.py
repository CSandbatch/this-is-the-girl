import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


PT_PER_IN = 72.0


def pt_to_in(pt: float) -> float:
    return pt / PT_PER_IN


@dataclass(frozen=True)
class MarginThresholdsIn:
    top: float
    bottom: float
    outside: float
    inside: float


def kdp_no_bleed_thresholds_in(page_count: int) -> MarginThresholdsIn:
    # KDP paperback guidance (common tiers). We choose the inside/gutter requirement by page count.
    # 24–150 pages -> 0.375 in
    # 151–300 pages -> 0.5 in
    # 301–500 pages -> 0.625 in
    # 501–700 pages -> 0.75 in
    if page_count <= 150:
        inside = 0.375
    elif page_count <= 300:
        inside = 0.5
    elif page_count <= 500:
        inside = 0.625
    else:
        inside = 0.75
    return MarginThresholdsIn(top=0.25, bottom=0.25, outside=0.25, inside=inside)


def union_bbox(bboxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    it = iter(bboxes)
    x0, y0, x1, y1 = next(it)
    for a0, b0, a1, b1 in it:
        x0 = min(x0, a0)
        y0 = min(y0, b0)
        x1 = max(x1, a1)
        y1 = max(y1, b1)
    return x0, y0, x1, y1


def page_content_bbox(page) -> tuple[float, float, float, float] | None:
    # Union of all text + image blocks.
    d = page.get_text("dict")
    bboxes: list[tuple[float, float, float, float]] = []
    for block in d.get("blocks", []):
        bbox = block.get("bbox")
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        if (x1 - x0) <= 0.25 or (y1 - y0) <= 0.25:
            continue
        if block.get("type") in (0, 1):  # text or image
            bboxes.append((x0, y0, x1, y1))
    if not bboxes:
        return None
    return union_bbox(bboxes)


ref_re = re.compile(r"^(\d+)\s+\d+\s+R$")


def ref_to_xref(ref_str: str | None) -> int | None:
    if not ref_str or ref_str == "null":
        return None
    m = ref_re.match(ref_str.strip())
    return int(m.group(1)) if m else None


def font_is_embedded(doc, font_xref: int) -> tuple[bool, str]:
    subtype = doc.xref_get_key(font_xref, "Subtype")[1]

    def descriptor_has_fontfile(desc_xref: int) -> bool:
        for key in ("FontFile", "FontFile2", "FontFile3"):
            v = doc.xref_get_key(desc_xref, key)[1]
            if v and v != "null":
                return True
        return False

    if subtype == "/Type0":
        v = doc.xref_get_key(font_xref, "DescendantFonts")[1]
        if not v or v == "null":
            return False, "Type0 missing DescendantFonts"
        m = re.search(r"(\d+)\s+\d+\s+R", v)
        if not m:
            return False, f"cannot parse DescendantFonts: {v}"
        descendant_xref = int(m.group(1))
        fd_xref = ref_to_xref(doc.xref_get_key(descendant_xref, "FontDescriptor")[1])
        if not fd_xref:
            return False, "Descendant font missing FontDescriptor"
        return descriptor_has_fontfile(fd_xref), f"FontDescriptor xref={fd_xref}"

    fd_xref = ref_to_xref(doc.xref_get_key(font_xref, "FontDescriptor")[1])
    if not fd_xref:
        return False, "missing FontDescriptor"
    return descriptor_has_fontfile(fd_xref), f"FontDescriptor xref={fd_xref}"


def check_pdf(path: Path, expected_trim_in: tuple[float, float] | None) -> int:
    import fitz  # PyMuPDF

    failures = 0
    doc = fitz.open(path)

    print(f"pdf={path}")
    print(f"pages={doc.page_count} encrypted={doc.is_encrypted}")

    w_pt = doc[0].rect.width
    h_pt = doc[0].rect.height
    w_in = pt_to_in(w_pt)
    h_in = pt_to_in(h_pt)
    print(f"trim={w_in:.4f}in x {h_in:.4f}in (mediabox)")
    if expected_trim_in is not None:
        exp_w, exp_h = expected_trim_in
        if abs(w_in - exp_w) > 1e-3 or abs(h_in - exp_h) > 1e-3:
            failures += 1
            print(f"FAIL trim_expected={exp_w}in x {exp_h}in")

    sizes = {}
    for i in range(doc.page_count):
        page = doc.load_page(i)
        key = (round(page.rect.width, 3), round(page.rect.height, 3))
        sizes[key] = sizes.get(key, 0) + 1
    if len(sizes) != 1:
        failures += 1
        print("FAIL inconsistent_page_sizes:")
        for (w, h), count in sorted(sizes.items(), key=lambda kv: -kv[1]):
            print(f"  {w}x{h}pt count={count}")

    annots = 0
    widgets = 0
    for i in range(doc.page_count):
        page = doc.load_page(i)
        a = page.annots()
        if a:
            for _ in a:
                annots += 1
        w = page.widgets()
        if w:
            for _ in w:
                widgets += 1
    print(f"annotations={annots} form_fields={widgets}")

    # Fonts (embedded?)
    seen_fonts = {}
    for i in range(doc.page_count):
        page = doc.load_page(i)
        for f in page.get_fonts(full=True):
            xref = f[0]
            basefont = f[3]
            seen_fonts.setdefault(xref, basefont)
    missing_fonts = []
    for xref, basefont in sorted(seen_fonts.items()):
        ok, reason = font_is_embedded(doc, xref)
        if not ok:
            missing_fonts.append((xref, basefont, reason))
    if missing_fonts:
        failures += 1
        print(f"FAIL fonts_not_embedded={len(missing_fonts)}")
        for row in missing_fonts[:20]:
            print(" ", row)
        if len(missing_fonts) > 20:
            print("  ...")
    else:
        print(f"fonts_embedded_ok unique_fonts={len(seen_fonts)}")

    # Images: effective DPI
    low_dpi = []
    for page_index in range(doc.page_count):
        page_no = page_index + 1
        page = doc.load_page(page_index)
        for img in page.get_images(full=True):
            xref = img[0]
            cs = img[5]
            info = doc.extract_image(xref)
            px_w, px_h = info.get("width"), info.get("height")
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            dpi_min = None
            for r in rects:
                disp_w_in = pt_to_in(r.width)
                disp_h_in = pt_to_in(r.height)
                if disp_w_in <= 0 or disp_h_in <= 0:
                    continue
                dpi_w = px_w / disp_w_in
                dpi_h = px_h / disp_h_in
                d = min(dpi_w, dpi_h)
                dpi_min = d if dpi_min is None else min(dpi_min, d)
            if dpi_min is not None and dpi_min < 300:
                low_dpi.append((page_no, xref, px_w, px_h, float(dpi_min), cs))
    if low_dpi:
        failures += 1
        print(f"FAIL low_dpi_images={len(low_dpi)} (threshold 300)")
        for row in low_dpi[:20]:
            print(" ", row)
        if len(low_dpi) > 20:
            print("  ...")
    else:
        print("images_dpi_ok (all >= 300 or none)")

    # Content bounding box margins (no-bleed heuristic)
    thresholds = kdp_no_bleed_thresholds_in(doc.page_count)
    worst = {"top": (999.0, None), "bottom": (999.0, None), "inside": (999.0, None), "outside": (999.0, None)}
    violations = []
    for i in range(doc.page_count):
        page_no = i + 1
        page = doc.load_page(i)
        bbox = page_content_bbox(page)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        left = pt_to_in(x0)
        right = pt_to_in(w_pt - x1)
        top = pt_to_in(y0)
        bottom = pt_to_in(h_pt - y1)
        if page_no % 2 == 1:
            inside, outside = left, right
        else:
            inside, outside = right, left
        for key, val in (("top", top), ("bottom", bottom), ("inside", inside), ("outside", outside)):
            if val < worst[key][0]:
                worst[key] = (val, page_no)
        if top < thresholds.top or bottom < thresholds.bottom or outside < thresholds.outside or inside < thresholds.inside:
            violations.append((page_no, top, bottom, inside, outside))

    print(
        "worst_margins_in "
        f"top={worst['top'][0]:.3f}(p{worst['top'][1]}) "
        f"bottom={worst['bottom'][0]:.3f}(p{worst['bottom'][1]}) "
        f"inside={worst['inside'][0]:.3f}(p{worst['inside'][1]}) "
        f"outside={worst['outside'][0]:.3f}(p{worst['outside'][1]})"
    )
    print(
        "thresholds_in "
        f"top>={thresholds.top} bottom>={thresholds.bottom} outside>={thresholds.outside} inside>={thresholds.inside}"
    )
    if violations:
        failures += 1
        print(f"FAIL margin_violations={len(violations)}")
        for page_no, top, bottom, inside, outside in violations[:25]:
            print(f"  p{page_no:03d} top={top:.3f} bottom={bottom:.3f} inside={inside:.3f} outside={outside:.3f}")
        if len(violations) > 25:
            print("  ...")
    else:
        print("margins_ok (heuristic)")

    doc.close()
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Amazon KDP POD preflight checks (heuristic).")
    parser.add_argument(
        "pdf",
        nargs="?",
        default="project/final_pass/build/final_pass.pdf",
        help="Path to the PDF to check (default: project/final_pass/build/final_pass.pdf).",
    )
    parser.add_argument("--trim", default="5.5x8.5", help="Expected trim in inches as WxH (default: 5.5x8.5).")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR missing pdf: {pdf_path}", file=sys.stderr)
        return 2

    expected = None
    if args.trim:
        try:
            w_str, h_str = args.trim.lower().split("x", 1)
            expected = (float(w_str), float(h_str))
        except Exception:
            print(f"ERROR invalid --trim: {args.trim} (expected WxH like 5.5x8.5)", file=sys.stderr)
            return 2

    failures = check_pdf(pdf_path, expected)
    if failures:
        print(f"RESULT FAIL failures={failures}")
        return 1
    print("RESULT PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

