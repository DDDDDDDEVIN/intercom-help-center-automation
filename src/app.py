"""
Main Flask application with webhook endpoint
Step 1: Catch Hook - Trigger by HTTP POST with article ID
"""
from flask import Flask, request, jsonify
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


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
