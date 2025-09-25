# Vietnamese DBPedia - Test Queries

This directory contains comprehensive SPARQL queries for testing all aspects of the Vietnamese DBPedia system.

## 📁 Query Files

### 1. **01_ontology_tests.sparql**
Tests the Vietnamese ontology structure and metadata:
- Class definitions and labels (Vietnamese/English)
- Property domains and ranges  
- Class hierarchy and relationships
- Ontology metadata and imports
- Statistics on classes and properties

### 2. **02_data_integrity_tests.sparql**
Validates Vietnamese entity data quality:
- Entity counts by type
- Vietnamese labels and language tags
- People with birth/death information
- Places with location data
- Organizations and their types
- Data quality checks (missing labels, invalid dates)
- Property usage statistics
- Entities with multiple types
- Circular reference detection

### 3. **03_entity_linking_tests.sparql**
Tests cross-language entity linking:
- Link counts by type (owl:sameAs vs rdfs:seeAlso)
- High-confidence and low-confidence links
- Link metadata (confidence scores, methods)
- Linking statistics by method
- Entities with multiple English matches
- Vietnamese entities without links
- Link quality assessment
- Cross-language consistency checks
- Entity link coverage by type

### 4. **04_performance_tests.sparql**
System performance and scalability tests:
- Repository size statistics
- Graph/context distribution
- Large result set performance
- Complex join operations
- Full-text search (if Lucene enabled)
- Property path performance
- OPTIONAL clause performance
- Aggregation operations
- Cross-graph joins
- Memory usage estimation

### 5. **05_federated_queries.sparql**
Cross-language federated queries with English DBPedia:
- Basic Vietnamese-English entity matching
- Birth information comparison
- Geographic data with coordinates
- Common categories across languages
- Data enrichment opportunities
- Cross-language relationship discovery
- Historical timeline comparison
- Cultural works with awards
- Population data comparison
- Educational institutions
- Connectivity tests
- Link quality for federated queries

## 🚀 How to Run Tests

### Using the CLI
```bash
# Execute a specific query file
python cli.py query execute --file queries/tests/01_ontology_tests.sparql --format table

# Execute individual queries (copy from files)
python cli.py query execute --query "SELECT * WHERE { ?s ?p ?o } LIMIT 5" --format json

# Show query execution statistics
python cli.py query execute --file queries/tests/04_performance_tests.sparql --format table --stats
```

### Using GraphDB Workbench
1. Open GraphDB Workbench at `http://localhost:7200`
2. Select your repository (`vietnamese-dbpedia`)
3. Go to SPARQL tab
4. Copy and paste queries from the test files
5. Execute and analyze results

### Using Python/RDFLib
```python
from src.interfaces.sparql_interface import SPARQLInterface

sparql = SPARQLInterface()

# Load and execute query file
with open('queries/tests/01_ontology_tests.sparql', 'r') as f:
    queries = f.read().split('\n\n# Query')
    
for query in queries:
    if query.strip():
        results = sparql.execute_query(query)
        print(results)
```

## 📊 Expected Results

### Healthy System Indicators
- **Ontology**: 15+ classes, 30+ properties, proper Vietnamese/English labels
- **Data**: 1000+ entities, proper type distribution, <5% missing labels
- **Entity Links**: 500+ links, 60%+ coverage, >85% accuracy on high-confidence
- **Performance**: <1s for simple queries, <5s for complex joins

### Common Issues to Check
- **Missing Labels**: Entities without rdfs:label
- **Invalid Dates**: Malformed date literals
- **Broken Links**: Entity links to non-existent English entities  
- **Type Inconsistencies**: Entities with incompatible types
- **Performance Degradation**: Slow queries indicating indexing issues

## 🔧 Customization

### Adding New Test Queries
1. Create queries following the existing pattern
2. Include comments explaining what each query tests
3. Use appropriate LIMIT clauses for performance
4. Test both positive and negative cases

### Modifying for Your Data
- Update entity URIs and namespaces if different
- Adjust confidence thresholds in entity linking tests
- Modify expected counts based on your dataset size
- Add domain-specific test cases

### Performance Tuning
- Increase/decrease LIMIT values based on data size
- Add TIMEOUT clauses for long-running queries
- Use EXPLAIN PLAN for query optimization
- Monitor memory usage during complex queries

## 📈 Monitoring & Alerting

### Key Metrics to Track
```sparql
# Data growth over time
SELECT (COUNT(?entity) AS ?totalEntities) WHERE {
  ?entity rdfs:label ?label .
  FILTER(STRSTARTS(STR(?entity), "http://vi.dbpedia.org/resource/"))
}

# Link quality trends
SELECT ?method (AVG(?confidence) AS ?avgConfidence) WHERE {
  ?link vidbp:matchMethod ?method ;
        vidbp:confidenceScore ?confidence .
} GROUP BY ?method

# Query performance benchmarks
SELECT ?queryType ?avgTime WHERE {
  # Your performance tracking implementation
}
```

### Automated Testing
Set up regular execution of these test queries to:
- Detect data quality regressions
- Monitor system performance
- Validate new data loads
- Ensure entity linking accuracy

## 🎯 Quality Gates

### Before Production Deployment
- [ ] All ontology tests pass
- [ ] <5% data integrity issues  
- [ ] >80% entity linking coverage
- [ ] All performance benchmarks within thresholds
- [ ] Federated queries return expected results

### Regular Health Checks
- [ ] Weekly data integrity scans
- [ ] Monthly performance benchmarks
- [ ] Quarterly entity linking quality reviews
- [ ] Annual comprehensive system validation

These test queries provide comprehensive coverage of your Vietnamese DBPedia system, ensuring quality, performance, and functionality across all components.