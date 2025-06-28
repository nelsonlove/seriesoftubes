#!/usr/bin/env python3
"""Generate secure configuration for SeriesOfTubes"""

import sys
from pathlib import Path

from seriesoftubes.config_validation import generate_secure_config_template


def main() -> None:
    """Generate secure configuration template"""
    print("SeriesOfTubes Secure Configuration Generator")
    print("=" * 45)
    print()
    
    # Check if .env already exists
    env_path = Path(".env")
    if env_path.exists():
        response = input(".env file already exists. Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)
    
    # Generate template
    template = generate_secure_config_template()
    
    # Write to file
    env_path.write_text(template)
    print(f"✓ Generated secure configuration in {env_path}")
    print()
    print("Next steps:")
    print("1. Review and update the generated .env file")
    print("2. Set strong passwords for Redis and PostgreSQL")
    print("3. Update CORS_ORIGINS for your domain")
    print("4. Keep the JWT_SECRET_KEY secure and never commit it")
    print()
    print("To validate your configuration, run:")
    print("  python -m seriesoftubes.config_validation")


if __name__ == "__main__":
    main()