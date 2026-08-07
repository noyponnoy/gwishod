#!/usr/bin/env python3
"""
Patch: mobile responsiveness + performance + overlay fixes
Run: python3 fix_mobile.py
"""
import os, re

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "src")
STYLE = os.path.join(BASE, "styles")
COMP = os.path.join(BASE, "components")

def patch(path, old, new):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if old not in content:
        print(f"  [SKIP] Pattern not found in {os.path.basename(path)}")
        return False
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] {os.path.basename(path)}")
    return True

# ── 1. theme.css: mobile performance ─────────────────────────
print("\n=== theme.css ===")
p = os.path.join(STYLE, "theme.css")
patch(p,
  "/* Фокус-кольцо для доступности */\n:focus-visible {\n  outline: 2px solid var(--accent-400);\n  outline-offset: 2px;\n  border-radius: 4px;\n}",
  """/* Фокус-кольцо для доступности */
:focus-visible {
  outline: 2px solid var(--accent-400);
  outline-offset: 2px;
  border-radius: 4px;
}

/* ── Mobile performance: disable heavy effects ────────────── */
@media (max-width: 1024px) {
  body { background-attachment: scroll; }

  .sidebar,
  .topbar,
  .bottom-nav,
  .card,
  .stat-card,
  .dashboard-hero,
  .dashboard-health-card,
  .server-tile,
  .modal {
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
  }

  .app-shell::before { display: none; }

  .stat-card:hover,
  .server-tile:hover {
    transform: none !important;
  }

  .pulse-dot::after { animation: none !important; opacity: 0; }
  .spinner { animation-duration: 0.9s !important; }
}"""
)

# ── 2. layout.css: sidebar + overlay + mobile ─────────────────
print("\n=== layout.css ===")
p = os.path.join(STYLE, "layout.css")

# 2a. Sidebar z-index fix on mobile
patch(p,
  """/* ── Mobile sidebar drawer ───────────────────────────────────── */
.mobile-overlay {
  display: none;
  position: fixed; inset: 0;
  background: var(--bg-overlay);
  z-index: 200;
  animation: fadeIn 160ms ease;
}

/* ── Адаптивность ────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    left: 0; top: 0;
    transform: translateX(-100%);
    box-shadow: var(--shadow-xl);
  }
  .sidebar.open { transform: translateX(0); }
  .mobile-overlay.show { display: block; }
}""",
  """/* ── Mobile sidebar drawer ───────────────────────────────────── */
.mobile-overlay {
  display: none;
  position: fixed; inset: 0;
  background: var(--bg-overlay);
  z-index: 250;
  animation: fadeIn 160ms ease;
  -webkit-tap-highlight-color: transparent;
}

/* ── Адаптивность ────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    left: 0; top: 0;
    transform: translateX(-100%);
    box-shadow: var(--shadow-xl);
    z-index: 300;
    will-change: transform;
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .sidebar.open { transform: translateX(0); }
  .mobile-overlay.show { display: block; }
}"""
)

# 2b. Add bottom nav touch-action
patch(p,
  """  z-index: 100;
  padding-bottom: env(safe-area-inset-bottom);
}""",
  """  z-index: 100;
  padding-bottom: env(safe-area-inset-bottom);
  touch-action: manipulation;
}""",
)

# ── 3. components.css: modal + mobile touch ───────────────────
print("\n=== components.css ===")
p = os.path.join(STYLE, "components.css")

# 3a. Modal overscroll-behavior
patch(p,
  """  animation: slideUp 200ms cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(22px) saturate(1.25);
  -webkit-backdrop-filter: blur(22px) saturate(1.25);
}
.modal-lg { max-width: 760px; }""",
  """  animation: slideUp 200ms cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(22px) saturate(1.25);
  -webkit-backdrop-filter: blur(22px) saturate(1.25);
  overscroll-behavior: contain;
}
.modal-lg { max-width: 760px; }""",
)

# 3b. Touch action on modal-overlay
patch(p,
  """  z-index: 1000;
  padding: 16px;
  animation: fadeIn 160ms ease;
}""",
  """  z-index: 1000;
  padding: 16px;
  animation: fadeIn 160ms ease;
  touch-action: manipulation;
}""",
)

# 3c. Add mobile touch overrides at end of file
if "/* ── Mobile touch & performance overrides" not in open(p).read():
    with open(p, "a", encoding="utf-8") as f:
        f.write("""

/* ── Mobile touch & performance overrides ─────────────────── */
@media (max-width: 1024px) {
  .btn,
  .nav-item,
  .bn-item,
  .tab,
  .page-btn,
  .switch-slider,
  input[type="checkbox"],
  a {
    -webkit-tap-highlight-color: transparent;
  }

  .btn { min-height: 44px; min-width: 44px; }
  .btn-sm { min-height: 36px; }
  .btn-icon { min-width: 44px; }
  .btn-icon.btn-sm { min-width: 36px; }

  .switch {
    min-width: 50px;
    min-height: 28px;
  }

  .modal-overlay {
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    background: rgba(8, 11, 24, 0.65);
  }

  .modal {
    max-width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
  }

  .tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scroll-snap-type: x proximity;
  }
  .tab { scroll-snap-align: start; min-height: 44px; }

  .toast-container {
    left: 8px;
    right: 8px;
    bottom: calc(var(--bottomnav-h) + 12px);
  }

  .page-content {
    -webkit-overflow-scrolling: touch;
  }

  .table-wrap {
    -webkit-overflow-scrolling: touch;
  }
}
""")
    print("  [OK] Added mobile touch overrides")
else:
    print("  [SKIP] Mobile touch overrides already present")

# ── 4. Modal.tsx: fix overflow on mobile ──────────────────────
print("\n=== Modal.tsx ===")
p = os.path.join(COMP, "Modal.tsx")
patch(p,
  """    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };""",
  """    const prev = document.body.style.overflow;
    const prevHtml = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
      document.documentElement.style.overflow = prevHtml;
    };""",
)

# ── 5. Layout.tsx: swipe-to-close sidebar ─────────────────────
print("\n=== Layout.tsx ===")
p = os.path.join(COMP, "Layout.tsx")

# 5a. Add useRef import
patch(p,
  "import { useEffect } from 'react';",
  "import { useEffect, useRef } from 'react';",
)

# 5b. Add swipe-to-close
patch(p,
  "  // Закрытие drawer при смене роута.\n  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);",
  """  // Закрытие drawer при смене роута.
  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  // Swipe-to-close sidebar
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  useEffect(() => {
    if (!sidebarOpen) return;
    const onStart = (e: TouchEvent) => {
      touchStartX.current = e.touches[0].clientX;
      touchStartY.current = e.touches[0].clientY;
    };
    const onEnd = (e: TouchEvent) => {
      const dx = e.changedTouches[0].clientX - touchStartX.current;
      const dy = Math.abs(e.changedTouches[0].clientY - touchStartY.current);
      if (dx < -60 && dy < 80) setSidebarOpen(false);
    };
    document.addEventListener('touchstart', onStart, { passive: true });
    document.addEventListener('touchend', onEnd, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onStart);
      document.removeEventListener('touchend', onEnd);
    };
  }, [sidebarOpen]);""",
)

# ── 6. Dashboard.tsx: slower polling ──────────────────────────
print("\n=== Dashboard.tsx ===")
p = os.path.join(BASE, "pages", "Dashboard.tsx")
patch(p, "setInterval(loadMain, 5000)", "setInterval(loadMain, 15000)")

print("\n=== Done! ===")
print("Now rebuild the frontend:")
print("  cd panel/frontend && npm run build")
