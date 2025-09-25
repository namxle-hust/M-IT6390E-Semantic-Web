"""
GraphDB Data Loader Module

This module provides specialized data loading capabilities for GraphDB
including batch loading, indexing optimization, and performance monitoring.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from rdflib import Graph
import json

from src.graphdb.graphdb_manager import GraphDBManager, GraphDBError
from src.transformers.rdf_transformer import RDFTransformer
from src.collectors.wikipedia_collector import WikipediaArticle

logger = logging.getLogger(__name__)


@dataclass
class LoadingResult:
    """Result of a data loading operation."""
    success: bool
    statements_loaded: int
    loading_time: float
    error_message: Optional[str] = None
    file_path: Optional[str] = None


class GraphDBLoader:
    """Advanced GraphDB data loader with batch processing and optimization."""
    
    def __init__(self, graphdb_manager: GraphDBManager, repository_id: str = 'vietnamese_dbpedia'):
        self.graphdb_manager = graphdb_manager
        self.repository_id = repository_id
        self.loading_stats = {
            'total_files_processed': 0,
            'total_statements_loaded': 0,
            'total_loading_time': 0.0,
            'successful_loads': 0,
            'failed_loads': 0,
            'average_loading_speed': 0.0,
            'batch_results': []
        }
        self._loading_lock = threading.Lock()
    
    def ensure_repository_exists(self) -> bool:
        """Ensure the target repository exists."""
        try:
            if not self.graphdb_manager.repository_exists(
                self.graphdb_manager.repository_configs[self.repository_id]['id']
            ):
                logger.info(f"Creating repository: {self.repository_id}")
                return self.graphdb_manager.create_repository(self.repository_id)
            return True
        except Exception as e:
            logger.error(f"Failed to ensure repository exists: {e}")
            return False
    
    def load_rdf_file(self, file_path: str, format: str = 'turtle', 
                     context: str = None, validate: bool = True) -> LoadingResult:
        """Load a single RDF file with performance monitoring."""
        start_time = time.time()
        
        try:
            if not self.ensure_repository_exists():
                return LoadingResult(
                    success=False,
                    statements_loaded=0,
                    loading_time=0.0,
                    error_message="Repository creation failed",
                    file_path=file_path
                )
            
            # Get initial repository size
            initial_size = self.graphdb_manager.get_repository_size(self.repository_id) or 0
            
            # Validate RDF file if requested
            if validate and not self._validate_rdf_file(file_path, format):
                return LoadingResult(
                    success=False,
                    statements_loaded=0,
                    loading_time=time.time() - start_time,
                    error_message="RDF validation failed",
                    file_path=file_path
                )
            
            # Load the file
            success = self.graphdb_manager.load_rdf_data(
                self.repository_id, file_path, format, context
            )
            
            loading_time = time.time() - start_time
            
            if success:
                # Calculate statements loaded
                final_size = self.graphdb_manager.get_repository_size(self.repository_id) or 0
                statements_loaded = final_size - initial_size
                
                with self._loading_lock:
                    self.loading_stats['total_files_processed'] += 1
                    self.loading_stats['total_statements_loaded'] += statements_loaded
                    self.loading_stats['total_loading_time'] += loading_time
                    self.loading_stats['successful_loads'] += 1
                
                logger.info(f"Loaded {statements_loaded} statements from {file_path} in {loading_time:.2f}s")
                
                return LoadingResult(
                    success=True,
                    statements_loaded=statements_loaded,
                    loading_time=loading_time,
                    file_path=file_path
                )
            else:
                with self._loading_lock:
                    self.loading_stats['failed_loads'] += 1
                
                return LoadingResult(
                    success=False,
                    statements_loaded=0,
                    loading_time=loading_time,
                    error_message="GraphDB loading failed",
                    file_path=file_path
                )
                
        except Exception as e:
            loading_time = time.time() - start_time
            with self._loading_lock:
                self.loading_stats['failed_loads'] += 1
            
            logger.error(f"Failed to load {file_path}: {e}")
            return LoadingResult(
                success=False,
                statements_loaded=0,
                loading_time=loading_time,
                error_message=str(e),
                file_path=file_path
            )
    
    def _validate_rdf_file(self, file_path: str, format: str) -> bool:
        """Validate RDF file before loading."""
        try:
            graph = Graph()
            graph.parse(file_path, format=format)
            
            if len(graph) == 0:
                logger.warning(f"RDF file is empty: {file_path}")
                return False
            
            logger.debug(f"RDF file validated: {file_path} ({len(graph)} triples)")
            return True
            
        except Exception as e:
            logger.error(f"RDF validation failed for {file_path}: {e}")
            return False
    
    def load_directory(self, directory_path: str, pattern: str = "*.ttl", 
                      concurrent_loads: int = 3, validate: bool = True) -> List[LoadingResult]:
        """Load all RDF files from a directory with concurrent processing."""
        return self.load_directory_with_context(directory_path, pattern, None, concurrent_loads, validate)
    
    def load_directory_with_context(self, directory_path: str, pattern: str = "*.ttl", 
                                   context: str = None, concurrent_loads: int = 3, 
                                   validate: bool = True) -> List[LoadingResult]:
        """Load all RDF files from a directory with concurrent processing."""
        directory = Path(directory_path)
        if not directory.exists():
            logger.error(f"Directory not found: {directory_path}")
            return []
        
        # Find all matching files
        rdf_files = list(directory.glob(pattern))
        if not rdf_files:
            logger.warning(f"No RDF files found in {directory_path} with pattern {pattern}")
            return []
        
        logger.info(f"Loading {len(rdf_files)} RDF files from {directory_path}")
        
        results = []
        
        # Determine format from file extension
        format_mapping = {
            '.ttl': 'turtle',
            '.turtle': 'turtle',
            '.rdf': 'xml',
            '.xml': 'xml',
            '.n3': 'n3',
            '.nt': 'nt',
            '.jsonld': 'json-ld'
        }
        
        with ThreadPoolExecutor(max_workers=concurrent_loads) as executor:
            future_to_file = {}
            
            for file_path in rdf_files:
                file_format = format_mapping.get(file_path.suffix.lower(), 'turtle')
                future = executor.submit(
                    self.load_rdf_file, 
                    str(file_path), 
                    file_format, 
                    context, 
                    validate
                )
                future_to_file[future] = file_path
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Loading failed for {file_path}: {e}")
                    results.append(LoadingResult(
                        success=False,
                        statements_loaded=0,
                        loading_time=0.0,
                        error_message=str(e),
                        file_path=str(file_path)
                    ))
        
        # Update batch statistics
        with self._loading_lock:
            self.loading_stats['batch_results'].append({
                'directory': directory_path,
                'files_processed': len(results),
                'successful': sum(1 for r in results if r.success),
                'failed': sum(1 for r in results if not r.success),
                'total_statements': sum(r.statements_loaded for r in results),
                'total_time': sum(r.loading_time for r in results)
            })
        
        logger.info(f"Directory loading complete. Success: {sum(1 for r in results if r.success)}/{len(results)}")
        return results
    
    def load_articles_batch(self, articles: List[WikipediaArticle], 
                          batch_size: int = 100) -> List[LoadingResult]:
        """Load Wikipedia articles in batches after RDF transformation."""
        logger.info(f"Loading {len(articles)} articles in batches of {batch_size}")
        
        results = []
        transformer = RDFTransformer()
        
        # Process articles in batches
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            logger.info(f"Processing batch {batch_num}: {len(batch)} articles")
            
            try:
                # Transform batch to RDF
                transformer.transform_articles_batch(batch)
                
                # Convert graph to string
                rdf_data = transformer.graph.serialize(format='turtle')
                
                # Load into GraphDB
                start_time = time.time()
                success = self.graphdb_manager.load_rdf_from_string(
                    self.repository_id, rdf_data, format='turtle'
                )
                loading_time = time.time() - start_time
                
                if success:
                    statements_loaded = len(transformer.graph)
                    
                    result = LoadingResult(
                        success=True,
                        statements_loaded=statements_loaded,
                        loading_time=loading_time,
                        file_path=f"batch_{batch_num}"
                    )
                    
                    with self._loading_lock:
                        self.loading_stats['total_files_processed'] += 1
                        self.loading_stats['total_statements_loaded'] += statements_loaded
                        self.loading_stats['total_loading_time'] += loading_time
                        self.loading_stats['successful_loads'] += 1
                    
                    logger.info(f"Batch {batch_num} loaded: {statements_loaded} statements in {loading_time:.2f}s")
                else:
                    result = LoadingResult(
                        success=False,
                        statements_loaded=0,
                        loading_time=loading_time,
                        error_message="GraphDB loading failed",
                        file_path=f"batch_{batch_num}"
                    )
                    
                    with self._loading_lock:
                        self.loading_stats['failed_loads'] += 1
                
                results.append(result)
                
                # Clear transformer graph for next batch
                transformer.graph = Graph()
                for prefix, namespace in transformer.ontology.namespaces.items():
                    transformer.graph.bind(prefix, namespace)
                
            except Exception as e:
                logger.error(f"Batch {batch_num} processing failed: {e}")
                result = LoadingResult(
                    success=False,
                    statements_loaded=0,
                    loading_time=0.0,
                    error_message=str(e),
                    file_path=f"batch_{batch_num}"
                )
                results.append(result)
                
                with self._loading_lock:
                    self.loading_stats['failed_loads'] += 1
        
        logger.info(f"Batch loading complete. Total results: {len(results)}")
        return results
    
    def setup_full_text_indexing(self) -> bool:
        """Set up full-text indexing for Vietnamese text search."""
        try:
            # Check if FTS is already configured
            query = """
            PREFIX lucene: <http://www.ontotext.com/connectors/lucene#>
            ASK { ?index a lucene:Instance }
            """
            
            result = self.graphdb_manager.execute_sparql_query(
                self.repository_id, query, 'ask'
            )
            
            if result and result.get('boolean', False):
                logger.info("Full-text indexing already configured")
                return True
            
            # Create FTS index configuration
            fts_config = """
            PREFIX lucene: <http://www.ontotext.com/connectors/lucene#>
            PREFIX inst: <http://www.ontotext.com/connectors/lucene/instance#>
            
            INSERT DATA {
                inst:vietnamese_fts a lucene:Instance ;
                    lucene:dataDir "lucene" ;
                    lucene:useExternalDir "true" ;
                    lucene:queryTimeout "10000" ;
                    lucene:queryLimit "1000" ;
                    lucene:includeInferred "true" ;
                    lucene:moleculeSize "1000" ;
                    lucene:indexBlankNodes "false" ;
                    lucene:literalIndex [
                        lucene:field "title" ;
                        lucene:propertyChain ( <http://www.w3.org/2000/01/rdf-schema#label> ) ;
                        lucene:analyzer "org.apache.lucene.analysis.standard.StandardAnalyzer" ;
                        lucene:multivalued "true"
                    ] ;
                    lucene:literalIndex [
                        lucene:field "content" ;
                        lucene:propertyChain ( <http://www.w3.org/2000/01/rdf-schema#comment> ) ;
                        lucene:analyzer "org.apache.lucene.analysis.standard.StandardAnalyzer" ;
                        lucene:multivalued "true"
                    ] .
            }
            """
            
            # Execute FTS setup
            result = self.graphdb_manager.execute_sparql_query(
                self.repository_id, fts_config, 'update'
            )
            
            if result is not None:
                logger.info("Full-text indexing configured successfully")
                return True
            else:
                logger.error("Failed to configure full-text indexing")
                return False
                
        except Exception as e:
            logger.error(f"FTS setup failed: {e}")
            return False
    
    def optimize_repository(self) -> bool:
        """Optimize repository for better query performance."""
        try:
            # Update statistics
            stats_query = "REFRESH STATS"
            
            result = self.graphdb_manager.execute_sparql_query(
                self.repository_id, stats_query, 'update'
            )
            
            if result is not None:
                logger.info("Repository statistics updated")
                
                # Additional optimization queries could be added here
                # For example, creating specific indexes for common query patterns
                
                return True
            else:
                logger.warning("Statistics update may have failed")
                return False
                
        except Exception as e:
            logger.error(f"Repository optimization failed: {e}")
            return False
    
    def get_loading_statistics(self) -> Dict[str, Any]:
        """Get comprehensive loading statistics."""
        stats = self.loading_stats.copy()
        
        # Calculate derived statistics
        if stats['total_loading_time'] > 0:
            stats['average_loading_speed'] = stats['total_statements_loaded'] / stats['total_loading_time']
        
        if stats['total_files_processed'] > 0:
            stats['success_rate'] = (stats['successful_loads'] / stats['total_files_processed']) * 100
            stats['average_statements_per_file'] = stats['total_statements_loaded'] / stats['successful_loads'] if stats['successful_loads'] > 0 else 0
            stats['average_loading_time_per_file'] = stats['total_loading_time'] / stats['total_files_processed']
        
        # Get current repository size
        try:
            stats['current_repository_size'] = self.graphdb_manager.get_repository_size(self.repository_id) or 0
        except Exception:
            stats['current_repository_size'] = 'Unknown'
        
        return stats
    
    def generate_loading_report(self, output_path: str = None) -> str:
        """Generate a detailed loading report."""
        stats = self.get_loading_statistics()
        
        report = f"""
Vietnamese DBPedia Data Loading Report
=====================================

Repository: {self.repository_id}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

Summary Statistics:
------------------
Total Files Processed: {stats['total_files_processed']}
Successful Loads: {stats['successful_loads']}
Failed Loads: {stats['failed_loads']}
Success Rate: {stats.get('success_rate', 0):.1f}%

Data Statistics:
---------------
Total Statements Loaded: {stats['total_statements_loaded']:,}
Current Repository Size: {stats['current_repository_size']:,}
Average Statements per File: {stats.get('average_statements_per_file', 0):.0f}

Performance Statistics:
----------------------
Total Loading Time: {stats['total_loading_time']:.2f} seconds
Average Loading Time per File: {stats.get('average_loading_time_per_file', 0):.2f} seconds
Average Loading Speed: {stats.get('average_loading_speed', 0):.0f} statements/second

Batch Results:
-------------
"""
        
        for i, batch in enumerate(stats['batch_results'], 1):
            report += f"""
Batch {i} ({batch['directory']}):
  Files: {batch['files_processed']} (Success: {batch['successful']}, Failed: {batch['failed']})
  Statements: {batch['total_statements']:,}
  Time: {batch['total_time']:.2f}s
"""
        
        if output_path:
            try:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as file:
                    file.write(report)
                logger.info(f"Loading report saved to: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save loading report: {e}")
        
        return report


def main():
    """Main function for testing the loader."""
    try:
        # Initialize GraphDB manager and loader
        manager = GraphDBManager()
        loader = GraphDBLoader(manager)
        
        # Ensure repository exists
        if not loader.ensure_repository_exists():
            print("Failed to create repository")
            return
        
        # Load sample RDF files
        if Path("data/rdf").exists():
            results = loader.load_directory("data/rdf", "*.ttl")
            print(f"Loaded {len(results)} files")
        
        # Setup full-text indexing
        if loader.setup_full_text_indexing():
            print("Full-text indexing configured")
        
        # Optimize repository
        if loader.optimize_repository():
            print("Repository optimized")
        
        # Generate report
        report = loader.generate_loading_report("reports/loading_report.txt")
        print("Loading Report:")
        print("=" * 50)
        print(report[:1000] + "..." if len(report) > 1000 else report)
        
    except Exception as e:
        logger.error(f"Loader test failed: {e}")
        raise


if __name__ == "__main__":
    main()