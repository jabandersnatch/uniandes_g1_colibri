#!/bin/bash
# Build all standalone TikZ figures to SVG
# Uses pdflatex -> dvisvgm --pdf

set -e
cd "$(dirname "$0")"

FAILURES=0

for texfile in fig_*.tex; do
    base="${texfile%.tex}"
    echo "=== Building $base ==="

    # Compile to PDF
    if pdflatex -interaction=nonstopmode "$texfile" > "${base}.log" 2>&1; then
        echo "  PDF OK"
    else
        echo "  PDF FAILED - check ${base}.log"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # Convert PDF to SVG using pdftocairo (poppler)
    if pdftocairo -svg "${base}.pdf" "${base}.svg" 2>/dev/null; then
        echo "  SVG OK -> ${base}.svg"
    else
        echo "  SVG conversion FAILED"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # Clean auxiliary files
    rm -f "${base}.aux" "${base}.log" "${base}.pdf"
done

echo ""
if [ $FAILURES -eq 0 ]; then
    echo "All figures built successfully!"
else
    echo "$FAILURES figure(s) failed."
fi

echo ""
echo "Generated SVGs:"
ls -la *.svg 2>/dev/null || echo "  (none)"
