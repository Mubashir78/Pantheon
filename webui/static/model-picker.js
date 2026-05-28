/* ── Pantheon Model Picker: Phase 2 session-scoped drawer ──
 * /model opens a compact provider → model drawer.
 * Selecting a model updates the active session via /api/session/update.
 * This file only reads localStorage for the active session identity; model
 * authority comes from the server session update response.
 */
(function () {
  'use strict';

  var state = {
    open: false,
    loading: false,
    saving: false,
    providers: [],
    selectedProviderId: null,
    activeProvider: null,
    defaultModel: '',
    loaded: false,
    loadingPromise: null
  };

  function apiUrl(path) {
    return new URL(path, document.baseURI || window.location.href).href;
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function shortModelName(modelId) {
    var text = String(modelId || '');
    var colon = text.indexOf(':');
    if (text.charAt(0) === '@' && colon !== -1) text = text.slice(colon + 1);
    if (text.indexOf('/') !== -1) text = text.split('/').pop();
    return text || 'model';
  }

  function toast(message, kind) {
    if (typeof window.showToast === 'function') {
      try { window.showToast(message, 3000); return; } catch (_) {}
    }
    var el = document.createElement('div');
    el.className = 'mp-toast mp-toast-' + (kind || 'info');
    el.textContent = message;
    document.body.appendChild(el);
    window.setTimeout(function () {
      el.classList.add('mp-toast-hide');
      window.setTimeout(function () { if (el.parentNode) el.remove(); }, 240);
    }, 3200);
  }

  function readResponseError(response, data, fallback) {
    if (data && typeof data === 'object') {
      return data.error || data.detail || data.message || fallback;
    }
    if (typeof data === 'string' && data.trim()) return data.trim();
    return fallback;
  }

  async function fetchJson(path, options) {
    var response = await fetch(apiUrl(path), Object.assign({ credentials: 'include' }, options || {}));
    var text = await response.text();
    var data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = text; }
    }
    if (!response.ok || (data && typeof data === 'object' && data.ok === false)) {
      throw new Error(readResponseError(response, data, 'HTTP ' + response.status));
    }
    return data || {};
  }

  function normalizeGroups(data) {
    var groups = Array.isArray(data && data.groups) ? data.groups : [];
    return groups.map(function (group) {
      return {
        provider: group.provider || group.provider_id || 'Provider',
        provider_id: group.provider_id || group.provider || '',
        models: Array.isArray(group.models) ? group.models : []
      };
    }).filter(function (group) { return group.provider_id; });
  }

  async function loadModels(force) {
    if (state.loaded && !force) return state.providers;
    if (state.loadingPromise && !force) return state.loadingPromise;
    state.loading = true;
    renderDrawer();
    state.loadingPromise = fetchJson('/api/models').then(function (data) {
      state.providers = normalizeGroups(data);
      state.activeProvider = data.active_provider || null;
      state.defaultModel = data.default_model || '';
      if (!state.selectedProviderId || !state.providers.some(function (p) { return p.provider_id === state.selectedProviderId; })) {
        var preferred = state.providers.find(function (p) { return p.provider_id === state.activeProvider; });
        state.selectedProviderId = (preferred || state.providers[0] || {}).provider_id || null;
      }
      state.loaded = true;
      return state.providers;
    }).catch(function (err) {
      state.providers = [];
      state.loaded = true;
      toast('Could not load models: ' + (err && err.message ? err.message : err), 'error');
      return [];
    }).finally(function () {
      state.loading = false;
      state.loadingPromise = null;
      renderDrawer();
    });
    return state.loadingPromise;
  }

  function getActiveSessionId() {
    var candidates = [];
    try {
      candidates.push(window.__hermesActiveSessionId);
      candidates.push(window.activeSessionId);
      candidates.push(window.currentSessionId);
    } catch (_) {}
    try {
      candidates.push(localStorage.getItem('hermes-active-session'));
      candidates.push(localStorage.getItem('hermes-webui-session'));
    } catch (_) {}
    try {
      var url = new URL(window.location.href);
      candidates.push(url.searchParams.get('session_id'));
      candidates.push(url.searchParams.get('session'));
    } catch (_) {}
    for (var i = 0; i < candidates.length; i += 1) {
      var value = String(candidates[i] || '').trim();
      if (value && value !== 'null' && value !== 'undefined') return value;
    }
    return '';
  }

  function findModel(modelId, providerId) {
    var id = String(modelId || '').trim();
    if (!id) return null;
    var providerHint = String(providerId || '').trim();
    for (var i = 0; i < state.providers.length; i += 1) {
      var provider = state.providers[i];
      if (providerHint && provider.provider_id !== providerHint) continue;
      var models = provider.models || [];
      for (var j = 0; j < models.length; j += 1) {
        if (String(models[j].id || '') === id) return { provider: provider, model: models[j] };
      }
    }
    if (id.charAt(0) === '@') {
      var colon = id.indexOf(':');
      if (colon > 1) {
        var inferredProvider = id.slice(1, colon);
        var matchProvider = state.providers.find(function (p) { return p.provider_id === inferredProvider; });
        if (matchProvider) return { provider: matchProvider, model: { id: id, label: shortModelName(id), capabilities: {} } };
      }
    }
    if (providerHint) {
      var explicitProvider = state.providers.find(function (p) { return p.provider_id === providerHint; });
      if (explicitProvider) return { provider: explicitProvider, model: { id: id, label: shortModelName(id), capabilities: {} } };
    }
    return null;
  }

  function parseDirectModelCommand(commandText) {
    return parseDirectModelArg(String(commandText || '').trim().slice('/model'.length).trim());
  }

  function parseDirectModelArg(arg) {
    arg = String(arg || '').trim();
    if (!arg) return null;
    var providerId = '';
    var modelId = arg;
    var slash = arg.indexOf('/');
    if (slash > 0) {
      var possibleProvider = arg.slice(0, slash).trim();
      var rest = arg.slice(slash + 1).trim();
      if (rest && state.providers.some(function (p) { return p.provider_id === possibleProvider || p.provider === possibleProvider; })) {
        var provider = state.providers.find(function (p) { return p.provider_id === possibleProvider || p.provider === possibleProvider; });
        providerId = provider.provider_id;
        modelId = rest;
      }
    }
    return { modelId: modelId, providerId: providerId, rawArg: arg };
  }

  function selectedProvider() {
    return state.providers.find(function (p) { return p.provider_id === state.selectedProviderId; }) || state.providers[0] || null;
  }

  function ensureStyles() {
    if (document.getElementById('mp-drawer-styles')) return;
    var style = document.createElement('style');
    style.id = 'mp-drawer-styles';
    style.textContent = [
      '.mp-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.48);z-index:99990;}',
      '.mp-drawer{position:fixed;right:14px;bottom:88px;width:min(420px,calc(100vw - 28px));max-height:min(620px,calc(100dvh - 116px));z-index:99991;background:var(--bg-secondary,#1e1e2e);border:1px solid var(--border,#313244);border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,.45);display:flex;flex-direction:column;overflow:hidden;font-family:inherit;color:var(--text-primary,#cdd6f4);}',
      '.mp-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid var(--border,#313244);}',
      '.mp-title{font-size:14px;font-weight:750;letter-spacing:.01em}.mp-subtitle{margin-top:2px;font-size:11px;color:var(--text-muted,#6c7086);}',
      '.mp-icon-btn{border:0;background:transparent;color:var(--text-muted,#6c7086);font-size:18px;line-height:1;cursor:pointer;border-radius:8px;padding:4px 7px}.mp-icon-btn:hover{background:rgba(255,255,255,.06);color:var(--text-primary,#cdd6f4);}',
      '.mp-provider-row{display:flex;gap:6px;padding:9px 12px;border-bottom:1px solid var(--border,#313244);overflow-x:auto;}',
      '.mp-provider-btn{border:0;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:650;cursor:pointer;white-space:nowrap;background:transparent;color:var(--text-secondary,#a6adc8);}.mp-provider-btn:hover{background:rgba(137,180,250,.10);color:var(--text-primary,#cdd6f4);}.mp-provider-btn.active{background:rgba(137,180,250,.18);color:var(--accent,#89b4fa);}',
      '.mp-body{overflow:auto;padding:8px;}.mp-empty{padding:28px 16px;text-align:center;color:var(--text-muted,#6c7086);font-size:13px;}',
      '.mp-model-btn{width:100%;border:0;border-radius:12px;padding:10px 11px;margin:2px 0;cursor:pointer;text-align:left;background:transparent;color:inherit;display:flex;align-items:center;justify-content:space-between;gap:10px;}.mp-model-btn:hover{background:rgba(137,180,250,.09);}.mp-model-btn:disabled{opacity:.55;cursor:wait;}',
      '.mp-model-main{display:flex;flex-direction:column;gap:3px;min-width:0;}.mp-model-label{font-size:13px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.mp-model-id{font-size:10px;color:var(--text-muted,#6c7086);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
      '.mp-caps{display:flex;gap:4px;flex-shrink:0;}.mp-cap{font-size:9px;font-weight:750;border-radius:5px;padding:2px 5px;background:rgba(255,255,255,.07);color:var(--text-secondary,#a6adc8);}.mp-cap.vision{background:rgba(81,207,102,.15);color:var(--success,#51CF66);}.mp-cap.reasoning{background:rgba(255,212,59,.14);color:#FFD43B;}',
      '.mp-toast{position:fixed;left:50%;bottom:82px;transform:translateX(-50%);z-index:100000;max-width:min(92vw,560px);padding:10px 16px;border-radius:12px;background:var(--bg-secondary,#1e1e2e);border:1px solid var(--border,#313244);box-shadow:0 12px 36px rgba(0,0,0,.35);color:var(--text-primary,#cdd6f4);font-size:13px;font-weight:650;text-align:center;transition:opacity .22s ease, transform .22s ease;}.mp-toast-ok{border-color:rgba(81,207,102,.45);}.mp-toast-error{border-color:rgba(255,107,107,.45);}.mp-toast-hide{opacity:0;transform:translateX(-50%) translateY(8px);}',
      '@media (max-width:600px){.mp-drawer{left:10px;right:10px;bottom:74px;width:auto;max-height:calc(100dvh - 94px);}}'
    ].join('\n');
    document.head.appendChild(style);
  }

  function openDrawer() {
    if (state.open) return;
    ensureStyles();
    state.open = true;
    renderDrawer();
    loadModels(false);
  }

  function closeDrawer() {
    state.open = false;
    var backdrop = document.getElementById('mp-backdrop');
    var drawer = document.getElementById('mp-drawer');
    if (backdrop) backdrop.remove();
    if (drawer) drawer.remove();
  }

  async function selectModel(modelId, providerId, modelLabel) {
    if (state.saving) return;
    var sessionId = getActiveSessionId();
    if (!sessionId) {
      toast('Open a chat first.', 'error');
      return;
    }
    var resolved = findModel(modelId, providerId);
    var resolvedProviderId = providerId || (resolved && resolved.provider && resolved.provider.provider_id) || '';
    var exactModelId = String(modelId || '').trim();
    if (!exactModelId) return;
    if (!resolvedProviderId) {
      toast('Could not determine provider for ' + shortModelName(exactModelId) + '.', 'error');
      return;
    }

    state.saving = true;
    renderDrawer();
    try {
      var data = await fetchJson('/api/session/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          model: exactModelId,
          model_provider: resolvedProviderId
        })
      });
      var session = data.session || data;
      var canonicalModel = session.model || exactModelId;
      var canonicalProvider = session.model_provider || resolvedProviderId;
      updateVisibleModelSelect(canonicalModel, canonicalProvider);
      closeDrawer();
      toast('Switched this chat to ' + canonicalModel + ' via ' + canonicalProvider, 'ok');
    } catch (err) {
      toast('Could not switch model: ' + (err && err.message ? err.message : err), 'error');
    } finally {
      state.saving = false;
      renderDrawer();
    }
  }

  function updateVisibleModelSelect(modelId, providerId) {
    // Cosmetic only: keep any visible native select/chip in sync when possible.
    // This is not a runtime source of authority and does not persist anything.
    var select = document.getElementById('modelSelect');
    if (select) {
      var option = Array.prototype.find.call(select.options || [], function (opt) {
        var optProvider = opt.parentElement && opt.parentElement.dataset ? opt.parentElement.dataset.provider : '';
        return opt.value === modelId && (!providerId || !optProvider || optProvider === providerId);
      });
      if (option) select.value = option.value;
      if (typeof window.syncModelChip === 'function') {
        try { window.syncModelChip(); } catch (_) {}
      }
    }
    try {
      window.dispatchEvent(new CustomEvent('hermes:model-session-updated', {
        detail: { model: modelId, model_provider: providerId, session_id: getActiveSessionId() }
      }));
    } catch (_) {}
  }

  function renderDrawer() {
    if (!state.open) return;
    ensureStyles();
    var previousBackdrop = document.getElementById('mp-backdrop');
    var previousDrawer = document.getElementById('mp-drawer');
    if (previousBackdrop) previousBackdrop.remove();
    if (previousDrawer) previousDrawer.remove();

    var provider = selectedProvider();
    var models = provider && Array.isArray(provider.models) ? provider.models : [];
    var html = '';
    html += '<div id="mp-backdrop" class="mp-backdrop"></div>';
    html += '<section id="mp-drawer" class="mp-drawer" role="dialog" aria-modal="true" aria-label="Choose chat model">';
    html += '<header class="mp-head"><div><div class="mp-title">Chat model</div><div class="mp-subtitle">Applies to this chat from your next message.</div></div><button id="mp-close" class="mp-icon-btn" type="button" aria-label="Close">×</button></header>';

    if (state.loading) {
      html += '<div class="mp-empty">Loading models…</div>';
    } else if (!state.providers.length) {
      html += '<div class="mp-empty">No models available.</div>';
    } else {
      html += '<nav class="mp-provider-row" aria-label="Providers">';
      state.providers.forEach(function (p) {
        var active = p.provider_id === state.selectedProviderId;
        html += '<button type="button" class="mp-provider-btn' + (active ? ' active' : '') + '" data-provider="' + escapeHtml(p.provider_id) + '">' + escapeHtml(p.provider || p.provider_id) + '</button>';
      });
      html += '</nav>';
      html += '<div class="mp-body">';
      if (!models.length) {
        html += '<div class="mp-empty">No models in this provider.</div>';
      }
      models.forEach(function (m) {
        var id = String(m.id || '');
        var label = String(m.label || shortModelName(id));
        var caps = m.capabilities || {};
        html += '<button type="button" class="mp-model-btn" data-model="' + escapeHtml(id) + '" data-label="' + escapeHtml(label) + '" data-provider="' + escapeHtml(provider.provider_id) + '"' + (state.saving ? ' disabled' : '') + '>';
        html += '<span class="mp-model-main"><span class="mp-model-label">' + escapeHtml(label) + '</span><span class="mp-model-id">' + escapeHtml(id) + '</span></span>';
        html += '<span class="mp-caps">';
        if (caps.vision) html += '<span class="mp-cap vision">Vision</span>';
        if (caps.reasoning) html += '<span class="mp-cap reasoning">Reasoning</span>';
        html += '</span></button>';
      });
      html += '</div>';
    }
    html += '</section>';

    var mount = document.createElement('div');
    mount.innerHTML = html;
    while (mount.firstElementChild) document.body.appendChild(mount.firstElementChild);

    var backdrop = document.getElementById('mp-backdrop');
    var close = document.getElementById('mp-close');
    if (backdrop) backdrop.addEventListener('click', closeDrawer);
    if (close) close.addEventListener('click', closeDrawer);
    Array.prototype.forEach.call(document.querySelectorAll('.mp-provider-btn'), function (btn) {
      btn.addEventListener('click', function () {
        state.selectedProviderId = btn.dataset.provider;
        renderDrawer();
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.mp-model-btn'), function (btn) {
      btn.addEventListener('click', function () {
        selectModel(btn.dataset.model, btn.dataset.provider, btn.dataset.label);
      });
    });
  }

  function clearControlledTextarea(textarea) {
    var proto = window.HTMLTextAreaElement && window.HTMLTextAreaElement.prototype;
    var descriptor = proto && Object.getOwnPropertyDescriptor(proto, 'value');
    if (descriptor && descriptor.set) descriptor.set.call(textarea, '');
    else textarea.value = '';
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function isComposerTextarea(target) {
    if (!target || target.tagName !== 'TEXTAREA') return false;
    if (target.id === 'msg') return true;
    return !!(target.closest && (target.closest('.composer-box') || target.closest('.input-area')));
  }

  async function handleDirectCommand(commandText) {
    var parsed = parseDirectModelCommand(commandText);
    if (!parsed) return;
    if (!state.loaded) {
      await loadModels(false);
      // Re-parse after the catalog is available so optional provider/model
      // shorthand can resolve provider names without treating them as model IDs.
      parsed = parseDirectModelArg(parsed.rawArg || parsed.modelId);
    }
    var match = findModel(parsed.modelId, parsed.providerId);
    if (!match && !parsed.providerId) {
      toast('Open the model drawer to choose a provider for ' + shortModelName(parsed.modelId) + '.', 'error');
      openDrawer();
      return;
    }
    selectModel(parsed.modelId, parsed.providerId || (match && match.provider.provider_id), parsed.modelId);
  }

  function interceptSlashCommand() {
    function handleExactModelInput(event) {
      var textarea = event.target;
      if (!isComposerTextarea(textarea)) return;
      if (String(textarea.value || '').trim() !== '/model') return;

      if (typeof event.stopPropagation === 'function') event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
      clearControlledTextarea(textarea);
      openDrawer();
    }

    document.addEventListener('input', handleExactModelInput, true);
    document.addEventListener('change', handleExactModelInput, true);

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
      var textarea = event.target;
      if (!isComposerTextarea(textarea)) return;
      var text = String(textarea.value || '').trim();
      if (text !== '/model' && text.indexOf('/model ') !== 0) return;

      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
      clearControlledTextarea(textarea);

      if (text === '/model') openDrawer();
      else handleDirectCommand(text);
    }, true);
  }

  function init() {
    ensureStyles();
    interceptSlashCommand();
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && state.open) {
      event.preventDefault();
      closeDrawer();
    }
  }, true);

  window.PantheonModelPicker = {
    open: openDrawer,
    close: closeDrawer,
    reload: function () { return loadModels(true); }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
