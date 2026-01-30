# TODO - TOCKERDUI CODEBASE ANALYSIS

**Last Updated:** 30 Gennaio 2026  
**Total Effort:** 45-57 hours (4 sprints)  
**Current Status:** ✅ SPRINT 1 COMPLETATO + Sprint 2 In Progress (Task 2.1/7 done)

---

## 📋 Quick Wins (< 30 min each)

- [x] **QW1** - Fix syntax error `draw_help_modal()` (5 min) - ui.py:420 ✅
- [x] **QW2** - Rimuovere debug code `/tmp/tockerdui_debug.log` (5 min) - backend.py ✅
- [x] **QW3** - Sincronizzare dipendenze pyproject/requirements (10 min) ✅
- [x] **QW4** - Fix import nei test (10 min) - test_main_integration.py ✅

---

## 🔴 SPRINT 1: Stabilità Critica (8-10 ore)

**Obiettivo:** Rendere il progetto non-crashy, installabile e testabile

### Task

- [x] **1.1** - Fix syntax error `draw_help_modal()` (5 min) ✅
  - **File:** `src/tockerdui/ui.py:420`
  - **Descrizione:** Aggiungere `lines = [...]` prima di usare la variabile
  - **Impatto:** Crash UI su tasto `?` → CRASH
  - **Severity:** 🔴 CRITICA

- [x] **1.2** - Rimuovere duplicati file root (10 min) ✅
  - **File:** Root: `main.py`, `backend.py`, `ui.py`, `model.py`, `state.py`
  - **Descrizione:** Eliminare file root (duplicati di src/tockerdui/)
  - **Impatto:** Confusione sulla sorgente della verità
  - **Severity:** 🔴 CRITICA

- [x] **1.3** - Sincronizzare dipendenze (10 min) ✅
  - **File:** `pyproject.toml`, `requirements.txt`
  - **Descrizione:** Rimuovere `requests`, `urllib3` da requirements.txt (non usati nel codice)
  - **Impatto:** Installazione fallisce o inconsistenza
  - **Severity:** 🔴 CRITICA

- [x] **1.4** - Fix import nei test (10 min) ✅
  - **File:** `tests/test_main_integration.py`
  - **Descrizione:** Cambiare `from tockerdui.main import ListWorker` → `from tockerdui.state import ListWorker`
  - **Impatto:** Test non eseguibili
  - **Severity:** 🔴 CRITICA

- [x] **1.5** - Rimuovere debug code (5 min) ✅
  - **File:** `src/tockerdui/backend.py:272, 278`
  - **Descrizione:** Remove `with open("/tmp/tockerdui_debug.log", "a")` code blocks
  - **Impatto:** Code clutter, log pollution
  - **Severity:** 🟡 MEDIA

- [x] **1.6** - Aggiungere docstring ai moduli (40 min) ✅
  - **File:** `src/tockerdui/__init__.py`, `main.py`, `backend.py`, `ui.py`, `state.py`, `model.py`
  - **Descrizione:** Module-level docstring che spiega responsabilità e componenti principali
  - **Impatto:** Documentazione, IDE support
  - **Severity:** 🟢 BASSA

**Checklist Sprint 1:**

- [x] Eseguire `pytest` - tutti i test passano ✅
- [x] Eseguire `python -m tockerdui --help` - nessun error ✅
- [x] Verificare `python -m pip install -e .` funziona ✅

---

## 🟠 SPRINT 2: Error Handling & Robustness (12-15 ore)

**Obiettivo:** Errori visibili, nessun silent fail, UI resiliente

### Task

- [x] **2.1** - Centralizzare error handling in backend (1h) ✅
  - **File:** `src/tockerdui/backend.py`
  - **Descrizione:**
    - Creare decorator `@docker_safe` che:
      - Loga eccezione con traceback
      - Ritorna valore default ([], {}, None)
      - Salva error message in state
    - Applicare a tutti i metodi backend
  - **Impatto:** Errori visibili, facilita debug
  - **Severity:** 🟠 ALTA

- [ ] **2.2** - Aggiungere error footer in UI (1h 30 min)
  - **File:** `src/tockerdui/ui.py`, `src/tockerdui/state.py`
  - **Descrizione:**
    - Aggiungere `state.last_error` con timestamp
    - Aggiungere `draw_error_footer()` che visualizza in RED se error < 3s
    - Clear error su any new action
  - **Impatto:** UX migliorata, utente sa cosa è fallito
  - **Severity:** 🟠 ALTA

- [ ] **2.3** - Fix race condition update modal (30 min)
  - **File:** `src/tockerdui/main.py:276-280`
  - **Descrizione:**
    - Usare `with state.lock:` attorno modal per impedire aggiornamenti concorrenti
    - Oppure async-safe mechanism per modal
  - **Impatto:** Crash durante update check
  - **Severity:** 🟠 ALTA

- [ ] **2.4** - Aggiungere type hints a funzioni critiche (1h)
  - **File:** `src/tockerdui/main.py`, `src/tockerdui/backend.py`, `src/tockerdui/state.py`
  - **Descrizione:**
    - Aggiungere type hints a `handle_action()`, `get_containers()`, `ListWorker`, `StatsWorker`
    - Usare `typing` module per complex types
  - **Impatto:** IDE support, fewer runtime errors
  - **Severity:** 🟡 MEDIA

- [ ] **2.5** - Implementare Compose actions (45 min)
  - **File:** `src/tockerdui/main.py:handle_action()`, `src/tockerdui/backend.py`
  - **Descrizione:**
    - Aggiungere case per U (up), D (down), R (remove), P (pause) nel Compose tab
    - Implementare `compose_up()`, `compose_down()`, `compose_remove()`, `compose_pause()` in backend
  - **Impatto:** Compose tab fully functional
  - **Severity:** 🟠 ALTA

- [ ] **2.6** - Validare path in `copy_to_container()` (30 min)
  - **File:** `src/tockerdui/backend.py:copy_to_container()`
  - **Descrizione:**
    - Aggiungere checks per path traversal (`../`, `~`, absolute paths)
    - Validare src_path e dest_path
  - **Impatto:** Security (prevent path traversal attacks)
  - **Severity:** 🟡 MEDIA

- [ ] **2.7** - Fix logging path hardcoded (20 min)
  - **File:** `src/tockerdui/backend.py`, `src/tockerdui/__init__.py`
  - **Descrizione:**
    - Usare `Path.home() / ".local/share/tockerdui/logs"` with XDG support
    - Create directory se non esiste
    - Fallback a `/tmp` se permission denied
  - **Impatto:** Portabilità, macOS/Windows compatibility
  - **Severity:** 🟡 MEDIA

**Checklist Sprint 2:**

- [ ] Eseguire `pytest` - tutti i test passano
- [ ] Simulare Docker error - error message visualizzato in UI
- [ ] Verificare race condition non si verifica (stress test)
- [ ] Testare Compose up/down/remove/pause

---

## 🟡 SPRINT 3: Testing & Quality (10-12 ore)

**Obiettivo:** Test coverage >= 60%, nessun magic numbers, CI/CD setup

### Task

- [ ] **3.1** - Refactor column width logic (45 min)
  - **File:** `src/tockerdui/ui.py:draw_list()`
  - **Descrizione:**
    - Estrarre logica colonne in `ColumnLayout` dataclass
    - Aggiungere named constants per fixed widths
    - Renderizzare column layout più leggibile
  - **Impatto:** Manutenibilità, estensibilità
  - **Severity:** 🟡 MEDIA

- [ ] **3.2** - Aumentare test coverage a 60% (2-3 ore)
  - **File:** `tests/test_backend.py`, `tests/test_state.py`, `tests/test_main_integration.py`
  - **Descrizione:**
    - Aggiungere test per backend error handling
    - Aggiungere test per threading/worker shutdown
    - Aggiungere test per UI resize edge cases
    - Aggiungere test per filtering logic completo
    - Mock curses per testare UI
  - **Impatto:** Regression prevention, confidence per refactoring
  - **Severity:** 🟡 MEDIA

- [ ] **3.3** - Setup GitHub Actions (1h)
  - **File:** `.github/workflows/test.yml`
  - **Descrizione:**
    - Aggiungere workflow che esegue:
      - `pytest` su ogni push
      - `black --check` code formatting
      - `flake8` linting
      - `mypy` type checking
  - **Impatto:** Quality gate, CI/CD
  - **Severity:** 🟡 MEDIA

- [ ] **3.4** - Setup pre-commit hooks (30 min)
  - **File:** `.pre-commit-config.yaml`
  - **Descrizione:**
    - Configurare pre-commit hooks:
      - black (code formatting)
      - isort (import sorting)
      - flake8 (linting)
      - mypy (type checking)
  - **Impatto:** Code quality enforcement
  - **Severity:** 🟡 MEDIA

- [ ] **3.5** - Aggiungere Architecture Documentation (1h)
  - **File:** `ARCHITECTURE.md` (new)
  - **Descrizione:**
    - ASCII diagram mostrando:
      - main.py event loop
      - state.py threading model
      - backend.py Docker API wrapper
      - ui.py curses rendering
    - Spiegare data flow tra componenti
    - Spiegare worker lifecycle
  - **Impatto:** Onboarding, maintainability
  - **Severity:** 🟡 MEDIA

**Checklist Sprint 3:**

- [ ] `pytest --cov` reports >= 60%
- [ ] `black --check` passa
- [ ] `flake8` passa (0 errors)
- [ ] `mypy` passa (0 errors)
- [ ] GitHub Actions workflow esegue su push
- [ ] ARCHITECTURE.md aggiunto e completo

---

## 🟢 SPRINT 4: Features & Enhancements (15-20 ore)

**Obiettivo:** Funzionalità next-gen, caching, bulk operations

### Task

- [ ] **4.1** - Implementare differential updates (1h)
  - **File:** `src/tockerdui/state.py:AppState`
  - **Descrizione:**
    - Aggiungere versioning a state collections
    - Solo re-render UI se state version effettivamente cambiato
    - Ridurre flickering e CPU usage
  - **Impatto:** Performance optimization
  - **Severity:** 🟢 BASSA

- [ ] **4.2** - Aggiungere image caching (1h 30 min)
  - **File:** `src/tockerdui/backend.py`
  - **Descrizione:**
    - Implementare cache layer per `get_images()` con TTL 5 min
    - Invalidare cache on build/pull/remove actions
    - Usare decorator `@cache_with_ttl(seconds=300)`
  - **Impatto:** Performance (fewer Docker API calls)
  - **Severity:** 🟢 BASSA

- [ ] **4.3** - Implementare bulk select mode (1h 30 min)
  - **File:** `src/tockerdui/main.py`, `src/tockerdui/state.py`, `src/tockerdui/ui.py`
  - **Descrizione:**
    - Aggiungere checkbox selection mode
    - Spacebar: toggle checkbox su selected item
    - Ctrl+A: select all
    - Ctrl+D: deselect all
    - Bulk actions: start/stop/restart/remove su selected items
  - **Impatto:** UX enhancement, productivity
  - **Severity:** 🟢 BASSA

- [ ] **4.4** - Aggiungere config file support (2 ore)
  - **File:** `src/tockerdui/config.py` (new)
  - **Descrizione:**
    - Creare Config manager che legge da `~/.config/tockerdui/config.yaml`
    - Supportare:
      - Keybindings customizzabili
      - Color themes
      - Auto-update on/off
      - Log location override
    - Merge con defaults se file manca
  - **Impatto:** Flexibility, user preference
  - **Severity:** 🟢 BASSA

- [ ] **4.5** - Implementare log follow mode (1h)
  - **File:** `src/tockerdui/state.py:LogsWorker`
  - **Descrizione:**
    - Usare `docker logs --follow` invece di snapshot
    - Implementare stream parsing
    - Mantenere buffer últimas N righe
  - **Impatto:** Real-time logs, UX migliorata
  - **Severity:** 🟢 BASSA

- [ ] **4.6** - Aggiungere statistics dashboard (2-3 ore)
  - **File:** `src/tockerdui/ui.py`, `src/tockerdui/backend.py`
  - **Descrizione:**
    - Tab dedicato "Stats" con:
      - Total CPU/RAM usage (aggregate)
      - Container count by state (running/stopped/paused)
      - Image count
      - Disk usage breakdown (volumes)
      - ASCII art charts
  - **Impatto:** Monitoring, insights
  - **Severity:** 🟢 BASSA

**Checklist Sprint 4:**

- [ ] Differential updates reduce render calls
- [ ] Image cache hits >= 80% (log cache stats)
- [ ] Bulk select works per tutti i tab
- [ ] Config file loaded e applied
- [ ] Log follow mostra realtime updates
- [ ] Stats dashboard renders correttamente

---

## 📊 Tabella Riepilogativa: Priorità e Impatto

| ID  | Problema                     | Severità   | Impact           | Fix Time | Sprint | File            |
| --- | ---------------------------- | ---------- | ---------------- | -------- | ------ | --------------- |
| 1.1 | Syntax error draw_help_modal | 🔴 CRITICA | Crash            | 5 min    | 1      | ui.py:420       |
| 1.2 | Duplicati root               | 🔴 CRITICA | Confusione       | 10 min   | 1      | Root            |
| 1.3 | Dep mismatch                 | 🔴 CRITICA | Install fail     | 10 min   | 1      | pyproject/req   |
| 1.4 | Test import error            | 🔴 CRITICA | Test fail        | 10 min   | 1      | test*main*\*    |
| 1.5 | Debug code                   | 🟡 MEDIA   | Clutter          | 5 min    | 1      | backend.py      |
| 1.6 | No docstrings                | 🟡 MEDIA   | Documentation    | 40 min   | 1      | Various         |
| 2.1 | Silent exceptions            | 🟠 ALTA    | No debug         | 1h       | 2      | backend.py      |
| 2.2 | Error display                | 🟠 ALTA    | Poor UX          | 1h 30    | 2      | ui/state.py     |
| 2.3 | Race condition               | 🟠 ALTA    | Crash            | 30 min   | 2      | main.py         |
| 2.4 | No type hints                | 🟡 MEDIA   | IDE/errors       | 1h       | 2      | Various         |
| 2.5 | Compose incomplete           | 🟠 ALTA    | Incomplete       | 45 min   | 2      | main.py         |
| 2.6 | Path validation              | 🟡 MEDIA   | Security         | 30 min   | 2      | backend.py      |
| 2.7 | Log path hardcoded           | 🟡 MEDIA   | Portability      | 20 min   | 2      | backend.py      |
| 3.1 | Magic numbers                | 🟡 MEDIA   | Hard to maintain | 45 min   | 3      | ui.py           |
| 3.2 | Low test coverage            | 🟡 MEDIA   | Regression risk  | 2-3h     | 3      | tests/          |
| 3.3 | No CI/CD                     | 🟡 MEDIA   | Quality gate     | 1h       | 3      | .github/        |
| 3.4 | No pre-commit                | 🟡 MEDIA   | Code quality     | 30 min   | 3      | .pre-commit/    |
| 3.5 | No architecture doc          | 🟡 MEDIA   | Onboarding       | 1h       | 3      | ARCHITECTURE.md |
| 4.1 | No differential updates      | 🟢 BASSA   | Perf             | 1h       | 4      | state.py        |
| 4.2 | No caching                   | 🟢 BASSA   | Perf             | 1h 30    | 4      | backend.py      |
| 4.3 | No bulk select               | 🟢 BASSA   | UX               | 1h 30    | 4      | main/state      |
| 4.4 | No config file               | 🟢 BASSA   | Flexibility      | 2h       | 4      | config.py       |
| 4.5 | No log follow                | 🟢 BASSA   | Feature          | 1h       | 4      | state.py        |
| 4.6 | No stats dashboard           | 🟢 BASSA   | Feature          | 2-3h     | 4      | ui.py           |

---

## ⏱️ Effort Breakdown

| Sprint                       | Hours           | Status        | Target Date    |
| ---------------------------- | --------------- | ------------- | -------------- |
| Sprint 1 (Stabilità Critica) | 8-10h           | ✅ COMPLETATO | ✅ 30 Gen 2026 |
| Sprint 2 (Error Handling)    | 12-15h          | ⏳ TODO       | Next week      |
| Sprint 3 (Testing & Quality) | 10-12h          | ⏳ TODO       | Week 3         |
| Sprint 4 (Features)          | 15-20h          | ⏳ TODO       | Week 4-5       |
| **TOTAL**                    | **45-57 hours** | -             | ~2 months      |

---

## 🎯 Execution Notes

### Cosa NON fare (out of scope)

- ❌ Rewrite completo UI in different framework (curses → rich è future work)
- ❌ Aggiungere feature Docker Swarm (too niche, out of scope)
- ❌ Aggiungere support Kubernetes (out of scope)
- ❌ Port a Windows natively (WSL è supported)

### Decisioni Architetturali

- ✅ Mantenere curses (lightweight, works, responsive)
- ✅ Mantenere threading model (responsive UI guaranteed)
- ✅ Aggiungere config file (YAML) instead of env vars (easier)
- ✅ Python 3.10+ requirement (modern features, better error messages)

### Testing Strategy

- **Unit tests:** Ogni funzione backend (docker operations)
- **Integration tests:** State manager (threading, concurrency)
- **Acceptance tests:** UI (curses mocking per testare rendering)
- **Manual smoke tests:** Docker container effettivo per validare

---

## 📝 Status Legend

- ⏳ TODO - Not started
- 🔄 IN_PROGRESS - Currently being worked on
- ✅ DONE - Completed successfully
- 🔴 BLOCKED - Blocked on dependency
- ⚠️ PARTIAL - Partially completed

---

## 🚀 Next Immediate Actions

1. **TODAY (30 Gen):**
   - [ ] Review this todo.md file
   - [ ] Start Sprint 1 tasks (QW1, 1.1, 1.2 first)

2. **TOMORROW (31 Gen):**
   - [ ] Complete Sprint 1 remaining tasks
   - [ ] Run full test suite, verify no regressions

3. **THIS WEEK:**
   - [ ] Complete Sprint 1 fully
   - [ ] Start Sprint 2 error handling

4. **NEXT WEEK:**
   - [ ] Complete Sprint 2
   - [ ] Begin Sprint 3 testing & CI/CD

5. **WEEKS 3-4:**
   - [ ] Complete Sprint 3 & 4
   - [ ] Final integration testing
   - [ ] Release v1.0.0 (production-ready)

---

## 📞 Questions / Clarifications Needed

- [ ] Should we bump version to 1.0.0 after Sprint 2? Or wait for Sprint 4?
- [ ] Should we update GitHub URLs in pyproject.toml before first release?
- [ ] Any preference on color theme for stats dashboard?
- [ ] Should Docker Swarm be considered for future sprints?

---

**Last Updated:** 30 Gennaio 2026  
**Next Review:** After Sprint 1 completion
