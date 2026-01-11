# Agent Workflow (LuaLaTeX + Proof Sets)

## Targets

- Full project PDF: `project/proof.tex` -> `project/proof.pdf`
- Style proofs: `project/proofs/proof-*.tex` -> `project/proofs/proof-*.pdf`

## Preconditions (one-time)

1. TeX Live (or equivalent) is installed and `lualatex` + `latexmk` are on PATH.
2. A root-level junction exists so LuaTeX can reliably open the local font cache when building from `project/`:
   - Expected: `fonts/` (repo root) -> `project/fonts/`

Create the junction (only if missing):

```powershell
if (-not (Test-Path -LiteralPath "fonts")) { cmd /c "mklink /J fonts project\\fonts" }
```

## Secrets

Secrets live in `.secrets.json` at repo root. Do not commit this file.

Expected keys:

- `google_fonts_api_key` (required for the Google Fonts downloader)
- `OPENAI_API_KEY` (optional; reserved for agent tooling)

## Fonts (Google Fonts -> local cache)

### Files

- Secrets: `.secrets.json` (repo root)
- Downloader: `project/scripts/fetch-google-fonts.ps1`
- Cache dir: `project/fonts/google/` (marker file: `project/fonts/google/.texgraph-fonts`)

## Preamble layout

TexGraph uses three preamble layers.

- Repo templates: `preamble/layers/`
- Project wrappers (used by drivers): `project/preamble/`

### Fetch/update

```powershell
powershell -ExecutionPolicy Bypass -File project/scripts/fetch-google-fonts.ps1
```

Notes:

- The downloader is idempotent: it skips files already present.
- Proof regimes prefer local `*.ttf` files and fall back to installed fonts if the cache is missing.

## Build - full project

From `project/`:

```powershell
cd project
latexmk -pdflua -interaction=nonstopmode -halt-on-error proof.tex
```

Outputs:

- `project/proof.pdf`

## Build - proof set (active)

From `project/proofs/`:

```powershell
cd project/proofs
latexmk -pdflua -interaction=nonstopmode -halt-on-error proof-noir_optimal.tex
latexmk -pdflua -interaction=nonstopmode -halt-on-error proof-noir_optimal_serif4.tex
latexmk -pdflua -interaction=nonstopmode -halt-on-error proof-blackened.tex
```

## Sweep build artifacts (keep PDFs)

Use `latexmk -c` (small cleanup; keeps PDF):

```powershell
cd project
latexmk -c proof.tex

cd ../project/proofs
Get-ChildItem -Filter "proof-*.tex" | ForEach-Object { latexmk -c $_.Name }
```

## Single-pass compile (debug only)

If you explicitly want just one engine run (no multi-pass cross-ref resolution), use `lualatex` directly:

```powershell
cd project
lualatex -interaction=nonstopmode -halt-on-error proof.tex
```

## Troubleshooting

### pdfLaTeX keeps getting used

If building via VS Code LaTeX Workshop, ensure your recipe uses `latexmk` with `-pdflua` and set it as default.
Example snippet: `docs/vscode-latex-workshop-settings.json`.

### Fonts "not found"

Check:

1. `project/fonts/google/` contains `.ttf` files.
2. The repo root has the `fonts` junction (`fonts/` -> `project/fonts/`).
3. You are using LuaLaTeX (not pdfLaTeX).

### Proof style doesn't change

Each proof driver sets `\TexGraphRegimeFile` before `\input{proof-template.tex}`.
Verify the correct driver is being built (e.g. `project/proofs/proof-noir_optimal.tex`).
