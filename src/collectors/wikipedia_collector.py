"""
Wikipedia Data Collection Module

This module provides comprehensive Wikipedia data extraction capabilities
for Vietnamese articles with advanced rate limiting and error handling.
"""

import requests
import time
import json
import yaml
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup
import re
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading

logger = logging.getLogger(__name__)


@dataclass
class WikipediaArticle:
    """Data structure for Wikipedia article information."""

    title: str
    page_id: int
    url: str
    abstract: str
    content: str
    infobox: Dict[str, Any]
    categories: List[str]
    templates: List[str]
    language: str = "vi"
    last_modified: Optional[str] = None
    revision_id: Optional[int] = None


class RateLimiter:
    """Thread-safe rate limiter for API requests."""

    def __init__(self, requests_per_second: float = 1.0, burst_limit: int = 5):
        self.requests_per_second = requests_per_second
        self.burst_limit = burst_limit
        self.tokens = burst_limit
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        """Acquire a token for making a request."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(
                self.burst_limit, self.tokens + elapsed * self.requests_per_second
            )
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
            else:
                # Wait until we have a token
                wait_time = (1 - self.tokens) / self.requests_per_second
                time.sleep(wait_time)
                self.tokens = 0


class WikipediaCollector:
    """Advanced Wikipedia data collector with comprehensive extraction capabilities."""

    def __init__(self, config_path: str = "config/wikipedia.yaml"):
        self.config_path = config_path
        self.session = requests.Session()
        self.rate_limiter = None
        self.collected_articles: Dict[str, WikipediaArticle] = {}
        self.failed_articles: Set[str] = set()

        self._load_config()
        self._setup_session()
        self._setup_rate_limiter()

    def _load_config(self) -> None:
        """Load Wikipedia collector configuration."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                self.config = config["wikipedia"]
                self.api_config = config["api"]
                self.extraction_config = config["extraction"]
                self.target_categories = config["target_categories"]
                self.sample_articles = config["sample_articles"]
                logger.info("Wikipedia collector configuration loaded")
        except Exception as e:
            logger.error(f"Failed to load Wikipedia config: {e}")
            raise

    def _setup_session(self) -> None:
        """Set up HTTP session with proper headers."""
        self.session.headers.update(
            {
                "User-Agent": self.config["user_agent"],
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
        )

        # Set timeout
        self.session.timeout = self.api_config["timeout"]
        logger.info("HTTP session configured")

    def _setup_rate_limiter(self) -> None:
        """Set up rate limiter based on configuration."""
        rate_config = self.config["rate_limit"]
        self.rate_limiter = RateLimiter(
            requests_per_second=rate_config["requests_per_second"],
            burst_limit=rate_config["burst_limit"],
        )
        logger.info("Rate limiter configured")

    def _make_api_request(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make rate-limited API request to Wikipedia."""
        self.rate_limiter.acquire()

        # Add default parameters
        default_params = {
            "action": self.api_config["action"],
            "format": self.api_config["format"],
        }
        params.update(default_params)

        max_retries = self.api_config["max_retries"]
        backoff_factor = self.api_config["backoff_factor"]

        for attempt in range(max_retries):
            try:
                response = self.session.get(self.config["base_url"], params=params)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning(f"API request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = backoff_factor**attempt
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"All API request attempts failed for params: {params}"
                    )
                    return None

        return None

    def get_article_by_title(self, title: str) -> Optional[WikipediaArticle]:
        """Get Wikipedia article by title."""
        if title in self.collected_articles:
            return self.collected_articles[title]

        logger.info(f"Fetching article: {title}")

        # Get basic article information
        params = {
            "prop": "info|extracts|categories|templates|revisions",
            "titles": title,
            "exintro": True,
            "explaintext": True,
            "exsectionformat": "plain",
            "cllimit": 500,
            "tllimit": 500,
            "rvprop": "timestamp|ids",
            "rvlimit": 1,
        }

        response = self._make_api_request(params)
        if not response or "query" not in response:
            logger.error(f"Failed to fetch basic info for: {title}")
            self.failed_articles.add(title)
            return None

        pages = response["query"].get("pages", {})
        if not pages:
            logger.warning(f"No pages found for: {title}")
            return None

        # Get the first (and should be only) page
        page_data = next(iter(pages.values()))

        if "missing" in page_data:
            logger.warning(f"Article not found: {title}")
            self.failed_articles.add(title)
            return None

        # Extract basic information
        page_id = page_data.get("pageid", 0)
        page_title = page_data.get("title", title)
        abstract = page_data.get("extract", "")
        categories = [cat["title"] for cat in page_data.get("categories", [])]
        templates = [tpl["title"] for tpl in page_data.get("templates", [])]

        # Get revision information
        revisions = page_data.get("revisions", [])
        last_modified = None
        revision_id = None
        if revisions:
            last_modified = revisions[0].get("timestamp")
            revision_id = revisions[0].get("revid")

        # Get infobox data
        infobox = self._extract_infobox(page_title)

        # Create article object
        article = WikipediaArticle(
            title=page_title,
            page_id=page_id,
            url=f"https://vi.wikipedia.org/wiki/{quote(page_title)}",
            abstract=abstract,
            content="",  # Will be populated if needed
            infobox=infobox,
            categories=categories,
            templates=templates,
            last_modified=last_modified,
            revision_id=revision_id,
        )

        # Get full content if requested
        if self.extraction_config.get("include_content", False):
            content = self._get_article_content(page_title)
            article.content = content or ""

        self.collected_articles[title] = article
        logger.info(f"Successfully collected article: {title}")
        return article

    def _extract_infobox(self, title: str) -> Dict[str, Any]:
        """Extract infobox data from Wikipedia article."""
        params = {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "section": 0,
            "disablelimitreport": True,
        }

        response = self._make_api_request(params)
        if not response or "parse" not in response:
            logger.warning(f"Failed to get wikitext for: {title}")
            return {}

        wikitext = response["parse"].get("wikitext", {}).get("*", "")
        if not wikitext:
            return {}

        return self._parse_infobox_from_wikitext(wikitext)

    def _parse_infobox_from_wikitext(self, wikitext: str) -> Dict[str, Any]:
        """Parse infobox data from wikitext."""
        infobox = {}

        # Common Vietnamese infobox patterns
        infobox_patterns = [
            r"{{Thông tin ([^}]+)}}",
            r"{{Infobox ([^}]+)}}",
            r"{{Hộp thông tin ([^}]+)}}",
        ]

        for pattern in infobox_patterns:
            matches = re.finditer(pattern, wikitext, re.IGNORECASE | re.DOTALL)

            for match in matches:
                infobox_content = match.group(1)
                template_name = infobox_content.split("|")[0].strip()
                infobox["template_type"] = template_name

                # Parse infobox parameters
                params = self._parse_infobox_parameters(infobox_content)
                infobox.update(params)

                if infobox:  # If we found an infobox, we're done
                    break

        return infobox

    def _parse_infobox_parameters(self, content: str) -> Dict[str, str]:
        """Parse parameters from infobox content."""
        params = {}

        # Split by | but handle nested braces
        parts = []
        current_part = ""
        brace_depth = 0

        for char in content:
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
            elif char == "|" and brace_depth == 0:
                parts.append(current_part.strip())
                current_part = ""
                continue

            current_part += char

        if current_part.strip():
            parts.append(current_part.strip())

        # Parse each parameter
        for part in parts[1:]:  # Skip template name
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Clean up value (remove wiki markup)
                value = self._clean_wiki_markup(value)

                if key and value:
                    params[key] = value

        return params

    def _clean_wiki_markup(self, text: str) -> str:
        """Clean Wikipedia markup from text."""
        if not text:
            return ""

        # Remove wiki links [[link|text]] -> text or [[link]] -> link
        text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
        text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

        # Remove external links
        text = re.sub(r"\[https?://[^\s]+ ([^\]]+)\]", r"\1", text)
        text = re.sub(r"https?://[^\s]+", "", text)

        # Remove templates {{template}}
        text = re.sub(r"{{[^}]+}}", "", text)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove formatting
        text = re.sub(r"'''([^']+)'''", r"\1", text)  # Bold
        text = re.sub(r"''([^']+)''", r"\1", text)  # Italic

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _get_article_content(self, title: str) -> Optional[str]:
        """Get full article content."""
        params = {
            "prop": "extracts",
            "titles": title,
            "explaintext": True,
            "exsectionformat": "plain",
        }

        response = self._make_api_request(params)
        if not response or "query" not in response:
            return None

        pages = response["query"].get("pages", {})
        if not pages:
            return None

        page_data = next(iter(pages.values()))
        return page_data.get("extract", "")

    def get_articles_from_category(
        self, category: str, limit: int = 50
    ) -> List[WikipediaArticle]:
        """Get articles from a Wikipedia category."""
        logger.info(f"Collecting articles from category: {category}")
        articles = []

        params = {
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": min(limit, 500),
            "cmnamespace": 0,  # Main namespace only
        }

        response = self._make_api_request(params)
        if not response or "query" not in response:
            logger.error(f"Failed to get category members: {category}")
            return articles

        members = response["query"].get("categorymembers", [])

        for member in members[:limit]:
            title = member.get("title", "")
            if title:
                article = self.get_article_by_title(title)
                if article:
                    articles.append(article)

        logger.info(f"Collected {len(articles)} articles from category: {category}")
        return articles

    def collect_sample_articles(self) -> List[WikipediaArticle]:
        """Collect predefined sample articles."""
        logger.info("Collecting sample articles")
        articles = []

        all_titles = []
        for category_articles in self.sample_articles.values():
            all_titles.extend(category_articles)

        with tqdm(total=len(all_titles), desc="Collecting articles") as pbar:
            for title in all_titles:
                article = self.get_article_by_title(title)
                if article:
                    articles.append(article)
                pbar.update(1)

        logger.info(f"Collected {len(articles)} sample articles")
        return articles

    def collect_articles_by_categories(
        self, max_per_category: int = 20
    ) -> List[WikipediaArticle]:
        """Collect articles from target categories."""
        logger.info("Collecting articles from target categories")
        all_articles = []

        for category_type, categories in self.target_categories.items():
            logger.info(f"Processing {category_type} categories")

            for category in categories:
                articles = self.get_articles_from_category(category, max_per_category)
                all_articles.extend(articles)

                # Add delay between categories
                time.sleep(self.config["rate_limit"]["delay_between_requests"])

        # Remove duplicates
        unique_articles = {}
        for article in all_articles:
            if article.title not in unique_articles:
                unique_articles[article.title] = article

        final_articles = list(unique_articles.values())
        logger.info(f"Collected {len(final_articles)} unique articles from categories")
        return final_articles

    def save_articles_to_json(
        self, articles: List[WikipediaArticle], output_path: str
    ) -> None:
        """Save collected articles to JSON file."""
        try:
            # Convert articles to dictionaries
            articles_data = []
            for article in articles:
                article_dict = {
                    "title": article.title,
                    "page_id": article.page_id,
                    "url": article.url,
                    "abstract": article.abstract,
                    "content": article.content,
                    "infobox": article.infobox,
                    "categories": article.categories,
                    "templates": article.templates,
                    "language": article.language,
                    "last_modified": article.last_modified,
                    "revision_id": article.revision_id,
                }
                articles_data.append(article_dict)

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Save to JSON
            with open(output_path, "w", encoding="utf-8") as file:
                json.dump(articles_data, file, ensure_ascii=False, indent=2)

            logger.info(f"Saved {len(articles)} articles to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save articles: {e}")
            raise

    def load_articles_from_json(self, input_path: str) -> List[WikipediaArticle]:
        """Load articles from JSON file."""
        try:
            with open(input_path, "r", encoding="utf-8") as file:
                articles_data = json.load(file)

            articles = []
            for article_dict in articles_data:
                article = WikipediaArticle(**article_dict)
                articles.append(article)
                self.collected_articles[article.title] = article

            logger.info(f"Loaded {len(articles)} articles from {input_path}")
            return articles

        except Exception as e:
            logger.error(f"Failed to load articles: {e}")
            raise

    def get_collection_statistics(self) -> Dict[str, Any]:
        """Get statistics about collected articles."""
        if not self.collected_articles:
            return {"total_articles": 0}

        stats = {
            "total_articles": len(self.collected_articles),
            "failed_articles": len(self.failed_articles),
            "success_rate": (
                len(self.collected_articles)
                / (len(self.collected_articles) + len(self.failed_articles))
            )
            * 100,
            "articles_with_infobox": sum(
                1 for article in self.collected_articles.values() if article.infobox
            ),
            "average_categories_per_article": sum(
                len(article.categories) for article in self.collected_articles.values()
            )
            / len(self.collected_articles),
            "infobox_templates": {},
        }

        # Count infobox templates
        for article in self.collected_articles.values():
            if article.infobox and "template_type" in article.infobox:
                template = article.infobox["template_type"]
                stats["infobox_templates"][template] = (
                    stats["infobox_templates"].get(template, 0) + 1
                )

        return stats


def main():
    """Main function for testing the collector."""
    try:
        collector = WikipediaCollector()

        # Collect sample articles
        articles = collector.collect_sample_articles()

        # Save to JSON
        collector.save_articles_to_json(articles, "data/raw/vietnamese_articles.json")

        # Print statistics
        stats = collector.get_collection_statistics()
        print("Collection Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        raise


if __name__ == "__main__":
    main()
