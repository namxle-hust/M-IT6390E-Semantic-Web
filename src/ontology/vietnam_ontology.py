"""
Vietnamese Ontology Management Module

This module provides comprehensive management of the Vietnamese DBPedia ontology,
including class definitions, property mappings, and validation capabilities.
"""

import yaml
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import FOAF, DCTERMS, SKOS

logger = logging.getLogger(__name__)


class VietnamOntology:
    """Vietnamese DBPedia ontology manager with comprehensive class and property definitions."""
    
    def __init__(self, config_path: str = "config/ontology.yaml"):
        self.config_path = config_path
        self.graph = Graph()
        self.namespaces = {}
        self.classes = {}
        self.properties = {}
        self.mappings = {}
        
        self._load_config()
        self._setup_namespaces()
        self._create_ontology()
    
    def _load_config(self) -> None:
        """Load ontology configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.ontology_config = config['ontology']
                self.namespace_config = config['namespaces']
                self.class_config = config['classes']
                self.property_config = config['properties']
                self.mapping_config = config['mappings']
                logger.info("Ontology configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load ontology config: {e}")
            raise
    
    def _setup_namespaces(self) -> None:
        """Set up RDF namespaces for the ontology."""
        # Core namespaces
        self.namespaces.update({
            'vi': Namespace(self.namespace_config['vi']),
            'vidbp': Namespace(self.namespace_config['vidbp']),
            'vires': Namespace(self.namespace_config['vires']),
            'dbpedia': Namespace(self.namespace_config['dbpedia']),
            'dbpprop': Namespace(self.namespace_config['dbpprop']),
            'dbpres': Namespace(self.namespace_config['dbpres']),
            'rdfs': RDFS,
            'rdf': RDF,
            'owl': OWL,
            'foaf': FOAF,
            'dct': DCTERMS,
            'xsd': XSD,
            'skos': SKOS
        })
        
        # Bind namespaces to graph
        for prefix, namespace in self.namespaces.items():
            self.graph.bind(prefix, namespace)
        
        logger.info(f"Set up {len(self.namespaces)} namespaces")
    
    def _create_ontology(self) -> None:
        """Create the complete Vietnamese ontology with classes and properties."""
        self._create_ontology_metadata()
        self._create_classes()
        self._create_properties()
        self._create_mappings()
        logger.info("Vietnamese ontology created successfully")
    
    def _create_ontology_metadata(self) -> None:
        """Create ontology metadata and imports."""
        vi_ontology = URIRef(self.ontology_config['base_uri'])
        
        # Basic ontology metadata
        self.graph.add((vi_ontology, RDF.type, OWL.Ontology))
        self.graph.add((vi_ontology, RDFS.label, Literal("Vietnamese DBPedia Ontology", lang="en")))
        self.graph.add((vi_ontology, RDFS.label, Literal("Bản thể học DBPedia Việt Nam", lang="vi")))
        self.graph.add((vi_ontology, RDFS.comment, 
                       Literal("Comprehensive ontology for Vietnamese knowledge representation", lang="en")))
        self.graph.add((vi_ontology, RDFS.comment, 
                       Literal("Bản thể học toàn diện cho biểu diễn tri thức Việt Nam", lang="vi")))
        self.graph.add((vi_ontology, DCTERMS.creator, Literal("Vietnamese DBPedia Project")))
        self.graph.add((vi_ontology, OWL.versionInfo, Literal("1.0")))
        
        # Import related ontologies
        self.graph.add((vi_ontology, OWL.imports, URIRef("http://dbpedia.org/ontology/")))
        self.graph.add((vi_ontology, OWL.imports, URIRef("http://xmlns.com/foaf/0.1/")))
    
    def _create_classes(self) -> None:
        """Create ontology classes with Vietnamese and English labels."""
        for class_name, class_info in self.class_config.items():
            class_uri = self.namespaces['vi'][class_info['uri']]
            
            # Create class
            self.graph.add((class_uri, RDF.type, OWL.Class))
            self.graph.add((class_uri, RDFS.label, Literal(class_info['label_vi'], lang="vi")))
            self.graph.add((class_uri, RDFS.label, Literal(class_info['label_en'], lang="en")))
            self.graph.add((class_uri, RDFS.comment, Literal(class_info['comment_vi'], lang="vi")))
            
            # Add equivalent class mapping to DBPedia
            if 'equivalent_class' in class_info:
                equivalent_uri = URIRef(class_info['equivalent_class'])
                self.graph.add((class_uri, OWL.equivalentClass, equivalent_uri))
            
            # Create subclasses
            if 'subclasses' in class_info:
                for subclass_name in class_info['subclasses']:
                    subclass_info = self.class_config.get(subclass_name)
                    if subclass_info:
                        subclass_uri = self.namespaces['vi'][subclass_info['uri']]
                        self.graph.add((subclass_uri, RDFS.subClassOf, class_uri))
            
            self.classes[class_name] = class_uri
        
        logger.info(f"Created {len(self.classes)} ontology classes")
    
    def _create_properties(self) -> None:
        """Create ontology properties with domains and ranges."""
        for prop_name, prop_info in self.property_config.items():
            prop_uri = self.namespaces['vidbp'][prop_info['uri']]
            
            # Create property (default to object property, can be overridden)
            prop_type = OWL.ObjectProperty if prop_info.get('range') in self.classes else OWL.DatatypeProperty
            self.graph.add((prop_uri, RDF.type, prop_type))
            self.graph.add((prop_uri, RDFS.label, Literal(prop_info['label_vi'], lang="vi")))
            self.graph.add((prop_uri, RDFS.label, Literal(prop_info['label_en'], lang="en")))
            self.graph.add((prop_uri, RDFS.comment, Literal(prop_info['comment_vi'], lang="vi")))
            
            # Set domain
            if 'domain' in prop_info:
                domain_class = self.classes.get(prop_info['domain'])
                if domain_class:
                    self.graph.add((prop_uri, RDFS.domain, domain_class))
            
            # Set range
            if 'range' in prop_info:
                range_value = prop_info['range']
                if range_value in self.classes:
                    self.graph.add((prop_uri, RDFS.range, self.classes[range_value]))
                elif range_value.startswith('xsd:'):
                    xsd_type = range_value.replace('xsd:', '')
                    self.graph.add((prop_uri, RDFS.range, getattr(XSD, xsd_type)))
            
            # Add equivalent property mapping
            if 'equivalent_property' in prop_info:
                equivalent_uri = URIRef(prop_info['equivalent_property'])
                self.graph.add((prop_uri, OWL.equivalentProperty, equivalent_uri))
            
            self.properties[prop_name] = prop_uri
        
        logger.info(f"Created {len(self.properties)} ontology properties")
    
    def _create_mappings(self) -> None:
        """Create mappings between infobox templates and ontology classes."""
        for template, class_name in self.mapping_config['infobox_templates'].items():
            if class_name in self.classes:
                self.mappings[template] = self.classes[class_name]
        
        logger.info(f"Created {len(self.mappings)} template mappings")
    
    def get_class_for_template(self, template_name: str) -> Optional[URIRef]:
        """Get ontology class URI for Wikipedia infobox template."""
        return self.mappings.get(template_name)
    
    def get_property_uri(self, property_name: str) -> Optional[URIRef]:
        """Get property URI by name."""
        return self.properties.get(property_name)
    
    def get_class_uri(self, class_name: str) -> Optional[URIRef]:
        """Get class URI by name."""
        return self.classes.get(class_name)
    
    def validate_triple(self, subject: URIRef, predicate: URIRef, obj) -> bool:
        """Validate if a triple conforms to the ontology constraints."""
        try:
            # Check if predicate exists in ontology
            if not any(self.graph.triples((predicate, RDF.type, None))):
                logger.warning(f"predicate is not exists in ontology, {predicate}")
                return False
            
            # Check domain constraints
            for domain in self.graph.objects(predicate, RDFS.domain):
                logger.warning(f"domain constraints")
                if not any(self.graph.triples((subject, RDF.type, domain))):
                    return False
            
            # Check range constraints for object properties
            if isinstance(obj, URIRef):
                for range_class in self.graph.objects(predicate, RDFS.range):
                    if not any(self.graph.triples((obj, RDF.type, range_class))):
                        logger.warning(f"range constraints")
                        return False
            
            return True
        except Exception as e:
            logger.warning(f"Triple validation failed: {e}")
            return False
    
    def export_ontology(self, output_path: str, format: str = 'turtle') -> None:
        """Export ontology to file in specified format."""
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            self.graph.serialize(destination=output_path, format=format)
            logger.info(f"Ontology exported to {output_path} in {format} format")
        except Exception as e:
            logger.error(f"Failed to export ontology: {e}")
            raise
    
    def get_ontology_statistics(self) -> Dict[str, int]:
        """Get statistics about the ontology."""
        return {
            'classes': len(self.classes),
            'properties': len(self.properties),
            'mappings': len(self.mappings),
            'total_triples': len(self.graph)
        }
    
    def generate_documentation(self, output_path: str) -> None:
        """Generate HTML documentation for the ontology."""
        try:
            doc_content = self._generate_html_documentation()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as file:
                file.write(doc_content)
            
            logger.info(f"Ontology documentation generated at {output_path}")
        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
            raise
    
    def _generate_html_documentation(self) -> str:
        """Generate HTML documentation content."""
        html_content = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Vietnamese DBPedia Ontology Documentation</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .class {{ margin: 20px 0; padding: 15px; border: 1px solid #ccc; }}
                .property {{ margin: 15px 0; padding: 10px; background: #f9f9f9; }}
                .uri {{ color: #0066cc; font-family: monospace; }}
                .label {{ font-weight: bold; }}
                .comment {{ font-style: italic; color: #666; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Vietnamese DBPedia Ontology Documentation</h1>
            <p>Comprehensive ontology for Vietnamese knowledge representation</p>
            
            <h2>Classes</h2>
        """
        
        # Add class documentation
        for class_name, class_info in self.class_config.items():
            html_content += f"""
            <div class="class">
                <h3>{class_info['label_vi']} ({class_info['label_en']})</h3>
                <p class="uri">URI: {self.namespaces['vi'][class_info['uri']]}</p>
                <p class="comment">{class_info['comment_vi']}</p>
                {'<p><strong>Equivalent to:</strong> ' + class_info.get('equivalent_class', '') + '</p>' if 'equivalent_class' in class_info else ''}
            </div>
            """
        
        html_content += "<h2>Properties</h2>"
        
        # Add property documentation
        for prop_name, prop_info in self.property_config.items():
            html_content += f"""
            <div class="property">
                <h4>{prop_info['label_vi']} ({prop_info['label_en']})</h4>
                <p class="uri">URI: {self.namespaces['vidbp'][prop_info['uri']]}</p>
                <p class="comment">{prop_info['comment_vi']}</p>
                <p><strong>Domain:</strong> {prop_info.get('domain', 'N/A')}</p>
                <p><strong>Range:</strong> {prop_info.get('range', 'N/A')}</p>
                {'<p><strong>Equivalent to:</strong> ' + prop_info.get('equivalent_property', '') + '</p>' if 'equivalent_property' in prop_info else ''}
            </div>
            """
        
        html_content += """
            </body>
        </html>
        """
        
        return html_content


def main():
    """Main function for testing the ontology."""
    try:
        # Create ontology
        ontology = VietnamOntology()
        
        # Export to different formats
        ontology.export_ontology("ontology/vietnamese_dbpedia.ttl", "turtle")
        ontology.export_ontology("ontology/vietnamese_dbpedia.owl", "xml")
        ontology.export_ontology("ontology/vietnamese_dbpedia.jsonld", "json-ld")
        
        # Generate documentation
        ontology.generate_documentation("ontology/vietnamese_ontology_docs.html")
        
        # Print statistics
        stats = ontology.get_ontology_statistics()
        print("Ontology Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
    except Exception as e:
        logger.error(f"Ontology creation failed: {e}")
        raise


if __name__ == "__main__":
    main()