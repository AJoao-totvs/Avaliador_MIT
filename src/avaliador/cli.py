"""
Command-line interface for Avaliador de MITs.

Provides the main CLI commands for evaluating MIT documents.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from avaliador import __version__
from avaliador.cache.manager import CacheManager, get_cached_extraction, save_extraction
from avaliador.config import settings
from avaliador.evaluators.mit041 import MIT041Evaluator
from avaliador.ingestors.docling_extractor import DoclingExtractor
from avaliador.models.schemas import EvaluationResult

# Initialize CLI app
app = typer.Typer(
    name="avaliador",
    help="Avaliador de qualidade de MITs TOTVS",
    add_completion=False,
)

console = Console()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _print_result_console(result: EvaluationResult, filename: str) -> None:
    """Format and print result to console."""
    # Determine color and status
    if result.score >= 8.0:
        color = "green"
        status = "APROVADO"
    elif result.score >= 5.0:
        color = "yellow"
        status = "REQUER REVISAO"
    else:
        color = "red"
        status = "REPROVADO"

    # Header panel
    console.print()
    console.print(
        Panel(
            f"[bold]NOTA: [{color}]{result.score:.1f}/10[/{color}][/bold]\n"
            f"STATUS: [{color}]{status}[/{color}]",
            title=f"Avaliacao: {filename}",
            border_style=color,
        )
    )

    # Recommendations
    if result.recommendations:
        console.print("\n[bold]Recomendacoes para atingir nota >= 8.0:[/bold]")
        for i, rec in enumerate(result.recommendations, 1):
            console.print(f"  {i}. {rec}")
    else:
        console.print("\n[green]Documento perfeito! Nenhuma recomendacao.[/green]")

    console.print()


def _check_configuration() -> bool:
    """Check if the application is properly configured."""
    if not settings.is_configured:
        console.print(
            "[red]Erro: DTA Proxy API Key nao configurada.[/red]\n"
            "Configure a variavel de ambiente DTA_PROXY_API_KEY ou crie um arquivo .env"
        )
        return False
    return True


@app.command()
def avaliar(
    arquivo: Path = typer.Argument(
        ...,
        help="Caminho para o arquivo .docx a ser avaliado",
        exists=True,
        readable=True,
    ),
    tipo: str = typer.Option(
        "MIT041",
        "--tipo",
        "-t",
        help="Tipo de MIT a avaliar",
    ),
    output_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Retornar resultado em formato JSON",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Ignorar cache de extracoes anteriores",
    ),
    no_vision: bool = typer.Option(
        False,
        "--no-vision",
        help="Desabilitar analise de imagens/diagramas",
    ),
    include_metadata: bool = typer.Option(
        False,
        "--metadata",
        "-m",
        help="Incluir metadados detalhados no resultado",
    ),
) -> None:
    """
    Avalia a qualidade de uma MIT e retorna nota + recomendacoes.

    Exemplo:
        avaliador documento.docx
        avaliador documento.docx --json
        avaliador documento.docx --no-vision --no-cache
    """
    # Check configuration
    if not _check_configuration():
        raise typer.Exit(1)

    # Validate file
    if not arquivo.exists():
        console.print(f"[red]Erro: Arquivo nao encontrado: {arquivo}[/red]")
        raise typer.Exit(1)

    if arquivo.suffix.lower() not in [".docx", ".doc"]:
        console.print(
            f"[red]Erro: Formato nao suportado: {arquivo.suffix}[/red]\n"
            "Apenas arquivos .docx sao suportados."
        )
        raise typer.Exit(1)

    # Check cache
    extraction_dict = None
    if not no_cache:
        extraction_dict = get_cached_extraction(arquivo)
        if extraction_dict:
            if not output_json:
                console.print("[dim]Usando extracao em cache...[/dim]")

    # Extract document if not cached
    if extraction_dict is None:
        if not output_json:
            console.print("[dim]Extraindo documento...[/dim]")

        try:
            extractor = DoclingExtractor(enable_vision=not no_vision)
            extraction_dict = extractor.extract_to_dict(arquivo)
            save_extraction(arquivo, extraction_dict)
        except ImportError as e:
            console.print(
                f"[red]Erro: Docling nao instalado.[/red]\n"
                f"Instale com: pip install docling\n"
                f"Detalhes: {e}"
            )
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Erro ao extrair documento: {e}[/red]")
            raise typer.Exit(1)

    # Warn if vision disabled
    if no_vision or not extraction_dict.get("metadata", {}).get("vision_enabled", False):
        if not output_json:
            console.print(
                "[yellow]Aviso: Avaliacao sem analise de imagens. "
                "O criterio de Diagramas BPMN tera penalidade.[/yellow]"
            )

    # Evaluate
    if not output_json:
        console.print("[dim]Avaliando documento...[/dim]")

    try:
        # Select evaluator based on type
        tipo_upper = tipo.upper()
        if tipo_upper in ["MIT041", "41"]:
            evaluator = MIT041Evaluator()
        else:
            console.print(
                f"[red]Erro: Tipo de MIT nao suportado: {tipo}[/red]\nTipos disponiveis: MIT041"
            )
            raise typer.Exit(1)

        result = evaluator.evaluate(extraction_dict, include_metadata=include_metadata)

    except Exception as e:
        console.print(f"[red]Erro ao avaliar documento: {e}[/red]")
        logger.exception("Evaluation failed")
        raise typer.Exit(1)

    # Output result
    if output_json:
        if include_metadata:
            print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result.to_simple_dict(), ensure_ascii=False, indent=2))
    else:
        _print_result_console(result, arquivo.name)


@app.command()
def limpar_cache() -> None:
    """Limpa o cache de extracoes de documentos."""
    cache = CacheManager()
    count = cache.clear()
    console.print(f"[green]Cache limpo. {count} arquivo(s) removido(s).[/green]")


@app.command()
def config() -> None:
    """Mostra a configuracao atual."""
    table = Table(title="Configuracao do Avaliador")
    table.add_column("Configuracao", style="cyan")
    table.add_column("Valor", style="green")

    table.add_row("DTA Proxy URL", settings.dta_proxy_base_url)
    table.add_row(
        "DTA API Key",
        "****" + settings.dta_proxy_api_key[-4:]
        if settings.dta_proxy_api_key
        else "[red]Nao configurada[/red]",
    )
    table.add_row("Modelo", settings.dta_model)
    table.add_row("Cache Habilitado", str(settings.cache_enabled))
    table.add_row("Cache Dir", str(settings.cache_dir))
    table.add_row("Vision Habilitado", str(settings.vision_enabled))
    table.add_row("Log Level", settings.log_level)

    console.print(table)


@app.command()
def versao() -> None:
    """Mostra a versao do Avaliador."""
    console.print(f"Avaliador de MITs TOTVS v{__version__}")


@app.callback()
def main() -> None:
    """
    Avaliador de MITs TOTVS - Ferramenta de auditoria de qualidade de documentacao.
    """
    pass


if __name__ == "__main__":
    app()
