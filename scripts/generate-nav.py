#!/usr/bin/env python3
"""generate-nav.py — Scan _sources/ for docs and generate mkdocs nav structure.

For each cloned repo in _sources/:
1. If the repo has docs/mkdocs.yml, extract its nav structure.
2. Otherwise, scan docs/ for .md files and create a flat nav.
3. Merge all navs into the hub's mkdocs.yml.
"""

import os
from typing import Optional
import yaml
from pathlib import Path

SOURCES_DIR = "docs/_sources"
MKDOCS_YML = "mkdocs.yml"
NAV_MARKER = "# REST OF NAV IS AUTO-GENERATED FROM _sources/"

# Category mapping — which top-level section each repo belongs to.
# Add repos to the appropriate category as they're onboarded.
CATEGORY_MAP = {
    # Platform Architecture
    "evo-dtoflow-protos": {
        "section": "Platform Architecture",
        "label": "DTOflow & DTOs",
    },

    # Services (add as services are onboarded)
    # "platform-item-registry-api": {
    #     "section": "Services",
    #     "label": "Item Registry API",
    # },
    # "platform-link-service": {
    #     "section": "Services",
    #     "label": "Link Service",
    # },

    # Consumer Apps
    # "chain-management-centralization": {
    #     "section": "Consumer Apps",
    #     "label": "Central-Manager",
    # },
    # "plaza-mobile-ui-backend": {
    #     "section": "Consumer Apps",
    #     "label": "Plaza Mobile BFF",
    # },
}


def scan_repo_docs(repo_name: str, repo_path: Path) -> Optional[list[dict]]:
    """Scan a repo's docs/ folder and return nav entries."""
    docs_path = repo_path / "docs"
    if not docs_path.is_dir():
        return None

    # Check for per-repo mkdocs.yml which may have a nav section
    per_repo_mkdocs = repo_path / "mkdocs.yml"
    if per_repo_mkdocs.exists():
        try:
            with open(per_repo_mkdocs) as f:
                config = yaml.safe_load(f)
            if config and "nav" in config:
                return rewrite_paths(repo_name, config["nav"])
        except Exception:
            pass

    # Fallback: flat list of .md files
    md_files = sorted(docs_path.rglob("*.md"))
    if not md_files:
        return None

    nav = []
    for f in md_files:
        rel = f.relative_to(docs_path)
        src_path = f"_sources/{repo_name}/docs/{rel}"
        title = f.stem.replace("-", " ").replace("_", " ").title()
        if rel == Path("index.md"):
            nav.insert(0, {title: src_path})
        else:
            nav.append({title: src_path})
    return nav


def rewrite_paths(repo_name: str, nav: list) -> list:
    """Rewrite paths in a nav structure to point to _sources/."""
    result = []
    for item in nav:
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str):
                    if not value.startswith("http") and not value.startswith("_"):
                        if value.startswith("../") or not value.startswith("docs/"):
                            value = f"_sources/{repo_name}/{value.lstrip('./')}"
                        else:
                            value = f"_sources/{repo_name}/{value}"
                        value = value.replace("//", "/")
                    result.append({key: value})
                elif isinstance(value, list):
                    result.append({key: rewrite_paths(repo_name, value)})
                else:
                    result.append(item)
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(item)
    return result


def main():
    sources = Path(SOURCES_DIR)
    if not sources.is_dir():
        print("No _sources/ directory — skipping nav generation")
        return

    # Group nav entries by section
    sections: dict[str, list] = {}

    for repo_dir in sorted(sources.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue

        repo_name = repo_dir.name
        nav_entries = scan_repo_docs(repo_name, repo_dir)
        if not nav_entries:
            continue

        category = CATEGORY_MAP.get(repo_name, {})
        section = category.get("section", "Other")
        label = category.get("label", repo_name.replace("-", " ").title())

        if section is None:  # Skip (e.g., hub repo itself)
            continue

        if section not in sections:
            sections[section] = []

        sections[section].append({label: nav_entries})

    # Generate nav lines
    nav_lines = []
    for section in ["Platform Architecture", "Services", "Consumer Apps",
                     "Infrastructure", "Other"]:
        if section in sections:
            nav_lines.append(f"  - {section}:")
            for entry in sections[section]:
                for label, items in entry.items():
                    nav_lines.append(f"      - {label}:")
                    for nav_item in items:
                        nav_lines.append(
                            f"        - {yaml.dump(nav_item, default_flow_style=True).strip()}"
                        )

    # Update mkdocs.yml
    with open(MKDOCS_YML, "r") as f:
        content = f.read()

    if NAV_MARKER not in content:
        print(f"ERROR: Nav marker not found in {MKDOCS_YML}")
        return

    before = content.split(NAV_MARKER)[0]
    new_nav = "\n".join(nav_lines)
    new_content = f"{before}{NAV_MARKER}\n{new_nav}\n"

    with open(MKDOCS_YML, "w") as f:
        f.write(new_content)

    print(
        f"Generated nav with {sum(len(v) for v in sections.values())} repos "
        f"across {len(sections)} sections"
    )


if __name__ == "__main__":
    main()
