"""
RDF Transformation Pipeline

This module provides comprehensive transformation of Vietnamese Wikipedia data
to RDF format using the Vietnamese ontology and proper semantic mapping.
"""

import json
import yaml
import logging
import re
from typing import Dict, List, Optional, Set, Any, Tuple
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import FOAF, DCTERMS

from src.ontology.vietnam_ontology import VietnamOntology
from src.collectors.wikipedia_collector import WikipediaArticle

logger = logging.getLogger(__name__)


class RDFTransformer:
    """Comprehensive RDF transformation pipeline for Vietnamese Wikipedia data."""
    
    def __init__(self, ontology: Optional[VietnamOntology] = None, config_path: str = "config/ontology.yaml"):
        self.ontology = ontology or VietnamOntology(config_path)
        self.graph = Graph()
        self.entity_count = 0
        self.triple_count = 0
        self.transformation_stats = {
            'articles_processed': 0,
            'entities_created': 0,
            'triples_generated': 0,
            'infoboxes_processed': 0,
            'failed_transformations': 0,
            'template_mappings': {}
        }
        
        self._setup_namespaces()
        self._load_property_mappings()
    
    def _setup_namespaces(self) -> None:
        """Set up RDF namespaces."""
        # Copy namespaces from ontology
        for prefix, namespace in self.ontology.namespaces.items():
            self.graph.bind(prefix, namespace)
        
        logger.info("RDF namespaces configured")
    
    def _load_property_mappings(self) -> None:
        """Load property mappings for Vietnamese Wikipedia infoboxes."""
        self.property_mappings = {
            # Person properties
            'ngày sinh': 'birthDate',
            'sinh': 'birthDate',
            'nơi sinh': 'birthPlace',
            'quê quán': 'birthPlace',
            'ngày mất': 'deathDate',
            'mất': 'deathDate',
            'nơi mất': 'deathPlace',
            'nghề nghiệp': 'occupation',
            'quốc tịch': 'nationality',
            'dân tộc': 'ethnicity',
            
            # Place properties
            'tọa độ': 'coordinates',
            'diện tích': 'area',
            'dân số': 'population',
            'thành lập': 'foundingDate',
            'múi giờ': 'timeZone',
            'tỉnh': 'province',
            'quận': 'district',
            'phường': 'ward',
            
            # Organization properties
            'thành lập': 'foundingDate',
            'trụ sở': 'headquarters',
            'giám đốc': 'director',
            'hiệu trưởng': 'rector',
            
            # General properties
            'tên': 'name',
            'tên đầy đủ': 'fullName',
            'tên khác': 'alternateName',
            'mô tả': 'description',
            'website': 'homepage',
            'hình ảnh': 'image'
        }
        
        logger.info(f"Loaded {len(self.property_mappings)} property mappings")
    
    def create_entity_uri(self, title: str, entity_type: str = 'resource') -> URIRef:
        """Create a properly formatted URI for Vietnamese entities."""
        # Clean and encode the title
        cleaned_title = self._clean_title_for_uri(title)
        
        if entity_type == 'resource':
            base_uri = self.ontology.ontology_config['resource_uri']
        elif entity_type == 'property':
            base_uri = self.ontology.ontology_config['property_uri']
        else:
            base_uri = self.ontology.ontology_config['base_uri']
        
        return URIRef(base_uri + quote(cleaned_title, safe=''))
    
    def _clean_title_for_uri(self, title: str) -> str:
        """Clean Wikipedia title for use in URIs."""
        # Replace spaces with underscores
        cleaned = title.replace(' ', '_')
        
        # Remove special characters but keep Vietnamese diacritics
        cleaned = re.sub(r'[^\w\u00C0-\u1EF9]', '_', cleaned)
        
        # Remove multiple underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        
        # Remove leading/trailing underscores
        cleaned = cleaned.strip('_')
        
        return cleaned
    
    def transform_article(self, article: WikipediaArticle) -> int:
        """Transform a Wikipedia article to RDF triples."""
        logger.info(f"Transforming article: {article.title}")
        
        try:
            # Create entity URI
            entity_uri = self.create_entity_uri(article.title)
            
            # Determine entity type from infobox template
            entity_class = self._determine_entity_class(article)
            
            if entity_class:
                # Add type information
                self.graph.add((entity_uri, RDF.type, entity_class))
                
                # Add basic properties
                self._add_basic_properties(entity_uri, article)
                
                # Transform infobox data
                if article.infobox:
                    self._transform_infobox(entity_uri, article.infobox, entity_class)
                
                # Add categories
                self._add_categories(entity_uri, article.categories)
                
                # Add Wikipedia metadata
                self._add_wikipedia_metadata(entity_uri, article)
                
                self.entity_count += 1
                self.transformation_stats['articles_processed'] += 1
                self.transformation_stats['entities_created'] += 1
                
                if article.infobox:
                    self.transformation_stats['infoboxes_processed'] += 1
                    template_type = article.infobox.get('template_type', 'unknown')
                    self.transformation_stats['template_mappings'][template_type] = \
                        self.transformation_stats['template_mappings'].get(template_type, 0) + 1
                
                logger.info(f"Successfully transformed article: {article.title}")
                return len(list(self.graph.triples((entity_uri, None, None))))
            
            else:
                logger.warning(f"Could not determine entity class for: {article.title}")
                self.transformation_stats['failed_transformations'] += 1
                return 0
                
        except Exception as e:
            logger.error(f"Failed to transform article {article.title}: {e}")
            self.transformation_stats['failed_transformations'] += 1
            return 0
    
    def _determine_entity_class(self, article: WikipediaArticle) -> Optional[URIRef]:
        """Determine the ontology class for an article based on its infobox template."""
        if article.infobox and 'template_type' in article.infobox:
            template_type = article.infobox['template_type']
            
            # Check direct template mapping
            ontology_class = self.ontology.get_class_for_template(template_type)
            if ontology_class:
                return ontology_class
        
        # Fallback: analyze categories
        return self._determine_class_from_categories(article.categories)
    
    def _determine_class_from_categories(self, categories: List[str]) -> Optional[URIRef]:
        """Determine entity class from Wikipedia categories."""
        category_mappings = {
            'người': 'Person',
            'nhân vật': 'Person',
            'chính trị gia': 'PoliticalFigure',
            'nghệ sĩ': 'Artist',
            'nhà văn': 'Writer',
            'nhà khoa học': 'Scientist',
            'địa điểm': 'Place',
            'tỉnh': 'Province',
            'thành phố': 'City',
            'trường': 'University',
            'đại học': 'University',
            'công ty': 'Company',
            'tổ chức': 'Organization',
            'sự kiện': 'Event',
            'lịch sử': 'HistoricalEvent',
            'văn học': 'LiteraryWork',
            'âm nhạc': 'MusicalWork',
            'phim': 'Film'
        }
        
        for category in categories:
            category_lower = category.lower()
            for keyword, class_name in category_mappings.items():
                if keyword in category_lower:
                    return self.ontology.get_class_uri(class_name)
        
        # Default to generic entity
        return self.ontology.get_class_uri('Person')  # Most articles are about people
    
    def _add_basic_properties(self, entity_uri: URIRef, article: WikipediaArticle) -> None:
        """Add basic properties for any entity."""
        # Title and labels
        self.graph.add((entity_uri, RDFS.label, Literal(article.title, lang="vi")))
        self.graph.add((entity_uri, FOAF.name, Literal(article.title, lang="vi")))
        
        # Abstract/description
        if article.abstract:
            self.graph.add((entity_uri, RDFS.comment, Literal(article.abstract, lang="vi")))
            self.graph.add((entity_uri, DCTERMS.description, Literal(article.abstract, lang="vi")))
        
        # Wikipedia URL
        self.graph.add((entity_uri, FOAF.isPrimaryTopicOf, URIRef(article.url)))
        
        # Language
        self.graph.add((entity_uri, DCTERMS.language, Literal("vi")))
    
    def _transform_infobox(self, entity_uri: URIRef, infobox: Dict[str, Any], entity_class: URIRef) -> None:
        """Transform infobox data to RDF properties."""
        for key, value in infobox.items():
            if key == 'template_type' or not value or not value.strip():
                continue
            
            # Map Vietnamese property name to ontology property
            property_name = self.property_mappings.get(key.lower())
            if property_name:
                property_uri = self.ontology.get_property_uri(property_name)
                if property_uri:
                    # Determine if this is a literal or object property
                    object_value = self._process_property_value(value, property_name, entity_class)
                    if object_value:
                        self.graph.add((entity_uri, property_uri, object_value))
            else:
                # Create a custom property for unmapped infobox fields
                custom_property_uri = self.create_entity_uri(key, 'property')
                literal_value = Literal(str(value), lang="vi")
                self.graph.add((entity_uri, custom_property_uri, literal_value))
    
    def _process_property_value(self, value: str, property_name: str, entity_class: URIRef) -> Optional[Any]:
        """Process and convert property values to appropriate RDF objects."""
        if not value or not value.strip():
            return None
        
        value = value.strip()
        
        # Date processing
        if property_name in ['birthDate', 'deathDate', 'foundingDate']:
            date_value = self._parse_vietnamese_date(value)
            if date_value:
                return Literal(date_value, datatype=XSD.date)
        
        # Numeric processing
        elif property_name in ['population', 'area']:
            numeric_value = self._extract_number(value)
            if numeric_value is not None:
                return Literal(numeric_value, datatype=XSD.integer)
        
        # Location processing (create linked entities)
        elif property_name in ['birthPlace', 'deathPlace', 'province', 'district', 'ward']:
            place_uri = self.create_entity_uri(value)
            # Add basic information about the place
            self.graph.add((place_uri, RDF.type, self.ontology.get_class_uri('Place')))
            self.graph.add((place_uri, RDFS.label, Literal(value, lang="vi")))
            return place_uri
        
        # URL processing
        elif property_name == 'homepage':
            if value.startswith('http'):
                return URIRef(value)
        
        # Coordinates processing
        elif property_name == 'coordinates':
            coords = self._parse_coordinates(value)
            if coords:
                return Literal(coords, datatype=XSD.string)
        
        # Default: return as Vietnamese literal
        return Literal(value, lang="vi")
    
    def _parse_vietnamese_date(self, date_str: str) -> Optional[str]:
        """Parse Vietnamese date strings to ISO format."""
        if not date_str:
            return None
        
        # Remove common Vietnamese date prefixes
        date_str = re.sub(r'^(ngày |tháng |năm )', '', date_str.lower())
        
        # Common Vietnamese date patterns
        patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY
            r'(\d{4})',                       # YYYY only
            r'(\d{1,2}) tháng (\d{1,2}), (\d{4})'  # DD tháng MM, YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 1:  # Year only
                    return groups[0]
                elif len(groups) == 3:  # Full date
                    if 'tháng' in date_str:  # DD tháng MM, YYYY
                        day, month, year = groups
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:  # DD/MM/YYYY or DD-MM-YYYY
                        day, month, year = groups
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return None
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract numeric value from text."""
        # Remove common Vietnamese number separators and words
        text = re.sub(r'[.,\s]', '', text.lower())
        text = re.sub(r'(người|km²|m²|ha|hecta)', '', text)
        
        # Extract number
        match = re.search(r'\d+', text)
        if match:
            return int(match.group())
        
        return None
    
    def _parse_coordinates(self, coord_str: str) -> Optional[str]:
        """Parse coordinate strings."""
        # This is a simplified parser - could be expanded for more formats
        coord_pattern = r'(\d+\.?\d*)[°,\s]+(\d+\.?\d*)'
        match = re.search(coord_pattern, coord_str)
        if match:
            lat, lon = match.groups()
            return f"{lat},{lon}"
        
        return None
    
    def _add_categories(self, entity_uri: URIRef, categories: List[str]) -> None:
        """Add category information as SKOS concepts."""
        for category in categories:
            # Create category URI
            category_uri = self.create_entity_uri(category.replace('Thể loại:', ''))
            
            # Add category as SKOS concept
            self.graph.add((category_uri, RDF.type, self.ontology.namespaces['skos'].Concept))
            self.graph.add((category_uri, self.ontology.namespaces['skos'].prefLabel, 
                           Literal(category, lang="vi")))
            
            # Link entity to category
            self.graph.add((entity_uri, DCTERMS.subject, category_uri))
    
    def _add_wikipedia_metadata(self, entity_uri: URIRef, article: WikipediaArticle) -> None:
        """Add Wikipedia-specific metadata."""
        # Page ID
        self.graph.add((entity_uri, self.ontology.namespaces['vidbp'].wikipediaPageID, 
                       Literal(article.page_id, datatype=XSD.integer)))
        
        # Last modified
        if article.last_modified:
            self.graph.add((entity_uri, DCTERMS.modified, 
                           Literal(article.last_modified, datatype=XSD.dateTime)))
        
        # Revision ID
        if article.revision_id:
            self.graph.add((entity_uri, self.ontology.namespaces['vidbp'].wikipediaRevisionID, 
                           Literal(article.revision_id, datatype=XSD.integer)))
    
    def transform_articles_batch(self, articles: List[WikipediaArticle]) -> None:
        """Transform a batch of articles to RDF."""
        logger.info(f"Transforming {len(articles)} articles to RDF")
        
        for article in articles:
            self.transform_article(article)
        
        self.transformation_stats['triples_generated'] = len(self.graph)
        logger.info(f"Transformation complete. Generated {len(self.graph)} triples.")
    
    def export_rdf(self, output_path: str, format: str = 'turtle') -> None:
        """Export RDF graph to file."""
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            self.graph.serialize(destination=output_path, format=format)
            logger.info(f"RDF exported to {output_path} in {format} format")
        except Exception as e:
            logger.error(f"Failed to export RDF: {e}")
            raise
    
    def validate_rdf(self) -> Dict[str, Any]:
        """Validate the generated RDF data."""
        validation_results = {
            'total_triples': len(self.graph),
            'unique_subjects': len(set(self.graph.subjects())),
            'unique_predicates': len(set(self.graph.predicates())),
            'unique_objects': len(set(self.graph.objects())),
            'validation_errors': [],
            'warnings': []
        }
        
        # Check for common issues
        for subject, predicate, obj in self.graph:
            # Validate triple against ontology
            if not self.ontology.validate_triple(subject, predicate, obj):
                validation_results['validation_errors'].append({
                    'subject': str(subject),
                    'predicate': str(predicate),
                    'object': str(obj),
                    'issue': 'Ontology constraint violation'
                })
        
        # Check for missing required properties
        for subject in self.graph.subjects(RDF.type, None):
            if not any(self.graph.triples((subject, RDFS.label, None))):
                validation_results['warnings'].append({
                    'subject': str(subject),
                    'issue': 'Missing rdfs:label'
                })
        
        return validation_results
    
    def get_transformation_statistics(self) -> Dict[str, Any]:
        """Get detailed transformation statistics."""
        stats = self.transformation_stats.copy()
        stats['current_graph_size'] = len(self.graph)
        return stats
    
    def merge_with_existing_graph(self, existing_graph_path: str) -> None:
        """Merge current graph with an existing RDF file."""
        try:
            existing_graph = Graph()
            existing_graph.parse(existing_graph_path)
            
            # Merge graphs
            for triple in existing_graph:
                self.graph.add(triple)
            
            logger.info(f"Merged with existing graph. Total triples: {len(self.graph)}")
        except Exception as e:
            logger.error(f"Failed to merge with existing graph: {e}")
            raise


def main():
    """Main function for testing the transformer."""
    try:
        # Load sample articles
        from src.collectors.wikipedia_collector import WikipediaCollector
        
        collector = WikipediaCollector()
        articles = collector.load_articles_from_json("data/raw/vietnamese_articles.json")
        
        if not articles:
            # Collect sample articles if none exist
            articles = collector.collect_sample_articles()
            collector.save_articles_to_json(articles, "data/raw/vietnamese_articles.json")
        
        # Transform to RDF
        transformer = RDFTransformer()
        transformer.transform_articles_batch(articles)
        
        # Export RDF
        transformer.export_rdf("data/rdf/vietnamese_dbpedia.ttl", "turtle")
        transformer.export_rdf("data/rdf/vietnamese_dbpedia.xml", "xml")
        transformer.export_rdf("data/rdf/vietnamese_dbpedia.jsonld", "json-ld")
        
        # Validate RDF
        validation_results = transformer.validate_rdf()
        print("RDF Validation Results:")
        print(f"  Total triples: {validation_results['total_triples']}")
        print(f"  Unique subjects: {validation_results['unique_subjects']}")
        print(f"  Validation errors: {len(validation_results['validation_errors'])}")
        print(f"  Warnings: {len(validation_results['warnings'])}")
        
        # Print transformation statistics
        stats = transformer.get_transformation_statistics()
        print("\nTransformation Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
    except Exception as e:
        logger.error(f"RDF transformation failed: {e}")
        raise


if __name__ == "__main__":
    main()