let articles = [];
let selectedArticles = new Set();
let currentNestedStructure = null;  // Store nested structure for re-rendering

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

        if (data.status === 'success') {
            if (data.nested_structure && Object.keys(data.nested_structure).length > 0) {
                // Use nested structure if available
                articles = data.articles;  // Keep flat list for selection tracking
                currentNestedStructure = data.nested_structure;  // Store for re-rendering
                const orderedStructure = orderNestedStructure(data.nested_structure);
                articleList.innerHTML = renderNestedStructure(orderedStructure);

                // Reattach checkbox listeners
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
            } else {
                // Fallback to flat display
                articles = data.articles;
                currentNestedStructure = null;
                renderArticles();
            }
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

// Render nested structure recursively
function renderNestedStructure(structure, level = 0, pathPrefix = '') {
    let html = '';

    for (const [key, value] of Object.entries(structure)) {
        if (key === 'articles') {
            // Render articles at this level
            html += value.map(article => `
                <div class="article-item" style="margin-left: ${level * 30}px;">
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
                            ${article.category_name ? `<span class="article-category">${escapeHtml(article.category_name)}</span>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            // Render category header with collapse/expand
            // Use full path to create unique ID
            const currentPath = pathPrefix ? `${pathPrefix}-${key}` : key;
            const categoryId = `category-${currentPath.replace(/\s+/g, '-')}`;
            html += `
                <div class="category-group" style="margin-left: ${level * 20}px;">
                    <div class="category-header" onclick="toggleCategory('${categoryId}')">
                        <span class="expand-icon">▼</span>
                        <span class="category-name">${escapeHtml(key)}</span>
                    </div>
                    <div id="${categoryId}" class="category-content">
                        ${renderNestedStructure(value, level + 1, currentPath)}
                    </div>
                </div>
            `;
        }
    }

    return html;
}

// Toggle category visibility
function toggleCategory(categoryId) {
    const element = document.getElementById(categoryId);
    if (!element) return;

    const header = element.previousElementSibling;
    const icon = header.querySelector('.expand-icon');

    // Check if currently collapsed
    const isCollapsed = element.classList.contains('collapsed');

    if (isCollapsed) {
        element.classList.remove('collapsed');
        icon.textContent = '▼';
    } else {
        element.classList.add('collapsed');
        icon.textContent = '▶';
    }
}

// Order nested structure: PV first, ESS second, Other last
function orderNestedStructure(structure) {
    const ordered = {};
    const keys = Object.keys(structure);

    // Define order
    const order = ['PV', 'ESS', 'Other'];

    // Add keys in specified order
    for (const key of order) {
        if (keys.includes(key)) {
            ordered[key] = structure[key];
        }
    }

    // Add any remaining keys that weren't in the order list
    for (const key of keys) {
        if (!order.includes(key)) {
            ordered[key] = structure[key];
        }
    }

    return ordered;
}

// Re-render current view (nested or flat)
function reRenderCurrentView() {
    if (currentNestedStructure) {
        // Re-render nested structure with proper ordering
        const orderedStructure = orderNestedStructure(currentNestedStructure);
        articleList.innerHTML = renderNestedStructure(orderedStructure);

        // Reattach checkbox listeners
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
    } else {
        // Render flat list
        renderArticles();
    }
    updatePublishButton();
}

// Select all articles
function selectAll() {
    selectedArticles = new Set(articles.map(a => a.id));
    reRenderCurrentView();
}

// Deselect all articles
function deselectAll() {
    selectedArticles.clear();
    reRenderCurrentView();
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
