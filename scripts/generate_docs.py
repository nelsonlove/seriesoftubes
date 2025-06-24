#!/usr/bin/env python3
"""
Generate documentation from SeriesOfTubes workflow schema.

This script parses the JSON Schema and generates:
- Markdown reference documentation
- VS Code snippets
- Quick reference guides
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from seriesoftubes.docs.schema_parser import SchemaDocGenerator


def main():
    """Generate documentation from workflow schema."""
    schema_path = project_root / "src" / "seriesoftubes" / "schemas" / "workflow-schema.yaml"
    docs_dir = project_root / "docs"

    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}")
        sys.exit(1)

    # Create documentation directories
    (docs_dir / "reference" / "nodes").mkdir(parents=True, exist_ok=True)
    (docs_dir / "guides").mkdir(parents=True, exist_ok=True)
    (docs_dir / "examples").mkdir(parents=True, exist_ok=True)

    # Initialize generator
    generator = SchemaDocGenerator(schema_path)

    # Generate node type documentation
    print("Generating node type documentation...")
    node_types = generator.get_node_types()

    for node_type in node_types:
        doc_content = generator.generate_node_documentation(node_type)
        doc_path = docs_dir / "reference" / "nodes" / f"{node_type}.md"
        doc_path.write_text(doc_content)
        print(f"  ✓ Generated {doc_path}")

    # Generate workflow guide
    print("\nGenerating workflow guide...")
    workflow_guide = generator.generate_workflow_guide()
    guide_path = docs_dir / "guides" / "workflow-structure.md"
    guide_path.write_text(workflow_guide)
    print(f"  ✓ Generated {guide_path}")

    # Generate quick reference
    print("\nGenerating quick reference...")
    quick_ref = generator.generate_quick_reference()
    ref_path = docs_dir / "reference" / "quick-reference.md"
    ref_path.write_text(quick_ref)
    print(f"  ✓ Generated {ref_path}")

    # Generate VS Code snippets
    print("\nGenerating VS Code snippets...")
    snippets = generator.generate_vscode_snippets()
    snippets_path = project_root / ".vscode" / "seriesoftubes.code-snippets"
    snippets_path.parent.mkdir(exist_ok=True)
    with open(snippets_path, "w") as f:
        json.dump(snippets, f, indent=2)
    print(f"  ✓ Generated {snippets_path}")

    print("\n✅ Documentation generation complete!")


if __name__ == "__main__":
    main()
