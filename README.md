# 🐳 DOCKTERM V2

**Dockterm** è un'alternativa leggera, veloce e interamente basata su terminale a Docker Desktop. Gestisci i tuoi container, immagini, volumi e reti con la velocità della tastiera.

![Dockterm UI](https://via.placeholder.com/800x400?text=Dockterm+V2+TUI) <!-- Se carichi uno screenshot, metti il link qui -->

## ✨ Caratteristiche Principali

- **Interfaccia Multi-Tab**: Naviga tra Container, Immagini, Volumi, Reti e Progetti Compose.
- **Menu Azioni Rapide**: Premi `Invio` su qualsiasi elemento per vedere cosa puoi farci.
- **Statistiche in Tempo Reale**: Monitora CPU e RAM dei container mentre lavorano.
- **Log Interattivi**: Visualizzazione log a schermo intero con ricerca e scroll fluido.
- **Gestione Compose**: Avvia, ferma e aggiorna i tuoi progetti `docker-compose`.
- **Flicker-Free**: Rendering ottimizzato per evitare sfarfallii del terminale.
- **Filtro Istantaneo**: Cerca e filtra velocemente in ogni lista.

---

## 🚀 Installazione Rapida

Per installare Dockterm e averlo disponibile come comando globale:

```bash
git clone https://github.com/TUO_USERNAME/dockterm_v2.git
cd dockterm_v2
./install.sh
```

Dopo l'installazione, riavvia il terminale o scrivi `source ~/.bashrc` (o `~/.zshrc`).

---

## 🗑️ Disinstallazione

Se desideri rimuovere Dockterm dal tuo sistema:

```bash
./uninstall.sh
```

---

## ⌨️ Come Usarlo (Keybindings)

### Navigazione Generale
| Tasto | Azione |
|-------|--------|
| `F1` - `F5` | Cambia Tab (Containers, Images, Vol, Net, Compose) |
| `↑` / `↓` | Naviga nella lista |
| `Invio` | **Apri Menu Azioni** (Consigliato) |
| `/` | Attiva Filtro / Ricerca |
| `Esc` | Pulisce filtro o chiude menu |
| `h` o `?` | Mostra aiuto rapido |
| `q` | Esci da Dockterm |

### Scorciatoie Container
| Tasto | Azione |
|-------|--------|
| `s` | Avvia (Start) |
| `t` | Ferma (Stop) |
| `r` | Riavvia (Restart) |
| `z` | Pausa / Riprendi |
| `l` | Visualizza Log (Interattivo) |
| `x` | Apri Shell (`exec /bin/bash`) |
| `n` | Rinomina Container |
| `k` | Commit (Crea immagine da container) |
| `cp` | Copia file nel container |

### Scorciatoie Immagini
| Tasto | Azione |
|-------|--------|
| `R` | Esegui (Run) come nuovo container |
| `p` | Pull / Aggiorna immagine |
| `H` | Visualizza Storia (History) |
| `B` | Build da Dockerfile |
| `S` / `L` | Salva / Carica immagine (.tar) |

---

## 🛠 Azioni Globali
- **Pruning**: Premi `Shift + P` per pulire tutte le risorse Docker inutilizzate (container fermi, immagini orfane, ecc.).
- **Inspect**: Premi `i` su qualsiasi risorsa per vedere la sua configurazione JSON completa.

## 📄 Licenza
Distribuito sotto licenza **MIT**. Vedi il file `LICENSE` per dettagli.
