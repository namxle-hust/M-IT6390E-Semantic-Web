"""
Vietnamese DBPedia - Semantic Web Knowledge Base

A comprehensive Vietnamese semantic web knowledge base with GraphDB integration.
"""

__version__ = "1.0.0"
__author__ = "M-IT6390E Semantic Web Project"
__email__ = "student@example.com"

from src.ontology.vietnam_ontology import VietnamOntology
from src.collectors.wikipedia_collector import WikipediaCollector
from src.transformers.rdf_transformer import RDFTransformer
from src.graphdb.graphdb_manager import GraphDBManager
from src.entity_linking.entity_linker import EntityLinker
from src.interfaces.sparql_interface import SPARQLInterface

__all__ = [
    "VietnamOntology",
    "WikipediaCollector", 
    "RDFTransformer",
    "GraphDBManager",
    "EntityLinker",
    "SPARQLInterface"
]