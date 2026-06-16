---
name: Concessionaria page layout decisions
description: Key design decisions for the /concessionaria Flask page in Tokyo Horizon RP
---

**Layout**: Two-column grid (260px sidebar + main). Sidebar is sticky with category buttons and stats. No horizontal tabs.

**Cards**: "Poster" style — 280px tall, full-bleed background image (object-fit:cover), glass gradient overlay, info at bottom. Emoji fallback when image fails.

**Images**: All car images use `https://gta.fandom.com/wiki/Special:FilePath/<filename>`. Wiki may block hotlinking in some browsers — onerror="this.remove()" handles gracefully.

**Colors**: --red #e63946, --pink #ff6b9d, --sakura #ffb7c5, --gold #f4d03f on dark bg.

**Why**: User wanted the original sakura/lantern Japanese aesthetic but with a completely different layout from a competitor server that used the same horizontal-tab + vertical-card grid pattern.
