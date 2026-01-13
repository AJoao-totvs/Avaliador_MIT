"""
Entry point for running avaliador as a module.

Usage:
    python -m avaliador <command> [options]
    python -m avaliador documento.docx
"""

from avaliador.cli import app

if __name__ == "__main__":
    app()
