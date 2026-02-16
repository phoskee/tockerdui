# TockerDUI - Architecture Documentation

**Last Updated:** 16 February 2026  
**Version:** 0.1.0  
**Python:** 3.10+

## Overview

`tockerdui` now runs on a **Textual** UI runtime. The old curses UI layer has been removed.

High-level stack:

- `src/tockerdui/textual_app.py`: Textual app, input bindings, layout, modal flows, action dispatch.
- `src/tockerdui/backend.py`: Docker API integration and shell-based compose/helper actions.
- `src/tockerdui/model.py`: Data structures for resources and app-level state objects.
- `src/tockerdui/stats.py`: Aggregation/parsing logic for the stats tab.
- `src/tockerdui/config.py`: Config loading and keybinding normalization.
- `src/tockerdui/cache.py`: TTL cache for backend calls.

Entrypoints:

- `python -m tockerdui` (default)
- console script `tockerdui` (via `pyproject.toml`)

## Runtime Model

The Textual app drives UI refresh via timer (`set_interval`) and calls backend methods directly.

Update cadence:

- Containers + self usage: ~1s
- Images/Volumes/Networks/Compose: ~5s
- Logs: refreshed on tick when `containers` tab is active

Bulk selection is maintained per-tab in-memory in `TockerTextualApp.bulk_selected`.

## Action Flow

1. Key binding (`Binding` or `on_key`) triggers action.
2. Action dispatch routes to single-item or bulk handler.
3. Backend executes Docker SDK call or subprocess command.
4. App forces refresh and re-renders list/details/status.

Modal interactions (`ConfirmScreen`, `InputScreen`, `ActionMenuScreen`) are handled via `push_screen_wait`.

## Testing

Current tests focus on:

- Backend behavior and error handling.
- State/cache/config utility behavior.
- Textual smoke/regression coverage (imports/bindings).

Legacy curses integration tests were removed with the old UI runtime.

## Notes

- `src/tockerdui/state.py` remains as legacy compatibility/test support and is not the primary UI runtime.
- Future improvements should centralize state into Textual reactive models and add richer Textual integration tests.
