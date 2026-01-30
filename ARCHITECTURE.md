# TockerDUI - Architecture Documentation

**Last Updated:** 30 Gennaio 2026  
**Version:** 0.1.0  
**Python:** 3.10+

---

## 📐 System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     TockerDUI Terminal UI                        │
│                    (curses-based interface)                      │
└────────────────┬──────────────────────────────────────┬──────────┘
                 │                                      │
         ┌───────▼────────┐                    ┌────────▼──────────┐
         │   main.py      │                    │    ui.py          │
         │  Event Loop    │◄──────────────────►│  Rendering Engine │
         │  & Handlers    │    State Snapshot  │  (Curses library) │
         └───────┬────────┘                    └───────────────────┘
                 │
                 │  Commands
         ┌───────▼────────────────────────────┐
         │      backend.py                    │
         │   Docker API Wrapper               │
         │  (docker-py library)               │
         └───────┬────────────────────────────┘
                 │
         ┌───────▼────────────────────────────┐
         │   state.py                         │
         │ Thread-Safe State Manager          │
         │ (RLock, async workers)             │
         └───────┬────────────────────────────┘
                 │
         ┌───────▼────────────────────────────┐
         │   model.py                         │
         │ Data Structures (Dataclasses)      │
         └────────────────────────────────────┘
```

---

## 🏗️ Component Responsibilities

### 1. **main.py** - Event Loop & Orchestration

```
┌──────────────────────────────────┐
│     Main Event Loop              │
│  ┌────────────────────────────┐  │
│  │ 1. Check state changes     │  │
│  │ 2. Poll user input (getch) │  │
│  │ 3. Handle keyboard commands│  │
│  │ 4. Trigger backend actions │  │
│  │ 5. Render UI (if changed)  │  │
│  └────────────────────────────┘  │
│                                  │
│  Key Functions:                  │
│  • main(stdscr)                  │
│  • handle_action(key, tab, ...)  │
│                                  │
│  Thread Model:                   │
│  ┌─ Main Thread (curses)         │
│  └─ Workers (background)         │
│     • ListWorker (1s refresh)    │
│     • StatsWorker (5s refresh)   │
│     • LogsWorker (1s refresh)    │
└──────────────────────────────────┘
```

**Key Responsibilities:**

- Non-blocking input handling (100ms timeout)
- State change detection (differential updates)
- Action dispatch to backend
- Terminal resize handling
- Worker lifecycle management

---

### 2. **backend.py** - Docker API Wrapper

```
┌──────────────────────────────────┐
│   DockerBackend Class            │
│                                  │
│  Data Retrieval:                 │
│  • get_containers()              │
│  • get_images()                  │
│  • get_volumes()                 │
│  • get_networks()                │
│  • get_composes()                │
│  • get_stats(container_id)       │
│  • get_logs(container_id)        │
│                                  │
│  Container Actions:              │
│  • start_container()             │
│  • stop_container()              │
│  • restart_container()           │
│  • pause_container()             │
│  • unpause_container()           │
│  • remove_container()            │
│  • rename_container()            │
│  • commit_container()            │
│  • copy_to_container()           │
│                                  │
│  Image Actions:                  │
│  • run_container()               │
│  • remove_image()                │
│  • save_image()                  │
│  • load_image()                  │
│  • build_image()                 │
│                                  │
│  Compose Actions:                │
│  • compose_up()                  │
│  • compose_down()                │
│  • compose_remove()              │
│  • compose_pause()               │
│                                  │
│  Error Handling:                 │
│  @docker_safe decorator:         │
│  • Catches all exceptions        │
│  • Logs errors w/ traceback      │
│  • Returns default value         │
│  • Prevents silent failures      │
└──────────────────────────────────┘
```

**Error Handling Pattern:**

```python
@docker_safe(default_return=[])
def get_containers(self) -> List[ContainerInfo]:
    # Exception caught and logged automatically
    # Returns [] if Docker error occurs
```

---

### 3. **state.py** - Thread-Safe State Management

```
┌──────────────────────────────────┐
│   StateManager Class             │
│                                  │
│  State Storage:                  │
│  ┌─ AppState (dataclass)         │
│  │  • containers[]               │
│  │  • images[]                   │
│  │  • volumes[]                  │
│  │  • networks[]                 │
│  │  • composes[]                 │
│  │  • selected_tab/index         │
│  │  • filter_text                │
│  │  • last_error                 │
│  │  • version (for diffing)      │
│  └─                              │
│                                  │
│  Thread Safety:                  │
│  • RLock() for reentrant access  │
│  • get_snapshot() w/ lock        │
│  • update_* methods w/ lock      │
│                                  │
│  Background Workers:             │
│  ┌─ ListWorker                   │
│  │  Periodically fetches:        │
│  │  - get_containers()           │
│  │  - get_images()               │
│  │  - get_volumes()              │
│  │  - get_networks()             │
│  │  - get_composes()             │
│  │  - Filters & sorts            │
│  │  Interval: 1 second           │
│  │                               │
│  ├─ StatsWorker                  │
│  │  Fetches CPU/RAM for each     │
│  │  running container            │
│  │  Interval: 5 seconds          │
│  │                               │
│  └─ LogsWorker                   │
│     Fetches tail of logs for     │
│     selected container           │
│     Interval: 1 second           │
│                                  │
│  Threading Model:                │
│  • Daemon threads (auto-cleanup) │
│  • Main thread: UI rendering     │
│  • Workers: background updates   │
│  • No curses calls from workers  │
└──────────────────────────────────┘
```

**Thread Safety Guarantees:**

- All state access protected by RLock
- Main thread never blocked
- Workers use try-except for robustness
- Graceful shutdown via daemon threads

---

### 4. **ui.py** - Curses Rendering Engine

```
┌─────────────────────────────────────┐
│      Curses Rendering Module        │
│                                     │
│  Initialization:                    │
│  • init_colors() - 8 color pairs    │
│  • stdscr setup (nodelay mode)      │
│                                     │
│  Main Rendering:                    │
│  • draw_ui(stdscr, state)           │
│    ├─ draw_header(state)            │
│    ├─ draw_list(state) ← MAIN VIEW  │
│    ├─ draw_details(state)           │
│    ├─ draw_error_footer(state)      │
│    └─ stdscr.refresh()              │
│                                     │
│  draw_list() Layout:                │
│  ┌─────────────────────────────┐    │
│  │ HEADER: Tab, Title, Filter  │    │
│  ├─────────────────────────────┤    │
│  │ COL_1  COL_2  COL_3  COL_4  │    │
│  ├─────────────────────────────┤    │
│  │ item1  val   val    val    │     │
│  │ item2  val   val    val    │     │
│  │ item3  val   val    val    │     │
│  ├─────────────────────────────┤    │
│  │ FOOTER: Status, Shortcuts   │    │
│  └─────────────────────────────┘    │
│                                     │
│  Modal Dialogs:                     │
│  • draw_action_menu()               │
│  • draw_help_modal()                │
│  • ask_confirmation()               │
│  • prompt_input()                   │
│                                     │
│  Color Pairs (1-8):                 │
│  1 = White (default)                │
│  2 = Green (running/success)        │
│  3 = Red (stopped/error)            │
│  4 = Cyan (headers)                 │
│  5 = Blue (column headers)          │
│  6 = Yellow (paused)                │
│  7 = Reverse (selected item)        │
│  8 = Dim (secondary text)           │
└─────────────────────────────────────┘
```

**Column Layout Constants:**

```python
COL_PROJECT = 12
COL_NAME_CONTAINER = 20
COL_STATUS = 10
COL_CPU = 7
COL_MEMORY = 10
COL_IMAGE = 20
# ... (8 constants total)
```

---

### 5. **model.py** - Data Structures

```
Dataclasses (immutable, type-safe):
├─ ContainerInfo(id, name, status, image, ...)
├─ ImageInfo(id, tags, size_mb, created)
├─ VolumeInfo(name, driver, mountpoint)
├─ NetworkInfo(id, name, driver, subnet)
├─ ComposeInfo(name, status, config_files)
└─ AppState(containers, images, volumes, ...)
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                   │
│                     (Keyboard getch)                                │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│                    main.py Event Loop                               │
│                                                                     │
│  1. handle_action(key) → Dispatch command                           │
│  2. backend.method() → Docker API call                              │
│  3. state.update_*() → State change (locked)                        │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
     ┌─────────────────┴─────────────────┐
     │                                   │
┌────▼──────────────┐         ┌─────────▼───────────┐
│  Main Thread      │         │  Background Workers │
│                   │         │                     │
│ 1. get_snapshot() │         │ • ListWorker        │
│ 2. Check version  │         │ • StatsWorker       │
│ 3. Draw UI        │         │ • LogsWorker        │
│ 4. render() loop  │         │ (every 1-5 seconds) │
└───────────────────┘         └─────────────────────┘
       │
       │ Rendered Terminal Output
       │
┌──────▼──────────────────────────────────────────────────────────────┐
│                        TERMINAL (curses)                            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ TOCKERDUI │ CONTAINERS IMAGES VOLUMES NETWORKS COMPOSE        │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │ PROJECT      NAME           STATUS     CPU   MEM   IMAGE      │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │ myapp        web_container  running    1.2%  256M  nginx:...  │  │
│  │ myapp        db_container   running    0.5%  512M  postgres   │  │
│  │ cache        redis_server   exited     --    --    redis:...  │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │ [SORT: NAME] | TAB: Focus (LIST) | Enter: Menu | ?: Help      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Worker Thread Lifecycle

```
main() starts workers:
├─ ListWorker.start()
├─ StatsWorker.start()
└─ LogsWorker.start()

Each worker:
┌────────────────────────┐
│ while True:            │
│  ├─ try:               │
│  │  ├─ backend.get()   │
│  │  ├─ state.update()  │
│  │  └─ sleep(interval) │
│  └─ except Exception:  │
│     └─ log & continue  │
└────────────────────────┘

Shutdown:
├─ User presses 'q' → main() exits
├─ All workers are daemon threads
└─ Auto-cleanup on process exit
```

---

## 🔒 Thread Safety Pattern

```python
# StateManager uses RLock for reentrant locking:

with self._state_lock:  # Acquire lock
    self._state.containers = new_containers
    self._state.version += 1
    # Lock automatically released

# Main thread:
state = state_mgr.get_snapshot()  # Returns copy w/ lock
for item in state.containers:      # Safe iteration
    render(item)

# Worker threads:
state_mgr.update_containers(data)  # Thread-safe update
```

---

## 🛡️ Error Handling Strategy

```
Backend errors are NEVER silently ignored:

┌─────────────────────────────────────┐
│  Docker operation fails (exception) │
└────────────────┬────────────────────┘
                 │
         ┌───────▼────────────┐
         │ @docker_safe       │
         │ decorator catches  │
         └───────┬────────────┘
                 │
         ┌───────▼────────────────────┐
         │ 1. logger.error() - logged │
         │ 2. return default_value    │
         │ 3. state.set_error() - UI  │
         └───────┬────────────────────┘
                 │
         ┌───────▼──────────────┐
         │ User sees error in:  │
         │ • Red footer (3s)    │
         │ • Message bar        │
         │ • UI doesn't crash   │
         └──────────────────────┘
```

---

## 📈 Performance Optimizations

### 1. **Differential Rendering**

- Only re-render if state.version changed
- Track render version separately
- Skip draw calls when nothing changed

### 2. **Filtered Collections**

- Filter on state update (not on render)
- Cache filtered results
- Only render visible items

### 3. **Worker Intervals**

- ListWorker: 1s (fast container updates)
- StatsWorker: 5s (CPU/RAM less critical)
- LogsWorker: 1s (user expects fresh logs)

### 4. **Terminal Resize Handling**

- Detect via getmaxyx() each loop
- Recreate windows only when size changes
- Clear and redraw on resize

---

## 🧪 Testing Strategy

```
├─ Unit Tests (test_backend.py, test_state.py)
│  └─ Individual function behavior
│
├─ Integration Tests (test_main_integration.py)
│  └─ Worker threads, state manager interactions
│
├─ Coverage Tests (test_coverage_improvements.py)
│  ├─ Error handling (@docker_safe)
│  ├─ Path validation (security)
│  ├─ Compose actions
│  └─ State filtering/selection
│
└─ Manual Tests
   ├─ Docker container actual interaction
   ├─ Terminal resize scenarios
   └─ High-frequency user input
```

**Test Metrics:**

- Total Tests: 39
- Coverage: ~60%+ (tracked via pytest --cov)
- CI/CD: GitHub Actions (every push)

---

## 🚀 Future Enhancements

### Sprint 4 - Planned Features:

1. **Differential Updates** - Only re-render changed items
2. **Image Caching** - Cache get_images() with 5min TTL
3. **Bulk Select** - Multi-select with Ctrl+A
4. **Config File** - YAML config for keybindings/themes
5. **Log Follow** - Real-time log streaming
6. **Stats Dashboard** - Aggregate CPU/RAM/disk metrics

### Potential Improvements:

- Port to Rich framework (better rendering)
- Docker Swarm support (future)
- Kubernetes support (future)
- Windows native support (WSL recommended now)

---

## 📚 Dependency Map

```
tockerdui (main package)
├─ docker>=7.0.0 (runtime)
│  └─ Used by backend.py for Docker API
├─ curses (stdlib, Python 3.10+)
│  └─ Used by ui.py for terminal rendering
└─ dev dependencies (testing/code quality)
   ├─ pytest, pytest-cov, pytest-mock
   ├─ black, flake8, mypy, isort
   └─ bandit, safety
```

---

## 🔧 Development Workflow

```
1. Make code changes
2. Run tests: pytest -v
3. Format code: black src/tockerdui
4. Lint: flake8 src/tockerdui
5. Type check: mypy src/tockerdui
6. Git commit (pre-commit hooks run)
7. Push to GitHub (CI/CD runs)
```

---

## 📖 Key Takeaways

1. **Main Loop:** Non-blocking event loop with ~100ms refresh
2. **State Management:** Thread-safe with RLock, immutable snapshots
3. **Error Handling:** Centralized via @docker_safe decorator
4. **UI Rendering:** Differential updates to avoid flicker
5. **Workers:** Background threads for async data fetching
6. **Type Safety:** Dataclasses + type hints for clarity
7. **Testing:** 39 unit/integration tests with CI/CD

---

**Last Updated:** 30 Gennaio 2026  
**Version:** 0.1.0
