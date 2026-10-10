document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const urlInput = document.getElementById('urlInput');
  const btnPaste = document.getElementById('btnPaste');
  const btnConvert = document.getElementById('btnConvert');
  const urlError = document.getElementById('urlError');
  const resultSection = document.getElementById('resultSection');

  // Video Info Elements
  const videoThumb = document.getElementById('videoThumb');
  const videoDuration = document.getElementById('videoDuration');
  const videoTitle = document.getElementById('videoTitle');
  const videoUploaderText = document.getElementById('videoUploaderText');
  const videoViewsText = document.getElementById('videoViewsText');

  // Tables
  const audioTableBody = document.getElementById('audioTableBody');
  const videoTableBody = document.getElementById('videoTableBody');
  const otherTableBody = document.getElementById('otherTableBody');

  // Tabs
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  // Modal elements
  const progressModal = document.getElementById('progressModal');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalFormatBadge = document.getElementById('modalFormatBadge');
  const modalVideoTitle = document.getElementById('modalVideoTitle');
  const progressBar = document.getElementById('progressBar');
  const progressPercent = document.getElementById('progressPercent');
  const progressSpeed = document.getElementById('progressSpeed');
  const progressEta = document.getElementById('progressEta');
  const modalStatusText = document.getElementById('modalStatusText');
  const modalCompletedActions = document.getElementById('modalCompletedActions');
  const btnDirectDownload = document.getElementById('btnDirectDownload');
  const modalFileSize = document.getElementById('modalFileSize');
  const btnOpenLocalFolder = document.getElementById('btnOpenLocalFolder');

  // History & Header
  const historyList = document.getElementById('historyList');
  const btnRefreshHistory = document.getElementById('btnRefreshHistory');
  const btnOpenDownloadsFolder = document.getElementById('btnOpenDownloadsFolder');

  let currentVideoData = null;
  let activeTaskId = null;
  let pollInterval = null;

  // Tab switching
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const tabName = btn.getAttribute('data-tab');
      const targetPane = document.getElementById(`tab-${tabName}`);
      if (targetPane) {
        targetPane.classList.add('active');
      }
    });
  });

  // Paste from clipboard
  btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        fetchVideoInfo();
      }
    } catch (err) {
      urlInput.focus();
    }
  });

  // Enter key trigger
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      fetchVideoInfo();
    }
  });

  btnConvert.addEventListener('click', fetchVideoInfo);

  function showError(msg) {
    urlError.textContent = msg;
    urlError.style.display = 'block';
  }

  function hideError() {
    urlError.textContent = '';
    urlError.style.display = 'none';
  }

  // Fetch Video Information
  async function fetchVideoInfo() {
    const url = urlInput.value.trim();
    hideError();

    if (!url) {
      showError('Vui lòng dán đường dẫn video YouTube hợp lệ.');
      return;
    }

    if (!url.includes('youtube.com/') && !url.includes('youtu.be/')) {
      showError('Đường dẫn không phải từ YouTube. Vui lòng kiểm tra lại.');
      return;
    }

    btnConvert.classList.add('loading');
    btnConvert.disabled = true;

    try {
      const res = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Không thể lấy thông tin video');
      }

      currentVideoData = data;
      renderVideoInfo(data);
      resultSection.classList.remove('hidden');

      // Scroll smoothly to result
      resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    } catch (err) {
      showError(err.message || 'Có lỗi xảy ra khi phân tích video.');
    } finally {
      btnConvert.classList.remove('loading');
      btnConvert.disabled = false;
    }
  }

  // Render Video Preview & Option Tables
  function renderVideoInfo(data) {
    videoThumb.src = data.thumbnail || 'https://via.placeholder.com/320x180?text=No+Thumbnail';
    videoDuration.textContent = data.duration_str || '0:00';
    videoTitle.textContent = data.title;
    videoUploaderText.textContent = data.uploader;
    videoViewsText.textContent = `${data.view_count} lượt xem`;

    // Render Audio Table
    renderTableRows(audioTableBody, data.audio_options, 'audio');

    // Render Video Table
    renderTableRows(videoTableBody, data.video_options, 'video');

    // Render Other Table
    renderTableRows(otherTableBody, data.other_options, 'other');
  }

  function renderTableRows(tbody, options, type) {
    tbody.innerHTML = '';
    if (!options || options.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: #888;">Không có định dạng phù hợp</td></tr>`;
      return;
    }

    options.forEach(opt => {
      const tr = document.createElement('tr');
      
      const tdType = document.createElement('td');
      tdType.innerHTML = `<strong>${opt.label}</strong>`;

      const tdFormat = document.createElement('td');
      tdFormat.innerHTML = `${opt.format_display || 'Auto'} <span class="size-hint">(~${opt.size_approx})</span>`;

      const tdAction = document.createElement('td');
      const btn = document.createElement('button');
      btn.className = 'btn-download-action';
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
        </svg>
        Download
      `;

      btn.addEventListener('click', () => {
        startDownload(type, opt);
      });

      tdAction.appendChild(btn);

      tr.appendChild(tdType);
      tr.appendChild(tdFormat);
      tr.appendChild(tdAction);
      tbody.appendChild(tr);
    });
  }

  // Start Download & Open Progress Modal
  async function startDownload(type, opt) {
    if (!currentVideoData) return;

    // Reset and open modal
    activeTaskId = null;
    if (pollInterval) clearInterval(pollInterval);

    modalTitle.textContent = 'Đang chuyển đổi tệp tin...';
    modalFormatBadge.textContent = opt.label;
    modalVideoTitle.textContent = currentVideoData.title;
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    progressSpeed.textContent = '0 KB/s';
    progressEta.textContent = 'ETA: --:--';
    modalStatusText.textContent = 'Đang gửi yêu cầu tới máy chủ...';
    modalCompletedActions.classList.add('hidden');
    progressModal.classList.remove('hidden');

    try {
      const res = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentVideoData.original_url,
          type: type,
          quality: opt.quality,
          format: opt.format,
          save_to_downloads: true
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Không thể bắt đầu tải xuống');
      }

      activeTaskId = data.task_id;
      // Start polling progress
      pollInterval = setInterval(checkProgress, 600);

    } catch (err) {
      modalStatusText.textContent = `Lỗi: ${err.message}`;
      modalStatusText.style.color = '#dc2626';
    }
  }

  async function checkProgress() {
    if (!activeTaskId) return;

    try {
      const res = await fetch(`/api/progress/${activeTaskId}`);
      if (!res.ok) return;

      const task = await res.json();

      progressBar.style.width = `${task.progress}%`;
      progressPercent.textContent = task.percent_str || `${task.progress}%`;
      progressSpeed.textContent = task.speed_str || '0 KB/s';
      progressEta.textContent = task.eta_str ? `ETA: ${task.eta_str}` : 'ETA: --:--';
      modalStatusText.textContent = task.status_text || 'Đang xử lý...';

      if (task.status === 'completed') {
        clearInterval(pollInterval);
        modalTitle.textContent = 'Chuyển đổi hoàn tất!';
        progressBar.style.width = '100%';
        progressPercent.textContent = '100%';
        modalStatusText.textContent = 'Tệp đã sẵn sàng! Đang tự động lưu về máy...';
        modalFileSize.textContent = task.filesize_str || 'File';
        btnDirectDownload.href = `/api/file/${activeTaskId}`;
        modalCompletedActions.classList.remove('hidden');

        // Automatically trigger browser download
        const hiddenLink = document.createElement('a');
        hiddenLink.href = `/api/file/${activeTaskId}`;
        hiddenLink.download = task.filename || 'download';
        document.body.appendChild(hiddenLink);
        hiddenLink.click();
        document.body.removeChild(hiddenLink);

        loadHistory();

      } else if (task.status === 'error') {
        clearInterval(pollInterval);
        modalTitle.textContent = 'Đã xảy ra lỗi!';
        modalStatusText.textContent = task.error_message || 'Không thể hoàn thành quá trình tải.';
        modalStatusText.style.color = '#dc2626';
      }

    } catch (err) {
      console.error('Error polling progress:', err);
    }
  }

  // Open folder action
  btnOpenLocalFolder.addEventListener('click', async () => {
    if (!activeTaskId) return;
    try {
      await fetch(`/api/open-folder/${activeTaskId}`, { method: 'POST' });
    } catch (err) {
      alert('Không thể mở thư mục: ' + err.message);
    }
  });

  btnOpenDownloadsFolder.addEventListener('click', async () => {
    // Open default folder
    if (activeTaskId) {
      fetch(`/api/open-folder/${activeTaskId}`, { method: 'POST' });
    } else {
      window.open('/api/history', '_blank');
    }
  });

  btnCloseModal.addEventListener('click', () => {
    progressModal.classList.add('hidden');
    if (pollInterval) clearInterval(pollInterval);
  });

  progressModal.addEventListener('click', (e) => {
    if (e.target === progressModal) {
      progressModal.classList.add('hidden');
      if (pollInterval) clearInterval(pollInterval);
    }
  });

  // History loader
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      if (!res.ok) return;

      const items = await res.json();
      if (!items || items.length === 0) {
        historyList.innerHTML = `<div class="empty-history">Chưa có tệp nào được tải xuống. Hãy dán một link YouTube để bắt đầu!</div>`;
        return;
      }

      historyList.innerHTML = '';
      items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.innerHTML = `
          <div class="history-left">
            <span class="history-badge ${item.type === 'audio' ? 'audio' : 'video'}">${item.format}</span>
            <div>
              <div class="history-title" title="${item.title}">${item.filename}</div>
              <div class="history-meta">${item.quality} • ${item.filesize_str} • ${item.time}</div>
            </div>
          </div>
          <div class="history-actions">
            <a href="/api/file/${item.task_id}" class="btn-icon" title="Tải lại">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
              </svg>
              Tải lại
            </a>
            <button class="btn-icon btn-open-hist" data-task="${item.task_id}" title="Mở trên máy">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
              Mở file
            </button>
          </div>
        `;

        div.querySelector('.btn-open-hist').addEventListener('click', () => {
          fetch(`/api/open-folder/${item.task_id}`, { method: 'POST' });
        });

        historyList.appendChild(div);
      });
    } catch (err) {
      console.error('Error loading history:', err);
    }
  }

  btnRefreshHistory.addEventListener('click', loadHistory);
  loadHistory();
});
