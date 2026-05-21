/* ── Pantheon Ideas Panel v2 ──
 * Right-side slide-in panel for the Hermes UI.
 * Full CRUD: view, edit, delete, reorder (drag/arrows), status change, add.
 * Reads/writes via /api/ideas endpoints (project-ideas.md on disk).
 */
(function() {
  'use strict';

  var panelOpen = false;
  var sectionsData = [];
  var editingEntry = null; // { sectionName, entryName }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ── Panel DOM ──

  function createPanel() {
    var existing = document.getElementById('ideas-right-panel');
    if (existing) return existing;

    var panel = document.createElement('div');
    panel.id = 'ideas-right-panel';
    panel.style.cssText = [
      'position:fixed;top:0;right:0;width:480px;max-width:94vw;height:100vh;',
      'z-index:8990;background:var(--bg-primary,#0a0908);',
      'border-left:1px solid var(--border,#3B4A50);',
      'box-shadow:-8px 0 32px rgba(0,0,0,0.5);',
      'display:flex;flex-direction:column;',
      'transform:translateX(100%);transition:transform 0.25s ease;',
      'font-family:system-ui,-apple-system,sans-serif;'
    ].join('');
    panel.innerHTML = [
      '<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border,#3B4A50);flex-shrink:0">',
        '<h2 style="margin:0;font-size:1rem;font-weight:600;color:var(--text-primary,#EAE0D5)">💡 Ideas</h2>',
        '<div style="display:flex;gap:6px">',
          '<button id="ideas-panel-add" style="background:var(--accent,#7c6fe0);color:white;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:11px;font-weight:600">+ Entry</button>',
          '<button id="ideas-panel-close" style="background:none;border:none;color:var(--text-muted);font-size:1.1rem;cursor:pointer;padding:4px 8px;border-radius:6px">✕</button>',
        '</div>',
      '</div>',
      '<div id="ideas-panel-body" style="flex:1;overflow:auto;padding:14px 18px"></div>',
    ].join('\n');

    document.body.appendChild(panel);

    document.getElementById('ideas-panel-close').onclick = closePanel;
    document.getElementById('ideas-panel-add').onclick = showAddEntryDialog;

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && panelOpen) {
        if (editingEntry) { editingEntry = null; renderSections(sectionsData); }
        else closePanel();
      }
    });

    return panel;
  }

  function openPanel() {
    var panel = createPanel();
    panel.style.transform = 'translateX(0)';
    panelOpen = true;
    loadIdeas();
  }

  function closePanel() {
    var panel = document.getElementById('ideas-right-panel');
    if (panel) panel.style.transform = 'translateX(100%)';
    panelOpen = false;
  }

  function togglePanel() {
    if (panelOpen) closePanel();
    else openPanel();
  }

  // ── Data ──

  function loadIdeas() {
    var body = document.getElementById('ideas-panel-body');
    if (!body) return;
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading ideas...</div>';

    fetch('/api/ideas')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        sectionsData = data.sections || [];
        renderSections(sectionsData);
      })
      .catch(function(err) {
        body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--error,#F87171)">Failed to load: ' + esc(err.message) + '</div>';
      });
  }

  function reloadAfterAction() {
    fetch('/api/ideas')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        sectionsData = data.sections || [];
        renderSections(sectionsData);
      });
  }

  // ── Render ──

  function renderSections(sections) {
    var body = document.getElementById('ideas-panel-body');
    if (!body) return;

    if (!sections.length) {
      body.innerHTML = [
        '<div style="text-align:center;padding:40px;color:var(--text-muted)">',
          '<div style="font-size:48px;margin-bottom:12px">💡</div>',
          '<div style="font-size:14px;font-weight:600;margin-bottom:6px">No ideas yet</div>',
          '<div style="font-size:12px">Add ideas to ~/pantheon/project-ideas.md</div>',
        '</div>'
      ].join('\n');
      return;
    }

    body.innerHTML = sections.map(function(section) {
      var sectionName = section.name || 'Untitled';
      var entries = section.entries || [];
      return [
        '<div class="ideas-section" style="margin-bottom:20px" data-section="' + esc(sectionName) + '">',
          '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid var(--border)">',
            '<h3 style="color:var(--text-primary,#EAE0D5);font-size:14px;font-weight:600;margin:0;flex:1">' + esc(sectionName) + '</h3>',
            '<button class="ideas-add-entry" data-section="' + esc(sectionName) + '" style="background:var(--bg-secondary,#11100E);color:var(--accent);border:1px solid var(--border);border-radius:4px;padding:2px 8px;cursor:pointer;font-size:10px;font-weight:600">+</button>',
          '</div>',
          entries.map(function(entry, i) {
            return renderEntry(sectionName, entry, i, entries.length);
          }).join('\n'),
        '</div>'
      ].join('\n');
    }).join('\n');

    // ── Arrow reorder wiring ──
    body.querySelectorAll('.ideas-move-up').forEach(function(el) {
      el.onclick = function(e) { e.stopPropagation(); moveEntry(el.dataset.section, el.dataset.entry, 'up'); };
    });
    body.querySelectorAll('.ideas-move-down').forEach(function(el) {
      el.onclick = function(e) { e.stopPropagation(); moveEntry(el.dataset.section, el.dataset.entry, 'down'); };
    });

    // Wire up buttons

    body.querySelectorAll('.ideas-view-entry').forEach(function(el) {
      el.onclick = function(e) {
        if (e.target.closest('button')) return;
        var section = el.dataset.section;
        var entry = el.dataset.entry;
        viewEntryDetail(section, entry);
      };
    });

    body.querySelectorAll('.ideas-delete-entry').forEach(function(el) {
      el.onclick = function(e) { e.stopPropagation(); deleteEntry(el.dataset.section, el.dataset.entry); };
    });
    body.querySelectorAll('.ideas-edit-entry').forEach(function(el) {
      el.onclick = function(e) { e.stopPropagation(); editEntryInline(el.dataset.section, el.dataset.entry); };
    });
    body.querySelectorAll('.ideas-add-entry').forEach(function(el) {
      el.onclick = function(e) { e.stopPropagation(); showAddEntryDialog(el.dataset.section); };
    });
    body.querySelectorAll('.ideas-status-cycle').forEach(function(el) {
      el.onclick = function(e) { e.stopPropagation(); cycleStatus(el.dataset.section, el.dataset.entry); };
    });
  }

  var STATUSES = ['Backlog', 'In Progress', 'Done', 'On Hold', 'Cancelled'];

  function normalizeStatus(status) {
    var raw = String(status || '').replace(/\*\*/g, '').trim();
    raw = raw.replace(/^Status:\s*/i, '').replace(/\s+/g, ' ').trim();
    var lower = raw.toLowerCase();
    if (/^in progress(?: progress)*$/.test(lower) || lower === 'in') return 'In Progress';
    if (lower === 'on hold' || lower === 'hold') return 'On Hold';
    if (lower === 'cancelled' || lower === 'canceled') return 'Cancelled';
    for (var i = 0; i < STATUSES.length; i++) {
      if (STATUSES[i].toLowerCase() === lower) return STATUSES[i];
    }
    if (lower === 'idea') return 'Idea';
    return raw;
  }

  function statusColor(status) {
    status = normalizeStatus(status);
    var map = {
      'Backlog': 'var(--text-muted,#6B7280)',
      'In Progress': 'var(--accent,#7c6fe0)',
      'Done': 'var(--success,#86C08B)',
      'On Hold': '#F59E0B',
      'Cancelled': 'var(--error,#F87171)'
    };
    return map[status] || 'var(--text-muted,#6B7280)';
  }

  function renderEntry(sectionName, entry, index, total) {
    var entryName = entry.name || '';
    var lines = entry.lines || [];
    var displayName = entryName;
    if (lines.length && lines[0].indexOf('### ') === 0) {
      displayName = lines[0].replace(/^###\s+/, '');
    }
    var statusLine = '';
    var statusVal = '';
    for (var i = 0; i < Math.min(lines.length, 5); i++) {
      var match = lines[i].match(/\*\*Status:\*\*\s*(.+)/);
      if (match) {
        statusVal = normalizeStatus(match[1]);
        statusLine = '- **Status:** ' + statusVal;
        break;
      }
    }

    var previewText = lines.slice(1).filter(function(line) {
      return !/^\s*-\s*\*\*(Status|Added):\*\*/i.test(line)
        && !/^\s*-\s*\*\*Notes:\*\*\s*-\s*\*\*Status:\*\*/i.test(line);
    }).map(function(line) {
      return line.replace(/^\s*-\s*\*\*Notes:\*\*\s*/i, '');
    }).join(' ').slice(0, 160);

    var isEditing = editingEntry && editingEntry.sectionName === sectionName && editingEntry.entryName === entryName;

    if (isEditing) {
      var allLines = lines.join('\n');
      return [
        '<div style="background:var(--bg-secondary,#11100E);border:2px solid var(--accent);border-radius:8px;padding:10px 12px;margin-bottom:6px">',
          '<textarea class="ideas-edit-textarea" style="width:100%;min-height:150px;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:6px;padding:8px;font-family:Monaco,Menlo,monospace;font-size:11px;resize:vertical;box-sizing:border-box;line-height:1.5">' + esc(allLines) + '</textarea>',
          '<div style="display:flex;gap:6px;margin-top:8px;justify-content:flex-end">',
            '<button class="ideas-save-edit" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" style="background:var(--success,#86C08B);color:#0A0908;border:none;border-radius:4px;padding:4px 12px;cursor:pointer;font-size:11px;font-weight:600">Save</button>',
            '<button class="ideas-cancel-edit" style="background:var(--bg-tertiary);color:var(--text-secondary);border:1px solid var(--border);border-radius:4px;padding:4px 12px;cursor:pointer;font-size:11px">Cancel</button>',
          '</div>',
        '</div>'
      ].join('\n');
    }

    return [
      '<div class="ideas-view-entry" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" data-index="' + index + '" style="background:var(--bg-secondary,#11100E);border:1px solid var(--border);border-radius:8px;margin-bottom:6px;cursor:default;transition:border-color 0.15s,opacity 0.15s;display:flex;position:relative">',
        // Reorder arrows
        '<div style="flex-shrink:0;width:38px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:2px;padding:4px 6px">',
          '<button class="ideas-move-up" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" ' + (index === 0 ? 'disabled' : '') + ' style="background:none;border:1px solid ' + (index === 0 ? 'transparent' : 'var(--border)') + ';color:' + (index === 0 ? 'var(--text-muted)' : 'var(--text-secondary)') + ';cursor:' + (index === 0 ? 'default' : 'pointer') + ';font-size:14px;padding:2px 7px;border-radius:4px;line-height:1;opacity:' + (index === 0 ? '0.3' : '0.8') + ';transition:all 0.15s" title="Move up">▲</button>',
          '<button class="ideas-move-down" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" ' + (index === total - 1 ? 'disabled' : '') + ' style="background:none;border:1px solid ' + (index === total - 1 ? 'transparent' : 'var(--border)') + ';color:' + (index === total - 1 ? 'var(--text-muted)' : 'var(--text-secondary)') + ';cursor:' + (index === total - 1 ? 'default' : 'pointer') + ';font-size:14px;padding:2px 7px;border-radius:4px;line-height:1;opacity:' + (index === total - 1 ? '0.3' : '0.8') + ';transition:all 0.15s" title="Move down">▼</button>',
        '</div>',
        // Content + actions
        '<div style="flex:1;display:flex;align-items:flex-start;gap:6px;padding:10px 12px;min-width:0">',
          '<div style="flex:1;min-width:0">',
            '<div style="font-weight:600;color:var(--text-primary);font-size:13px;margin-bottom:2px">' + esc(displayName) + '</div>',
            statusLine ? '<div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">' + esc(statusLine.replace(/\*\*/g, '')) + '</div>' : '',
            '<div style="font-size:11px;color:var(--text-secondary);line-height:1.5;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">' + esc(previewText) + '</div>',
          '</div>',
          // Action buttons
          '<div style="display:flex;gap:2px;flex-shrink:0;flex-direction:column">',
            '<button class="ideas-status-cycle" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" style="background:' + statusColor(statusVal) + ';color:#fff;border:none;border-radius:3px;padding:1px 6px;cursor:pointer;font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;line-height:1.4;min-width:42px;text-align:center" title="Cycle status">' + (statusVal || '⋯') + '</button>',
            '<button class="ideas-edit-entry" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" style="background:var(--bg-tertiary);color:var(--text-secondary);border:1px solid var(--border);border-radius:3px;padding:1px 6px;cursor:pointer;font-size:9px" title="Edit">✏️</button>',
            '<button class="ideas-delete-entry" data-section="' + esc(sectionName) + '" data-entry="' + esc(entryName) + '" style="background:var(--bg-tertiary);color:var(--error,#F87171);border:1px solid var(--border);border-radius:3px;padding:1px 6px;cursor:pointer;font-size:9px" title="Delete">✕</button>',
          '</div>',
        '</div>',
      '</div>'
    ].join('\n');
  }

  // Wire up edit save/cancel after render
  function wireEditButtons() {
    document.querySelectorAll('.ideas-save-edit').forEach(function(btn) {
      btn.onclick = function() { saveEdit(btn.dataset.section, btn.dataset.entry); };
    });
    document.querySelectorAll('.ideas-cancel-edit').forEach(function(btn) {
      btn.onclick = function() { editingEntry = null; renderSections(sectionsData); };
    });
  }

  // ── CRUD Actions ──

  function moveEntry(sectionName, entryName, direction) {
    var section = sectionsData.find(function(s) { return s.name === sectionName; });
    if (!section) return;
    var entries = section.entries || [];
    var idx = -1;
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].name === entryName) { idx = i; break; }
    }
    if (idx === -1) return;
    if (direction === 'up' && idx === 0) return;
    if (direction === 'down' && idx === entries.length - 1) return;

    var swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    var tmp = entries[idx];
    entries[idx] = entries[swapIdx];
    entries[swapIdx] = tmp;
    var order = entries.map(function(e) { return e.name; });
    postReorder(sectionName, order);
  }

  function postReorder(sectionName, order) {
    fetch('/api/ideas/reorder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_name: sectionName, order: order })
    }).then(reloadAfterAction).catch(reloadAfterAction);
  }

  function cycleStatus(sectionName, entryName) {
    var section = sectionsData.find(function(s) { return s.name === sectionName; });
    if (!section) return;
    var entry = (section.entries || []).find(function(e) { return e.name === entryName; });
    if (!entry) return;
    var lines = entry.lines || [];
    // Find current status
    var curStatus = 'Backlog';
    for (var i = 0; i < lines.length; i++) {
      var m = lines[i].match(/\*\*Status:\*\*\s*(.+)/);
      if (m) { curStatus = m[1].trim(); break; }
    }
    curStatus = normalizeStatus(curStatus);
    // Cycle to next — normalize first so lowercase/corrupted legacy values still advance.
    var curIdx = -1;
    var curLower = curStatus.toLowerCase();
    for (var i = 0; i < STATUSES.length; i++) {
      if (STATUSES[i].toLowerCase() === curLower) { curIdx = i; break; }
    }
    var nextStatus = STATUSES[(curIdx + 1 + STATUSES.length) % STATUSES.length];
    fetch('/api/ideas/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_name: sectionName, entry_name: entryName, new_status: nextStatus })
    }).then(reloadAfterAction).catch(reloadAfterAction);
  }

  function deleteEntry(sectionName, entryName) {
    if (!confirm('Delete "' + entryName + '"?')) return;
    fetch('/api/ideas/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_name: sectionName, entry_name: entryName })
    }).then(reloadAfterAction).catch(reloadAfterAction);
  }

  function editEntryInline(sectionName, entryName) {
    editingEntry = { sectionName: sectionName, entryName: entryName };
    renderSections(sectionsData);
    wireEditButtons();
    setTimeout(function() {
      var ta = document.querySelector('.ideas-edit-textarea');
      if (ta) ta.focus();
    }, 100);
  }

  function saveEdit(sectionName, entryName) {
    var ta = document.querySelector('.ideas-edit-textarea');
    if (!ta) return;
    var raw = ta.value;
    var lines = raw.split('\n');
    var newName = entryName;
    var newNotes = raw;
    var newStatus = '';
    // If first line is a markdown heading, split into name + editable body.
    // The backend writes Status/Added metadata itself, so do not feed those
    // metadata lines back as Notes or they become visible duplicate text.
    if (lines.length && lines[0].trim().startsWith('### ')) {
      newName = lines[0].trim().replace(/^###\s+/, '');
      var noteLines = [];
      lines.slice(1).forEach(function(line) {
        var statusMatch = line.match(/^\s*-\s*\*\*Status:\*\*\s*(.+)/i);
        if (statusMatch) {
          newStatus = normalizeStatus(statusMatch[1]);
          return;
        }
        if (/^\s*-\s*\*\*Added:\*\*/i.test(line)) return;
        var notesMatch = line.match(/^\s*-\s*\*\*Notes:\*\*\s*(.*)$/i);
        if (notesMatch) {
          if (notesMatch[1]) noteLines.push(notesMatch[1]);
          return;
        }
        noteLines.push(line);
      });
      newNotes = noteLines.join('\n').trim();
    }
    fetch('/api/ideas/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        section_name: sectionName,
        entry_name: entryName,
        new_name: newName,
        new_notes: newNotes,
        new_status: newStatus
      })
    }).then(function() {
      editingEntry = null;
      reloadAfterAction();
    }).catch(function() {
      editingEntry = null;
      reloadAfterAction();
    });
  }

  function viewEntryDetail(sectionName, entryName) {
    editEntryInline(sectionName, entryName); // Open in edit mode for now
  }

  function showAddEntryDialog(presetSection) {
    var sectionName = presetSection || '';
    var sections = sectionsData.map(function(s) { return s.name; });

    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = [
      '<div style="background:var(--bg-primary,#0a0908);border:1px solid var(--border);border-radius:12px;padding:20px;width:400px;max-width:90vw" onclick="event.stopPropagation()">',
        '<h3 style="margin:0 0 16px;color:var(--text-primary);font-size:15px">New Idea Entry</h3>',
        '<select id="add-section-select" style="width:100%;background:var(--bg-secondary);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box">',
          sections.map(function(n) { return '<option value="' + esc(n) + '"' + (n === sectionName ? ' selected' : '') + '>' + esc(n) + '</option>'; }).join(''),
        '</select>',
        '<input id="add-entry-name" type="text" placeholder="Entry name" style="width:100%;background:var(--bg-secondary);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box">',
        '<textarea id="add-entry-body" rows="6" placeholder="Entry body (markdown)" style="width:100%;background:var(--bg-secondary);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text-primary);font-size:13px;font-family:Monaco,Menlo,monospace;margin-bottom:12px;box-sizing:border-box;resize:vertical"></textarea>',
        '<div style="display:flex;gap:8px;justify-content:flex-end">',
          '<button id="add-cancel" style="background:var(--bg-tertiary);color:var(--text-secondary);border:1px solid var(--border);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px">Cancel</button>',
          '<button id="add-submit" style="background:var(--accent,#7c6fe0);color:white;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px;font-weight:600">Add Entry</button>',
        '</div>',
      '</div>'
    ].join('\n');

    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };
    document.body.appendChild(overlay);

    document.getElementById('add-cancel').onclick = function() { overlay.remove(); };
    document.getElementById('add-submit').onclick = function() {
      var sel = document.getElementById('add-section-select').value;
      var name = document.getElementById('add-entry-name').value.trim();
      var body = document.getElementById('add-entry-body').value.trim();
      if (!sel || !name || !body) return;
      overlay.remove();
      addEntry(sel, name, body);
    };
    document.getElementById('add-entry-name').focus();
  }

  function addEntry(sectionName, entryName, body) {
    fetch('/api/ideas/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_name: sectionName, entry_name: entryName, body: body })
    }).then(reloadAfterAction).catch(reloadAfterAction);
  }

  // Wire edit buttons after each render
  var origRender = renderSections;
  renderSections = function(sections) {
    origRender(sections);
    wireEditButtons();
  };

  // ── Header button injection ──

  function injectHeaderButton() {
    if (document.getElementById('ideas-header-btn')) return;

    var toolbar = document.querySelector('.toolbar-pill');
    if (!toolbar) return;

    var btn = document.createElement('button');
    btn.id = 'ideas-header-btn';
    btn.className = 'header-btn';
    btn.title = 'Ideas';
    btn.innerHTML = '💡';
    btn.style.cssText = 'background:none;border:1px solid transparent;border-radius:6px;padding:4px 8px;cursor:pointer;font-size:16px;color:var(--text-secondary);display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;transition:all 0.2s';
    btn.onmouseenter = function() { btn.style.background = 'var(--bg-tertiary)'; };
    btn.onmouseleave = function() { if (!panelOpen) btn.style.background = 'none'; };
    btn.onclick = function() {
      togglePanel();
      btn.style.background = panelOpen ? 'var(--bg-tertiary)' : 'none';
    };

    var overflowBtn = document.getElementById('header-overflow-btn');
    var target = overflowBtn || toolbar.lastElementChild;
    if (target) {
      toolbar.insertBefore(btn, target);
    } else {
      toolbar.appendChild(btn);
    }
  }

  // ── Startup ──

  var pollCount = 0;
  var pollInterval = setInterval(function() {
    injectHeaderButton();
    pollCount++;
    if (document.getElementById('ideas-header-btn') || pollCount > 40) {
      clearInterval(pollInterval);
    }
  }, 400);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      setTimeout(injectHeaderButton, 1800);
    });
  } else {
    setTimeout(injectHeaderButton, 1800);
  }

  window._ideasPanelToggle = togglePanel;
  window._ideasPanelOpen = function() { if (!panelOpen) openPanel(); };

})();
