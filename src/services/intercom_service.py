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

    def list_articles(self, collection_id: str) -> Dict:
        """
        List all articles in a specific collection

        Args:
            collection_id: Collection ID to list articles from

        Returns:
            Dictionary with list of articles
        """
        url = f"{self.base_url}/articles"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Intercom-Version": "2.14"
        }

        try:
            # Fetch articles with pagination
            all_articles = []
            page = 1
            per_page = 50

            while True:
                params = {
                    "per_page": per_page,
                    "page": page
                }

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()
                articles = data.get("data", [])

                # Filter by collection_id
                for article in articles:
                    if article.get("parent_id") == collection_id:
                        all_articles.append({
                            "id": article.get("id"),
                            "title": article.get("title"),
                            "url": article.get("url"),
                            "state": article.get("state")
                        })

                # Check if there are more pages
                if len(articles) < per_page:
                    break

                page += 1

            return {
                "status": "success",
                "articles": all_articles,
                "count": len(all_articles)
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Failed to list Intercom articles: {str(e)}",
                "articles": []
            }

    def list_all_articles(self) -> Dict:
        """
        List ALL articles from Intercom (without filtering by collection)

        Returns:
            Dictionary with list of all articles including their parent_id
        """
        url = f"{self.base_url}/articles"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Intercom-Version": "2.14"
        }

        try:
            # Fetch articles with pagination
            all_articles = []
            page = 1
            per_page = 50

            while True:
                params = {
                    "per_page": per_page,
                    "page": page
                }

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()
                articles = data.get("data", [])

                # Add ALL articles (no filtering)
                for article in articles:
                    all_articles.append({
                        "id": article.get("id"),
                        "title": article.get("title"),
                        "url": article.get("url"),
                        "state": article.get("state"),
                        "parent_id": article.get("parent_id"),  # Include parent_id for grouping
                        "parent_type": article.get("parent_type")
                    })

                # Check if there are more pages
                if len(articles) < per_page:
                    break

                page += 1

            return {
                "status": "success",
                "articles": all_articles,
                "count": len(all_articles)
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Failed to list all Intercom articles: {str(e)}",
                "articles": []
            }

    def get_article(self, article_id: str) -> Dict:
        """
        Fetch a single article from Intercom by ID

        Args:
            article_id: The Intercom article ID

        Returns:
            Dictionary with status and article body HTML
        """
        url = f"{self.base_url}/articles/{article_id}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Intercom-Version": "2.14"
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            return {
                "status": "success",
                "html": data.get("body", "")
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Failed to fetch Intercom article: {str(e)}",
                "html": ""
            }

    def delete_article(self, article_id: str) -> Dict:
        """
        Delete an article from Intercom

        Args:
            article_id: Article ID to delete

        Returns:
            Dictionary with deletion status
        """
        url = f"{self.base_url}/articles/{article_id}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Intercom-Version": "2.14"
        }

        try:
            response = requests.delete(
                url,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            return {
                "status": "success",
                "article_id": article_id,
                "message": "Article deleted successfully"
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Failed to delete Intercom article: {str(e)}",
                "article_id": article_id
            }
