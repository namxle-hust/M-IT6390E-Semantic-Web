# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vietnamese DBPedia is a comprehensive semantic web knowledge base for Vietnamese entities with GraphDB integration, built for the M-IT6390E Semantic Web course. The project includes Wikipedia data collection, RDF transformation, entity linking, and full-featured web and CLI interfaces.

## Key Components

1. **Vietnamese Ontology** (`src/ontology/`) - Comprehensive ontology with Vietnamese-specific classes and properties
2. **Wikipedia Collector** (`src/collectors/`) - Automated Vietnamese Wikipedia data extraction
3. **RDF Transformer** (`src/transformers/`) - Convert Wikipedia data to RDF using the Vietnamese ontology
4. **GraphDB Integration** (`src/graphdb/`) - Complete GraphDB repository management and data loading
5. **Entity Linking** (`src/entity_linking/`) - Link Vietnamese entities to English DBPedia
6. **SPARQL Interface** (`src/interfaces/`) - Advanced query capabilities with Vietnamese text search
7. **Web Interface** - Flask-based web application for querying and browsing
8. **CLI Tools** (`cli.py`) - Comprehensive command-line interface

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .

# Check system status
python cli.py status
```

### GraphDB Operations
```bash
# Set up GraphDB repository
python cli.py graphdb setup --repository vietnamese_dbpedia

# Load RDF data
python cli.py graphdb load --input data/rdf --clear
```

### Data Pipeline
```bash
# Create Vietnamese ontology
python cli.py ontology create --output-dir ontology

# Collect Wikipedia articles
python cli.py collect wikipedia --articles sample

# Transform to RDF
python cli.py transform rdf --input data/raw/articles.json

# Link entities to English DBPedia
python cli.py link entities --threshold 0.8
```

### Query and Interface
```bash
# Execute SPARQL queries
python cli.py query execute --query "SELECT * WHERE { ?s ?p ?o } LIMIT 5"

# Start web interface
python cli.py web --host 0.0.0.0 --port 5000
```

### Testing
```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=html
```

## Architecture

The project follows a modular architecture with clear separation of concerns:

```
Data Collection → RDF Transformation → GraphDB Storage → Query Interface
       ↓                   ↓                 ↓              ↓
  Wikipedia API    Vietnamese Ontology   GraphDB       SPARQL/Web
   (Collector)       (Transformer)      (Manager)      (Interface)
```

### Key Design Patterns

- **Factory Pattern**: Used in ontology creation for different entity types
- **Repository Pattern**: GraphDB operations abstracted through managers
- **Pipeline Pattern**: Data flows through collection → transformation → loading stages
- **Caching**: Implemented in SPARQL interface and entity linking for performance

## Configuration

Configuration files are in the `config/` directory:
- `graphdb.yaml` - GraphDB connection and repository settings
- `ontology.yaml` - Vietnamese ontology class and property definitions
- `wikipedia.yaml` - Wikipedia API and collection parameters
- `logging.yaml` - Logging configuration

Environment variables should be set in `.env` (copy from `.env.example`).

## Testing Strategy

Tests are organized by component in the `tests/` directory:
- Unit tests for individual modules
- Integration tests for component interactions
- End-to-end tests for complete workflows

Use `pytest` for running tests with rich output and coverage reporting.

## Common Issues and Solutions

1. **GraphDB Connection**: Ensure GraphDB server is running on localhost:7200
2. **Vietnamese Text**: All text handling uses UTF-8 encoding
3. **Large Datasets**: Use batch processing for loading large amounts of RDF data
4. **Entity Linking**: Confidence thresholds can be adjusted based on data quality needs

## Performance Considerations

- GraphDB is optimized for Vietnamese text with Lucene full-text indexing
- SPARQL queries are cached with configurable TTL
- Batch processing is used for data loading and entity linking
- Connection pooling is implemented for database operations

## Deployment

The project supports both local and Docker deployment:

### Local Development
```bash
python cli.py web --debug
```

### Docker Deployment
```bash
docker-compose up -d
```

This starts GraphDB, the web application, and nginx reverse proxy.

## Notable Vietnamese-Specific Features

- Proper handling of Vietnamese diacritics in URIs and text search
- Vietnamese Wikipedia infobox template mappings
- Bilingual labels (Vietnamese and English) throughout the ontology
- Cross-language entity linking with English DBPedia
- Vietnamese text normalization for similarity matching