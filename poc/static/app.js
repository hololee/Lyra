const chatEl = document.getElementById('chat');
const form = document.getElementById('chatForm');
const input = document.getElementById('messageInput');
const resetBtn = document.getElementById('resetBtn');
const modelBadge = document.getElementById('modelBadge');
const phaseBadge = document.getElementById('phaseBadge');
const goalView = document.getElementById('goalView');
const draftView = document.getElementById('draftView');
const violationsView = document.getElementById('violationsView');
const llmView = document.getElementById('llmView');
const targetMode = document.getElementById('targetMode');
const hostGpu = document.getElementById('hostGpu');
const workerGpu = document.getElementById('workerGpu');
const langSel = document.getElementById('langSel');
const applyInfra = document.getElementById('applyInfra');

let sessionId = '';

function escapeHtml(text) {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderMarkdown(text) {
  const src = String(text || '').replace(/\r\n/g, '\n');
  const lines = src.split('\n');
  const out = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i] || '';
    const next = lines[i + 1] || '';
    const isTableHeader = line.includes('|') && /^\s*\|?\s*[-: ]+\|[-|: ]+\s*\|?\s*$/.test(next);
    if (isTableHeader) {
      const tableLines = [line, next];
      i += 2;
      while (i < lines.length && lines[i].includes('|')) {
        tableLines.push(lines[i]);
        i += 1;
      }
      const headerCells = tableLines[0].split('|').map((v) => v.trim()).filter(Boolean);
      const bodyLines = tableLines.slice(2);
      out.push('<table class="md-table"><thead><tr>');
      headerCells.forEach((cell) => out.push(`<th>${escapeHtml(cell)}</th>`));
      out.push('</tr></thead><tbody>');
      bodyLines.forEach((row) => {
        const cells = row.split('|').map((v) => v.trim()).filter(Boolean);
        out.push('<tr>');
        headerCells.forEach((_, idx) => {
          const cell = cells[idx] ?? '';
          const code = cell.startsWith('`') && cell.endsWith('`');
          const textCell = code ? cell.slice(1, -1) : cell;
          out.push(`<td>${code ? `<code>${escapeHtml(textCell)}</code>` : escapeHtml(textCell)}</td>`);
        });
        out.push('</tr>');
      });
      out.push('</tbody></table>');
      continue;
    }

    if (!line.trim()) {
      out.push('<br/>');
    } else {
      out.push(`<div>${escapeHtml(line)}</div>`);
    }
    i += 1;
  }
  return out.join('');
}

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = renderMarkdown(text);
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addAssistantDoneMsg(text, actionHint = '') {
  const div = document.createElement('div');
  div.className = 'msg assistant';

  const body = document.createElement('div');
  body.className = 'msg-body';
  body.innerHTML = renderMarkdown(text);
  div.appendChild(body);

  const actionWrap = document.createElement('div');
  actionWrap.className = 'msg-actions';
  if (String(actionHint || '').trim()) {
    const hint = document.createElement('div');
    hint.className = 'msg-action-hint';
    hint.textContent = String(actionHint).trim();
    actionWrap.appendChild(hint);
  }
  const actionBtn = document.createElement('button');
  actionBtn.type = 'button';
  actionBtn.className = 'msg-action-btn';
  actionBtn.textContent = '생성하기';
  actionBtn.addEventListener('click', async () => {
    try {
      await resetSession();
    } catch (err) {
      addMsg('assistant', String(err));
    }
  });
  actionWrap.appendChild(actionBtn);
  div.appendChild(actionWrap);

  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function refresh(payload) {
  modelBadge.textContent = `model: ${payload.model}`;
  phaseBadge.textContent = `phase: ${payload.phase}`;
  goalView.textContent = payload.goal || '(empty)';
  draftView.textContent = JSON.stringify(payload.draft || {}, null, 2);
  violationsView.textContent = (payload.violations || []).join('\n') || '(none)';
  llmView.textContent = JSON.stringify(payload.llm_response || { message: 'No LLM response', error_code: payload.error_code || null }, null, 2);
}

async function post(url, body) {
  const res = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function resetSession() {
  chatEl.innerHTML = '';
  const data = await post('/api/session/reset', { session_id: sessionId });
  sessionId = data.session_id;
  modelBadge.textContent = `model: ${data.model}`;
  phaseBadge.textContent = '';
  goalView.textContent = '(empty)';
  draftView.textContent = '{}';
  violationsView.textContent = '(none)';
  llmView.textContent = '{}';
}

async function newSession() {
  const data = await post('/api/session/new', {});
  sessionId = data.session_id;
  modelBadge.textContent = `model: ${data.model}`;
}

async function send(message) {
  addMsg('user', message);
  const payload = await post('/api/chat', { session_id: sessionId, message });
  if (payload.phase === 'done' && payload.result === 'success') {
    addAssistantDoneMsg(payload.assistant || '(empty response)', payload?.llm_response?.question || '');
  } else {
    addMsg('assistant', payload.assistant || '(empty response)');
  }
  refresh(payload);
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = '';
  try { await send(message); } catch (err) { addMsg('assistant', String(err)); }
});

resetBtn.addEventListener('click', async () => {
  await resetSession();
});

applyInfra.addEventListener('click', async () => {
  if (!sessionId) return;
  await post('/api/session/infra', {
    session_id: sessionId,
    target_mode: targetMode.value,
    host_gpu_count: Number(hostGpu.value || 0),
    worker_gpu_count: Number(workerGpu.value || 0),
    language: langSel.value,
  });
});

newSession().catch((err) => addMsg('assistant', String(err)));
