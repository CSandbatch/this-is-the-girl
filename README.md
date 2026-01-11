# TexGraph

TexGraph is a layered LuaLaTeX project for producing a full-length poetry book and multiple style proofs from the same source.

## Quick start

- Build the full project: `cd project; latexmk -pdflua -interaction=nonstopmode -halt-on-error proof.tex`
- Build style proofs: `cd project/proofs; latexmk -pdflua -interaction=nonstopmode -halt-on-error proof-noir_optimal.tex`

## Docs

- Agent workflow + build notes: `docs/workflow.md`
- Proof drivers: `project/proofs/README.md`

Style notes (human-readable sources for the regimes) live in `docs/style-notes/`.

## Preamble

- Repo templates (3 layers): `preamble/layers/`
- Project wrappers (3 layers): `project/preamble/`

## Secrets

Secrets live in `.secrets.json` at repo root and should not be committed.
