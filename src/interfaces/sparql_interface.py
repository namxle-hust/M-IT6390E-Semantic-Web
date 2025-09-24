"""
SPARQL Interface Module

This module provides comprehensive SPARQL query capabilities with Vietnamese
text search, federated queries, caching, and result processing.
"""

import json
import time
import hashlib
import logging
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from SPARQLWrapper import SPARQLWrapper, JSON, XML, TURTLE, N3
import requests

from src.graphdb.graphdb_manager import GraphDBManager

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """SPARQL query result with metadata."""
    success: bool
    results: Dict[str, Any]
    execution_time: float
    result_count: int
    query: str
    error_message: Optional[str] = None
    cached: bool = False


class SPARQLInterface:
    """Advanced SPARQL interface with caching, optimization, and Vietnamese text search."""
    
    def __init__(self, graphdb_manager: GraphDBManager, repository_id: str = 'vietnamese_dbpedia'):
        self.graphdb_manager = graphdb_manager
        self.repository_id = repository_id
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Configure SPARQL endpoints
        self.local_endpoint = None
        self.dbpedia_endpoint = "https://dbpedia.org/sparql"
        
        self._setup_endpoints()
        self._load_sample_queries()
        
        # Statistics
        self.query_stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'cached_queries': 0,
            'average_execution_time': 0.0,
            'total_execution_time': 0.0
        }
    
    def _setup_endpoints(self) -> None:
        """Set up SPARQL endpoints."""
        try:
            # Get local GraphDB endpoint
            config = self.graphdb_manager.repository_configs.get(self.repository_id)
            if config:
                base_url = self.graphdb_manager.base_url
                self.local_endpoint = f"{base_url}/repositories/{config['id']}"
                logger.info(f"Local SPARQL endpoint: {self.local_endpoint}")
            
            # Set up DBPedia endpoint
            self.dbpedia_sparql = SPARQLWrapper(self.dbpedia_endpoint)
            self.dbpedia_sparql.setReturnFormat(JSON)
            logger.info("SPARQL endpoints configured")
            
        except Exception as e:
            logger.error(f"Failed to setup SPARQL endpoints: {e}")
    
    def _load_sample_queries(self) -> None:
        """Load sample SPARQL queries for Vietnamese DBPedia."""
        self.sample_queries = {
            'list_people': """
                PREFIX vi: <http://vi.dbpedia.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?person ?name WHERE {
                    ?person a vi:Người ;
                            rdfs:label ?name .
                    FILTER(LANG(?name) = "vi")
                } LIMIT 10
            """,
            
            'list_places': """
                PREFIX vi: <http://vi.dbpedia.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?place ?name WHERE {
                    ?place a vi:ĐịaĐiểm ;
                           rdfs:label ?name .
                    FILTER(LANG(?name) = "vi")
                } LIMIT 10
            """,
            
            'search_by_name': """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX vidbp: <http://vi.dbpedia.org/property/>
                
                SELECT ?entity ?label ?type WHERE {
                    ?entity rdfs:label ?label ;
                            a ?type .
                    FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{search_term}")))
                    FILTER(LANG(?label) = "vi")
                } LIMIT 20
            """,
            
            'entity_details': """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX vidbp: <http://vi.dbpedia.org/property/>
                
                SELECT ?property ?value WHERE {
                    <{entity_uri}> ?property ?value .
                } LIMIT 50
            """,
            
            'federated_search': """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX dbpedia: <http://dbpedia.org/resource/>
                
                SELECT ?viEntity ?enEntity ?viLabel ?enLabel WHERE {
                    ?viEntity rdfs:label ?viLabel ;
                             owl:sameAs ?enEntity .
                    SERVICE <https://dbpedia.org/sparql> {
                        ?enEntity rdfs:label ?enLabel .
                        FILTER(LANG(?enLabel) = "en")
                    }
                    FILTER(LANG(?viLabel) = "vi")
                } LIMIT 10
            """,
            
            'full_text_search': """
                PREFIX lucene: <http://www.ontotext.com/connectors/lucene#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?entity ?label ?score WHERE {
                    ?search a lucene:LuceneQuery ;
                            lucene:query "{search_text}" ;
                            lucene:entities ?entity .
                    ?entity rdfs:label ?label ;
                            lucene:score ?score .
                    FILTER(LANG(?label) = "vi")
                } ORDER BY DESC(?score) LIMIT 20
            """
        }
        
        logger.info(f"Loaded {len(self.sample_queries)} sample queries")
    
    def execute_query(self, query: str, endpoint: str = 'local', 
                     use_cache: bool = True, timeout: int = 30) -> QueryResult:
        """Execute SPARQL query with caching and error handling."""
        start_time = time.time()
        
        # Generate cache key
        cache_key = hashlib.md5((query + endpoint).encode()).hexdigest()
        
        # Check cache
        if use_cache and cache_key in self.cache:
            cached_result, cache_time = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                self.query_stats['cached_queries'] += 1
                self.query_stats['total_queries'] += 1
                
                execution_time = time.time() - start_time
                logger.info(f"Query served from cache in {execution_time:.3f}s")
                
                return QueryResult(
                    success=True,
                    results=cached_result,
                    execution_time=execution_time,
                    result_count=self._count_results(cached_result),
                    query=query,
                    cached=True
                )
        
        try:
            # Execute query based on endpoint
            if endpoint == 'local':
                results = self._execute_local_query(query, timeout)
            elif endpoint == 'dbpedia':
                results = self._execute_dbpedia_query(query, timeout)
            elif endpoint == 'federated':
                results = self._execute_federated_query(query, timeout)
            else:
                raise ValueError(f"Unknown endpoint: {endpoint}")
            
            execution_time = time.time() - start_time
            result_count = self._count_results(results)
            
            # Cache successful results
            if use_cache:
                self.cache[cache_key] = (results, time.time())
            
            # Update statistics
            self.query_stats['total_queries'] += 1
            self.query_stats['successful_queries'] += 1
            self.query_stats['total_execution_time'] += execution_time
            self.query_stats['average_execution_time'] = (
                self.query_stats['total_execution_time'] / self.query_stats['successful_queries']
            )
            
            logger.info(f"Query executed successfully in {execution_time:.3f}s ({result_count} results)")
            
            return QueryResult(
                success=True,
                results=results,
                execution_time=execution_time,
                result_count=result_count,
                query=query
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.query_stats['total_queries'] += 1
            self.query_stats['failed_queries'] += 1
            
            logger.error(f"Query execution failed: {e}")
            
            return QueryResult(
                success=False,
                results={},
                execution_time=execution_time,
                result_count=0,
                query=query,
                error_message=str(e)
            )
    
    def _execute_local_query(self, query: str, timeout: int) -> Dict[str, Any]:
        """Execute query on local GraphDB repository."""
        return self.graphdb_manager.execute_sparql_query(
            self.repository_id, query, self._detect_query_type(query)
        )
    
    def _execute_dbpedia_query(self, query: str, timeout: int) -> Dict[str, Any]:
        """Execute query on DBPedia SPARQL endpoint."""
        self.dbpedia_sparql.setQuery(query)
        self.dbpedia_sparql.setTimeout(timeout)
        return self.dbpedia_sparql.query().convert()
    
    def _execute_federated_query(self, query: str, timeout: int) -> Dict[str, Any]:
        """Execute federated query across local and remote endpoints."""
        # For federated queries, we execute on the local endpoint
        # which should handle SERVICE clauses for remote endpoints
        return self._execute_local_query(query, timeout)
    
    def _detect_query_type(self, query: str) -> str:
        """Detect SPARQL query type."""
        query_upper = query.upper().strip()
        
        if query_upper.startswith('SELECT'):
            return 'select'
        elif query_upper.startswith('CONSTRUCT'):
            return 'construct'
        elif query_upper.startswith('DESCRIBE'):
            return 'describe'
        elif query_upper.startswith('ASK'):
            return 'ask'
        else:
            return 'select'  # Default
    
    def _count_results(self, results: Dict[str, Any]) -> int:
        """Count the number of results in a SPARQL response."""
        try:
            if 'results' in results and 'bindings' in results['results']:
                return len(results['results']['bindings'])
            elif 'boolean' in results:
                return 1 if results['boolean'] else 0
            else:
                return 0
        except Exception:
            return 0
    
    def search_entities(self, search_term: str, limit: int = 20) -> QueryResult:
        """Search for entities by name."""
        query = self.sample_queries['search_by_name'].format(search_term=search_term)
        query = query.replace('LIMIT 20', f'LIMIT {limit}')
        return self.execute_query(query)
    
    def get_entity_details(self, entity_uri: str) -> QueryResult:
        """Get detailed information about an entity."""
        query = self.sample_queries['entity_details'].format(entity_uri=entity_uri)
        return self.execute_query(query)
    
    def full_text_search(self, search_text: str, limit: int = 20) -> QueryResult:
        """Perform full-text search using Lucene index."""
        query = self.sample_queries['full_text_search'].format(search_text=search_text)
        query = query.replace('LIMIT 20', f'LIMIT {limit}')
        return self.execute_query(query)
    
    def execute_federated_query(self, vietnamese_entity: str = None) -> QueryResult:
        """Execute federated query to link with English DBPedia."""
        if vietnamese_entity:
            # Modify federated query to search for specific entity
            query = f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                
                SELECT ?viEntity ?enEntity ?viLabel ?enLabel WHERE {{
                    ?viEntity rdfs:label ?viLabel ;
                             owl:sameAs ?enEntity .
                    FILTER(CONTAINS(LCASE(STR(?viLabel)), LCASE("{vietnamese_entity}")))
                    SERVICE <https://dbpedia.org/sparql> {{
                        ?enEntity rdfs:label ?enLabel .
                        FILTER(LANG(?enLabel) = "en")
                    }}
                    FILTER(LANG(?viLabel) = "vi")
                }} LIMIT 10
            """
        else:
            query = self.sample_queries['federated_search']
        
        return self.execute_query(query, endpoint='federated')
    
    def get_ontology_statistics(self) -> QueryResult:
        """Get statistics about the Vietnamese ontology."""
        query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX vi: <http://vi.dbpedia.org/ontology/>
            
            SELECT 
                (COUNT(DISTINCT ?entity) AS ?total_entities)
                (COUNT(DISTINCT ?class) AS ?total_classes)
                (COUNT(DISTINCT ?property) AS ?total_properties)
                (COUNT(*) AS ?total_triples)
            WHERE {
                {
                    ?entity a ?class .
                } UNION {
                    ?entity ?property ?value .
                }
            }
        """
        return self.execute_query(query)
    
    def export_results(self, query_result: QueryResult, format: str = 'json', 
                      output_path: str = None) -> Optional[str]:
        """Export query results to various formats."""
        if not query_result.success:
            logger.error("Cannot export failed query results")
            return None
        
        try:
            if format.lower() == 'json':
                content = json.dumps(query_result.results, ensure_ascii=False, indent=2)
            elif format.lower() == 'csv':
                content = self._convert_to_csv(query_result.results)
            elif format.lower() == 'tsv':
                content = self._convert_to_tsv(query_result.results)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as file:
                    file.write(content)
                logger.info(f"Query results exported to {output_path}")
                return output_path
            else:
                return content
                
        except Exception as e:
            logger.error(f"Failed to export query results: {e}")
            return None
    
    def _convert_to_csv(self, results: Dict[str, Any]) -> str:
        """Convert SPARQL results to CSV format."""
        if 'results' not in results or 'bindings' not in results['results']:
            return ""
        
        bindings = results['results']['bindings']
        if not bindings:
            return ""
        
        # Get headers
        headers = list(bindings[0].keys())
        lines = [','.join(headers)]
        
        # Add data rows
        for binding in bindings:
            row = []
            for header in headers:
                value = binding.get(header, {}).get('value', '')
                # Escape CSV values
                if ',' in value or '"' in value or '\n' in value:
                    value = '"' + value.replace('"', '""') + '"'
                row.append(value)
            lines.append(','.join(row))
        
        return '\n'.join(lines)
    
    def _convert_to_tsv(self, results: Dict[str, Any]) -> str:
        """Convert SPARQL results to TSV format."""
        csv_content = self._convert_to_csv(results)
        return csv_content.replace(',', '\t')
    
    def batch_execute_queries(self, queries: Dict[str, str], 
                             max_workers: int = 3) -> Dict[str, QueryResult]:
        """Execute multiple queries concurrently."""
        logger.info(f"Executing {len(queries)} queries in batch")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(self.execute_query, query): name
                for name, query in queries.items()
            }
            
            for future in as_completed(future_to_name):
                query_name = future_to_name[future]
                try:
                    result = future.result()
                    results[query_name] = result
                except Exception as e:
                    logger.error(f"Batch query {query_name} failed: {e}")
                    results[query_name] = QueryResult(
                        success=False,
                        results={},
                        execution_time=0.0,
                        result_count=0,
                        query=queries.get(query_name, ''),
                        error_message=str(e)
                    )
        
        logger.info(f"Batch execution complete. Success: {sum(1 for r in results.values() if r.success)}/{len(results)}")
        return results
    
    def clear_cache(self) -> None:
        """Clear the query cache."""
        self.cache.clear()
        logger.info("Query cache cleared")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        valid_entries = 0
        
        for _, (_, cache_time) in self.cache.items():
            if current_time - cache_time < self.cache_ttl:
                valid_entries += 1
        
        return {
            'total_cache_entries': len(self.cache),
            'valid_cache_entries': valid_entries,
            'cache_hit_rate': (self.query_stats['cached_queries'] / max(1, self.query_stats['total_queries'])) * 100,
            'cache_ttl_seconds': self.cache_ttl
        }
    
    def get_query_statistics(self) -> Dict[str, Any]:
        """Get comprehensive query statistics."""
        stats = self.query_stats.copy()
        
        if stats['total_queries'] > 0:
            stats['success_rate'] = (stats['successful_queries'] / stats['total_queries']) * 100
            stats['failure_rate'] = (stats['failed_queries'] / stats['total_queries']) * 100
            stats['cache_hit_rate'] = (stats['cached_queries'] / stats['total_queries']) * 100
        
        # Add cache statistics
        cache_stats = self.get_cache_statistics()
        stats.update(cache_stats)
        
        return stats


def main():
    """Main function for testing SPARQL interface."""
    try:
        from src.graphdb.graphdb_manager import GraphDBManager
        
        # Initialize components
        manager = GraphDBManager()
        sparql_interface = SPARQLInterface(manager)
        
        # Test basic queries
        print("Testing SPARQL Interface")
        print("=" * 50)
        
        # List people
        print("\n1. Listing people...")
        result = sparql_interface.execute_query(sparql_interface.sample_queries['list_people'])
        if result.success:
            print(f"   Found {result.result_count} people in {result.execution_time:.3f}s")
        
        # Search entities
        print("\n2. Searching for 'Hồ Chí Minh'...")
        result = sparql_interface.search_entities("Hồ Chí Minh")
        if result.success:
            print(f"   Found {result.result_count} matches in {result.execution_time:.3f}s")
        
        # Get statistics
        print("\n3. Ontology statistics...")
        result = sparql_interface.get_ontology_statistics()
        if result.success and result.results.get('results', {}).get('bindings'):
            stats = result.results['results']['bindings'][0]
            print(f"   Entities: {stats.get('total_entities', {}).get('value', 'N/A')}")
            print(f"   Classes: {stats.get('total_classes', {}).get('value', 'N/A')}")
            print(f"   Properties: {stats.get('total_properties', {}).get('value', 'N/A')}")
            print(f"   Triples: {stats.get('total_triples', {}).get('value', 'N/A')}")
        
        # Print query statistics
        query_stats = sparql_interface.get_query_statistics()
        print(f"\nQuery Statistics:")
        for key, value in query_stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
        
    except Exception as e:
        logger.error(f"SPARQL interface test failed: {e}")
        raise


if __name__ == "__main__":
    main()