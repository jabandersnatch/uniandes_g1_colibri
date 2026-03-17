---
name: citation-search
description: Find, verify, and format academic citations — BibTeX management, reference verification, and bibliography maintenance
context: fork
---

# Citation Search and Management

Use this skill when finding references, building bibliographies, or managing citations.

## Finding References

### Search Strategy
When the user needs a citation for a claim or concept:

1. **Web search** for the paper using precise academic terms
2. **Verify** the paper exists — check title, authors, venue, year
3. **Generate BibTeX** entry with all required fields
4. **Add** to `paper/references.bib`

### BibTeX Entry Templates

**Conference paper:**
```bibtex
@inproceedings{authorYEARkeyword,
  author    = {First Last and First Last},
  title     = {Full Paper Title},
  booktitle = {Proceedings of the Xth Conference Name (ABBREV)},
  year      = {2024},
  pages     = {1--10},
  doi       = {10.xxxx/xxxxx},
}
```

**Journal article:**
```bibtex
@article{authorYEARkeyword,
  author  = {First Last and First Last},
  title   = {Full Paper Title},
  journal = {Journal Name},
  volume  = {42},
  number  = {3},
  pages   = {100--115},
  year    = {2024},
  doi     = {10.xxxx/xxxxx},
}
```

**arXiv preprint:**
```bibtex
@misc{authorYEARkeyword,
  author = {First Last and First Last},
  title  = {Full Paper Title},
  year   = {2024},
  eprint = {2401.12345},
  archiveprefix = {arXiv},
  primaryclass  = {cs.DS},
}
```

**Book:**
```bibtex
@book{authorYEARkeyword,
  author    = {First Last},
  title     = {Book Title},
  publisher = {Publisher Name},
  year      = {2024},
  edition   = {3rd},
  isbn      = {978-x-xxx-xxxxx-x},
}
```

### Key Naming Convention
Format: `firstauthorlastnameYEARoneword`
- `cormen2009introduction` for CLRS textbook
- `knuth1997art` for The Art of Computer Programming
- `dijkstra1959shortest` for Dijkstra's shortest path paper

## Citation Verification Checklist
Before adding any reference:
- [ ] Paper title is exact (not paraphrased)
- [ ] All author names are correct and complete
- [ ] Venue name matches the official proceedings/journal title
- [ ] Year is the publication year (not submission or arXiv upload year)
- [ ] Page numbers are included if available
- [ ] DOI is included if available
- [ ] No duplicate entries in `references.bib`

## In-Text Citation Guidelines
- Use `\cite{key}` for parenthetical: "...has been studied extensively \cite{cormen2009introduction}."
- Use `\citet{key}` (with natbib) for textual: "Cormen et al.~\citet{cormen2009introduction} showed..."
- Multiple citations: `\cite{key1,key2,key3}` — sorted by year
- Specific results: "Theorem~3 in \cite{key}" or "\cite[Theorem~3]{key}"

## CRITICAL RULES
- **NEVER fabricate a citation**. If you cannot verify a paper exists, say so explicitly.
- **NEVER guess author names, venues, or years**. When uncertain, flag with `% TODO: verify`
- Prefer citing the **original/primary source**, not a survey or textbook that mentions it
- If a paper has been published in both arXiv and a venue, cite the **venue version**
- Check for and remove orphaned BibTeX entries (entries not cited in the paper)

## Bibliography Maintenance
Periodically run:
```bash
# Find undefined references
grep -o '\\cite{[^}]*}' paper/sections/*.tex | sed 's/.*\\cite{//;s/}//' | tr ',' '\n' | sort -u > /tmp/cited.txt
grep '@.*{' paper/references.bib | sed 's/@.*{//;s/,//' | sort -u > /tmp/defined.txt
comm -23 /tmp/cited.txt /tmp/defined.txt  # cited but not defined
comm -13 /tmp/cited.txt /tmp/defined.txt  # defined but not cited
```
