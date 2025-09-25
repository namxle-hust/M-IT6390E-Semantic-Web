"""
Entity Linking Module

This module provides comprehensive entity linking capabilities to connect
Vietnamese entities with English DBPedia entities using multiple similarity
algorithms and SPARQL queries.
"""

import json
import re
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import requests
from SPARQLWrapper import SPARQLWrapper, JSON
from Levenshtein import distance as levenshtein_distance
from fuzzywuzzy import fuzz
from unidecode import unidecode

from src.collectors.wikipedia_collector import WikipediaArticle

logger = logging.getLogger(__name__)


@dataclass
class EntityMatch:
    """Entity match result with confidence scoring."""
    vietnamese_entity: str
    english_entity: str
    dbpedia_uri: str
    confidence_score: float
    similarity_scores: Dict[str, float]
    match_method: str
    additional_info: Dict[str, Any] = None


class EntityLinker:
    """Advanced entity linking system for Vietnamese-English DBPedia alignment."""
    
    def __init__(self, dbpedia_endpoint: str = "https://dbpedia.org/sparql"):
        self.dbpedia_endpoint = dbpedia_endpoint
        self.sparql = SPARQLWrapper(dbpedia_endpoint)
        self.sparql.setReturnFormat(JSON)
        
        # Caching for SPARQL results
        self.sparql_cache = {}
        self.language_links_cache = {}
        
        # Configuration
        self.confidence_threshold = 0.8
        self.max_candidates = 10
        self.request_timeout = 30
        
        # Statistics
        self.linking_stats = {
            'entities_processed': 0,
            'successful_links': 0,
            'high_confidence_links': 0,
            'medium_confidence_links': 0,
            'low_confidence_links': 0,
            'failed_links': 0,
            'cache_hits': 0,
            'sparql_queries': 0
        }
        
        self._setup_session()
        self._load_name_mappings()
    
    def _setup_session(self) -> None:
        """Set up HTTP session for external requests."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Vietnamese-DBPedia-EntityLinker/1.0'
        })
        self.session.timeout = self.request_timeout
        logger.info("Entity linker HTTP session configured")
    
    def _load_name_mappings(self) -> None:
        """Load predefined name mappings for Vietnamese entities."""
        self.name_mappings = {
            # Historical figures
            'Hồ Chí Minh': 'Ho Chi Minh',
            'Nguyễn Trãi': 'Nguyen Trai',
            'Võ Nguyên Giáp': 'Vo Nguyen Giap',
            'Lê Lợi': 'Le Loi',
            'Trần Hưng Đạo': 'Tran Hung Dao',
            
            # Places
            'Hà Nội': 'Hanoi',
            'Thành phố Hồ Chí Minh': 'Ho Chi Minh City',
            'Sài Gòn': 'Ho Chi Minh City',
            'Huế': 'Hue',
            'Đà Nẵng': 'Da Nang',
            'Cần Thơ': 'Can Tho',
            'Hải Phòng': 'Haiphong',
            'Vịnh Hạ Long': 'Ha Long Bay',
            'Hội An': 'Hoi An',
            
            # Organizations
            'Đại học Quốc gia Hà Nội': 'Vietnam National University, Hanoi',
            'Đại học Bách khoa Hà Nội': 'Hanoi University of Science and Technology',
            
            # Events
            'Chiến thắng Điện Biên Phủ': 'Battle of Dien Bien Phu',
            'Cách mạng tháng Tám': 'August Revolution',
            
            # Literary works
            'Truyện Kiều': 'The Tale of Kieu',
            'Số đỏ': 'Dumb Luck'
        }
        logger.info(f"Loaded {len(self.name_mappings)} predefined name mappings")
    
    def find_matching_entities(self, vietnamese_entity: str, 
                             entity_type: str = None) -> List[EntityMatch]:
        """Find matching English DBPedia entities for a Vietnamese entity."""
        logger.info(f"Finding matches for: {vietnamese_entity}")
        
        self.linking_stats['entities_processed'] += 1
        matches = []
        
        try:
            # Method 1: Direct name mapping
            direct_match = self._find_direct_mapping(vietnamese_entity)
            if direct_match:
                matches.append(direct_match)
            
            # Method 2: Wikipedia language links
            lang_link_matches = self._find_language_link_matches(vietnamese_entity)
            matches.extend(lang_link_matches)
            
            # Method 3: String similarity search
            similarity_matches = self._find_similarity_matches(vietnamese_entity, entity_type)
            matches.extend(similarity_matches)
            
            # Method 4: SPARQL property-based search
            property_matches = self._find_property_based_matches(vietnamese_entity)
            matches.extend(property_matches)
            
            # Remove duplicates and sort by confidence
            unique_matches = self._deduplicate_matches(matches)
            sorted_matches = sorted(unique_matches, key=lambda x: x.confidence_score, reverse=True)
            
            # Update statistics
            if sorted_matches:
                self.linking_stats['successful_links'] += 1
                best_confidence = sorted_matches[0].confidence_score
                
                if best_confidence >= 0.9:
                    self.linking_stats['high_confidence_links'] += 1
                elif best_confidence >= 0.7:
                    self.linking_stats['medium_confidence_links'] += 1
                else:
                    self.linking_stats['low_confidence_links'] += 1
            else:
                self.linking_stats['failed_links'] += 1
            
            logger.info(f"Found {len(sorted_matches)} matches for {vietnamese_entity}")
            return sorted_matches[:self.max_candidates]
            
        except Exception as e:
            logger.error(f"Entity linking failed for {vietnamese_entity}: {e}")
            self.linking_stats['failed_links'] += 1
            return []
    
    def _find_direct_mapping(self, vietnamese_entity: str) -> Optional[EntityMatch]:
        """Find entity using direct name mapping."""
        english_name = self.name_mappings.get(vietnamese_entity)
        if not english_name:
            return None
        
        # Query DBPedia for the English name
        dbpedia_uri = self._query_dbpedia_by_label(english_name)
        if dbpedia_uri:
            return EntityMatch(
                vietnamese_entity=vietnamese_entity,
                english_entity=english_name,
                dbpedia_uri=dbpedia_uri,
                confidence_score=0.95,
                similarity_scores={'direct_mapping': 1.0},
                match_method='direct_mapping',
                additional_info={'predefined': True}
            )
        
        return None
    
    def _find_language_link_matches(self, vietnamese_entity: str) -> List[EntityMatch]:
        """Find matches using Wikipedia cross-language links."""
        try:
            # Check cache first
            cache_key = f"langlinks_{vietnamese_entity}"
            if cache_key in self.language_links_cache:
                self.linking_stats['cache_hits'] += 1
                cached_result = self.language_links_cache[cache_key]
                if cached_result:
                    return [cached_result]
                else:
                    return []
            
            # Query Vietnamese Wikipedia for language links
            api_url = "https://vi.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'titles': vietnamese_entity,
                'prop': 'langlinks',
                'lllang': 'en',
                'lllimit': 1
            }
            
            response = self.session.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            for page_data in pages.values():
                langlinks = page_data.get('langlinks', [])
                
                for link in langlinks:
                    if link.get('lang') == 'en':
                        english_title = link.get('*', '')
                        if english_title:
                            # Get DBPedia URI for English entity
                            dbpedia_uri = self._get_dbpedia_uri_from_wikipedia_title(english_title)
                            
                            if dbpedia_uri:
                                match = EntityMatch(
                                    vietnamese_entity=vietnamese_entity,
                                    english_entity=english_title,
                                    dbpedia_uri=dbpedia_uri,
                                    confidence_score=0.9,
                                    similarity_scores={'language_link': 1.0},
                                    match_method='language_link',
                                    additional_info={'wikipedia_link': True}
                                )
                                
                                # Cache the result
                                self.language_links_cache[cache_key] = match
                                return [match]
            
            # Cache negative result
            self.language_links_cache[cache_key] = None
            return []
            
        except Exception as e:
            logger.warning(f"Language link search failed for {vietnamese_entity}: {e}")
            self.language_links_cache[cache_key] = None
            return []
    
    def _find_similarity_matches(self, vietnamese_entity: str, 
                               entity_type: str = None) -> List[EntityMatch]:
        """Find matches using string similarity algorithms."""
        matches = []
        
        # Generate candidate English names
        candidates = self._generate_english_candidates(vietnamese_entity)
        
        # Search DBPedia for similar entities
        for candidate in candidates:
            similar_entities = self._search_dbpedia_by_similarity(candidate, entity_type)
            
            for entity_uri, entity_label in similar_entities:
                # Calculate similarity scores
                scores = self._calculate_similarity_scores(vietnamese_entity, entity_label)
                
                # Calculate overall confidence
                confidence = self._calculate_confidence(scores)
                
                if confidence >= 0.5:  # Minimum threshold for similarity matches
                    match = EntityMatch(
                        vietnamese_entity=vietnamese_entity,
                        english_entity=entity_label,
                        dbpedia_uri=entity_uri,
                        confidence_score=confidence,
                        similarity_scores=scores,
                        match_method='similarity',
                        additional_info={'candidate': candidate}
                    )
                    matches.append(match)
        
        return matches
    
    def _find_property_based_matches(self, vietnamese_entity: str) -> List[EntityMatch]:
        """Find matches using property-based SPARQL queries."""
        matches = []
        
        try:
            # Extract potential birth/death years, locations, etc.
            # This is a simplified implementation - could be expanded
            
            # Search for entities with similar names
            query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            
            SELECT DISTINCT ?entity ?label WHERE {{
                ?entity rdfs:label ?label .
                FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{vietnamese_entity.split()[0]}")))
                FILTER(LANG(?label) = "en")
            }} LIMIT 20
            """
            
            results = self._execute_sparql_query(query)
            
            for result in results.get('results', {}).get('bindings', []):
                entity_uri = result['entity']['value']
                entity_label = result['label']['value']
                
                # Calculate similarity
                scores = self._calculate_similarity_scores(vietnamese_entity, entity_label)
                confidence = self._calculate_confidence(scores)
                
                if confidence >= 0.4:
                    match = EntityMatch(
                        vietnamese_entity=vietnamese_entity,
                        english_entity=entity_label,
                        dbpedia_uri=entity_uri,
                        confidence_score=confidence,
                        similarity_scores=scores,
                        match_method='property_based',
                        additional_info={'sparql_query': True}
                    )
                    matches.append(match)
            
        except Exception as e:
            logger.warning(f"Property-based search failed for {vietnamese_entity}: {e}")
        
        return matches
    
    def _generate_english_candidates(self, vietnamese_name: str) -> List[str]:
        """Generate potential English name candidates from Vietnamese name."""
        candidates = []
        
        # Original name
        candidates.append(vietnamese_name)
        
        # Romanized version (remove diacritics)
        romanized = unidecode(vietnamese_name)
        if romanized != vietnamese_name:
            candidates.append(romanized)
        
        # Common transformations for Vietnamese names
        transformations = {
            'Nguyễn': 'Nguyen',
            'Trần': 'Tran',
            'Lê': 'Le',
            'Phạm': 'Pham',
            'Huỳnh': 'Huynh',
            'Vũ': 'Vu',
            'Võ': 'Vo',
            'Đặng': 'Dang',
            'Bùi': 'Bui',
            'Đỗ': 'Do',
            'Hồ': 'Ho',
            'Ngô': 'Ngo',
            'Dương': 'Duong',
            'Lý': 'Ly'
        }
        
        transformed = vietnamese_name
        for viet, eng in transformations.items():
            transformed = transformed.replace(viet, eng)
        
        if transformed != vietnamese_name:
            candidates.append(transformed)
        
        # Remove duplicates while preserving order
        unique_candidates = []
        for candidate in candidates:
            if candidate not in unique_candidates:
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def _calculate_similarity_scores(self, text1: str, text2: str) -> Dict[str, float]:
        """Calculate various similarity scores between two strings."""
        # Normalize texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        scores = {}
        
        # Levenshtein distance (normalized)
        max_len = max(len(norm1), len(norm2))
        if max_len > 0:
            scores['levenshtein'] = 1 - (levenshtein_distance(norm1, norm2) / max_len)
        else:
            scores['levenshtein'] = 1.0
        
        # Fuzzy matching scores
        scores['ratio'] = fuzz.ratio(norm1, norm2) / 100.0
        scores['partial_ratio'] = fuzz.partial_ratio(norm1, norm2) / 100.0
        scores['token_sort_ratio'] = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        scores['token_set_ratio'] = fuzz.token_set_ratio(norm1, norm2) / 100.0
        
        # Jaccard similarity (word-based)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if words1 or words2:
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            scores['jaccard'] = intersection / union if union > 0 else 0.0
        else:
            scores['jaccard'] = 1.0
        
        return scores
    
    def _calculate_confidence(self, scores: Dict[str, float]) -> float:
        """Calculate overall confidence score from similarity scores."""
        # Weighted average of different similarity metrics
        weights = {
            'levenshtein': 0.2,
            'ratio': 0.25,
            'partial_ratio': 0.15,
            'token_sort_ratio': 0.2,
            'token_set_ratio': 0.15,
            'jaccard': 0.05
        }
        
        total_weight = 0
        weighted_sum = 0
        
        for metric, score in scores.items():
            if metric in weights:
                weight = weights[metric]
                weighted_sum += score * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return 0.0
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Convert to lowercase
        text = text.lower()
        
        # Remove diacritics
        text = unidecode(text)
        
        # Remove special characters
        text = re.sub(r'[^\w\s]', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text
    
    def _query_dbpedia_by_label(self, label: str) -> Optional[str]:
        """Query DBPedia for entity URI by label."""
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?entity WHERE {{
            ?entity rdfs:label "{label}"@en .
        }} LIMIT 1
        """
        
        try:
            results = self._execute_sparql_query(query)
            bindings = results.get('results', {}).get('bindings', [])
            
            if bindings:
                return bindings[0]['entity']['value']
            
        except Exception as e:
            logger.warning(f"DBPedia label query failed for {label}: {e}")
        
        return None
    
    def _get_dbpedia_uri_from_wikipedia_title(self, wikipedia_title: str) -> Optional[str]:
        """Convert Wikipedia title to DBPedia URI."""
        # DBPedia resource URIs follow the pattern: http://dbpedia.org/resource/Title
        # with spaces replaced by underscores
        encoded_title = wikipedia_title.replace(' ', '_')
        dbpedia_uri = f"http://dbpedia.org/resource/{encoded_title}"
        
        # Verify the entity exists
        if self._verify_dbpedia_entity_exists(dbpedia_uri):
            return dbpedia_uri
        
        return None
    
    def _verify_dbpedia_entity_exists(self, uri: str) -> bool:
        """Verify that a DBPedia entity exists."""
        query = f"""
        ASK WHERE {{
            <{uri}> ?p ?o .
        }}
        """
        
        try:
            results = self._execute_sparql_query(query)
            return results.get('boolean', False)
        except Exception:
            return False
    
    def _search_dbpedia_by_similarity(self, search_term: str, 
                                    entity_type: str = None) -> List[Tuple[str, str]]:
        """Search DBPedia entities by similarity."""
        # Build type filter
        type_filter = ""
        if entity_type:
            type_mappings = {
                'Person': 'dbo:Person',
                'Place': 'dbo:Place',
                'Organization': 'dbo:Organisation'
            }
            if entity_type in type_mappings:
                type_filter = f"?entity a {type_mappings[entity_type]} ."
        
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dbo: <http://dbpedia.org/ontology/>
        
        SELECT DISTINCT ?entity ?label WHERE {{
            ?entity rdfs:label ?label .
            {type_filter}
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{search_term}")))
            FILTER(LANG(?label) = "en")
            FILTER(!CONTAINS(STR(?entity), "vi.dbpedia.org"))
            FILTER(STRSTARTS(STR(?entity), "http://dbpedia.org/resource/"))
        }} LIMIT 10
        """
        
        try:
            results = self._execute_sparql_query(query)
            entities = []
            
            for result in results.get('results', {}).get('bindings', []):
                entity_uri = result['entity']['value']
                entity_label = result['label']['value']
                entities.append((entity_uri, entity_label))
            
            return entities
            
        except Exception as e:
            logger.warning(f"DBPedia similarity search failed for {search_term}: {e}")
            return []
    
    def _execute_sparql_query(self, query: str) -> Dict[str, Any]:
        """Execute SPARQL query with caching."""
        # Check cache
        cache_key = hash(query)
        if cache_key in self.sparql_cache:
            self.linking_stats['cache_hits'] += 1
            return self.sparql_cache[cache_key]
        
        try:
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            
            # Cache results
            self.sparql_cache[cache_key] = results
            self.linking_stats['sparql_queries'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            raise
    
    def _deduplicate_matches(self, matches: List[EntityMatch]) -> List[EntityMatch]:
        """Remove duplicate matches based on DBPedia URI."""
        unique_matches = {}
        
        for match in matches:
            uri = match.dbpedia_uri
            if uri not in unique_matches or match.confidence_score > unique_matches[uri].confidence_score:
                unique_matches[uri] = match
        
        return list(unique_matches.values())
    
    def link_articles_batch(self, articles: List[WikipediaArticle]) -> Dict[str, List[EntityMatch]]:
        """Link a batch of articles to English DBPedia entities."""
        logger.info(f"Linking {len(articles)} articles to English DBPedia")
        
        all_matches = {}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_article = {
                executor.submit(self.find_matching_entities, article.title): article.title
                for article in articles
            }
            
            for future in as_completed(future_to_article):
                article_title = future_to_article[future]
                try:
                    matches = future.result()
                    all_matches[article_title] = matches
                except Exception as e:
                    logger.error(f"Failed to link {article_title}: {e}")
                    all_matches[article_title] = []
        
        return all_matches
    
    def save_linking_results(self, matches: Dict[str, List[EntityMatch]], 
                           output_path: str) -> None:
        """Save entity linking results to JSON file."""
        try:
            # Convert matches to serializable format
            serializable_matches = {}
            for entity, match_list in matches.items():
                serializable_matches[entity] = [
                    {
                        'vietnamese_entity': match.vietnamese_entity,
                        'english_entity': match.english_entity,
                        'dbpedia_uri': match.dbpedia_uri,
                        'confidence_score': match.confidence_score,
                        'similarity_scores': match.similarity_scores,
                        'match_method': match.match_method,
                        'additional_info': match.additional_info
                    }
                    for match in match_list
                ]
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as file:
                json.dump(serializable_matches, file, ensure_ascii=False, indent=2)
            
            logger.info(f"Entity linking results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save linking results: {e}")
            raise
    
    def export_links_to_rdf(self, matches: Dict[str, List[EntityMatch]], 
                           output_path: str, format: str = 'turtle') -> None:
        """Export entity linking results to RDF format."""
        try:
            from rdflib import Graph, Namespace, URIRef, Literal
            from rdflib.namespace import OWL, RDFS, XSD
            from urllib.parse import quote
            
            # Create graph and namespaces
            g = Graph()
            VIRES = Namespace('http://vi.dbpedia.org/resource/')
            DBPEDIA = Namespace('http://dbpedia.org/resource/')
            
            # Bind namespaces
            g.bind('vires', VIRES)
            g.bind('dbpedia', DBPEDIA)
            g.bind('owl', OWL)
            g.bind('rdfs', RDFS)
            
            # Add entity links as RDF triples
            for entity, match_list in matches.items():
                # Create Vietnamese entity URI
                entity_encoded = quote(entity.replace(' ', '_'), safe='')
                vi_uri = VIRES[entity_encoded]
                
                for match in match_list:
                    # Skip self-links (Vietnamese entity linking to itself)
                    if self._is_self_link(entity, match.english_entity, match.dbpedia_uri):
                        continue
                    
                    # Create English DBpedia URI
                    en_entity_encoded = quote(match.english_entity.replace(' ', '_'), safe='')
                    en_uri = DBPEDIA[en_entity_encoded]
                    
                    # Add owl:sameAs relationship (high confidence links)
                    if match.confidence_score >= 0.9:
                        g.add((vi_uri, OWL.sameAs, en_uri))
                    else:
                        # Add rdfs:seeAlso for lower confidence links
                        g.add((vi_uri, RDFS.seeAlso, en_uri))
                    
                    # Add metadata about the link
                    g.add((vi_uri, RDFS.label, Literal(entity, lang='vi')))
                    
                    # Add confidence score as annotation
                    link_uri = URIRef(f"{vi_uri}_link_{hash(match.english_entity)}")
                    g.add((link_uri, URIRef('http://vi.dbpedia.org/property/confidenceScore'), 
                          Literal(match.confidence_score, datatype=XSD.double)))
                    g.add((link_uri, URIRef('http://vi.dbpedia.org/property/matchMethod'), 
                          Literal(match.match_method)))
                    g.add((link_uri, URIRef('http://vi.dbpedia.org/property/linkedEntity'), en_uri))
                    g.add((link_uri, URIRef('http://vi.dbpedia.org/property/sourceEntity'), vi_uri))
            
            # Serialize graph
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            g.serialize(destination=output_path, format=format)
            
            logger.info(f"Entity links exported to RDF: {output_path}")
            logger.info(f"Total triples generated: {len(g)}")
            
        except Exception as e:
            logger.error(f"Failed to export entity links to RDF: {e}")
            raise
    
    def _is_self_link(self, vietnamese_entity: str, english_entity: str, dbpedia_uri: str) -> bool:
        """Check if this is a self-link (Vietnamese entity linking to itself)."""
        # Check if the DBPedia URI contains Vietnamese DBPedia patterns
        vietnamese_patterns = [
            'vi.dbpedia.org',
            '/vi/',
            'vietnamese',
            'viet'
        ]
        
        # Check URI patterns
        for pattern in vietnamese_patterns:
            if pattern in dbpedia_uri.lower():
                logger.warning(f"Skipping self-link: {vietnamese_entity} -> {dbpedia_uri}")
                return True
        
        # Check if the entities are essentially the same
        normalized_vi = self._normalize_text(vietnamese_entity)
        normalized_en = self._normalize_text(english_entity)
        
        # Skip if they're identical after normalization
        if normalized_vi == normalized_en:
            logger.warning(f"Skipping identical entities: {vietnamese_entity} -> {english_entity}")
            return True
        
        # Skip if English entity is just Vietnamese entity with diacritics removed
        import unicodedata
        vietnamese_no_diacritics = ''.join(
            c for c in unicodedata.normalize('NFD', vietnamese_entity)
            if unicodedata.category(c) != 'Mn'
        )
        
        if self._normalize_text(vietnamese_no_diacritics) == normalized_en:
            logger.warning(f"Skipping diacritic-only difference: {vietnamese_entity} -> {english_entity}")
            return True
        
        return False
    
    def get_linking_statistics(self) -> Dict[str, Any]:
        """Get entity linking statistics."""
        stats = self.linking_stats.copy()
        
        if stats['entities_processed'] > 0:
            stats['success_rate'] = (stats['successful_links'] / stats['entities_processed']) * 100
            stats['high_confidence_rate'] = (stats['high_confidence_links'] / stats['entities_processed']) * 100
        
        return stats


def main():
    """Main function for testing entity linking."""
    try:
        linker = EntityLinker()
        
        # Test with sample Vietnamese entities
        test_entities = [
            "Hồ Chí Minh",
            "Hà Nội", 
            "Nguyễn Du",
            "Truyện Kiều"
        ]
        
        for entity in test_entities:
            print(f"\nLinking: {entity}")
            matches = linker.find_matching_entities(entity)
            
            for i, match in enumerate(matches[:3], 1):
                print(f"  {i}. {match.english_entity} ({match.confidence_score:.3f})")
                print(f"     URI: {match.dbpedia_uri}")
                print(f"     Method: {match.match_method}")
        
        # Print statistics
        stats = linker.get_linking_statistics()
        print(f"\nLinking Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
    except Exception as e:
        logger.error(f"Entity linking test failed: {e}")
        raise


if __name__ == "__main__":
    main()