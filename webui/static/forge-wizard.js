/* ── Pantheon Forge Wizard ──
 * Chat-based god creation via Hephaestus backend.
 * Opens when +New God is clicked in the god picker.
 */
(function() {
  'use strict';

  function el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => {
      // Skip 'disabled' in attrs — use DOM property instead (setAttribute('disabled', false)
      // still makes the element disabled in HTML because any presence of the attribute = disabled)
      if (k === 'disabled') return;
      if (k === 'cls') e.className = v;
      else if (k === 'style') Object.assign(e.style, v);
      else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
      else e.setAttribute(k, v);
    });
    children.flat().forEach(c => { if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }

  function ForgeWizard(container) {
    let godName = '';
    let godDomain = '';
    let godIcon = '🧑‍💻';
    let godIconImage = null; // base64 data URL for uploaded image (overrides emoji)
    let godColor = '#7c6fe0';
    let godDisplayName = '';
    let messages = [];
    let state = 'name'; // name | chatting | review | forging | done | error
    let busy = false;
    let soulDraft = '';
    let emojiExpanded = false; // emoji grid collapsed by default

    // Common god emojis for the picker
    const GOD_EMOJIS = ['⚡','🔨','☀️','🔥','🦉','⚔️','🌾','🍷','🧠','📚','🎵','💻','🔮','🛡️','💀','🌊','🌙','⭐','🗡️','🏹','🎭','💼','🔬','✈️','🗺️','🎨','💰','🏛️','🌿','🖥️','🤖','🧑‍💻'];
    const root = el('div', { id: 'forge-wizard-overlay', cls: 'fw-overlay', style: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 9500, display: 'flex', alignItems: 'center', justifyContent: 'center' } });
    const panel = el('div', { cls: 'fw-panel', style: { background: 'var(--bg-primary, #0a0908)', border: '1px solid var(--border, #3B4A50)', borderRadius: '12px', width: '650px', maxWidth: '95vw', maxHeight: '85vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' } });
    root.appendChild(panel);

    function render() {
      panel.innerHTML = '';
      panel.appendChild(header());
      panel.appendChild(body());
      panel.appendChild(footer());
    }

    function header() {
      return el('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border, #3B4A50)' } },
        el('h2', { style: { margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary, #EAE0D5)' } }, '⚒️ Forge a God'),
        el('button', { style: { background: 'none', border: 'none', color: 'var(--text-muted, #666)', fontSize: '1.2rem', cursor: 'pointer', padding: '4px 8px' }, onClick: close }, '✕')
      );
    }

    function body() {
      const b = el('div', { style: { flex: 1, overflow: 'auto', padding: '20px 20px 24px 20px', display: 'flex', flexDirection: 'column', gap: '12px' } });

      if (state === 'name') {
        b.appendChild(el('p', { style: { color: 'var(--text-secondary, #C6AC8F)', fontSize: '14px', margin: '0 0 8px', lineHeight: 1.6 } },
          'Name your god and optionally describe their domain. Hephaestus will interview you to forge their SOUL.md.'));
        b.appendChild(el('input', { type: 'text', id: 'fw-god-name', placeholder: 'God name (e.g. athena, thoth)', value: godName, style: { width: '100%', boxSizing: 'border-box', background: 'var(--bg-secondary, #11100E)', border: '1px solid var(--border, #3B4A50)', borderRadius: '8px', padding: '10px 14px', color: 'var(--text-primary, #EAE0D5)', fontSize: '1rem', outline: 'none', marginBottom: '8px' },
          onInput: e => { godName = e.target.value.trim(); godDisplayName = godName.charAt(0).toUpperCase() + godName.slice(1); updateForgeBtn(); },
          onKeyDown: e => { if (e.key === 'Enter' && godName) startForge(); }
        }));
        b.appendChild(el('input', { type: 'text', id: 'fw-god-domain', placeholder: 'Domain (e.g. Knowledge, Code, Music)', value: godDomain, style: { width: '100%', boxSizing: 'border-box', background: 'var(--bg-secondary, #11100E)', border: '1px solid var(--border, #3B4A50)', borderRadius: '8px', padding: '10px 14px', color: 'var(--text-primary, #EAE0D5)', fontSize: '1rem', outline: 'none', marginBottom: '12px' },
          onInput: e => { godDomain = e.target.value.trim(); },
          onKeyDown: e => { if (e.key === 'Enter' && godName) startForge(); }
        }));

        // ── Icon section ──
        b.appendChild(el('label', { style: { display: 'block', fontSize: '12px', color: 'var(--text-muted, #666)', marginBottom: '4px', fontWeight: 600 } }, 'Icon'));

        // Preview row: shows selected emoji or uploaded image
        const previewRow = el('div', { style: { display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '8px' } });
        const previewBox = el('div', { id: 'fw-icon-preview', style: { width: '48px', height: '48px', borderRadius: '8px', border: '2px solid var(--accent, #7c6fe0)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '28px', background: 'var(--bg-secondary, #11100E)', overflow: 'hidden', flexShrink: 0 } });
        function updateIconPreview() {
          if (godIconImage) {
            previewBox.innerHTML = `<img src="${godIconImage}" style="width:100%;height:100%;object-fit:cover">`;
          } else {
            previewBox.innerHTML = '';
            previewBox.textContent = godIcon;
          }
        }
        previewRow.appendChild(previewBox);

        // Upload button
        const uploadLabel = el('label', { style: { display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'var(--bg-secondary, #11100E)', border: '1px solid var(--border, #3B4A50)', borderRadius: '6px', padding: '6px 12px', fontSize: '12px', color: 'var(--text-secondary, #C6AC8F)', cursor: 'pointer', whiteSpace: 'nowrap' } },
          '📁 Upload',
          el('input', { type: 'file', accept: 'image/*', style: { display: 'none' },
            onChange: function(e) {
              const file = e.target.files && e.target.files[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = function(ev) {
                godIconImage = ev.target.result;
                godIcon = '';
                updateIconPreview();
              };
              reader.readAsDataURL(file);
            }
          })
        );
        previewRow.appendChild(uploadLabel);

        // Clear button
        const clearBtn = el('button', { type: 'button', id: 'fw-clear-icon', style: { display: godIconImage ? 'inline-flex' : 'none', alignItems: 'center', background: 'transparent', border: '1px solid var(--border, #3B4A50)', borderRadius: '6px', padding: '6px 8px', fontSize: '12px', color: 'var(--text-muted, #666)', cursor: 'pointer' },
          onClick: function() {
            godIconImage = null;
            godIcon = '🧑‍💻';
            updateIconPreview();
            render();
          }
        }, '✕ Clear');
        previewRow.appendChild(clearBtn);
        b.appendChild(previewRow);
        updateIconPreview();

        // Emoji toggle + collapsible grid
        const emojiToggle = el('button', { type: 'button', style: { background: 'none', border: 'none', color: 'var(--text-muted, #666)', fontSize: '11px', cursor: 'pointer', padding: '2px 0', textAlign: 'left', marginBottom: emojiExpanded ? '4px' : '0' },
          onClick: () => { emojiExpanded = !emojiExpanded; render(); }
        }, emojiExpanded ? '▾ Hide emoji picker' : '▸ Show emoji picker');
        b.appendChild(emojiToggle);

        if (emojiExpanded) {
          const iconGrid = el('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(36px, 1fr))', gap: '4px', marginBottom: '12px', maxHeight: '100px', overflowY: 'auto' } });
          GOD_EMOJIS.forEach(emoji => {
            const btn = el('button', { type: 'button', style: { background: (!godIconImage && godIcon === emoji) ? 'var(--accent, #7c6fe0)' : 'var(--bg-secondary, #11100E)', border: (!godIconImage && godIcon === emoji) ? '2px solid var(--accent, #7c6fe0)' : '1px solid var(--border, #3B4A50)', borderRadius: '6px', fontSize: '18px', cursor: 'pointer', padding: '2px', width: '36px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center' },
              onClick: () => { godIcon = emoji; godIconImage = null; updateIconPreview(); render(); } }, emoji);
            iconGrid.appendChild(btn);
          });
          b.appendChild(iconGrid);
        }

    // ── Color picker helpers (HSL ↔ Hex) ──
    function hexToHsl(hex) {
      let r = 0, g = 0, b = 0;
      hex = hex.replace('#', '');
      if (hex.length === 3) { r = parseInt(hex[0]+hex[0],16); g = parseInt(hex[1]+hex[1],16); b = parseInt(hex[2]+hex[2],16); }
      else { r = parseInt(hex.substring(0,2),16); g = parseInt(hex.substring(2,4),16); b = parseInt(hex.substring(4,6),16); }
      r /= 255; g /= 255; b /= 255;
      const max = Math.max(r,g,b), min = Math.min(r,g,b);
      let h = 0, s = 0, l = (max + min) / 2;
      if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
          case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
          case g: h = ((b - r) / d + 2) / 6; break;
          case b: h = ((r - g) / d + 4) / 6; break;
        }
      }
      return { h: h * 360, s: s * 100, l: l * 100 };
    }
    function hslToHex(h, s, l) {
      s /= 100; l /= 100;
      const a = s * Math.min(l, 1 - l);
      const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
      };
      return '#' + f(0) + f(8) + f(4);
    }

    // ── Color section ──
    b.appendChild(el('label', { style: { display: 'block', fontSize: '12px', color: 'var(--text-muted, #666)', marginBottom: '6px', fontWeight: 600 } }, 'Color'));

    const hsl = hexToHsl(godColor);
    const huePercent = (hsl.h / 360 * 100).toFixed(1);

    // Spectrum bar (hue)
    const spectrumBar = el('div', { style: { width: '100%', height: '24px', borderRadius: '6px', cursor: 'pointer', marginBottom: '6px', position: 'relative',
      background: 'linear-gradient(to right, #ff0000 0%, #ffff00 17%, #00ff00 33%, #00ffff 50%, #0000ff 67%, #ff00ff 83%, #ff0000 100%)' },
      onClick: function(e) {
        const rect = this.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const hue = x * 360;
        const newHsl = hexToHsl(godColor);
        godColor = hslToHex(hue, newHsl.s, newHsl.l);
        render();
      }
    });
    // Hue indicator dot
    spectrumBar.innerHTML = `<div style="position:absolute;left:${huePercent}%;top:-2px;width:10px;height:28px;background:white;border:2px solid var(--bg-primary);border-radius:3px;transform:translateX(-50%);box-shadow:0 0 4px rgba(0,0,0,0.5);pointer-events:none"></div>`;
    b.appendChild(spectrumBar);

    // Saturation / Brightness pad
    const padW = 160, padH = 100;
    const padContainer = el('div', { style: { display: 'flex', gap: '10px', alignItems: 'flex-start', marginBottom: '6px' } });
    const satBriPad = el('div', { style: { width: padW + 'px', height: padH + 'px', borderRadius: '6px', cursor: 'crosshair', flexShrink: 0, position: 'relative',
      background: `linear-gradient(to bottom, transparent, #000), linear-gradient(to right, #fff, transparent), hsl(${hsl.h}, 100%, 50%)` },
      onClick: function(e) {
        const rect = this.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
        const sat = x * 100;
        const bri = (1 - y) * 100;
        godColor = hslToHex(hsl.h, sat, bri);
        render();
      }
    });
    // Cursor dot on pad
    const satPct = hsl.s;
    const briPct = hsl.l;
    satBriPad.innerHTML = `<div style="position:absolute;left:${satPct}%;top:${(100-briPct).toFixed(1)}%;width:10px;height:10px;background:transparent;border:2px solid white;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 3px rgba(0,0,0,0.7);pointer-events:none"></div>`;
    padContainer.appendChild(satBriPad);

    // Color preview + actions
    const previewCol = el('div', { style: { display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' } });
    const colorPreview = el('div', { style: { width: '48px', height: '48px', borderRadius: '8px', border: '2px solid var(--border, #3B4A50)', background: godColor } });
    previewCol.appendChild(colorPreview);
    // Native picker link
    const nativeLink = el('label', { style: { display: 'inline-flex', alignItems: 'center', gap: '2px', fontSize: '11px', color: 'var(--text-muted, #666)', cursor: 'pointer', textDecoration: 'underline' } },
      '🎨 More',
      el('input', { type: 'color', value: godColor, style: { display: 'none' },
        onInput: e => { godColor = e.target.value; render(); }
      })
    );
    previewCol.appendChild(nativeLink);
    padContainer.appendChild(previewCol);
    b.appendChild(padContainer);

    // Hex readout (small)
    b.appendChild(el('div', { style: { fontSize: '11px', color: 'var(--text-muted, #666)', marginBottom: '6px', fontFamily: 'monospace' } }, godColor.toUpperCase()));

    // Color swatches
    const swatchRow = el('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '4px' } });
    const MORE_SWATCHES = [
      '#7c6fe0','#5B4FCF','#748FFC','#3B82F6','#60A5FA',
      '#86C08B','#34D399','#10B981','#059669',
      '#F6BD60','#F59E0B','#D97706',
      '#F87171','#EF4444','#DC2626','#FF6B6B',
      '#4ECDC4','#06B6D4','#0EA5E9','#45B7D1',
      '#96CEB4','#84CC16','#A3E635',
      '#C6AC8F','#D4A574','#78716C',
      '#EAE0D5','#F5F0EB','#D6D3D1',
      '#0A0908','#1C1917','#44403C',
      '#EC4899','#D946EF','#A855F7','#8B5CF6'
    ];
    MORE_SWATCHES.forEach(c => {
      const swatch = el('button', { type: 'button', style: { width: '20px', height: '20px', borderRadius: '4px', background: c, border: godColor === c ? '2px solid white' : '1px solid var(--border, #3B4A50)', cursor: 'pointer', padding: 0, flexShrink: 0, boxShadow: godColor === c ? '0 0 6px ' + c : 'none', transition: 'transform 0.1s' },
        onClick: () => { godColor = c; render(); }
      });
      swatch.title = c;
      swatchRow.appendChild(swatch);
    });
    b.appendChild(swatchRow);
      }

      if (state === 'chatting' || state === 'review') {
        // Chat messages
        const msgList = el('div', { style: { marginBottom: '10px' } });
        messages.forEach(m => {
          const isHeph = m.role === 'hephaestus';
          const bubble = el('div', { style: { marginBottom: '8px', alignSelf: isHeph ? 'flex-start' : 'flex-end', maxWidth: '85%', marginLeft: isHeph ? '0' : 'auto', marginRight: isHeph ? 'auto' : '0', background: isHeph ? 'var(--bg-secondary, #11100E)' : 'var(--accent, #7c6fe0)', color: isHeph ? 'var(--text-primary, #EAE0D5)' : 'white', borderRadius: '10px', padding: '10px 14px', fontSize: '13px', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word' } });
          bubble.textContent = m.content;
          msgList.appendChild(bubble);
        });
        b.appendChild(msgList);

        // Review state: show soul draft + accept button
        if (state === 'review' && soulDraft) {
          b.appendChild(el('div', { style: { background: 'var(--bg-secondary, #11100E)', border: '1px solid var(--accent, #7c6fe0)', borderRadius: '8px', padding: '12px', marginBottom: '8px', maxHeight: '200px', overflow: 'auto' } },
            el('div', { style: { fontSize: '11px', color: 'var(--accent, #7c6fe0)', fontWeight: 600, marginBottom: '4px' } }, 'SOUL.md Draft'),
            el('pre', { style: { margin: 0, fontSize: '11px', color: 'var(--text-secondary, #C6AC8F)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace' } }, soulDraft)
          ));
          // Accept button in body (scrollable area) so it never gets clipped
          const acceptBodyBtn = el('button', { style: { background: 'var(--success, #86C08B)', color: '#0A0908', border: 'none', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1, marginBottom: '8px', display: 'block', width: '100%' },
            onClick: acceptForge
          }, '⚒️ Accept & Forge');
          acceptBodyBtn.disabled = busy;
          b.appendChild(acceptBodyBtn);
        }

        // Chat input
        const inputRow = el('div', { style: { display: 'flex', gap: '8px' } });
        const input = el('input', { type: 'text', placeholder: state === 'review' ? 'Say "accept" to forge, or ask for changes...' : 'Type your response...', style: { flex: 1, background: 'var(--bg-secondary, #11100E)', border: '1px solid var(--border, #3B4A50)', borderRadius: '8px', padding: '10px 14px', color: 'var(--text-primary, #EAE0D5)', fontSize: '13px', outline: 'none' },
          onKeyDown: e => { if (e.key === 'Enter' && input.value.trim() && !busy) sendMessage(input.value.trim(), input); }
        });
        const sendBtn = el('button', { style: { background: 'var(--accent, #7c6fe0)', color: 'white', border: 'none', borderRadius: '8px', padding: '10px 16px', fontSize: '13px', fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1, whiteSpace: 'nowrap' },
          onClick: () => { if (input.value.trim() && !busy) sendMessage(input.value.trim(), input); }
        }, busy ? '...' : 'Send');
        sendBtn.disabled = busy;
        inputRow.appendChild(input);
        inputRow.appendChild(sendBtn);
        b.appendChild(inputRow);
        // Focus input after render
        setTimeout(() => input.focus(), 50);
      }

      if (state === 'forging') {
        b.appendChild(el('div', { style: { textAlign: 'center', padding: '40px' } },
          el('div', { style: { fontSize: '32px', marginBottom: '12px' } }, '⚒️'),
          el('p', { style: { color: 'var(--text-primary, #EAE0D5)', fontSize: '15px', fontWeight: 600 } }, 'Forging...'),
          el('p', { style: { color: 'var(--text-muted, #666)', fontSize: '13px' } }, `Creating ${godName} via Hephaestus`)
        ));
      }

      if (state === 'done') {
        b.appendChild(el('div', { style: { textAlign: 'center', padding: '40px' } },
          el('div', { style: { fontSize: '40px', marginBottom: '12px' } }, '✅'),
          el('p', { style: { color: 'var(--success, #86C08B)', fontSize: '16px', fontWeight: 600, marginBottom: '8px' } }, `${godName} has been forged!`),
          el('p', { style: { color: 'var(--text-secondary, #C6AC8F)', fontSize: '13px', marginBottom: '16px' } }, 'Refresh the page to see your new god in the God Rail.'),
          el('button', { style: { background: 'var(--accent, #7c6fe0)', color: 'white', border: 'none', borderRadius: '8px', padding: '10px 24px', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }, onClick: () => { close(); window.location.reload(); } }, 'View in Pantheon')
        ));
      }

      if (state === 'error') {
        b.appendChild(el('div', { style: { textAlign: 'center', padding: '40px' } },
          el('div', { style: { fontSize: '32px', marginBottom: '8px' } }, '⚠️'),
          el('p', { style: { color: 'var(--error, #F87171)', fontSize: '14px', fontWeight: 600 } }, 'Forge failed'),
          el('p', { style: { color: 'var(--text-muted, #666)', fontSize: '13px' } }, 'Check that the server is running and try again.'),
          el('button', { style: { marginTop: '16px', background: 'var(--bg-secondary, #11100E)', color: 'var(--text-secondary, #C6AC8F)', border: '1px solid var(--border, #3B4A50)', borderRadius: '8px', padding: '10px 20px', fontSize: '14px', cursor: 'pointer' }, onClick: () => { state = 'name'; render(); } }, 'Try Again')
        ));
      }

      return b;
    }

    function footer() {
      const f = el('div', { style: { display: 'flex', gap: '10px', justifyContent: 'flex-end', padding: '12px 20px', borderTop: '1px solid var(--border, #3B4A50)', minHeight: '20px' } });

      if (state === 'name') {
        const beginBtn = el('button', { id: 'fw-begin-btn', style: { background: 'var(--accent, #7c6fe0)', color: 'white', border: 'none', borderRadius: '8px', padding: '10px 24px', fontSize: '14px', fontWeight: 600, cursor: godName ? 'pointer' : 'not-allowed', opacity: godName ? 1 : 0.5 }, onClick: startForge }, 'Begin Forge →');
        beginBtn.disabled = !godName;
        f.appendChild(beginBtn);
      }

      if (state === 'review') {
        // Accept button is now inside body (scrollable area) — not in footer
      }

      return f;
    }

    async function apiCall(body) {
      const r = await fetch(`/api/gods/${encodeURIComponent(godName)}/forge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    }

    function extractSoulDraft(text) {
      const match = text.match(/```markdown\s*\n([\s\S]*?)```/) || text.match(/```\s*\n([\s\S]*?)```/);
      return match ? match[1].trim() : '';
    }

    async function startForge() {
      if (!godName) return;
      busy = true;
      state = 'chatting';
      render();
      try {
        const data = await apiCall({ action: 'start', domain: godDomain });
        const reply = data.reply || data.message || data.greeting || 'Hello! Let me help you forge this god.';
        messages.push({ role: 'hephaestus', content: reply });
        const draft = extractSoulDraft(reply);
        if (draft) { soulDraft = draft; state = 'review'; }
        busy = false;
        render();
      } catch (e) {
        messages.push({ role: 'hephaestus', content: '⚠️ Could not start the forge. Is the server running?' });
        state = 'error';
        busy = false;
        render();
      }
    }

    function updateForgeBtn() {
      var btn = document.getElementById('fw-begin-btn');
      if (btn) {
        btn.disabled = !godName;
        btn.style.opacity = godName ? '1' : '0.5';
        btn.style.cursor = godName ? 'pointer' : 'not-allowed';
      }
    }

    async function sendMessage(text, inputEl) {
      messages.push({ role: 'user', content: text });
      busy = true;
      render();
      try {
        const data = await apiCall({ action: 'chat', message: text, domain: godDomain });
        const reply = data.reply || data.message || '(no response)';
        messages.push({ role: 'hephaestus', content: reply });
        // Check for SOUL.md draft
        const draft = extractSoulDraft(reply);
        if (draft) {
          soulDraft = draft;
          state = 'review';
        }
        busy = false;
        render();
        if (inputEl) inputEl.value = '';
      } catch (e) {
        messages.push({ role: 'hephaestus', content: '⚠️ Error communicating with Hephaestus.' });
        busy = false;
        render();
      }
    }

    async function acceptForge() {
      if (!soulDraft) return;
      busy = true;
      state = 'forging';
      render();
      try {
        const data = await apiCall({ action: 'accept', soul_draft: soulDraft, domain: godDomain, icon: godIcon, color: godColor, display_name: godDisplayName || godName });
        if (!data.ok && !data.success) { state = 'error'; render(); busy = false; return; }
        // Upload icon image if one was selected
        if (godIconImage) {
          try {
            const iconResp = await fetch('/api/gods/' + encodeURIComponent(godName) + '/icon', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ image: godIconImage })
            });
            if (iconResp.ok) {
              const iconData = await iconResp.json();
              // Persist icon URL in metadata
              if (iconData && iconData.url) {
                await fetch('/api/gods/' + encodeURIComponent(godName) + '/metadata', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ icon: iconData.url })
                });
              }
            }
          } catch (e) { /* icon upload failed but forge succeeded — non-fatal */ }
        }
        state = 'done';
        render();
      } catch (e) { state = 'error'; render(); }
      busy = false;
    }

    function close() { root.remove(); }
    root.addEventListener('click', e => { if (e.target === root) close(); });

    render();
    container.appendChild(root);
  }

  window.mountForgeWizard = function(container) {
    new ForgeWizard(container || document.body);
  };

  window.openForgeWizard = function() {
    var existing = document.getElementById('forge-wizard-overlay');
    if (existing) { existing.remove(); return; }
    window.mountForgeWizard(document.body);
  };
})();
