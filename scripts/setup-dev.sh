#!/bin/bash
# Setup script for development environment with pre-commit

set -e

echo "Setting up seriesoftubes development environment..."

# Check if in virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment. Consider creating one:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate  # On Windows: venv\\Scripts\\activate"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install project with dev dependencies
echo "📦 Installing project with development dependencies..."
pip install -e ".[dev,api]"

# Install pre-commit
echo "🔧 Installing pre-commit hooks..."
pre-commit install
pre-commit install --hook-type commit-msg  # For commit message linting

# Install frontend dependencies if frontend exists
if [ -d "frontend" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Run pre-commit on all files to check setup
echo "✅ Running pre-commit on all files to verify setup..."
pre-commit run --all-files || true

echo ""
echo "✨ Setup complete! Development environment is ready."
echo ""
echo "Tips:"
echo "  - Run 'pre-commit run --all-files' to check all files"
echo "  - Run 'pre-commit run <hook-id>' to run specific hooks"
echo "  - Use 'git commit --no-verify' to skip hooks (not recommended)"
echo "  - Hooks will run automatically on git commit"
