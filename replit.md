# Tokyo Horizon RP

A Discord bot and API server for managing the Tokyo Horizon GTA V roleplay community — economy, heists (furti), inventory, and vehicle theft systems.

## Run & Operate

- **Run button** starts the `Tokyo Horizon Bot` workflow (`python3 bot.py`)
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)

## Required Secrets

- `DISCORD_TOKEN` — Discord bot token (from Discord Developer Portal → Bot → Token)
- `DATABASE_URL` — Postgres connection string (auto-provisioned by Replit)

## Stack

- **Bot:** Python 3.11, discord.py 2.x, Flask (keep-alive server on port 3000)
- **API:** Node.js 24, Express 5, TypeScript 5.9
- **DB:** PostgreSQL + Drizzle ORM
- **Monorepo:** pnpm workspaces

## Where things live

- `bot.py` — Discord bot (main entry point)
- `dati_bot.json` — local JSON persistence for economy, cooldowns, inventory
- `artifacts/api-server/` — Express API server
- `lib/db/` — Drizzle ORM schema and DB client
- `lib/api-spec/` — OpenAPI spec + Orval codegen config
- `lib/api-zod/` — generated Zod schemas
- `lib/api-client-react/` — generated React query hooks
- `artifacts/mockup-sandbox/` — Vite/React UI component previewer

## Architecture decisions

- Bot data is persisted locally in `dati_bot.json` (economy, cooldowns, inventory, pending vehicle orders)
- The Flask keep-alive server runs on port 3000 inside the bot process to satisfy Replit's port-binding requirement
- Discord token is stored in Replit Secrets as `DISCORD_TOKEN` — never hardcoded
- API server requires `PORT` env var (set to 5000) and `DATABASE_URL` (auto-provisioned)

## Product

- `/furto villa`, `/furto casa`, `/furto macchina` — heist minigames with cooldowns, loot tiers, and staff notifications
- `/economia`, `/deposita`, `/preleva` — player wallet and bank management
- `/negozio`, `/compra` — in-game item shop (crowbar, lockpick)
- `/inventario` — view player inventory
- `/setcanale` — staff command to configure the heist notification channel

## User preferences

- **Termina sempre con una domanda** — alla fine di ogni risposta usa il tool `user_query` per fare una domanda all'utente, così può continuare a scrivere anche dopo la scadenza della prova gratuita.

## Gotchas

- Always restart the `Tokyo Horizon Bot` workflow after changing `bot.py`
- `dati_bot.json` is the source of truth for live economy/inventory data — don't delete it
- The bot syncs slash commands globally on startup (`await self.tree.sync()`) which can take up to 1 hour to propagate in Discord

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
