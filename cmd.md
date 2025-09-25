```sparql
# Show some entity links
  PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT * WHERE {
    GRAPH <http://vi.dbpedia.org/links/> {
      ?vi_entity owl:sameAs ?en_entity .
    }
  } LIMIT 10
```
