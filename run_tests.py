#!/usr/bin/env python3
"""
Vietnamese DBPedia Test Runner
Executes comprehensive SPARQL tests for all system components
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from src.interfaces.sparql_interface import SPARQLInterface
    from src.graphdb.graphdb_manager import GraphDBManager
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

console = Console()

class TestResult:
    def __init__(self, query_name: str, success: bool, execution_time: float, 
                 result_count: int = 0, error: str = None):
        self.query_name = query_name
        self.success = success
        self.execution_time = execution_time
        self.result_count = result_count
        self.error = error

class DBPediaTestRunner:
    """Comprehensive test runner for Vietnamese DBPedia system."""
    
    def __init__(self):
        self.console = console
        self.sparql = None
        self.graphdb = None
        self.test_results: List[TestResult] = []
        self.queries_dir = Path("queries/tests")
        
    def initialize_connections(self) -> bool:
        """Initialize SPARQL and GraphDB connections."""
        try:
            self.console.print("[blue]Initializing connections...[/blue]")
            
            # Initialize SPARQL interface
            self.sparql = SPARQLInterface()
            self.console.print("[green]✓[/green] SPARQL interface connected")
            
            # Initialize GraphDB manager
            self.graphdb = GraphDBManager()
            self.console.print("[green]✓[/green] GraphDB manager connected")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]✗ Connection failed: {e}[/red]")
            return False
    
    def load_query_file(self, file_path: Path) -> List[Dict[str, str]]:
        """Load and parse SPARQL queries from file."""
        queries = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by query comments
            query_blocks = content.split('\n# Query ')
            
            for i, block in enumerate(query_blocks):
                if block.strip():
                    lines = block.strip().split('\n')
                    
                    # Extract query name from first line
                    if i == 0:
                        # First block might not have query prefix
                        query_name = f"{file_path.stem}_query_1"
                        query_content = block.strip()
                    else:
                        query_name = lines[0].split(':')[0].strip() if ':' in lines[0] else f"{file_path.stem}_query_{i+1}"
                        query_content = '\n'.join(lines[1:]).strip()
                    
                    # Skip empty queries or comments
                    if query_content and not query_content.startswith('#'):
                        queries.append({
                            'name': query_name,
                            'content': query_content
                        })
            
        except Exception as e:
            self.console.print(f"[red]✗ Failed to load {file_path}: {e}[/red]")
        
        return queries
    
    def execute_query(self, query: Dict[str, str]) -> TestResult:
        """Execute a single SPARQL query and measure performance."""
        start_time = time.time()
        
        try:
            # Execute query
            results = self.sparql.execute_query(query['content'])
            execution_time = time.time() - start_time
            
            # Count results
            result_count = 0
            if isinstance(results, dict):
                if 'results' in results and 'bindings' in results['results']:
                    result_count = len(results['results']['bindings'])
                elif 'boolean' in results:
                    result_count = 1 if results['boolean'] else 0
            elif isinstance(results, list):
                result_count = len(results)
            
            return TestResult(
                query_name=query['name'],
                success=True,
                execution_time=execution_time,
                result_count=result_count
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return TestResult(
                query_name=query['name'],
                success=False,
                execution_time=execution_time,
                error=str(e)
            )
    
    def run_test_file(self, file_path: Path) -> List[TestResult]:
        """Run all queries in a test file."""
        results = []
        
        self.console.print(f"\n[bold blue]Running tests from {file_path.name}[/bold blue]")
        
        queries = self.load_query_file(file_path)
        
        if not queries:
            self.console.print(f"[yellow]⚠ No queries found in {file_path.name}[/yellow]")
            return results
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task(f"Executing {len(queries)} queries...", total=len(queries))
            
            for query in queries:
                progress.update(task, description=f"Running {query['name']}")
                
                result = self.execute_query(query)
                results.append(result)
                
                # Show result immediately
                status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
                time_str = f"{result.execution_time:.3f}s"
                count_str = f"({result.result_count} results)" if result.success else f"({result.error})"
                
                self.console.print(f"  {status} {result.query_name} - {time_str} {count_str}")
                
                progress.advance(task)
        
        return results
    
    def run_all_tests(self) -> None:
        """Run all test files in the queries/tests directory."""
        if not self.queries_dir.exists():
            self.console.print(f"[red]✗ Test directory not found: {self.queries_dir}[/red]")
            return
        
        # Get all test files
        test_files = sorted(self.queries_dir.glob("*.sparql"))
        
        if not test_files:
            self.console.print(f"[red]✗ No test files found in {self.queries_dir}[/red]")
            return
        
        self.console.print(f"[bold green]Running Vietnamese DBPedia Test Suite[/bold green]")
        self.console.print(f"Found {len(test_files)} test files")
        
        # Run each test file
        for test_file in test_files:
            file_results = self.run_test_file(test_file)
            self.test_results.extend(file_results)
        
        # Show summary
        self.show_test_summary()
    
    def run_specific_tests(self, test_names: List[str]) -> None:
        """Run specific test files."""
        for test_name in test_names:
            test_file = self.queries_dir / f"{test_name}.sparql"
            if test_file.exists():
                file_results = self.run_test_file(test_file)
                self.test_results.extend(file_results)
            else:
                self.console.print(f"[red]✗ Test file not found: {test_file}[/red]")
        
        if self.test_results:
            self.show_test_summary()
    
    def show_test_summary(self) -> None:
        """Display test execution summary."""
        if not self.test_results:
            self.console.print("[yellow]No tests executed[/yellow]")
            return
        
        # Calculate statistics
        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r.success])
        failed_tests = total_tests - successful_tests
        total_time = sum(r.execution_time for r in self.test_results)
        avg_time = total_time / total_tests if total_tests > 0 else 0
        total_results = sum(r.result_count for r in self.test_results if r.success)
        
        # Create summary table
        table = Table(title="Test Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Tests", str(total_tests))
        table.add_row("Successful", str(successful_tests))
        table.add_row("Failed", str(failed_tests))
        table.add_row("Success Rate", f"{(successful_tests/total_tests*100):.1f}%")
        table.add_row("Total Time", f"{total_time:.3f}s")
        table.add_row("Average Time", f"{avg_time:.3f}s")
        table.add_row("Total Results", str(total_results))
        
        self.console.print("\n")
        self.console.print(table)
        
        # Show failed tests if any
        if failed_tests > 0:
            self.console.print(f"\n[bold red]Failed Tests ({failed_tests}):[/bold red]")
            for result in self.test_results:
                if not result.success:
                    self.console.print(f"[red]✗ {result.query_name}[/red]: {result.error}")
        
        # Show performance warnings
        slow_queries = [r for r in self.test_results if r.success and r.execution_time > 5.0]
        if slow_queries:
            self.console.print(f"\n[bold yellow]Slow Queries (>5s):[/bold yellow]")
            for result in slow_queries:
                self.console.print(f"[yellow]⚠ {result.query_name}[/yellow]: {result.execution_time:.3f}s")
    
    def export_results(self, output_file: str) -> None:
        """Export test results to JSON file."""
        if not self.test_results:
            self.console.print("[yellow]No results to export[/yellow]")
            return
        
        results_data = []
        for result in self.test_results:
            results_data.append({
                'query_name': result.query_name,
                'success': result.success,
                'execution_time': result.execution_time,
                'result_count': result.result_count,
                'error': result.error,
                'timestamp': time.time()
            })
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'test_run': {
                        'timestamp': time.time(),
                        'total_tests': len(self.test_results),
                        'successful_tests': len([r for r in self.test_results if r.success]),
                        'total_time': sum(r.execution_time for r in self.test_results)
                    },
                    'results': results_data
                }, f, indent=2)
            
            self.console.print(f"[green]✓ Results exported to {output_file}[/green]")
        except Exception as e:
            self.console.print(f"[red]✗ Failed to export results: {e}[/red]")


@click.command()
@click.option('--tests', '-t', multiple=True, help='Specific test files to run (without .sparql extension)')
@click.option('--output', '-o', help='Output file for results (JSON format)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(tests, output, verbose):
    """Run Vietnamese DBPedia SPARQL test suite."""
    
    # Initialize test runner
    runner = DBPediaTestRunner()
    
    # Check connections
    if not runner.initialize_connections():
        console.print("[red]✗ Failed to initialize connections[/red]")
        sys.exit(1)
    
    try:
        if tests:
            # Run specific tests
            runner.run_specific_tests(list(tests))
        else:
            # Run all tests
            runner.run_all_tests()
        
        # Export results if requested
        if output:
            runner.export_results(output)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Test execution interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Test execution failed: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()