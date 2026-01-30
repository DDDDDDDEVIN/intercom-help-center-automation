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
