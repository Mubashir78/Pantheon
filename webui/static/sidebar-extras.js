/* ── Pantheon Sidebar Extras ──
 * Injects Athenaeum as a visible sidebar item.
 * Boons and Ideas live in the header toolbar.
 * Uses polling instead of MutationObserver to avoid React reconciliation conflicts.
 */
(function() {
  'use strict';

  var ATTR = 'data-pantheon-extra';

  function createAthenaeumButton() {
    var athBtn = document.createElement('div');
    athBtn.className = 'nav-item pantheon-extra pantheon-athenaeum-btn';
    athBtn.setAttribute(ATTR, 'athenaeum');
    athBtn.innerHTML = '<span class="nav-item-icon" style="color:#a589c5">📚</span><span class="nav-item-label">Athenaeum</span>';
    athBtn.onclick = function() {
      if (window.openAthenaeumPanel) window.openAthenaeumPanel();
    };
    athBtn.title = 'Knowledge graph search';
    return athBtn;
  }

  function hasAthenaeumButton(root) {
    root = root || document;
    return !!root.querySelector('[' + ATTR + '="athenaeum"]');
  }

  function injectVisibleAthenaeum() {
    if (hasAthenaeumButton(document)) return true;

    var expander = document.querySelector('.nav-expander');
    if (expander && expander.parentNode) {
      expander.parentNode.insertBefore(createAthenaeumButton(), expander);
      return true;
    }

    // Fallback for older/expanded-only shells.
    var navExtra = document.querySelector('.nav-extra');
    if (navExtra && !hasAthenaeumButton(navExtra)) {
      navExtra.appendChild(createAthenaeumButton());
      return true;
    }

    return false;
  }

  // Poll for React sidebar render/re-render. Reset is implicit: if React removes
  // our injected node, querySelector stops finding it and the next tick re-adds.
  setInterval(injectVisibleAthenaeum, 500);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { setTimeout(injectVisibleAthenaeum, 1000); });
  } else {
    setTimeout(injectVisibleAthenaeum, 1000);
  }
})();
