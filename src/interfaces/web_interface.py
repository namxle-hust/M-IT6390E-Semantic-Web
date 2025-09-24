"""
Web Interface for Vietnamese DBPedia

This module provides a Flask-based web interface for querying and browsing
the Vietnamese DBPedia knowledge base with Vietnamese text search capabilities.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
from pathlib import Path

from src.graphdb.graphdb_manager import GraphDBManager
from src.interfaces.sparql_interface import SPARQLInterface, QueryResult

logger = logging.getLogger(__name__)

app = Flask(__name__, 
           template_folder='../../web/templates',
           static_folder='../../web/static')
CORS(app)

# Global variables for application components
graphdb_manager = None
sparql_interface = None


def initialize_app():
    """Initialize the web application with required components."""
    global graphdb_manager, sparql_interface
    
    try:
        graphdb_manager = GraphDBManager()
        sparql_interface = SPARQLInterface(graphdb_manager)
        logger.info("Web application initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize web application: {e}")
        raise


@app.route('/')
def index():
    """Main page with search interface."""
    try:
        # Get basic statistics
        stats_result = sparql_interface.get_ontology_statistics()
        stats = {}
        
        if stats_result.success and stats_result.results.get('results', {}).get('bindings'):
            binding = stats_result.results['results']['bindings'][0]
            stats = {
                'total_entities': binding.get('total_entities', {}).get('value', '0'),
                'total_classes': binding.get('total_classes', {}).get('value', '0'),
                'total_properties': binding.get('total_properties', {}).get('value', '0'),
                'total_triples': binding.get('total_triples', {}).get('value', '0')
            }
        
        return render_template('index.html', stats=stats)
    except Exception as e:
        logger.error(f"Index page error: {e}")
        return render_template('error.html', error="Failed to load main page")


@app.route('/search')
def search():
    """Search interface page."""
    return render_template('search.html')


@app.route('/sparql')
def sparql_editor():
    """SPARQL query editor page."""
    sample_queries = sparql_interface.sample_queries if sparql_interface else {}
    return render_template('sparql.html', sample_queries=sample_queries)


@app.route('/browse')
def browse():
    """Entity browsing interface."""
    return render_template('browse.html')


@app.route('/api/search')
def api_search():
    """API endpoint for entity search."""
    try:
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 20)), 100)
        search_type = request.args.get('type', 'name')  # name, fulltext
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        if search_type == 'fulltext':
            result = sparql_interface.full_text_search(query, limit)
        else:
            result = sparql_interface.search_entities(query, limit)
        
        if result.success:
            # Process results for web display
            entities = []
            bindings = result.results.get('results', {}).get('bindings', [])
            
            for binding in bindings:
                entity = {
                    'uri': binding.get('entity', {}).get('value', ''),
                    'label': binding.get('label', {}).get('value', ''),
                    'type': binding.get('type', {}).get('value', ''),
                    'score': binding.get('score', {}).get('value', '1.0')
                }
                entities.append(entity)
            
            return jsonify({
                'success': True,
                'entities': entities,
                'count': len(entities),
                'execution_time': result.execution_time,
                'query_type': search_type
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message
            }), 500
            
    except Exception as e:
        logger.error(f"Search API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/entity/<path:entity_uri>')
def api_entity_details(entity_uri: str):
    """API endpoint for entity details."""
    try:
        # Decode URI if needed
        if not entity_uri.startswith('http'):
            entity_uri = f"http://vi.dbpedia.org/resource/{entity_uri}"
        
        result = sparql_interface.get_entity_details(entity_uri)
        
        if result.success:
            # Process properties for web display
            properties = []
            bindings = result.results.get('results', {}).get('bindings', [])
            
            for binding in bindings:
                prop = {
                    'property': binding.get('property', {}).get('value', ''),
                    'value': binding.get('value', {}).get('value', ''),
                    'value_type': binding.get('value', {}).get('type', 'literal')
                }
                properties.append(prop)
            
            return jsonify({
                'success': True,
                'entity_uri': entity_uri,
                'properties': properties,
                'count': len(properties),
                'execution_time': result.execution_time
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message
            }), 500
            
    except Exception as e:
        logger.error(f"Entity details API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sparql', methods=['POST'])
def api_sparql_query():
    """API endpoint for SPARQL queries."""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        endpoint = data.get('endpoint', 'local')
        format_type = data.get('format', 'json')
        
        if not query:
            return jsonify({'error': 'SPARQL query is required'}), 400
        
        result = sparql_interface.execute_query(query, endpoint)
        
        if result.success:
            if format_type == 'csv':
                csv_content = sparql_interface.export_results(result, 'csv')
                return jsonify({
                    'success': True,
                    'data': csv_content,
                    'format': 'csv',
                    'execution_time': result.execution_time,
                    'result_count': result.result_count
                })
            else:
                return jsonify({
                    'success': True,
                    'results': result.results,
                    'execution_time': result.execution_time,
                    'result_count': result.result_count,
                    'cached': result.cached
                })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message,
                'execution_time': result.execution_time
            }), 500
            
    except Exception as e:
        logger.error(f"SPARQL API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/federated')
def api_federated_query():
    """API endpoint for federated queries."""
    try:
        entity = request.args.get('entity', '').strip()
        result = sparql_interface.execute_federated_query(entity)
        
        if result.success:
            # Process federated results
            links = []
            bindings = result.results.get('results', {}).get('bindings', [])
            
            for binding in bindings:
                link = {
                    'vietnamese_entity': binding.get('viEntity', {}).get('value', ''),
                    'english_entity': binding.get('enEntity', {}).get('value', ''),
                    'vietnamese_label': binding.get('viLabel', {}).get('value', ''),
                    'english_label': binding.get('enLabel', {}).get('value', '')
                }
                links.append(link)
            
            return jsonify({
                'success': True,
                'links': links,
                'count': len(links),
                'execution_time': result.execution_time
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error_message
            }), 500
            
    except Exception as e:
        logger.error(f"Federated query API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics')
def api_statistics():
    """API endpoint for system statistics."""
    try:
        # Get ontology statistics
        ontology_result = sparql_interface.get_ontology_statistics()
        ontology_stats = {}
        
        if ontology_result.success and ontology_result.results.get('results', {}).get('bindings'):
            binding = ontology_result.results['results']['bindings'][0]
            ontology_stats = {
                'total_entities': int(binding.get('total_entities', {}).get('value', '0')),
                'total_classes': int(binding.get('total_classes', {}).get('value', '0')),
                'total_properties': int(binding.get('total_properties', {}).get('value', '0')),
                'total_triples': int(binding.get('total_triples', {}).get('value', '0'))
            }
        
        # Get query statistics
        query_stats = sparql_interface.get_query_statistics()
        
        # Get repository size
        repo_size = graphdb_manager.get_repository_size(sparql_interface.repository_id) or 0
        
        return jsonify({
            'success': True,
            'ontology': ontology_stats,
            'queries': query_stats,
            'repository_size': repo_size,
            'timestamp': int(os.path.getctime(__file__))
        })
        
    except Exception as e:
        logger.error(f"Statistics API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export')
def api_export():
    """API endpoint for data export."""
    try:
        format_type = request.args.get('format', 'json')
        query = request.args.get('query', '')
        
        if not query:
            # Default query to export all data (limited)
            query = """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT ?subject ?predicate ?object WHERE {
                    ?subject ?predicate ?object .
                } LIMIT 1000
            """
        
        result = sparql_interface.execute_query(query)
        
        if result.success:
            if format_type in ['csv', 'tsv']:
                content = sparql_interface.export_results(result, format_type)
                filename = f"vietnamese_dbpedia_export.{format_type}"
                
                # Save to temporary file
                temp_path = f"/tmp/{filename}"
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return send_file(
                    temp_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype=f'text/{format_type}'
                )
            else:
                return jsonify(result.results)
        else:
            return jsonify({'error': result.error_message}), 500
            
    except Exception as e:
        logger.error(f"Export API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/samples')
def api_sample_queries():
    """API endpoint to get sample queries."""
    try:
        return jsonify({
            'success': True,
            'queries': sparql_interface.sample_queries
        })
    except Exception as e:
        logger.error(f"Sample queries API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """404 error handler."""
    return render_template('error.html', 
                         error="Page not found",
                         error_code=404), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler."""
    return render_template('error.html',
                         error="Internal server error",
                         error_code=500), 500


def create_templates():
    """Create basic HTML templates for the web interface."""
    template_dir = Path("web/templates")
    template_dir.mkdir(parents=True, exist_ok=True)
    
    # Base template
    base_template = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Vietnamese DBPedia{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">Vietnamese DBPedia</a>
            <div class="navbar-nav">
                <a class="nav-link" href="{{ url_for('index') }}">Home</a>
                <a class="nav-link" href="{{ url_for('search') }}">Search</a>
                <a class="nav-link" href="{{ url_for('sparql_editor') }}">SPARQL</a>
                <a class="nav-link" href="{{ url_for('browse') }}">Browse</a>
            </div>
        </div>
    </nav>
    
    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>"""
    
    # Index template
    index_template = """{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <div class="jumbotron bg-light p-5 rounded">
            <h1 class="display-4">Vietnamese DBPedia</h1>
            <p class="lead">Explore Vietnamese knowledge through semantic web technologies</p>
            <hr class="my-4">
            <p>Search and browse Vietnamese entities, their properties, and relationships.</p>
        </div>
        
        <div class="search-section mt-4">
            <h3>Quick Search</h3>
            <div class="input-group mb-3">
                <input type="text" class="form-control" id="quickSearch" placeholder="Search Vietnamese entities...">
                <button class="btn btn-primary" type="button" onclick="performQuickSearch()">Search</button>
            </div>
        </div>
        
        <div id="searchResults" class="mt-4"></div>
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5>Knowledge Base Statistics</h5>
            </div>
            <div class="card-body">
                <ul class="list-unstyled">
                    <li><strong>Entities:</strong> {{ stats.total_entities or 'N/A' }}</li>
                    <li><strong>Classes:</strong> {{ stats.total_classes or 'N/A' }}</li>
                    <li><strong>Properties:</strong> {{ stats.total_properties or 'N/A' }}</li>
                    <li><strong>Triples:</strong> {{ stats.total_triples or 'N/A' }}</li>
                </ul>
            </div>
        </div>
        
        <div class="card mt-3">
            <div class="card-header">
                <h5>Quick Links</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="{{ url_for('search') }}" class="btn btn-outline-primary">Advanced Search</a>
                    <a href="{{ url_for('sparql_editor') }}" class="btn btn-outline-secondary">SPARQL Editor</a>
                    <a href="{{ url_for('browse') }}" class="btn btn-outline-info">Browse Entities</a>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function performQuickSearch() {
    const query = document.getElementById('quickSearch').value.trim();
    if (query) {
        window.location.href = `/search?q=${encodeURIComponent(query)}`;
    }
}

document.getElementById('quickSearch').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        performQuickSearch();
    }
});
</script>
{% endblock %}"""
    
    # Error template
    error_template = """{% extends "base.html" %}

{% block title %}Error - Vietnamese DBPedia{% endblock %}

{% block content %}
<div class="alert alert-danger" role="alert">
    <h4 class="alert-heading">Error {{ error_code or '' }}</h4>
    <p>{{ error }}</p>
    <hr>
    <p class="mb-0">
        <a href="{{ url_for('index') }}" class="btn btn-primary">Return to Home</a>
    </p>
</div>
{% endblock %}"""
    
    # Write templates
    with open(template_dir / "base.html", "w", encoding="utf-8") as f:
        f.write(base_template)
    
    with open(template_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_template)
    
    with open(template_dir / "error.html", "w", encoding="utf-8") as f:
        f.write(error_template)
    
    # Create static directory and basic CSS
    static_dir = Path("web/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "css").mkdir(exist_ok=True)
    (static_dir / "js").mkdir(exist_ok=True)
    
    # Basic CSS
    css_content = """
body {
    background-color: #f8f9fa;
}

.jumbotron {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.card {
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
}

.search-results {
    margin-top: 20px;
}

.entity-card {
    border-left: 4px solid #007bff;
    margin-bottom: 10px;
}

.property-list {
    max-height: 400px;
    overflow-y: auto;
}

.sparql-editor {
    height: 300px;
}

.loading {
    text-align: center;
    padding: 20px;
}
"""
    
    with open(static_dir / "css" / "style.css", "w", encoding="utf-8") as f:
        f.write(css_content)
    
    # Basic JavaScript
    js_content = """
// Vietnamese DBPedia Web Interface JavaScript

class VietnameseDBPediaAPI {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }
    
    async search(query, type = 'name', limit = 20) {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&type=${type}&limit=${limit}`);
        return response.json();
    }
    
    async getEntity(entityUri) {
        const response = await fetch(`/api/entity/${encodeURIComponent(entityUri)}`);
        return response.json();
    }
    
    async executeSPARQL(query, endpoint = 'local') {
        const response = await fetch('/api/sparql', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query, endpoint })
        });
        return response.json();
    }
}

const api = new VietnameseDBPediaAPI();

// Utility functions
function showLoading(elementId) {
    document.getElementById(elementId).innerHTML = '<div class="loading"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
}

function formatURI(uri) {
    return uri.replace('http://vi.dbpedia.org/resource/', '').replace('http://vi.dbpedia.org/ontology/', '');
}

function createEntityCard(entity) {
    return `
        <div class="card entity-card mb-2">
            <div class="card-body">
                <h5 class="card-title">${entity.label || formatURI(entity.uri)}</h5>
                <p class="card-text">
                    <small class="text-muted">Type: ${formatURI(entity.type || '')}</small><br>
                    <small class="text-muted">URI: ${entity.uri}</small>
                </p>
                <a href="#" class="btn btn-sm btn-primary" onclick="viewEntity('${entity.uri}')">View Details</a>
            </div>
        </div>
    `;
}

function viewEntity(entityUri) {
    // Implementation would go here
    console.log('Viewing entity:', entityUri);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Vietnamese DBPedia web interface loaded');
});
"""
    
    with open(static_dir / "js" / "app.js", "w", encoding="utf-8") as f:
        f.write(js_content)


def run_web_interface(host='0.0.0.0', port=5000, debug=False):
    """Run the web interface."""
    try:
        # Create templates if they don't exist
        create_templates()
        
        # Initialize application
        initialize_app()
        
        logger.info(f"Starting Vietnamese DBPedia web interface on {host}:{port}")
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"Failed to start web interface: {e}")
        raise


if __name__ == "__main__":
    run_web_interface(debug=True)