let articles = [];
let selectedArticles = new Set();
let currentNestedStructure = null;  // Store nested structure for re-rendering
let loadedPreviews = new Set();  // Track which previews have been loaded
let publishedArticles = new Set();  // Track which articles are published (by title)

// DOM Elements - Joomla Tab
const articleList = document.getElementById('articleList');
const loading = document.getElementById('loading');
const statusPanel = document.getElementById('statusPanel');
const statusList = document.getElementById('statusList');
const refreshBtn = document.getElementById('refreshBtn');
const selectAllBtn = document.getElementById('selectAllBtn');
const deselectAllBtn = document.getElementById('deselectAllBtn');
const publishBtn = document.getElementById('publishBtn');
const updateBtn = document.getElementById('updateBtn');
const progressPanel = document.getElementById('progressPanel');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');

// DOM Elements - Intercom Tab
const intercomArticleList = document.getElementById('intercomArticleList');
const intercomLoading = document.getElementById('intercomLoading');
const refreshIntercomBtn = document.getElementById('refreshIntercomBtn');
const selectAllIntercomBtn = document.getElementById('selectAllIntercomBtn');
const deselectAllIntercomBtn = document.getElementById('deselectAllIntercomBtn');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');

// Tracking
let selectedIntercomArticles = new Map();
let intercomArticlesLoaded = false;  // Track if Intercom articles have been loaded

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Load Joomla articles on startup
    loadArticles();
    // Intercom articles will lazy-load when switching to that tab

    // Joomla tab event listeners
    refreshBtn.addEventListener('click', loadArticles);
    selectAllBtn.addEventListener('click', selectAll);
    deselectAllBtn.addEventListener('click', deselectAll);
    publishBtn.addEventListener('click', publishSelected);
    updateBtn.addEventListener('click', updateSelected);

    // Intercom tab event listeners
    refreshIntercomBtn.addEventListener('click', loadIntercomArticles);
    selectAllIntercomBtn.addEventListener('click', selectAllIntercom);
    deselectAllIntercomBtn.addEventListener('click', deselectAllIntercom);
    deleteSelectedBtn.addEventListener('click', deleteSelectedIntercom);

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => switchTab(e.target.dataset.tab));
    });
});

// Load published articles from Google Sheets
async function loadPublishedArticles() {
    try {
        const response = await fetch('/api/articles/published');
        const data = await response.json();

        if (data.status === 'success') {
            publishedArticles.clear();
            data.published_titles.forEach(title => publishedArticles.add(title));
            console.log(`Loaded ${publishedArticles.size} published articles from Google Sheets`);
        }
    } catch (error) {
        console.error('Failed to load published articles:', error);
    }
}

// Load articles from API
async function loadArticles() {
    loading.style.display = 'block';
    articleList.innerHTML = '';

    // Load published articles first
    await loadPublishedArticles();

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
            html += value.map(article => {
                const isPublished = publishedArticles.has(article.title);
                const joomlaUrl = `https://rocket.sunwiz.com.au/sites/default/index.php?option=com_content&view=article&id=${article.id}`;
                return `
                <div class="article-item ${isPublished ? 'published' : ''}" style="margin-left: ${level * 30}px;">
                    <input
                        type="checkbox"
                        class="article-checkbox"
                        data-article-id="${article.id}"
                        ${selectedArticles.has(article.id) ? 'checked' : ''}
                    >
                    <div class="article-info">
                        <div class="article-title-row">
                            <div class="article-title">${escapeHtml(article.title)}${isPublished ? ' <span class="published-badge">✓ Published</span>' : ''}</div>
                            <div class="article-actions">
                                <a href="${joomlaUrl}" target="_blank" class="btn-link" title="View original in Joomla">
                                    View Original
                                </a>
                                <button
                                    class="preview-btn"
                                    onclick="togglePreview('${article.id}')"
                                    title="Preview article"
                                >
                                    Preview
                                </button>
                            </div>
                        </div>
                        <div class="article-meta">
                            <span class="article-id">ID: ${article.id}</span>
                            ${article.category_name ? `<span class="article-category">${escapeHtml(article.category_name)}</span>` : ''}
                        </div>
                    </div>
                    <div id="preview-${article.id}" class="article-preview collapsed">
                        <div class="preview-loading">Loading preview...</div>
                    </div>
                </div>
            `;
            }).join('');
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

// Toggle article preview
async function togglePreview(articleId) {
    const previewEl = document.getElementById(`preview-${articleId}`);
    if (!previewEl) return;

    const isCollapsed = previewEl.classList.contains('collapsed');

    if (isCollapsed) {
        // Expand and load content if not already loaded
        previewEl.classList.remove('collapsed');

        if (!loadedPreviews.has(articleId)) {
            // Fetch article content
            try {
                previewEl.innerHTML = '<div class="preview-loading">Loading preview...</div>';

                const response = await fetch(`/api/joomla/articles/${articleId}`);
                const data = await response.json();

                if (data.status === 'success') {
                    previewEl.innerHTML = `
                        <div class="preview-content">
                            <div class="preview-header">
                                <h3>${escapeHtml(data.title)}</h3>
                                <button class="preview-close" onclick="togglePreview('${articleId}')">✕</button>
                            </div>
                            <div class="preview-body">
                                ${data.raw_html}
                            </div>
                        </div>
                    `;
                    loadedPreviews.add(articleId);
                } else {
                    previewEl.innerHTML = `<div class="preview-error">Failed to load preview: ${escapeHtml(data.message)}</div>`;
                }
            } catch (error) {
                previewEl.innerHTML = `<div class="preview-error">Error loading preview: ${escapeHtml(error.message)}</div>`;
            }
        }
    } else {
        // Collapse
        previewEl.classList.add('collapsed');
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
        attachCheckboxListeners();
    } else {
        // Render flat list
        renderArticles();
    }
    updatePublishButton();
}

// Attach checkbox event listeners
function attachCheckboxListeners() {
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

// Update publish and update button states
function updatePublishButton() {
    const isDisabled = selectedArticles.size === 0;
    updateBtn.disabled = isDisabled;
    updateBtn.textContent = `Update Selected (${selectedArticles.size})`;

    // Check if ALL selected articles are already published
    let allPublished = true;

    for (const articleId of selectedArticles) {
        const article = articles.find(a => a.id === articleId);
        if (article && !publishedArticles.has(article.title)) {
            // Found an unpublished article
            allPublished = false;
            break;
        }
    }

    // Disable publish button if no selection OR all selected are published
    publishBtn.disabled = isDisabled || allPublished;
    publishBtn.textContent = allPublished && selectedArticles.size > 0
        ? `Already Published (${selectedArticles.size})`
        : `Publish Selected (${selectedArticles.size})`;
}

// Publish selected articles
async function publishSelected() {
    if (selectedArticles.size === 0) return;

    // Filter out published articles
    const articleIds = Array.from(selectedArticles).filter(id => {
        const article = articles.find(a => a.id === id);
        return article && !publishedArticles.has(article.title);
    });

    if (articleIds.length === 0) {
        alert('All selected articles are already published!');
        return;
    }

    // Show status and progress panels
    statusPanel.style.display = 'block';
    statusList.innerHTML = '';
    showProgress(0, articleIds.length);

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
            let completedCount = 0;
            result.results.forEach(item => {
                completedCount++;
                showProgress(completedCount, articleIds.length);

                const statusElement = document.getElementById(statusItems[item.article_id]);
                if (statusElement) {
                    statusElement.className = `status-item status-${item.status}`;
                    statusElement.querySelector('span:last-child').textContent =
                        item.status === 'success' ? 'Published ✓' :
                        item.status === 'skipped' ? 'Skipped (duplicate)' :
                        `Error: ${item.message}`;
                }

                // Add successfully published articles to publishedArticles Set
                if (item.status === 'success' || item.status === 'skipped') {
                    const article = articles.find(a => a.id === item.article_id);
                    if (article) {
                        publishedArticles.add(article.title);
                    }
                }
            });

            // Re-render the nested structure to show green highlighting
            if (currentNestedStructure) {
                articleList.innerHTML = renderNestedStructure(currentNestedStructure);
                attachCheckboxListeners();
            }
        }
    } catch (error) {
        showError('Failed to publish articles: ' + error.message);
    } finally {
        hideProgress();
        publishBtn.disabled = false;
        updatePublishButton();
    }
}

// Update selected articles (with preview comparison)
async function updateSelected() {
    if (selectedArticles.size === 0) return;

    const articleIds = Array.from(selectedArticles);

    // Disable buttons during operation
    updateBtn.disabled = true;
    updateBtn.textContent = 'Generating Previews...';
    publishBtn.disabled = true;

    try {
        // Step 1: Call API with preview mode to get comparisons
        const response = await fetch('/api/articles/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                article_ids: articleIds,
                preview: true
            })
        });

        const result = await response.json();

        if (result.results) {
            // Collect all comparisons from all articles
            let allComparisons = [];
            let errors = [];

            result.results.forEach(item => {
                if (item.status === 'preview' && item.comparisons) {
                    allComparisons = allComparisons.concat(item.comparisons);
                } else if (item.status === 'error') {
                    errors.push(item);
                }
            });

            if (errors.length > 0) {
                // Show errors in console or status panel
                console.error('Some articles failed to generate preview:', errors);
            }

            if (allComparisons.length > 0) {
                // Show comparison modal with all comparisons (charts, data fields, main articles)
                showComparisonModal(allComparisons);
            } else {
                showError('No previews could be generated');
            }
        }
    } catch (error) {
        showError('Failed to generate previews: ' + error.message);
    } finally {
        updateBtn.disabled = false;
        updateBtn.textContent = 'Update Selected';
        updatePublishButton();
    }
}

// Show comparison modal with old vs new HTML
function showComparisonModal(comparisons) {
    const modal = document.getElementById('comparisonModal');
    const comparisonList = document.getElementById('comparisonList');
    const closeBtn = document.getElementById('closeComparisonBtn');
    const cancelBtn = document.getElementById('cancelComparisonBtn');
    const confirmBtn = document.getElementById('confirmAllBtn');

    // Store comparisons for later confirmation
    window.currentComparisons = comparisons;

    // Build comparison HTML
    let html = '';
    comparisons.forEach((comp, index) => {
        // Determine article type label
        let typeLabel = '';
        let typeBadgeClass = '';
        if (comp.article_type === 'chart') {
            typeLabel = 'Chart';
            typeBadgeClass = 'type-badge-chart';
        } else if (comp.article_type === 'data_field') {
            typeLabel = 'Data Field';
            typeBadgeClass = 'type-badge-field';
        } else if (comp.article_type === 'main_article') {
            typeLabel = 'Main Article';
            typeBadgeClass = 'type-badge-article';
        }

        html += `
            <div class="comparison-item">
                <div class="comparison-item-header">
                    <h3>
                        <span class="type-badge ${typeBadgeClass}">${typeLabel}</span>
                        ${escapeHtml(comp.article_title)}
                    </h3>
                </div>
                <div class="comparison-panels">
                    <div class="comparison-panel">
                        <div class="comparison-panel-header">
                            <h4>Current Version</h4>
                            <label class="choice-label">
                                <input type="radio" name="choice-${index}" value="old" checked>
                                Keep Original
                            </label>
                        </div>
                        <div class="html-preview">
                            ${comp.old_html || '<p style="color: #999;">No existing content</p>'}
                        </div>
                    </div>
                    <div class="comparison-panel">
                        <div class="comparison-panel-header">
                            <h4>New Version</h4>
                            <label class="choice-label">
                                <input type="radio" name="choice-${index}" value="new">
                                Use New Version
                            </label>
                        </div>
                        <div class="html-preview">
                            ${comp.new_html}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    comparisonList.innerHTML = html;

    // Show modal
    modal.style.display = 'flex';

    // Attach event listeners
    closeBtn.onclick = () => {
        modal.style.display = 'none';
    };
    cancelBtn.onclick = () => {
        modal.style.display = 'none';
    };
    confirmBtn.onclick = confirmUpdates;
}

// Apply confirmed updates
async function confirmUpdates() {
    const comparisons = window.currentComparisons;
    if (!comparisons) return;

    const modal = document.getElementById('comparisonModal');
    const confirmBtn = document.getElementById('confirmAllBtn');

    // Disable confirm button
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Applying Updates...';

    // Build update payload based on user selections
    const updates = [];
    comparisons.forEach((comp, index) => {
        const radioButtons = document.getElementsByName(`choice-${index}`);
        let selectedVersion = 'old';  // Default to keeping original

        for (const radio of radioButtons) {
            if (radio.checked) {
                selectedVersion = radio.value;
                break;
            }
        }

        // Only include updates where user chose "new"
        if (selectedVersion === 'new') {
            updates.push({
                article_title: comp.article_title,
                article_type: comp.article_type,
                intercom_article_id: comp.intercom_article_id || '',
                collection_id: comp.collection_id || '',
                html: comp.new_html,
                original_name: comp.original_chart_name || comp.field_name || comp.article_title
            });
        }
    });

    if (updates.length === 0) {
        alert('No updates selected. All articles will keep their original version.');
        modal.style.display = 'none';
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Apply Selected Updates';
        return;
    }

    // Show status panel
    statusPanel.style.display = 'block';
    statusList.innerHTML = '';

    try {
        // Call confirm endpoint
        const response = await fetch('/api/articles/update/confirm', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ updates })
        });

        const result = await response.json();

        if (result.results) {
            // Show status for each update
            result.results.forEach(item => {
                const statusHtml = `
                    <div class="status-item status-${item.status}">
                        <span>${escapeHtml(item.article_title || 'unknown')}</span>
                        <span>${item.status === 'success' ? 'Updated ✓' : `Error: ${item.message}`}</span>
                    </div>
                `;
                statusList.innerHTML += statusHtml;

                // Add to publishedArticles Set (only for main articles, not charts/data fields)
                if (item.status === 'success' && item.article_type === 'main_article') {
                    publishedArticles.add(item.article_title);
                }
            });

            // Re-render to show green highlighting
            if (currentNestedStructure) {
                articleList.innerHTML = renderNestedStructure(currentNestedStructure);
                attachCheckboxListeners();
            }
        }

        // Close modal
        modal.style.display = 'none';
    } catch (error) {
        showError('Failed to apply updates: ' + error.message);
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Apply Selected Updates';
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

// ==================== NEW FEATURES ====================

// Tab switching
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    document.getElementById('joomlaTab').classList.toggle('active', tabName === 'joomla');
    document.getElementById('intercomTab').classList.toggle('active', tabName === 'intercom');

    // Lazy load Intercom articles when first switching to that tab
    if (tabName === 'intercom' && !intercomArticlesLoaded) {
        loadIntercomArticles();
    }
}

// Load Intercom articles from all collections
async function loadIntercomArticles() {
    intercomLoading.style.display = 'block';
    intercomArticleList.innerHTML = '';
    selectedIntercomArticles.clear();
    deleteSelectedBtn.disabled = true;

    try {
        const response = await fetch('/api/intercom/articles');
        const data = await response.json();

        if (data.status === 'success') {
            renderIntercomArticles(data.collections);
            intercomArticlesLoaded = true;  // Mark as loaded
        } else {
            showIntercomError('Failed to load Intercom articles: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        showIntercomError('Network error: ' + error.message);
    } finally {
        intercomLoading.style.display = 'none';
    }
}

// Render Intercom articles grouped by collection
function renderIntercomArticles(collections) {
    if (!collections || Object.keys(collections).length === 0) {
        intercomArticleList.innerHTML = `
            <div class="empty-state">
                <p>No articles found in Intercom</p>
            </div>
        `;
        return;
    }

    let html = '';
    for (const [collectionName, articles] of Object.entries(collections)) {
        html += `
            <div class="intercom-collection">
                <h3 class="intercom-collection-title">${escapeHtml(collectionName)} (${articles.length})</h3>
                <div class="intercom-articles">
                    ${articles.map(article => `
                        <div class="intercom-article-item">
                            <input
                                type="checkbox"
                                class="intercom-checkbox"
                                data-article-id="${article.id}"
                                data-article-title="${escapeHtml(article.title)}"
                                data-collection="${escapeHtml(collectionName)}"
                            >
                            <div class="intercom-article-info">
                                <div class="intercom-article-title">${escapeHtml(article.title)}</div>
                                <div class="intercom-article-meta">
                                    <span>ID: ${article.id}</span>
                                    ${article.url ? `<a href="${article.url}" target="_blank" class="intercom-link">View in Intercom →</a>` : ''}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    intercomArticleList.innerHTML = html;

    // Attach checkbox listeners
    document.querySelectorAll('.intercom-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const articleId = e.target.dataset.articleId;
            const articleTitle = e.target.dataset.articleTitle;
            const collection = e.target.dataset.collection;

            if (e.target.checked) {
                selectedIntercomArticles.set(articleId, {
                    title: articleTitle,
                    collection: collection
                });
            } else {
                selectedIntercomArticles.delete(articleId);
            }
            updateDeleteButton();
        });
    });
}

// Update delete button state
function updateDeleteButton() {
    const isDisabled = selectedIntercomArticles.size === 0;
    deleteSelectedBtn.disabled = isDisabled;
    deleteSelectedBtn.textContent = `Delete Selected (${selectedIntercomArticles.size})`;
}

// Select all Intercom articles
function selectAllIntercom() {
    document.querySelectorAll('.intercom-checkbox').forEach(checkbox => {
        checkbox.checked = true;
        const articleId = checkbox.dataset.articleId;
        const articleTitle = checkbox.dataset.articleTitle;
        const collection = checkbox.dataset.collection;
        selectedIntercomArticles.set(articleId, {
            title: articleTitle,
            collection: collection
        });
    });
    updateDeleteButton();
}

// Deselect all Intercom articles
function deselectAllIntercom() {
    document.querySelectorAll('.intercom-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    selectedIntercomArticles.clear();
    updateDeleteButton();
}

// Delete selected Intercom articles
async function deleteSelectedIntercom() {
    if (selectedIntercomArticles.size === 0) return;

    // Build articles array with metadata
    const articles = Array.from(selectedIntercomArticles.entries()).map(([id, meta]) => ({
        id: id,
        title: meta.title,
        collection: meta.collection
    }));

    if (!confirm(`Are you sure you want to delete ${articles.length} article(s) from Intercom and Google Sheets? This action cannot be undone.`)) {
        return;
    }

    deleteSelectedBtn.disabled = true;
    deleteSelectedBtn.textContent = 'Deleting...';

    try {
        const response = await fetch('/api/intercom/articles/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({articles: articles})
        });

        const result = await response.json();

        if (result.status === 'success') {
            alert(`Successfully deleted ${result.deleted_count} article(s)`);
            loadIntercomArticles(); // Refresh the list
        } else {
            alert('Failed to delete articles: ' + (result.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Network error: ' + error.message);
    } finally {
        deleteSelectedBtn.disabled = false;
        updateDeleteButton();
    }
}

// Show error in Intercom tab
function showIntercomError(message) {
    intercomArticleList.innerHTML = `
        <div class="empty-state">
            <p style="color: #d32f2f;">Error</p>
            <small>${escapeHtml(message)}</small>
        </div>
    `;
}

// Show progress bar
function showProgress(current, total) {
    progressPanel.style.display = 'block';
    const percentage = total > 0 ? (current / total) * 100 : 0;
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${current} / ${total} completed`;
}

// Hide progress bar
function hideProgress() {
    progressPanel.style.display = 'none';
    progressBar.style.width = '0%';
    progressText.textContent = '0 / 0 completed';
}
