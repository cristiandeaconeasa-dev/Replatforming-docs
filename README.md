# Pricer Documentation — PoC Hub

This is the **Proof of Concept** hub for Pricer AB's documentation-as-code platform. It aggregates documentation from multiple PricerAB repositories into a single MkDocs Material site.

👉 **[View the documentation site →](https://cristiandeaconeasa-dev.github.io/Replatforming-docs/)**

## How it works

1. **Source repos** are listed in [`repos.txt`](repos.txt) — each repo that has a `docs/` folder gets pulled in
2. **CI pipeline** (`.github/workflows/build-and-deploy.yml`) runs daily at 6am UTC or on push
3. **`scripts/sync-repos.sh`** clones all source repos
4. **`scripts/generate-nav.py`** builds the sidebar navigation from cloned repos
5. **MkDocs Material** generates a static HTML site
6. **GitHub Pages** serves the site

## Adding a new doc source

1. Add the repo name to `repos.txt`
2. Add a category mapping in `scripts/generate-nav.py`
3. Push — the next build picks it up automatically

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Clone source repos and build
./scripts/sync-repos.sh
mkdocs serve    # Preview at http://localhost:8000
```

> **Note:** This is a PoC hub under `cristiandeaconeasa-dev`. The production hub will be `PricerAB/platform-docs-hub`.
