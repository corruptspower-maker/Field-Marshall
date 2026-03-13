/**
 * app.js — Field Marshal Dashboard JavaScript
 *
 * - Chat submission via fetch POST to /chat
 * - SSE connection to /stream for real-time feed
 * - Auto-scroll for both panels
 * - Markdown-lite rendering (code blocks)
 * - Timestamp formatting
 */

'use strict';

// ---- Utility ---------------------------------------------------------------

function formatTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Very light Markdown renderer:
 *  - ```lang ... ``` → <pre><code>
 *  - `inline` → <code>
 *  - **bold**
 *  - \n → <br> outside code blocks
 */
function renderMarkdown(text) {
  // Protect code blocks first
  const codeBlocks = [];
  let html = text.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push('<pre><code>' + escapeHtml(code.trimEnd()) + '</code></pre>');
    return `\x00CODE${idx}\x00`;
  });

  // Escape remaining HTML
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');

  // Restore code blocks
  html = html.replace(/\x00CODE(\d+)\x00/g, (_, idx) => codeBlocks[parseInt(idx)]);

  return html;
}

function scrollToBottom(el) {
  el.scrollTop = el.scrollHeight;
}

// ---- Chat ------------------------------------------------------------------

const chatMessages = document.getElementById('chat-messages');
const chatInput    = document.getElementById('chat-input');
const sendBtn      = document.getElementById('chat-send');

function appendMessage(speaker, text, cssClass) {
  const div = document.createElement('div');
  div.className = 'msg ' + cssClass;

  const header = document.createElement('div');
  header.className = 'msg-header';
  header.innerHTML = `<span class="msg-speaker">${escapeHtml(speaker)}</span><span class="msg-time">${formatTimestamp()}</span>`;

  const body = document.createElement('div');
  body.className = 'msg-body';
  body.innerHTML = renderMarkdown(text);

  div.appendChild(header);
  div.appendChild(body);
  chatMessages.appendChild(div);
  scrollToBottom(chatMessages);
  return div;
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  appendMessage('YOU', text, 'user');
  chatInput.value = '';
  sendBtn.disabled = true;

  // Show "thinking" indicator
  const thinkingDiv = appendMessage('BONDSMAN', '…', 'bondsman thinking');

  fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text }),
  })
    .then(r => r.json())
    .then(data => {
      thinkingDiv.remove();
      appendMessage('BONDSMAN', data.response || '[no response]', 'bondsman');
    })
    .catch(err => {
      thinkingDiv.remove();
      appendMessage('SYSTEM', 'Error: ' + err.message, 'system-msg');
    })
    .finally(() => {
      sendBtn.disabled = false;
      chatInput.focus();
    });
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    sendMessage();
  }
});

// ---- Live Feed -------------------------------------------------------------

const feedEntries = document.getElementById('feed-entries');
const clearBtn    = document.getElementById('feed-clear');

clearBtn.addEventListener('click', () => {
  feedEntries.innerHTML = '';
});

function appendFeedEntry(cssClass, speakerLabel, speakerCss, bodyHtml, extra) {
  const entry = document.createElement('div');
  entry.className = 'feed-entry ' + cssClass;

  let inner = `<span class="feed-ts">${formatTimestamp()}</span>`;
  if (speakerLabel) {
    inner += `<span class="feed-speaker ${speakerCss || ''}">${escapeHtml(speakerLabel)}</span>`;
  }
  if (extra) inner += extra;
  inner += `<span class="feed-text">${bodyHtml}</span>`;

  entry.innerHTML = inner;
  feedEntries.appendChild(entry);
  scrollToBottom(feedEntries);
}

function handleSSEEvent(event) {
  let payload;
  try { payload = JSON.parse(event.data); } catch { return; }

  const type = payload.type;
  const data = payload.data || {};

  if (type === 'heartbeat') return;  // Silently ignore heartbeats

  switch (type) {
    case 'dialectic': {
      const speaker = (data.speaker || '').toLowerCase();
      const round   = data.round ? `<span class="round-badge">Round ${data.round}</span>` : '';
      if (speaker === 'lord') {
        appendFeedEntry(
          'lord-entry', 'THE LORD', '',
          renderMarkdown(data.text || ''), round
        );
      } else if (speaker === 'bondsman') {
        appendFeedEntry(
          'bondsman-entry', 'BONDSMAN', '',
          renderMarkdown(data.text || ''), round
        );
      } else {
        appendFeedEntry(
          'status-entry', null, '',
          escapeHtml(data.text || ''), null
        );
      }
      break;
    }

    case 'evidence': {
      const sev = (data.severity || 'info').toLowerCase();
      const sevClass = sev === 'error' ? 'sev-error' : sev === 'warn' ? 'sev-warn' : 'sev-info';
      const screenshotBadge = data.has_screenshot
        ? '<span class="round-badge">📷 screenshot</span>'
        : '';
      appendFeedEntry(
        'evidence-entry',
        `EVIDENCE [${data.source_agent || 'agent'}]`,
        '',
        `<span class="${sevClass}">[${sev.toUpperCase()}]</span> ${escapeHtml(data.caption || '')}`,
        screenshotBadge
      );
      // Update active tasks counter
      refreshHealth();
      break;
    }

    case 'dispatch': {
      appendFeedEntry(
        'dispatch-entry',
        `DISPATCH → ${(data.target || '').toUpperCase()}`,
        '',
        escapeHtml(String(data.payload || '').substring(0, 120)),
        null
      );
      refreshHealth();
      break;
    }

    case 'status': {
      const eventName = data.event || '';
      if (eventName === 'chat_response') return;  // Skip internal events
      appendFeedEntry(
        'status-entry', null, '',
        escapeHtml(JSON.stringify(data).substring(0, 200)),
        null
      );
      break;
    }

    default: {
      appendFeedEntry(
        'status-entry', null, '',
        escapeHtml(JSON.stringify(payload).substring(0, 300)),
        null
      );
    }
  }
}

// ---- SSE Connection --------------------------------------------------------

let _sse = null;

function connectSSE() {
  if (_sse) { _sse.close(); }
  _sse = new EventSource('/stream');

  _sse.onopen = () => {
    document.getElementById('router-status').textContent = 'online';
    document.getElementById('connect-ts').textContent = formatTimestamp();
    feedEntries.querySelector('.feed-text') &&
      (feedEntries.querySelector('.feed-text').textContent = 'Connected to live feed.');
    refreshHealth();
  };

  _sse.onmessage = handleSSEEvent;

  _sse.onerror = () => {
    document.getElementById('router-status').textContent = 'reconnecting…';
    // Browser auto-reconnects EventSource
  };
}

// ---- Health polling --------------------------------------------------------

function refreshHealth() {
  fetch('/health')
    .then(r => r.json())
    .then(data => {
      document.getElementById('active-tasks').textContent = data.tasks_active ?? '?';
      document.getElementById('router-status').textContent = 'online';
    })
    .catch(() => {
      document.getElementById('router-status').textContent = 'offline';
    });
}

// ---- Init ------------------------------------------------------------------

connectSSE();
refreshHealth();
setInterval(refreshHealth, 10000);  // Poll health every 10s
