# 🐳 tockerdui

**tockerdui** is a lightweight, fast, and entirely terminal-based alternative to Docker Desktop. Manage your containers, images, volumes, and networks with the speed of your keyboard.

> **The Story**: tockerdui was born out of the frustration of having to run dozens of Docker CLI commands to get an overview, often receiving fragmented information that is difficult to read quickly. It is designed for those who want the power of Docker without having to memorize every CLI flag, and for all those environments (headless servers, remote SSH connections, resource-constrained systems) where Docker Desktop is not available or its GUI is too heavy.

<!-- ![tockerdui UI](https://via.placeholder.com/800x400?text=tockerdui+ +TUI) -->

## ✨ Key Features

- **Multi-Tab Interface**: Navigate through Containers, Images, Volumes, Networks, Compose Projects, and Stats.
- **Bulk Selection**: Manage multiple items simultaneously (mass start, stop, removal).
- **Quick Action Menu**: Press `Enter` on any item to see available actions.
- **Real-Time Stats**: Monitor container CPU and RAM usage directly.
- **Interactive Logs**: Full-screen log viewer with search and smooth scrolling.
- **Compose Management**: Start, stop, and refresh your `docker-compose` projects.
- **Flicker-Free**: Optimized rendering to avoid terminal flickering.
- **Instant Filter**: Quickly search and filter through every list.

---

## 🚀 Quick Installation

To install tockerdui and have it available as a global command:

```bash
git clone https://github.com/phoskee/tockerdui.git
cd tockerdui
./install.sh
```

This will install the application in `~/.local/share/tockerdui` and create a symbolic link in `~/.local/bin`. Ensure that `~/.local/bin` is in your PATH.

## 🔄 Updating

To update the application to the latest version:

```bash
cd tockerdui
./update.sh
```

After installation, restart your terminal or run `source ~/.bashrc` (or `~/.zshrc`).

---

## 🗑️ Uninstallation

If you wish to remove tockerdui from your system:

```bash
./uninstall.sh
```

---

## ⌨️ How to Use (Keybindings)

### General Navigation

| Key        | Action                                                    |
| ---------- | --------------------------------------------------------- |
| `1` - `6`  | Change Tab (Containers, Images, Vol, Net, Compose, Stats) |
| `↑` / `↓`  | Navigate the list                                         |
| `Enter`    | **Open Action Menu** (Recommended)                        |
| `/`        | Activate Filter / Search                                  |
| `Esc`      | Clear filter or close menu                                |
| `Tab`      | Toggle Focus between list and logs/details                |
| `h` or `?` | Show quick help                                           |
| `q`        | Exit tockerdui                                            |

### Multi-Selection (Bulk Mode)

| Key     | Action                       |
| ------- | ---------------------------- |
| `b`     | Toggle Multi-Selection Mode  |
| `Space` | Select/Deselect current item |
| `a`     | Select all items in the list |
| `d`     | Deselect all items           |

### Container Shortcuts

| Key  | Action                               |
| ---- | ------------------------------------ |
| `s`  | Start                                |
| `t`  | Stop                                 |
| `r`  | Restart                              |
| `z`  | Pause / Unpause                      |
| `l`  | View Logs (Interactive)              |
| `x`  | Open Shell (`exec /bin/bash`)        |
| `n`  | Rename Container                     |
| `k`  | Commit (Create image from container) |
| `cp` | Copy file to container               |

### Image Shortcuts

| Key | Action                 |
| --- | ---------------------- |
| `R` | Run as a new container |
| `p` | Pull / Update image    |
| `H` | View History           |
| `B` | Build from Dockerfile  |
| `L` | Load image (.tar)      |
| `S` | Save image (.tar)      |

---

## 🛠 Global Actions

- **Pruning**: Press `Shift + P` to clean all unused Docker resources (stopped containers, orphaned images, etc.).
- **Inspect**: Press `i` on any resource to view its complete JSON configuration.

## 📄 License

Distributed under the **MIT** license. See the `LICENSE` file for details.
