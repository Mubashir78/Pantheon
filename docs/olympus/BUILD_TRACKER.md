     1|# Olympus UI — Build Tracker
     2|
     3|> Systematic build tracker with QA gates. All architectural decisions resolved.
     4|> Updated: 2026-05-27 — Merged from QUESTIONS.md. All 25 questions answered.
     5|> Builder: Hephaestus
     6|
     7|## Legend
     8|- 🔲 Not started
     9|- 🔄 In progress
    10|- ✅ Verified working
    11|- ❌ Failed / needs fix
    12|- ➖ Skipped / deferred
    13|- 🚦 QA Gate — must pass before proceeding
    14|
    15|---
    16|
    17|## Resolved Architecture Decisions
    18|
    19|### Backend: Olympus Backend Service
    20|A new lightweight backend service runs alongside Hermes Agent. Stack: Python + FastAPI (keep simple; future standalone mobile app will prompt refactor). It serves:
    21|- `POST /api/auth/login`, `POST /api/auth/logout`
    22|- `GET/POST/PATCH/DELETE /api/users`
    23|- `GET/PUT /api/feature-flags`
    24|- `GET/PUT /api/theme`
    25|- `GET /api/athenaeum/walk`, `GET /api/athenaeum/read`, `GET /api/athenaeum/search`
    26|- `GET /api/stream/entities`, `GET /api/stream/edges`, `GET /api/stream/metrics`
    27|
    28|### Admin vs Settings
    29|- **Settings** (gear ⚙): Profile, Appearance/Theme, Notifications, Integrations, Language, User Cron
    30|- **Admin** (shield 🛡): Gods, Users & Roles, Feature Flags, System Cron, Health, Logs, Plugins, Skills, MCP, Terminal, Export
    31|
    32|### Feature Toggles (11 total)
    33|Cron, Plugins, Skills, MCP, Kanban, Webhooks, Terminal, Summon God, Edit God, Forge God, Multi-user mode.
    34|OFF = hidden from UI, route blocked. Backend still exists.
    35|
    36|### Theme System
    37|- Runtime loading from Olympus backend (`GET /api/theme`)
    38|- YAML format at `~/pantheon/config/olympus-theme.yaml`
    39|- Terminology map included under `terminology:` block
    40|
    41|### Auth
    42|- localStorage tokens (upgrade to httpOnly cookies later)
    43|- Single-user default, multi-user toggleable
    44|- On multi-user ON: existing data auto-scoped to owner
    45|- Login UX: grid of user icons → password prompt
    46|
    47|### Route Tree
    48|```
    49|__root.tsx                          (checks onboarding_completed flag)
    50|├── index.lazy.tsx                  / (chat)
    51|├── login.lazy.tsx                  /login
    52|├── settings.lazy.tsx               /settings (overlay from rail)
    53|├── stream.lazy.tsx                 /stream
    54|└── onboarding/
    55|    ├── welcome.lazy.tsx
    56|    ├── runtime-choice.lazy.tsx
    57|    ├── custom/
    58|    │   ├── inference.lazy.tsx
    59|    │   ├── integrations.lazy.tsx
    60|    │   ├── voice.lazy.tsx
    61|    │   └── search.lazy.tsx
    62|    └── complete.lazy.tsx
    63|```
    64|
    65|### Zustand Stores (6 total)
    66|`auth-store` (extend), `onboarding-store`, `feature-flag-store`, `stream-store`, `user-store`, `search-store`
    67|
    68|### Session Management
    69|Mirror :8787 pattern — always-visible icon overlays: ☆ pin, ▾ context, ✏ rename, × delete
    70|
    71|### QA Requirements (all new components)
    72|- Matching `*.test.tsx` with render + interaction tests
    73|- Mobile viewport check (≤768px)
    74|- Basic keyboard nav (Tab/Enter/Escape)
    75|
    76|---
    77|
    78|## Pre-Build Investigations
    79|
    80|| # | Task | Status | Depends on |
    81||---|------|--------|------------|
    82|| I1 | Audit Hermes Agent plugin hooks — does `on_pre_write` exist for wiki ops? | 🔲 | Nothing |
    83|| I2 | Research Composio API — client IDs, deep-link URLs, callback pattern | ✅ | Nothing → See composio-setup.md |
    84|
    85|**Rule:** I1 must complete before Stream B starts. I2 must complete before T14 starts.
    86|
    87|---
    88|
    89|## Tier 0 — Foundation Verification (Pre-Flight)
    90|
    91|| # | Step | Status | Verified | Notes |
    92||---|------|--------|----------|-------|
    93|| 0.1 | TypeScript compiles clean (`npx tsc --noEmit`) | ✅ | 2026-05-26 | Exit 0, no errors |
    94|| 0.2 | Vite build succeeds | ✅ | 2026-05-26 | 2,101 modules, 1.43s |
    95|| 0.3 | Dev server starts on :5173 | ✅ | 2026-05-26 | Proxy /api/* → :8787 working |
    96|| 0.4 | Test suite passes | ✅ | 2026-05-27 | 16/16 files, 145/145 tests — zero failures |
    97|| 0.5 | Hermes gateway :8787 reachable | ✅ | 2026-05-26 | Status: ok |
    98|
    99|### 🚦 QA Gate 0
   100|```
   101|- [ ] npx tsc --noEmit → exit 0
   102|- [ ] npx vitest run → ≤9 failures (baseline)
   103|- [ ] Dev server loads without console errors
   104|- [ ] git status clean on master
   105|```
   106|
   107|---
   108|
   109|## Tier 0.5 — Cleanup
   110|
   111|### T0.5 — Delete Dead Code
   112|
   113|| Field | Value |
   114||-------|-------|
   115|| **Status** | ✅ |
   116|| **Commit** | `23b49a9` |
   117|| **Files** | Delete: `SidebarRail.tsx`, `SidebarRail.test.tsx` |
   118|
   119|**What:** Remove old standalone rail component. Sidebar.tsx is canonical.
   120|
   121|**🚦 QA Gate T0.5:**
   122|```
   123|- [ ] SidebarRail.tsx deleted
   124|- [ ] SidebarRail.test.tsx deleted
   125|- [ ] npx tsc --noEmit → exit 0 (no broken imports)
   126|- [ ] npx vitest run → ≤9 failures
   127|- [ ] Dev server loads, rail works normally
   128|- [ ] Commit: "chore: remove dead SidebarRail.tsx"
   129|```
   130|
   131|---
   132|
   133|## Stream A: Olympus Gaps + Auth
   134|
   135|> Olympus backend service + frontend components
   136|> Can start after T0.5 (no other dependencies)
   137|
   138|### T1 — Admin/Settings Split + Feature Toggles
   139|
   140|| Field | Value |
   141||-------|-------|
   142|| **Status** | ✅ |
   143|| **Commit** | `8d50ea2` |
   144|| **Depends on** | T0.5 |
   145|| **Files** | `app-store.ts`, `SettingsRoot.tsx`, `AdminPanel.tsx`, `Sidebar.tsx`, `feature-flag-store.ts`, Olympus backend: `/api/feature-flags` |
   146|
   147|**What it builds:**
   148|- Split Settings overlay into two distinct surfaces
   149|- Settings tabs: Profile, Appearance/Theme, Notifications, Integrations, Language, User Cron
   150|- Admin tabs: Gods, Users & Roles, Feature Flags, System Cron, Health, Logs, Plugins, Skills, MCP, Terminal, Export
   151|- Feature toggle system: 11 toggles persisted via Olympus backend `GET/PUT /api/feature-flags`
   152|- Feature flag store: `isEnabled('skills')` gating helper
   153|
   154|**🚦 QA Gate T1:**
   155|```
   156|COMPONENT TESTS:
   157|- [ ] SettingsRoot.test.tsx → PASS (user tabs only)
   158|- [ ] AdminPanel.test.tsx → PASS (operator tabs)
   159|- [ ] Sidebar.test.tsx → PASS (both buttons work)
   160|- [ ] New: feature-flag-store.test.ts → PASS
   161|- [ ] Every new component has matching *.test.tsx
   162|- [ ] npx vitest run → ≤9 failures
   163|
   164|BROWSER VERIFICATION:
   165|- [ ] Settings gear → opens with user-facing tabs only
   166|- [ ] Admin shield → opens with operator tabs
   167|- [ ] Toggle Cron OFF → Cron tabs disappear from both Settings and Admin
   168|- [ ] Toggle Skills OFF → Skills tab disappears from Admin
   169|- [ ] Toggle MCP OFF → MCP tab disappears from Admin
   170|- [ ] Toggle Plugins OFF → Plugins tab disappears from Admin
   171|- [ ] All toggles survive page refresh
   172|- [ ] All toggles survive dev server restart
   173|- [ ] Mobile viewport (≤768px): tabs scrollable, buttons tappable
   174|- [ ] Keyboard: Tab through tabs, Enter to activate
   175|- [ ] Zero console errors
   176|- [ ] git branch --show-current verified
   177|
   178|GIT:
   179|- [ ] Commit: "feat(admin): split Settings/Admin + feature toggle system"
   180|```
   181|
   182|---
   183|
   184|### T2 — Athenaeum Browser
   185|
   186|| Field | Value |
   187||-------|-------|
   188|| **Status** | ✅ |
   189|| **Commit** | `b22d550` |
   190|| **Depends on** | T1 |
   191|| **Files** | `Sidebar.tsx`, `BoonPanel.tsx`, `AdminPanel.tsx`, new: `AthenaeumBrowser.tsx`, `use-athenaeum.ts`. Olympus backend: `/api/athenaeum/*` |
   192|
   193|**What it builds:**
   194|- Rename every "Library" → "Athenaeum" across all components, tests, stores
   195|- Rename "Trove Library" → "Athenaeum" in BoonPanel, AdminPanel
   196|- Build Athenaeum browser: file explorer tree + viewer pop-up
   197|- Integrate existing file tree viewer (HTML/JSON/Python — research during build)
   198|- Olympus backend wraps Pantheon MCP athenaeum operations as HTTP endpoints
   199|- Rail icon + expanded drawer nav item wired with onClick
   200|
   201|**🚦 QA Gate T2:**
   202|```
   203|COMPONENT TESTS:
   204|- [ ] Sidebar.test.tsx → PASS
   205|- [ ] AthenaeumBrowser.test.tsx → PASS (new)
   206|- [ ] grep -r "Library" src/ → only lucide-react imports remain
   207|- [ ] npx vitest run → ≤9 failures
   208|
   209|BROWSER VERIFICATION:
   210|- [ ] Rail icon tooltip shows "Athenaeum" not "Library"
   211|- [ ] Expanded drawer nav shows "Athenaeum"
   212|- [ ] Click rail icon → Athenaeum browser opens
   213|- [ ] File tree loads from /api/athenaeum/walk
   214|- [ ] Click file → viewer pop-up shows content with line numbers
   215|- [ ] Search within Athenaeum filters results
   216|- [ ] BoonPanel header shows "Athenaeum"
   217|- [ ] Mobile: tree navigable, files tappable
   218|- [ ] Keyboard: Escape closes viewer
   219|- [ ] Zero console errors
   220|
   221|GIT:
   222|- [ ] Commit: "feat(athenaeum): rename Library→Athenaeum + file browser"
   223|```
   224|
   225|---
   226|
   227|### T3 — Unified Search
   228|
   229|| Field | Value |
   230||-------|-------|
   231|| **Status** | ✅ |
   232|| **Commit** | `6fe1b8a` |
   233|| **Depends on** | T2 (shares athenaeum data) |
   234|| **Files** | New: `SearchPanel.tsx`, `use-search.ts`, `search-store.ts`. Modify: `Sidebar.tsx` |
   235|
   236|**What it builds:**
   237|- Search panel triggered from rail icon + Cmd/Ctrl+K
   238|- Client-side aggregation: parallel fetches to `/api/sessions`, `/api/athenaeum/search`, `/api/gods`, `/api/mcp/tools`
   239|- Source toggle pills: ● Sessions, ● Athenaeum, ○ Gods, ○ Tools
   240|- Results grouped by source, ranked by relevance
   241|- Remove "coming soon" from rail icon
   242|
   243|**🚦 QA Gate T3:**
   244|```
   245|COMPONENT TESTS:
   246|- [ ] SearchPanel.test.tsx → PASS (new)
   247|- [ ] search-store.test.ts → PASS (new)
   248|- [ ] use-search.test.ts → PASS (new)
   249|- [ ] Sidebar.test.tsx → PASS
   250|- [ ] npx vitest run → ≤9 failures
   251|
   252|BROWSER VERIFICATION:
   253|- [ ] Rail Search icon clickable — opens search panel
   254|- [ ] Cmd/Ctrl+K from anywhere opens search
   255|- [ ] Type query → results grouped by source
   256|- [ ] Toggle Gods OFF → god results disappear instantly
   257|- [ ] Toggle Tools OFF → tool results disappear
   258|- [ ] Click session result → navigates to that session
   259|- [ ] Click athenaeum result → opens file viewer
   260|- [ ] Click god result → switches active god
   261|- [ ] Empty state: "No results for [query]"
   262|- [ ] Escape closes panel
   263|- [ ] Click outside closes panel
   264|- [ ] Mobile: panel full-width, toggles tappable
   265|- [ ] Keyboard: Tab between results, Enter to select
   266|- [ ] Zero console errors
   267|
   268|GIT:
   269|- [ ] Commit: "feat(search): unified search with source toggle pills"
   270|```
   271|
   272|---
   273|
   274|### T4 — Local Auth (Owner-First)
   275|
   276|| Field | Value |
   277||-------|-------|
   278|| **Status** | ✅ |
   279|| **Commit** | `ce3a539` |
   280|| **Depends on** | T1 (admin panel exists) |
   281|| **Files** | `auth-store.ts` (extend), `use-auth.ts`, `LoginPage.tsx`, `router.tsx`, `__root.tsx`, Olympus backend: `/api/auth/login`, `/api/auth/logout`, `/api/olympus/auth/me` |
   282|
   283|**What it builds:**
   284|- Olympus backend: simple credential check, token generation
   285|- Login UX: blank screen, grid of user icons, click → password prompt → authenticate
   286|- localStorage token persistence
   287|- `Authorization: Bearer <token>` on all API calls
   288|- Auth context wraps AppShell, unauthenticated → redirect to /login
   289|- Owner = first user created at install, always has full access
   290|- Multi-user mode OFF by default (login page hidden, auto-login as owner)
   291|
   292|**🚦 QA Gate T4:**
   293|```
   294|COMPONENT TESTS:
   295|- [ ] LoginPage.test.tsx → PASS (new)
   296|- [ ] auth-store.test.ts → PASS
   297|- [ ] Login: username+password fields render
   298|- [ ] Sign In disabled until both fields filled
   299|- [ ] Invalid credentials → error message
   300|- [ ] Valid credentials → redirect to /
   301|- [ ] npx vitest run → ≤9 failures
   302|
   303|BROWSER VERIFICATION:
   304|- [ ] Cold load with multi-user OFF → straight to chat (no login)
   305|- [ ] Multi-user ON → redirected to /login
   306|- [ ] User grid visible with icons
   307|- [ ] Click user → password prompt appears
   308|- [ ] Enter correct password → lands on chat
   309|- [ ] Profile button shows user info (not hardcoded "Y")
   310|- [ ] Close tab, reopen → still authenticated (token persists)
   311|- [ ] Logout → redirected to /login
   312|- [ ] Mobile: grid scrollable, password input visible
   313|- [ ] Keyboard: Tab between users, Enter to select
   314|- [ ] Zero console errors on login/logout
   315|- [ ] No auth secrets in devtools/frontend
   316|- [ ] git branch verified
   317|
   318|GIT:
   319|- [ ] Commit: "feat(auth): owner-first local auth with grid login"
   320|```
   321|
   322|---
   323|
   324|### T5 — User Management Panel
   325|
   326|| Field | Value |
   327||-------|-------|
   328|| **Status** | ✅ |
   329|| **Commits** | `487e5ff`, `b9e3a61` (branch `feat/user-management`) |
   330|| **Depends on** | T4, T1 |
   331|| **Files** | `UserManagementPanel.tsx` + test (23 tests), `olympus-auth.ts`, `vite.config.ts`, `AdminPanel.tsx` |
   332|
   333|**What it builds:**
   334|- "Users & Roles" tab in Admin panel
   335|- List all users: name, role, last login, status (active/disabled)
   336|- Add User modal: username, display name, initial password, role
   337|- Edit User: change role, reset password, disable/enable
   338|- Delete User: confirmation, cannot delete self (owner)
   339|- Olympus backend: user CRUD with JSON file store
   340|
   341|**🚦 QA Gate T5:**
   342|```
   343|COMPONENT TESTS:
   344|- [ ] UserManagementPanel.test.tsx → PASS (new)
   345|- [ ] user-store.test.ts → PASS (new)
   346|- [ ] Add user flow, edit user flow, delete confirmation tested
   347|- [ ] Cannot delete self tested
   348|- [ ] npx vitest run → ≤9 failures
   349|
   350|BROWSER VERIFICATION:
   351|- [ ] Admin → Users & Roles tab visible
   352|- [ ] Shows all users with correct roles
   353|- [ ] Add User → fills form → user appears in list
   354|- [ ] New user CAN log in with given credentials
   355|- [ ] Edit user → change role → applied on next login
   356|- [ ] Disable user → user cannot log in
   357|- [ ] Delete user → confirmation → removed
   358|- [ ] Try delete self → blocked with message
   359|- [ ] Mobile: forms usable, buttons tappable
   360|- [ ] Zero console errors
   361|
   362|GIT:
   363|- [ ] Commit: "feat(admin): user management with add/edit/delete/disable"
   364|```
   365|
   366|---
   367|
   368|### T6 — Role Assignment + God Permissions
   369|
   370|| Field | Value |
   371||-------|-------|
   372|| **Status** | ✅ |
   373|| **Commits** | `40636ef` (Olympus-UI), `63b82b3` (Pantheon) |
   374|| **Depends on** | T5 |
   375|| **Files** | `god-store.ts`, `GodPicker.tsx`, `UserManagementPanel.tsx`, `olympus_users.py` |
   376|
   377|**What it builds:**
   378|- Role definitions: owner, admin, user
   379|- God permission assignment per user: which gods each user can access
   380|- Owner always has access to all gods
   381|- GodPicker filters to permitted gods
   382|- Chat blocked for unauthorized god switch
   383|
   384|**🚦 QA Gate T6:**
   385|```
   386|COMPONENT TESTS:
   387|- [ ] GodPicker filters to permitted gods for non-owner
   388|- [ ] Owner sees all gods regardless of permissions
   389|- [ ] God switch blocked for unauthorized god
   390|- [ ] npx vitest run → ≤9 failures
   391|
   392|BROWSER VERIFICATION:
   393|- [ ] Admin → Users → click user → god permission checklist visible
   394|- [ ] Uncheck a god → save → user's GodPicker no longer shows that god
   395|- [ ] Owner still sees all gods
   396|- [ ] Re-check god → reappears for user
   397|- [ ] Zero console errors
   398|
   399|GIT:
   400|- [ ] Commit: "feat(auth): role-based god permissions per user"
   401|```
   402|
   403|---
   404|
   405|### T7 — Multi-User Toggle
   406|
   407|| Field | Value |
   408||-------|-------|
   409|| **Status** | ✅ |
   410|| **Commit** | `d12e416` (branch `feat/user-management`) |
   411|| **Depends on** | T5, T6 |
   412|| **Files** | `__root.tsx`, `AdminPanel.tsx`, `feature-flag-store.ts` |
   413|
   414|**What it builds:**
   415|- Toggle in Admin → Feature Flags: "Multi-User Mode"
   416|- OFF (default): login page hidden, auto-login as owner
   417|- ON: login page active, user management visible, role enforcement active
   418|- On toggle ON: all existing data auto-scoped to owner
   419|
   420|**🚦 QA Gate T7:**
   421|```
   422|BROWSER VERIFICATION:
   423|- [ ] Multi-user OFF → cold load goes straight to chat
   424|- [ ] Multi-user OFF → Users tab hidden in Admin
   425|- [ ] Toggle ON → Users tab appears
   426|- [ ] Toggle ON → logout → redirected to /login
   427|- [ ] Toggle ON → different user can log in
   428|- [ ] Toggle OFF → other users logged out, owner restored
   429|- [ ] Toggle survives server restart
   430|- [ ] All existing sessions still visible to owner after toggle ON
   431|- [ ] New user sees empty session list
   432|- [ ] Zero console errors
   433|
   434|GIT:
   435|- [ ] Commit: "feat(admin): multi-user mode toggle"
   436|```
   437|
   438|---
   439|
   440|### 🚦 Stream A Integration Gate (T1-T7)
   441|```
   442|- [ ] Admin/Settings split working with correct tabs
   443|- [ ] All 11 feature toggles functional
   444|- [ ] Athenaeum browser loads real data
   445|- [ ] Search returns results from all sources
   446|- [ ] Login/logout works end-to-end
   447|- [ ] User CRUD works
   448|- [ ] God permissions enforced
   449|- [ ] Multi-user toggle transitions cleanly
   450|- [ ] npx vitest run → ≤9 failures
   451|- [ ] Mobile: all new surfaces usable at ≤768px
   452|```
   453|
   454|---
   455|
   456|## Stream B: Integration Backend
   457|
   458|> Hermes plugins + cron jobs. Independent of Stream A.
   459|> Location: `~/.hermes/plugins/` and `~/.hermes/cron/pantheon-sync/`
   460|> **Prerequisite:** I1 (Hermes plugin hooks audit) must complete first.
   461|
   462|### I1 — Hermes Plugin Hooks Audit
   463|
   464|| Field | Value |
   465||-------|-------|
   466|| **Status** | ✅ Complete |
   467|| **Files** | Research only |
   468|
   469|**Finding:** No dedicated wiki/content write hooks exist. Strategy confirmed:
   470|
   471|- **`pre_tool_call`** — fires before any tool executes, can veto with `{"action": "block"}`. Use for WikiGuard (block low-quality content) and Dedup (block duplicates). Matcher: `athenaeum_write|write_file|patch`
   472|- **`transform_tool_result`** — fires after tool returns, can rewrite result string. Use for Provenance (inject source/provider tags into result)
   473|- 15 plugin hook types total. Key files: `hermes_cli/plugins.py:78-114` (VALID_HOOKS), `model_tools.py:688-696` (pre_tool_call dispatch at tool boundary)
   474|- T8-T10 implementation: register `pre_tool_call` handler per plugin, gate content before it reaches the write tool. No new hook types needed.
   475|
   476|---
   477|
   478|### T8 — WikiGuard Admission Gate (P0a)
   479|
   480|| Field | Value |
   481||-------|-------|
   482|| **Status** | ✅ Complete |
   483|
   484|---
   485|
   486|### 🚦 Phase 0 Integration Gate (T8+T9+T10)
   487|```
   488|- [ ] All three plugins coexist without conflicts
   489|- [ ] Test chunk → passes gate → has provenance → stored
   490|- [ ] Duplicate chunk → dedup blocks it
   491|- [ ] Junk chunk → gate drops it → logged to dropped.log
   492|```
   493|
   494|---
   495|
   496|### T11 — Sync Scheduler (P1b)
   497|
   498|| Field | Value |
   499||-------|-------|
   500|| **Status** | ✅ |
   501|| **Commit** | `0f959ef` (Pantheon repo) |
   502|| **Depends on** | Phase 0 Gate |
   503|| **Files** | `~/pantheon/cron/pantheon-sync/{sync_scheduler.py, sync_state.py, connections.json, README.md}` |
   504|
   505|**What:** 20-minute cron loop. Walk active connections, check sync state, call adapter.
   506|
   507|**🚦 QA Gate T11:**
   508|```
   509|- [ ] connections.json loads active connections
   510|- [ ] SyncState: last_sync, cursor, records_today, daily budget
   511|- [ ] Daily budget resets on date change
   512|- [ ] Skips not-yet-due connections
   513|- [ ] Skips over-budget connections
   514|- [ ] Errors logged, scheduler never crashes
   515|- [ ] Crontab: */20 * * * *
   516|- [ ] Manual run_sync_tick() works
   517|- [ ] scan.log records every tick
   518|- [ ] Commit: "feat(sync): 20-min cron scheduler"
   519|```
   520|
   521|---
   522|
   523|### T12 — Adapters: Gmail, GitHub, Slack (P1c)
   524|
   525|| Field | Value |
   526||-------|-------|
   527|| **Status** | ✅ |
   528|| **Commit** | `12ad4a7` (Pantheon repo) |
   529|| **Depends on** | Phase 0 Gate |
   530|| **Files** | `cron/pantheon-sync/adapters/{__init__,base,gmail,github,slack}.py` |
   531|
   532|**What:** Provider-specific adapters. Fetch → canonical Markdown + metadata.
   533|
   534|**🚦 QA Gate T12:**
   535|```
   536|PER ADAPTER:
   537|- [ ] get_adapter(provider) returns correct class
   538|- [ ] sync() → {"records": [...], "next_cursor": ...}
   539|- [ ] canonicalize() → {"content": "markdown...", "metadata": {...}}
   540|- [ ] Empty results handled gracefully
   541|- [ ] Auth failure logged clearly
   542|
   543|GMAIL: sender/subject/body, provider="gmail", tags=["email"]
   544|GITHUB: repo/event_type, provider="github", tags=["code"]
   545|SLACK: sender/text/timestamp, provider="slack", tags=["chat"]
   546|
   547|- [ ] Commit: "feat(adapters): Gmail, GitHub, Slack canonicalization"
   548|```
   549|
   550|---
   551|
   552|### T13 — Codex-Stream Ingest Pipeline (P1d)
   553|
   554|> **ARCHITECTURE CHANGE (2026-05-28):** Pipeline moved from `~/.hermes/cron/pantheon-sync/` to `~/athenaeum/Codex-Stream/ingest/` — it's now a self-contained Athenaeum Codex. Data lives alongside the pipeline. Raw chunks have 30-day TTL. Entities are promoted to permanent Codexes at ≥5 mentions. See Thoth handoff: `~/athenaeum/handoffs/hephaestus-handoff-2026-05-28-ingest-pipeline-move.md`
   555|
   556|| Field | Value |
   557||-------|-------|
   558|| **Status** | ✅ |
   559|| **Commit** | `TBD` (Pantheon repo: Codex-Stream/ingest/ + sync_scheduler) |
   560|| **Depends on** | T8, T9, T10, T11, T12 |
   561|| **Files** | `~/athenaeum/Codex-Stream/ingest/{__init__,pipeline,chunker,hotness,cleanup}.py`. Modified: `~/pantheon/cron/pantheon-sync/sync_scheduler.py`. |
   562|| **Note** | ✅ End-to-end verified: sync tick → chunks in raw/ → spaCy NER extracts entities → hotness updated. Co-occurrence edges logged to JSONL (Ichor graph write pending). |
   563|
   564|**What:** Sync scheduler calls `ingest_into_codex_stream(canonical, connection)` → chunk (≤3k tokens, SHA256 IDs) → WikiGuard score → dedup check → provenance inject → write to `~/athenaeum/Codex-Stream/raw/{provider}/{date}/{chunk_id}.md`. Entity extraction (spaCy NER), co-occurrence edges → Ichor graph, hotness tracking. Daily cleanup: purge raw/ >30 days, promote entities ≥5 mentions.
   565|
   566|**🚦 QA Gate T13:**
   567|```
   568|PIPELINE (pipeline.py):
   569|- [ ] ingest_into_codex_stream(canonical, connection) → IngestResult(written=N, dropped=N, skipped=N)
   570|- [ ] WikiGuard score gate called (T8) — DROP/BORDERLINE/KEEP respected
   571|- [ ] Dedup check called (T10) — duplicates skipped
   572|- [ ] Provenance injected (T9) — source/provider/connector in frontmatter
   573|- [ ] Written to ~/athenaeum/Codex-Stream/raw/{provider}/{date}/{chunk_id}.md
   574|- [ ] Handles empty/malformed adapter results gracefully (no crash)
   575|
   576|CHUNKER (chunker.py):
   577|- [ ] chunk_text() splits on paragraph boundaries, ≤3000 tokens
   578|- [ ] Chunk IDs are SHA256 content-addressed
   579|- [ ] Standalone: `python -c "from athenaeum.codex_stream.ingest.chunker import chunk_text; ..."` works
   580|
   581|HOTNESS (hotness.py):
   582|- [ ] HotnessTracker.increment(entity_name) works
   583|- [ ] trending(n) returns top-N entities by mention count
   584|- [ ] mark_promoted(entity) persists flag
   585|- [ ] JSON persistence survives restarts (~/athenaeum/Codex-Stream/hotness.json)
   586|
   587|CLEANUP (cleanup.py):
   588|- [ ] CodexStreamCleanup.run() purges raw/ files >30 days old
   589|- [ ] Empty date directories cleaned up after purge
   590|- [ ] Entities with ≥5 mentions promoted to ~/athenaeum/Codex-Stream/entities/{slug}.md
   591|- [ ] Promotion routing: default → Codex-General (configurable)
   592|- [ ] Hotness decay applied to cold entities
   593|- [ ] Cleanup never touches entities/, graph edges, or summaries
   594|- [ ] Crontab: `0 2 * * * cd ~/athenaeum/Codex-Stream && python -m ingest.cleanup`
   595|
   596|INTEGRATION:
   597|- [ ] sync_scheduler.py imports from athenaeum.codex_stream.ingest.pipeline
   598|- [ ] End-to-end: manual sync tick → chunks land in Codex-Stream/raw/
   599|- [ ] spaCy NER extracts entities (zero LLM cost)
   600|- [ ] Co-occurrence edges created in Ichor graph
   601|- [ ] Commit: "feat(ingest): Codex-Stream pipeline — chunk + score + write + cleanup"
   602|```
   603|
   604|---
   605|
   606|### 🚦 Phase 1 Integration Gate (T11+T12+T13)
   607|```
   608|- [ ] Gmail connected → sync tick → chunks in ~/athenaeum/Codex-Stream/raw/gmail/
   609|- [ ] dropped.log has entries for low-quality chunks
   610|- [ ] Entities extracted and co-occurrence edges created
   611|- [ ] Hotness counters incremented
   612|- [ ] Cleanup cron: 30-day TTL enforced, entities promoted at ≥5 mentions
   613|```
   614|
   615|---
   616|
   617|## Stream C: Integration UI + Onboarding
   618|
   619|> Olympus frontend components for the integration pipeline.
   620|> OAuth components can be built standalone (parallel with T1).
   621|
   622|### I2 — Composio API Research
   623|
   624|| Field | Value |
   625||-------|-------|
   626|| **Status** | ✅ |
   627|| **Note** | 508-line comprehensive doc at `~/pantheon/docs/olympus/composio-setup.md`. Covers: account setup, OAuth architecture, callback URLs, per-service client IDs (Gmail/GitHub/Slack), Python+TS code patterns, BYOK flow, design decisions, sequence diagram. |
   628|| **Depends on** | Nothing |
   629|| **Files** | `~/pantheon/docs/olympus/composio-setup.md` |
   630|
   631|**What:** Research Composio BYOK setup — client ID requirements, deep-link URLs for Gmail/GitHub/Slack, callback URL pattern (`localhost:53824/oauth/callback?provider=`), integration guide.
   632|
   633|**🚦 QA Gate I2:**
   634|```
   635|- [ ] Composio account creation documented
   636|- [ ] Deep-link URLs for Gmail, GitHub, Slack documented
   637|- [ ] OAuth callback URL pattern confirmed
   638|- [ ] Client ID / API key setup steps documented
   639|- [ ] Research doc written to ~/pantheon/docs/olympus/composio-setup.md
   640|```
   641|
   642|---
   643|
   644|### T14 — OAuth Flow UI (P3a)
   645|
   646|| Field | Value |
   647||-------|-------|
   648|| **Status** | ✅ |
   649|| **Commit** | `TBD` |
   650|| **Note** | All 4 states handled (idle/connecting/connected/error) + 60s timeout per spec. 70 integration tests pass. Wired into Settings ✅ (T14b). Loopback listener (port 53824) and manual token fallback deferred to T14c. |
   651|| **Depends on** | I2 |
   652|| **Files** | `src/components/settings/integrations/`, `src/components/settings/integrations/useOAuth.ts` |
   653|
   654|**What:** ConnectionManager page, ConnectionCards (Gmail, GitHub, Slack), OAuthButton with loopback listener on port 53824, manual token fallback.
   655|
   656|**🚦 QA Gate T14:**
   657|```
   658|COMPONENT TESTS:
   659|- [ ] OAuthButton.test.tsx → PASS (new)
   660|- [ ] ConnectionCard.test.tsx → PASS (new)
   661|- [ ] ConnectionManager.test.tsx → PASS (new)
   662|- [ ] useOAuth.test.ts → PASS (new)
   663|- [ ] All states: idle, connecting, connected, error
   664|- [ ] npx vitest run → ≤9 failures
   665|
   666|BROWSER VERIFICATION:
   667|- [ ] Settings → Integrations tab visible
   668|- [ ] Grid: Gmail, GitHub, Slack, Notion, Telegram
   669|- [ ] Connected provider: green dot + last sync
   670|- [ ] Not connected: "Connect" button
   671|- [ ] Click Connect → OAuth flow opens
   672|- [ ] Manual token entry fallback visible
   673|- [ ] Disconnect button with confirmation
   674|- [ ] Mobile: cards stack vertically, buttons tappable
   675|- [ ] Keyboard: Tab between cards
   676|- [ ] Zero console errors
   677|
   678|GIT:
   679|- [ ] Commit: "feat(integrations): OAuth flow UI with Composio BYOK"
   680|```
   681|
   682|---
   683|
   684|### T14b — Wire Integrations Into Settings
   685|
   686|| Field | Value |
   687||-------|-------|
   688|| **Status** | ✅ |
   689|| **Commit** | `1c90323` (Olympus-UI, branch `feat/user-management`) |
   690|| **Depends on** | T1 AND T14 |
   691|| **Files** | `SettingsRoot.tsx`, `ConnectionManager.tsx` + tests |
   692|
   693|**What:** Import ConnectionManager, place in Settings → Integrations tab. Micro-task — fires when both T1 and T14 complete.
   694|
   695|**🚦 QA Gate T14b:**
   696|```
   697|- [ ] Settings → Integrations tab shows ConnectionManager
   698|- [ ] All connection cards render correctly
   699|- [ ] Zero console errors
   700|- [ ] Commit: "feat(integrations): wire ConnectionManager into Settings"
   701|```
   702|
   703|---
   704|
   705|## Stream C: Pre-Wizard Backend
   706|
   707|> Prerequisite endpoints the onboarding wizard calls. Build these BEFORE T15 (wizard UI).
   708|
   709|### T15a — Hardware Detection Endpoint
   710|
   711|| Field | Value |
   712||-------|-------|
   713|| **Status** | ✅ |
   714|| **Depends on** | Nothing |
   715|| **Files** | `~/pantheon/webui/api/onboarding.py` (get_hardware_info), `~/pantheon/webui/api/routes.py` (route handler) |
   716|
   717|**What:** Endpoint that probes the host machine and returns model recommendations. Detects total RAM, CPU cores, and GPU availability (via `lspci` or similar). Maps to one of three tiers: 8GB, 16GB, 16GB+GPU. Returns recommended Ollama models for that tier.
   718|
   719|**Response shape:**
   720|```json
   721|{
   722|  "tier": "16gb_gpu",
   723|  "ram_gb": 32,
   724|  "cpu_cores": 16,
   725|  "gpu_detected": true,
   726|  "gpu_name": "NVIDIA RTX 3060",
   727|  "recommended_models": ["qwen2.5:14b", "deepseek-r1:14b", "gemma3:12b"],
   728|  "embedding_model": "nomic-embed-text"
   729|}
   730|```
   731|
   732|**🚦 QA Gate T15a:**
   733|```
   734|- [ ] Returns valid JSON with all fields
   735|- [ ] Correctly detects RAM via /proc/meminfo or sysctl
   736|- [ ] Detects GPU via lspci | grep -i vga
   737|- [ ] Falls back to tier "8gb" if detection fails
   738|- [ ] Embedding model always "nomic-embed-text"
   739|- [ ] Curl: curl -s http://localhost:8787/api/onboarding/hardware
   740|```
   741|
   742|---
   743|
   744|### T15b — Ollama Model Install + Download Script
   745|
   746|| Field | Value |
   747||-------|-------|
   748|| **Status** | 🔲 |
   749|| **Depends on** | T15a |
   750|| **Files** | `~/pantheon/scripts/onboarding/setup-ollama-models.sh` |
   751|
   752|**What:** Script that installs Ollama if not present, then pulls user-selected models + `nomic-embed-text`. Called by the wizard UI during Step 2 (Local path). Reports download progress. Returns JSON status.
   753|
   754|**🚦 QA Gate T15b:**
   755|```
   756|- [ ] Detects if ollama is installed; if not, runs: curl -fsSL https://ollama.com/install.sh | sh
   757|- [ ] Accepts model list as argument: setup-ollama-models.sh qwen2.5:7b llama3.1:8b
   758|- [ ] Auto-includes nomic-embed-text in every pull
   759|- [ ] Reports per-model status (pending/downloading/done/error)
   760|- [ ] Idempotent: already-pulled models return "done" immediately
   761|- [ ] Works from wizard UI: subprocess.run with progress parsing
   762|- [ ] Test: bash ~/pantheon/scripts/onboarding/setup-ollama-models.sh qwen2.5:3b
   763|```
   764|
   765|---
   766|
   767|### T15c — OpenCode Go API Verification
   768|
   769|| Field | Value |
   770||-------|-------|
   771|| **Status** | ✅ |
   772|| **Depends on** | Nothing |
   773|| **Files** | Olympus backend: `POST /api/onboarding/verify-opencode` |
   774|
   775|**What:** Endpoint that validates an OpenCode Go API key by making a test call. Returns success + model list, or error with message. Referral link embedded in response for frontend display.
   776|
   777|**Response shape:**
   778|```json
   779|{
   780|  "valid": true,
   781|  "models_available": ["deepseek-v4-flash-free", "deepseek-v4-pro", "..."],
   782|  "referral_url": "https://opencode.ai/go?ref=3QSR50S9K2",
   783|  "error": null
   784|}
   785|```
   786|
   787|**🚦 QA Gate T15c:**
   788|```
   789|- [ ] Valid key → returns valid:true + model list
   790|- [ ] Invalid key → returns valid:false + error message
   791|- [ ] Referral link always included in response
   792|- [ ] Timeout after 10s (don't hang the wizard)
   793|- [ ] Curl: curl -s -X POST http://localhost:8787/api/onboarding/verify-opencode -d '{"api_key":"sk-..."}'
   794|```
   795|
   796|---
   797|
   798|### T15d — God Registration Endpoint
   799|
   800|| Field | Value |
   801||-------|-------|
   802|| **Status** | ✅ |
   803|| **Depends on** | Nothing |
   804|| **Files** | Olympus backend: `POST /api/onboarding/register-gods` |
   805|
   806|**What:** Endpoint that registers the core gods (Hermes + Hephaestus) during onboarding. Calls `/api/gods/summon` internally for each. Returns per-god status. Hermes is the default profile so it may already exist — handle gracefully. Hephaestus needs a full summon (SOUL.md + god.json).
   807|
   808|**Response shape:**
   809|```json
   810|{
   811|  "gods": [
   812|    {"name": "hermes", "status": "already_exists"},
   813|    {"name": "hephaestus", "status": "registered", "display_name": "Hephaestus"}
   814|  ],
   815|  "all_registered": true
   816|}
   817|```
   818|
   819|**🚦 QA Gate T15d:**
   820|```
   821|- [ ] POST with no body registers both Hermes + Hephaestus
   822|- [ ] Hermes already exists → returns "already_exists" (no error)
   823|- [ ] Hephaestus summon creates full profile with SOUL.md + god.json
   824|- [ ] Gods visible in GodPicker after registration (GET /api/gods includes both)
   825|- [ ] Re-run is idempotent (both return "already_exists")
   826|- [ ] Curl: curl -s -X POST http://localhost:8787/api/onboarding/register-gods
   827|```
   828|
   829|---
   830|
   831|### T15 — Onboarding Wizard (P3b)
   832|
   833|> **DESIGN DECISION (2026-05-28):** Replaced Cloud/Custom branching with Local/BYOK. Cloud path was OpenHuman artifact — Pantheon runs locally. Personalities moved to god SOUL.md (not global config). Voice is skip-able. Search is background-configured (DDGS + Scrapeling), not a user step. Core gods (Hermes + Hephaestus) auto-registered during wizard.
   834|
   835|| Field | Value |
   836||-------|-------|
   837|| **Status** | 🔲 |
   838|| **Depends on** | T14, T4 |
   839|| **Files** | `src/routes/onboarding/` (6 route files), `src/stores/onboarding-store.ts`. Modify: `src/routes/__root.tsx`, router |
   840|
   841|**What:** First-run wizard shown to new users. 6 steps:
   842|
   843|```
   844|Step 1 — Welcome         Intro + "Get Started"
   845|Step 2 — Runtime Choice  Local (hardware detect → model picker → Ollama download)
   846|                         vs BYOK (OpenCode Go referral link + API key paste)
   847|                         Both paths auto-download nomic-embed-text
   848|Step 3 — Register Gods   Auto-register Hermes + Hephaestus (visible in GodPicker)
   849|Step 4 — Integrations    OAuth connections: Gmail, GitHub, Slack [SKIP-ABLE]
   850|Step 5 — Voice           Voice provider: faster-whisper base/small, whisper.cpp medium [SKIP-ABLE]
   851|Step 6 — Complete        "You're ready" → onboarding_completed=true → redirect to /
   852|```
   853|
   854|**Guard:** `localStorage.getItem('onboarding_completed')` checked in `__root.tsx`. Wizard never runs again once completed.
   855|
   856|**Local path models by tier:**
   857|| RAM | Models |
   858||-----|--------|
   859|| 8GB (no GPU) | `qwen2.5:3b`, `gemma3:4b`, `phi4-mini:3.8b` |
   860|| 16GB (no GPU) | `qwen2.5:7b`, `mistral:7b`, `llama3.1:8b` |
   861|| 16GB+ (GPU) | `qwen2.5:14b`, `deepseek-r1:14b`, `gemma3:12b` |
   862|
   863|**Base config shipped:** Auto-compact on, guardrails, checkpoints, ichor memory, terminal local, browser auto. Personalities stripped (lives in SOUL.md). Critical cron jobs pre-configured: ichor-daily-maintenance, hades, pantheon-sync, Codex-Stream cleanup.
   864|
   865|**🚦 QA Gate T15:**
   866|```
   867|COMPONENT TESTS:
   868|- [ ] All 6 step components have *.test.tsx
   869|- [ ] onboarding-store.test.ts → PASS
   870|- [ ] Local path: hardware detect → model selection → download trigger
   871|- [ ] BYOK path: referral link → API key input → validation
   872|- [ ] Skip buttons work on integrations and voice steps
   873|- [ ] completeAndExit() persists onboarding_completed flag
   874|- [ ] npx vitest run → 0 failures
   875|
   876|BROWSER VERIFICATION:
   877|- [ ] First visit → redirected to /onboarding/welcome
   878|- [ ] Welcome: intro content + "Get Started" button
   879|- [ ] Runtime Choice: Local card vs BYOK card with referral link
   880|- [ ] Local: model tier shown based on detected hardware
   881|- [ ] BYOK: OpenCode Go link opens in new tab, API key field validates
   882|- [ ] Gods step: auto-registers Hermes + Hephaestus (visible in GodPicker after)
   883|- [ ] Integrations: OAuth cards render, Skip button works
   884|- [ ] Voice: model picker renders, Skip button works
   885|- [ ] Complete → redirected to / (chat), onboarding never shown again
   886|- [ ] Reload page → no redirect (onboarding_completed=true)
   887|- [ ] Mobile: steps full-width, buttons tappable (44px min)
   888|- [ ] Keyboard: Tab through options, Enter to select, Escape for skip
   889|- [ ] Zero console errors
   890|- [ ] git branch verified before browser QA
   891|
   892|GIT:
   893|- [ ] Commit: "feat(onboarding): 6-step first-run wizard — Local/BYOK + gods + integrations + voice"
   894|```
   895|
   896|---
   897|
   898|### T16 — Context Gathering Pipeline (P3c)
   899|
   900|| Field | Value |
   901||-------|-------|
   902|| **Status** | 🔲 |
   903|| **Depends on** | T12, T13, T15 |
   904|| **Files** | `ContextGatheringStep.tsx` |
   905|
   906|**What:** Background pipeline after first OAuth: search Gmail for LinkedIn → build user profile. "Still working" UI after 30s. Core alive probe. Error state with retry.
   907|
   908|**🚦 QA Gate T16:**
   909|```
   910|BROWSER VERIFICATION:
   911|- [ ] After OAuth connect in wizard → ContextGatheringStep appears
   912|- [ ] Pipeline stages visible (Gmail search → profile build)
   913|- [ ] Core alive indicator (green dot)
   914|- [ ] After 30s → "Still working" UI swaps in
   915|- [ ] "Continue to Chat" button always visible
   916|- [ ] Completion → auto-advances after 800ms
   917|- [ ] No Gmail connected → stages skipped gracefully
   918|- [ ] Error state → retry/continue options
   919|- [ ] Profile written to ~/wiki/entities/{username}-profile.md
   920|- [ ] Mobile: status readable, buttons tappable
   921|
   922|GIT:
   923|- [ ] Commit: "feat(onboarding): background context gathering pipeline"
   924|```
   925|
   926|---
   927|
   928|### T17 — Stream Dashboard (P3d)
   929|
   930|| Field | Value |
   931||-------|-------|
   932|| **Status** | 🔲 |
   933|| **Depends on** | T13, T1 |
   934|| **Files** | `src/components/stream/` (KnowledgeGraph, EntityDetailPanel, MemoryMetricsCard, StreamSearchBar), `stream-store.ts`. Olympus backend: `/api/stream/*` |
   935|
   936|**What:** Obsidian-style D3 force-directed knowledge graph as modal overlay. Nodes = entities, edges = co-occurrence, size = hotness. Entity detail panel. Metrics bar.
   937|
   938|**🚦 QA Gate T17:**
   939|```
   940|COMPONENT TESTS:
   941|- [ ] KnowledgeGraph.test.tsx → PASS (new)
   942|- [ ] EntityDetailPanel.test.tsx → PASS (new)
   943|- [ ] MemoryMetricsCard.test.tsx → PASS (new)
   944|- [ ] stream-store.test.ts → PASS (new)
   945|- [ ] D3 renders SVG with nodes+edges
   946|- [ ] Node sizes proportional to hotness
   947|- [ ] Node colors by category
   948|- [ ] npx vitest run → ≤9 failures
   949|
   950|BROWSER VERIFICATION:
   951|- [ ] Stream tab visible in navigation
   952|- [ ] Metrics bar: Storage, Sources, Chunks, Entities, Connections, 🔥 Trending
   953|- [ ] "🗺️ Graph" button visible
   954|- [ ] Click → full-screen modal with D3 force graph
   955|- [ ] Nodes sized by hotness, colored by category
   956|- [ ] Drag node → physics re-layout
   957|- [ ] Scroll to zoom, drag to pan
   958|- [ ] Click node → side panel with entity detail
   959|- [ ] Search entities → graph filters
   960|- [ ] Click wikilink → focuses graph on that entity
   961|- [ ] Close modal → back to Stream tab
   962|- [ ] Mobile: graph pannable, nodes tappable
   963|- [ ] Zero console errors
   964|
   965|GIT:
   966|- [ ] Commit: "feat(stream): D3 knowledge graph dashboard"
   967|```
   968|
   969|---
   970|
   971|## Tier 5 — Polish
   972|
   973|### T18 — Theming Foundations
   974|
   975|| Field | Value |
   976||-------|-------|
   977|| **Status** | 🔲 |
   978|| **Depends on** | T1 |
   979|| **Files** | `src/lib/theme.ts`, `src/index.css`, Olympus backend: `/api/theme` |
   980|
   981|**What:** Config-driven theme. YAML at `~/pantheon/config/olympus-theme.yaml`. Runtime loading. Terminology map. Appearance tab in Settings. Don't paint into corners — no hardcoded values.
   982|
   983|**🚦 QA Gate T18:**
   984|```
   985|- [ ] Theme YAML schema defined and documented
   986|- [ ] GET /api/theme returns config, PUT /api/theme saves it
   987|- [ ] Colors (lumen-0 through lumen-7) configurable
   988|- [ ] Logo/favicon swappable via config
   989|- [ ] Border radius, spacing density configurable
   990|- [ ] Settings → Appearance shows preview
   991|- [ ] Theme persists across restarts
   992|- [ ] Terminology map functional (t('knowledge') → "Athenaeum")
   993|- [ ] No hardcoded color hex values in component code
   994|- [ ] Commit: "feat(theme): config-driven theming with YAML + runtime loading"
   995|```
   996|
   997|---
   998|
   999|### T19 — Kanban Fix + Port
  1000|
  1001|| Field | Value |
  1002||-------|-------|
  1003|| **Status** | 🔲 |
  1004|| **Depends on** | T1 |
  1005|| **Files** | `KanbanPanel.tsx`. Investigate: :8787 and Hermes Agent dashboard Kanban implementations. |
  1006|
  1007|**What:** Kanban works on :8787 and in Hermes dashboard. Investigate correct API path → fix Olympus proxy → port working UI. Feature-flag gated.
  1008|
  1009|**🚦 QA Gate T19:**
  1010|```
  1011|- [ ] Root cause of 500 identified (likely wrong API path)
  1012|- [ ] Kanban board renders with real data
  1013|- [ ] Create/edit/move/delete cards works
  1014|- [ ] Drag between columns works
  1015|- [ ] Feature toggle OFF → Kanban hidden from Tools menu
  1016|- [ ] Feature toggle ON → Kanban visible and functional
  1017|- [ ] Mobile: board scrollable, cards tappable
  1018|- [ ] Zero console errors
  1019|
  1020|GIT:
  1021|- [ ] Commit: "fix(kanban): correct API path + port from Pantheon UI"
  1022|```
  1023|
  1024|---
  1025|
  1026|### T20 — Tasks in Settings
  1027|
  1028|| Field | Value |
  1029||-------|-------|
  1030|| **Status** | 🔲 |
  1031|| **Depends on** | T19, T1 |
  1032|| **Files** | `TasksPanel.tsx` |
  1033|
  1034|**What:** Tasks tab in Admin. Pull from existing Hermes integration. Create/edit/complete tasks. Feature-flag gated.
  1035|
  1036|**🚦 QA Gate T20:**
  1037|```
  1038|- [ ] Tasks tab visible in Admin
  1039|- [ ] Task list loads from Hermes API
  1040|- [ ] Create task works
  1041|- [ ] Edit task (status, assignee, due date) works
  1042|- [ ] Complete/reopen task works
  1043|- [ ] Feature toggle gated
  1044|- [ ] Mobile: list scrollable, forms usable
  1045|- [ ] Zero console errors
  1046|
  1047|GIT:
  1048|- [ ] Commit: "feat(tasks): task management panel"
  1049|```
  1050|
  1051|---
  1052|
  1053|## Tier 6 — Integration Polish (Phase 4)
  1054|
  1055|> From OpenHuman/Pantheon integration spec. Depends on Phase 1 data flowing.
  1056|
  1057|### T21 — Obsidian Vault Mirror (P4a)
  1058|
  1059|| Field | Value |
  1060||-------|-------|
  1061|| **Status** | 🔲 |
  1062|| **Depends on** | T13 (data flowing to Codex-Stream) |
  1063|| **Files** | `~/.config/systemd/user/obsidian-stream-sync.service`, `~/.hermes/cron/obsidian-mirror/` |
  1064|
  1065|**What:** Sync `~/athenaeum/Codex-Stream/` as an Obsidian vault. Install `obsidian-headless` CLI, configure remote vault, systemd service for continuous sync. `sudo loginctl enable-linger konan` for logout survival.
  1066|
  1067|**🚦 QA Gate T21:**
  1068|```
  1069|- [ ] obsidian-headless installed globally (npm)
  1070|- [ ] Remote vault created via `ob sync-create-remote`
  1071|- [ ] Initial sync completes without errors
  1072|- [ ] systemd service starts: systemctl --user start obsidian-stream-sync
  1073|- [ ] Linger enabled: sudo loginctl enable-linger konan
  1074|- [ ] New chunks in Codex-Stream → appear in Obsidian within 60s
  1075|- [ ] Survives logout (linger keeps user session alive)
  1076|- [ ] Commit: "feat(obsidian): Codex-Stream → Obsidian vault mirror"
  1077|```
  1078|
  1079|---
  1080|
  1081|### T22 — Agent Retrieval Tools (P4b)
  1082|
  1083|| Field | Value |
  1084||-------|-------|
  1085|| **Status** | 🔲 |
  1086|| **Depends on** | T13 (data + entity co-occurrence in Ichor graph) |
  1087|| **Files** | `~/.hermes/plugins/stream-retrieval/` |
  1088|
  1089|**What:** Hermes plugin exposing 6 retrieval tools: `stream_search`, `stream_filter`, `stream_entity`, `stream_trending`, `stream_connections`, `stream_fetch_chunks`. FTS5 + ChromaDB hybrid search. Entity lookups via Ichor graph.
  1090|
  1091|**🚦 QA Gate T22:**
  1092|```
  1093|- [ ] plugin.yaml with 6 tool schemas
  1094|- [ ] stream_search(query, filters) → ranked chunks (FTS5 + ChromaDB)
  1095|- [ ] stream_filter(source, date_from, date_to) → time/provider filtered
  1096|- [ ] stream_entity(entity_name) → all chunks + co-occurring entities
  1097|- [ ] stream_trending(min_mentions=3) → hot entities from HotnessTracker
  1098|- [ ] stream_connections(entity_name) → entity neighbors via Ichor graph
  1099|- [ ] stream_fetch_chunks(chunk_ids) → full content by path
  1100|- [ ] Each tool returns empty [] not crash on missing data
  1101|