"""Documentation API routes for serving generated docs."""

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/docs", tags=["documentation"])

# Path to the docs directory
DOCS_ROOT = Path(__file__).parent.parent.parent.parent / "docs"


class DocsListResponse(BaseModel):
    """Response for docs list endpoint"""
    
    success: bool = Field(..., description="Whether the request succeeded")
    message: str = Field(..., description="Response message")
    data: list[dict[str, Any]] = Field(..., description="List of documentation files")


class DocFile:
    """Represents a documentation file with metadata."""
    
    def __init__(self, path: Path, relative_path: str):
        self.path = path
        self.relative_path = relative_path
        self.title = self._extract_title()
        self.category = self._determine_category()
    
    def _extract_title(self) -> str:
        """Extract title from markdown file."""
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('# Node Type: `'):
                    # Extract node type name from title like "# Node Type: `llm`"
                    return first_line.replace('# Node Type: `', '').replace('`', '').strip() + ' Node'
                elif first_line.startswith('# '):
                    return first_line[2:].strip()
        except Exception:
            pass
        
        # Fallback to filename
        return self.path.stem.replace('-', ' ').replace('_', ' ').title()
    
    def _determine_category(self) -> str:
        """Determine category based on file path."""
        parts = Path(self.relative_path).parts
        
        if 'reference' in parts and 'nodes' in parts:
            return 'Node Types'
        elif 'guides' in parts:
            return 'Guides'
        elif 'reference' in parts:
            return 'Reference'
        elif 'examples' in parts:
            return 'Examples'
        else:
            return 'Documentation'
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'path': self.relative_path,
            'title': self.title,
            'category': self.category,
        }


def _discover_docs() -> list[DocFile]:
    """Discover all markdown files in the docs directory."""
    if not DOCS_ROOT.exists():
        return []
    
    docs = []
    for md_file in DOCS_ROOT.rglob("*.md"):
        if md_file.is_file():
            relative_path = str(md_file.relative_to(DOCS_ROOT))
            docs.append(DocFile(md_file, relative_path))
    
    # Sort by category and title
    docs.sort(key=lambda d: (d.category, d.title))
    return docs


@router.get("/")
async def list_docs() -> DocsListResponse:
    """List all available documentation files with metadata."""
    try:
        docs = _discover_docs()
        return DocsListResponse(
            success=True,
            message=f"Found {len(docs)} documentation files",
            data=[doc.to_dict() for doc in docs]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documentation: {str(e)}")


@router.get("/{file_path:path}")
async def get_doc_content(file_path: str) -> Response:
    """Get the content of a specific documentation file."""
    try:
        # Sanitize path to prevent directory traversal
        safe_path = Path(file_path).as_posix()
        if '..' in safe_path or safe_path.startswith('/'):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        full_path = DOCS_ROOT / safe_path
        
        # Ensure the file exists and is within docs directory
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="Documentation file not found")
        
        try:
            # Resolve to check it's actually within DOCS_ROOT
            full_path.resolve().relative_to(DOCS_ROOT.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Read and return the markdown content
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read documentation: {str(e)}")