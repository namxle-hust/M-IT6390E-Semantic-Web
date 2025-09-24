Create a complete Vietnamese DBPedia project with GraphDB integration and the following requirements:

## PROJECT STRUCTURE
Create a well-organized Python project with these components:
- `src/` directory with main modules
- `data/` directory for storing RDF files and raw Wikipedia data
- `ontology/` directory for ontology files
- `config/` directory for configuration files (including GraphDB settings)
- `graphdb/` directory for GraphDB repository configurations
- `queries/` directory for sample SPARQL queries
- `tests/` directory for unit tests
- `docker/` directory for GraphDB Docker setup (optional)
- `requirements.txt` with all dependencies
- `README.md` with complete setup and usage instructions
- `setup.py` for package installation

## CORE REQUIREMENTS

### 1. ONTOLOGY DESIGN
Create a comprehensive Vietnamese ontology using RDFLib:
- Define Vietnamese-specific classes: Person (Người), Place (Địa điểm), Organization (Tổ chức), Event (Sự kiện), Work (Tác phẩm)
- Include detailed subclasses: PoliticalFigure, Artist, Scientist, Province, District, Ward, University, Company, HistoricalEvent, CulturalEvent, LiteraryWork, MusicalWork, Film
- Define comprehensive properties: birthDate, birthPlace, locatedIn, memberOf, childOf, vietnameseTitle, dynastyPeriod, lunarDate, administrativeCenter, borders
- Support both Vietnamese (@vi) and English (@en) labels
- Include rdfs:comment descriptions in Vietnamese
- Export ontology as OWL/Turtle files
- Create mapping to existing DBPedia ontology classes using owl:equivalentClass
- Generate ontology documentation

### 2. WIKIPEDIA DATA COLLECTION
Build a robust Wikipedia scraper for Vietnamese articles:
- Use Wikipedia API (vi.wikipedia.org) to fetch 100+ Vietnamese articles
- Target articles with rich infoboxes (people, places, organizations, events, works)
- Extract infobox data, categories, abstracts, and basic article content
- Handle Vietnamese text encoding (UTF-8) properly
- Store raw data in structured JSON format
- Include rate limiting and error handling
- Support batch processing of articles
- Target specific article categories: Vietnamese historical figures, provinces/cities, universities, cultural sites, historical events, literature, music

### 3. RDF DATA TRANSFORMATION
Create comprehensive data transformation pipeline:
- Parse Vietnamese Wikipedia infoboxes and map to ontology classes
- Convert Vietnamese infobox templates ({{Thông tin nhân vật}}, {{Thông tin địa điểm}}, etc.) to RDF triples
- Generate unique URIs for Vietnamese entities (http://vi.dbpedia.org/resource/...)
- Handle Vietnamese language tags (@vi) for all Vietnamese literals
- Create proper RDF/Turtle output files
- Validate RDF data against ontology constraints
- Support incremental data updates
- Generate statistics about transformed data

### 4. GRAPHDB INTEGRATION
Implement complete GraphDB local setup and integration:
- Create GraphDB repository configuration files
- Implement GraphDB connection management class
- Build data loading pipeline to GraphDB repository
- Create repository backup/restore functionality
- Implement GraphDB SPARQL query interface
- Support GraphDB Workbench integration
- Include GraphDB inference rule configuration
- Add GraphDB performance monitoring
- Create GraphDB repository templates for different use cases

### 5. ENTITY LINKING TO ENGLISH DBPEDIA
Implement comprehensive entity matching system:
- Find cross-language links between Vietnamese and English Wikipedia
- Create owl:sameAs links to English DBPedia entities (http://dbpedia.org/resource/...)
- Use multiple string similarity algorithms (Levenshtein, Jaccard, etc.)
- Query English DBPedia SPARQL endpoint for verification
- Implement fuzzy matching for Vietnamese names
- Store and validate mapping results
- Create confidence scoring for entity matches
- Support manual validation of uncertain matches

### 6. LOCAL GRAPHDB SETUP & MANAGEMENT
Create complete GraphDB local deployment:
- GraphDB installation and configuration scripts
- Repository creation and management
- Data loading and indexing optimization
- GraphDB server startup/shutdown scripts
- Repository backup and restore procedures
- Performance tuning configurations
- Memory and storage optimization
- GraphDB Workbench setup instructions
- Docker deployment option (optional)

### 7. ADVANCED SPARQL INTERFACE
Set up comprehensive SPARQL query system:
- GraphDB SPARQL endpoint integration
- Vietnamese text search capabilities (full-text indexing)
- Complex federated queries with English DBPedia
- Query result caching and optimization
- Web-based query interface (Flask app)
- Command-line query tool
- Batch query processing
- Query result export (JSON, CSV, RDF)
- Vietnamese language query examples

## TECHNICAL SPECIFICATIONS

### Dependencies to include:
- rdflib (RDF manipulation)
- requests (API calls)
- beautifulsoup4 (HTML parsing)
- pandas (data processing)
- flask (web interface)
- SPARQLWrapper (SPARQL queries)
- langdetect (language detection)
- python-Levenshtein (string similarity)
- py2neo (graph database operations)
- python-dotenv (environment configuration)
- click (CLI interface)
- tqdm (progress bars)
- loguru (advanced logging)

### GraphDB-specific requirements:
- HTTP client for GraphDB REST API
- Repository management via GraphDB API
- RDF data upload via GraphDB REST API
- SPARQL query execution via GraphDB
- GraphDB Workbench integration
- Repository configuration templates

### Key Classes/Modules to implement:
1. `VietnamOntology` - ontology management and validation
2. `WikipediaCollector` - Wikipedia data extraction with rate limiting
3. `RDFTransformer` - data transformation to RDF with validation
4. `EntityLinker` - linking to English DBPedia with confidence scoring
5. `GraphDBManager` - GraphDB connection and repository management
6. `GraphDBLoader` - data loading and indexing in GraphDB
7. `SPARQLInterface` - GraphDB query interface with caching
8. `DataValidator` - RDF and ontology validation
9. `WebInterface` - Flask-based web application
10. `CLIInterface` - command-line interface

### GraphDB Configuration:
- Repository configuration files (TTL format)
- Inference rules and reasoning configurations
- Full-text indexing setup for Vietnamese text
- Performance and memory settings
- Backup and restore procedures
- User access control (optional)

### Configuration files needed:
- `config/graphdb.yaml` - GraphDB connection settings
- `config/wikipedia.yaml` - Wikipedia API configuration  
- `config/ontology.yaml` - Ontology namespace and URI patterns
- `config/logging.yaml` - Logging configuration
- `.env` - Environment variables

### Sample Vietnamese Wikipedia articles to target:
**People:** Hồ Chí Minh, Nguyễn Trãi, Võ Nguyên Giáp
**Places:** Hà Nội, Thành phố Hồ Chí Minh, Huế, Hạ Long
**Organizations:** Đại học Quốc gia Hà Nội, Đại học Bách khoa Hà Nội
**Events:** Chiến thắng Điện Biên Phủ, Cách mạng tháng Tám
**Works:** Truyện Kiều, Số đỏ, Dế Mèn phiêu lưu ký

### GraphDB Setup Requirements:
- Local GraphDB installation guide
- Repository creation scripts
- Data loading optimization
- Query performance tuning
- Workbench configuration
- Backup/restore procedures

## DELIVERABLES
The code should be production-ready with:
- Complete working implementation with GraphDB integration
- Comprehensive error handling and logging
- Configuration files for all components
- GraphDB repository setup and management
- Sample data and Vietnamese SPARQL queries
- Web interface for querying and browsing
- Command-line tools for all operations
- Docker deployment option
- Complete documentation and README with setup instructions
- Unit and integration tests
- Performance benchmarking tools
- Data quality validation reports

## ADDITIONAL FEATURES
Include these advanced features:
- Vietnamese text search and indexing in GraphDB
- Cross-language query capabilities
- Data quality metrics and reporting
- Automated ontology alignment with DBPedia
- RESTful API for external access
- Data export in multiple formats (JSON-LD, N-Triples, Turtle)
- Query result visualization
- Entity relationship exploration interface

Make this a complete, production-ready project that demonstrates all requirements with GraphDB as the primary triplestore, including local deployment, data loading, querying, and management capabilities. Include comprehensive documentation for setup, usage, and maintenance.