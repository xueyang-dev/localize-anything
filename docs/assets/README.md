# docs/assets/

Asset inventory for the Localize Anything documentation.

## SVGs

| File | Purpose | Used in | Maintained |
|------|---------|---------|------------|
| `workflow-dark.svg` | Main localization workflow (9 steps + QA loop) | README.md, README.en.md | hand-edited |
| `architecture-layers.svg` | Protocol → Runtime → Agent → Adapter layer stack | README.md | hand-edited |
| `delivery-package.svg` | Delivery package structure and evidence chain | docs/delivery-package.svg | hand-edited |
| `benchmark-antennapod.svg` | AntennaPod DeepSeek benchmark summary | README.md | hand-edited |

## Conventions

- All SVGs are dark-theme compatible (`#0f172a` background)
- Editable by hand — no build step, no external toolchain dependency
- Keep file sizes under 10 KB
- Do not commit raster images > 1 MB

## Adding new diagrams

1. Create the SVG in this directory
2. Reference it from the relevant markdown file using `![alt](docs/assets/filename.svg)`
3. Update this README
