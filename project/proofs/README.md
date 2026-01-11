# Style Proofs

Each `proof-*.tex` file is a full-book driver that differs only by the style regime it inputs from `project/preamble/styles/proof/`.

Build from `project/proofs/`:

```powershell
latexmk -pdflua -interaction=nonstopmode -halt-on-error proof-noir_optimal.tex
```

Available proof drivers:

- `proof-blackened.tex` - Regime V (Blackened Baroque)
- `proof-noir_optimal.tex` - Regime VI (Noir, optimized)
- `proof-noir_optimal_serif4.tex` - Regime VI (Noir, optimized; Source Serif 4 body)
- `working_draft_1.tex` - Snapshot driver (Noir optimal + Source Serif 4)

Other historical proof drivers/PDFs are kept under `archive/proofs/`.
