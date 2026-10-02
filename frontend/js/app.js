document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const channelInput = document.getElementById('channel-input');
  const channelCountBadge = document.getElementById('channel-count-badge');
  const contentTypeInput = document.getElementById('content-type-input');
  const typeTabs = document.querySelectorAll('.type-tab');
  const percentageSlider = document.getElementById('percentage-slider');
  const percentageVal = document.getElementById('percentage-val');
  const presetPills = document.querySelectorAll('.preset-pill');
  const chipButtons = document.querySelectorAll('.chip-btn');
  const metricCards = document.querySelectorAll('.metric-card');
  const maxVideosInput = document.getElementById('max-videos-input');
  const minViewsInput = document.getElementById('min-views-input');
  const fetchCommentsToggle = document.getElementById('fetch-comments-toggle');
  const scrapeForm = document.getElementById('scrape-form');
  const startScrapeBtn = document.getElementById('start-scrape-btn');

  // Status & Console Elements
  const overallStatusBadge = document.getElementById('overall-status-badge');
  const overallStatusText = document.getElementById('overall-status-text');
  const progressBar = document.getElementById('progress-bar');
  const progressPercentLabel = document.getElementById('progress-percent-label');
  const terminalConsole = document.getElementById('terminal-console');

  // Stat counters
  const statChannels = document.getElementById('stat-channels');
  const statTotalScanned = document.getElementById('stat-total-scanned');
  const statTopExtracted = document.getElementById('stat-top-extracted');
  const statTotalViews = document.getElementById('stat-total-views');

  // Results & Export Elements
  const resultsSummaryText = document.getElementById('results-summary-text');
  const resultsToolbar = document.getElementById('results-toolbar');
  const videosGrid = document.getElementById('videos-grid');
  const videosTableContainer = document.getElementById('videos-table-container');
  const videosTableBody = document.getElementById('videos-table-body');
  const videoSearchInput = document.getElementById('video-search-input');
  const viewGridBtn = document.getElementById('view-grid-btn');
  const viewTableBtn = document.getElementById('view-table-btn');

  const downloadTxtBtn = document.getElementById('download-txt-btn');
  const downloadDetailedTxtBtn = document.getElementById('download-detailed-txt-btn');
  const downloadCsvBtn = document.getElementById('download-csv-btn');
  const copyAllBtn = document.getElementById('copy-all-btn');
  const toast = document.getElementById('toast');

  // State
  let currentResults = null;
  let allVideosData = [];
  let isScraping = false;
  let activeView = 'grid';

  // Update channel counter badge
  function updateChannelBadge() {
    const lines = channelInput.value
      .split(/[\n,]+/)
      .map(s => s.trim())
      .filter(Boolean);
    channelCountBadge.textContent = `${lines.length} channel${lines.length === 1 ? '' : 's'}`;
  }

  channelInput.addEventListener('input', updateChannelBadge);

  // Content type selector (Shorts vs Regular)
  typeTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      typeTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const type = tab.getAttribute('data-type');
      contentTypeInput.value = type;
      
      const isShorts = type === 'shorts';
      startScrapeBtn.querySelector('.btn-text').textContent = isShorts ? 'Start Extracting Top Shorts' : 'Start Extracting Top Videos';
      downloadTxtBtn.title = isShorts ? 'Download clean .txt with 1 Shorts URL per line' : 'Download clean .txt with 1 Video URL per line';
    });
  });

  // Quick preset chips
  chipButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const channel = btn.getAttribute('data-channel');
      const current = channelInput.value.trim();
      if (!current) {
        channelInput.value = channel;
      } else if (!current.includes(channel)) {
        channelInput.value = current + '\n' + channel;
      }
      updateChannelBadge();
    });
  });

  // Slider synchronization
  percentageSlider.addEventListener('input', (e) => {
    const val = e.target.value;
    percentageVal.textContent = val;
    presetPills.forEach(pill => {
      if (pill.getAttribute('data-pct') === val) {
        pill.classList.add('active');
      } else {
        pill.classList.remove('active');
      }
    });
  });

  presetPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const pct = pill.getAttribute('data-pct');
      percentageSlider.value = pct;
      percentageVal.textContent = pct;
      presetPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });

  // Metric selector radios
  metricCards.forEach(card => {
    const radio = card.querySelector('input[type="radio"]');
    card.addEventListener('click', () => {
      metricCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      radio.checked = true;
      if (radio.value === 'comments' || radio.value === 'combined') {
        fetchCommentsToggle.checked = true;
      }
    });
  });

  // Terminal logging
  function logToConsole(message, type = 'info') {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    const time = new Date().toLocaleTimeString();
    line.innerHTML = `<span class="prompt">[${time}]</span> ${escapeHtml(message)}`;
    terminalConsole.appendChild(line);
    terminalConsole.scrollTop = terminalConsole.scrollHeight;
  }

  function clearConsole() {
    terminalConsole.innerHTML = '';
  }

  function setStatus(status, text) {
    const dot = overallStatusBadge.querySelector('.status-dot');
    dot.className = `status-dot ${status}`;
    overallStatusText.textContent = text;
  }

  function updateProgress(percent) {
    const p = Math.min(100, Math.max(0, percent));
    progressBar.style.width = `${p}%`;
    progressPercentLabel.textContent = `${p}%`;
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3200);
  }

  function formatNumber(num) {
    if (!num || isNaN(num)) return '0';
    return Number(num).toLocaleString();
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Form Submission
  scrapeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (isScraping) return;

    const rawInput = channelInput.value.trim();
    const channels = rawInput
      .split(/[\n,]+/)
      .map(s => s.trim())
      .filter(Boolean);

    if (channels.length === 0) {
      showToast('Please enter at least one YouTube channel handle or URL.');
      channelInput.focus();
      return;
    }

    const contentType = contentTypeInput.value || 'shorts';
    const percentage = parseFloat(percentageSlider.value) || 10;
    const selectedMetricRadio = document.querySelector('input[name="metric"]:checked');
    const metric = selectedMetricRadio ? selectedMetricRadio.value : 'views';
    const maxVideos = parseInt(maxVideosInput.value, 10) || 0;
    const minViews = Math.max(0, parseInt(minViewsInput.value, 10) || 0);
    const fetchComments = fetchCommentsToggle.checked;
    const typeLabel = contentType === 'shorts' ? 'Shorts' : 'Videos';

    // UI state
    isScraping = true;
    startScrapeBtn.disabled = true;
    startScrapeBtn.querySelector('.btn-text').textContent = `Extracting ${typeLabel}...`;
    setStatus('running', 'Scraping...');
    updateProgress(5);
    clearConsole();
    logToConsole(`Target: ${typeLabel.toUpperCase()} Only | Channels: ${channels.length}`, 'info');
    logToConsole(`Criteria: Top ${percentage}% ranked by ${metric.toUpperCase()}`, 'info');
    if (minViews > 0) logToConsole(`Minimum views: ${formatNumber(minViews)}`, 'info');

    statChannels.textContent = '0';
    statTotalScanned.textContent = '0';
    statTopExtracted.textContent = '0';
    statTotalViews.textContent = '0';
    downloadTxtBtn.disabled = true;
    downloadDetailedTxtBtn.disabled = true;
    downloadCsvBtn.disabled = true;
    copyAllBtn.disabled = true;

    // SSE Stream
    const params = new URLSearchParams({
      channels: channels.join(','),
      content_type: contentType,
      top_percentage: percentage,
      metric: metric,
      max_videos_per_channel: maxVideos,
      min_views: minViews,
      fetch_comments: fetchComments
    });

    const eventSource = new EventSource(`/api/scrape/stream?${params.toString()}`);

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);

        if (payload.type === 'progress') {
          logToConsole(payload.message, 'info');
          if (payload.progress_pct !== undefined) {
            updateProgress(payload.progress_pct);
          }
        } else if (payload.type === 'channel_done') {
          logToConsole(payload.message, 'success');
          if (payload.progress_pct !== undefined) {
            updateProgress(payload.progress_pct);
          }
          statChannels.textContent = payload.channel_index || '1';
        } else if (payload.type === 'error') {
          logToConsole(payload.message, 'error');
        } else if (payload.type === 'fatal_error') {
          logToConsole(`Fatal Error: ${payload.message}`, 'error');
          setStatus('error', 'Error');
          showToast(`Error: ${payload.message}`);
          eventSource.close();
          finishScrape(null);
        } else if (payload.type === 'complete') {
          eventSource.close();
          updateProgress(100);
          setStatus('success', 'Completed');
          logToConsole(`🎉 Scraping finished! Extracted ${payload.data.total_top_videos} top ${typeLabel.toLowerCase()}.`, 'success');
          finishScrape(payload.data);
        }
      } catch (err) {
        console.error('SSE error', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE connection closed', err);
      eventSource.close();
      if (isScraping) {
        finishScrape(null);
      }
    };
  });

  function finishScrape(data) {
    isScraping = false;
    startScrapeBtn.disabled = false;
    const isShorts = contentTypeInput.value === 'shorts';
    startScrapeBtn.querySelector('.btn-text').textContent = isShorts ? 'Start Extracting Top Shorts' : 'Start Extracting Top Videos';

    if (!data || !data.all_top_videos || data.all_top_videos.length === 0) {
      if (data) {
        logToConsole('No matching items found.', 'error');
      }
      return;
    }

    currentResults = data;
    allVideosData = data.all_top_videos || [];

    statChannels.textContent = data.channels_processed || 0;
    statTotalScanned.textContent = formatNumber(data.total_videos_scanned ?? data.total_videos_scraped);
    statTopExtracted.textContent = formatNumber(data.total_top_videos);
    
    const totalViews = allVideosData.reduce((acc, v) => acc + (v.view_count || 0), 0);
    statTotalViews.textContent = formatNumber(totalViews);

    downloadTxtBtn.disabled = false;
    downloadDetailedTxtBtn.disabled = false;
    downloadCsvBtn.disabled = false;
    copyAllBtn.disabled = false;
    resultsToolbar.style.display = 'flex';

    const itemLabel = isShorts ? 'shorts' : 'videos';
    const minViewsText = data.min_views > 0 ? `, minimum ${formatNumber(data.min_views)} views` : '';
    resultsSummaryText.textContent = `Found ${allVideosData.length} top ${itemLabel} from ${data.channels_processed} channel(s) (Top ${data.percentage}% by ${data.metric.toUpperCase()}${minViewsText})`;

    renderVideos(allVideosData);
    showToast(`Successfully extracted ${allVideosData.length} top ${itemLabel} URLs!`);
  }

  // Render Videos / Shorts
  function renderVideos(videos) {
    const isShorts = contentTypeInput.value === 'shorts';

    if (!videos || videos.length === 0) {
      videosGrid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <p>No items match your search filter.</p>
        </div>
      `;
      videosTableBody.innerHTML = '';
      return;
    }

    // Grid View
    videosGrid.innerHTML = videos.map(video => {
      const views = formatNumber(video.view_count);
      const comments = formatNumber(video.comment_count);
      const thumb = video.thumbnail || `https://i.ytimg.com/vi/${video.id}/hqdefault.jpg`;
      const rank = video.rank || '#';
      const pct = video.percentile_pct ? `Top ${video.percentile_pct}%` : 'Top';
      const watchText = isShorts ? '⚡ Open Short' : '▶ Watch';

      return `
        <div class="video-card">
          <div class="thumb-container">
            <img src="${thumb}" alt="${escapeHtml(video.title)}" class="thumb-img" loading="lazy" onerror="this.src='https://via.placeholder.com/320x180/1a1a24/ffffff?text=Video';">
            <div class="rank-badge">#${rank}</div>
            <div class="percentile-badge">${pct}</div>
          </div>
          <div class="video-content">
            <h3 class="video-title" title="${escapeHtml(video.title)}">${escapeHtml(video.title)}</h3>
            <div class="video-channel">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              ${escapeHtml(video.channel)}
            </div>
            <div class="video-metrics-row">
              <span class="metric-badge views" title="Views">
                👁️ ${views}
              </span>
              <span class="metric-badge comments" title="Comments">
                💬 ${comments}
              </span>
            </div>
            <div class="card-actions">
              <a href="${video.url}" target="_blank" rel="noopener noreferrer" class="btn-card-action watch">
                ${watchText}
              </a>
              <button class="btn-card-action copy-single-btn" data-url="${video.url}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy Link
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Table View
    videosTableBody.innerHTML = videos.map(video => {
      const views = formatNumber(video.view_count);
      const comments = formatNumber(video.comment_count);
      const thumb = video.thumbnail || `https://i.ytimg.com/vi/${video.id}/hqdefault.jpg`;
      const rank = video.rank || '-';
      const pct = video.percentile_pct ? `${video.percentile_pct}%` : '-';

      return `
        <tr>
          <td><strong style="font-family: var(--font-mono); color: #ff3366;">#${rank}</strong></td>
          <td>
            <div class="table-video-cell">
              <img src="${thumb}" alt="" class="table-thumb" onerror="this.style.display='none'">
              <div class="table-title" title="${escapeHtml(video.title)}">${escapeHtml(video.title)}</div>
            </div>
          </td>
          <td>${escapeHtml(video.channel)}</td>
          <td><span style="color: #60a5fa; font-family: var(--font-mono);">${views}</span></td>
          <td><span style="color: #f472b6; font-family: var(--font-mono);">${comments}</span></td>
          <td><span class="percentile-badge" style="position: static; display: inline-block;">${pct}</span></td>
          <td>
            <div style="display: flex; gap: 0.4rem;">
              <a href="${video.url}" target="_blank" class="btn-card-action watch" style="padding: 0.3rem 0.6rem;">Open</a>
              <button class="btn-card-action copy-single-btn" data-url="${video.url}" style="padding: 0.3rem 0.6rem;">Copy</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    document.querySelectorAll('.copy-single-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = btn.getAttribute('data-url');
        navigator.clipboard.writeText(url).then(() => {
          showToast('Copied URL to clipboard!');
        });
      });
    });
  }

  // Search Filter
  videoSearchInput.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
      renderVideos(allVideosData);
      return;
    }
    const filtered = allVideosData.filter(v => 
      (v.title && v.title.toLowerCase().includes(q)) ||
      (v.channel && v.channel.toLowerCase().includes(q))
    );
    renderVideos(filtered);
  });

  // View switchers
  viewGridBtn.addEventListener('click', () => {
    activeView = 'grid';
    viewGridBtn.classList.add('active');
    viewTableBtn.classList.remove('active');
    videosGrid.style.display = 'grid';
    videosTableContainer.style.display = 'none';
  });

  viewTableBtn.addEventListener('click', () => {
    activeView = 'table';
    viewTableBtn.classList.add('active');
    viewGridBtn.classList.remove('active');
    videosGrid.style.display = 'none';
    videosTableContainer.style.display = 'block';
  });

  // Exports
  downloadTxtBtn.addEventListener('click', () => {
    window.location.href = '/api/export/txt?mode=plain';
    showToast('Downloading Top Shorts URLs TXT file...');
  });

  downloadDetailedTxtBtn.addEventListener('click', () => {
    window.location.href = '/api/export/txt?mode=detailed';
    showToast('Downloading Detailed TXT file...');
  });

  downloadCsvBtn.addEventListener('click', () => {
    window.location.href = '/api/export/csv';
    showToast('Downloading CSV spreadsheet...');
  });

  copyAllBtn.addEventListener('click', () => {
    if (!allVideosData || allVideosData.length === 0) return;
    const urls = allVideosData.map(v => v.url).join('\n');
    navigator.clipboard.writeText(urls).then(() => {
      showToast(`Copied all ${allVideosData.length} URLs to clipboard!`);
    }).catch(() => {
      showToast('Failed to copy to clipboard.');
    });
  });
});
