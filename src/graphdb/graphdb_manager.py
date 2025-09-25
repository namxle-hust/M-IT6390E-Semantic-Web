"""
GraphDB Management Module

This module provides comprehensive GraphDB integration including repository
management, data loading, and SPARQL query capabilities.
"""

import requests
import json
import yaml
import logging
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from urllib.parse import urljoin
import io
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class GraphDBError(Exception):
    """Custom exception for GraphDB operations."""
    pass


class GraphDBManager:
    """Comprehensive GraphDB management with repository operations and data loading."""
    
    def __init__(self, config_path: str = "config/graphdb.yaml"):
        self.config_path = config_path
        self.session = requests.Session()
        self.base_url = None
        self.repositories = {}
        
        self._load_config()
        self._setup_session()
        self._check_connection()
    
    def _load_config(self) -> None:
        """Load GraphDB configuration."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.graphdb_config = config['graphdb']
                self.repository_configs = config['repositories']
                self.workbench_config = config['workbench']
                self.sparql_config = config['sparql']
                self.backup_config = config['backup']
                
                # Build base URL
                self.base_url = f"http://{self.graphdb_config['host']}:{self.graphdb_config['port']}"
                logger.info("GraphDB configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load GraphDB config: {e}")
            raise GraphDBError(f"Configuration error: {e}")
    
    def _setup_session(self) -> None:
        """Set up HTTP session for GraphDB API calls."""
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Set authentication if provided
        if self.graphdb_config.get('username') and self.graphdb_config.get('password'):
            self.session.auth = HTTPBasicAuth(
                self.graphdb_config['username'],
                self.graphdb_config['password']
            )
        
        # Set timeout
        self.session.timeout = self.graphdb_config.get('timeout', 30)
        logger.info("GraphDB session configured")
    
    def _check_connection(self) -> None:
        """Check connection to GraphDB server."""
        try:
            response = self.session.get(f"{self.base_url}/rest/info/version")
            if response.status_code == 200:
                version_info = response.json()
                logger.info(f"Connected to GraphDB {version_info.get('productVersion', 'Unknown')}")
            else:
                raise GraphDBError(f"Failed to connect: HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"GraphDB connection failed: {e}")
            raise GraphDBError(f"Connection failed: {e}")
    
    def list_repositories(self) -> List[Dict[str, Any]]:
        """List all repositories on GraphDB server."""
        try:
            response = self.session.get(f"{self.base_url}/rest/repositories")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list repositories: {e}")
            raise GraphDBError(f"Failed to list repositories: {e}")
    
    def repository_exists(self, repository_id: str) -> bool:
        """Check if repository exists."""
        repositories = self.list_repositories()
        return any(repo['id'] == repository_id for repo in repositories)
    
    def create_repository(self, repository_id: str = None) -> bool:
        """Create a new GraphDB repository."""
        if not repository_id:
            repository_id = list(self.repository_configs.keys())[0]
        
        if repository_id not in self.repository_configs:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        config = self.repository_configs[repository_id]
        
        if self.repository_exists(config['id']):
            logger.info(f"Repository {config['id']} already exists")
            return True
        
        # Create repository configuration
        repo_config = {
            "id": config['id'],
            "title": config['title'],
            "type": config['type'],
            "params": {
                "ruleset": {"value": config['ruleset']},
                "disableSameAs": {"value": str(config['disable_same_as']).lower()},
                "checkForInconsistencies": {"value": str(config['check_for_inconsistencies']).lower()},
                "disableContextIndex": {"value": str(config['disable_context_index']).lower()},
                "enableContextIndex": {"value": str(config['enable_context_index']).lower()},
                "enablePredicateList": {"value": str(config['enablePredicateList']).lower()},
                "inMemoryLiteralProperties": {"value": str(config['in_memory_literal_properties']).lower()},
                "enableLiteralIndex": {"value": str(config['enable_literal_index']).lower()},
                "indexCompressionRatio": {"value": str(config['index_compression_ratio'])},
                "enableFtsIndex": {"value": str(config['enable_fts_index']).lower()},
                "ftsStringLiteralsIndex": {"value": config['fts_string_literals_index']},
                "ftsIrisIndex": {"value": config['fts_iris_index']},
                "queryTimeout": {"value": str(config['query_timeout'])},
                "queryLimitResults": {"value": str(config['query_limit_results'])},
                "throwQueryEvaluationExceptionOnTimeout": {"value": str(config['throw_query_evaluation_exception_on_timeout']).lower()},
                "readOnly": {"value": str(config['read_only']).lower()}
            }
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/rest/repositories",
                json=repo_config,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 201:
                logger.info(f"Repository {config['id']} created successfully")
                self.repositories[repository_id] = config
                return True
            else:
                logger.error(f"Failed to create repository: HTTP {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create repository: {e}")
            raise GraphDBError(f"Repository creation failed: {e}")
    
    def delete_repository(self, repository_id: str) -> bool:
        """Delete a repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            response = self.session.delete(f"{self.base_url}/rest/repositories/{config['id']}")
            
            if response.status_code == 200:
                logger.info(f"Repository {config['id']} deleted successfully")
                if repository_id in self.repositories:
                    del self.repositories[repository_id]
                return True
            else:
                logger.error(f"Failed to delete repository: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete repository: {e}")
            raise GraphDBError(f"Repository deletion failed: {e}")
    
    def get_repository_info(self, repository_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            response = self.session.get(f"{self.base_url}/rest/repositories/{config['id']}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get repository info: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get repository info: {e}")
            return None
    
    def load_rdf_data(self, repository_id: str, rdf_file_path: str, 
                     format: str = 'turtle', context: str = None) -> bool:
        """Load RDF data into a repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        if not Path(rdf_file_path).exists():
            raise GraphDBError(f"RDF file not found: {rdf_file_path}")
        
        # Map format to MIME type
        format_mapping = {
            'turtle': 'text/turtle',
            'ttl': 'text/turtle',
            'xml': 'application/rdf+xml',
            'rdf': 'application/rdf+xml',
            'n3': 'text/n3',
            'nt': 'application/n-triples',
            'jsonld': 'application/ld+json',
            'json-ld': 'application/ld+json'
        }
        
        content_type = format_mapping.get(format.lower(), 'text/turtle')
        
        try:
            with open(rdf_file_path, 'rb') as file:
                data = file.read()
            
            # Build URL with context parameter if provided
            url = f"{self.base_url}/repositories/{config['id']}/statements"
            params = {}
            if context:
                params['context'] = f"<{context}>"
            
            response = self.session.post(
                url,
                params=params,
                data=data,
                headers={'Content-Type': content_type}
            )
            
            if response.status_code == 204:  # No Content - success
                logger.info(f"Successfully loaded RDF data from {rdf_file_path} into {config['id']}")
                return True
            else:
                logger.error(f"Failed to load RDF data: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load RDF data: {e}")
            raise GraphDBError(f"Data loading failed: {e}")
    
    def load_rdf_from_string(self, repository_id: str, rdf_data: str, 
                           format: str = 'turtle', context: str = None) -> bool:
        """Load RDF data from string."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        format_mapping = {
            'turtle': 'text/turtle',
            'ttl': 'text/turtle',
            'xml': 'application/rdf+xml',
            'rdf': 'application/rdf+xml',
            'n3': 'text/n3',
            'nt': 'application/n-triples',
            'jsonld': 'application/ld+json',
            'json-ld': 'application/ld+json'
        }
        
        content_type = format_mapping.get(format.lower(), 'text/turtle')
        
        try:
            url = f"{self.base_url}/repositories/{config['id']}/statements"
            params = {}
            if context:
                params['context'] = f"<{context}>"
            
            response = self.session.post(
                url,
                params=params,
                data=rdf_data.encode('utf-8'),
                headers={'Content-Type': content_type}
            )
            
            if response.status_code == 204:
                logger.info(f"Successfully loaded RDF data into {config['id']}")
                return True
            else:
                logger.error(f"Failed to load RDF data: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load RDF data: {e}")
            raise GraphDBError(f"Data loading failed: {e}")
    
    def clear_repository(self, repository_id: str, context: str = None) -> bool:
        """Clear all data from a repository or specific context."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            url = f"{self.base_url}/repositories/{config['id']}/statements"
            params = {}
            if context:
                params['context'] = f"<{context}>"
            
            response = self.session.delete(url, params=params)
            
            if response.status_code == 204:
                context_msg = f" (context: {context})" if context else ""
                logger.info(f"Successfully cleared repository {config['id']}{context_msg}")
                return True
            else:
                logger.error(f"Failed to clear repository: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to clear repository: {e}")
            raise GraphDBError(f"Repository clearing failed: {e}")
    
    def get_repository_size(self, repository_id: str) -> Optional[int]:
        """Get the number of statements in a repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            response = self.session.get(f"{self.base_url}/repositories/{config['id']}/size")
            
            if response.status_code == 200:
                return int(response.text.strip())
            else:
                logger.warning(f"Failed to get repository size: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get repository size: {e}")
            return None
    
    def execute_sparql_query(self, repository_id: str, query: str, 
                           query_type: str = 'select') -> Optional[Dict[str, Any]]:
        """Execute SPARQL query on repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            url = f"{self.base_url}/repositories/{config['id']}"
            
            # Determine accept header based on query type
            if query_type.lower() == 'construct' or query_type.lower() == 'describe':
                accept_header = 'application/rdf+xml'
            else:
                accept_header = 'application/sparql-results+json'
            
            response = self.session.post(
                url,
                data={'query': query},
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': accept_header
                }
            )
            
            if response.status_code == 200:
                if accept_header == 'application/sparql-results+json':
                    return response.json()
                else:
                    return {'rdf_data': response.text}
            else:
                logger.error(f"SPARQL query failed: HTTP {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            raise GraphDBError(f"Query execution failed: {e}")
    
    def create_backup(self, repository_id: str, backup_path: str = None) -> Optional[str]:
        """Create repository backup."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        if not backup_path:
            timestamp = int(time.time())
            backup_dir = Path(self.backup_config['directory'])
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{config['id']}_backup_{timestamp}.ttl"
        
        try:
            # Export all data as Turtle
            query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
            result = self.execute_sparql_query(repository_id, query, 'construct')
            
            if result and 'rdf_data' in result:
                with open(backup_path, 'w', encoding='utf-8') as file:
                    file.write(result['rdf_data'])
                
                logger.info(f"Backup created: {backup_path}")
                return str(backup_path)
            else:
                logger.error("Failed to create backup: No data returned")
                return None
                
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise GraphDBError(f"Backup failed: {e}")
    
    def restore_backup(self, repository_id: str, backup_path: str, 
                      clear_first: bool = True) -> bool:
        """Restore repository from backup."""
        if not Path(backup_path).exists():
            raise GraphDBError(f"Backup file not found: {backup_path}")
        
        try:
            if clear_first:
                self.clear_repository(repository_id)
            
            # Load backup data
            success = self.load_rdf_data(repository_id, backup_path, format='turtle')
            
            if success:
                logger.info(f"Repository {repository_id} restored from {backup_path}")
                return True
            else:
                logger.error("Backup restoration failed")
                return False
                
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}")
            raise GraphDBError(f"Restore failed: {e}")
    
    def get_namespaces(self, repository_id: str) -> Optional[Dict[str, str]]:
        """Get namespace prefixes from repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            response = self.session.get(f"{self.base_url}/repositories/{config['id']}/namespaces")
            
            if response.status_code == 200:
                result = response.json()
                namespaces = {}
                for binding in result.get('results', {}).get('bindings', []):
                    prefix = binding.get('prefix', {}).get('value', '')
                    namespace = binding.get('namespace', {}).get('value', '')
                    if prefix and namespace:
                        namespaces[prefix] = namespace
                return namespaces
            else:
                logger.warning(f"Failed to get namespaces: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get namespaces: {e}")
            return None
    
    def set_namespace(self, repository_id: str, prefix: str, namespace: str) -> bool:
        """Set namespace prefix in repository."""
        config = self.repository_configs.get(repository_id)
        if not config:
            raise GraphDBError(f"No configuration found for repository: {repository_id}")
        
        try:
            response = self.session.put(
                f"{self.base_url}/repositories/{config['id']}/namespaces/{prefix}",
                data=namespace,
                headers={'Content-Type': 'text/plain'}
            )
            
            if response.status_code == 204:
                logger.info(f"Namespace set: {prefix} -> {namespace}")
                return True
            else:
                logger.error(f"Failed to set namespace: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to set namespace: {e}")
            return False
    
    def load_ontology(self, repository_id: str, ontology_path: str = None) -> bool:
        """Load ontology file into repository."""
        if not ontology_path:
            # Default ontology path
            ontology_path = "ontology/vietnamese_ontology.ttl"
        
        if not Path(ontology_path).exists():
            logger.error(f"Ontology file not found: {ontology_path}")
            return False
        
        try:
            # Load ontology with specific context
            success = self.load_rdf_data(
                repository_id=repository_id,
                rdf_file_path=ontology_path,
                format='turtle',
                context='http://vi.dbpedia.org/ontology/'
            )
            
            if success:
                logger.info(f"Ontology loaded successfully from {ontology_path}")
                return True
            else:
                logger.error("Failed to load ontology")
                return False
                
        except Exception as e:
            logger.error(f"Ontology loading failed: {e}")
            return False
    
    def setup_repository_with_ontology(self, repository_id: str = None) -> bool:
        """Complete repository setup including ontology loading."""
        try:
            # Create repository
            if not self.create_repository(repository_id):
                return False
            
            # Load ontology
            if not self.load_ontology(repository_id or list(self.repository_configs.keys())[0]):
                logger.warning("Failed to load ontology, but repository was created")
                return False
            
            logger.info("Repository setup completed with ontology")
            return True
            
        except Exception as e:
            logger.error(f"Repository setup failed: {e}")
            return False


def main():
    """Main function for testing GraphDB manager."""
    try:
        manager = GraphDBManager()
        
        # List existing repositories
        repos = manager.list_repositories()
        print(f"Existing repositories: {[repo['id'] for repo in repos]}")
        
        # Create Vietnamese DBPedia repository
        repo_id = 'vietnamese_dbpedia'
        if manager.create_repository(repo_id):
            print(f"Repository {repo_id} created successfully")
            
            # Get repository info
            info = manager.get_repository_info(repo_id)
            if info:
                print(f"Repository info: {info.get('title', 'N/A')}")
            
            # Check repository size
            size = manager.get_repository_size(repo_id)
            if size is not None:
                print(f"Repository size: {size} statements")
        
    except Exception as e:
        logger.error(f"GraphDB manager test failed: {e}")
        raise


if __name__ == "__main__":
    main()