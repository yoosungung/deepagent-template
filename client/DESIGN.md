# client/DESIGN.md (Frontend Design & Execution)

## Directory Structure

```txt
client/
├── src/
│   ├── components/
│   │   ├── ChatView.tsx      # Multi-agent interaction (SSE Stream / Thread)
│   │   └── AdminView.tsx     # Postgres VFS file tree explorer and code editor
│   ├── App.tsx               # Main Dashboard combining views
│   ├── main.tsx              # React Entrypoint
│   └── index.css             # Premium CSS variables and styles
├── package.json              # Client npm dependencies
├── vite.config.ts            # Vite proxy definitions
├── tailwind.config.js        # Tailwind settings
├── index.html                # Entry HTML (Google Fonts Outfit/Inter)
└── DESIGN.md                 # This file
```

---

## Design System & Theme

We adopt a highly premium Dark-themed Glassmorphism aesthetic:
- **Base Background**: `#0b0c10` (Midnight Black)
- **Secondary Card Background**: `rgba(31, 38, 52, 0.4)` with `backdrop-filter: blur(12px)`
- **Accent Details**: HSL cyan and electric violet details (`#1f2833`, `#66fcf1`, `#45f3ff`)
- **Typography**:
  - Headings and dynamic UI elements: `Outfit`
  - Body text, logs, and inputs: `Inter`
- **Layout Mechanics**:
  - `100dvh` for full viewports to adapt smoothly on mobile and desktops.
  - `scrollbar-gutter: stable` and `overscroll-behavior: contain` for chat text boxes and file tree wrappers.
  - `overflow-y: auto` to prevent window-level scrollbar flickering.

---

## Commands

### Dependencies Installation
```bash
npm install
```

### Run Client (Development)
```bash
npm run dev
```

### Build Production Bundle
```bash
npm run build
```
