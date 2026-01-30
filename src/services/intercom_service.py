"""
Intercom Service
Publishes content to Intercom Help Center
"""
import requests
from typing import Dict


class IntercomService:
    def __init__(
        self,
        api_token: str,
        collection_id: str,
        data_dict_collection_id: str = None,
        chart_collection_id: str = None,
        article_collection_id: str = None
    ):
        """
        Initialize Intercom service

        Args:
            api_token: Intercom API token
            collection_id: Default collection ID for articles
            data_dict_collection_id: Collection ID for data dictionary articles
            chart_collection_id: Collection ID for chart library articles
            article_collection_id: Collection ID for article library articles
        """
        self.api_token = api_token
        self.collection_id = collection_id
        self.data_dict_collection_id = data_dict_collection_id or collection_id
        self.chart_collection_id = chart_collection_id or collection_id
        self.article_collection_id = article_collection_id or collection_id
        self.base_url = "https://api.intercom.io"

    def create_article(
        self,
        title: str,
        body_html: str,
        collection_id: str = None,
        author_id: str = None,
        state: str = "published"
    ) -> Dict:
        """
        Create and optionally publish an article in Intercom Help Center

        Args:
            title: Article title
            body_html: Article body in HTML format
            collection_id: Collection ID (uses default if not provided)
            author_id: Author ID (optional)
            state: Article state ('published', 'draft')

        Returns:
            Dictionary with article URL and ID
        """
        url = f"{self.base_url}/articles"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Intercom-Version": "2.14"
        }

        payload = {
            "title": title,
            "body": body_html,
            "state": state
        }

        # Add optional parameters
        if collection_id:
            payload["parent_id"] = collection_id
            payload["parent_type"] = "collection"
        elif self.collection_id:
            payload["parent_id"] = self.collection_id
            payload["parent_type"] = "collection"

        if author_id:
            payload["author_id"] = author_id

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            return {
                "status": "success",
                "article_id": data.get("id"),
                "article_url": data.get("url") or f"https://help.intercom.com/articles/{data.get('id')}",
                "state": data.get("state")
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Failed to create Intercom article: {str(e)}"
            }

    def update_article(
        self,
        article_id: str,
        title: str = None,
        body_html: str = None,
        state: str = None
    ) -> Dict:
        """
        Update an existing article in Intercom

        Args:
            article_id: The Intercom article ID
            title: New title (optional)
            body_html: New body HTML (optional)
            state: New state (optional)

        Returns:
            Dictionary with update status
        """
        url = f"{self.base_url}/articles/{article_id}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {}
        if title:
            payload["title"] = title
        if body_html:
            payload["body"] = body_html
        if state:
            payload["state"] = state

        try:
            response = requests.put(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            return {
                "status": "success",
                "article_id": data.get("id"),
                "article_url": data.get("url")
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Failed to update Intercom article: {str(e)}"
            }
