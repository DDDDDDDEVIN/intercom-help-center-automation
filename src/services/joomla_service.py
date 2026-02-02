"""
Step 2: Download Article from Joomla
Fetches article HTML from Joomla API using article ID
"""
import requests
from typing import Dict, Any


class JoomlaService:
    def __init__(self, base_url: str, api_endpoint: str, api_token: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_endpoint = api_endpoint
        self.api_token = api_token

    def download_article(self, article_id: str) -> Dict[str, Any]:
        """
        Download article HTML from Joomla API

        API Specification:
        - URL: {base_url}{api_endpoint}/{article_id}?format=jsonapi
        - Method: GET
        - Headers: X-Joomla-Token, Accept: application/vnd.api+json, Content-Type: application/json

        Args:
            article_id: The article ID to fetch

        Returns:
            Dictionary containing raw_html and other article data
        """
        url = f"{self.base_url}{self.api_endpoint}/{article_id}?format=jsonapi"

        headers = {
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/json'
        }

        if self.api_token:
            headers['X-Joomla-Token'] = self.api_token

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract HTML content and title from JSONAPI response
            attributes = data.get('data', {}).get('attributes', {})
            raw_html = attributes.get('text', '')
            article_title = attributes.get('title', 'Analysis Report')

            return {
                'raw_html': raw_html,
                'article_title': article_title,
                'article_id': article_id,
                'base_url': self.base_url
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download article {article_id}: {str(e)}")

    def get_global_category_ids(self, root_category_id: str = "227") -> tuple:
        """
        Fetch all category IDs under the Global category (including nested subcategories)

        Args:
            root_category_id: The root Global category ID (default "227")

        Returns:
            Tuple of (category_id_list, category_name_map)
        """
        # Use the same API path structure as articles endpoint, but for categories
        url = f"{self.base_url}/sites/default/api/index.php/v1/content/categories?format=jsonapi&page[limit]=1000"

        headers = {
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/json'
        }

        if self.api_token:
            headers['X-Joomla-Token'] = self.api_token

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            categories = data.get('data', [])

            target_ids = []
            category_names = {}

            for cat in categories:
                cat_id = cat.get('id')
                attrs = cat.get('attributes', {})
                title = attrs.get('title', '')

                # Store category name for all categories (ensure cat_id is string for consistent lookup)
                category_names[str(cat_id)] = title

                # Include category if:
                # 1. It's the root Global category (ID 227)
                # 2. Title starts with "Global"
                if (cat_id == root_category_id or
                    title.startswith("Global")):
                    target_ids.append(cat_id)

            # Remove duplicates and sort
            target_ids = sorted(list(set(target_ids)))
            print(f"[Joomla] Found {len(target_ids)} Global category IDs: {target_ids[:10]}..." if len(target_ids) > 10 else f"[Joomla] Found {len(target_ids)} Global category IDs: {target_ids}")

            # Debug: Print all category names
            print("[Joomla] DEBUG - Category names included:")
            for cat_id in target_ids:
                cat_name = category_names.get(str(cat_id), 'Unknown')
                print(f"  - ID {cat_id}: {cat_name}")

            return target_ids, category_names

        except requests.exceptions.RequestException as e:
            print(f"[Joomla] Error fetching categories: {str(e)}")
            return [root_category_id], {root_category_id: "Global"}  # Fallback to just root category

    def get_all_published_articles(self, limit: int = 500, offset: int = 0, category_id: str = None) -> Dict[str, Any]:
        """
        Fetch all published articles from Joomla API

        API Specification:
        - URL: {base_url}{api_endpoint}?format=jsonapi&filter[state]=1&filter[catid]={category_ids}&page[limit]={limit}&page[offset]={offset}
        - Method: GET
        - Headers: X-Joomla-Token, Accept: application/vnd.api+json
        - filter[state]=1 returns only published articles
        - filter[catid]={category_ids} filters by category (supports comma-separated IDs for nested categories)

        Args:
            limit: Number of articles per page (default 100)
            offset: Pagination offset (default 0)
            category_id: Root category ID to filter articles (optional, e.g., '227' for global section)
                        Will automatically fetch all subcategories under this root

        Returns:
            Dictionary containing list of articles with id, title, state, alias
        """
        # Build URL with filters
        # Note: Joomla API doesn't support filter[catid], so we fetch all and filter in code
        # Fetch all articles (both published and unpublished)
        url = f"{self.base_url}{self.api_endpoint}?format=jsonapi"

        # Get target category IDs and names for filtering
        category_names = {}
        target_category_ids = []
        if category_id:
            # Get all category IDs under the root (including nested subcategories)
            target_category_ids, category_names = self.get_global_category_ids(category_id)
            print(f"[Joomla] Will filter for articles from {len(target_category_ids)} Global categories")

        # Increase limit to fetch all articles (since we need to filter in code)
        url += f"&page[limit]=1000&page[offset]={offset}"

        headers = {
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/json'
        }

        if self.api_token:
            headers['X-Joomla-Token'] = self.api_token

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Extract articles from JSONAPI response
            articles = []
            category_article_count = {}  # Track articles per category
            seen_base_titles = {}  # Track base titles for deduplication

            for item in data.get('data', []):
                article_id = item.get('id')
                attributes = item.get('attributes', {})

                # Get category ID from relationships (JSON:API format)
                relationships = item.get('relationships', {})
                category_data = relationships.get('category', {}).get('data', {})
                cat_id = str(category_data.get('id', ''))

                # Look up category name
                category_name = category_names.get(cat_id, 'Unknown')

                # Filter: Only include articles from target Global categories
                # Skip if category ID is not in our target list
                if category_id and cat_id not in target_category_ids:
                    continue

                title = attributes.get('title', 'Untitled')

                # Get base title by removing country brackets at the end (e.g., "Article [Australia]" -> "Article")
                import re
                base_title = re.sub(r'\s*\(.*?\)\s*$', '', title).strip()

                # Deduplicate: Skip if we've already seen this base title
                if base_title in seen_base_titles:
                    continue

                seen_base_titles[base_title] = True

                # Count articles per category
                if cat_id not in category_article_count:
                    category_article_count[cat_id] = {'name': category_name, 'count': 0}
                category_article_count[cat_id]['count'] += 1

                articles.append({
                    'id': article_id,
                    'title': base_title,
                    'alias': attributes.get('alias', ''),
                    'state': attributes.get('state', 0),
                    'created': attributes.get('created', ''),
                    'modified': attributes.get('modified', ''),
                    'category_name': category_name
                })

            # Debug: Print article count per category
            print(f"[Joomla] DEBUG - Fetched {len(articles)} total articles")
            print("[Joomla] DEBUG - Articles per category:")
            for cat_id, info in sorted(category_article_count.items(), key=lambda x: x[1]['count'], reverse=True):
                print(f"  - ID {cat_id} ({info['name']}): {info['count']} articles")

            # Get pagination info
            meta = data.get('meta', {})
            total_pages = meta.get('total-pages', 1)

            return {
                'status': 'success',
                'articles': articles,
                'total_pages': total_pages,
                'current_page': (offset // limit) + 1,
                'total_count': len(articles)
            }

        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f"Failed to fetch articles: {str(e)}",
                'articles': []
            }
