"""
Main Flask application with webhook endpoint
Step 1: Catch Hook - Trigger by HTTP POST with article ID
"""
from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
from services.workflow import WorkflowOrchestrator

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize workflow orchestrator
orchestrator = WorkflowOrchestrator(
    joomla_base_url=os.getenv('JOOMLA_BASE_URL'),
    joomla_api_endpoint=os.getenv('JOOMLA_API_ENDPOINT'),
    joomla_api_token=os.getenv('JOOMLA_API_TOKEN'),
    tableau_server_url=os.getenv('TABLEAU_SERVER_URL'),
    tableau_username=os.getenv('TABLEAU_USERNAME'),
    tableau_password=os.getenv('TABLEAU_PASSWORD'),
    tableau_site_name=os.getenv('TABLEAU_SITE_NAME', ''),
    tableau_global_project_id=os.getenv('TABLEAU_GLOBAL_PROJECT_ID'),
    google_sheets_api_url=os.getenv('GOOGLE_SHEETS_API_URL'),
    openai_api_key=os.getenv('OPENAI_API_KEY'),
    openai_model=os.getenv('OPENAI_MODEL', 'gpt-4'),
    openai_text_model=os.getenv('OPENAI_TEXT_MODEL', 'gpt-4o'),
    openai_image_detail=os.getenv('OPENAI_IMAGE_DETAIL', 'high'),
    intercom_api_token=os.getenv('INTERCOM_API_TOKEN'),
    intercom_collection_id=os.getenv('INTERCOM_COLLECTION_ID'),
    intercom_author_id=os.getenv('INTERCOM_AUTHOR_ID'),
    intercom_data_dict_collection_id=os.getenv('INTERCOM_DATA_DICT_COLLECTION_ID'),
    intercom_chart_collection_id=os.getenv('INTERCOM_CHART_COLLECTION_ID'),
    intercom_article_collection_id=os.getenv('INTERCOM_ARTICLE_COLLECTION_ID'),
    google_sheets_data_dict_sheet=os.getenv('GOOGLE_SHEETS_DATA_DICT_SHEET', 'data_dictionary'),
    google_sheets_chart_library_sheet=os.getenv('GOOGLE_SHEETS_CHART_LIBRARY_SHEET', 'chart_library'),
    google_sheets_article_library_sheet=os.getenv('GOOGLE_SHEETS_ARTICLE_LIBRARY_SHEET', 'article_library')
)


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Webhook endpoint to receive article ID and trigger automation

    Expected POST body:
    {
        "article_id": "123"
    }
    """
    try:
        data = request.get_json()

        if not data or 'article_id' not in data:
            return jsonify({
                'error': 'Missing article_id in request body'
            }), 400

        article_id = data['article_id']

        print(f"[Webhook] Received request for article ID: {article_id}")

        # Execute the workflow
        result = orchestrator.execute(article_id)

        return jsonify({
            'success': True,
            'article_id': article_id,
            'result': result
        }), 200

    except Exception as e:
        print(f"[Webhook] Error: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'intercom-help-center-automation'
    }), 200


@app.route('/', methods=['GET'])
@app.route('/articles', methods=['GET'])
def articles_page():
    """Render the article selection interface"""
    return render_template('articles.html')


@app.route('/api/joomla/articles', methods=['GET'])
def get_joomla_articles():
    """
    API endpoint to fetch all published articles from Joomla

    Query Parameters:
        limit (optional): Number of articles per page (default 100)
        offset (optional): Pagination offset (default 0)

    Returns:
        JSON with list of articles and pagination info (filtered by category if configured)
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        # Get category ID from environment (e.g., 227 for global section)
        category_id = os.getenv('JOOMLA_CATEGORY_ID')

        # Use the joomla_service from orchestrator
        result = orchestrator.joomla_service.get_all_published_articles(limit, offset, category_id)

        return jsonify(result), 200

    except Exception as e:
        print(f"[API] Error fetching Joomla articles: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'articles': []
        }), 500


def filter_gpt_prompts(html_content):
    """
    Remove GPT prompts and extract generated content from data-gpt attributes

    1. Removes prompt text between "GPT PROMPT" and "END GPT (with replace)"
    2. Extracts content from data-gpt attributes and makes it visible
    3. Removes SunWiz License Terms and other junk endings
    """
    import re
    import html as html_module

    # Remove GPT prompts (pattern from html_cleaner.py line 84)
    html_content = re.sub(r'GPT PROMPT.*?END GPT \(with replace\)', '', html_content, flags=re.DOTALL | re.IGNORECASE)

    # Remove horizontal rules
    html_content = re.sub(r'<hr[^>]*>', '', html_content, flags=re.IGNORECASE)

    # Remove SunWiz License Terms & Conditions and other junk endings
    # Based on JUNK_ENDINGS from html_cleaner.py
    junk_endings = [
        "SunWiz License Terms", "Ownership Rights", "Quick Summary",
        "You MAY:", "Copyright", "Disclaimer", "Commentary by AI",
        "Interpreting this data", "Applying this data", "Key Insights",
        "Analysis:", "Recommendations:", "Next Steps:"
    ]

    # Find the earliest occurrence of any junk ending keyword
    cutoff_index = len(html_content)
    for keyword in junk_endings:
        # Case-insensitive search
        pattern = re.escape(keyword)
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match and match.start() < cutoff_index:
            cutoff_index = match.start()

    # Cut off content at the earliest junk ending
    html_content = html_content[:cutoff_index]

    # Extract and display content from data-gpt attributes
    # Pattern matches complete opening tag with data-gpt attribute: <tag ... data-gpt="content" ... >
    gpt_pattern = r'(<[^>]+\s+data-gpt=(["\'])(.*?)\2[^>]*>)'

    def extract_gpt_content(match):
        full_opening_tag = match.group(1)  # Complete opening tag with all attributes
        gpt_content = match.group(3)

        # Unescape HTML entities and clean whitespace
        clean_content = html_module.unescape(gpt_content).strip()
        # Normalize whitespace (collapse multiple spaces/newlines)
        clean_content = re.sub(r'\s+', ' ', clean_content)

        # Return original tag + visible content after it (no background styling)
        return f'{full_opening_tag}<div class="gpt-generated-content">{clean_content}</div>'

    html_content = re.sub(gpt_pattern, extract_gpt_content, html_content, flags=re.DOTALL)

    return html_content


@app.route('/api/articles/published', methods=['GET'])
def get_published_articles():
    """
    Get all published article titles from Google Sheets

    Returns:
        JSON with list of published article titles
    """
    try:
        # Fetch all rows from article_library sheet
        import requests
        params = {"sheet_name": os.getenv('GOOGLE_SHEETS_ARTICLE_LIBRARY_SHEET', 'article_library')}

        response = requests.get(
            os.getenv('GOOGLE_SHEETS_API_URL'),
            params=params,
            allow_redirects=True,
            timeout=30
        )

        if response.status_code == 200:
            all_rows = response.json()

            # Extract article titles (column 0)
            published_titles = []
            for row in all_rows:
                if len(row) > 0 and str(row[0]).strip():
                    published_titles.append(str(row[0]).strip())

            return jsonify({
                'status': 'success',
                'published_titles': published_titles,
                'count': len(published_titles)
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Google Sheets API error: {response.status_code}',
                'published_titles': []
            }), 500

    except Exception as e:
        print(f"[API] Error fetching published articles: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'published_titles': []
        }), 500


@app.route('/api/joomla/articles/<article_id>', methods=['GET'])
def get_article_preview(article_id):
    """
    Fetch full article content for preview

    Returns:
        JSON with article content and metadata
    """
    try:
        # Fetch full article from Joomla
        article_data = orchestrator.joomla_service.download_article(article_id)

        # Extract fields
        raw_html = article_data.get('raw_html', '')

        # Filter out GPT prompts, keep only generated content
        cleaned_html = filter_gpt_prompts(raw_html)

        # Create excerpt (first 1000 characters of cleaned text)
        # Remove HTML tags for excerpt
        import re
        text_only = re.sub(r'<[^>]+>', '', cleaned_html)
        excerpt = text_only[:1000].strip() + ('...' if len(text_only) > 1000 else '')

        return jsonify({
            'status': 'success',
            'article_id': article_id,
            'title': article_data.get('article_title', 'Untitled'),
            'raw_html': cleaned_html,
            'excerpt': excerpt
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/articles/create', methods=['POST'])
def create_articles():
    """
    API endpoint to create selected articles in Intercom

    Expected POST body:
    {
        "article_ids": ["123", "456", "789"]
    }

    Returns:
        JSON with processing results for each article
    """
    try:
        data = request.get_json()

        if not data or 'article_ids' not in data:
            return jsonify({
                'error': 'Missing article_ids in request body'
            }), 400

        article_ids = data['article_ids']

        if not isinstance(article_ids, list):
            return jsonify({
                'error': 'article_ids must be an array'
            }), 400

        results = []

        # Process each article
        for article_id in article_ids:
            try:
                print(f"\n[Batch] Processing article ID: {article_id}")

                # Execute the workflow for this article
                result = orchestrator.execute(str(article_id))

                results.append({
                    'article_id': article_id,
                    'status': result.get('status', 'success'),
                    'message': result.get('message', 'Processed successfully')
                })

            except Exception as e:
                error_msg = str(e)
                print(f"[Batch] Error processing article {article_id}: {error_msg}")

                results.append({
                    'article_id': article_id,
                    'status': 'error',
                    'message': error_msg
                })

        return jsonify({
            'success': True,
            'total': len(article_ids),
            'results': results
        }), 200

    except Exception as e:
        print(f"[API] Error in batch create: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/articles/update', methods=['POST'])
def update_articles():
    """
    API endpoint to update selected articles in Intercom

    Expected POST body:
    {
        "article_ids": ["123", "456", "789"],
        "preview": true  // Optional: if true, returns comparison data without updating
    }

    Returns:
        JSON with processing results for each article
        If preview=true, includes old_html and new_html for comparison
    """
    try:
        data = request.get_json()

        if not data or 'article_ids' not in data:
            return jsonify({
                'error': 'Missing article_ids in request body'
            }), 400

        article_ids = data['article_ids']
        preview = data.get('preview', False)  # Default to False for backward compatibility

        if not isinstance(article_ids, list):
            return jsonify({
                'error': 'article_ids must be an array'
            }), 400

        results = []

        # Process each article
        for article_id in article_ids:
            try:
                mode_text = "Preview" if preview else "Update"
                print(f"\n[{mode_text}] Processing article ID: {article_id}")

                # Execute the UPDATE workflow for this article (with preview mode if requested)
                result = orchestrator.execute_update(str(article_id), preview_mode=preview)

                result_data = {
                    'article_id': article_id,
                    'status': result.get('status', 'success'),
                    'message': result.get('message', 'Updated successfully')
                }

                # Include comparison data if in preview mode
                if preview and result.get('status') == 'preview':
                    result_data.update({
                        'comparisons': result.get('comparisons', []),
                        'total_comparisons': result.get('total_comparisons', 0)
                    })

                results.append(result_data)

            except Exception as e:
                error_msg = str(e)
                print(f"[Update] Error processing article {article_id}: {error_msg}")

                results.append({
                    'article_id': article_id,
                    'status': 'error',
                    'message': error_msg
                })

        return jsonify({
            'success': True,
            'total': len(article_ids),
            'results': results
        }), 200

    except Exception as e:
        print(f"[API] Error in batch update: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/articles/update/confirm', methods=['POST'])
def confirm_article_updates():
    """
    Apply confirmed article updates to Intercom

    Expected POST body:
    {
        "updates": [
            {
                "article_title": "Title",
                "article_type": "main_article|chart|data_field",
                "intercom_article_id": "456",  // empty if new
                "collection_id": "...",  // for charts and data fields
                "html": "chosen HTML content",
                "original_name": "...",  // for charts and data fields (Tableau name)
                "field_name": "..."  // for data fields only
            }
        ]
    }

    Returns:
        JSON with results for each applied update
    """
    try:
        data = request.get_json()

        if not data or 'updates' not in data:
            return jsonify({
                'error': 'Missing updates in request body'
            }), 400

        updates = data['updates']

        if not isinstance(updates, list):
            return jsonify({
                'error': 'updates must be an array'
            }), 400

        results = []

        # Apply each update
        for update_item in updates:
            try:
                article_title = update_item.get('article_title')
                article_type = update_item.get('article_type', 'main_article')
                intercom_article_id = update_item.get('intercom_article_id', '')
                html_content = update_item.get('html')
                collection_id = update_item.get('collection_id')
                original_name = update_item.get('original_name', article_title)

                if not all([article_title, html_content]):
                    raise Exception("Missing required fields: article_title or html")

                print(f"\n[Confirm] Applying update for [{article_type}]: {article_title}")

                # Determine action based on whether article exists
                if intercom_article_id:
                    # Update existing article
                    update_result = orchestrator.intercom_service.update_article(
                        article_id=intercom_article_id,
                        title=article_title,
                        body_html=html_content,
                        state='published'
                    )
                else:
                    # Create new article (for charts and data fields)
                    if not collection_id:
                        raise Exception("collection_id required for new articles")

                    update_result = orchestrator.intercom_service.create_article(
                        title=article_title,
                        body_html=html_content,
                        collection_id=collection_id,
                        author_id=orchestrator.intercom_author_id,
                        state='published'
                    )

                if update_result['status'] != 'success':
                    raise Exception(f"Intercom operation failed: {update_result.get('message')}")

                article_intercom_url = update_result['article_url']
                intercom_article_id = update_result.get('article_id', intercom_article_id)
                print(f"✓ {'Updated' if update_item.get('intercom_article_id') else 'Created'} in Intercom: {article_intercom_url}")

                # Determine sheet name based on article type
                if article_type == 'chart':
                    sheet_name = orchestrator.google_sheets_chart_library_sheet
                elif article_type == 'data_field':
                    sheet_name = orchestrator.google_sheets_data_dict_sheet
                else:  # main_article
                    sheet_name = orchestrator.google_sheets_article_library_sheet

                # Log to Google Sheets
                orchestrator.google_sheets_service.log_processed_item(
                    original_name=original_name,
                    human_name=article_title,
                    intercom_url=article_intercom_url,
                    intercom_id=intercom_article_id,
                    html=html_content,
                    sheet_name=sheet_name
                )
                print(f"✓ Logged to Google Sheets ({sheet_name})")

                results.append({
                    'article_title': article_title,
                    'article_type': article_type,
                    'status': 'success',
                    'message': 'Update applied successfully'
                })

            except Exception as e:
                error_msg = str(e)
                print(f"[Confirm] Error applying update: {error_msg}")

                results.append({
                    'article_title': update_item.get('article_title', 'unknown'),
                    'article_type': update_item.get('article_type', 'unknown'),
                    'status': 'error',
                    'message': error_msg
                })

        return jsonify({
            'success': True,
            'total': len(updates),
            'results': results
        }), 200

    except Exception as e:
        print(f"[API] Error in confirm updates: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/intercom/articles', methods=['GET'])
def get_intercom_articles():
    """
    API endpoint to fetch all articles from Intercom and group by collection

    Returns:
        JSON with articles grouped by human-readable collection names
    """
    try:
        # Collection ID to human-readable name mapping
        collection_mappings = {
            os.getenv('INTERCOM_ARTICLE_COLLECTION_ID'): 'Article Collection',
            os.getenv('INTERCOM_CHART_COLLECTION_ID'): 'Chart Library',
            os.getenv('INTERCOM_DATA_DICT_COLLECTION_ID'): 'Data Dictionary'
        }

        # Fetch ALL articles from Intercom
        result = orchestrator.intercom_service.list_all_articles()

        if result.get('status') != 'success':
            return jsonify({
                'status': 'error',
                'message': result.get('message', 'Failed to fetch articles'),
                'collections': {}
            }), 500

        all_articles = result.get('articles', [])

        # Initialize collections
        collections = {name: [] for name in collection_mappings.values()}

        # Group articles by parent_id - loop through articles ONCE
        # Convert parent_id to string for comparison
        for article in all_articles:
            parent_id = str(article.get('parent_id')) if article.get('parent_id') else None
            if parent_id in collection_mappings:
                collection_name = collection_mappings[parent_id]
                collections[collection_name].append(article)

        return jsonify({
            'status': 'success',
            'collections': collections
        }), 200

    except Exception as e:
        print(f"[API] Error fetching Intercom articles: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'collections': {}
        }), 500


@app.route('/api/intercom/articles/delete', methods=['POST'])
def delete_intercom_articles():
    """
    API endpoint to delete articles from Intercom AND Google Sheets

    Expected POST body:
    {
        "articles": [
            {"id": "123", "title": "Article Title", "collection": "Article Collection"},
            {"id": "456", "title": "Chart Title", "collection": "Chart Library"}
        ]
    }

    Returns:
        JSON with deletion results
    """
    try:
        data = request.get_json()

        if not data or 'articles' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing articles in request body'
            }), 400

        articles = data['articles']

        if not isinstance(articles, list):
            return jsonify({
                'status': 'error',
                'message': 'articles must be an array'
            }), 400

        # Map collection names to sheet names
        collection_to_sheet = {
            'Article Collection': 'article_library',
            'Chart Library': 'chart_library',
            'Data Dictionary': 'data_dictionary'
        }

        deleted_count = 0
        failed_count = 0
        results = []

        # Delete each article from both Intercom and Google Sheets
        for article in articles:
            article_id = article.get('id')
            article_title = article.get('title')
            collection_name = article.get('collection')

            try:
                # Delete from Intercom
                intercom_result = orchestrator.intercom_service.delete_article(article_id)

                if intercom_result.get('status') != 'success':
                    failed_count += 1
                    results.append({
                        'article_id': article_id,
                        'title': article_title,
                        'status': 'error',
                        'message': f"Intercom deletion failed: {intercom_result.get('message', 'Unknown error')}"
                    })
                    continue

                # Delete from Google Sheets
                sheet_name = collection_to_sheet.get(collection_name)
                if sheet_name:
                    orchestrator.google_sheets_service.delete_row_by_value(
                        value_to_match=article_id,
                        column_index=4,  # Column D (intercom_id)
                        sheet_name=sheet_name
                    )

                deleted_count += 1
                results.append({
                    'article_id': article_id,
                    'title': article_title,
                    'status': 'success'
                })

            except Exception as e:
                failed_count += 1
                results.append({
                    'article_id': article_id,
                    'title': article_title,
                    'status': 'error',
                    'message': str(e)
                })

        return jsonify({
            'status': 'success',
            'deleted_count': deleted_count,
            'failed_count': failed_count,
            'total': len(articles),
            'results': results
        }), 200

    except Exception as e:
        print(f"[API] Error in delete articles: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
