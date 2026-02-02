let articles = [];
let selectedArticles = new Set();

// DOM Elements
const articleList = document.getElementById('articleList');
const loading = document.getElementById('loading');
const statusPanel = document.getElementById('statusPanel');
const statusList = document.getElementById('statusList');
const refreshBtn = document.getElementById('refreshBtn');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const publishBtn = document.getElementById('publishBtn');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadArticles();

    refreshBtn.addEventListener('click', loadArticles);
    selectAllBtn.addEventListener('click', selectAll);
    deselectAllBtn.addEventListener('click', deselectAll);
    publishBtn.addEventListener('click', publishSelected);
});

// Load articles from API
async function loadArticles() {
    loading.style.display = 'block';
    articleList.innerHTML = '';

    try {
        const response = await fetch('/api/joomla/articles');
        const data = await response.json();

        if (data.status === 'success' && data.articles) {
            // Articles are already deduplicated by the backend
            articles = data.articles;
            renderArticles();
        } else {
            showError('Failed to load articles: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        loading.style.display = 'none';
    }
}

// Render articles list
function renderArticles() {
    if (articles.length === 0) {
        articleList.innerHTML = `
            <div class="empty-state">
                <p>No published articles found</p>
                <small>Check your Joomla connection settings</small>
            </div>
        `;
        return;
    }

    articleList.innerHTML = articles.map(article => `
        <div class="article-item">
            <input
                type="checkbox"
                class="article-checkbox"
                data-article-id="${article.id}"
                ${selectedArticles.has(article.id) ? 'checked' : ''}
            >
            <div class="article-info">
                <div class="article-title">${escapeHtml(article.title)}</div>
                <div class="article-meta">
                    <span class="article-id">ID: ${article.id}</span>
                    ${article.category_name ? `<span class="article-category">Category: ${escapeHtml(article.category_name)}</span>` : ''}
                    ${article.alias ? `<span>Alias: ${escapeHtml(article.alias)}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');

    // Attach checkbox listeners
    document.querySelectorAll('.article-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const articleId = e.target.dataset.articleId;
            if (e.target.checked) {
                selectedArticles.add(articleId);
            } else {
                selectedArticles.delete(articleId);
            }
            updatePublishButton();
        });
    });

    updatePublishButton();
}

// Select all articles
function selectAll() {
    selectedArticles = new Set(articles.map(a => a.id));
    renderArticles();
}

// Deselect all articles
function deselectAll() {
    selectedArticles.clear();
    renderArticles();
}

// Update publish button state
function updatePublishButton() {
    publishBtn.disabled = selectedArticles.size === 0;
    publishBtn.textContent = `Publish Selected (${selectedArticles.size})`;
}

// Publish selected articles
async function publishSelected() {
    if (selectedArticles.size === 0) return;

    const articleIds = Array.from(selectedArticles);

    // Show status panel
    statusPanel.style.display = 'block';
    statusList.innerHTML = '';

    // Disable publish button
    publishBtn.disabled = true;
    publishBtn.textContent = 'Publishing...';

    // Create status items
    const statusItems = {};
    articleIds.forEach(id => {
        const article = articles.find(a => a.id === id);
        const statusId = `status-${id}`;
        statusList.innerHTML += `
            <div id="${statusId}" class="status-item status-pending">
                <span>${escapeHtml(article.title)}</span>
                <span>Pending...</span>
            </div>
        `;
        statusItems[id] = statusId;
    });

    // Process each article
    try {
        const response = await fetch('/api/articles/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ article_ids: articleIds })
        });

        const result = await response.json();

        if (result.results) {
            result.results.forEach(item => {
                const statusElement = document.getElementById(statusItems[item.article_id]);
                if (statusElement) {
                    statusElement.className = `status-item status-${item.status}`;
                    statusElement.querySelector('span:last-child').textContent =
                        item.status === 'success' ? 'Published ✓' :
                        item.status === 'skipped' ? 'Skipped (duplicate)' :
                        `Error: ${item.message}`;
                }
            });
        }
    } catch (error) {
        showError('Failed to publish articles: ' + error.message);
    } finally {
        publishBtn.disabled = false;
        updatePublishButton();
    }
}

// Show error message
function showError(message) {
    articleList.innerHTML = `
        <div class="empty-state">
            <p style="color: #d32f2f;">Error</p>
            <small>${escapeHtml(message)}</small>
        </div>
    `;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
