#!/usr/bin/env python3
"""
Vietnamese DBPedia Command Line Interface

This module provides a comprehensive CLI for managing the Vietnamese DBPedia
project including data collection, transformation, loading, and querying.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.logging import RichHandler

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.collectors.wikipedia_collector import WikipediaCollector
from src.transformers.rdf_transformer import RDFTransformer
from src.ontology.vietnam_ontology import VietnamOntology
from src.graphdb.graphdb_manager import GraphDBManager
from src.graphdb.graphdb_loader import GraphDBLoader
from src.entity_linking.entity_linker import EntityLinker
from src.interfaces.sparql_interface import SPARQLInterface
from src.interfaces.web_interface import run_web_interface

console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)


@click.group(invoke_without_command=True)
@click.option('--version', is_flag=True, help='Show version information')
@click.pass_context
def cli(ctx, version):
    """Vietnamese DBPedia Management CLI
    
    A comprehensive tool for building and managing the Vietnamese DBPedia
    knowledge base with GraphDB integration.
    """
    if version:
        console.print("[bold blue]Vietnamese DBPedia CLI v1.0.0[/bold blue]")
        console.print("Built for M-IT6390E Semantic Web course")
        return
    
    if ctx.invoked_subcommand is None:
        console.print(Panel.fit(
            "[bold blue]Vietnamese DBPedia CLI[/bold blue]\n\n"
            "Use --help to see available commands.\n"
            "Example: python cli.py --help",
            title="Welcome"
        ))


@cli.group()
def ontology():
    """Ontology management commands."""
    pass


@ontology.command('create')
@click.option('--output-dir', default='ontology', help='Output directory for ontology files')
@click.option('--formats', default='turtle,xml,jsonld', help='Export formats (comma-separated)')
def create_ontology(output_dir: str, formats: str):
    """Create and export Vietnamese ontology."""
    try:
        console.print("[bold blue]Creating Vietnamese ontology...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Building ontology...", total=None)
            
            # Create ontology
            onto = VietnamOntology()
            progress.update(task, description="Ontology created")
            
            # Export in different formats
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            format_map = {
                'turtle': 'ttl',
                'xml': 'xml', 
                'jsonld': 'jsonld',
                'n3': 'n3'
            }
            
            # Map CLI format names to RDFLib format names
            rdflib_format_map = {
                'turtle': 'turtle',
                'xml': 'xml',
                'jsonld': 'json-ld',
                'n3': 'n3'
            }
            
            exported_files = []
            for fmt in formats.split(','):
                fmt = fmt.strip()
                if fmt in format_map and fmt in rdflib_format_map:
                    filename = f"vietnamese_ontology.{format_map[fmt]}"
                    file_path = output_path / filename
                    onto.export_ontology(str(file_path), rdflib_format_map[fmt])
                    exported_files.append(str(file_path))
                    progress.update(task, description=f"Exported {fmt} format")
            
            # Generate documentation
            doc_path = output_path / "ontology_documentation.html"
            onto.generate_documentation(str(doc_path))
            progress.update(task, description="Generated documentation")
            
        # Show statistics
        stats = onto.get_ontology_statistics()
        table = Table(title="Ontology Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        
        for key, value in stats.items():
            table.add_row(key.replace('_', ' ').title(), str(value))
        
        console.print(table)
        console.print(f"[green]✓[/green] Ontology exported to: {output_dir}")
        console.print(f"[green]✓[/green] Files: {', '.join(exported_files)}")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to create ontology: {e}[/red]")
        sys.exit(1)


@cli.group()
def collect():
    """Data collection commands."""
    pass


@collect.command('wikipedia')
@click.option('--articles', default='sample', help='Articles to collect: sample, categories, or custom file')
@click.option('--output', default='data/raw/articles.json', help='Output file path')
@click.option('--limit', default=100, help='Maximum articles to collect')
def collect_wikipedia(articles: str, output: str, limit: int):
    """Collect Wikipedia articles."""
    try:
        console.print("[bold blue]Collecting Wikipedia articles...[/bold blue]")
        
        collector = WikipediaCollector()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Collecting articles...", total=None)
            
            if articles == 'sample':
                collected_articles = collector.collect_sample_articles()
                progress.update(task, description="Collected sample articles")
            elif articles == 'categories':
                collected_articles = collector.collect_articles_by_categories(limit // 5)
                progress.update(task, description="Collected articles from categories")
            else:
                # Custom file with article titles
                with open(articles, 'r', encoding='utf-8') as f:
                    titles = [line.strip() for line in f if line.strip()]
                
                collected_articles = []
                for title in titles[:limit]:
                    article = collector.get_article_by_title(title)
                    if article:
                        collected_articles.append(article)
                
                progress.update(task, description=f"Collected {len(collected_articles)} custom articles")
            
            # Save articles
            collector.save_articles_to_json(collected_articles, output)
            progress.update(task, description="Articles saved")
        
        # Show statistics
        stats = collector.get_collection_statistics()
        table = Table(title="Collection Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        
        for key, value in stats.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    table.add_row(f"{key}: {sub_key}", str(sub_value))
            else:
                table.add_row(key.replace('_', ' ').title(), str(value))
        
        console.print(table)
        console.print(f"[green]✓[/green] Articles saved to: {output}")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to collect articles: {e}[/red]")
        sys.exit(1)


@cli.group()
def transform():
    """Data transformation commands."""
    pass


@transform.command('rdf')
@click.option('--input', default='data/raw/articles.json', help='Input articles JSON file')
@click.option('--output-dir', default='data/rdf', help='Output directory for RDF files')
@click.option('--formats', default='turtle,xml,jsonld', help='RDF formats to export')
def transform_rdf(input: str, output_dir: str, formats: str):
    """Transform articles to RDF format."""
    try:
        console.print("[bold blue]Transforming articles to RDF...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Loading articles...", total=None)
            
            # Load articles
            collector = WikipediaCollector()
            articles = collector.load_articles_from_json(input)
            progress.update(task, description=f"Loaded {len(articles)} articles")
            
            # Transform to RDF
            transformer = RDFTransformer()
            transformer.transform_articles_batch(articles)
            progress.update(task, description="Transformed to RDF")
            
            # Export in different formats
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            format_map = {
                'turtle': 'ttl',
                'xml': 'xml',
                'jsonld': 'jsonld',
                'n3': 'n3'
            }
            
            # Map CLI format names to RDFLib format names
            rdflib_format_map = {
                'turtle': 'turtle',
                'xml': 'xml',
                'jsonld': 'json-ld',
                'n3': 'n3'
            }
            
            exported_files = []
            for fmt in formats.split(','):
                fmt = fmt.strip()
                if fmt in format_map and fmt in rdflib_format_map:
                    filename = f"vietnamese_dbpedia.{format_map[fmt]}"
                    file_path = output_path / filename
                    transformer.export_rdf(str(file_path), rdflib_format_map[fmt])
                    exported_files.append(str(file_path))
                    progress.update(task, description=f"Exported {fmt} format")
            
            # Validate RDF
            validation = transformer.validate_rdf()
            progress.update(task, description="Validation complete")
        
        # Show statistics
        stats = transformer.get_transformation_statistics()
        table = Table(title="Transformation Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        
        for key, value in stats.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    table.add_row(f"{key}: {sub_key}", str(sub_value))
            else:
                table.add_row(key.replace('_', ' ').title(), str(value))
        
        console.print(table)
        console.print(f"[green]✓[/green] RDF files exported to: {output_dir}")
        console.print(f"[green]✓[/green] Validation errors: {len(validation['validation_errors'])}")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to transform to RDF: {e}[/red]")
        sys.exit(1)


@cli.group()
def graphdb():
    """GraphDB management commands."""
    pass


@graphdb.command('setup')
@click.option('--repository', default='vietnamese_dbpedia', help='Repository name')
def setup_graphdb(repository: str):
    """Set up GraphDB repository."""
    try:
        console.print("[bold blue]Setting up GraphDB repository...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Connecting to GraphDB...", total=None)
            
            manager = GraphDBManager()
            progress.update(task, description="Connected to GraphDB")
            
            # Create repository
            success = manager.create_repository(repository)
            if success:
                progress.update(task, description="Repository created")
            else:
                progress.update(task, description="Repository already exists")
            
            # Get repository info
            info = manager.get_repository_info(repository)
            progress.update(task, description="Repository configured")
        
        console.print(f"[green]✓[/green] Repository '{repository}' is ready")
        if info:
            console.print(f"[green]✓[/green] Title: {info.get('title', 'N/A')}")
            console.print(f"[green]✓[/green] Type: {info.get('type', 'N/A')}")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to setup GraphDB: {e}[/red]")
        sys.exit(1)


@graphdb.command('load')
@click.option('--input', default='data/rdf', help='Input directory or file')
@click.option('--repository', default='vietnamese_dbpedia', help='Repository name')
@click.option('--format', default='turtle', help='RDF format')
@click.option('--clear', is_flag=True, help='Clear repository before loading')
def load_graphdb(input: str, repository: str, format: str, clear: bool):
    """Load RDF data into GraphDB."""
    try:
        console.print("[bold blue]Loading data into GraphDB...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing loader...", total=None)
            
            manager = GraphDBManager()
            loader = GraphDBLoader(manager, repository)
            progress.update(task, description="Loader initialized")
            
            if clear:
                manager.clear_repository(repository)
                progress.update(task, description="Repository cleared")
            
            # Load data
            input_path = Path(input)
            if input_path.is_file():
                result = loader.load_rdf_file(str(input_path), format)
                results = [result]
            else:
                results = loader.load_directory(str(input_path), f"*.{format}")
            
            progress.update(task, description="Data loading complete")
            
            # Setup full-text indexing
            loader.setup_full_text_indexing()
            progress.update(task, description="Full-text indexing configured")
            
            # Optimize repository
            loader.optimize_repository()
            progress.update(task, description="Repository optimized")
        
        # Show statistics
        stats = loader.get_loading_statistics()
        table = Table(title="Loading Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        for key, value in stats.items():
            if key != 'batch_results':
                table.add_row(key.replace('_', ' ').title(), str(value))
        
        console.print(table)
        console.print(f"[green]✓[/green] Successfully loaded {stats['successful_loads']} files")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to load into GraphDB: {e}[/red]")
        sys.exit(1)


@cli.group()
def link():
    """Entity linking commands."""
    pass


@link.command('entities')
@click.option('--input', default='data/raw/articles.json', help='Input articles file')
@click.option('--output', default='data/mappings/entity_links.json', help='Output links file')
@click.option('--threshold', default=0.8, help='Confidence threshold')
def link_entities(input: str, output: str, threshold: float):
    """Link Vietnamese entities to English DBPedia."""
    try:
        console.print("[bold blue]Linking entities to English DBPedia...[/bold blue]")
        
        with Progress(
            SpinnerColumn(), 
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Loading articles...", total=None)
            
            # Load articles
            collector = WikipediaCollector()
            articles = collector.load_articles_from_json(input)
            progress.update(task, description=f"Loaded {len(articles)} articles")
            
            # Link entities
            linker = EntityLinker()
            linker.confidence_threshold = threshold
            
            all_matches = linker.link_articles_batch(articles)
            progress.update(task, description="Entity linking complete")
            
            # Filter by confidence threshold
            filtered_matches = {}
            for entity, matches in all_matches.items():
                high_confidence = [m for m in matches if m.confidence_score >= threshold]
                if high_confidence:
                    filtered_matches[entity] = high_confidence
            
            progress.update(task, description="Filtered by confidence")
            
            # Save results
            linker.save_linking_results(filtered_matches, output)
            progress.update(task, description="Results saved")
        
        # Show statistics
        stats = linker.get_linking_statistics()
        table = Table(title="Entity Linking Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                table.add_row(key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else str(value))
        
        console.print(table)
        console.print(f"[green]✓[/green] Entity links saved to: {output}")
        console.print(f"[green]✓[/green] High-confidence links: {len(filtered_matches)}")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to link entities: {e}[/red]")
        sys.exit(1)


@cli.group()
def query():
    """SPARQL query commands."""
    pass


@query.command('execute')
@click.option('--query', help='SPARQL query string')
@click.option('--file', help='SPARQL query file')
@click.option('--endpoint', default='local', help='Endpoint: local, dbpedia, or federated')
@click.option('--format', default='table', help='Output format: table, json, csv')
@click.option('--output', help='Output file path')
def execute_query(query: str, file: str, endpoint: str, format: str, output: str):
    """Execute SPARQL query."""
    try:
        # Get query
        if file:
            with open(file, 'r', encoding='utf-8') as f:
                query = f.read()
        elif not query:
            console.print("[red]✗ Query or file is required[/red]")
            sys.exit(1)
        
        console.print("[bold blue]Executing SPARQL query...[/bold blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Connecting to GraphDB...", total=None)
            
            manager = GraphDBManager()
            sparql_interface = SPARQLInterface(manager)
            progress.update(task, description="Executing query...")
            
            result = sparql_interface.execute_query(query, endpoint)
            progress.update(task, description="Query complete")
        
        if result.success:
            console.print(f"[green]✓[/green] Query executed in {result.execution_time:.3f}s")
            console.print(f"[green]✓[/green] Results: {result.result_count}")
            
            if format == 'table' and result.results.get('results', {}).get('bindings'):
                # Display as table
                bindings = result.results['results']['bindings']
                if bindings:
                    headers = list(bindings[0].keys())
                    table = Table(title="Query Results")
                    
                    for header in headers:
                        table.add_column(header, style="cyan")
                    
                    for binding in bindings[:20]:  # Limit display
                        row = []
                        for header in headers:
                            value = binding.get(header, {}).get('value', '')
                            # Truncate long URIs
                            if len(value) > 50:
                                value = value[:47] + "..."
                            row.append(value)
                        table.add_row(*row)
                    
                    console.print(table)
                    if len(bindings) > 20:
                        console.print(f"[yellow]Note: Showing first 20 of {len(bindings)} results[/yellow]")
            
            elif format in ['json', 'csv']:
                content = sparql_interface.export_results(result, format)
                if output:
                    with open(output, 'w', encoding='utf-8') as f:
                        f.write(content)
                    console.print(f"[green]✓[/green] Results saved to: {output}")
                else:
                    console.print(content)
        else:
            console.print(f"[red]✗ Query failed: {result.error_message}[/red]")
            sys.exit(1)
        
    except Exception as e:
        console.print(f"[red]✗ Failed to execute query: {e}[/red]")
        sys.exit(1)


@query.command('samples')
def show_samples():
    """Show sample SPARQL queries."""
    try:
        manager = GraphDBManager()
        sparql_interface = SPARQLInterface(manager)
        
        console.print("[bold blue]Sample SPARQL Queries[/bold blue]\n")
        
        for name, query in sparql_interface.sample_queries.items():
            panel = Panel(
                query.strip(),
                title=f"[bold cyan]{name.replace('_', ' ').title()}[/bold cyan]",
                expand=False
            )
            console.print(panel)
            console.print()
            
    except Exception as e:
        console.print(f"[red]✗ Failed to load samples: {e}[/red]")


@cli.command('web')
@click.option('--host', default='0.0.0.0', help='Host address')
@click.option('--port', default=5000, help='Port number')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def web(host: str, port: int, debug: bool):
    """Start web interface."""
    try:
        console.print(f"[bold blue]Starting Vietnamese DBPedia Web Interface...[/bold blue]")
        console.print(f"[green]✓[/green] Server: http://{host}:{port}")
        console.print(f"[green]✓[/green] Debug mode: {'enabled' if debug else 'disabled'}")
        
        run_web_interface(host=host, port=port, debug=debug)
        
    except Exception as e:
        console.print(f"[red]✗ Failed to start web interface: {e}[/red]")
        sys.exit(1)


@cli.command('status')
def status():
    """Show system status."""
    try:
        console.print("[bold blue]Vietnamese DBPedia System Status[/bold blue]\n")
        
        status_table = Table(title="Component Status")
        status_table.add_column("Component", style="cyan")
        status_table.add_column("Status", style="green")
        status_table.add_column("Details")
        
        # Check GraphDB
        try:
            manager = GraphDBManager()
            repos = manager.list_repositories()
            status_table.add_row("GraphDB", "✓ Connected", f"{len(repos)} repositories")
        except Exception as e:
            status_table.add_row("GraphDB", "✗ Error", str(e))
        
        # Check data files
        data_files = ['data/raw/articles.json', 'data/rdf/vietnamese_dbpedia.ttl']
        for file_path in data_files:
            if Path(file_path).exists():
                size = Path(file_path).stat().st_size
                status_table.add_row(f"Data: {file_path}", "✓ Available", f"{size:,} bytes")
            else:
                status_table.add_row(f"Data: {file_path}", "✗ Missing", "File not found")
        
        console.print(status_table)
        
    except Exception as e:
        console.print(f"[red]✗ Failed to get status: {e}[/red]")


if __name__ == '__main__':
    cli()