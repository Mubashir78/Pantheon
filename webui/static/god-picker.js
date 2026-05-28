/* ── Pantheon God Picker (Sidebar Grid) ──
 * 2xN responsive god grid between logo and Chat in sidebar.
 * Gods max 50x50px. Responsive columns.
 * Edit icon on each god circle, explicit summon button below grid.
 */
(function() {
  'use strict';

  function createGodPicker() {
    var picker = document.createElement('div');
    picker.id = 'god-picker';
    picker.innerHTML = 
      '<div class="gp-label">Gods</div>' +
      '<div class="gp-grid" id="gp-grid"></div>' +
      '<div class="gp-summon-row" id="gp-summon-row"></div>';
    return picker;
  }

  function fetchGods() {
    return fetch('/api/gods')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var gods = data.gods || data || [];
        return gods.filter(function(g) {
          return !(g.god && g.god.hidden) && !g.hidden;
        });
      })
      .catch(function() { return []; });
  }

  function renderGodGrid(gods) {
    var grid = document.getElementById('gp-grid');
    if (!grid) return;

    grid.innerHTML = gods.map(function(god) {
      var name = god.display_name || god.name || '?';
      var initial = name.charAt(0).toUpperCase();
      var icon = '/api/gods/' + encodeURIComponent(god.name || name) + '/icon';
      var activeCls = god.is_active ? ' active' : '';
      return '<div class="gp-circle' + activeCls + '" data-god="' + (god.name || name) + '" title="' + name + '">' +
        '<img src="' + icon + '" class="gp-icon" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' +
        '<span class="gp-initial" style="display:none">' + initial + '</span>' +
        '</div>';
    }).join('');

    // Attach edit buttons programmatically (avoids template rendering issues)
    grid.querySelectorAll('.gp-circle').forEach(function(circ) {
      var godName = circ.dataset.god;
      var editBtn = document.createElement('button');
      editBtn.className = 'gp-edit-btn';
      editBtn.title = 'Edit ' + (godName || '');
      editBtn.textContent = '\u270F\uFE0F';
      editBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        if (typeof window.openGodEditor === 'function') {
          window.openGodEditor(godName);
        }
      });
      circ.appendChild(editBtn);
    });

    // Click: god circle → summon
    grid.querySelectorAll('.gp-circle').forEach(function(c) {
      c.addEventListener('click', function(e) {
        if (e.target.classList.contains('gp-edit-btn')) return;
        switchGod(this.dataset.god);
      });
    });

    // Update summon row
    updateSummonRow(gods);
  }

  function updateSummonRow(gods) {
    var row = document.getElementById('gp-summon-row');
    if (!row) return;

    var activeGod = gods.find(function(g) { return g.is_active; });
    if (activeGod) {
      var name = activeGod.display_name || activeGod.name || 'Unknown';
      row.innerHTML = '<button class="gp-summon-btn gp-summon-active" disabled>&#x26A1; ' + escAttr(name) + ' (active)</button>';
      row.style.display = 'block';
    } else if (gods.length > 0) {
      var first = gods[0];
      var firstName = first.display_name || first.name || 'God';
      var godName = first.name || firstName;
      row.innerHTML = '<button class="gp-summon-btn" data-god="' + escAttr(godName) + '">&#x26A1; Summon ' + escAttr(firstName) + '</button>';
      var btn = row.querySelector('.gp-summon-btn');
      if (btn) {
        btn.addEventListener('click', function() {
          switchGod(this.dataset.god);
        });
      }
      row.style.display = 'block';
    } else {
      row.style.display = 'none';
      row.innerHTML = '';
    }
  }

  function escAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function switchGod(godName) {
    fetch('/api/profile/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: godName })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data && !data.error) {
        try { localStorage.setItem('hermes-personality', godName); } catch(e) {}
        
        fetchGods().then(function(gods) {
          if (gods.length) {
            renderGodGrid(gods);
            var active = gods.find(function(g) { return g.is_active; });
            if (active && active.color) {
              window.__GOD_CACHE__ = active;
              document.documentElement.style.setProperty('--god-accent', active.color);
              var r = parseInt(active.color.slice(1,3), 16);
              var gn = parseInt(active.color.slice(3,5), 16);
              var b = parseInt(active.color.slice(5,7), 16);
              var s = document.getElementById('god-glow-react-base');
              if (s) s.textContent = '.assistant-msg .message-content{background:linear-gradient(to right,rgba('+r+','+gn+','+b+',0.20),rgba('+r+','+gn+','+b+',0) 75%)!important;border-radius:4px!important}';
            }
          }
        });
        
        try {
          window.dispatchEvent(new CustomEvent('hermes:profile-changed', {
            detail: { profile: godName }
          }));
        } catch(e) {}
      }
    })
    .catch(function() {
      window.location.href = '/api/profile/switch?name=' + encodeURIComponent(godName);
    });
  }

  function injectStyles() {
    if (document.getElementById('gp-styles')) return;
    var style = document.createElement('style');
    style.id = 'gp-styles';
    style.textContent = ''
      + '#god-picker { padding: 8px 12px 4px; }'
      + '.gp-label { font-size: 10px; text-transform: uppercase; color: var(--text-muted,#6b7c84); margin-bottom: 6px; font-weight: 600; letter-spacing: 0.5px; }'
      + '.gp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(44px, 1fr)); gap: 6px; max-height: 130px; overflow-y: auto; }'
      + '.gp-grid::-webkit-scrollbar { width: 3px; }'
      + '.gp-grid::-webkit-scrollbar-thumb { background: var(--border,#3B4A50); border-radius: 2px; }'
      + '.gp-circle { width: 100%; max-width: 50px; aspect-ratio: 1; border-radius: 10px; background: var(--bg-secondary,#11100E); border: 2px solid transparent; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; overflow: visible; transition: border-radius 0.15s, border-color 0.15s; position: relative; margin: 0 auto; }'
      + '.gp-circle:hover { border-radius: 12px; border-color: var(--accent,#C6AC8F); }'
      + '.gp-circle.active { border-color: var(--accent,#C6AC8F); border-radius: 12px; }'
      + '.gp-icon { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }'
      + '.gp-initial { font-size: 14px; font-weight: 700; color: var(--text-primary,#EAE0D5); font-family: system-ui, sans-serif; }'
      /* ── Edit button (always visible, top-right corner) ── */
      + '.gp-edit-btn { position: absolute; top: -6px; right: -6px; width: 20px; height: 20px; border-radius: 50%; background: var(--bg-primary,#0a0908); border: 1px solid var(--border,#3B4A50); color: var(--text-muted,#6b7c84); font-size: 11px; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; line-height: 1; z-index: 2; transition: all 0.15s; }'
      + '.gp-edit-btn:active { background: var(--accent,#C6AC8F); color: #0a0908; border-color: var(--accent,#C6AC8F); transform: scale(1.15); }'
      /* ── Summon row ── */
      + '.gp-summon-row { margin-top: 6px; padding: 0 2px; display: none; }'
      + '.gp-summon-btn { width: 100%; background: var(--bg-secondary,#11100E); border: 1px solid var(--border,#3B4A50); border-radius: 8px; padding: 5px 10px; font-size: 11px; color: var(--text-secondary,#C6AC8F); cursor: pointer; transition: all 0.15s; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; box-sizing: border-box; }'
      + '.gp-summon-btn:hover:not(:disabled) { background: var(--accent,#C6AC8F); color: #0a0908; border-color: var(--accent,#C6AC8F); }'
      + '.gp-summon-btn:disabled { opacity: 0.5; cursor: default; border-color: var(--accent,#C6AC8F); color: var(--accent,#C6AC8F); }'
      + '.gp-summon-active { background: rgba(198,172,143,0.08); }';
    document.head.appendChild(style);
  }

  function inject() {
    injectStyles();

    // Hide the hardcoded personality dropdown from hermes-ui.html
    var hidePersonality = function() {
      var footer = document.querySelector('.sidebar-footer');
      if (footer) footer.style.display = 'none';
    };
    hidePersonality();
    var observer = new MutationObserver(function() {
      var footer = document.querySelector('.sidebar-footer');
      if (footer && footer.style.display !== 'none') footer.style.display = 'none';
    });
    observer.observe(document.body, { childList: true, subtree: true });

    function tryPlace() {
      var sidebarNav = document.querySelector('.sidebar-nav');
      if (!sidebarNav) return false;

      var existing = document.getElementById('god-picker');
      if (existing) return true;

      var picker = createGodPicker();
      sidebarNav.parentNode.insertBefore(picker, sidebarNav);

      fetchGods().then(function(gods) {
        if (gods.length) renderGodGrid(gods);
        setInterval(function() {
          fetchGods().then(function(g) { if (g.length) renderGodGrid(g); });
        }, 30000);
      });
      return true;
    }

    if (!tryPlace()) {
      var attempts = 0;
      var interval = setInterval(function() {
        attempts++;
        if (tryPlace() || attempts > 30) clearInterval(interval);
      }, 400);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { setTimeout(inject, 1000); });
  } else {
    setTimeout(inject, 1000);
  }
})();
