let streamSource = null;
    let streamTaskId = '';
    let liveConsoleLines = [];
    let liveConsoleFollow = true;
    let refreshTimer = null;
    let captureStatusTimer = null;
    let taskPageOffset = 0;
    const taskPageSize = 10;
    const RECENT_TASK_REFRESH_MS = 5000;
    const MAX_CONSOLE_LINES = 2000;
    const CONSOLE_STICKY_THRESHOLD_PX = 16;
    let compareDisplayMode = 'full';

    async function api(path, method = 'GET', body = null) {
      const options = { method, headers: {} };
      if (body) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
      }
      const res = await fetch(path, options);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
      return data;
    }

    function toNumber(value, fallback = 0) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    }

    function joinParts(parts) {
      return (parts || [])
        .filter((part) => String(part ?? '').trim().length > 0)
        .join(' | ');
    }

    function formatError(err) {
      return 'Error: ' + (err && err.message ? err.message : String(err));
    }

    function setTopActionStatus(message) {
      document.getElementById('topActionStatus').textContent = String(message || '');
    }

    function formatBrowserTime(epochSeconds) {
      const parsed = Number(epochSeconds);
      if (!Number.isFinite(parsed) || parsed <= 0) return '-';
      return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(new Date(parsed * 1000));
    }

    function statusTone(status, isRunning) {
      if (isRunning) return 'running';
      const normalized = String(status || '').toLowerCase();
      if (normalized === 'completed') return 'success';
      if (normalized === 'failed' || normalized === 'cancelled') return 'failed';
      return 'idle';
    }

    function setCaptureStatus(statusPayload, isRunning = false) {
      const panel = document.getElementById('captureStatusPanel');
      const spinner = document.getElementById('captureStatusSpinner');
      const label = document.getElementById('captureStatusLabel');
      const headline = document.getElementById('captureStatusHeadline');
      const summary = document.getElementById('captureStatusSummary');
      const taskId = document.getElementById('captureStatusTaskId');
      const base = document.getElementById('captureStatusBase');
      const mode = document.getElementById('captureStatusMode');
      const hosts = document.getElementById('captureStatusHosts');
      if (!panel || !spinner || !label || !headline || !summary || !taskId || !base || !mode || !hosts) return;

      const payload = (statusPayload && typeof statusPayload === 'object') ? statusPayload : {};
      const status = String(payload.status || 'idle');
      const tone = statusTone(status, isRunning);
      panel.classList.remove('idle', 'running', 'success', 'failed');
      panel.classList.add(tone);
      spinner.style.display = isRunning ? 'inline-block' : 'none';
      label.textContent = payload.label || status.charAt(0).toUpperCase() + status.slice(1);
      headline.textContent = payload.headline || 'Ready to start a batch capture';
      summary.textContent = payload.summary || 'Use one of the main actions to queue a capture across all configured hosts.';
      taskId.textContent = payload.taskId || '-';
      base.textContent = payload.base || '-';
      mode.textContent = payload.mode || '-';
      hosts.textContent = payload.hosts || '(all hosts)';
    }

    function stopCaptureStatusPolling() {
      if (captureStatusTimer) {
        clearInterval(captureStatusTimer);
        captureStatusTimer = null;
      }
    }

    function isTerminalTaskStatus(status) {
      const normalized = String(status || '').toLowerCase();
      return normalized === 'completed' || normalized === 'failed' || normalized === 'cancelled';
    }

    function summarizeTaskStatus(data) {
      const status = String((data && data.status) || 'unknown');
      const base = String((data && data.base) || 'unknown');
      const mode = String((data && data.mode) || 'unknown');
      const hosts = Array.isArray(data && data.hosts) ? data.hosts : [];
      const hostLabel = hosts.length > 0 ? hosts.join(', ') : '(all hosts)';
      const normalized = status.toLowerCase();
      let headline = 'Current task is ' + status;
      if (normalized === 'queued') headline = 'Capture request queued';
      if (normalized === 'running') headline = 'Capture is running';
      if (normalized === 'completed') headline = 'Capture completed';
      if (normalized === 'failed') headline = 'Capture failed';
      if (normalized === 'cancelled') headline = 'Capture cancelled';
      return {
        status,
        label: status,
        headline,
        summary: 'mode=' + mode + ' | base=' + base + ' | hosts=' + hostLabel,
        taskId: String((data && data.task_id) || ''),
        base,
        mode,
        hosts: hostLabel
      };
    }

    async function pollCaptureStatus(taskId) {
      if (!taskId) return;
      try {
        const data = await api('/api/v2/tasks/' + taskId);
        const taskStatus = String((data && data.status) || '').toLowerCase();
        const running = !isTerminalTaskStatus(taskStatus);
        setCaptureStatus(summarizeTaskStatus(data), running);
        if (!running) {
          stopCaptureStatusPolling();
        }
      } catch (err) {
        setCaptureStatus({
          status: 'failed',
          label: 'Error',
          headline: 'Failed to refresh capture status',
          summary: 'task=' + taskId + ' | ' + formatError(err),
          taskId,
          base: '-',
          mode: '-',
          hosts: '(unknown)'
        }, false);
        stopCaptureStatusPolling();
      }
    }

    function startCaptureStatusPolling(taskId) {
      stopCaptureStatusPolling();
      setCaptureStatus({
        status: 'queued',
        label: 'Queued',
        headline: 'Capture request queued',
        summary: 'Waiting for task execution to begin.',
        taskId,
        base: '-',
        mode: 'batch',
        hosts: '(all hosts)'
      }, true);
      pollCaptureStatus(taskId);
      captureStatusTimer = setInterval(() => pollCaptureStatus(taskId), 1200);
    }

    function formatWorkerStatus(data) {
      return joinParts([
        'queued=' + toNumber(data && data.queued, 0),
        'running=' + toNumber(data && data.running, 0),
        'completed=' + toNumber(data && data.completed, 0),
        'failed=' + toNumber(data && data.failed, 0),
        'cancelled=' + toNumber(data && data.cancelled, 0),
        'locked_hosts=' + toNumber(data && data.locked_hosts, 0),
        'total=' + toNumber(data && data.total, 0)
      ]);
    }

    function formatReadinessStatus(data) {
      const counts = (data && typeof data.counts === 'object' && data.counts) ? data.counts : {};
      const checks = Array.isArray(data && data.checks) ? data.checks : [];
      const head = joinParts([
        'status=' + String((data && data.status) || 'unknown'),
        'queued=' + toNumber(counts.queued, 0),
        'running=' + toNumber(counts.running, 0),
        'locked_hosts=' + toNumber(counts.locked_hosts, 0),
        'total=' + toNumber(counts.total, 0)
      ]);
      const checkSummary = checks.length
        ? 'checks=' + checks.map((check) => {
          const name = String((check && check.name) || 'unknown');
          return name + '=' + ((check && check.ok) ? 'ok' : 'ng');
        }).join(', ')
        : '';
      return [head, checkSummary].filter((line) => line).join('\n');
    }

    function formatContractStatus(data) {
      const missing = Array.isArray(data && data.missing)
        ? data.missing.length
        : toNumber(data && data.missing, 0);
      const extra = Array.isArray(data && data.extra)
        ? data.extra.length
        : toNumber(data && data.extra, 0);
      return joinParts([
        'status=' + String((data && data.status) || 'unknown'),
        'required_count=' + toNumber(data && data.required_count, 0),
        'actual_count=' + toNumber(data && data.actual_count, 0),
        'missing=' + missing,
        'extra=' + extra
      ]);
    }

    function formatLockStatus(data) {
      const locks = Array.isArray(data && data.locks) ? data.locks : [];
      const hosts = locks
        .slice(0, 5)
        .map((item) => String((item && item.host) || ''))
        .filter((host) => host);
      const more = Math.max(0, locks.length - hosts.length);
      const hostLine = hosts.length > 0
        ? 'hosts=' + hosts.join(', ') + (more > 0 ? ', +' + more + ' more' : '')
        : 'hosts=none';
      const head = joinParts([
        'count=' + toNumber(data && data.count, locks.length),
        'timeout_seconds=' + toNumber(data && data.timeout_seconds, 0)
      ]);
      return [head, hostLine].join('\n');
    }

    function formatLockMutationResult(data) {
      if (Array.isArray(data && data.released) || Array.isArray(data && data.not_locked)) {
        const released = Array.isArray(data.released) ? data.released : [];
        const notLocked = Array.isArray(data.not_locked) ? data.not_locked : [];
        return joinParts([
          'released=' + released.length + (released.length ? ' (' + released.join(', ') + ')' : ''),
          'not_locked=' + notLocked.length + (notLocked.length ? ' (' + notLocked.join(', ') + ')' : ''),
          'remaining=' + toNumber(data && data.remaining, 0)
        ]);
      }
      return joinParts([
        'deleted=' + toNumber(data && data.deleted, 0),
        'remaining=' + toNumber(data && data.remaining, 0),
        'timeout_seconds=' + toNumber(data && data.timeout_seconds, 0)
      ]);
    }

    function formatHostSummaryStatus(data) {
      const rows = Array.isArray(data && data.rows) ? data.rows : [];
      return joinParts([
        'displayed=' + toNumber(data && data.count, rows.length),
        'total_hosts=' + toNumber(data && data.total_hosts, rows.length)
      ]);
    }

    function updateDisplayToggleLabel(buttonId, mode) {
      const button = document.getElementById(buttonId);
      if (!button) return;
      button.textContent = mode === 'full'
        ? 'Display: Full (click for Compact)'
        : 'Display: Compact (click for Full)';
    }

    function applyDisplayMode(rootEl, mode) {
      if (!rootEl) return;
      rootEl.querySelectorAll('.diff-content').forEach((el) => {
        el.classList.remove('full', 'compact');
        el.classList.add(mode);
      });
      if (rootEl.classList && rootEl.classList.contains('diff-content')) {
        rootEl.classList.remove('full', 'compact');
        rootEl.classList.add(mode);
      }
    }

    function setCompareDisplayMode(mode) {
      compareDisplayMode = mode === 'compact' ? 'compact' : 'full';
      updateDisplayToggleLabel('compareDisplayModeToggle', compareDisplayMode);
      applyDisplayMode(document.getElementById('compareHtml'), compareDisplayMode);
    }

    function toggleCompareDisplayMode() {
      setCompareDisplayMode(compareDisplayMode === 'full' ? 'compact' : 'full');
    }

    async function captureSingle(host, base) {
      try {
        setTopActionStatus('[Capture ' + base + ' ' + host + '] started');
        setCaptureStatus({
          status: 'running',
          label: 'Running',
          headline: 'Starting single-host capture',
          summary: 'mode=single | base=' + base + ' | hosts=' + host,
          taskId: '-',
          base,
          mode: 'single',
          hosts: host
        }, true);
        const data = await api('/api/v2/captures', 'POST', { mode: 'single', base, hosts: [host] });
        document.getElementById('taskId').value = data.task_id;
        setTopActionStatus('[Capture ' + base + ' ' + host + '] queued task_id=' + data.task_id + ' status=queued');
        startCaptureStatusPolling(data.task_id);
        await selectTask(data.task_id);
      } catch (err) {
        setTopActionStatus('[Capture ' + base + ' ' + host + '] failed: ' + err.message);
        setCaptureStatus({
          status: 'failed',
          label: 'Failed',
          headline: 'Failed to start single-host capture',
          summary: formatError(err),
          taskId: '-',
          base,
          mode: 'single',
          hosts: host
        }, false);
        alert('Capture failed: ' + err.message);
      }
    }

    async function captureAll(base) {
      const isOrigin = base === 'origin';
      const actionLabel = isOrigin ? 'Capture Origin All' : 'Capture Dest All';
      const buttonId = isOrigin ? 'captureAllOrigin' : 'captureAllDest';
      const button = document.getElementById(buttonId);
      if (button) button.disabled = true;
      setTopActionStatus('[' + actionLabel + '] started');
      try {
        setCaptureStatus({
          status: 'running',
          label: 'Running',
          headline: actionLabel + ' started',
          summary: 'mode=batch | base=' + base + ' | hosts=(all hosts)',
          taskId: '-',
          base,
          mode: 'batch',
          hosts: '(all hosts)'
        }, true);
        const data = await api('/api/v2/captures', 'POST', { mode: 'batch', base, hosts: [] });
        setTopActionStatus('[' + actionLabel + '] queued task_id=' + data.task_id + ' status=queued');
        document.getElementById('taskId').value = data.task_id;
        startCaptureStatusPolling(data.task_id);
        await selectTask(data.task_id);
      } catch (err) {
        setTopActionStatus('[' + actionLabel + '] failed: ' + err.message);
        setCaptureStatus({
          status: 'failed',
          label: 'Failed',
          headline: actionLabel + ' failed to start',
          summary: formatError(err),
          taskId: '-',
          base,
          mode: 'batch',
          hosts: '(all hosts)'
        }, false);
        alert('Capture-all failed: ' + err.message);
      } finally {
        if (button) button.disabled = false;
      }
    }

    async function checkTask() {
      const taskId = document.getElementById('taskId').value.trim();
      if (!taskId) return;
      try {
        const data = await api('/api/v2/tasks/' + taskId);
        document.getElementById('taskQuickSummary').textContent = [
          'task=' + data.task_id,
          'status=' + data.status,
          'mode=' + data.mode,
          'base=' + data.base,
          'hosts=' + (data.hosts || []).join(','),
          'cancel_requested=' + Boolean(data.cancel_requested)
        ].join(' | ');
        renderLiveConsoleMeta();
        return data;
      } catch (err) {
        document.getElementById('taskQuickSummary').textContent = '';
        renderLiveConsoleMeta();
        throw err;
      }
    }

    async function loadWorkerStatus() {
      try {
        const data = await api('/api/v2/system/worker');
        document.getElementById('workerStatus').textContent = formatWorkerStatus(data);
        return data;
      } catch (err) {
        document.getElementById('workerStatus').textContent = formatError(err);
        throw err;
      }
    }

    async function loadContractStatus() {
      try {
        const data = await api('/api/v2/system/contract');
        document.getElementById('contractStatus').textContent = formatContractStatus(data);
        return data;
      } catch (err) {
        document.getElementById('contractStatus').textContent = formatError(err);
        throw err;
      }
    }

    async function loadReadinessStatus() {
      try {
        const data = await api('/api/v2/system/readiness');
        document.getElementById('readinessStatus').textContent = formatReadinessStatus(data);
        return data;
      } catch (err) {
        document.getElementById('readinessStatus').textContent = formatError(err);
        throw err;
      }
    }

    async function runTopWorkerStatus() {
      setTopActionStatus('[Worker Status] started');
      try {
        await loadWorkerStatus();
        setTopActionStatus('[Worker Status] success');
      } catch (err) {
        setTopActionStatus('[Worker Status] failed: ' + err.message);
      }
    }

    async function runTopReadinessStatus() {
      setTopActionStatus('[Readiness] started');
      try {
        await loadReadinessStatus();
        setTopActionStatus('[Readiness] success');
      } catch (err) {
        setTopActionStatus('[Readiness] failed: ' + err.message);
      }
    }

    async function runTopContractStatus() {
      setTopActionStatus('[Contract Check] started');
      try {
        await loadContractStatus();
        setTopActionStatus('[Contract Check] success');
      } catch (err) {
        setTopActionStatus('[Contract Check] failed: ' + err.message);
      }
    }

    async function loadLockStatus() {
      try {
        const data = await api('/api/v2/system/locks');
        document.getElementById('lockStatus').textContent = formatLockStatus(data);
      } catch (err) {
        document.getElementById('lockStatus').textContent = formatError(err);
      }
    }

    async function cleanupLocks() {
      try {
        const data = await api('/api/v2/system/locks/cleanup', 'POST');
        document.getElementById('lockStatus').textContent = formatLockMutationResult(data);
        await loadWorkerStatus();
        await loadReadinessStatus();
      } catch (err) {
        alert('Lock cleanup failed: ' + err.message);
      }
    }

    async function releaseLocks() {
      const raw = document.getElementById('lockReleaseHosts').value.trim();
      const hosts = raw
        .split(',')
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      try {
        const data = await api('/api/v2/system/locks/release', 'POST', { hosts });
        document.getElementById('lockStatus').textContent = formatLockMutationResult(data);
        await loadWorkerStatus();
        await loadReadinessStatus();
      } catch (err) {
        alert('Lock release failed: ' + err.message);
      }
    }

    async function loadRecentTasks() {
      try {
        const status = document.getElementById('statusFilter').value;
        const runningOnly = document.getElementById('runningOnly').checked;
        const hostSearch = document.getElementById('hostSearch').value.trim();
        const parts = ['limit=' + taskPageSize, 'offset=' + taskPageOffset];
        if (status) parts.push('status_filter=' + encodeURIComponent(status));
        if (runningOnly) parts.push('running_only=true');
        if (hostSearch) parts.push('host_contains=' + encodeURIComponent(hostSearch));
        const data = await api('/api/v2/tasks?' + parts.join('&'));
        renderTaskTable(data);
      } catch (err) {
        document.getElementById('taskTableWrap').innerHTML = '';
      }
    }

    async function loadHostSummary() {
      const hostSearch = document.getElementById('summaryHostSearch').value.trim();
      const limitValue = Number(document.getElementById('summaryLimit').value || '50');
      const prioritizeFailed = document.getElementById('summaryPrioritizeFailed').checked;
      const limit = Number.isFinite(limitValue) && limitValue > 0 ? Math.floor(limitValue) : 50;
      const parts = ['limit=' + limit];
      if (hostSearch) parts.push('host_contains=' + encodeURIComponent(hostSearch));
      if (!prioritizeFailed) parts.push('prioritize_failed=false');
      try {
        const data = await api('/api/v2/hosts/summary?' + parts.join('&'));
        document.getElementById('hostSummaryView').textContent = formatHostSummaryStatus(data);
        renderHostSummaryTable(data.rows || []);
      } catch (err) {
        document.getElementById('hostSummaryView').textContent = formatError(err);
        document.getElementById('hostSummaryTableWrap').innerHTML = '';
      }
    }

    function renderHostSummaryTable(rows) {
      const wrap = document.getElementById('hostSummaryTableWrap');
      if (!Array.isArray(rows) || rows.length === 0) {
        wrap.innerHTML = '<p>No summary data</p>';
        return;
      }
      const formatLocalDateTime = (epochSec) => {
        const value = Number(epochSec);
        if (!Number.isFinite(value) || value <= 0) return '';
        const date = new Date(value * 1000);
        const pad = (n) => String(n).padStart(2, '0');
        return [
          date.getFullYear(),
          '-',
          pad(date.getMonth() + 1),
          '-',
          pad(date.getDate()),
          ' ',
          pad(date.getHours()),
          ':',
          pad(date.getMinutes()),
          ':',
          pad(date.getSeconds())
        ].join('');
      };
      const formatCaptureStatus = (entry) => {
        const status = String((entry && entry.status) || '');
        if (status === 'running') return 'Running';
        if (status === 'captured') {
          const ts = formatLocalDateTime(entry.captured_at);
          return ts ? ('Captured (' + ts + ')') : 'Captured';
        }
        return 'Not Captured';
      };
      const renderCommandStatuses = (commands, side) => {
        if (!Array.isArray(commands) || commands.length === 0) {
          return '<span class="text-muted">No command data</span>';
        }
        return commands.map((item) => {
          const command = (item && item.command) ? item.command : item.command_key;
          const sideEntry = item && item[side];
          return [
            '<div>',
            '<code>' + escapeHtml(command) + '</code>: ',
            escapeHtml(formatCaptureStatus(sideEntry)),
            '</div>'
          ].join('');
        }).join('');
      };
      const body = rows.map((r) => [
        '<tr>',
        '<td>' + escapeHtml(r.host) + '</td>',
        '<td>' + escapeHtml(r.ip) + '</td>',
        '<td>' + escapeHtml(r.model) + '</td>',
        '<td>' + renderCommandStatuses(r.commands, 'origin') + '</td>',
        '<td>' + renderCommandStatuses(r.commands, 'dest') + '</td>',
        '<td><div class="host-summary-actions">' +
          '<button title="Capture origin config for this host" onclick="captureSingle(&quot;' + escapeHtml(r.host) + '&quot;, &quot;origin&quot;)">Origin</button>' +
          '<button class="secondary" title="Capture destination config for this host" onclick="captureSingle(&quot;' + escapeHtml(r.host) + '&quot;, &quot;dest&quot;)">Dest</button>' +
          '<a class="action-link secondary" title="Open detailed diff view for this host" href="/v2/hosts/' + encodeURIComponent(r.host) + '">Detail</a>' +
          '</div></td>',
        '</tr>'
      ].join('')).join('');
      wrap.innerHTML = [
        '<div class="hosts-table-wrap">',
        '<table class="mini-table host-summary-table">',
        '<thead><tr><th>Host</th><th>IP</th><th>Model</th><th>Origin Capture Status</th><th>Dest Capture Status</th><th>Actions</th></tr></thead>',
        '<tbody>',
        body,
        '</tbody>',
        '</table>',
        '</div>'
      ].join('');
    }

    function startAutoRefresh() {
      stopAutoRefresh();
      refreshTimer = setInterval(loadRecentTasks, RECENT_TASK_REFRESH_MS);
    }

    function stopAutoRefresh() {
      if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
      }
    }

    function nextTaskPage() {
      taskPageOffset += taskPageSize;
      loadRecentTasks();
    }

    function prevTaskPage() {
      taskPageOffset = Math.max(0, taskPageOffset - taskPageSize);
      loadRecentTasks();
    }

    function renderTaskTable(tasks) {
      const wrap = document.getElementById('taskTableWrap');
      if (!Array.isArray(tasks) || tasks.length === 0) {
        wrap.innerHTML = '<p>No tasks</p>';
        return;
      }
      const rows = tasks.map((t) => {
        const statusClass = 'status-' + String(t.status || '').toLowerCase();
        const hosts = (t.hosts || []).join(', ');
        return [
          '<tr>',
          '<td><code>' + escapeHtml(t.task_id) + '</code></td>',
          '<td><span class="status-pill ' + statusClass + '">' + escapeHtml(t.status) + '</span></td>',
          '<td>' + escapeHtml(t.mode) + '</td>',
          '<td>' + escapeHtml(t.base) + '</td>',
          '<td>' + escapeHtml(hosts) + '</td>',
          '<td>',
          '<button title="Select this task and open its live console" onclick="selectTask(&quot;' + escapeHtml(t.task_id) + '&quot;)">Select</button> ',
          '<button class="warn" title="Request cancellation for this task" onclick="quickCancel(&quot;' + escapeHtml(t.task_id) + '&quot;)">Cancel</button>',
          '</td>',
          '</tr>'
        ].join('');
      }).join('');
      wrap.innerHTML = [
        '<div class="row" style="margin-bottom: 6px;">',
        '<button title="Show previous page of tasks" onclick="prevTaskPage()">Prev</button>',
        '<button class="secondary" title="Show next page of tasks" onclick="nextTaskPage()">Next</button>',
        '<small>offset=' + taskPageOffset + ', limit=' + taskPageSize + '</small>',
        '</div>',
        '<table class="mini-table">',
        '<thead><tr><th>Task</th><th>Status</th><th>Mode</th><th>Base</th><th>Hosts</th><th>Actions</th></tr></thead>',
        '<tbody>',
        rows,
        '</tbody></table>'
      ].join('');
    }

    async function selectTask(taskId) {
      document.getElementById('taskId').value = taskId;
      try {
        await checkTask();
        startLiveConsole();
      } catch (err) {
        const message = formatError(err);
        stopLiveStream();
        streamTaskId = taskId;
        document.getElementById('taskQuickSummary').textContent = message;
        clearLiveConsole();
      }
    }

    function quickCancel(taskId) {
      document.getElementById('taskId').value = taskId;
      cancelTask();
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function isNearConsoleBottom(el) {
      if (!el) return true;
      const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
      return gap <= CONSOLE_STICKY_THRESHOLD_PX;
    }

    function setLiveConsoleFollow(next) {
      liveConsoleFollow = Boolean(next);
      const state = document.getElementById('liveConsoleFollowState');
      const button = document.getElementById('liveConsoleFollowButton');
      if (state) {
        state.textContent = liveConsoleFollow ? 'follow=on' : 'follow=off';
      }
      if (button) {
        button.textContent = liveConsoleFollow ? 'Follow: ON' : 'Follow: OFF';
      }
    }

    function toggleLiveConsoleFollow() {
      setLiveConsoleFollow(!liveConsoleFollow);
      if (liveConsoleFollow) {
        const view = document.getElementById('liveConsoleView');
        if (view) view.scrollTop = view.scrollHeight;
      }
      renderLiveConsoleMeta();
    }

    function renderLiveConsoleMeta() {
      const meta = document.getElementById('liveConsoleMeta');
      if (!meta) return;
      const labelTaskId = streamTaskId || document.getElementById('taskId').value.trim() || '-';
      meta.textContent = [
        'task=' + labelTaskId,
        'lines=' + liveConsoleLines.length + '/' + MAX_CONSOLE_LINES,
        'follow=' + (liveConsoleFollow ? 'on' : 'off'),
        'stream=' + (streamSource ? 'connected' : 'stopped'),
      ].join(' | ');
    }

    function appendLiveConsoleLine(line) {
      const view = document.getElementById('liveConsoleView');
      if (!view) return;
      const stickToBottom = liveConsoleFollow && isNearConsoleBottom(view);
      liveConsoleLines.push(String(line));
      if (liveConsoleLines.length > MAX_CONSOLE_LINES) {
        liveConsoleLines.splice(0, liveConsoleLines.length - MAX_CONSOLE_LINES);
      }
      view.textContent = liveConsoleLines.join('\n');
      if (stickToBottom) {
        view.scrollTop = view.scrollHeight;
      }
      renderLiveConsoleMeta();
    }

    function clearLiveConsole() {
      liveConsoleLines = [];
      const view = document.getElementById('liveConsoleView');
      if (view) view.textContent = '';
      renderLiveConsoleMeta();
    }

    async function cancelTask() {
      const taskId = document.getElementById('taskId').value.trim();
      if (!taskId) return;
      try {
        await api('/api/v2/tasks/' + taskId + '/cancel', 'POST');
        await checkTask();
        await loadRecentTasks();
      } catch (err) {
        alert('Cancel failed: ' + err.message);
      }
    }

    function startLiveConsole() {
      const taskId = document.getElementById('taskId').value.trim();
      if (!taskId) return;
      stopLiveStream();
      clearLiveConsole();
      streamTaskId = taskId;
      setLiveConsoleFollow(true);
      const tail = Number(document.getElementById('tailLines').value || '0');
      const safeTail = Number.isFinite(tail) && tail > 0 ? Math.floor(tail) : 0;
      appendLiveConsoleLine('[stream] connect task=' + taskId + ' tail=' + safeTail);
      streamSource = new EventSource('/api/v2/tasks/' + taskId + '/stream?tail_lines=' + safeTail);
      streamSource.onmessage = function(event) {
        appendLiveConsoleLine(event.data);
      };
      streamSource.addEventListener('status', function(event) {
        appendLiveConsoleLine('[status] ' + event.data);
        stopLiveStream();
      });
      streamSource.onerror = function() {
        appendLiveConsoleLine('[stream error]');
        stopLiveStream();
      };
      renderLiveConsoleMeta();
    }

    function stopLiveStream() {
      if (streamSource) {
        streamSource.close();
        streamSource = null;
      }
      renderLiveConsoleMeta();
    }

    function openExportJson() {
      const host = document.getElementById('exportHost').value.trim();
      if (!host) return;
      window.open('/api/v2/exports/' + host, '_blank');
    }

    function openExportHtml() {
      const host = document.getElementById('exportHost').value.trim();
      if (!host) return;
      window.open('/api/v2/exports/' + host + '/html', '_blank');
    }

    async function loadExportDiffJson() {
      const host = document.getElementById('exportHost').value.trim();
      if (!host) return;
      const box = document.getElementById('exportDiffView');
      try {
        const data = await api('/api/v2/exports/' + encodeURIComponent(host) + '/diff-json');
        box.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        box.textContent = err.message;
      }
    }

    function openLogsPage() {
      window.open('/v2/logs', '_blank');
    }

    async function runHostDiff() {
      const host = document.getElementById('diffHost').value.trim();
      if (!host) return;
      const view = document.getElementById('diffView').value;
      const viewBox = document.getElementById('compareView');
      const htmlBox = document.getElementById('compareHtml');
      try {
        const data = await api('/api/v2/diff/' + encodeURIComponent(host) + '?view=' + encodeURIComponent(view));
        viewBox.textContent = JSON.stringify(data.summary, null, 2);
        document.getElementById('compareSummary').textContent = [
          'host=' + data.hostname,
          'view=' + data.view,
          'total=' + data.summary.total,
          'changed=' + data.summary.changed,
          'identical=' + data.summary.identical,
          'unavailable=' + data.summary.unavailable
        ].join(' | ');
        const blocks = (data.commands || []).map((item) => {
          return [
            '<h4>' + escapeHtml(item.command) + '</h4>',
            '<p>origin=' + escapeHtml(item.origin_status) + ', dest=' + escapeHtml(item.dest_status) + ', diff=' + escapeHtml(item.diff_status) + '</p>',
            item.diff_html || ''
          ].join('');
        });
        htmlBox.innerHTML = blocks.join('<hr>');
        applyDisplayMode(htmlBox, compareDisplayMode);
      } catch (err) {
        document.getElementById('compareSummary').textContent = '';
        viewBox.textContent = err.message;
        htmlBox.innerHTML = '';
      }
    }

    async function runFileCompare() {
      const host1 = document.getElementById('cmpHost1').value.trim();
      const host2 = document.getElementById('cmpHost2').value.trim();
      const base = document.getElementById('cmpBase').value;
      const command = document.getElementById('cmpCommand').value.trim();
      const view = document.getElementById('cmpView').value;
      if (!host1 || !host2 || !command) return;
      if (host1 === host2) {
        const message = 'host1 and host2 must be different';
        document.getElementById('compareSummary').textContent = message;
        document.getElementById('compareView').textContent = message;
        document.getElementById('compareHtml').innerHTML = '';
        alert(message);
        return;
      }
      const viewBox = document.getElementById('compareView');
      const htmlBox = document.getElementById('compareHtml');
      try {
        const data = await api('/api/v2/compare/files', 'POST', { host1, host2, base, command, view });
        viewBox.textContent = JSON.stringify({
          host1: data.host1,
          host2: data.host2,
          base: data.base,
          command: data.command,
          status: data.status
        }, null, 2);
        document.getElementById('compareSummary').textContent = [
          'host1=' + data.host1,
          'host2=' + data.host2,
          'base=' + data.base,
          'command=' + data.command,
          'status=' + data.status
        ].join(' | ');
        htmlBox.innerHTML = data.diff_html || '';
        applyDisplayMode(htmlBox, compareDisplayMode);
      } catch (err) {
        document.getElementById('compareSummary').textContent = '';
        viewBox.textContent = err.message;
        htmlBox.innerHTML = '';
      }
    }

    document.getElementById('captureAllOrigin').addEventListener('click', () => captureAll('origin'));
    document.getElementById('captureAllDest').addEventListener('click', () => captureAll('dest'));
    document.getElementById('statusFilter').addEventListener('change', () => { taskPageOffset = 0; loadRecentTasks(); });
    document.getElementById('runningOnly').addEventListener('change', () => { taskPageOffset = 0; loadRecentTasks(); });
    document.getElementById('hostSearch').addEventListener('input', () => { taskPageOffset = 0; loadRecentTasks(); });
    document.getElementById('taskId').addEventListener('change', (event) => {
      const taskId = event.target.value.trim();
      if (taskId) selectTask(taskId);
    });
    document.getElementById('taskId').addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      const taskId = event.target.value.trim();
      if (taskId) selectTask(taskId);
    });
    document.getElementById('summaryHostSearch').addEventListener('input', loadHostSummary);
    document.getElementById('summaryPrioritizeFailed').addEventListener('change', loadHostSummary);
    document.getElementById('liveConsoleView').addEventListener('scroll', () => {
      const view = document.getElementById('liveConsoleView');
      setLiveConsoleFollow(isNearConsoleBottom(view));
      renderLiveConsoleMeta();
    });
    loadHostSummary();
    setCaptureStatus({
      status: 'idle',
      label: 'Idle',
      headline: 'Ready to start a batch capture',
      summary: 'Use one of the main actions to queue a capture across all configured hosts.',
      taskId: '-',
      base: '-',
      mode: '-',
      hosts: '(all hosts)'
    }, false);
    loadRecentTasks();
    startAutoRefresh();
    setLiveConsoleFollow(true);
    renderLiveConsoleMeta();
    setCompareDisplayMode('full');
