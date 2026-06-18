import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os
import json
import time
import signal
import sys
import io
from datetime import date
import aiohttp
from flask import Flask, render_template
from threading import Thread

# Mini-server keep-alive (porta 5000)
app = Flask(__name__)

@app.route('/')
def home():
    return 'Tokyo Horizon RP — Online', 200

@app.route('/concessionaria')
def concessionaria():
    return render_template('concessionaria.html')

_FLASK_PORT = int(os.environ.get('PORT', 10000))

def run_flask():
    while True:
        try:
            os.system(f"fuser -k {_FLASK_PORT}/tcp 2>/dev/null || true")
            time.sleep(1)
            app.run(host='0.0.0.0', port=_FLASK_PORT, use_reloader=False, threaded=True)
        except Exception as e:
            print(f"[FLASK] Server crashato: {e} — riavvio tra 5s...")
            time.sleep(5)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

async def self_ping_loop():
    """Pinga il server Flask ogni 4 minuti per tenerlo attivo."""
    await asyncio.sleep(30)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f'http://127.0.0.1:{_FLASK_PORT}/', timeout=aiohttp.ClientTimeout(total=10)) as r:
                    print(f"[PING] Server attivo — status {r.status}")
            except Exception as e:
                print(f"[PING] Errore ping: {e}")
            await asyncio.sleep(240)

# Shutdown pulito su SIGTERM (Replit invia SIGTERM per riavviare il workflow)
def _handle_sigterm(signum, frame):
    print("[BOT] SIGTERM ricevuto — uscita pulita.")
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)

_DEV_DOMAIN = os.environ.get("REPLIT_DEV_DOMAIN", "")
_CONCESSIONARIA_URL = f"https://{_DEV_DOMAIN}/concessionaria" if _DEV_DOMAIN else "https://tinyurl.com/284wjmmx"
print(f"[CONCESSIONARIA] URL configurato: {_CONCESSIONARIA_URL}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class HorizonTree(app_commands.CommandTree):
    """CommandTree personalizzato che filtra slash command pre-boot prima di eseguirli."""
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.type == discord.InteractionType.application_command:
            # Scarta solo interazioni create PRIMA che il bot fosse pronto (ghost interactions)
            # Non usiamo un check sull'età: Discord gestisce il timeout di 3s con un 404,
            # che i singoli command handler catturano già con except discord.NotFound.
            if bot.ready_time and interaction.created_at < bot.ready_time:
                cmd = getattr(interaction.command, 'name', '?')
                age = (discord.utils.utcnow() - interaction.created_at).total_seconds()
                print(f"[SKIP] Slash command pre-boot ({age:.1f}s): /{cmd} — ignorato.")
                try:
                    await interaction.response.send_message(
                        "⚡ Il bot si è appena riavviato — riprova il comando!",
                        ephemeral=True
                    )
                except Exception:
                    pass
                return False
        return True


class TokyoHorizonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, tree_cls=HorizonTree)
        self.aiohttp_session: aiohttp.ClientSession = None
        self.ready_time: "discord.utils.datetime" = None  # Impostato in on_ready

    async def setup_hook(self):
        self.aiohttp_session = aiohttp.ClientSession()
        self.add_view(VeicoloButtons())
        self.add_view(RichiestaPGView())
        self.add_view(CartaIdentitaView())
        self.add_view(ChiudiTicketView())
        self.add_view(TicketPannelloView())
        # Re-registra le view di approvazione per gli ordini in_attesa sopravvissuti al restart
        for uid, ordine in list(ordini_pendenti_macchina.items()):
            if ordine.get("in_attesa"):
                view = ApprovazioneCosegnaView(
                    autore_id=uid,
                    origin_ch_id=ordine.get("origin_ch_id"),
                )
                self.add_view(view)
                print(f"[VEICOLO] Vista approvazione ri-registrata per uid={uid} modello={ordine.get('modello', '?')}")
        # Re-registra le view di revisione PG sopravvissute al restart
        for uid, richiesta in list(richieste_pg_pendenti.items()):
            if not richiesta.get("processata"):
                self.add_view(RevisionePGView(autore_id=uid))
                print(f"[PG] Vista revisione ri-registrata per uid={uid} nome={richiesta.get('nome', '?')}")
        # Sync globale — una sola volta all'avvio
        await self.tree.sync()
        print("Tokyo Horizon Bot: setup_hook completato — comandi globali sincronizzati.")
        # Self-ping per tenere il server Flask attivo
        asyncio.create_task(self_ping_loop())

    async def close(self):
        if self.aiohttp_session and not self.aiohttp_session.closed:
            await self.aiohttp_session.close()
        await super().close()

    async def on_ready(self):
        bot.ready_time = discord.utils.utcnow()  # Timestamp da cui accettare interazioni
        print(f"✅ {self.user} è online e pronto!")
        print(f"   Connesso a {len(self.guilds)} server/i")
        # Rimuovi comandi guild-specifici residui (causano duplicati con i globali)
        for guild in self.guilds:
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)
        print("   Comandi guild-specifici rimossi — nessun duplicato.")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Tokyo Horizon RP 🗼"
            )
        )
        # Riprendi rapine pendenti sopravvissute al riavvio
        # (on_ready può essere chiamato più volte su riconnessione — salta se già in corso)
        for uid, info in list(rapine_pendenti_bancomat.items()):
            if uid in _bancomat_in_corso:
                print(f"[BANCOMAT] uid={uid} già in elaborazione — skip duplicato on_ready.")
                continue
            accepted_at = info.get("accepted_at", 0)
            elapsed = time.time() - accepted_at
            remaining = max(0.0, 240.0 - elapsed)
            print(f"[BANCOMAT] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            task = asyncio.create_task(accredita_bancomat(uid, remaining))
            _bancomat_tasks[uid] = task
        for uid, info in list(rapine_pendenti_minimarket.items()):
            if uid in _minimarket_in_corso:
                print(f"[MINIMARKET] uid={uid} già in elaborazione — skip duplicato on_ready.")
                continue
            accepted_at = info.get("accepted_at", 0)
            elapsed = time.time() - accepted_at
            remaining = max(0.0, 240.0 - elapsed)
            print(f"[MINIMARKET] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            task = asyncio.create_task(accredita_minimarket(uid, remaining))
            _minimarket_tasks[uid] = task
        for uid, info in list(rapine_pendenti_armeria.items()):
            if uid in _armeria_in_corso:
                continue
            elapsed = time.time() - info.get("accepted_at", 0)
            remaining = max(0.0, 360.0 - elapsed)
            print(f"[ARMERIA] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            _armeria_tasks[uid] = asyncio.create_task(accredita_armeria(uid, remaining))
        for uid, info in list(rapine_pendenti_fleeca.items()):
            if uid in _fleeca_in_corso:
                continue
            elapsed = time.time() - info.get("accepted_at", 0)
            remaining = max(0.0, 420.0 - elapsed)
            print(f"[FLEECA] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            _fleeca_tasks[uid] = asyncio.create_task(accredita_fleeca(uid, remaining))
        for uid, info in list(rapine_pendenti_gioielleria.items()):
            if uid in _gioielleria_in_corso:
                continue
            elapsed = time.time() - info.get("accepted_at", 0)
            remaining = max(0.0, 540.0 - elapsed)
            print(f"[GIOIELLERIA] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            _gioielleria_tasks[uid] = asyncio.create_task(accredita_gioielleria(uid, remaining))
        for uid, info in list(rapine_pendenti_mazebank.items()):
            if uid in _mazebank_in_corso:
                continue
            elapsed = time.time() - info.get("accepted_at", 0)
            remaining = max(0.0, 720.0 - elapsed)
            print(f"[MAZEBANK] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            _mazebank_tasks[uid] = asyncio.create_task(accredita_mazebank(uid, remaining))
        for uid, info in list(rapine_pendenti_meccanico.items()):
            if uid in _meccanico_in_corso:
                continue
            elapsed = time.time() - info.get("accepted_at", 0)
            remaining = max(0.0, 300.0 - elapsed)
            print(f"[MECCANICO] Ripresa rapina pendente uid={uid}, rimanenti={remaining:.0f}s")
            _meccanico_tasks[uid] = asyncio.create_task(accredita_meccanico(uid, remaining))

bot = TokyoHorizonBot()

RUOLO_BENVENUTO = 1516070200494002276  # Ruolo assegnato automaticamente a ogni nuovo membro

@bot.event
async def on_member_join(member: discord.Member):
    role = member.guild.get_role(RUOLO_BENVENUTO)
    if role:
        try:
            await member.add_roles(role, reason="Assegnazione automatica ruolo nuovo membro")
            print(f"[JOIN] Ruolo '{role.name}' assegnato a {member} (id={member.id})")
        except discord.Forbidden:
            print(f"[JOIN] ❌ Permessi insufficienti per assegnare il ruolo a {member}")
        except Exception as e:
            print(f"[JOIN] ❌ Errore assegnazione ruolo a {member}: {e}")
    else:
        print(f"[JOIN] ⚠️ Ruolo {RUOLO_BENVENUTO} non trovato nel server")

# =============================================================================
# POSIZIONI — Ville e Case
# =============================================================================

_VILLE_ALL = [
    {"nome": "Villa #1",  "esterno": "attached_assets/IMG_1326_1781366502000.png",  "rarità": "🔴 Leggendaria", "loot_tier": "leggendaria"},
    {"nome": "Villa #2",  "esterno": "attached_assets/IMG_1329_1781366502000.png",  "rarità": "🔴 Leggendaria", "loot_tier": "leggendaria"},
    {"nome": "Villa #3",  "esterno": "attached_assets/IMG_1320_1781366502000.png",  "rarità": "🔴 Leggendaria", "loot_tier": "leggendaria"},
    {"nome": "Villa #4",  "esterno": "attached_assets/IMG_1334_1781366502001.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #5",  "esterno": "attached_assets/IMG_1339_1781366502001.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #6",  "esterno": "attached_assets/IMG_1349_1781366502001.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #7",  "esterno": "attached_assets/IMG_1351_1781366502001.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #8",  "esterno": "attached_assets/IMG_1424_1781366502001.jpeg", "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #9",  "esterno": "attached_assets/IMG_1419_1781366502001.png",  "rarità": "🟣 Epica",       "loot_tier": "epica"},
    {"nome": "Villa #10", "esterno": "attached_assets/IMG_1416_1781366502001.png",  "rarità": "🔴 Leggendaria", "loot_tier": "leggendaria"},
    {"nome": "Villa #11", "esterno": "attached_assets/IMG_1413_1781366502001.png",  "rarità": "🟣 Epica",       "loot_tier": "epica"},
    {"nome": "Villa #12", "esterno": "attached_assets/IMG_1410_1781366502001.png",  "rarità": "🟣 Epica",       "loot_tier": "epica"},
    {"nome": "Villa #13", "esterno": "attached_assets/IMG_1407_1781366502001.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #14", "esterno": "attached_assets/IMG_1404_1781366502001.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #15", "esterno": "attached_assets/IMG_1401_1781366514831.png",  "rarità": "🔴 Leggendaria", "loot_tier": "leggendaria"},
    {"nome": "Villa #16", "esterno": "attached_assets/IMG_1395_1781366551705.png",  "rarità": "🟠 Rara",        "loot_tier": "rara"},
    {"nome": "Villa #17", "esterno": "attached_assets/IMG_1398_1781366590844.png",  "rarità": "🟣 Epica",       "loot_tier": "epica"},
    {"nome": "Villa #18", "esterno": "attached_assets/IMG_1346_1781366641199.png",  "rarità": "🔴 Leggendaria", "loot_tier": "leggendaria"},
]
VILLE = [v for v in _VILLE_ALL if v.get("esterno") and os.path.exists(v["esterno"])]
print(f"[VILLE] {len(VILLE)}/{len(_VILLE_ALL)} ville caricate (con immagine).")

CASE = [
    {
        "nome": "Appartamento Standard #1",
        "mappa": None,
        "esterno": None,
    },
]

# =============================================================================
# DESTINAZIONI CONSEGNA VEICOLI
# =============================================================================
DESTINAZIONI_MACCHINA = [
    {"nome": "Sfasciacarrozze di Sandy Shores (Desert)",         "foto": None},
    {"nome": "Discarica Centrale di South Los Santos",           "foto": None},
    {"nome": "Molo di Carico dei Container (Porto di LS)",       "foto": None},
    {"nome": "Chop Shop clandestino di Paleto Bay",              "foto": None},
    {"nome": "Garage Segreto a El Burro Heights",                "foto": None},
    {"nome": "Rimessa Industriale di Cypress Flats",             "foto": None},
    {"nome": "Officina Meccanica di Harmony (Route 68)",         "foto": None},
    {"nome": "Parcheggio Sotterraneo Clienti Privati (Richman)", "foto": None},
    {"nome": "Hangar dell'Esportatore a Grapeseed",              "foto": None},
    {"nome": "Pontile di Contrabbando a Chumash",                "foto": None},
]

# =============================================================================
# OGGETTI CON RARITÀ
# =============================================================================

LOOT_VILLA = {
    "rara": [
        {"nome": "💵 Contanti in Cassaforte",    "valore": 20000, "rarità": 10},
        {"nome": "💍 Orologio di Lusso",          "valore": 25000, "rarità": 6},
        {"nome": "📿 Bracciale d'Oro",            "valore": 30000, "rarità": 3},
    ],
    "epica": [
        {"nome": "🖼️ Quadro d'Autore",           "valore": 30000, "rarità": 10},
        {"nome": "📿 Collana di Smeraldi",        "valore": 35000, "rarità": 6},
        {"nome": "👑 Lingotto d'Oro Massiccio",   "valore": 40000, "rarità": 3},
    ],
    "leggendaria": [
        {"nome": "📿 Collana di Smeraldi",        "valore": 35000, "rarità": 10},
        {"nome": "👑 Lingotto d'Oro Massiccio",   "valore": 40000, "rarità": 5},
        {"nome": "💎 Diamante Purissimo",          "valore": 45000, "rarità": 2},
    ],
}

CONFIGURAZIONE_INGRESSI = {
    "rara": [
        {"chiave": "davanti",  "label": "Ingresso principale",        "descr": "dall'ingresso principale",          "emoji": "🚪", "style": discord.ButtonStyle.danger,    "rischio": 30},
        {"chiave": "dietro",   "label": "Entrata secondaria (retro)", "descr": "dall'entrata secondaria sul retro", "emoji": "🔙", "style": discord.ButtonStyle.secondary, "rischio": 30},
        {"chiave": "finestra", "label": "Finestra di lato",           "descr": "dalla finestra di lato",            "emoji": "🪟", "style": discord.ButtonStyle.primary,   "rischio": 30},
        {"chiave": "garage",   "label": "Dal garage",                 "descr": "dal garage",                        "emoji": "🚗", "style": discord.ButtonStyle.secondary, "rischio": 30},
    ],
    "epica": [
        {"chiave": "davanti",  "label": "Ingresso principale",        "descr": "dall'ingresso principale",          "emoji": "🚪", "style": discord.ButtonStyle.danger,    "rischio": 40},
        {"chiave": "dietro",   "label": "Entrata secondaria (retro)", "descr": "dall'entrata secondaria sul retro", "emoji": "🔙", "style": discord.ButtonStyle.secondary, "rischio": 40},
        {"chiave": "finestra", "label": "Finestra di lato",           "descr": "dalla finestra di lato",            "emoji": "🪟", "style": discord.ButtonStyle.primary,   "rischio": 40},
        {"chiave": "garage",   "label": "Dal garage",                 "descr": "dal garage",                        "emoji": "🚗", "style": discord.ButtonStyle.secondary, "rischio": 40},
    ],
    "leggendaria": [
        {"chiave": "davanti", "label": "Ingresso principale",        "descr": "dall'ingresso principale",          "emoji": "🚪", "style": discord.ButtonStyle.danger,    "rischio": 90},
        {"chiave": "dietro",  "label": "Entrata secondaria (retro)", "descr": "dall'entrata secondaria sul retro", "emoji": "🔙", "style": discord.ButtonStyle.secondary, "rischio": 40},
        {"chiave": "tetto",   "label": "Dal tetto",                  "descr": "dal tetto",                         "emoji": "🏠", "style": discord.ButtonStyle.primary,   "rischio": 25},
        {"chiave": "garage",  "label": "Dal garage",                 "descr": "dal garage",                        "emoji": "🚗", "style": discord.ButtonStyle.secondary, "rischio": 60},
    ],
}

OGGETTI_CASA = [
    {"nome": "📿 Scatola di Gioielli d'Argento", "valore": 10000, "rarità": 4},
    {"nome": "🏺 Vaso di Porcellana Pregiata",    "valore": 8000,  "rarità": 8},
    {"nome": "💵 Contanti nascosti nel cassetto",  "valore": 6000,  "rarità": 18},
    {"nome": "💻 Computer Portatile Gaming",       "valore": 5000,  "rarità": 30},
    {"nome": "📺 Televisore Led 4K",               "valore": 4000,  "rarità": 42},
]

def classifica_macchina(modello: str):
    m = modello.lower()
    alta = [
        "grotti", "cheetah", "itali", "turismo r", "pegassi", "zentorno", "osiris",
        "tempesta", "torero", "vacca", "truffade", "adder", "thrax", "nero custom",
        "nero", "t20", "fmj", "pariah", "überflöd", "overflöd", "entity", "tyrant",
        "krieger", "s80", "deveste", "cyclone", "pr4", "taipan", "emerus",
        "vigilante", "scramjet", "xa-21", "vagner", "revolter", "pfister 811",
        "811", "le7b", "autarch", "shinsen", "formula", "dr1", "br8", "r88",
        "etr1", "sc1", "ra4", "p1", "im-t", "neo", "x80", "dewbauchee",
        "specter custom", "growler", "visione", "reaper", "infernus classic",
        "massacro", "900r",
    ]
    media = [
        "sultan rs", "sultan", "elegy rh8", "elegy retro", "elegy", "kuruma",
        "rapid gt", "comet", "banshee 900r", "banshee", "buffalo", "coquette",
        "mamba", "jester", "stirling", "carbonizzare", "alpha", "sentinel xs",
        "sentinel", "dubsta", "felon gt", "felon", "exemplar", "zion cabrio",
        "zion", "oracle xs", "oracle", "schafter v12", "schafter lts", "schafter",
        "sabre turbo custom", "sabre turbo", "phoenix", "ruiner 2000", "ruiner",
        "gauntlet hellfire", "gauntlet", "dominator gtx", "dominator asc",
        "dominator", "nightshade", "faction custom", "faction", "tornado custom",
        "voodoo custom", "voodoo", "buccaneer custom", "buccaneer", "tornado",
        "camaro", "tampa", "zr380", "imponte", "ocelot", "recepter", "wraith",
        "specter", "bravado", "vapid", "issi sport", "gb200", "seven-70",
        "tyrus", "le chaud", "lynx", "locust", "neon", "furia", "outlaw",
        "drafter", "italirsx", "euros", "cypher", "vectre", "previon", "calico",
        "jester4", "sugoi", "imorgon",
    ]
    for k in alta:
        if k in m: return "🔴 Alta", 30000, discord.Color.gold()
    for k in media:
        if k in m: return "🟡 Media", 20000, discord.Color.blue()
    return "⚪ Bassa", 10000, discord.Color.light_gray()

def etichetta_rarità(peso: int) -> str:
    if peso <= 2:   return "✨ Leggendario"
    if peso <= 6:   return "💜 Molto Raro"
    if peso <= 12:  return "🟠 Raro"
    if peso <= 25:  return "🟡 Non Comune"
    return "🔴 Comune"

def campiona_con_rarità(pool: list, k: int) -> list:
    disponibili = list(pool)
    pesi = [o["rarità"] for o in disponibili]
    scelti = []
    for _ in range(k):
        if not disponibili: break
        [scelto] = random.choices(disponibili, weights=pesi, k=1)
        idx = disponibili.index(scelto)
        scelti.append(scelto)
        disponibili.pop(idx)
        pesi.pop(idx)
    return scelti

def costruisci_pool(oggetti_scelti: list, mostra_perc: bool = True) -> tuple[list, str]:
    pesi = [o["rarità"] for o in oggetti_scelti]
    pesi_inv = [round((1 / p) * 100, 2) for p in pesi]
    somma_inv = sum(pesi_inv)
    pool = []
    desc = ""
    for i, ogg in enumerate(oggetti_scelti):
        perc = round((pesi_inv[i] / somma_inv) * 100)
        perc = max(1, perc)
        o = ogg.copy()
        o["percentuale"] = perc
        pool.append(o)
        label = etichetta_rarità(ogg["rarità"])
        if mostra_perc:
            desc += f"• {ogg['nome']} {label} — `{perc}%` (Valore: `{ogg['valore']:,}€`)\n"
        else:
            desc += f"• {ogg['nome']} {label} — Valore: `{ogg['valore']:,}€`\n"
    return pool, desc

# =============================================================================
# SALVATAGGIO PERSISTENTE
# =============================================================================
DATI_FILE = "dati_bot.json"

def carica_dati():
    if os.path.exists(DATI_FILE):
        try:
            with open(DATI_FILE, "r") as f:
                dati = json.load(f)
                cooldown_raw = {int(k): v for k, v in dati.get("furto_cooldown", {}).items()}
                cooldown = {}
                for uid, val in cooldown_raw.items():
                    cooldown[uid] = val if isinstance(val, dict) else {}
                ordini_raw = dati.get("ordini_macchina", {})
                ordini = {int(k): v for k, v in ordini_raw.items()}
                rapine_raw = dati.get("rapine_pendenti", {})
                rapine = {int(k): v for k, v in rapine_raw.items()}
                rapine_mini_raw = dati.get("rapine_pendenti_minimarket", {})
                rapine_mini = {int(k): v for k, v in rapine_mini_raw.items()}
                rapine_armeria      = {int(k): v for k, v in dati.get("rapine_pendenti_armeria", {}).items()}
                rapine_fleeca       = {int(k): v for k, v in dati.get("rapine_pendenti_fleeca", {}).items()}
                rapine_gioielleria  = {int(k): v for k, v in dati.get("rapine_pendenti_gioielleria", {}).items()}
                rapine_mazebank     = {int(k): v for k, v in dati.get("rapine_pendenti_mazebank", {}).items()}
                rapine_meccanico    = {int(k): v for k, v in dati.get("rapine_pendenti_meccanico", {}).items()}
                richieste_pg        = {int(k): v for k, v in dati.get("richieste_pg_pendenti", {}).items()}
                storico_mods        = {int(k): v for k, v in dati.get("storico_modifiche", {}).items()}
                return (
                    {int(k): v for k, v in dati.get("economia", {}).items()},
                    cooldown,
                    {int(k): v for k, v in dati.get("inventario", {}).items()},
                    dati.get("canale_furti_id", None),
                    ordini,
                    rapine,
                    rapine_mini,
                    rapine_armeria,
                    rapine_fleeca,
                    rapine_gioielleria,
                    rapine_mazebank,
                    rapine_meccanico,
                    richieste_pg,
                    dati.get("categoria_ticket_id", None),
                    {int(k): v for k, v in dati.get("veicoli_posseduti", {}).items()},
                    dati.get("canale_meccanico_id", None),
                    storico_mods,
                )
        except Exception as e:
            print(f"[CARICA_DATI] Errore caricamento JSON: {e} — partenza con dati vuoti")
    return {}, {}, {}, None, {}, {}, {}, {}, {}, {}, {}, {}, {}, None, {}, None, {}

def salva_dati():
    tmp = DATI_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({
            "economia":        {str(k): v for k, v in economia.items()},
            "furto_cooldown":  {str(k): v for k, v in furto_cooldown.items()},
            "inventario":      {str(k): v for k, v in inventario.items()},
            "canale_furti_id": canale_furti_id,
            "ordini_macchina": {str(k): v for k, v in ordini_pendenti_macchina.items()},
            "rapine_pendenti":               {str(k): v for k, v in rapine_pendenti_bancomat.items()},
            "rapine_pendenti_minimarket":    {str(k): v for k, v in rapine_pendenti_minimarket.items()},
            "rapine_pendenti_armeria":       {str(k): v for k, v in rapine_pendenti_armeria.items()},
            "rapine_pendenti_fleeca":        {str(k): v for k, v in rapine_pendenti_fleeca.items()},
            "rapine_pendenti_gioielleria":   {str(k): v for k, v in rapine_pendenti_gioielleria.items()},
            "rapine_pendenti_mazebank":      {str(k): v for k, v in rapine_pendenti_mazebank.items()},
            "rapine_pendenti_meccanico":     {str(k): v for k, v in rapine_pendenti_meccanico.items()},
            "richieste_pg_pendenti":         {str(k): v for k, v in richieste_pg_pendenti.items()},
            "categoria_ticket_id":           categoria_ticket_id,
            "veicoli_posseduti":             {str(k): v for k, v in veicoli_posseduti.items()},
            "canale_meccanico_id":           canale_meccanico_id,
            "storico_modifiche":             {str(k): v for k, v in storico_modifiche.items()},
        }, f, indent=2)
    os.replace(tmp, DATI_FILE)

economia, furto_cooldown, inventario, canale_furti_id, ordini_pendenti_macchina, rapine_pendenti_bancomat, rapine_pendenti_minimarket, rapine_pendenti_armeria, rapine_pendenti_fleeca, rapine_pendenti_gioielleria, rapine_pendenti_mazebank, rapine_pendenti_meccanico, richieste_pg_pendenti, categoria_ticket_id, veicoli_posseduti, canale_meccanico_id, storico_modifiche = carica_dati()

def get_balance(user_id):
    if user_id not in economia:
        economia[user_id] = {"portafoglio": 0, "banca": 5000}
    return economia[user_id]

def get_inventario(user_id):
    if user_id not in inventario:
        inventario[user_id] = {}
    return inventario[user_id]

NEGOZIO = {
    "Piede di Porco":              {"prezzo": 1000,  "emoji": "🪓",  "descrizione": "Forza porte e finestre. Usabile anche per il Colpo al Minimarket. Indispensabile per bancomat, case e ville."},
    "Cacciavite":                  {"prezzo": 1250,  "emoji": "🪛",  "descrizione": "Forza la cassa dei minimarket. Indispensabile per il Colpo al Minimarket (in alternativa al Piede di Porco)."},
    "Grimaldello":                 {"prezzo": 1500,  "emoji": "🗝️", "descrizione": "Scassina serrature di alta sicurezza. Fondamentale per colpi in ville, operazioni epiche e leggendarie."},
    "Torcia":                      {"prezzo": 2000,  "emoji": "🔦",  "descrizione": "Illumina gli ambienti bui. Obbligatoria per il furto in casa (insieme al Piede di Porco)."},
    "Sistema di Hacking":          {"prezzo": 4000,  "emoji": "💻",  "descrizione": "Disabilita sistemi di allarme e telecamere base. Obbligatorio per ogni furto in villa (insieme a Piede di Porco o Grimaldello)."},
    "Slim Jim":                    {"prezzo": 4000,  "emoji": "🔓",  "descrizione": "Apre le portiere dei veicoli senza chiave. Obbligatorio per il furto di veicoli (insieme al Dispositivo di Hacking Base)."},
    "Dispositivo di Hacking Base": {"prezzo": 4000,  "emoji": "📟",  "descrizione": "Azzera il sistema antifurto del veicolo. Obbligatorio per il furto di veicoli (insieme allo Slim Jim)."},
    "Trapano":                     {"prezzo": 8000,  "emoji": "🔧",  "descrizione": "Perfora le cassette di sicurezza blindate. Obbligatorio per la Rapina alla Banca Fleeca (1x, insieme a 5x Piede di Porco)."},
    "Grimaldello Avanzato":        {"prezzo": 15000, "emoji": "🔐",  "descrizione": "Scassina serrature blindate di alta sicurezza. Obbligatorio per il Grande Colpo alla Maze Bank (min 2 unità)."},
}

MERCATO_NERO = {
    "Simulatore di Impronte Digitali": {"prezzo": 20000, "emoji": "👆", "descrizione": "Bypassa i lettori biometrici delle officine blindate. Obbligatorio per il Furto Officina Meccanica. Non viene consumato — resta in inventario."},
    "Gas Soporifero":                  {"prezzo": 8000,  "emoji": "😴",  "descrizione": "Gas anestetico militare che induce il sonno. Necessario per l'Assalto alla Gioielleria."},
    "Dispositivo di Hacking Medio":    {"prezzo": 15000, "emoji": "📡",  "descrizione": "Hackera sistemi di sorveglianza di livello medio. Obbligatorio per l'Assalto alla Gioielleria."},
    "Lancia Termica":                  {"prezzo": 30000, "emoji": "🔥",  "descrizione": "Brucia serrature e porte blindate. Necessaria per aprire le serrature del caveau della Maze Bank."},
    "Dispositivo di Hacking Avanzato": {"prezzo": 50000, "emoji": "🖥️", "descrizione": "Hackera sistemi digitali di livello militare. Obbligatorio per il Grande Colpo alla Maze Bank."},
    "Trapano Pesante Professionale":   {"prezzo": 50000, "emoji": "⚙️",  "descrizione": "Perfora il caveau della Maze Bank. Obbligatorio per il Grande Colpo."},
}

MERCATO_ARMI = {
    "Pistola": {"prezzo": 10000, "emoji": "🔫", "descrizione": "Arma da fuoco semi-automatica illegale. Obbligatoria per rapine ai bancomat e minimarket. Non viene consumata — resta in inventario."},
}

RUOLI_STAFF = {
    1514817350359060571,  # Founder
    1514817646229717174,  # CEO
    1514818027882024960,  # CO CEO
    1513686043155763280,  # Moderatore
}

RUOLI_APPROVAZIONE_VEICOLO = {
    1514817350359060571,  # Founder
    1514817646229717174,  # CEO
    1514818027882024960,  # CO CEO
    1513686043155763280,  # Moderatore
}


def ha_permessi_staff(interaction: discord.Interaction) -> bool:
    raw = getattr(interaction.user, '_roles', None)
    if raw is not None:
        return any(r_id in RUOLI_STAFF for r_id in raw)
    return False


def ha_permessi_approvazione(interaction: discord.Interaction) -> bool:
    raw = getattr(interaction.user, '_roles', None)
    if raw is not None:
        return any(r_id in RUOLI_APPROVAZIONE_VEICOLO for r_id in raw)
    return False


def ha_permessi_revisione_pg(interaction: discord.Interaction) -> bool:
    raw = getattr(interaction.user, '_roles', None)
    if raw is not None:
        return RUOLO_GESTORE_WL in raw or any(r_id in RUOLI_STAFF for r_id in raw)
    return False


def get_criminal_lock(uid: int) -> float:
    """Ritorna i secondi rimanenti del blocco attività criminale, 0 se libero."""
    lock_until = furto_cooldown.get(uid, {}).get("criminal_lock_until", 0)
    return max(0.0, lock_until - time.time())


def formatta_durata(secondi: float) -> str:
    """Formatta una durata in secondi in una stringa leggibile (giorni, ore, minuti)."""
    s = int(secondi)
    giorni = s // 86400
    ore = (s % 86400) // 3600
    minuti = (s % 3600) // 60
    parti = []
    if giorni: parti.append(f"**{giorni}g**")
    if ore: parti.append(f"**{ore}h**")
    if minuti or not parti: parti.append(f"**{minuti}m**")
    return " ".join(parti)


async def safe_defer(interaction: discord.Interaction, ephemeral: bool = True) -> bool:
    age = (discord.utils.utcnow() - interaction.created_at).total_seconds()
    if age > 2.8:
        cmd = getattr(interaction.command, 'name', '?')
        print(f"[SKIP] /{cmd} scaduto ({age:.1f}s) — ignorato.")
        return False
    try:
        await interaction.response.defer(ephemeral=ephemeral)
        return True
    except discord.NotFound:
        cmd = getattr(interaction.command, 'name', '?')
        print(f"[SKIP] /{cmd} — defer fallito (10062), interazione non più valida.")
        return False


async def invia_notifica_staff(guild_id, embed, view, canale_diretto=None):
    # PRIORITÀ: canale rapine configurato con /setcanale
    if canale_furti_id:
        try:
            canale = bot.get_channel(canale_furti_id) or await bot.fetch_channel(canale_furti_id)
            await canale.send(embed=embed, view=view)
            print(f"[STAFF] ✅ Inviato nel canale rapine #{canale.name}")
            return "canale"
        except discord.Forbidden:
            print("[STAFF] Forbidden nel canale rapine. Provo DM...")
        except discord.NotFound:
            print("[STAFF] Canale rapine non trovato. Provo DM...")
        except Exception as e:
            print(f"[STAFF] Errore canale rapine: {type(e).__name__}: {e}. Provo DM...")

    # FALLBACK: canale dove è stato usato /furto
    if canale_diretto is not None:
        try:
            await canale_diretto.send(embed=embed, view=view)
            print(f"[STAFF] ✅ Inviato nel canale diretto #{canale_diretto.name}")
            return "canale"
        except Exception as e:
            print(f"[STAFF] Errore canale diretto: {type(e).__name__}: {e}. Provo DM...")

    # ULTIMO FALLBACK: DM ai membri staff
    if not guild_id:
        return "fallito"

    guild = bot.get_guild(guild_id)
    if guild is None:
        try:
            guild = await bot.fetch_guild(guild_id)
        except Exception as e:
            print(f"[STAFF] fetch_guild fallito: {e}")
            return "fallito"

    inviati = set()
    try:
        async for member in guild.fetch_members(limit=None):
            if member.bot or member.id in inviati:
                continue
            if any(r.id in RUOLI_APPROVAZIONE_VEICOLO for r in member.roles):
                try:
                    await member.send(embed=embed, view=view)
                    inviati.add(member.id)
                    print(f"[STAFF] DM inviato a {member} ✅")
                except discord.Forbidden:
                    print(f"[STAFF] DM bloccato da {member}")
                except Exception as e:
                    print(f"[STAFF] DM a {member} fallito: {e}")
    except Exception as e:
        print(f"[STAFF] fetch_members fallito: {type(e).__name__}: {e}")

    return "dm" if inviati else "fallito"


# =============================================================================
# INTERFACCE BOTTONI
# =============================================================================

class ScassoButtons(discord.ui.View):
    def __init__(self, autore_id, tipo_furto, pool_oggetti, strumento):
        super().__init__(timeout=600)
        self.autore_id = autore_id
        self.tipo_furto = tipo_furto
        self.pool_oggetti = pool_oggetti
        self.strumento = strumento

    async def avvia_scasso(self, interaction: discord.Interaction, metodo: str):
        if interaction.user.id != self.autore_id:
            await interaction.response.send_message("❌ Questa non è la tua azione!", ephemeral=True)
            return

        inv = get_inventario(self.autore_id)
        if inv.get(self.strumento, 0) <= 0:
            await interaction.response.send_message(f"❌ Non hai più `{self.strumento}` nell'inventario!", ephemeral=True)
            return
        if self.tipo_furto == "casa" and inv.get("Torcia", 0) <= 0:
            await interaction.response.send_message("❌ Non hai più la `Torcia` nell'inventario!", ephemeral=True)
            return
        inv[self.strumento] -= 1
        if inv[self.strumento] == 0:
            del inv[self.strumento]
        if self.tipo_furto == "casa":
            inv["Torcia"] -= 1
            if inv["Torcia"] == 0:
                del inv["Torcia"]
        salva_dati()

        await interaction.response.send_message(
            f"🛠️ Hai iniziato a `{metodo}`. L'azione richiederà **5 minuti** come da regolamento. Rimani in zona!",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await asyncio.sleep(300)

        scelte = list(self.pool_oggetti)
        pesi = [ogg["percentuale"] for ogg in scelte]
        oggetto_estratto = random.choices(scelte, weights=pesi, k=1)[0]
        valore_finale = oggetto_estratto["valore"]

        bilancio = get_balance(self.autore_id)
        bilancio["banca"] += valore_finale
        salva_dati()

        embed_vittoria = discord.Embed(
            title=f"✅ FURTO IN {self.tipo_furto.upper()} COMPLETATO!",
            description=(
                f"Hai ripulito la zona senza lasciare tracce!\n\n"
                f"📦 **Refurtiva:** `{oggetto_estratto['nome']}`\n"
                f"💰 **Valore Guadagnato:** `{valore_finale:,}€` depositati in **Banca**."
            ),
            color=discord.Color.green()
        )
        embed_vittoria.set_footer(text="Tokyo Horizon RP | Sistema Economia")
        await interaction.followup.send(embed=embed_vittoria)

    @discord.ui.button(label="Forza la finestra", style=discord.ButtonStyle.secondary, emoji="🪟")
    async def finestra(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avvia_scasso(interaction, "Forzare la finestra")

    @discord.ui.button(label="Forza la porta", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def porta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avvia_scasso(interaction, "Forzare la porta")


class VillaScassoButtons(discord.ui.View):
    def __init__(self, autore_id, pool_oggetti, strumento, tier="rara"):
        super().__init__(timeout=600)
        self.autore_id = autore_id
        self.pool_oggetti = pool_oggetti
        self.strumento = strumento
        self.usata = False

        ingressi = CONFIGURAZIONE_INGRESSI.get(tier, CONFIGURAZIONE_INGRESSI["rara"])
        for ing in ingressi:
            btn = discord.ui.Button(
                label=ing["label"],
                emoji=ing["emoji"],
                style=ing["style"],
                custom_id=ing["chiave"],
            )
            btn.callback = self._make_callback(ing["descr"], ing["rischio"])
            self.add_item(btn)

    def _make_callback(self, descr, rischio):
        async def callback(interaction: discord.Interaction):
            await self._avvia_ingresso(interaction, descr, rischio)
        return callback

    async def _avvia_ingresso(self, interaction: discord.Interaction, metodo: str, rischio: int):
        if interaction.user.id != self.autore_id:
            await interaction.response.send_message("❌ Questa non è la tua azione!", ephemeral=True)
            return
        if self.usata:
            await interaction.response.send_message("⚠️ Hai già effettuato un tentativo di ingresso!", ephemeral=True)
            return
        self.usata = True

        inv = get_inventario(self.autore_id)
        if inv.get(self.strumento, 0) <= 0:
            await interaction.response.send_message(f"❌ Non hai più `{self.strumento}` nell'inventario!", ephemeral=True)
            self.usata = False
            return
        inv[self.strumento] -= 1
        if inv[self.strumento] == 0:
            del inv[self.strumento]

        if inv.get("Sistema di Hacking", 0) <= 0:
            await interaction.response.send_message("❌ Non hai più il `Sistema di Hacking` nell'inventario!", ephemeral=True)
            self.usata = False
            return
        inv["Sistema di Hacking"] -= 1
        if inv["Sistema di Hacking"] == 0:
            del inv["Sistema di Hacking"]

        salva_dati()

        beccato = random.randint(1, 100) <= rischio

        if beccato:
            bilancio = get_balance(self.autore_id)
            multa = 2000
            bilancio["banca"] = max(0, bilancio["banca"] - multa)
            salva_dati()
            embed_fail = discord.Embed(
                title="🚨 SEI STATO ARRESTATO!",
                description=(
                    f"Hai tentato di entrare **{metodo}** ma le forze dell'ordine ti hanno sorpreso!\n\n"
                    f"💸 **Multa:** `{multa:,}€` scalati dalla **Banca**."
                ),
                color=discord.Color.red()
            )
            embed_fail.set_footer(text="Tokyo Horizon RP | Sistema Furto")
            await interaction.response.send_message(embed=embed_fail, ephemeral=True)
        else:
            scelte = list(self.pool_oggetti)
            pesi = [ogg["percentuale"] for ogg in scelte]
            oggetto_estratto = random.choices(scelte, weights=pesi, k=1)[0]
            valore_finale = oggetto_estratto["valore"]
            bilancio = get_balance(self.autore_id)
            bilancio["banca"] += valore_finale
            salva_dati()
            embed_vittoria = discord.Embed(
                title="✅ FURTO IN VILLA COMPLETATO!",
                description=(
                    f"Sei entrato **{metodo}** e hai ripulito la villa senza lasciare tracce!\n\n"
                    f"📦 **Refurtiva:** `{oggetto_estratto['nome']}`\n"
                    f"💰 **Valore Guadagnato:** `{valore_finale:,}€` depositati in **Banca**."
                ),
                color=discord.Color.green()
            )
            embed_vittoria.set_footer(text="Tokyo Horizon RP | Sistema Furto")
            await interaction.response.send_message(embed=embed_vittoria, ephemeral=True)


class MacchinaModal(discord.ui.Modal, title="🚗 Furto Veicolo — Inserisci il modello"):
    modello = discord.ui.TextInput(
        label="Modello del veicolo",
        placeholder="Es. Grotti Cheetah, Karin Dilettante, Pegassi Zentorno...",
        min_length=3,
        max_length=60,
        required=True,
    )

    def __init__(self, autore_id: int):
        super().__init__()
        self.autore_id = autore_id

    async def on_submit(self, interaction: discord.Interaction):
        # Consuma gli attrezzi richiesti
        inv = get_inventario(self.autore_id)
        if inv.get("Slim Jim", 0) < 1 or inv.get("Dispositivo di Hacking Base", 0) < 1:
            await interaction.response.send_message(
                "❌ Non hai più gli attrezzi richiesti (`Slim Jim` e `Dispositivo di Hacking Base`). Acquistali con `/negozio`.",
                ephemeral=True
            )
            return
        inv["Slim Jim"] -= 1
        if inv["Slim Jim"] == 0:
            del inv["Slim Jim"]
        inv["Dispositivo di Hacking Base"] -= 1
        if inv["Dispositivo di Hacking Base"] == 0:
            del inv["Dispositivo di Hacking Base"]
        salva_dati()

        modello_input = self.modello.value.strip()
        rarita_label, guadagno, colore = classifica_macchina(modello_input)
        dest = random.choice(DESTINAZIONI_MACCHINA)
        emoji_rarita = {"🔴 Alta": "🏎️", "🟡 Media": "🚘", "⚪ Bassa": "🚗"}.get(rarita_label, "🚗")

        embed = discord.Embed(
            title="🚘 Veicolo Agganciato — Ordine di Consegna",
            description=(
                f"Hai agganciato il veicolo tramite la centralina!\n\n"
                f"{emoji_rarita} **Modello:** `{modello_input}`\n"
                f"📊 **Fascia di Rarità:** {rarita_label}\n"
                f"💵 **Compenso:** `{guadagno:,}€` alla consegna\n\n"
                f"📍 **Punto di Consegna:** `{dest['nome']}`\n\n"
                f"⚠️ **REGOLAMENTO:** Hai **10 MINUTI** reali per raggiungere il punto in mappa e premere il tasto verde. Occhio alla Crash-Rule delle FDO!"
            ),
            color=colore
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Furto Veicoli")

        files = []
        embeds = [embed]
        if dest["foto"]:
            ext = dest["foto"].rsplit(".", 1)[-1]
            fname = f"dest_foto.{ext}"
            file_foto = discord.File(dest["foto"], filename=fname)
            files.append(file_foto)
            embed_foto = discord.Embed(description="📍 **Posizione di consegna sulla mappa**", color=colore)
            embed_foto.set_image(url=f"attachment://{fname}")
            embeds.append(embed_foto)

        # Pulisce qualsiasi ordine precedente (anche se in_attesa=True per bug/restart)
        ordini_pendenti_macchina.pop(self.autore_id, None)
        ordini_pendenti_macchina[self.autore_id] = {
            "guadagno":    guadagno,
            "destinazione": dest["nome"],
            "modello":     modello_input,
            "foto_ok":     False,
            "in_attesa":   False,
            "consegnato":  False,
        }
        salva_dati()
        print(f"[ORDINE] Creato ordine autore={self.autore_id} modello={modello_input}")

        view = VeicoloButtons()
        await interaction.response.defer()
        await interaction.followup.send(embeds=embeds, files=files, view=view)


class ApprovazioneCosegnaView(discord.ui.View):
    """
    Vista persistente per l'approvazione delle consegne veicolo.
    - timeout=None: i bottoni rimangono attivi senza limiti di tempo
    - custom_id univoco per utente: sopravvive ai riavvii del bot
    - I dati dell'ordine vengono riletti freschi dal dict in-memoria ad ogni click
    """
    def __init__(self, autore_id: int, origin_ch_id: int = None):
        super().__init__(timeout=None)
        self.autore_id = autore_id
        self.origin_ch_id = origin_ch_id

        btn_approva = discord.ui.Button(
            label="✅ Approva",
            style=discord.ButtonStyle.success,
            custom_id=f"vei:approva:{autore_id}",
        )
        btn_approva.callback = self._approva
        self.add_item(btn_approva)

        btn_rifiuta = discord.ui.Button(
            label="❌ Rifiuta",
            style=discord.ButtonStyle.danger,
            custom_id=f"vei:rifiuta:{autore_id}",
        )
        btn_rifiuta.callback = self._rifiuta
        self.add_item(btn_rifiuta)

    async def _approva(self, interaction: discord.Interaction):
        if not ha_permessi_approvazione(interaction):
            await interaction.response.send_message("❌ Solo lo staff può approvare le consegne.", ephemeral=True)
            return

        ordine = ordini_pendenti_macchina.get(self.autore_id)
        if not ordine or not ordine.get("in_attesa"):
            await interaction.response.send_message("⚠️ Questa consegna è già stata processata o è scaduta.", ephemeral=True)
            return

        guadagno     = ordine.get("guadagno", 0)
        modello      = ordine.get("modello", "?")
        destinazione = ordine.get("destinazione", "?")
        origin_ch_id = ordine.get("origin_ch_id") or self.origin_ch_id

        ordini_pendenti_macchina.pop(self.autore_id, None)
        furto_cooldown.setdefault(self.autore_id, {})["macchina"] = time.time()
        bilancio = get_balance(self.autore_id)
        bilancio["banca"] += guadagno
        salva_dati()

        for child in self.children:
            child.disabled = True

        embed_are = discord.Embed(
            title="✅ CONSEGNA APPROVATA",
            description=(
                f"La consegna del veicolo `{modello}` è stata approvata da {interaction.user.mention}.\n\n"
                f"💰 **Compenso:** `{guadagno:,}€` accreditati in banca al giocatore."
            ),
            color=discord.Color.green()
        )
        embed_are.set_footer(text="Tokyo Horizon RP | Pannello Staff")
        await interaction.response.edit_message(embed=embed_are, view=self)

        embed_rapine = discord.Embed(
            title="🚗 VEICOLO CONSEGNATO — APPROVATO!",
            description=(
                f"<@{self.autore_id}> Lo staff ha verificato e **approvato** la tua consegna!\n\n"
                f"🚘 **Veicolo:** `{modello}`\n"
                f"📍 **Destinazione:** `{destinazione}`\n"
                f"💰 **Compenso:** `{guadagno:,}€` accreditati in **Banca**."
            ),
            color=discord.Color.green()
        )
        embed_rapine.set_footer(text="Tokyo Horizon RP | Sistema Economia")
        try:
            ch = (bot.get_channel(origin_ch_id) or await bot.fetch_channel(origin_ch_id)) if origin_ch_id else None
            if ch:
                await ch.send(f"<@{self.autore_id}>", embed=embed_rapine)
        except Exception as e:
            print(f"[ERRORE] Notifica approvazione fallita: {e}")

    async def _rifiuta(self, interaction: discord.Interaction):
        if not ha_permessi_approvazione(interaction):
            await interaction.response.send_message("❌ Solo lo staff può rifiutare le consegne.", ephemeral=True)
            return

        ordine = ordini_pendenti_macchina.get(self.autore_id)
        if not ordine or not ordine.get("in_attesa"):
            await interaction.response.send_message("⚠️ Questa consegna è già stata processata o è scaduta.", ephemeral=True)
            return

        guadagno     = ordine.get("guadagno", 0)
        modello      = ordine.get("modello", "?")
        origin_ch_id = ordine.get("origin_ch_id") or self.origin_ch_id

        ordini_pendenti_macchina.pop(self.autore_id, None)
        salva_dati()

        for child in self.children:
            child.disabled = True

        embed_are = discord.Embed(
            title="❌ CONSEGNA RIFIUTATA",
            description=(
                f"La consegna del veicolo `{modello}` è stata **rifiutata** da {interaction.user.mention}.\n\n"
                f"Il compenso **non** è stato accreditato al giocatore."
            ),
            color=discord.Color.red()
        )
        embed_are.set_footer(text="Tokyo Horizon RP | Pannello Staff")
        await interaction.response.edit_message(embed=embed_are, view=self)

        embed_rapine = discord.Embed(
            title="🚗 CONSEGNA RIFIUTATA",
            description=(
                f"<@{self.autore_id}> Lo staff ha verificato e **rifiutato** la tua consegna.\n\n"
                f"🚘 **Veicolo:** `{modello}`\n"
                f"💰 Il compenso di `{guadagno:,}€` **non** è stato accreditato.\n\n"
                f"Contatta lo staff per maggiori informazioni."
            ),
            color=discord.Color.red()
        )
        embed_rapine.set_footer(text="Tokyo Horizon RP | Sistema Economia")
        try:
            ch = (bot.get_channel(origin_ch_id) or await bot.fetch_channel(origin_ch_id)) if origin_ch_id else None
            if ch:
                await ch.send(f"<@{self.autore_id}>", embed=embed_rapine)
        except Exception as e:
            print(f"[ERRORE] Notifica rifiuto fallita: {e}")


class VeicoloButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📸 Ho Inviato la Foto", style=discord.ButtonStyle.primary, custom_id="vei:foto")
    async def conferma_foto(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        ordine = ordini_pendenti_macchina.get(uid)
        if not ordine:
            # Ricarica dal file: potrebbe essere stato scritto da un'altra istanza
            _dati_r = carica_dati()
            ordini_pendenti_macchina.update(_dati_r[4])
            ordine = ordini_pendenti_macchina.get(uid)
        if not ordine:
            await interaction.response.send_message("❌ Questo ordine è scaduto. Usa `/furto macchina` per iniziarne uno nuovo.", ephemeral=True)
            return
        if ordine.get("in_attesa") or ordine.get("consegnato"):
            await interaction.response.send_message("⚠️ Questo furto è già stato processato.", ephemeral=True)
            return
        if ordine.get("foto_ok"):
            await interaction.response.send_message("✅ Foto già confermata! Ora premi **🏁 Consegna Veicolo**.", ephemeral=True)
            return

        ordine["foto_ok"] = True
        salva_dati()
        await interaction.response.send_message(
            "✅ **Foto confermata!** Ora raggiungi la destinazione e premi **🏁 Consegna Veicolo**.",
            ephemeral=True
        )

    @discord.ui.button(label="🏁 Consegna Veicolo", style=discord.ButtonStyle.success, custom_id="vei:consegna")
    async def consegna(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        ordine = ordini_pendenti_macchina.get(uid)
        if not ordine:
            # Ricarica dal file: potrebbe essere stato scritto da un'altra istanza
            _dati_r = carica_dati()
            ordini_pendenti_macchina.update(_dati_r[4])
            ordine = ordini_pendenti_macchina.get(uid)
        if not ordine:
            await interaction.response.send_message("❌ Questo ordine è scaduto. Usa `/furto macchina` per iniziarne uno nuovo.", ephemeral=True)
            return
        if not ordine.get("foto_ok"):
            await interaction.response.send_message("❌ Prima invia la foto nel canale e clicca **📸 Ho Inviato la Foto**!", ephemeral=True)
            return
        if ordine.get("in_attesa"):
            await interaction.response.send_message("⏳ La tua consegna è già in attesa di approvazione dello staff!", ephemeral=True)
            return
        if ordine.get("consegnato"):
            await interaction.response.send_message("✅ Questa consegna è già stata processata.", ephemeral=True)
            return

        ordine["in_attesa"]    = True
        ordine["in_attesa_at"] = time.time()
        ordine["origin_ch_id"] = interaction.channel_id   # per notifica dopo approvazione/rifiuto
        salva_dati()
        print(f"[VEICOLO] Consegna uid={uid} modello={ordine['modello']} → in_attesa=True salvato")

        embed_staff = discord.Embed(
            title="🚗 RICHIESTA APPROVAZIONE CONSEGNA",
            description=(
                f"**{interaction.user.mention}** ha completato un furto veicolo e richiede il compenso.\n\n"
                f"🚘 **Veicolo:** `{ordine['modello']}`\n"
                f"📍 **Destinazione:** `{ordine['destinazione']}`\n"
                f"💰 **Compenso richiesto:** `{ordine['guadagno']:,}€`\n\n"
                f"Verificate se la consegna è stata effettuata correttamente, poi approvate o rifiutate."
            ),
            color=discord.Color.orange()
        )
        embed_staff.set_footer(text="Tokyo Horizon RP | Pannello Staff — Furto Veicoli")

        # Vista persistente: timeout=None, custom_id univoco per utente — sopravvive ai riavvii
        view_approvazione = ApprovazioneCosegnaView(
            autore_id=uid,
            origin_ch_id=interaction.channel_id,
        )
        bot.add_view(view_approvazione)   # registra subito per questo bot instance

        await interaction.response.send_message(
            "📋 **Richiesta inviata allo staff!** Attendi che verifichino la tua consegna.",
            ephemeral=True
        )
        try:
            canale_staff = await bot.fetch_channel(CANALE_STAFF_VEICOLI)
            await canale_staff.send(content="<@&1514407155577524385>", embed=embed_staff, view=view_approvazione)
            print(f"[VEICOLO] Embed staff inviato in #{canale_staff.name} ✅")
        except discord.Forbidden:
            print(f"[VEICOLO] ❌ Permessi mancanti in CANALE_STAFF_VEICOLI ({CANALE_STAFF_VEICOLI})")
            await interaction.followup.send(embed=embed_staff, view=view_approvazione)
        except discord.NotFound:
            print(f"[VEICOLO] ❌ Canale staff non trovato ({CANALE_STAFF_VEICOLI})")
            await interaction.followup.send(embed=embed_staff, view=view_approvazione)
        except Exception as e:
            print(f"[VEICOLO] ❌ Errore invio staff: {e}")
            await interaction.followup.send(embed=embed_staff, view=view_approvazione)


# =============================================================================
# GESTORE ERRORI GLOBALE
# =============================================================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Interazioni scadute o già gestite — ignora silenziosamente
    if isinstance(error, app_commands.CheckFailure):
        return
    orig = getattr(error, "original", None)
    if orig is not None:
        # InteractionResponded: interazione già risposta (non è HTTPException, non ha .code)
        if isinstance(orig, discord.InteractionResponded):
            print(f"[SKIP] InteractionResponded ignorato: {orig}")
            return
        code = getattr(orig, "code", None)
        if code in (10062, 40060):
            print(f"[SKIP] Errore transiente ignorato ({code}): {orig}")
            return
    print(f"[ERRORE COMANDO] {type(error).__name__}: {error}")
    if isinstance(error, app_commands.CommandSignatureMismatch):
        print("[INFO] Firma comando non aggiornata — risincronizzazione in corso...")
        try:
            await bot.tree.sync()
        except Exception:
            pass
        try:
            msg = "⚠️ Il comando è stato aggiornato — riprova tra qualche secondo."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass
    # Tutti gli altri errori: solo log, nessun messaggio all'utente


# =============================================================================
# COMANDO /FURTO
# =============================================================================
@bot.tree.command(name="furto", description="Seleziona il tipo di furto da effettuare nel server")
@app_commands.describe(tipo="Seleziona il tipo di furto (Villa, Casa o Macchina)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Villa",    value="villa"),
    app_commands.Choice(name="Casa",     value="casa"),
    app_commands.Choice(name="Macchina", value="macchina"),
])
async def furto(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    uid = interaction.user.id
    tipo_scelto = tipo.value

    # Blocco post-colpo: impossibile fare attività criminale per il tempo prestabilito
    lock_rem = get_criminal_lock(uid)
    if lock_rem > 0:
        await interaction.response.send_message(
            f"🔒 Hai completato un colpo di alto profilo di recente.\n"
            f"Non puoi svolgere attività criminale per ancora {formatta_durata(lock_rem)}.",
            ephemeral=True
        )
        return

    if tipo_scelto == "macchina":
        if canale_furti_id and interaction.channel_id != canale_furti_id:
            await interaction.response.send_message(
                f"❌ I furti veicolo si effettuano solo nel canale <#{canale_furti_id}>!", ephemeral=True
            )
            return
        ora_attuale = time.time()
        cooldown_sec = 2 * 3600
        ultimo = furto_cooldown.get(uid, {}).get("macchina", 0)
        if ora_attuale - ultimo < cooldown_sec:
            rimanenti = int(cooldown_sec - (ora_attuale - ultimo))
            ore = rimanenti // 3600
            minuti = (rimanenti % 3600) // 60
            await interaction.response.send_message(
                f"⏳ Devi aspettare ancora **{ore}h {minuti}m** prima di poter rubare un'altra macchina.", ephemeral=True
            )
            return
        # Blocca se c'è già un ordine in attesa di approvazione staff
        # Ricarica dal file per avere lo stato aggiornato anche dopo un restart del bot
        _dati_r = carica_dati()
        ordini_pendenti_macchina.update(_dati_r[4])
        for _k, _v in _dati_r[2].items():
            inventario[_k] = _v
        ordine_attivo = ordini_pendenti_macchina.get(uid)
        if ordine_attivo and ordine_attivo.get("in_attesa"):
            # Auto-cancella ordini bloccati da più di 4 ore (bot riavviato prima che lo staff approvasse)
            in_attesa_da = time.time() - ordine_attivo.get("in_attesa_at", 0)
            if in_attesa_da > 4 * 3600:
                ordini_pendenti_macchina.pop(uid, None)
                salva_dati()
                print(f"[VEICOLO] Ordine scaduto auto-rimosso per uid={uid} (in attesa da {in_attesa_da/3600:.1f}h)")
            else:
                await interaction.response.send_message(
                    f"⏳ Hai già una consegna del veicolo `{ordine_attivo.get('modello', '?')}` **in attesa di approvazione dello staff**.\n"
                    f"Attendi che lo staff approvi o rifiuti prima di iniziare un nuovo furto.\n"
                    f"Se pensi ci sia un errore, contatta lo staff per usare `/resetordine`.",
                    ephemeral=True
                )
                return
        # Controlla inventario: serve Slim Jim + Dispositivo di Hacking Base
        inv = get_inventario(uid)
        items_mancanti = []
        if inv.get("Slim Jim", 0) < 1:
            items_mancanti.append("1x **Slim Jim** (da `/negozio`)")
        if inv.get("Dispositivo di Hacking Base", 0) < 1:
            items_mancanti.append("1x **Dispositivo di Hacking Base** (da `/negozio`)")
        if items_mancanti:
            await interaction.response.send_message(
                "🔒 Per rubare un veicolo ti mancano:\n• " + "\n• ".join(items_mancanti),
                ephemeral=True
            )
            return
        await interaction.response.send_modal(MacchinaModal(uid))
        return

    if canale_furti_id and interaction.channel_id != canale_furti_id:
        await interaction.response.send_message(
            f"❌ I furti si effettuano solo nel canale <#{canale_furti_id}>!", ephemeral=True
        )
        return

    # --- Controllo inventario PRIMA del defer: errori visibili solo al giocatore ---
    strumento_usato = None
    if tipo_scelto == "villa":
        inv_check = get_inventario(uid)
        strumento_usato = next((s for s in ["Grimaldello", "Piede di Porco"] if inv_check.get(s, 0) > 0), None)
        if not strumento_usato:
            await interaction.response.send_message(
                "🔒 Per il furto in villa servono **`Piede di Porco`** o **`Grimaldello`** e **`Sistema di Hacking`**. Acquistali con `/negozio`.", ephemeral=True
            )
            return
        if inv_check.get("Sistema di Hacking", 0) <= 0:
            await interaction.response.send_message(
                "💻 Hai lo strumento da scasso ma ti manca il **`Sistema di Hacking`** (4.000€). Acquistalo con `/negozio`.", ephemeral=True
            )
            return
    elif tipo_scelto == "casa":
        inv_check = get_inventario(uid)
        strumento_usato = next((s for s in ["Piede di Porco"] if inv_check.get(s, 0) > 0), None)
        if not strumento_usato:
            await interaction.response.send_message(
                "🔒 Per il furto in casa serve **`1x Piede di Porco`** e **`1x Torcia`**. Acquistali con `/negozio`.", ephemeral=True
            )
            return
        if inv_check.get("Torcia", 0) <= 0:
            await interaction.response.send_message(
                "🔦 Hai il Piede di Porco ma ti manca la **`Torcia`** (2.000€). Acquistala con `/negozio`.", ephemeral=True
            )
            return

    await interaction.response.defer()  # Pubblico: il risultato del furto è visibile a tutti

    ora_attuale = time.time()
    if tipo_scelto != "villa":
        cooldown_sec = 4 * 3600
        ultimo = furto_cooldown.get(uid, {}).get(tipo_scelto, 0)
        if ora_attuale - ultimo < cooldown_sec:
            rimanenti = int(cooldown_sec - (ora_attuale - ultimo))
            ore = rimanenti // 3600
            minuti = (rimanenti % 3600) // 60
            await interaction.followup.send(
                f"⏳ Devi aspettare ancora **{ore}h {minuti}m** prima di poter fare un altro furto in {tipo_scelto}.", ephemeral=True
            )
            return
    if tipo_scelto == "villa":
        _PESI_TIER = {"rara": 60, "epica": 30, "leggendaria": 10}
        _pesi_ville = [_PESI_TIER.get(v.get("loot_tier", "rara"), 60) for v in VILLE]
        location = random.choices(VILLE, weights=_pesi_ville, k=1)[0]
        tier = location.get("loot_tier", "rara")
        pool_per_tier = LOOT_VILLA[tier]
        oggetti_scelti = campiona_con_rarità(pool_per_tier, k=len(pool_per_tier))
        pool_finale, descrizione_oggetti = costruisci_pool(oggetti_scelti, mostra_perc=False)
        valore_max = max(o["valore"] for o in oggetti_scelti)

        ingressi_tier = CONFIGURAZIONE_INGRESSI.get(tier, CONFIGURAZIONE_INGRESSI["rara"])
        lista_ingressi = "\n".join(f"• {i['emoji']} {i['label']}" for i in ingressi_tier)

        embed = discord.Embed(
            title=f"🏰 Furto Selezionato: {location['nome']}",
            description=(
                f"⭐ **Rarità Obiettivo:** {location.get('rarità', '—')}\n\n"
                "**INFORMAZIONI SUL COLPO OTTENUTE DAI SATELLITI**\n\n"
                f"**Scegli il punto di ingresso:**\n{lista_ingressi}\n\n"
                f"📦 **Merci preziose rilevate all'interno (Max {valore_max:,}€):**\n{descrizione_oggetti}\n"
                "🔑 **Oggetti richiesti:** 🪓 `Piede di Porco` o `Grimaldello` + 💻 `Sistema di Hacking`"
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Furto")

        view = VillaScassoButtons(interaction.user.id, pool_finale, strumento_usato, tier=tier)
        files = []
        embeds = [embed]

        if location["esterno"]:
            try:
                ext = location["esterno"].rsplit(".", 1)[-1]
                fname = f"villa_esterno.{ext}"
                file_esterno = discord.File(location["esterno"], filename=fname)
                files.append(file_esterno)
                embed.set_image(url=f"attachment://{fname}")
            except FileNotFoundError:
                pass

        if location.get("mappa"):
            try:
                ext_m = location["mappa"].rsplit(".", 1)[-1]
                fname_m = f"villa_mappa.{ext_m}"
                file_mappa = discord.File(location["mappa"], filename=fname_m)
                files.append(file_mappa)
                embed_mappa = discord.Embed(description="📍 **Posizione sulla mappa**", color=discord.Color.purple())
                embed_mappa.set_image(url=f"attachment://{fname_m}")
                embeds.append(embed_mappa)
            except FileNotFoundError:
                pass

        furto_cooldown.setdefault(uid, {})[tipo_scelto] = ora_attuale
        salva_dati()
        await interaction.followup.send(embeds=embeds, files=files, view=view)

    elif tipo_scelto == "casa":
        oggetti_scelti = campiona_con_rarità(OGGETTI_CASA, k=random.randint(3, 4))
        pool_finale, descrizione_oggetti = costruisci_pool(oggetti_scelti)
        valore_max = max(o["valore"] for o in oggetti_scelti)
        location = random.choice(CASE)

        embed = discord.Embed(
            title=f"🏡 Furto Selezionato: {location['nome']}",
            description=(
                "**SOPRALLUOGO EFFETTUATO. OBIETTIVO STANDARD.**\n\n"
                "**Scegli come entrare:**\n"
                "• 🪟 Forza la finestra\n"
                "• 🚪 Forza la porta\n\n"
                f"📦 **Beni comuni individuati all'interno (Max {valore_max:,}€):**\n{descrizione_oggetti}\n"
                "🔑 **Strumenti richiesti:** 🪓 `Piede di Porco` + 🔦 `Torcia`"
            ),
            color=discord.Color.dark_green()
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Furto")

        view = ScassoButtons(interaction.user.id, "casa", pool_finale, strumento_usato)
        files = []
        embeds = [embed]

        if location["esterno"]:
            try:
                file_esterno = discord.File(location["esterno"], filename="casa_esterno.jpeg")
                files.append(file_esterno)
                embed.set_image(url="attachment://casa_esterno.jpeg")
            except FileNotFoundError:
                pass

        if location.get("mappa"):
            try:
                file_mappa = discord.File(location["mappa"], filename="casa_mappa.jpeg")
                files.append(file_mappa)
                embed_mappa = discord.Embed(description="📍 **Posizione sulla mappa**", color=discord.Color.dark_green())
                embed_mappa.set_image(url="attachment://casa_mappa.jpeg")
                embeds.append(embed_mappa)
            except FileNotFoundError:
                pass

        furto_cooldown.setdefault(uid, {})[tipo_scelto] = ora_attuale
        salva_dati()
        await interaction.followup.send(embeds=embeds, files=files, view=view)


# =============================================================================
# COMANDO /CLASSIFICA
# =============================================================================
@bot.tree.command(name="classifica", description="Mostra i giocatori più ricchi del server")
async def classifica(interaction: discord.Interaction):
    await interaction.response.defer()
    if not economia:
        await interaction.followup.send("📊 Nessun dato disponibile. Nessuno ha ancora usato il sistema economia!", ephemeral=True)
        return

    classifica_list = []
    for user_id, dati in economia.items():
        totale = dati["portafoglio"] + dati["banca"]
        classifica_list.append((user_id, totale, dati["portafoglio"], dati["banca"]))

    classifica_list.sort(key=lambda x: x[1], reverse=True)
    top = classifica_list[:10]

    medaglie = ["🥇", "🥈", "🥉"]
    descrizione = ""
    for i, (user_id, totale, portafoglio, banca) in enumerate(top):
        try:
            member = interaction.guild.get_member(user_id)
            nome = member.display_name if member else f"Utente #{user_id}"
        except Exception:
            nome = f"Utente #{user_id}"
        posizione = medaglie[i] if i < 3 else f"`#{i+1}`"
        descrizione += f"{posizione} **{nome}** — `{totale:,}€`\n"

    embed = discord.Embed(
        title="🏆 Classifica Ricchezza — Tokyo Horizon RP",
        description=descrizione,
        color=discord.Color.gold()
    )
    embed.set_footer(text="Tokyo Horizon RP | Sistema Economia")
    await interaction.followup.send(embed=embed)


# =============================================================================
# COMANDO /BILANCIO
# =============================================================================
@bot.tree.command(name="bilancio", description="Verifica il tuo conto corrente e il contante in tasca")
async def bilancio(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = interaction.user.id
    # Leggi sempre dal file per evitare dati obsoleti in caso di riavvii del bot
    bil = None
    try:
        if os.path.exists(DATI_FILE):
            with open(DATI_FILE, "r") as f:
                dati_file = json.load(f)
            eco_file = {int(k): v for k, v in dati_file.get("economia", {}).items()}
            # Aggiorna la memoria con i dati del file (fonte unica di verità)
            for k, v in eco_file.items():
                economia[k] = v
            bil = economia.get(uid)
    except Exception as e:
        print(f"[BILANCIO] Errore lettura file: {e} — uso dati in memoria")
    if bil is None:
        bil = get_balance(uid)
    embed = discord.Embed(
        title=f"💳 Conto Corrente: {interaction.user.display_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="💵 Contanti in Tasca:", value=f"`{bil['portafoglio']:,}€`", inline=False)
    embed.add_field(name="🏛️ Deposito Bancario (Maze Bank):", value=f"`{bil['banca']:,}€`", inline=False)
    totale = bil["portafoglio"] + bil["banca"]
    embed.add_field(name="💼 Patrimonio Totale:", value=f"`{totale:,}€`", inline=False)
    embed.set_footer(text="Tokyo Horizon RP | Sistema Economia")
    await interaction.followup.send(embed=embed, ephemeral=True)


cooldown_banca = {}

def controlla_cooldown(user_id: int, azione: str, secondi: int = 60):
    chiave = f"{user_id}_{azione}"
    ora = time.time()
    if chiave in cooldown_banca:
        trascorso = ora - cooldown_banca[chiave]
        if trascorso < secondi:
            return int(secondi - trascorso)
    cooldown_banca[chiave] = ora
    return 0


@bot.tree.command(name="deposita", description="Deposita contanti dal portafoglio alla banca")
@app_commands.describe(importo="Importo in euro da depositare")
async def deposita(interaction: discord.Interaction, importo: int):
    await interaction.response.defer(ephemeral=True)
    attesa = controlla_cooldown(interaction.user.id, "deposita")
    if attesa > 0:
        await interaction.followup.send(f"⏳ Devi aspettare ancora **{attesa} secondi**.", ephemeral=True)
        return
    if importo <= 0:
        await interaction.followup.send("❌ L'importo deve essere maggiore di 0€.", ephemeral=True)
        return
    bil = get_balance(interaction.user.id)
    if importo > bil["portafoglio"]:
        await interaction.followup.send("❌ Non hai abbastanza contanti in tasca.", ephemeral=True)
        return
    bil["portafoglio"] -= importo
    bil["banca"] += importo
    salva_dati()
    await interaction.followup.send(f"🏛️ Depositati con successo **`{importo:,}€`**.")


@bot.tree.command(name="preleva", description="Preleva contanti dalla banca al portafoglio")
@app_commands.describe(importo="Importo in euro da prelevare")
async def preleva(interaction: discord.Interaction, importo: int):
    await interaction.response.defer(ephemeral=True)
    attesa = controlla_cooldown(interaction.user.id, "preleva")
    if attesa > 0:
        await interaction.followup.send(f"⏳ Devi aspettare ancora **{attesa} secondi**.", ephemeral=True)
        return
    if importo <= 0:
        await interaction.followup.send("❌ L'importo deve essere maggiore di 0€.", ephemeral=True)
        return
    bil = get_balance(interaction.user.id)
    if importo > bil["banca"]:
        await interaction.followup.send("❌ Non hai abbastanza soldi in banca.", ephemeral=True)
        return
    bil["banca"] -= importo
    bil["portafoglio"] += importo
    salva_dati()
    await interaction.followup.send(f"💵 Prelevati con successo **`{importo:,}€`**.")


@bot.tree.command(name="paga", description="Paga un altro giocatore con i contanti in tasca")
@app_commands.describe(utente="Il giocatore a cui vuoi pagare", importo="Importo in euro da pagare")
async def paga(interaction: discord.Interaction, utente: discord.Member, importo: int):
    await interaction.response.defer()
    mittente = interaction.user
    if utente.id == mittente.id or utente.bot or importo <= 0:
        await interaction.followup.send("❌ Transazione non valida.", ephemeral=True)
        return
    bil_mittente = get_balance(mittente.id)
    if importo > bil_mittente["portafoglio"]:
        await interaction.followup.send("❌ Contanti insufficienti in tasca.", ephemeral=True)
        return
    bil_mittente["portafoglio"] -= importo
    bil_destinatario = get_balance(utente.id)
    bil_destinatario["portafoglio"] += importo
    salva_dati()
    await interaction.followup.send(f"💸 Hai pagato a {utente.mention} l'importo di `{importo:,}€`.")


# =============================================================================
# NEGOZIO, INVENTARIO
# =============================================================================

@bot.tree.command(name="concessionaria", description="Informazioni sulla concessionaria di Tokyo Horizon Motors")
async def concessionaria_cmd(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
    except Exception as e:
        print(f"[CONCESSIONARIA] defer() fallito: {e}")
        return
    try:
        embed = discord.Embed(
            title="🏮 Tokyo Horizon Motors — 東京ホライズン",
            description=(
                "東京ホライズン · カーディーラー\n\n"
                "📋 Il catalogo completo dei veicoli è disponibile nel canale dedicato del server.\n"
                "Cerca il canale **concessionaria** e scorri gli embed per vedere tutte le auto disponibili.\n\n"
                "🌐 **Sito web:** attualmente in fase di sviluppo — disponibile prossimamente.\n\n"
                "📅 Ogni settimana viene aggiunto un nuovo veicolo per ogni categoria!\n\n"
                "💬 Per acquistare un veicolo, contatta uno **staff** o apri un **ticket**."
            ),
            color=discord.Color.from_rgb(220, 40, 40)
        )
        embed.set_footer(text="Tokyo Horizon RP · Catalogo Ufficiale · 公式ディーラー")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"[CONCESSIONARIA] Errore in /concessionaria: {e}")
        try:
            await interaction.followup.send("❌ Errore nel caricamento. Riprova più tardi.", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="negozio", description="Visualizza gli articoli disponibili nel negozio")
async def negozio(interaction: discord.Interaction):
    await interaction.response.defer()
    embed = discord.Embed(
        title="🏪 NEGOZIO — Tokyo Horizon RP",
        description="Acquista gli strumenti necessari per i furti con `/compra <articolo>`.",
        color=discord.Color.gold()
    )
    for nome, info in NEGOZIO.items():
        embed.add_field(name=f"{info['emoji']} {nome} — `{info['prezzo']:,}€`", value=info["descrizione"], inline=False)
    embed.set_footer(text="Tokyo Horizon RP | Sistema Negozio")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="compra", description="Acquista un articolo dal negozio")
@app_commands.describe(articolo="L'articolo che vuoi acquistare")
@app_commands.choices(articolo=[
    app_commands.Choice(name="Piede di Porco (1.000€)",              value="Piede di Porco"),
    app_commands.Choice(name="Cacciavite (1.250€)",                  value="Cacciavite"),
    app_commands.Choice(name="Grimaldello (1.500€)",                 value="Grimaldello"),
    app_commands.Choice(name="Torcia (2.000€)",                      value="Torcia"),
    app_commands.Choice(name="Sistema di Hacking (4.000€)",          value="Sistema di Hacking"),
    app_commands.Choice(name="Slim Jim (4.000€)",                    value="Slim Jim"),
    app_commands.Choice(name="Dispositivo di Hacking Base (4.000€)", value="Dispositivo di Hacking Base"),
    app_commands.Choice(name="Trapano (8.000€)",                     value="Trapano"),
    app_commands.Choice(name="Grimaldello Avanzato (15.000€)",       value="Grimaldello Avanzato"),
])
async def compra(interaction: discord.Interaction, articolo: app_commands.Choice[str]):
    if not await safe_defer(interaction, ephemeral=True):
        return
    nome = articolo.value
    info = NEGOZIO.get(nome)
    if not info:
        await interaction.followup.send("❌ Articolo non trovato nel negozio.", ephemeral=True)
        return
    prezzo = info["prezzo"]
    bil = get_balance(interaction.user.id)
    totale = bil["portafoglio"] + bil["banca"]
    if totale < prezzo:
        await interaction.followup.send(
            f"❌ Non hai abbastanza soldi! Ti servono `{prezzo:,}€`.\n"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`",
            ephemeral=True
        )
        return
    da_tasca = min(bil["portafoglio"], prezzo)
    da_banca = prezzo - da_tasca
    bil["portafoglio"] -= da_tasca
    bil["banca"] -= da_banca
    inv = get_inventario(interaction.user.id)
    inv[nome] = inv.get(nome, 0) + 1
    salva_dati()
    fonte = ""
    if da_banca > 0 and da_tasca > 0:
        fonte = f"💵 `{da_tasca:,}€` dalla tasca + 🏛️ `{da_banca:,}€` dalla banca\n"
    elif da_banca > 0:
        fonte = f"🏛️ Pagato dalla banca\n"
    embed = discord.Embed(
        title="✅ Acquisto Completato!",
        description=(
            f"Hai acquistato **{info['emoji']} {nome}** per `{prezzo:,}€`.\n\n"
            f"{fonte}"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`\n"
            f"🎒 **In inventario:** `{inv[nome]}x {nome}`"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Tokyo Horizon RP | Sistema Negozio")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="mercatonero", description="Visualizza gli articoli del mercato nero illegale")
async def mercatonero(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="🖤 MERCATO NERO — Tokyo Horizon RP",
        description="Articoli illegali acquistabili con `/compranero <articolo>`.\n⚠️ Acquistare armi è contro la legge — usale a tuo rischio.",
        color=discord.Color.dark_red()
    )
    for nome, info in MERCATO_NERO.items():
        embed.add_field(name=f"{info['emoji']} {nome} — `{info['prezzo']:,}€`", value=info["descrizione"], inline=False)
    embed.set_footer(text="Tokyo Horizon RP | Mercato Nero")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="compranero", description="Acquista un articolo dal mercato nero")
@app_commands.describe(articolo="L'articolo illegale che vuoi acquistare")
@app_commands.choices(articolo=[
    app_commands.Choice(name="Simulatore di Impronte Digitali (20.000€)", value="Simulatore di Impronte Digitali"),
    app_commands.Choice(name="Gas Soporifero (8.000€)",                    value="Gas Soporifero"),
    app_commands.Choice(name="Dispositivo di Hacking Medio (15.000€)",     value="Dispositivo di Hacking Medio"),
    app_commands.Choice(name="Lancia Termica (30.000€)",                   value="Lancia Termica"),
    app_commands.Choice(name="Dispositivo di Hacking Avanzato (50.000€)",  value="Dispositivo di Hacking Avanzato"),
    app_commands.Choice(name="Trapano Pesante Professionale (50.000€)",    value="Trapano Pesante Professionale"),
])
async def compranero(interaction: discord.Interaction, articolo: app_commands.Choice[str]):
    if not await safe_defer(interaction, ephemeral=True):
        return
    nome = articolo.value
    info = MERCATO_NERO.get(nome)
    if not info:
        await interaction.followup.send("❌ Articolo non trovato nel mercato nero.", ephemeral=True)
        return
    prezzo = info["prezzo"]
    bil = get_balance(interaction.user.id)
    totale = bil["portafoglio"] + bil["banca"]
    if totale < prezzo:
        await interaction.followup.send(
            f"❌ Non hai abbastanza soldi! Ti servono `{prezzo:,}€`.\n"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`",
            ephemeral=True
        )
        return
    da_tasca = min(bil["portafoglio"], prezzo)
    da_banca = prezzo - da_tasca
    bil["portafoglio"] -= da_tasca
    bil["banca"] -= da_banca
    inv = get_inventario(interaction.user.id)
    inv[nome] = inv.get(nome, 0) + 1
    salva_dati()
    fonte = ""
    if da_banca > 0 and da_tasca > 0:
        fonte = f"💵 `{da_tasca:,}€` dalla tasca + 🏛️ `{da_banca:,}€` dalla banca\n"
    elif da_banca > 0:
        fonte = f"🏛️ Pagato dalla banca\n"
    embed = discord.Embed(
        title="✅ Acquisto Completato!",
        description=(
            f"Hai acquistato **{info['emoji']} {nome}** per `{prezzo:,}€`.\n\n"
            f"{fonte}"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`\n"
            f"🎒 **In inventario:** `{inv[nome]}x {nome}`"
        ),
        color=discord.Color.dark_red()
    )
    embed.set_footer(text="Tokyo Horizon RP | Mercato Nero")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="mercatoarmi", description="Visualizza le armi disponibili nel mercato armi")
async def mercatoarmi(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(
        title="🔫 MERCATO ARMI — Tokyo Horizon RP",
        description="Armi acquistabili con `/compraarmi <arma>`.\n⚠️ Detenere armi è illegale — usale a tuo rischio.",
        color=discord.Color.dark_orange()
    )
    for nome, info in MERCATO_ARMI.items():
        embed.add_field(name=f"{info['emoji']} {nome} — `{info['prezzo']:,}€`", value=info["descrizione"], inline=False)
    embed.set_footer(text="Tokyo Horizon RP | Mercato Armi")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="compraarmi", description="Acquista un'arma dal mercato armi")
@app_commands.describe(arma="L'arma che vuoi acquistare")
@app_commands.choices(arma=[
    app_commands.Choice(name="Pistola (10.000€)", value="Pistola"),
])
async def compraarmi(interaction: discord.Interaction, arma: app_commands.Choice[str]):
    if not await safe_defer(interaction, ephemeral=True):
        return
    nome = arma.value
    info = MERCATO_ARMI.get(nome)
    if not info:
        await interaction.followup.send("❌ Arma non trovata nel mercato armi.", ephemeral=True)
        return
    prezzo = info["prezzo"]
    bil = get_balance(interaction.user.id)
    totale = bil["portafoglio"] + bil["banca"]
    if totale < prezzo:
        await interaction.followup.send(
            f"❌ Non hai abbastanza soldi! Ti servono `{prezzo:,}€`.\n"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`",
            ephemeral=True
        )
        return
    da_tasca = min(bil["portafoglio"], prezzo)
    da_banca = prezzo - da_tasca
    bil["portafoglio"] -= da_tasca
    bil["banca"] -= da_banca
    inv = get_inventario(interaction.user.id)
    inv[nome] = inv.get(nome, 0) + 1
    salva_dati()
    fonte = ""
    if da_banca > 0 and da_tasca > 0:
        fonte = f"💵 `{da_tasca:,}€` dalla tasca + 🏛️ `{da_banca:,}€` dalla banca\n"
    elif da_banca > 0:
        fonte = f"🏛️ Pagato dalla banca\n"
    embed = discord.Embed(
        title="✅ Acquisto Completato!",
        description=(
            f"Hai acquistato **{info['emoji']} {nome}** per `{prezzo:,}€`.\n\n"
            f"{fonte}"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`\n"
            f"🎒 **In inventario:** `{inv[nome]}x {nome}`"
        ),
        color=discord.Color.dark_orange()
    )
    embed.set_footer(text="Tokyo Horizon RP | Mercato Armi")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="inventario", description="Visualizza il tuo inventario")
async def inventario_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        inv = get_inventario(interaction.user.id)
        inv_filtrato = {n: q for n, q in inv.items() if isinstance(q, int) and q > 0}
        if not inv_filtrato:
            await interaction.followup.send("🎒 Il tuo inventario è vuoto. Acquista qualcosa con `/negozio`, `/mercatonero` o `/mercatoarmi`!", ephemeral=True)
            return
        TUTTI_ITEMS = {**NEGOZIO, **MERCATO_NERO, **MERCATO_ARMI}
        righe = "\n".join(
            f"• {TUTTI_ITEMS[n]['emoji'] if n in TUTTI_ITEMS else '📦'} **{n}** — `{q}x`"
            for n, q in inv_filtrato.items()
        )
        embed = discord.Embed(
            title=f"🎒 Inventario di {interaction.user.display_name}",
            description=righe,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Inventario")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"[ERRORE INVENTARIO] {e}")
        await interaction.followup.send("❌ Errore nel caricare l'inventario. Riprova.", ephemeral=True)


# =============================================================================
# GARAGE E PEZZI DI RICAMBIO
# =============================================================================

@bot.tree.command(name="garage", description="Visualizza tutte le macchine che possiedi")
async def garage_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = interaction.user.id
    veicoli = veicoli_posseduti.get(uid, [])

    embed = discord.Embed(
        title=f"🚗 Garage di {interaction.user.display_name}",
        color=discord.Color.dark_gold()
    )

    if veicoli:
        righe = "\n".join(
            f"`{i+1}.` 🚘 **{v['modello']}**  —  acquistato il `{v.get('data', '?')}`"
            for i, v in enumerate(veicoli)
        )
        embed.description = righe
    else:
        embed.description = "Non hai ancora nessun veicolo registrato nel tuo garage.\nAcquistane uno in concessionaria!"

    embed.set_footer(text=f"Tokyo Horizon RP | Totale veicoli: {len(veicoli)}")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="lavorazione", description="Visualizza il tuo furto veicolo in corso e i Pezzi di Ricambio")
async def lavorazione_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = interaction.user.id
    inv = get_inventario(uid)
    ordine = ordini_pendenti_macchina.get(uid)
    pezzi = inv.get("Pezzo di Ricambio", 0)

    embed = discord.Embed(
        title=f"🔩 Pezzi di Ricambio — {interaction.user.display_name}",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="🔩 Pezzi di Ricambio in inventario",
        value=f"`{pezzi}x` disponibili" if pezzi > 0 else "Non hai pezzi di ricambio al momento.",
        inline=False
    )
    embed.set_footer(text="Tokyo Horizon RP | Officina")
    await interaction.followup.send(embed=embed, ephemeral=True)


RUOLO_CONCESSIONARIO = 1517103897469124678

@bot.tree.command(name="vendiauto", description="[CONCESSIONARIO] Vendi una macchina a un giocatore")
@app_commands.describe(
    acquirente="Il giocatore che acquista la macchina",
    modello="Modello del veicolo (es: Pfister 811, Sultan RS...)",
    prezzo="Prezzo di vendita in €"
)
async def vendiauto_cmd(interaction: discord.Interaction, acquirente: discord.Member, modello: str, prezzo: int):
    raw_roles = getattr(interaction.user, '_roles', None)
    ha_ruolo = (raw_roles is not None and RUOLO_CONCESSIONARIO in raw_roles) or ha_permessi_staff(interaction)
    if not ha_ruolo:
        await interaction.response.send_message("❌ Solo i Concessionari possono usare questo comando.", ephemeral=True)
        return

    if prezzo <= 0:
        await interaction.response.send_message("❌ Il prezzo deve essere maggiore di 0.", ephemeral=True)
        return

    if acquirente.id == interaction.user.id:
        await interaction.response.send_message("❌ Non puoi venderti una macchina da solo.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)

    bil_acquirente = get_balance(acquirente.id)
    totale_disponibile = bil_acquirente["portafoglio"] + bil_acquirente["banca"]

    if totale_disponibile < prezzo:
        mancanti = prezzo - totale_disponibile
        await interaction.followup.send(
            f"❌ **{acquirente.display_name}** non ha fondi sufficienti.\n"
            f"💰 Disponibili: `{totale_disponibile:,}€` — Necessari: `{prezzo:,}€` (mancano `{mancanti:,}€`)",
            ephemeral=True
        )
        return

    # Scala prima dal portafoglio, poi dalla banca
    if bil_acquirente["portafoglio"] >= prezzo:
        bil_acquirente["portafoglio"] -= prezzo
    else:
        resto = prezzo - bil_acquirente["portafoglio"]
        bil_acquirente["portafoglio"] = 0
        bil_acquirente["banca"] -= resto

    # 20% al concessionario, 80% alla banca del server (rimosso dall'economia)
    commissione = int(prezzo * 0.20)
    bil_concessionario = get_balance(interaction.user.id)
    bil_concessionario["banca"] += commissione

    # Aggiunge il veicolo al garage dell'acquirente
    from datetime import datetime
    data_oggi = datetime.now().strftime("%d/%m/%Y")
    if acquirente.id not in veicoli_posseduti:
        veicoli_posseduti[acquirente.id] = []
    veicoli_posseduti[acquirente.id].append({
        "modello": modello.strip(),
        "data": data_oggi,
        "prezzo": prezzo,
        "venduto_da": interaction.user.display_name,
    })
    salva_dati()

    embed = discord.Embed(
        title="🚘 Vendita Veicolo Completata!",
        color=discord.Color.green()
    )
    embed.add_field(name="🚗 Veicolo", value=f"`{modello.strip()}`", inline=True)
    embed.add_field(name="👤 Acquirente", value=acquirente.mention, inline=True)
    embed.add_field(name="💵 Prezzo", value=f"`{prezzo:,}€`", inline=True)
    embed.add_field(name="💼 Commissione concessionario (20%)", value=f"`{commissione:,}€`", inline=True)
    embed.add_field(name="🏦 Alla banca del server (80%)", value=f"`{prezzo - commissione:,}€`", inline=True)
    embed.set_footer(text=f"Tokyo Horizon RP | Venduto da {interaction.user.display_name}")
    await interaction.followup.send(embed=embed)

    # Notifica privata all'acquirente
    try:
        embed_acquirente = discord.Embed(
            title="🚘 Hai acquistato un veicolo!",
            description=(
                f"La tua nuova **{modello.strip()}** è stata registrata nel tuo garage.\n\n"
                f"💵 Pagato: `{prezzo:,}€`\n"
                f"📅 Data: `{data_oggi}`\n"
                f"🏪 Venduto da: `{interaction.user.display_name}`\n\n"
                f"Usa `/garage` per vedere tutti i tuoi veicoli!"
            ),
            color=discord.Color.blue()
        )
        embed_acquirente.set_footer(text="Tokyo Horizon RP | Concessionaria")
        await acquirente.send(embed=embed_acquirente)
    except Exception:
        pass

    print(f"[VENDIAUTO] {interaction.user} ha venduto {modello} a {acquirente} per {prezzo:,}€ (comm. {commissione:,}€)")


VALORE_PEZZO_RICAMBIO = 7000

@bot.tree.command(name="usapezzo", description="Vendi i tuoi Pezzi di Ricambio ad un meccanico (7.000€ cad.)")
@app_commands.describe(quantita="Quanti pezzi vuoi vendere (lascia vuoto per vendere tutti)")
async def usapezzo_cmd(interaction: discord.Interaction, quantita: int = None):
    await interaction.response.defer(ephemeral=True)
    uid = interaction.user.id
    inv = get_inventario(uid)
    disponibili = inv.get("Pezzo di Ricambio", 0)

    if disponibili <= 0:
        await interaction.followup.send(
            "❌ Non hai **Pezzi di Ricambio** nell'inventario.\n"
            "Ottienili svaligiando un'officina meccanica con `/rapina`!",
            ephemeral=True
        )
        return

    da_vendere = quantita if quantita is not None else disponibili

    if da_vendere <= 0:
        await interaction.followup.send("❌ La quantità deve essere almeno 1.", ephemeral=True)
        return

    if da_vendere > disponibili:
        await interaction.followup.send(
            f"❌ Hai solo **`{disponibili}x Pezzo di Ricambio`** — non puoi venderne `{da_vendere}`.",
            ephemeral=True
        )
        return

    guadagno = da_vendere * VALORE_PEZZO_RICAMBIO
    inv["Pezzo di Ricambio"] -= da_vendere
    if inv["Pezzo di Ricambio"] <= 0:
        del inv["Pezzo di Ricambio"]
    bil = get_balance(uid)
    bil["banca"] += guadagno
    salva_dati()

    embed = discord.Embed(
        title="🔩 Pezzi Venduti al Meccanico!",
        description=(
            f"Hai venduto **`{da_vendere}x Pezzo di Ricambio`** a un meccanico di fiducia.\n\n"
            f"💰 Guadagno: **`{guadagno:,}€`** accreditati in banca.\n"
            f"🔩 Rimasti in inventario: **`{inv.get('Pezzo di Ricambio', 0)}x`**"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Tokyo Horizon RP | Sistema Garage")
    await interaction.followup.send(embed=embed, ephemeral=True)
    print(f"[GARAGE] uid={uid} ha venduto {da_vendere}x pezzi di ricambio per {guadagno:,}€")


# =============================================================================
# COMANDI MOD
# =============================================================================

@bot.tree.command(name="resetcooldown", description="[MOD] Azzera il cooldown furto di un giocatore")
@app_commands.describe(utente="Il giocatore di cui resettare il cooldown", tipo="Quale cooldown azzerare")
@app_commands.choices(tipo=[
    app_commands.Choice(name="🏰 Villa",          value="villa"),
    app_commands.Choice(name="🏠 Casa",           value="casa"),
    app_commands.Choice(name="🚗 Macchina",       value="macchina"),
    app_commands.Choice(name="🏧 Bancomat",       value="bancomat"),
    app_commands.Choice(name="🍏 Minimarket",     value="minimarket"),
    app_commands.Choice(name="🔫 Armeria",        value="armeria"),
    app_commands.Choice(name="🏦 Banca Fleeca",   value="fleeca"),
    app_commands.Choice(name="💎 Gioielleria",    value="gioielleria"),
    app_commands.Choice(name="🔧 Officina Meccanica", value="meccanico"),
    app_commands.Choice(name="🏛️ Maze Bank",         value="mazebank"),
    app_commands.Choice(name="⚡ Tutti",              value="tutti"),
])
async def resetcooldown(interaction: discord.Interaction, utente: discord.Member, tipo: app_commands.Choice[str]):
    if not await safe_defer(interaction, ephemeral=True):
        return

    if not ha_permessi_staff(interaction):
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return

    # Esegui il reset PRIMA di qualsiasi chiamata Discord (non può fallire)
    if tipo.value == "tutti":
        furto_cooldown[utente.id] = {}
        for _pd, _td, _label in [
            (rapine_pendenti_bancomat,    _bancomat_tasks,    "bancomat"),
            (rapine_pendenti_minimarket,  _minimarket_tasks,  "minimarket"),
            (rapine_pendenti_armeria,     _armeria_tasks,     "armeria"),
            (rapine_pendenti_fleeca,      _fleeca_tasks,      "fleeca"),
            (rapine_pendenti_gioielleria, _gioielleria_tasks, "gioielleria"),
            (rapine_pendenti_mazebank,    _mazebank_tasks,    "mazebank"),
            (rapine_pendenti_meccanico,   _meccanico_tasks,   "meccanico"),
        ]:
            _pd.pop(utente.id, None)
            _t = _td.pop(utente.id, None)
            if _t and not _t.done():
                _t.cancel()
                print(f"[RESETCD] Task {_label} uid={utente.id} cancellato.")
        azzerati = "🏰 Villa, 🏠 Casa, 🚗 Macchina, 🏧 Bancomat, 🍏 Minimarket, 🔧 Meccanico, 🔫 Armeria, 🏦 Fleeca, 💎 Gioielleria, 🏛️ Maze Bank"
    else:
        cd = furto_cooldown.get(utente.id, {})
        cd.pop(tipo.value, None)
        furto_cooldown[utente.id] = cd
        _rapine_map = {
            "bancomat":    (rapine_pendenti_bancomat,    _bancomat_tasks),
            "minimarket":  (rapine_pendenti_minimarket,  _minimarket_tasks),
            "armeria":     (rapine_pendenti_armeria,     _armeria_tasks),
            "fleeca":      (rapine_pendenti_fleeca,      _fleeca_tasks),
            "gioielleria": (rapine_pendenti_gioielleria, _gioielleria_tasks),
            "mazebank":    (rapine_pendenti_mazebank,    _mazebank_tasks),
            "meccanico":   (rapine_pendenti_meccanico,   _meccanico_tasks),
        }
        if tipo.value in _rapine_map:
            _pd, _td = _rapine_map[tipo.value]
            _pd.pop(utente.id, None)
            _t = _td.pop(utente.id, None)
            if _t and not _t.done():
                _t.cancel()
                print(f"[RESETCD] Task {tipo.value} uid={utente.id} cancellato.")
        azzerati = tipo.name
    print(f"[RESETCD] uid={utente.id} tipo={tipo.value} → furto_cooldown ora: {furto_cooldown.get(utente.id, {})}")
    try:
        salva_dati()
    except Exception as e:
        print(f"[RESETCD] salva_dati fallito: {e}")

    await interaction.followup.send(f"✅ Azzerato **{azzerati}** per {utente.mention}.", ephemeral=True)


@bot.tree.command(name="resetordine", description="[MOD] Cancella l'ordine veicolo bloccato di un giocatore")
@app_commands.describe(utente="Il giocatore con l'ordine bloccato")
async def resetordine(interaction: discord.Interaction, utente: discord.Member):
    if not await safe_defer(interaction, ephemeral=True):
        return
    if not ha_permessi_staff(interaction):
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    ordine = ordini_pendenti_macchina.pop(utente.id, None)
    salva_dati()
    if ordine:
        modello = ordine.get("modello", "?")
        stato = "in attesa" if ordine.get("in_attesa") else ("foto ok" if ordine.get("foto_ok") else "aperto")
        await interaction.followup.send(
            f"🗑️ Ordine veicolo di {utente.mention} cancellato.\n"
            f"Modello: `{modello}` | Stato: `{stato}`",
            ephemeral=True
        )
        print(f"[RESETORDINE] Ordine di uid={utente.id} ({modello}) cancellato da {interaction.user}")
    else:
        await interaction.followup.send(
            f"ℹ️ {utente.mention} non ha nessun ordine veicolo attivo.", ephemeral=True
        )


@bot.tree.command(name="dai", description="[MOD] Dai contanti o oggetti a un giocatore")
@app_commands.describe(
    utente="Il giocatore a cui dare qualcosa",
    tipo="Cosa vuoi dare",
    quantita="Importo in € (per contanti) o quantità (per oggetti)"
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Contanti in tasca",                   value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",                   value="banca"),
    app_commands.Choice(name="Cacciavite",                          value="Cacciavite"),
    app_commands.Choice(name="Grimaldello",                         value="Grimaldello"),
    app_commands.Choice(name="Grimaldello Avanzato",                value="Grimaldello Avanzato"),
    app_commands.Choice(name="Piede di Porco",                      value="Piede di Porco"),
    app_commands.Choice(name="Torcia",                              value="Torcia"),
    app_commands.Choice(name="Sistema di Hacking",                  value="Sistema di Hacking"),
    app_commands.Choice(name="Slim Jim",                            value="Slim Jim"),
    app_commands.Choice(name="Dispositivo di Hacking Base",         value="Dispositivo di Hacking Base"),
    app_commands.Choice(name="Trapano",                             value="Trapano"),
    app_commands.Choice(name="Simulatore di Impronte Digitali",     value="Simulatore di Impronte Digitali"),
    app_commands.Choice(name="Pistola",                             value="Pistola"),
    app_commands.Choice(name="Gas Soporifero",                      value="Gas Soporifero"),
    app_commands.Choice(name="Dispositivo di Hacking Medio",        value="Dispositivo di Hacking Medio"),
    app_commands.Choice(name="Dispositivo di Hacking Avanzato",     value="Dispositivo di Hacking Avanzato"),
    app_commands.Choice(name="Lancia Termica",                      value="Lancia Termica"),
    app_commands.Choice(name="Trapano Pesante Professionale",       value="Trapano Pesante Professionale"),
    app_commands.Choice(name="Giubbotto Antiproiettile",            value="Giubbotto Antiproiettile"),
    app_commands.Choice(name="Mitra Compatto",                      value="Mitra Compatto"),
    app_commands.Choice(name="Pezzo di Ricambio",                   value="Pezzo di Ricambio"),
])
async def dai(interaction: discord.Interaction, utente: discord.Member, tipo: app_commands.Choice[str], quantita: int):
    if not await safe_defer(interaction): return
    if not ha_permessi_staff(interaction):
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    if utente.bot or quantita <= 0:
        await interaction.followup.send("❌ Valore non valido.", ephemeral=True)
        return

    valore = tipo.value
    if valore in ("portafoglio", "banca"):
        bil = get_balance(utente.id)
        bil[valore] += quantita
        salva_dati()
        dove = "in tasca" if valore == "portafoglio" else "in banca"
        embed = discord.Embed(
            title="💸 Fondi Accreditati",
            description=(
                f"Hai accreditato **`{quantita:,}€`** {dove} a {utente.mention}.\n\n"
                f"💵 Tasca: `{bil['portafoglio']:,}€` | 🏛️ Banca: `{bil['banca']:,}€`"
            ),
            color=discord.Color.green()
        )
    else:
        inv = get_inventario(utente.id)
        inv[valore] = inv.get(valore, 0) + quantita
        salva_dati()
        info = NEGOZIO.get(valore, {})
        emoji = info.get("emoji", "📦")
        embed = discord.Embed(
            title="🎒 Oggetto Consegnato",
            description=(
                f"Hai dato **{quantita}x {emoji} {valore}** a {utente.mention}.\n\n"
                f"🎒 Ha ora `{inv[valore]}x {valore}` in inventario."
            ),
            color=discord.Color.green()
        )
    embed.set_footer(text="Tokyo Horizon RP | Pannello Staff")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="togli", description="[MOD] Rimuovi contanti o oggetti da un giocatore")
@app_commands.describe(
    utente="Il giocatore a cui rimuovere qualcosa",
    tipo="Cosa vuoi togliere",
    quantita="Importo in € (per contanti) o quantità (per oggetti)"
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Contanti in tasca",                   value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",                   value="banca"),
    app_commands.Choice(name="Cacciavite",                          value="Cacciavite"),
    app_commands.Choice(name="Grimaldello",                         value="Grimaldello"),
    app_commands.Choice(name="Grimaldello Avanzato",                value="Grimaldello Avanzato"),
    app_commands.Choice(name="Piede di Porco",                      value="Piede di Porco"),
    app_commands.Choice(name="Torcia",                              value="Torcia"),
    app_commands.Choice(name="Sistema di Hacking",                  value="Sistema di Hacking"),
    app_commands.Choice(name="Slim Jim",                            value="Slim Jim"),
    app_commands.Choice(name="Dispositivo di Hacking Base",         value="Dispositivo di Hacking Base"),
    app_commands.Choice(name="Trapano",                             value="Trapano"),
    app_commands.Choice(name="Simulatore di Impronte Digitali",     value="Simulatore di Impronte Digitali"),
    app_commands.Choice(name="Pistola",                             value="Pistola"),
    app_commands.Choice(name="Gas Soporifero",                      value="Gas Soporifero"),
    app_commands.Choice(name="Dispositivo di Hacking Medio",        value="Dispositivo di Hacking Medio"),
    app_commands.Choice(name="Dispositivo di Hacking Avanzato",     value="Dispositivo di Hacking Avanzato"),
    app_commands.Choice(name="Lancia Termica",                      value="Lancia Termica"),
    app_commands.Choice(name="Trapano Pesante Professionale",       value="Trapano Pesante Professionale"),
    app_commands.Choice(name="Giubbotto Antiproiettile",            value="Giubbotto Antiproiettile"),
    app_commands.Choice(name="Mitra Compatto",                      value="Mitra Compatto"),
    app_commands.Choice(name="Pezzo di Ricambio",                   value="Pezzo di Ricambio"),
])
async def togli(interaction: discord.Interaction, utente: discord.Member, tipo: app_commands.Choice[str], quantita: int):
    if not await safe_defer(interaction): return
    raw = getattr(interaction.user, '_roles', None)
    ha_perm = ha_permessi_staff(interaction) or (raw is not None and RUOLO_POLIZIA_HARDCODED in raw)
    if not ha_perm:
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    if utente.bot or quantita <= 0:
        await interaction.followup.send("❌ Valore non valido.", ephemeral=True)
        return

    valore = tipo.value
    if valore in ("portafoglio", "banca"):
        bil = get_balance(utente.id)
        disponibile = bil[valore]
        rimosso = min(quantita, disponibile)
        bil[valore] = max(0, bil[valore] - quantita)
        salva_dati()
        dove = "in tasca" if valore == "portafoglio" else "in banca"
        avviso = f"\n⚠️ Aveva solo `{disponibile:,}€` — rimosso il disponibile." if rimosso < quantita else ""
        embed = discord.Embed(
            title="💸 Fondi Rimossi",
            description=(
                f"Hai rimosso **`{rimosso:,}€`** {dove} da {utente.mention}.{avviso}\n\n"
                f"💵 Tasca: `{bil['portafoglio']:,}€` | 🏛️ Banca: `{bil['banca']:,}€`"
            ),
            color=discord.Color.red()
        )
    else:
        inv = get_inventario(utente.id)
        attuale = inv.get(valore, 0)
        if attuale == 0:
            await interaction.followup.send(f"❌ {utente.mention} non ha nessun **{valore}** in inventario.", ephemeral=True)
            return
        rimosso = min(quantita, attuale)
        inv[valore] = attuale - rimosso
        salva_dati()
        TUTTI_ITEMS = {**NEGOZIO, **MERCATO_NERO, **MERCATO_ARMI}
        info = TUTTI_ITEMS.get(valore, {})
        emoji = info.get("emoji", "📦")
        avviso = f"\n⚠️ Ne aveva solo `{attuale}` — rimossi tutti." if rimosso < quantita else ""
        embed = discord.Embed(
            title="🗑️ Oggetto Rimosso",
            description=(
                f"Hai rimosso **{rimosso}x {emoji} {valore}** da {utente.mention}.{avviso}\n\n"
                f"🎒 Ne ha ora `{inv[valore]}x` in inventario."
            ),
            color=discord.Color.red()
        )
    embed.set_footer(text="Tokyo Horizon RP | Pannello Staff")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setcanale", description="[MOD] Imposta questo canale come canale dedicato ai furti veicolo")
async def setcanale(interaction: discord.Interaction):
    global canale_furti_id
    if not await safe_defer(interaction): return
    if not ha_permessi_staff(interaction):
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    canale_furti_id = interaction.channel_id
    salva_dati()
    embed = discord.Embed(
        title="✅ Canale Furti Veicolo Impostato",
        description=(
            f"D'ora in poi i furti veicolo potranno essere effettuati **solo** in <#{interaction.channel_id}>.\n\n"
            f"Gli utenti che useranno `/furto macchina` in altri canali riceveranno un errore."
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Tokyo Horizon RP | Pannello Staff")
    await interaction.followup.send(embed=embed, ephemeral=True)



@bot.tree.command(name="cooldown", description="Controlla i tuoi tempi di attesa per i furti")
@app_commands.describe(utente="[MOD] Controlla il cooldown di un altro giocatore (opzionale)")
async def cooldown_cmd(interaction: discord.Interaction, utente: discord.Member = None):
    await interaction.response.defer(ephemeral=True)

    if utente is not None and not ha_permessi_staff(interaction):
        await interaction.followup.send("❌ Solo lo staff può controllare il cooldown di altri giocatori.", ephemeral=True)
        return

    target = utente if utente is not None else interaction.user
    uid = target.id
    ora = time.time()

    furti = {
        "villa":       {"label": "🏰 Villa",              "cooldown": 4 * 3600},
        "casa":        {"label": "🏠 Casa",               "cooldown": 4 * 3600},
        "macchina":    {"label": "🚗 Macchina",           "cooldown": 2 * 3600},
        "bancomat":    {"label": "🏧 Bancomat",           "cooldown": 12 * 3600},
        "minimarket":  {"label": "🍏 Minimarket",         "cooldown": 24 * 3600},
        "meccanico":   {"label": "🔧 Officina Meccanica", "cooldown": 48 * 3600},
        "armeria":     {"label": "🔫 Ammu-Nation",        "cooldown": 24 * 3600},
        "fleeca":      {"label": "🏦 Banca Fleeca",       "cooldown": 48 * 3600},
        "gioielleria": {"label": "💎 Gioielleria",        "cooldown": 96 * 3600},
        "mazebank":    {"label": "🏛️ Maze Bank",          "cooldown": 168 * 3600},
    }

    righe = []
    cd_utente = furto_cooldown.get(uid, {})

    for tipo, info in furti.items():
        ultimo = cd_utente.get(tipo, 0)
        trascorso = ora - ultimo
        rimanente = info["cooldown"] - trascorso

        if rimanente <= 0:
            righe.append(f"{info['label']} — ✅ **Disponibile**")
        else:
            ore = int(rimanente // 3600)
            minuti = int((rimanente % 3600) // 60)
            secondi = int(rimanente % 60)
            if ore >= 24:
                giorni = ore // 24
                ore_r = ore % 24
                tempo_str = f"{giorni}g {ore_r}h {minuti}m"
            elif ore > 0:
                tempo_str = f"{ore}h {minuti}m"
            else:
                tempo_str = f"{minuti}m {secondi}s"
            righe.append(f"{info['label']} — ⏳ `{tempo_str}`")

    # Blocco attività criminale post-colpo
    lock_rem = get_criminal_lock(uid)
    if lock_rem > 0:
        righe.append(f"\n🔒 **Blocco attività criminale** — ⏳ `{formatta_durata(lock_rem)}`")

    nome = target.display_name
    embed = discord.Embed(
        title=f"⏱️ Cooldown Furti — {nome}",
        description="\n".join(righe),
        color=discord.Color.orange()
    )
    embed.set_footer(text="Tokyo Horizon RP | Sistema Furto")
    await interaction.followup.send(embed=embed, ephemeral=True)



# =============================================================================
# RAPINA — BANCOMAT
# =============================================================================

LOOT_BANCOMAT            = 7000
LOOT_MINIMARKET          = 15_000
_minimarket_in_corso: set = set()
_minimarket_tasks: dict   = {}
ATM_IMAGE = "attached_assets/IMG_1429_1781378756942.jpeg"
CANALE_POLIZIA_HARDCODED = 1515439682333180015   # canale #RAPINE (criminale)
CANALE_FDO               = 1513574802156425267   # canale allerta FDO
CANALE_STAFF_VEICOLI     = 1515676328622428310   # canale revisione consegna veicoli (staff)
CANALE_PG                = 1516143484145242253   # canale richiesta personaggio (whitelist)
CANALE_REVISIONE_PG      = 1516174570837770241   # canale revisione staff PG (whitelist)
CANALE_ESITO_PG          = 1516168066227241073   # canale esito PG (pubblico)
RUOLO_GESTORE_WL         = 1514818877014409227   # ruolo @gestore wl
CANALE_CARTA             = 1516151385064869928   # canale carta d'identità
CANALE_MECCANICO_RICHIESTE = 1517160752123875339  # canale richieste modifiche veicolo (player)
CANALE_MECCANICO_STAFF    = 1517200240510238900  # canale staff meccanico (accetta/rifiuta)
RUOLO_POLIZIA_HARDCODED  = 1515441313216991262
RUOLO_CITTADINO          = 1513574080232558804   # ruolo assegnato al completamento della carta d'identità

# Tiene traccia di quali uid hanno già un task accredita_bancomat in esecuzione
# per evitare doppi accrediti in caso di istanze multiple o on_ready duplicati
_bancomat_in_corso: set = set()
# task bancomat attivi per uid → cancellabili da resetcooldown
_bancomat_tasks: dict = {}

LOOT_ARMERIA     = 50_000
LOOT_FLEECA      = 250_000
LOOT_GIOIELLERIA = 500_000
LOOT_MAZEBANK    = 1_000_000
LOOT_MECCANICO   = 35_000

_armeria_in_corso: set     = set()
_armeria_tasks: dict       = {}
_fleeca_in_corso: set      = set()
_fleeca_tasks: dict        = {}
_gioielleria_in_corso: set = set()
_gioielleria_tasks: dict   = {}
_mazebank_in_corso: set    = set()
_mazebank_tasks: dict      = {}
_meccanico_in_corso: set   = set()
_meccanico_tasks: dict     = {}


async def accredita_bancomat(criminal_uid: int, delay: float):
    """Aspetta `delay` secondi, poi accredita il bottino e notifica nel canale."""
    if criminal_uid in _bancomat_in_corso:
        print(f"[BANCOMAT] uid={criminal_uid} già in elaborazione — task duplicato ignorato.")
        return
    _bancomat_in_corso.add(criminal_uid)
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        # Controllo in-memory: resettato dallo staff durante il sleep?
        if criminal_uid not in rapine_pendenti_bancomat:
            print(f"[BANCOMAT] uid={criminal_uid} rimosso dalla memoria durante il sleep (reset staff) — skip.")
            return
        # Rilegge il file per stato fresco (prevenzione doppio accredito multi-istanza)
        try:
            with open(DATI_FILE, "r") as _f:
                _dati_freschi = json.load(_f)
            _rapine_nel_file = {int(k): v for k, v in _dati_freschi.get("rapine_pendenti", {}).items()}
        except Exception as _e:
            print(f"[BANCOMAT] Errore lettura JSON fresco: {_e} — uso memoria")
            _rapine_nel_file = rapine_pendenti_bancomat
        if criminal_uid not in _rapine_nel_file:
            print(f"[BANCOMAT] uid={criminal_uid} non più presente nel file — già accreditato o resettato, skip.")
            rapine_pendenti_bancomat.pop(criminal_uid, None)
            return
        bil = get_balance(criminal_uid)
        bil["banca"] += LOOT_BANCOMAT
        furto_cooldown.setdefault(criminal_uid, {})["bancomat"] = time.time()
        rapine_pendenti_bancomat.pop(criminal_uid, None)
        salva_dati()
        print(f"[BANCOMAT] Bottino accreditato a uid={criminal_uid}.")
        testo = (
            f"✅ <@{criminal_uid}> **Scassinamento completato!**\n"
            f"💰 **`{LOOT_BANCOMAT:,}€`** sono stati accreditati in banca.\n"
            f"🏃 Puoi scappare adesso — buona fuga!"
        )
        inviato = False
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo)
            inviato = True
        except Exception as e:
            print(f"[BANCOMAT] Messaggio canale fallito: {e}")
        if not inviato:
            try:
                utente = await bot.fetch_user(criminal_uid)
                await utente.send(
                    f"✅ **Scassinamento completato!**\n"
                    f"💰 **`{LOOT_BANCOMAT:,}€`** sono stati accreditati in banca.\n"
                    f"🏃 Puoi scappare adesso — buona fuga!"
                )
            except Exception as e:
                print(f"[BANCOMAT] DM fallback bottino fallito: {e}")
    finally:
        _bancomat_in_corso.discard(criminal_uid)
        _bancomat_tasks.pop(criminal_uid, None)


class AccettaRapinaView(discord.ui.View):
    def __init__(self, criminal_uid: int, nome_pg: str, posizione: str, partecipanti: str):
        super().__init__(timeout=600)
        self.criminal_uid = criminal_uid
        self.nome_pg = nome_pg
        self.posizione = posizione
        self.partecipanti = partecipanti
        self.accettata = False
        self.message: discord.Message = None

    @discord.ui.button(label="Accetta Servizio", style=discord.ButtonStyle.success, emoji="🚔")
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        role_ids = [r.id for r in member.roles] if member else []
        if RUOLO_POLIZIA_HARDCODED not in role_ids:
            await interaction.response.send_message("❌ Non hai il ruolo necessario per accettare il servizio.", ephemeral=True)
            return
        if self.accettata:
            await interaction.response.send_message("❌ Questa rapina è già stata presa in carico!", ephemeral=True)
            return
        self.accettata = True
        self.stop()

        for child in self.children:
            child.disabled = True

        fdo_nome = interaction.user.display_name
        criminal_uid = self.criminal_uid

        embed = discord.Embed(
            title="🚔 RAPINA IN CARICO — BANCOMAT 🏧",
            description=(
                f"✅ **Agente in servizio:** {interaction.user.mention}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n"
                f"👥 **Partecipanti criminale:** `{self.partecipanti}`\n\n"
                f"⏳ **Scassinamento in corso — 4 minuti.**\n"
                f"💰 Il bottino di `{LOOT_BANCOMAT:,}€` verrà accreditato al termine.\n"
                f"🏃 Dopo 4 minuti il criminale può scappare."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina in Corso")
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

        # Salva la rapina nel JSON così sopravvive ai riavvii
        rapine_pendenti_bancomat[criminal_uid] = {"accepted_at": time.time()}
        salva_dati()

        # Messaggio scassinamento iniziato — canale con fallback DM
        testo_inizio = (
            f"🚔 <@{criminal_uid}> Un FDO (**{fdo_nome}**) ha accettato il servizio — **scassinamento iniziato!**\n"
            f"⏳ Aspetta **4 minuti** mentre scarti il bancomat.\n"
            f"💰 Riceverai **`{LOOT_BANCOMAT:,}€`** in banca allo scadere del tempo.\n"
            f"⚠️ Non scappare prima dei 4 minuti!"
        )
        inviato_inizio = False
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo_inizio)
            inviato_inizio = True
        except Exception as e:
            print(f"[BANCOMAT] Messaggio canale inizio fallito: {e}")
        if not inviato_inizio:
            try:
                utente = await bot.fetch_user(criminal_uid)
                await utente.send(
                    f"🚔 Un FDO (**{fdo_nome}**) ha accettato il servizio — **scassinamento iniziato!**\n"
                    f"⏳ Aspetta **4 minuti** mentre scarti il bancomat.\n"
                    f"💰 Riceverai **`{LOOT_BANCOMAT:,}€`** in banca allo scadere del tempo.\n"
                    f"⚠️ Non scappare prima dei 4 minuti!"
                )
            except Exception as e:
                print(f"[BANCOMAT] DM fallback inizio fallito: {e}")

        # Task persistente: usa la funzione condivisa (sopravvive ai restart via on_ready)
        task = asyncio.create_task(accredita_bancomat(criminal_uid, 240))
        _bancomat_tasks[criminal_uid] = task

    async def on_timeout(self):
        inv = get_inventario(self.criminal_uid)
        inv["Piede di Porco"] = inv.get("Piede di Porco", 0) + 1
        salva_dati()

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="⌛ RAPINA ANNULLATA — Nessun FDO disponibile",
            description=(
                f"La rapina di `{self.nome_pg}` è scaduta dopo **10 minuti** senza risposta FDO.\n\n"
                f"📍 **Posizione:** `{self.posizione}`\n\n"
                f"🪓 Il `Piede di Porco` è stato restituito al criminale.\n"
                f"⏱️ Il cooldown è stato azzerato — può riprovare."
            ),
            color=discord.Color.dark_gray()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina Scaduta")
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[])
            except Exception as e:
                print(f"[BANCOMAT] Edit timeout fallito: {e}")

        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(
                f"⌛ <@{self.criminal_uid}> Nessun FDO ha risposto alla tua rapina al bancomat entro 10 minuti.\n"
                f"🪓 Il tuo **Piede di Porco** è stato restituito e il cooldown azzerato.\n"
                f"Puoi riprovare quando vuoi!"
            )
        except Exception as e:
            print(f"[BANCOMAT] Messaggio timeout fallito: {e}")


class BancomatModal(discord.ui.Modal, title="🏧 Verbale di Rapina — Bancomat"):
    nome_pg = discord.ui.TextInput(
        label="Nome del tuo personaggio",
        placeholder="Es: Marco Rossi",
        min_length=2,
        max_length=50,
    )
    posizione = discord.ui.TextInput(
        label="Posizione del bancomat",
        placeholder="Es: Via del Mare 14, Downtown Los Santos",
        min_length=3,
        max_length=100,
    )
    partecipanti = discord.ui.TextInput(
        label="Partecipi solo o in coppia?",
        placeholder="Solo  /  In coppia con [nome personaggio]",
        min_length=4,
        max_length=80,
    )

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        uid  = self.uid
        nome = self.nome_pg.value.strip()
        pos  = self.posizione.value.strip()
        part = self.partecipanti.value.strip()

        inv = get_inventario(uid)
        if inv.get("Piede di Porco", 0) <= 0:
            await interaction.followup.send("❌ Non hai il `Piede di Porco` nell'inventario! Acquistalo con `/negozio`.", ephemeral=True)
            return
        if inv.get("Pistola", 0) <= 0:
            await interaction.followup.send("❌ Non hai la `Pistola` nell'inventario! Acquistala con `/compraarmi`.", ephemeral=True)
            return

        # Prepara embed conferma criminale
        embed_ok = discord.Embed(
            title="✅ Rapina Bancomat Inviata!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"🪓 Hai usato **1x Piede di Porco** (consumato) + 🔫 **Pistola** (mantenuta).\n"
                f"📡 La notifica è stata inviata agli FDO — aspetta che uno accetti.\n"
                f"⏳ Una volta accettata, iniziano **4 minuti** di scassinamento.\n"
                f"💰 I **`{LOOT_BANCOMAT:,}€`** ti vengono accreditati in banca **allo scadere dei 4 minuti**.\n\n"
                f"🚫 La rapina si annulla se nessun FDO risponde entro **10 minuti** — "
                f"il Piede di Porco ti viene restituito.\n"
                f"⚠️ Equipaggiamento consentito: **Piede di Porco + Pistola**"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")

        # Prepara embed notifica FDO
        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 RAPINA IN CORSO — BANCOMAT 🏧",
            description=(
                f"🦹 **Criminale:** `{nome}`\n"
                f"📍 **Posizione dichiarata:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"👮 **FDO richiesti:** Max **1 FDO**\n"
                f"⚔️ **Equipaggiamento criminale:** Piede di Porco + Pistola\n"
                f"⏱️ **Scassinamento:** 4 minuti | Fuga immediata (nessun dialogo)\n"
                f"💰 **Bottino:** `{LOOT_BANCOMAT:,}€` in contanti puliti\n\n"
                f"⏳ Clicca **Accetta Servizio** entro 10 minuti o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — 10 minuti per rispondere")

        view = AccettaRapinaView(uid, nome, pos, part)

        # Consuma solo il Piede di Porco — la Pistola rimane in inventario
        inv["Piede di Porco"] -= 1
        if inv["Piede di Porco"] == 0:
            del inv["Piede di Porco"]
        salva_dati()

        # 1) Conferma al criminale (pubblica via followup — non richiede Send Messages)
        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[BANCOMAT] Followup criminale fallito: {e}")
            try:
                await interaction.followup.send(embed=embed_ok, ephemeral=True)
            except Exception:
                pass

        # 2) Chiedi screenshot radar — il criminale deve mandare la posizione sulla mappa
        try:
            await interaction.followup.send(
                "📍 **Manda subito uno screenshot del radar** (apri la mappa in-game) "
                "per far vedere la tua posizione esatta agli FDO!",
                ephemeral=False
            )
        except Exception as e:
            print(f"[BANCOMAT] Messaggio radar fallito: {e}")

        # 3) Notifica FDO nel canale allerta FDO dedicato
        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            print(f"[BANCOMAT] Canale FDO trovato: #{canale_fdo.name} (id={canale_fdo.id})")
            msg = await canale_fdo.send(
                content=mention,
                embed=embed_pol,
                view=view,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            view.message = msg
            print(f"[BANCOMAT] Notifica FDO inviata in #{canale_fdo.name} ✅")
        except discord.Forbidden as e:
            print(f"[BANCOMAT] ❌ Permessi mancanti nel canale FDO (id={CANALE_FDO}): {e}")
            try:
                await interaction.followup.send(
                    f"⚠️ **Errore:** Il bot non ha i permessi per scrivere nel canale FDO (`{CANALE_FDO}`). "
                    f"Aggiungi il permesso **Invia Messaggi** al bot in quel canale.",
                    ephemeral=True
                )
            except Exception:
                pass
        except discord.NotFound as e:
            print(f"[BANCOMAT] ❌ Canale FDO non trovato (id={CANALE_FDO}): {e}")
            try:
                await interaction.followup.send(
                    f"⚠️ **Errore:** Canale FDO non trovato (id `{CANALE_FDO}`). Controlla l'ID.",
                    ephemeral=True
                )
            except Exception:
                pass
        except Exception as e:
            print(f"[BANCOMAT] ❌ Notifica FDO fallita ({type(e).__name__}): {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        code = getattr(getattr(error, "original", error), "code", None)
        print(f"[BANCOMAT MODAL] {type(error).__name__} (code={code}): {error}")
        if code in (10062, 40060):
            return  # Errore transiente — non mostrare niente
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


# =============================================================================
# RAPINA — MINIMARKET
# =============================================================================

async def accredita_minimarket(criminal_uid: int, delay: float):
    """Aspetta `delay` secondi, poi accredita il bottino del minimarket."""
    if criminal_uid in _minimarket_in_corso:
        print(f"[MINIMARKET] uid={criminal_uid} già in elaborazione — task duplicato ignorato.")
        return
    _minimarket_in_corso.add(criminal_uid)
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        # Controllo in-memory: resettato dallo staff durante il sleep?
        if criminal_uid not in rapine_pendenti_minimarket:
            print(f"[MINIMARKET] uid={criminal_uid} rimosso dalla memoria durante il sleep (reset staff) — skip.")
            return
        # Rilegge il file per stato fresco
        try:
            with open(DATI_FILE, "r") as _f:
                _dati_freschi = json.load(_f)
            _rapine_nel_file = {int(k): v for k, v in _dati_freschi.get("rapine_pendenti_minimarket", {}).items()}
        except Exception as _e:
            print(f"[MINIMARKET] Errore lettura JSON fresco: {_e} — uso memoria")
            _rapine_nel_file = rapine_pendenti_minimarket
        if criminal_uid not in _rapine_nel_file:
            print(f"[MINIMARKET] uid={criminal_uid} non più nel file — già accreditato o resettato, skip.")
            rapine_pendenti_minimarket.pop(criminal_uid, None)
            return
        bil = get_balance(criminal_uid)
        bil["banca"] += LOOT_MINIMARKET
        furto_cooldown.setdefault(criminal_uid, {})["minimarket"] = time.time()
        rapine_pendenti_minimarket.pop(criminal_uid, None)
        salva_dati()
        print(f"[MINIMARKET] Bottino accreditato a uid={criminal_uid}.")
        testo = (
            f"✅ <@{criminal_uid}> **Colpo al Minimarket completato!**\n"
            f"💰 **`{LOOT_MINIMARKET:,}€`** sono stati accreditati in banca.\n"
            f"🏃 Il bottino è tuo — dialogo obbligatorio di **almeno 2 minuti** con gli FDO!"
        )
        inviato = False
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo)
            inviato = True
        except Exception as e:
            print(f"[MINIMARKET] Messaggio canale fallito: {e}")
        if not inviato:
            try:
                utente = await bot.fetch_user(criminal_uid)
                await utente.send(
                    f"✅ **Colpo al Minimarket completato!**\n"
                    f"💰 **`{LOOT_MINIMARKET:,}€`** sono stati accreditati in banca.\n"
                    f"🏃 Dialogo obbligatorio di almeno **2 minuti** con gli FDO!"
                )
            except Exception as e:
                print(f"[MINIMARKET] DM fallback bottino fallito: {e}")
    finally:
        _minimarket_in_corso.discard(criminal_uid)
        _minimarket_tasks.pop(criminal_uid, None)


class AccettaRapinaMinimarketView(discord.ui.View):
    def __init__(self, criminal_uid: int, nome_pg: str, posizione: str, nome_complice: str, strumento: str):
        super().__init__(timeout=600)
        self.criminal_uid = criminal_uid
        self.nome_pg = nome_pg
        self.posizione = posizione
        self.nome_complice = nome_complice
        self.strumento = strumento
        self.fdo_list: list = []      # nomi FDO che hanno cliccato
        self.avviata = False          # scassinamento avviato (2 FDO raggiunti)
        self.message: discord.Message = None

    @discord.ui.button(label="Accetta Servizio (0/2)", style=discord.ButtonStyle.success, emoji="🚔")
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        role_ids = [r.id for r in member.roles] if member else []
        if RUOLO_POLIZIA_HARDCODED not in role_ids:
            await interaction.response.send_message("❌ Non hai il ruolo necessario per accettare il servizio.", ephemeral=True)
            return
        if self.avviata:
            await interaction.response.send_message("❌ Lo scassinamento è già iniziato!", ephemeral=True)
            return
        fdo_nome = interaction.user.display_name
        if fdo_nome in self.fdo_list:
            await interaction.response.send_message("❌ Hai già accettato questo servizio!", ephemeral=True)
            return

        self.fdo_list.append(fdo_nome)
        criminal_uid = self.criminal_uid
        emoji_str = "🪛" if self.strumento == "Cacciavite" else "🪓"

        if len(self.fdo_list) == 1:
            # Primo FDO — aggiorna embed e label, bottone rimane attivo
            button.label = "Accetta Servizio (1/2)"
            embed = discord.Embed(
                title="🚔 IN ATTESA 2° FDO — MINIMARKET 🍏",
                description=(
                    f"✅ **1° Agente:** {interaction.user.mention}\n"
                    f"⏳ **In attesa del 2° FDO…**\n\n"
                    f"🦹 **Criminale:** `{self.nome_pg}`\n"
                    f"🤝 **Complice:** `{self.nome_complice}`\n"
                    f"📍 **Posizione:** `{self.posizione}`\n"
                    f"{emoji_str} **Strumento:** `{self.strumento}`\n\n"
                    f"👮 Serve un **2° FDO** per avviare lo scassinamento."
                ),
                color=discord.Color.yellow()
            )
            embed.set_footer(text="Tokyo Horizon RP | In attesa del 2° agente")
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
            return

        # Secondo FDO — avvia lo scassinamento
        self.avviata = True
        self.stop()
        for child in self.children:
            child.disabled = True

        fdo1, fdo2 = self.fdo_list[0], self.fdo_list[1]
        embed = discord.Embed(
            title="🚔 RAPINA IN CARICO — MINIMARKET 🍏",
            description=(
                f"✅ **1° Agente:** `{fdo1}`\n"
                f"✅ **2° Agente:** {interaction.user.mention}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"🤝 **Complice:** `{self.nome_complice}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n"
                f"{emoji_str} **Strumento:** `{self.strumento}`\n\n"
                f"⏳ **Scassinamento in corso — 4 minuti.**\n"
                f"💰 Il bottino di `{LOOT_MINIMARKET:,}€` verrà accreditato al termine.\n"
                f"⚠️ Dopo i 4 minuti dialogo obbligatorio di **2 minuti** con gli FDO."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina in Corso")
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

        rapine_pendenti_minimarket[criminal_uid] = {"accepted_at": time.time()}
        salva_dati()

        testo_inizio = (
            f"🚔 <@{criminal_uid}> **2 FDO hanno accettato** (`{fdo1}` e `{fdo2}`) — **scassinamento minimarket iniziato!**\n"
            f"⏳ Aspetta **4 minuti** per forzare la cassa.\n"
            f"💰 Riceverai **`{LOOT_MINIMARKET:,}€`** in banca allo scadere del tempo.\n"
            f"⚠️ Dopo i 4 minuti devi dialogare con gli FDO per almeno **2 minuti**!"
        )
        inviato_inizio = False
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo_inizio)
            inviato_inizio = True
        except Exception as e:
            print(f"[MINIMARKET] Messaggio canale inizio fallito: {e}")
        if not inviato_inizio:
            try:
                utente = await bot.fetch_user(criminal_uid)
                await utente.send(
                    f"🚔 **2 FDO hanno accettato** — **scassinamento minimarket iniziato!**\n"
                    f"⏳ Aspetta **4 minuti** per forzare la cassa.\n"
                    f"💰 Riceverai **`{LOOT_MINIMARKET:,}€`** in banca allo scadere del tempo.\n"
                    f"⚠️ Dopo i 4 minuti devi dialogare con gli FDO per almeno **2 minuti**!"
                )
            except Exception as e:
                print(f"[MINIMARKET] DM fallback inizio fallito: {e}")

        task = asyncio.create_task(accredita_minimarket(criminal_uid, 240))
        _minimarket_tasks[criminal_uid] = task

    async def on_timeout(self):
        if not self.avviata:
            inv = get_inventario(self.criminal_uid)
            inv[self.strumento] = inv.get(self.strumento, 0) + 1
            salva_dati()

        for child in self.children:
            child.disabled = True

        emoji_str = "🪛" if self.strumento == "Cacciavite" else "🪓"
        n_fdo = len(self.fdo_list)
        if n_fdo == 0:
            motivo = "Nessun FDO ha risposto entro 10 minuti."
        else:
            motivo = f"Solo **1 FDO** ha accettato (`{self.fdo_list[0]}`) — servono 2 agenti."

        embed = discord.Embed(
            title="⌛ RAPINA ANNULLATA — FDO insufficienti",
            description=(
                f"{motivo}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n\n"
                f"{emoji_str} Il `{self.strumento}` è stato restituito al criminale.\n"
                f"⏱️ Il cooldown è stato azzerato — può riprovare."
            ),
            color=discord.Color.dark_gray()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina Scaduta")
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[])
            except Exception as e:
                print(f"[MINIMARKET] Edit timeout fallito: {e}")

        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(
                f"⌛ <@{self.criminal_uid}> La rapina al minimarket è annullata — {motivo}\n"
                f"{emoji_str} Il tuo **{self.strumento}** è stato restituito e il cooldown azzerato.\n"
                f"Puoi riprovare quando vuoi!"
            )
        except Exception as e:
            print(f"[MINIMARKET] Messaggio timeout fallito: {e}")


class MinimarketModal(discord.ui.Modal, title="🍏 Verbale di Rapina — Minimarket"):
    nome_pg = discord.ui.TextInput(
        label="Nome del tuo personaggio",
        placeholder="Es: Marco Rossi",
        min_length=2,
        max_length=50,
    )
    posizione = discord.ui.TextInput(
        label="Posizione del minimarket",
        placeholder="Es: Via Roma 8, Strawberry, LS",
        min_length=3,
        max_length=100,
    )
    nome_complice = discord.ui.TextInput(
        label="Nome del tuo 2° complice (obbligatorio)",
        placeholder="Es: Luigi Bianchi",
        min_length=2,
        max_length=50,
    )

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        uid      = self.uid
        nome     = self.nome_pg.value.strip()
        pos      = self.posizione.value.strip()
        complice = self.nome_complice.value.strip()

        inv = get_inventario(uid)
        # Determina strumento disponibile (preferisce Cacciavite)
        if inv.get("Cacciavite", 0) > 0:
            strumento = "Cacciavite"
            emoji_str = "🪛"
        elif inv.get("Piede di Porco", 0) > 0:
            strumento = "Piede di Porco"
            emoji_str = "🪓"
        else:
            await interaction.followup.send(
                "❌ Non hai gli strumenti! Serve **`1x Cacciavite`** o **`1x Piede di Porco`**. Acquistali con `/negozio`.",
                ephemeral=True
            )
            return
        if inv.get("Pistola", 0) <= 0:
            await interaction.followup.send(
                "❌ Non hai la `Pistola` nell'inventario! Acquistala con `/compraarmi`.", ephemeral=True
            )
            return

        embed_ok = discord.Embed(
            title="✅ Rapina Minimarket Inviata!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"🤝 **Complice:** `{complice}`\n"
                f"📍 **Posizione:** `{pos}`\n\n"
                f"{emoji_str} Hai usato **1x {strumento}** (consumato) + 🔫 **Pistola** (mantenuta).\n"
                f"📡 La notifica è stata inviata agli FDO — aspetta che **2 FDO** accettino.\n"
                f"⏳ Una volta confermata da 2 agenti, iniziano **4 minuti** di scassinamento.\n"
                f"💰 I **`{LOOT_MINIMARKET:,}€`** ti vengono accreditati in banca **allo scadere dei 4 minuti**.\n"
                f"⚠️ Dopo i 4 minuti dialogo obbligatorio con gli FDO per almeno **2 minuti**.\n\n"
                f"🚫 La rapina si annulla se non si raggiungono 2 FDO entro **10 minuti** — "
                f"lo strumento ti viene restituito.\n"
                f"⚠️ Equipaggiamento consentito: **{strumento} + Pistola** (vietati caschi e giubbotti)"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")

        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 RAPINA IN CORSO — MINIMARKET 🍏",
            description=(
                f"🦹 **Criminale:** `{nome}`\n"
                f"🤝 **Complice:** `{complice}`\n"
                f"📍 **Posizione dichiarata:** `{pos}`\n\n"
                f"👮 **FDO richiesti:** **2 FDO** devono cliccare il bottone\n"
                f"⚔️ **Equipaggiamento criminale:** {strumento} + Pistola (vietati caschi e giubbotti)\n"
                f"⏱️ **Scassinamento:** 4 minuti | Dialogo minimo: 2 minuti\n"
                f"🚫 **Ostaggi:** Non consentiti\n"
                f"💰 **Bottino:** `{LOOT_MINIMARKET:,}€` in banca\n\n"
                f"⏳ **Devono cliccare 2 FDO** entro 10 minuti o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — servono 2 agenti")

        view = AccettaRapinaMinimarketView(uid, nome, pos, complice, strumento)

        # Consuma lo strumento — la Pistola rimane in inventario
        inv[strumento] -= 1
        if inv[strumento] == 0:
            del inv[strumento]
        salva_dati()

        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[MINIMARKET] Followup criminale fallito: {e}")
            try:
                await interaction.followup.send(embed=embed_ok, ephemeral=True)
            except Exception:
                pass

        try:
            await interaction.followup.send(
                "📍 **Manda subito uno screenshot del radar** per far vedere la tua posizione esatta agli FDO!",
                ephemeral=False
            )
        except Exception as e:
            print(f"[MINIMARKET] Messaggio radar fallito: {e}")

        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            msg = await canale_fdo.send(
                content=mention,
                embed=embed_pol,
                view=view,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            view.message = msg
            print(f"[MINIMARKET] Notifica FDO inviata in #{canale_fdo.name} ✅")
        except discord.Forbidden as e:
            print(f"[MINIMARKET] ❌ Permessi mancanti nel canale FDO (id={CANALE_FDO}): {e}")
            try:
                await interaction.followup.send(
                    f"⚠️ **Errore:** Il bot non ha i permessi per scrivere nel canale FDO (`{CANALE_FDO}`).",
                    ephemeral=True
                )
            except Exception:
                pass
        except discord.NotFound as e:
            print(f"[MINIMARKET] ❌ Canale FDO non trovato (id={CANALE_FDO}): {e}")
            try:
                await interaction.followup.send(
                    f"⚠️ **Errore:** Canale FDO non trovato (id `{CANALE_FDO}`).",
                    ephemeral=True
                )
            except Exception:
                pass
        except Exception as e:
            print(f"[MINIMARKET] ❌ Errore invio FDO: {e}")


# =============================================================================
# RAPINE AVANZATE — Armeria, Banca Fleeca, Gioielleria, Maze Bank
# =============================================================================

async def _accredita_generico(
    criminal_uid: int, delay: float, loot: int,
    cooldown_key: str, etichetta: str,
    rapine_dict: dict, file_key: str,
    in_corso_set: set, tasks_dict: dict,
    dialogo_min: int, criminal_lock_sec: int = 0
):
    if criminal_uid in in_corso_set:
        print(f"[{etichetta.upper()}] uid={criminal_uid} già in elaborazione — ignorato.")
        return
    in_corso_set.add(criminal_uid)
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        if criminal_uid not in rapine_dict:
            return
        try:
            with open(DATI_FILE, "r") as _f:
                _dati_freschi = json.load(_f)
            _nel_file = {int(k): v for k, v in _dati_freschi.get(file_key, {}).items()}
        except Exception as _e:
            print(f"[{etichetta.upper()}] Errore lettura JSON: {_e} — uso memoria")
            _nel_file = rapine_dict
        if criminal_uid not in _nel_file:
            rapine_dict.pop(criminal_uid, None)
            return
        bil = get_balance(criminal_uid)
        bil["banca"] += loot
        furto_cooldown.setdefault(criminal_uid, {})[cooldown_key] = time.time()
        if criminal_lock_sec > 0:
            furto_cooldown[criminal_uid]["criminal_lock_until"] = time.time() + criminal_lock_sec
        rapine_dict.pop(criminal_uid, None)
        salva_dati()
        lock_msg = f"\n🔒 Attività criminale bloccata per **{formatta_durata(criminal_lock_sec)}**." if criminal_lock_sec > 0 else ""
        testo = (
            f"✅ <@{criminal_uid}> **{etichetta} completata!**\n"
            f"💰 **`{loot:,}€`** accreditati in banca.\n"
            f"⚠️ Dialogo obbligatorio di almeno **{dialogo_min} minuti** con gli FDO!"
            f"{lock_msg}"
        )
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo)
        except Exception as e:
            print(f"[{etichetta.upper()}] Messaggio canale fallito: {e}")
            try:
                utente = await bot.fetch_user(criminal_uid)
                await utente.send(testo)
            except Exception:
                pass
    finally:
        in_corso_set.discard(criminal_uid)
        tasks_dict.pop(criminal_uid, None)


async def accredita_armeria(criminal_uid: int, delay: float):
    if criminal_uid in _armeria_in_corso:
        print(f"[ARMERIA] uid={criminal_uid} già in elaborazione — ignorato.")
        return
    _armeria_in_corso.add(criminal_uid)
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        if criminal_uid not in rapine_pendenti_armeria:
            return
        try:
            with open(DATI_FILE, "r") as _f:
                _dati_freschi = json.load(_f)
            _nel_file = {int(k): v for k, v in _dati_freschi.get("rapine_pendenti_armeria", {}).items()}
        except Exception as _e:
            print(f"[ARMERIA] Errore lettura JSON: {_e} — uso memoria")
            _nel_file = rapine_pendenti_armeria
        if criminal_uid not in _nel_file:
            rapine_pendenti_armeria.pop(criminal_uid, None)
            return
        inv = get_inventario(criminal_uid)
        inv["Giubbotto Antiproiettile"] = inv.get("Giubbotto Antiproiettile", 0) + 5
        inv["Pistola"]                  = inv.get("Pistola", 0) + 3
        inv["Mitra Compatto"]           = inv.get("Mitra Compatto", 0) + 1
        furto_cooldown.setdefault(criminal_uid, {})["armeria"] = time.time()
        furto_cooldown[criminal_uid]["criminal_lock_until"] = time.time() + 86400  # 1 giorno
        rapine_pendenti_armeria.pop(criminal_uid, None)
        salva_dati()
        testo = (
            f"✅ <@{criminal_uid}> **Svaligiamento Ammu-Nation completato!**\n"
            f"🎒 Bottino: **5x Giubbotto Antiproiettile**, **3x Pistola**, **1x Mitra Compatto** + munizioni — aggiunti all'inventario.\n"
            f"⚠️ Dialogo obbligatorio di almeno **4 minuti** con gli FDO!\n"
            f"🔒 Attività criminale bloccata per **1 giorno**."
        )
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo)
        except Exception as e:
            print(f"[ARMERIA] Messaggio canale fallito: {e}")
            try:
                utente_obj = await bot.fetch_user(criminal_uid)
                await utente_obj.send(testo)
            except Exception:
                pass
    finally:
        _armeria_in_corso.discard(criminal_uid)
        _armeria_tasks.pop(criminal_uid, None)

async def accredita_fleeca(criminal_uid: int, delay: float):
    await _accredita_generico(criminal_uid, delay, LOOT_FLEECA, "fleeca", "Rapina Banca Fleeca",
        rapine_pendenti_fleeca, "rapine_pendenti_fleeca", _fleeca_in_corso, _fleeca_tasks, dialogo_min=6,
        criminal_lock_sec=4 * 86400)  # 4 giorni

async def accredita_gioielleria(criminal_uid: int, delay: float):
    await _accredita_generico(criminal_uid, delay, LOOT_GIOIELLERIA, "gioielleria", "Assalto alla Gioielleria",
        rapine_pendenti_gioielleria, "rapine_pendenti_gioielleria", _gioielleria_in_corso, _gioielleria_tasks, dialogo_min=7,
        criminal_lock_sec=7 * 86400)  # 1 settimana

async def accredita_meccanico(criminal_uid: int, delay: float):
    if criminal_uid in _meccanico_in_corso:
        print(f"[MECCANICO] uid={criminal_uid} già in elaborazione — ignorato.")
        return
    _meccanico_in_corso.add(criminal_uid)
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        if criminal_uid not in rapine_pendenti_meccanico:
            return
        try:
            with open(DATI_FILE, "r") as _f:
                _dati_freschi = json.load(_f)
            _nel_file = {int(k): v for k, v in _dati_freschi.get("rapine_pendenti_meccanico", {}).items()}
        except Exception as _e:
            print(f"[MECCANICO] Errore lettura JSON: {_e} — uso memoria")
            _nel_file = rapine_pendenti_meccanico
        if criminal_uid not in _nel_file:
            rapine_pendenti_meccanico.pop(criminal_uid, None)
            return
        modifica_scelta = _nel_file[criminal_uid].get("modifica_scelta", "Non specificata")
        furto_cooldown.setdefault(criminal_uid, {})["meccanico"] = time.time()
        furto_cooldown[criminal_uid]["criminal_lock_until"] = time.time() + 12 * 3600
        rapine_pendenti_meccanico.pop(criminal_uid, None)
        salva_dati()
        testo = (
            f"✅ <@{criminal_uid}> **Furto Officina Meccanica completato!**\n"
            f"🔧 Modifica applicata: **{modifica_scelta}**\n"
            f"⚠️ Dialogo obbligatorio di almeno **3 minuti** con gli FDO!\n"
            f"🔒 Attività criminale bloccata per **12 ore**."
        )
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo)
        except Exception as e:
            print(f"[MECCANICO] Messaggio canale fallito: {e}")
            try:
                utente_obj = await bot.fetch_user(criminal_uid)
                await utente_obj.send(testo)
            except Exception:
                pass
        # Notifica staff meccanico della modifica applicata
        try:
            embed_staff = discord.Embed(
                title="🔧 Modifica Veicolo Applicata — Furto Officina",
                description=(
                    f"👤 **Giocatore:** <@{criminal_uid}>\n"
                    f"🔧 **Modifica:** {modifica_scelta}\n\n"
                    f"✅ Modifica applicata automaticamente al termine del furto officina."
                ),
                color=discord.Color.orange()
            )
            embed_staff.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
            canale_meccanico = await bot.fetch_channel(CANALE_MECCANICO_STAFF)
            await canale_meccanico.send(embed=embed_staff)
        except Exception as e:
            print(f"[MECCANICO] Notifica staff meccanico fallita: {e}")
    finally:
        _meccanico_in_corso.discard(criminal_uid)
        _meccanico_tasks.pop(criminal_uid, None)

async def accredita_mazebank(criminal_uid: int, delay: float):
    await _accredita_generico(criminal_uid, delay, LOOT_MAZEBANK, "mazebank", "Grande Colpo Maze Bank",
        rapine_pendenti_mazebank, "rapine_pendenti_mazebank", _mazebank_in_corso, _mazebank_tasks, dialogo_min=10,
        criminal_lock_sec=10 * 86400)  # 1 settimana e 3 giorni


class AccettaRapinaGenericaView(discord.ui.View):
    """View riusabile per rapine che richiedono N FDO prima dello scassinamento."""

    def __init__(self, criminal_uid: int, nome_pg: str, posizione: str, partecipanti: str,
                 fdo_required: int, titolo: str, emoji_tipo: str,
                 loot: int, delay_s: int, cooldown_key: str,
                 items_da_restituire: dict,
                 rapine_dict: dict, in_corso_set: set, tasks_dict: dict,
                 accredita_func):
        super().__init__(timeout=600)
        self.criminal_uid        = criminal_uid
        self.nome_pg             = nome_pg
        self.posizione           = posizione
        self.partecipanti        = partecipanti
        self.fdo_required        = fdo_required
        self.titolo              = titolo
        self.emoji_tipo          = emoji_tipo
        self.loot                = loot
        self.delay_s             = delay_s
        self.cooldown_key        = cooldown_key
        self.items_da_restituire = items_da_restituire
        self.rapine_dict         = rapine_dict
        self.in_corso_set        = in_corso_set
        self.tasks_dict          = tasks_dict
        self.accredita_func      = accredita_func
        self.fdo_list: list      = []
        self.avviata             = False
        self.message: discord.Message = None
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.label = f"Accetta Servizio (0/{fdo_required})"

    @discord.ui.button(label="Accetta Servizio", style=discord.ButtonStyle.success, emoji="🚔")
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        role_ids = [r.id for r in member.roles] if member else []
        if RUOLO_POLIZIA_HARDCODED not in role_ids:
            await interaction.response.send_message("❌ Non hai il ruolo necessario per accettare il servizio.", ephemeral=True)
            return
        if self.avviata:
            await interaction.response.send_message("❌ Lo scassinamento è già iniziato!", ephemeral=True)
            return
        fdo_nome = interaction.user.display_name
        if fdo_nome in self.fdo_list:
            await interaction.response.send_message("❌ Hai già accettato questo servizio!", ephemeral=True)
            return

        self.fdo_list.append(fdo_nome)
        n = len(self.fdo_list)
        r = self.fdo_required

        if n < r:
            button.label = f"Accetta Servizio ({n}/{r})"
            fdo_str = "\n".join(f"✅ **{i+1}° Agente:** `{nome}`" for i, nome in enumerate(self.fdo_list))
            mancanti = r - n
            embed = discord.Embed(
                title=f"🚔 IN ATTESA FDO ({n}/{r}) — {self.titolo} {self.emoji_tipo}",
                description=(
                    f"{fdo_str}\n"
                    f"⏳ **In attesa... manc{'a' if mancanti==1 else 'ano'} ancora {mancanti} FDO**\n\n"
                    f"🦹 **Criminale:** `{self.nome_pg}`\n"
                    f"👥 **Partecipanti:** `{self.partecipanti}`\n"
                    f"📍 **Posizione:** `{self.posizione}`"
                ),
                color=discord.Color.yellow()
            )
            embed.set_footer(text="Tokyo Horizon RP | In attesa FDO")
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
            return

        # Raggiunto il numero richiesto — avvia lo scassinamento
        self.avviata = True
        self.stop()
        for child in self.children:
            child.disabled = True

        fdo_str = "\n".join(f"✅ **{i+1}° Agente:** `{nome}`" for i, nome in enumerate(self.fdo_list))
        minuti_s = self.delay_s // 60
        embed = discord.Embed(
            title=f"🚔 RAPINA IN CARICO — {self.titolo} {self.emoji_tipo}",
            description=(
                f"{fdo_str}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"👥 **Partecipanti:** `{self.partecipanti}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n\n"
                f"⏳ **Scassinamento in corso — {minuti_s} minuti.**\n"
                f"💰 Il bottino di `{self.loot:,}€` verrà accreditato al termine."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina in Corso")
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

        self.rapine_dict[self.criminal_uid] = {"accepted_at": time.time()}
        salva_dati()

        nomi_fdo = ", ".join(f"`{n}`" for n in self.fdo_list)
        testo_inizio = (
            f"🚔 <@{self.criminal_uid}> **{r} FDO hanno accettato** ({nomi_fdo}) — **scassinamento iniziato!**\n"
            f"⏳ Aspetta **{minuti_s} minuti**.\n"
            f"💰 Riceverai **`{self.loot:,}€`** in banca allo scadere del tempo."
        )
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo_inizio)
        except Exception as e:
            print(f"[{self.titolo.upper()}] Messaggio inizio fallito: {e}")
            try:
                utente = await bot.fetch_user(self.criminal_uid)
                await utente.send(testo_inizio)
            except Exception:
                pass

        task = asyncio.create_task(self.accredita_func(self.criminal_uid, self.delay_s))
        self.tasks_dict[self.criminal_uid] = task

    async def on_timeout(self):
        if not self.avviata:
            inv = get_inventario(self.criminal_uid)
            for nome_item, qty in self.items_da_restituire.items():
                inv[nome_item] = inv.get(nome_item, 0) + qty
            furto_cooldown.get(self.criminal_uid, {}).pop(self.cooldown_key, None)
            salva_dati()

        for child in self.children:
            child.disabled = True

        n_fdo = len(self.fdo_list)
        if n_fdo == 0:
            motivo = "Nessun FDO ha risposto entro 10 minuti."
        else:
            nomi = ", ".join(f"`{n}`" for n in self.fdo_list)
            motivo = f"Solo **{n_fdo} FDO** {'ha' if n_fdo==1 else 'hanno'} accettato ({nomi}) — servono **{self.fdo_required} agenti**."

        items_str = (", ".join(f"{q}x {n}" for n, q in self.items_da_restituire.items())
                     if self.items_da_restituire else "Nessun attrezzo da restituire")

        embed = discord.Embed(
            title="⌛ RAPINA ANNULLATA — FDO insufficienti",
            description=(
                f"{motivo}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n\n"
                f"🎒 **Restituito:** `{items_str}`\n"
                f"⏱️ Il cooldown è stato azzerato — può riprovare."
            ),
            color=discord.Color.dark_gray()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina Scaduta")
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[])
            except Exception as e:
                print(f"[{self.titolo.upper()}] Edit timeout fallito: {e}")
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(
                f"⌛ <@{self.criminal_uid}> La rapina ({self.titolo}) è annullata — {motivo}\n"
                f"🎒 Attrezzi restituiti e cooldown azzerato. Puoi riprovare!"
            )
        except Exception as e:
            print(f"[{self.titolo.upper()}] Messaggio timeout fallito: {e}")


def _invia_fdo_generica(canale_fdo, mention, embed_pol, view):
    """Helper per l'invio della notifica FDO (chiamato con await)."""
    return canale_fdo.send(content=mention, embed=embed_pol, view=view,
                            allowed_mentions=discord.AllowedMentions(roles=True))


class ArmeriaModal(discord.ui.Modal, title="🔫 Verbale — Svaligiamento Armeria"):
    nome_pg      = discord.ui.TextInput(label="Nome del tuo personaggio", placeholder="Es: Marco Rossi", min_length=2, max_length=50)
    posizione    = discord.ui.TextInput(label="Posizione dell'armeria", placeholder="Es: Ammu-Nation di Little Seoul, LS", min_length=3, max_length=100)
    partecipanti = discord.ui.TextInput(label="Partecipanti (max 3 criminali)", placeholder="Es: Solo / Con [nomi personaggi]", min_length=2, max_length=120)

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        uid  = self.uid
        nome = self.nome_pg.value.strip()
        pos  = self.posizione.value.strip()
        part = self.partecipanti.value.strip()

        embed_ok = discord.Embed(
            title="✅ Svaligiamento Ammu-Nation Inviato!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"🔫 **Nessun attrezzo speciale richiesto.** Le armi sono in bella vista nel negozio.\n"
                f"📡 Notifica inviata agli FDO — aspetta che **3 FDO** accettino.\n"
                f"⏳ Dopo conferma, iniziano **6 minuti** di scassinamento.\n"
                f"🎒 **Bottino:** 5x Giubbotto Antiproiettile + 3x Pistola + 1x Mitra Compatto + munizioni.\n"
                f"⚠️ Dialogo obbligatorio di **almeno 4 minuti** con gli FDO.\n\n"
                f"⚔️ Equipaggiamento consentito: **Pistole + Giubbotti antiproiettile** (vietati caschi)"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")
        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 SVALIGIAMENTO IN CORSO — AMMU-NATION 🔫",
            description=(
                f"🦹 **Criminale:** `{nome}`\n"
                f"👥 **Partecipanti:** `{part}`\n"
                f"📍 **Posizione:** `{pos}`\n\n"
                f"👮 **FDO richiesti:** **3 FDO** devono cliccare il bottone\n"
                f"⚔️ **Equipaggiamento criminale:** Pistole + Giubbotti antiproiettile (vietati caschi)\n"
                f"🔒 **Ostaggi:** Max 1\n"
                f"⏱️ **Scassinamento:** 6 min | **Dialogo min.:** 4 min\n"
                f"🎒 **Bottino:** 5x Giubbotto + 3x Pistola + 1x Mitra Compatto + munizioni\n\n"
                f"⏳ Devono cliccare **3 FDO** entro 10 min o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — servono 3 agenti")
        view = AccettaRapinaGenericaView(
            uid, nome, pos, part,
            fdo_required=3, titolo="Svaligiamento Armeria", emoji_tipo="🔫",
            loot=LOOT_ARMERIA, delay_s=360, cooldown_key="armeria",
            items_da_restituire={},
            rapine_dict=rapine_pendenti_armeria, in_corso_set=_armeria_in_corso,
            tasks_dict=_armeria_tasks, accredita_func=accredita_armeria
        )
        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[ARMERIA] Followup criminale fallito: {e}")
            try:
                await interaction.followup.send(embed=embed_ok, ephemeral=True)
            except Exception:
                pass
        try:
            await interaction.followup.send("📍 **Manda subito uno screenshot del radar** per la tua posizione esatta!", ephemeral=False)
        except Exception as e:
            print(f"[ARMERIA] Messaggio radar fallito: {e}")
        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            msg = await canale_fdo.send(content=mention, embed=embed_pol, view=view,
                                         allowed_mentions=discord.AllowedMentions(roles=True))
            view.message = msg
            print(f"[ARMERIA] Notifica FDO inviata ✅")
        except discord.Forbidden as e:
            print(f"[ARMERIA] ❌ Permessi mancanti canale FDO: {e}")
        except discord.NotFound as e:
            print(f"[ARMERIA] ❌ Canale FDO non trovato: {e}")
        except Exception as e:
            print(f"[ARMERIA] ❌ Errore invio FDO: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        code = getattr(getattr(error, "original", error), "code", None)
        print(f"[ARMERIA MODAL] {type(error).__name__} (code={code}): {error}")
        if code in (10062, 40060):
            return
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


class FleecaModal(discord.ui.Modal, title="🏦 Verbale — Rapina alla Banca Fleeca"):
    nome_pg      = discord.ui.TextInput(label="Nome del tuo personaggio", placeholder="Es: Marco Rossi", min_length=2, max_length=50)
    posizione    = discord.ui.TextInput(label="Posizione della banca Fleeca", placeholder="Es: Fleeca di Rockford Hills, LS", min_length=3, max_length=100)
    partecipanti = discord.ui.TextInput(label="Partecipanti (max 4 criminali)", placeholder="Es: Con [nomi personaggi]", min_length=2, max_length=150)

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        uid  = self.uid
        nome = self.nome_pg.value.strip()
        pos  = self.posizione.value.strip()
        part = self.partecipanti.value.strip()

        inv = get_inventario(uid)
        if inv.get("Piede di Porco", 0) < 5:
            mancanti = 5 - inv.get("Piede di Porco", 0)
            await interaction.followup.send(
                f"❌ Ti mancano **{mancanti}x Piede di Porco** (ne hai `{inv.get('Piede di Porco',0)}/5`). Acquistali con `/negozio`.",
                ephemeral=True)
            return
        if inv.get("Trapano", 0) < 1:
            await interaction.followup.send("❌ Ti manca **1x Trapano**. Acquistalo con `/negozio`.", ephemeral=True)
            return

        embed_ok = discord.Embed(
            title="✅ Rapina Banca Fleeca Inviata!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"🪓 Consumati: **5x Piede di Porco** + **1x Trapano**.\n"
                f"📡 Notifica inviata agli FDO — aspetta che **4 FDO** accettino.\n"
                f"⏳ Dopo conferma, iniziano **7 minuti** di scassinamento.\n"
                f"💰 **`{LOOT_FLEECA:,}€`** accreditati in banca al termine.\n"
                f"⚠️ Dialogo obbligatorio di **almeno 6 minuti** con gli FDO.\n\n"
                f"⚔️ Equipaggiamento: **Pistole, mitra leggeri, giubbotti** (vietati caschi)"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")
        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 RAPINA IN CORSO — BANCA FLEECA 🏦",
            description=(
                f"🦹 **Criminale:** `{nome}`\n"
                f"👥 **Partecipanti:** `{part}`\n"
                f"📍 **Posizione:** `{pos}`\n\n"
                f"👮 **FDO richiesti:** **4 FDO** devono cliccare il bottone\n"
                f"⚔️ **Equipaggiamento criminale:** Pistole, mitra leggeri, giubbotti (vietati caschi)\n"
                f"🔒 **Ostaggi:** Max 1 (riscatto max 15.000€)\n"
                f"⏱️ **Scassinamento:** 7 min | **Dialogo min.:** 6 min\n"
                f"💰 **Bottino:** `{LOOT_FLEECA:,}€`\n\n"
                f"⏳ Devono cliccare **4 FDO** entro 10 min o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — servono 4 agenti")
        view = AccettaRapinaGenericaView(
            uid, nome, pos, part,
            fdo_required=4, titolo="Banca Fleeca", emoji_tipo="🏦",
            loot=LOOT_FLEECA, delay_s=420, cooldown_key="fleeca",
            items_da_restituire={"Piede di Porco": 5, "Trapano": 1},
            rapine_dict=rapine_pendenti_fleeca, in_corso_set=_fleeca_in_corso,
            tasks_dict=_fleeca_tasks, accredita_func=accredita_fleeca
        )
        # Consuma gli attrezzi
        inv["Piede di Porco"] -= 5
        if inv["Piede di Porco"] <= 0:
            del inv["Piede di Porco"]
        inv["Trapano"] = inv.get("Trapano", 1) - 1
        if inv["Trapano"] <= 0:
            del inv["Trapano"]
        salva_dati()
        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[FLEECA] Followup criminale fallito: {e}")
            try:
                await interaction.followup.send(embed=embed_ok, ephemeral=True)
            except Exception:
                pass
        try:
            await interaction.followup.send("📍 **Manda subito uno screenshot del radar** per la tua posizione esatta!", ephemeral=False)
        except Exception as e:
            print(f"[FLEECA] Messaggio radar fallito: {e}")
        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            msg = await canale_fdo.send(content=mention, embed=embed_pol, view=view,
                                         allowed_mentions=discord.AllowedMentions(roles=True))
            view.message = msg
            print(f"[FLEECA] Notifica FDO inviata ✅")
        except discord.Forbidden as e:
            print(f"[FLEECA] ❌ Permessi mancanti canale FDO: {e}")
        except discord.NotFound as e:
            print(f"[FLEECA] ❌ Canale FDO non trovato: {e}")
        except Exception as e:
            print(f"[FLEECA] ❌ Errore invio FDO: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        code = getattr(getattr(error, "original", error), "code", None)
        print(f"[FLEECA MODAL] {type(error).__name__} (code={code}): {error}")
        if code in (10062, 40060):
            return
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


class GioielleriaModal(discord.ui.Modal, title="💎 Verbale — Assalto alla Gioielleria"):
    nome_pg      = discord.ui.TextInput(label="Nome del tuo personaggio", placeholder="Es: Marco Rossi", min_length=2, max_length=50)
    posizione    = discord.ui.TextInput(label="Posizione della gioielleria", placeholder="Es: Gioielleria di Rockford Hills, LS", min_length=3, max_length=100)
    partecipanti = discord.ui.TextInput(label="Partecipanti (max 5 criminali)", placeholder="Es: Con [nomi personaggi]", min_length=2, max_length=180)

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        uid  = self.uid
        nome = self.nome_pg.value.strip()
        pos  = self.posizione.value.strip()
        part = self.partecipanti.value.strip()

        inv = get_inventario(uid)
        if inv.get("Dispositivo di Hacking Medio", 0) < 1:
            await interaction.followup.send("❌ Ti manca **1x Dispositivo di Hacking Medio**. Acquistalo con `/compranero`.", ephemeral=True)
            return
        if inv.get("Gas Soporifero", 0) < 1:
            await interaction.followup.send("❌ Ti manca **Gas Soporifero**. Acquistalo con `/compranero`.", ephemeral=True)
            return

        embed_ok = discord.Embed(
            title="✅ Assalto alla Gioielleria Inviato!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"📡 Consumati: **1x Dispositivo di Hacking Medio** + **1x Gas Soporifero**\n"
                f"🔔 Notifica inviata agli FDO — aspetta che **4 FDO** accettino.\n"
                f"⏳ Dopo conferma, iniziano **9 minuti** di scassinamento.\n"
                f"💰 **`{LOOT_GIOIELLERIA:,}€`** accreditati in banca al termine.\n"
                f"⚠️ Dialogo obbligatorio di **almeno 7 minuti** con gli FDO.\n\n"
                f"⚔️ Equipaggiamento: **Libero totale** (caschi, giubbotti, armi automatiche)\n"
                f"🔒 **Ostaggi:** Max 2 (riscatto max **30.000€** a ostaggio)"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")
        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 ASSALTO IN CORSO — GIOIELLERIA 💎",
            description=(
                f"🦹 **Criminale (leader):** `{nome}`\n"
                f"👥 **Partecipanti:** `{part}`\n"
                f"📍 **Posizione:** `{pos}`\n\n"
                f"👮 **FDO richiesti:** **4 FDO** devono cliccare il bottone\n"
                f"⚔️ **Equipaggiamento criminale:** Libero totale (caschi integrali, giubbotti, armi automatiche)\n"
                f"🔒 **Ostaggi:** Max 2 | Riscatto max **30.000€** a ostaggio\n"
                f"⏱️ **Scassinamento:** 9 min | **Dialogo min.:** 7 min\n"
                f"💰 **Bottino:** `{LOOT_GIOIELLERIA:,}€`\n\n"
                f"⏳ Devono cliccare **4 FDO** entro 10 min o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — servono 4 agenti")
        view = AccettaRapinaGenericaView(
            uid, nome, pos, part,
            fdo_required=4, titolo="Gioielleria", emoji_tipo="💎",
            loot=LOOT_GIOIELLERIA, delay_s=540, cooldown_key="gioielleria",
            items_da_restituire={"Dispositivo di Hacking Medio": 1, "Gas Soporifero": 1},
            rapine_dict=rapine_pendenti_gioielleria, in_corso_set=_gioielleria_in_corso,
            tasks_dict=_gioielleria_tasks, accredita_func=accredita_gioielleria
        )
        for item in ("Dispositivo di Hacking Medio", "Gas Soporifero"):
            inv[item] = inv.get(item, 1) - 1
            if inv[item] <= 0:
                del inv[item]
        salva_dati()
        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[GIOIELLERIA] Followup criminale fallito: {e}")
            try:
                await interaction.followup.send(embed=embed_ok, ephemeral=True)
            except Exception:
                pass
        try:
            await interaction.followup.send("📍 **Manda subito uno screenshot del radar** per la tua posizione esatta!", ephemeral=False)
        except Exception as e:
            print(f"[GIOIELLERIA] Messaggio radar fallito: {e}")
        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            msg = await canale_fdo.send(content=mention, embed=embed_pol, view=view,
                                         allowed_mentions=discord.AllowedMentions(roles=True))
            view.message = msg
            print(f"[GIOIELLERIA] Notifica FDO inviata ✅")
        except discord.Forbidden as e:
            print(f"[GIOIELLERIA] ❌ Permessi mancanti canale FDO: {e}")
        except discord.NotFound as e:
            print(f"[GIOIELLERIA] ❌ Canale FDO non trovato: {e}")
        except Exception as e:
            print(f"[GIOIELLERIA] ❌ Errore invio FDO: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        code = getattr(getattr(error, "original", error), "code", None)
        print(f"[GIOIELLERIA MODAL] {type(error).__name__} (code={code}): {error}")
        if code in (10062, 40060):
            return
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


class MazeBankModal(discord.ui.Modal, title="🏛️ Verbale — Grande Colpo alla Maze Bank"):
    nome_pg      = discord.ui.TextInput(label="Nome del tuo personaggio", placeholder="Es: Marco Rossi", min_length=2, max_length=50)
    posizione    = discord.ui.TextInput(label="Posizione della Maze Bank", placeholder="Es: Maze Bank Tower, Downtown LS", min_length=3, max_length=100)
    partecipanti = discord.ui.TextInput(label="Partecipanti (max 6 criminali)", placeholder="Es: Con [nomi personaggi]", min_length=2, max_length=200)

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        uid  = self.uid
        nome = self.nome_pg.value.strip()
        pos  = self.posizione.value.strip()
        part = self.partecipanti.value.strip()

        inv = get_inventario(uid)
        if inv.get("Dispositivo di Hacking Avanzato", 0) < 1:
            await interaction.followup.send("❌ Ti manca **1x Dispositivo di Hacking Avanzato**. Acquistalo con `/compranero`.", ephemeral=True)
            return
        if inv.get("Lancia Termica", 0) < 1:
            await interaction.followup.send("❌ Ti manca **1x Lancia Termica**. Acquistala con `/compraarmi`.", ephemeral=True)
            return
        if inv.get("Trapano Pesante Professionale", 0) < 1:
            await interaction.followup.send("❌ Ti manca **1x Trapano Pesante Professionale**. Acquistalo con `/compranero`.", ephemeral=True)
            return
        if inv.get("Grimaldello Avanzato", 0) < 2:
            mancanti = 2 - inv.get("Grimaldello Avanzato", 0)
            await interaction.followup.send(
                f"❌ Ti mancano **{mancanti}x Grimaldello Avanzato** (ne hai `{inv.get('Grimaldello Avanzato',0)}/2`). Acquistali con `/negozio`.",
                ephemeral=True)
            return

        embed_ok = discord.Embed(
            title="✅ Grande Colpo alla Maze Bank Inviato!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"🖥️ Consumati: **1x Hack Avanzato** + **1x Lancia Termica** + **1x Trapano Pesante Professionale** + **2x Grimaldello Avanzato**\n"
                f"📡 Notifica inviata agli FDO — aspetta che **5 FDO** accettino.\n"
                f"⏳ Dopo conferma, iniziano **12 minuti** di scassinamento.\n"
                f"💰 **`{LOOT_MAZEBANK:,}€`** accreditati in banca al termine.\n"
                f"⚠️ Dialogo obbligatorio di **almeno 10 minuti** con gli FDO.\n\n"
                f"⚔️ Equipaggiamento: **Libero totale**\n"
                f"🔒 **Ostaggi:** Max 3 (riscatto max **80.000€** a ostaggio)"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")
        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 GRANDE COLPO IN CORSO — MAZE BANK 🏛️",
            description=(
                f"🦹 **Criminale (leader):** `{nome}`\n"
                f"👥 **Partecipanti:** `{part}`\n"
                f"📍 **Posizione:** `{pos}`\n\n"
                f"👮 **FDO richiesti:** **5 FDO** devono cliccare il bottone\n"
                f"⚔️ **Equipaggiamento criminale:** Libero totale\n"
                f"🔒 **Ostaggi:** Max 3 | Riscatto max **80.000€** a ostaggio\n"
                f"⏱️ **Scassinamento:** 12 min | **Dialogo min.:** 10 min\n"
                f"💰 **Bottino:** `{LOOT_MAZEBANK:,}€`\n\n"
                f"⏳ Devono cliccare **5 FDO** entro 10 min o la rapina viene annullata."
            ),
            color=discord.Color.dark_red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | ALLERTA MASSIMA — servono 5 agenti")
        view = AccettaRapinaGenericaView(
            uid, nome, pos, part,
            fdo_required=5, titolo="Maze Bank", emoji_tipo="🏛️",
            loot=LOOT_MAZEBANK, delay_s=720, cooldown_key="mazebank",
            items_da_restituire={"Dispositivo di Hacking Avanzato": 1, "Lancia Termica": 1,
                                  "Trapano Pesante Professionale": 1, "Grimaldello Avanzato": 2},
            rapine_dict=rapine_pendenti_mazebank, in_corso_set=_mazebank_in_corso,
            tasks_dict=_mazebank_tasks, accredita_func=accredita_mazebank
        )
        for item, qty in [("Dispositivo di Hacking Avanzato", 1), ("Lancia Termica", 1),
                           ("Trapano Pesante Professionale", 1), ("Grimaldello Avanzato", 2)]:
            inv[item] = inv.get(item, qty) - qty
            if inv[item] <= 0:
                del inv[item]
        salva_dati()
        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[MAZEBANK] Followup criminale fallito: {e}")
            try:
                await interaction.followup.send(embed=embed_ok, ephemeral=True)
            except Exception:
                pass
        try:
            await interaction.followup.send("📍 **Manda subito uno screenshot del radar** per la tua posizione esatta!", ephemeral=False)
        except Exception as e:
            print(f"[MAZEBANK] Messaggio radar fallito: {e}")
        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            msg = await canale_fdo.send(content=mention, embed=embed_pol, view=view,
                                         allowed_mentions=discord.AllowedMentions(roles=True))
            view.message = msg
            print(f"[MAZEBANK] Notifica FDO inviata ✅")
        except discord.Forbidden as e:
            print(f"[MAZEBANK] ❌ Permessi mancanti canale FDO: {e}")
        except discord.NotFound as e:
            print(f"[MAZEBANK] ❌ Canale FDO non trovato: {e}")
        except Exception as e:
            print(f"[MAZEBANK] ❌ Errore invio FDO: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        code = getattr(getattr(error, "original", error), "code", None)
        print(f"[MAZEBANK MODAL] {type(error).__name__} (code={code}): {error}")
        if code in (10062, 40060):
            return
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


# =============================================================================
# FURTO OFFICINA MECCANICA — View speciale (max 2 FDO, 2 min finestra)
# =============================================================================

class AccettaRapinaMeccanicoView(discord.ui.View):
    """View per Furto Officina Meccanica — max 2 FDO, parte 2 min dopo il primo accettante."""

    def __init__(self, criminal_uid: int, nome_pg: str, posizione: str, partecipanti: str, modifica_scelta: str = "Non specificata"):
        super().__init__(timeout=600)
        self.criminal_uid          = criminal_uid
        self.nome_pg               = nome_pg
        self.posizione             = posizione
        self.partecipanti          = partecipanti
        self.modifica_scelta       = modifica_scelta
        self.fdo_list: list        = []
        self.avviata               = False
        self.message: discord.Message = None
        self._timer_task: asyncio.Task = None

    @discord.ui.button(label="Accetta Servizio (0/2 max)", style=discord.ButtonStyle.success, emoji="🚔")
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        role_ids = [r.id for r in member.roles] if member else []
        if RUOLO_POLIZIA_HARDCODED not in role_ids:
            await interaction.response.send_message("❌ Non hai il ruolo necessario per accettare il servizio.", ephemeral=True)
            return
        if self.avviata:
            await interaction.response.send_message("❌ Lo scassinamento è già iniziato!", ephemeral=True)
            return
        fdo_nome = interaction.user.display_name
        if fdo_nome in self.fdo_list:
            await interaction.response.send_message("❌ Hai già accettato questo servizio!", ephemeral=True)
            return
        if len(self.fdo_list) >= 2:
            await interaction.response.send_message("❌ Al massimo 2 FDO per questa operazione.", ephemeral=True)
            return

        self.fdo_list.append(fdo_nome)
        n = len(self.fdo_list)

        if n == 1:
            button.label = "Accetta Servizio (1/2 max)"
            embed = discord.Embed(
                title="🚔 IN ATTESA 2° FDO — FURTO OFFICINA MECCANICA 🔧",
                description=(
                    f"✅ **1° Agente:** `{fdo_nome}`\n"
                    f"⏳ **1 FDO ha accettato — il 2° ha 2 minuti per unirsi.**\n"
                    f"Se nessun altro accetta, la rapina parte comunque tra **2 min**.\n\n"
                    f"🦹 **Criminale:** `{self.nome_pg}`\n"
                    f"👥 **Partecipanti:** `{self.partecipanti}`\n"
                    f"📍 **Posizione:** `{self.posizione}`"
                ),
                color=discord.Color.yellow()
            )
            embed.set_footer(text="Tokyo Horizon RP | In attesa 2° FDO (2 min)")
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
            self._timer_task = asyncio.create_task(self._avvia_dopo_attesa())
            return

        # n == 2: secondo cop arrivato in tempo — cancella timer e avvia subito
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        await self._avvia_rapina(interaction=interaction)

    async def _avvia_dopo_attesa(self):
        """Aspetta 2 min poi avvia la rapina anche con 1 solo FDO."""
        try:
            await asyncio.sleep(120)
        except asyncio.CancelledError:
            return
        if not self.avviata:
            await self._avvia_rapina(interaction=None)

    async def _avvia_rapina(self, interaction):
        self.avviata = True
        self.stop()
        for child in self.children:
            child.disabled = True

        fdo_str = "\n".join(f"✅ **{i+1}° Agente:** `{nome}`" for i, nome in enumerate(self.fdo_list))
        embed = discord.Embed(
            title="🚔 RAPINA IN CARICO — FURTO OFFICINA MECCANICA 🔧",
            description=(
                f"{fdo_str}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"👥 **Partecipanti:** `{self.partecipanti}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n"
                f"🔧 **Modifica richiesta:** `{self.modifica_scelta}`\n\n"
                f"⏳ **Scassinamento in corso — 5 minuti.**\n"
                f"🔒 Dopo il colpo: **12 ore** di blocco attività criminale."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina in Corso")

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[])
            except Exception as e:
                print(f"[MECCANICO] Edit timer fallito: {e}")

        rapine_pendenti_meccanico[self.criminal_uid] = {"accepted_at": time.time(), "modifica_scelta": self.modifica_scelta}
        salva_dati()

        n_fdo = len(self.fdo_list)
        nomi_fdo = ", ".join(f"`{n}`" for n in self.fdo_list)
        testo_inizio = (
            f"🚔 <@{self.criminal_uid}> **{n_fdo} FDO {'ha' if n_fdo==1 else 'hanno'} accettato** ({nomi_fdo}) — **scassinamento iniziato!**\n"
            f"⏳ Aspetta **5 minuti**.\n"
            f"🔧 Modifica scelta: **{self.modifica_scelta}** — verrà confermata ai meccanici al termine.\n"
            f"🔒 Dopo il colpo, attività criminale bloccata per **12 ore**."
        )
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(testo_inizio)
        except Exception as e:
            print(f"[MECCANICO] Messaggio inizio fallito: {e}")
            try:
                utente = await bot.fetch_user(self.criminal_uid)
                await utente.send(testo_inizio)
            except Exception:
                pass

        task = asyncio.create_task(accredita_meccanico(self.criminal_uid, 300))
        _meccanico_tasks[self.criminal_uid] = task

    async def on_timeout(self):
        if not self.avviata:
            # Azzera cooldown (il Simulatore di Impronte Digitali NON viene consumato)
            furto_cooldown.get(self.criminal_uid, {}).pop("meccanico", None)
            salva_dati()

        for child in self.children:
            child.disabled = True

        n_fdo = len(self.fdo_list)
        if n_fdo == 0:
            motivo = "Nessun FDO ha risposto entro 10 minuti."
        else:
            nomi = ", ".join(f"`{n}`" for n in self.fdo_list)
            motivo = f"**{n_fdo} FDO** {'ha' if n_fdo==1 else 'hanno'} accettato ({nomi})."

        embed = discord.Embed(
            title="⌛ RAPINA ANNULLATA — Officina Meccanica",
            description=(
                f"{motivo}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n\n"
                f"👆 **Simulatore di Impronte Digitali:** non consumato, rimane in inventario.\n"
                f"⏱️ Il cooldown è stato azzerato — può riprovare."
            ),
            color=discord.Color.dark_gray()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina Scaduta")
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[])
            except Exception as e:
                print(f"[MECCANICO] Edit timeout fallito: {e}")
        try:
            canale = await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
            await canale.send(
                f"⌛ <@{self.criminal_uid}> Rapina officina annullata — {motivo}\n"
                f"🎒 Grimaldello restituito e cooldown azzerato. Puoi riprovare!"
            )
        except Exception as e:
            print(f"[MECCANICO] Messaggio timeout fallito: {e}")


class MeccanicoModal(discord.ui.Modal, title="🔧 Verbale — Furto Officina Meccanica"):
    nome_pg      = discord.ui.TextInput(label="Nome del tuo personaggio", placeholder="Es: Marco Rossi", min_length=2, max_length=50)
    posizione    = discord.ui.TextInput(label="Posizione dell'officina", placeholder="Es: Officina di Harmony, Route 68", min_length=3, max_length=100)
    partecipanti = discord.ui.TextInput(label="Partecipanti (max 2 criminali)", placeholder="Es: Solo / Con [nome personaggio]", min_length=2, max_length=120)
    modifica_scelta = discord.ui.TextInput(label="Modifica che vuoi applicare al tuo veicolo", placeholder="Es: Turbo Racing / Motore Liv.4 / Corazza 100%", min_length=3, max_length=150)

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        uid      = self.uid
        nome     = self.nome_pg.value.strip()
        pos      = self.posizione.value.strip()
        part     = self.partecipanti.value.strip()
        modifica = self.modifica_scelta.value.strip()

        inv = get_inventario(uid)
        if inv.get("Simulatore di Impronte Digitali", 0) < 1:
            await interaction.followup.send(
                "🔒 Per svaligiare l'officina serve **`1x Simulatore di Impronte Digitali`**. Acquistalo con `/compranero` (20.000€).\n"
                "ℹ️ Non viene consumato — rimane in inventario dopo l'uso.",
                ephemeral=True)
            return

        furto_cooldown.setdefault(uid, {})["meccanico"] = time.time()
        salva_dati()

        embed_ok = discord.Embed(
            title="✅ Furto Officina Meccanica Inviato!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n"
                f"🔧 **Modifica scelta:** `{modifica}`\n\n"
                f"👆 **Simulatore di Impronte Digitali** usato (non consumato).\n"
                f"📡 Notifica inviata agli FDO — **massimo 2 FDO** possono accettare.\n"
                f"⏳ Dopo il primo FDO, hai **2 minuti** per il secondo. Poi parte comunque.\n"
                f"🔩 **Bottino:** La modifica scelta verrà applicata al termine (5 min).\n"
                f"⚠️ Dialogo obbligatorio di **almeno 3 minuti** con gli FDO.\n"
                f"🔒 Dopo il colpo: **12 ore** di blocco attività criminale.\n\n"
                f"⚔️ Equipaggiamento: **Pistola** (vietate armi automatiche)"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")

        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 FURTO IN CORSO — OFFICINA MECCANICA 🔧",
            description=(
                f"🦹 **Criminale:** `{nome}`\n"
                f"👥 **Partecipanti:** `{part}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"🔧 **Modifica richiesta:** `{modifica}`\n\n"
                f"👮 **FDO richiesti:** **Massimo 2** (basta 1 — il 2° ha 2 min per unirsi)\n"
                f"⚔️ **Equipaggiamento criminale:** Pistola (vietate armi automatiche)\n"
                f"⏱️ **Scassinamento:** 5 min | **Dialogo min.:** 3 min\n\n"
                f"⏳ Clicca entro 10 min o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — max 2 agenti")

        view = AccettaRapinaMeccanicoView(uid, nome, pos, part, modifica)
        try:
            await interaction.followup.send(embed=embed_ok, ephemeral=False)
        except Exception as e:
            print(f"[MECCANICO] Followup criminale fallito: {e}")
        try:
            await interaction.followup.send("📍 **Manda subito uno screenshot del radar** per la tua posizione esatta!", ephemeral=False)
        except Exception as e:
            print(f"[MECCANICO] Messaggio radar fallito: {e}")
        try:
            canale_fdo = await bot.fetch_channel(CANALE_FDO)
            msg = await canale_fdo.send(content=mention, embed=embed_pol, view=view,
                                         allowed_mentions=discord.AllowedMentions(roles=True))
            view.message = msg
            print(f"[MECCANICO] Notifica FDO inviata ✅")
        except discord.Forbidden as e:
            print(f"[MECCANICO] ❌ Permessi mancanti canale FDO: {e}")
        except discord.NotFound as e:
            print(f"[MECCANICO] ❌ Canale FDO non trovato: {e}")
        except Exception as e:
            print(f"[MECCANICO] ❌ Errore invio FDO: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        code = getattr(getattr(error, "original", error), "code", None)
        print(f"[MECCANICO MODAL] {type(error).__name__} (code={code}): {error}")
        if code in (10062, 40060):
            return
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="rapina", description="Esegui una rapina — bancomat, armeria, banca e altro")
@app_commands.describe(tipo="Tipo di rapina da effettuare")
@app_commands.choices(tipo=[
    app_commands.Choice(name="🏧 Bancomat — 7.000€ | Piede di Porco + Pistola | Cooldown 12h",                         value="bancomat"),
    app_commands.Choice(name="🍏 Minimarket — 15.000€ | Cacciavite/PdP + Pistola | Cooldown 24h",                      value="minimarket"),
    app_commands.Choice(name="🔧 Officina Meccanica — 3x Pezzi di Ricambio | Piede di Porco + Sim. Impronte | CD 48h",  value="meccanico"),
    app_commands.Choice(name="🔫 Ammu-Nation — Giubbotti+Pistole+Mitra | Nessun attrezzo | Cooldown 24h",               value="armeria"),
    app_commands.Choice(name="🏦 Banca Fleeca — 250.000€ | 5x PdP + Trapano | Cooldown 48h",                           value="fleeca"),
    app_commands.Choice(name="💎 Gioielleria — 500.000€ | Hack Medio + Gas Soporifero | Cooldown 4gg",               value="gioielleria"),
    app_commands.Choice(name="🏛️ Maze Bank — 1.000.000€ | Hack Avanzato + Lancia + Trapano + Grim | Cooldown 1 sett.", value="mazebank"),
])
async def rapina(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    uid = interaction.user.id

    # Blocco post-colpo: impossibile fare attività criminale per il tempo prestabilito
    lock_rem = get_criminal_lock(uid)
    if lock_rem > 0:
        try:
            await interaction.response.send_message(
                f"🔒 Hai completato un colpo di alto profilo di recente.\n"
                f"Non puoi svolgere attività criminale per ancora {formatta_durata(lock_rem)}.",
                ephemeral=True
            )
        except Exception:
            pass
        return

    if interaction.channel_id != CANALE_POLIZIA_HARDCODED:
        try:
            await interaction.response.send_message(
                f"❌ Le rapine si possono avviare solo nel canale <#{CANALE_POLIZIA_HARDCODED}>.",
                ephemeral=True
            )
        except Exception:
            pass
        return

    if tipo.value == "bancomat":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("bancomat", 0)
        print(f"[RAPINA CHECK] uid={uid} ora={ora:.0f} ultimo={ultimo:.0f} diff={ora-ultimo:.0f}s (limite={12*3600}s) CD={ora-ultimo < 12*3600}")
        if ora - ultimo < 12 * 3600:
            rimanenti = int(12 * 3600 - (ora - ultimo))
            ore_r = rimanenti // 3600
            min_r = (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di poter rapinare un altro bancomat.",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        inv = get_inventario(uid)
        print(f"[RAPINA INV] uid={uid} pdp={inv.get('Piede di Porco',0)} pistola={inv.get('Pistola',0)}")
        if inv.get("Piede di Porco", 0) <= 0:
            try:
                await interaction.response.send_message(
                    "🔒 Per rapinare un bancomat servono **`1x Piede di Porco`** e **`1x Pistola`**. Acquistali con `/negozio` e `/compraarmi`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        if inv.get("Pistola", 0) <= 0:
            try:
                await interaction.response.send_message(
                    "🔒 Per rapinare un bancomat serve anche **`1x Pistola`**. Acquistala con `/compraarmi`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.send_modal(BancomatModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] send_modal ignorato — interazione già risposta per uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] send_modal 10062 — interazione scaduta per uid={uid}")
        except discord.HTTPException as e:
            print(f"[RAPINA] send_modal fallito: {e}")
        except Exception as e:
            print(f"[RAPINA] send_modal errore inatteso: {e}")

    elif tipo.value == "meccanico":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("meccanico", 0)
        if ora - ultimo < 48 * 3600:
            rimanenti = int(48 * 3600 - (ora - ultimo))
            ore_r, min_r = rimanenti // 3600, (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di svaligiare un'altra officina.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        inv = get_inventario(uid)
        if inv.get("Piede di Porco", 0) < 1:
            try:
                await interaction.response.send_message(
                    "🔒 Per svaligiare l'officina serve **`1x Piede di Porco`**. Acquistalo con `/negozio`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        try:
            await interaction.response.send_modal(MeccanicoModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] MeccanicoModal già risposta uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] MeccanicoModal 10062 uid={uid}")
        except Exception as e:
            print(f"[RAPINA] MeccanicoModal errore: {e}")

    elif tipo.value == "minimarket":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("minimarket", 0)
        print(f"[RAPINA CHECK] uid={uid} tipo=minimarket ora={ora:.0f} ultimo={ultimo:.0f} diff={ora-ultimo:.0f}s (limite={24*3600}s) CD={ora-ultimo < 24*3600}")
        if ora - ultimo < 24 * 3600:
            rimanenti = int(24 * 3600 - (ora - ultimo))
            ore_r = rimanenti // 3600
            min_r = (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di poter rapinare un altro minimarket.",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        inv = get_inventario(uid)
        ha_strumento = inv.get("Cacciavite", 0) > 0 or inv.get("Piede di Porco", 0) > 0
        print(f"[RAPINA INV] uid={uid} cacciavite={inv.get('Cacciavite',0)} pdp={inv.get('Piede di Porco',0)} pistola={inv.get('Pistola',0)}")
        if not ha_strumento:
            try:
                await interaction.response.send_message(
                    "🔒 Per rapinare un minimarket serve **`1x Cacciavite`** o **`1x Piede di Porco`** e **`1x Pistola`**. Acquistali con `/negozio` e `/compraarmi`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        if inv.get("Pistola", 0) <= 0:
            try:
                await interaction.response.send_message(
                    "🔒 Per rapinare un minimarket serve anche **`1x Pistola`**. Acquistala con `/compraarmi`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.send_modal(MinimarketModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] MinimarketModal ignorato — interazione già risposta per uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] MinimarketModal 10062 — interazione scaduta per uid={uid}")
        except discord.HTTPException as e:
            print(f"[RAPINA] MinimarketModal fallito: {e}")
        except Exception as e:
            print(f"[RAPINA] MinimarketModal errore inatteso: {e}")

    elif tipo.value == "armeria":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("armeria", 0)
        if ora - ultimo < 24 * 3600:
            rimanenti = int(24 * 3600 - (ora - ultimo))
            ore_r, min_r = rimanenti // 3600, (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di svaligiare un'altra armeria.", ephemeral=True)
            except Exception: pass
            return
        try:
            await interaction.response.send_modal(ArmeriaModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] ArmeriaModal già risposta uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] ArmeriaModal 10062 uid={uid}")
        except Exception as e:
            print(f"[RAPINA] ArmeriaModal errore: {e}")

    elif tipo.value == "fleeca":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("fleeca", 0)
        if ora - ultimo < 48 * 3600:
            rimanenti = int(48 * 3600 - (ora - ultimo))
            ore_r, min_r = rimanenti // 3600, (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di rapinare un'altra Fleeca.", ephemeral=True)
            except Exception: pass
            return
        inv = get_inventario(uid)
        if inv.get("Piede di Porco", 0) < 5:
            mancanti = 5 - inv.get("Piede di Porco", 0)
            try:
                await interaction.response.send_message(
                    f"🔒 Ti mancano **{mancanti}x Piede di Porco** (hai `{inv.get('Piede di Porco',0)}/5`). Comprali con `/negozio`.", ephemeral=True)
            except Exception: pass
            return
        if inv.get("Trapano", 0) < 1:
            try:
                await interaction.response.send_message("🔒 Ti manca **1x Trapano**. Compralo con `/negozio`.", ephemeral=True)
            except Exception: pass
            return
        try:
            await interaction.response.send_modal(FleecaModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] FleecaModal già risposta uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] FleecaModal 10062 uid={uid}")
        except Exception as e:
            print(f"[RAPINA] FleecaModal errore: {e}")

    elif tipo.value == "gioielleria":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("gioielleria", 0)
        if ora - ultimo < 96 * 3600:
            rimanenti = int(96 * 3600 - (ora - ultimo))
            ore_r, min_r = rimanenti // 3600, (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di assaltare un'altra gioielleria.", ephemeral=True)
            except Exception: pass
            return
        inv = get_inventario(uid)
        items_mancanti = []
        if inv.get("Dispositivo di Hacking Medio", 0) < 1:
            items_mancanti.append("1x Dispositivo di Hacking Medio (da `/compranero`)")
        if inv.get("Gas Soporifero", 0) < 1:
            items_mancanti.append("1x Gas Soporifero (da `/compranero`)")
        if items_mancanti:
            try:
                await interaction.response.send_message(
                    "🔒 Ti mancano:\n• " + "\n• ".join(items_mancanti), ephemeral=True)
            except Exception: pass
            return
        try:
            await interaction.response.send_modal(GioielleriaModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] GioielleriaModal già risposta uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] GioielleriaModal 10062 uid={uid}")
        except Exception as e:
            print(f"[RAPINA] GioielleriaModal errore: {e}")

    elif tipo.value == "mazebank":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("mazebank", 0)
        if ora - ultimo < 168 * 3600:
            rimanenti = int(168 * 3600 - (ora - ultimo))
            ore_r, min_r = rimanenti // 3600, (rimanenti % 3600) // 60
            try:
                await interaction.response.send_message(
                    f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di colpire un'altra Maze Bank.", ephemeral=True)
            except Exception: pass
            return
        inv = get_inventario(uid)
        items_mancanti = []
        if inv.get("Dispositivo di Hacking Avanzato", 0) < 1:
            items_mancanti.append("1x Dispositivo di Hacking Avanzato (da `/compranero`)")
        if inv.get("Lancia Termica", 0) < 1:
            items_mancanti.append("1x Lancia Termica (da `/compranero`)")
        if inv.get("Trapano Pesante Professionale", 0) < 1:
            items_mancanti.append("1x Trapano Pesante Professionale (da `/compranero`)")
        if inv.get("Grimaldello Avanzato", 0) < 2:
            mancanti = 2 - inv.get("Grimaldello Avanzato", 0)
            items_mancanti.append(f"{mancanti}x Grimaldello Avanzato (hai `{inv.get('Grimaldello Avanzato',0)}/2` — da `/negozio`)")
        if items_mancanti:
            try:
                await interaction.response.send_message(
                    "🔒 Ti mancano:\n• " + "\n• ".join(items_mancanti), ephemeral=True)
            except Exception: pass
            return
        try:
            await interaction.response.send_modal(MazeBankModal(uid))
        except discord.InteractionResponded:
            print(f"[RAPINA] MazeBankModal già risposta uid={uid}")
        except discord.NotFound:
            print(f"[RAPINA] MazeBankModal 10062 uid={uid}")
        except Exception as e:
            print(f"[RAPINA] MazeBankModal errore: {e}")


# =============================================================================
# COMANDO PULISCI — Cancella messaggi (solo staff)
# =============================================================================
RUOLI_PULISCI = {
    1514817350359060571,  # Founder
    1514817646229717174,  # CEO
    1514818027882024960,  # CO CEO
    1513686043155763280,  # Moderatore
}

@bot.tree.command(name="pulisci", description="Cancella un numero di messaggi recenti dal canale (solo staff)")
@app_commands.describe(quantita="Quanti messaggi cancellare (1–100)")
async def pulisci(interaction: discord.Interaction, quantita: app_commands.Range[int, 1, 100]):
    member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
    role_ids = {r.id for r in member.roles} if member else set()
    if not role_ids.intersection(RUOLI_PULISCI):
        await interaction.response.send_message(
            "❌ Non hai i permessi per usare questo comando.", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True)
    try:
        cancellati = await interaction.channel.purge(limit=quantita)
        await interaction.followup.send(
            f"🗑️ Cancellati **{len(cancellati)}** messaggi.", ephemeral=True
        )
        print(f"[PULISCI] {interaction.user} ha cancellato {len(cancellati)} messaggi in #{interaction.channel.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Non ho i permessi per cancellare messaggi in questo canale.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# MODULO PG — Richiesta Personaggio (Whitelist)
# =============================================================================

class RifiutoPGModal(discord.ui.Modal, title="❌ Motivo del Rifiuto PG"):
    """Modal che lo staffer compila per specificare il motivo del rifiuto."""
    motivo = discord.ui.TextInput(
        label="Motivo del rifiuto",
        placeholder="Spiega al giocatore perché la richiesta è stata rifiutata...",
        min_length=10,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, autore_id: int, nome_pg: str):
        super().__init__()
        self.autore_id = autore_id
        self.nome_pg   = nome_pg

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        richiesta = richieste_pg_pendenti.get(self.autore_id)
        if not richiesta or richiesta.get("processata"):
            await interaction.followup.send("⚠️ Questa richiesta è già stata processata.", ephemeral=True)
            return

        richiesta["processata"] = True
        salva_dati()

        # Disabilita i bottoni sul messaggio staff
        for child in interaction.message.components:
            pass  # gestito sotto con edit_message
        embed_staff = discord.Embed(
            title="❌ RICHIESTA PG RIFIUTATA",
            description=(
                f"La richiesta di **{self.nome_pg}** è stata **rifiutata** da {interaction.user.mention}.\n\n"
                f"📝 **Motivo:** {self.motivo.value.strip()}"
            ),
            color=discord.Color.red(),
        )
        embed_staff.set_footer(text=f"User ID: {self.autore_id} | Tokyo Horizon RP | Whitelist")
        await interaction.message.edit(embed=embed_staff, view=None)

        # Notifica nel canale esito PG (pubblico)
        try:
            canale_esito = bot.get_channel(CANALE_ESITO_PG) or await bot.fetch_channel(CANALE_ESITO_PG)
            embed_esito = discord.Embed(
                title="❌ Richiesta Personaggio Rifiutata",
                description=(
                    f"<@{self.autore_id}> la tua richiesta di personaggio **{self.nome_pg}** "
                    f"è stata **rifiutata** dallo staff.\n\n"
                    f"📝 **Motivo:** {self.motivo.value.strip()}\n\n"
                    "Correggila e ripresentala quando vuoi usando il bottone **📋 Richiesta PG**. 🗼"
                ),
                color=discord.Color.red(),
            )
            embed_esito.set_footer(text="Tokyo Horizon RP | Sistema Whitelist")
            await canale_esito.send(content=f"<@{self.autore_id}>", embed=embed_esito)
            print(f"[PG] Richiesta rifiutata per uid={self.autore_id} — notifica in esito PG inviata.")
        except Exception as e:
            print(f"[PG] ❌ Errore notifica rifiuto in esito PG: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"[PG RIFIUTO MODAL] Errore: {type(error).__name__}: {error}")
        try:
            await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


class RevisionePGView(discord.ui.View):
    """
    Vista persistente per la revisione delle richieste PG.
    - custom_id univoco per utente: sopravvive ai riavvii del bot
    """
    def __init__(self, autore_id: int):
        super().__init__(timeout=None)
        self.autore_id = autore_id

        btn_accetta = discord.ui.Button(
            label="✅ Accetta",
            style=discord.ButtonStyle.success,
            custom_id=f"pg:accetta:{autore_id}",
        )
        btn_accetta.callback = self._accetta
        self.add_item(btn_accetta)

        btn_rifiuta = discord.ui.Button(
            label="❌ Rifiuta",
            style=discord.ButtonStyle.danger,
            custom_id=f"pg:rifiuta:{autore_id}",
        )
        btn_rifiuta.callback = self._rifiuta
        self.add_item(btn_rifiuta)

    async def _accetta(self, interaction: discord.Interaction):
        if not ha_permessi_revisione_pg(interaction):
            await interaction.response.send_message(
                "❌ Solo il gestore WL o lo staff può approvare le richieste PG.", ephemeral=True
            )
            return

        richiesta = richieste_pg_pendenti.get(self.autore_id)
        if not richiesta or richiesta.get("processata"):
            await interaction.response.send_message(
                "⚠️ Questa richiesta è già stata processata.", ephemeral=True
            )
            return

        nome_pg = richiesta.get("nome", "?")
        richiesta["processata"] = True
        salva_dati()

        embed_staff = discord.Embed(
            title="✅ RICHIESTA PG ACCETTATA",
            description=(
                f"La richiesta di **{nome_pg}** è stata **accettata** da {interaction.user.mention}."
            ),
            color=discord.Color.green(),
        )
        embed_staff.set_footer(text=f"User ID: {self.autore_id} | Tokyo Horizon RP | Whitelist")
        await interaction.response.edit_message(embed=embed_staff, view=None)

        # Notifica nel canale esito PG (pubblico)
        try:
            canale_esito = bot.get_channel(CANALE_ESITO_PG) or await bot.fetch_channel(CANALE_ESITO_PG)
            embed_esito = discord.Embed(
                title="✅ Richiesta Personaggio Accettata!",
                description=(
                    f"<@{self.autore_id}> il tuo personaggio **{nome_pg}** è stato accettato, "
                    f"hai superato la prima fase! 🎉\n\n"
                    "Sarai contattato a breve per il **colloquio orale** e il completamento della whitelist.\n"
                    "Benvenuto su Tokyo Horizon RP! 🗼"
                ),
                color=discord.Color.green(),
            )
            embed_esito.set_footer(text="Tokyo Horizon RP | Sistema Whitelist")
            await canale_esito.send(content=f"<@{self.autore_id}>", embed=embed_esito)
            print(f"[PG] Richiesta accettata per uid={self.autore_id} — notifica in esito PG inviata.")
        except Exception as e:
            print(f"[PG] ❌ Errore notifica accettazione in esito PG: {e}")

    async def _rifiuta(self, interaction: discord.Interaction):
        if not ha_permessi_revisione_pg(interaction):
            await interaction.response.send_message(
                "❌ Solo il gestore WL o lo staff può rifiutare le richieste PG.", ephemeral=True
            )
            return

        richiesta = richieste_pg_pendenti.get(self.autore_id)
        if not richiesta or richiesta.get("processata"):
            await interaction.response.send_message(
                "⚠️ Questa richiesta è già stata processata.", ephemeral=True
            )
            return

        nome_pg = richiesta.get("nome", "?")
        await interaction.response.send_modal(RifiutoPGModal(autore_id=self.autore_id, nome_pg=nome_pg))


class RichiestaPGModal(discord.ui.Modal, title="📋 Richiesta Personaggio — Tokyo Horizon RP"):
    nome_cognome = discord.ui.TextInput(
        label="1. Nome e Cognome del Personaggio",
        placeholder="Es: Luca Moretti  (includi il soprannome se ce l'hai)",
        min_length=3,
        max_length=80,
        style=discord.TextStyle.short,
    )
    eta = discord.ui.TextInput(
        label="2. Età del Personaggio",
        placeholder="Es: 28",
        min_length=1,
        max_length=10,
        style=discord.TextStyle.short,
    )
    background = discord.ui.TextInput(
        label="3. Breve Storia (Background)",
        placeholder="Qualche riga su chi è e come è arrivato a Tokyo Horizon...",
        min_length=20,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )
    esperienza_rp = discord.ui.TextInput(
        label="4. Hai già esperienza di RP?",
        placeholder="Sì / No — e se sì, dove hai già giocato",
        min_length=2,
        max_length=200,
        style=discord.TextStyle.short,
    )
    disponibilita = discord.ui.TextInput(
        label="5. Disponibilità per il colloquio orale",
        placeholder="Es: Lunedì-Venerdì dopo le 19:00, weekend tutto il giorno",
        min_length=5,
        max_length=200,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        uid   = interaction.user.id
        nome  = self.nome_cognome.value.strip()
        eta   = self.eta.value.strip()
        bg    = self.background.value.strip()
        exp   = self.esperienza_rp.value.strip()
        dispo = self.disponibilita.value.strip()

        # Conferma all'utente
        embed_utente = discord.Embed(
            title="✅ Richiesta PG Inviata!",
            description=(
                "La tua richiesta di personaggio è stata inviata allo staff.\n"
                f"Riceverai un messaggio in <#{CANALE_ESITO_PG}> non appena verrà revisionata.\n\n"
                "Nel frattempo puoi esplorare il server e leggere le regole. 🗼"
            ),
            color=discord.Color.green(),
        )
        embed_utente.set_footer(text="Tokyo Horizon RP | Sistema Whitelist")
        await interaction.followup.send(embed=embed_utente, ephemeral=True)

        # Registra la richiesta come pendente
        richieste_pg_pendenti[uid] = {"nome": nome, "processata": False}
        salva_dati()

        # Registra la view persistente
        view = RevisionePGView(autore_id=uid)
        bot.add_view(view)

        # Embed per il canale revisione staff
        embed_staff = discord.Embed(
            title="📋 NUOVA RICHIESTA PERSONAGGIO",
            color=discord.Color.blurple(),
        )
        embed_staff.set_author(
            name=f"{interaction.user.display_name} ({interaction.user})",
            icon_url=interaction.user.display_avatar.url,
        )
        embed_staff.add_field(name="1️⃣ Nome e Cognome", value=nome, inline=False)
        embed_staff.add_field(name="2️⃣ Età", value=eta, inline=True)
        embed_staff.add_field(name="4️⃣ Esperienza RP", value=exp, inline=True)
        embed_staff.add_field(name="3️⃣ Background", value=bg, inline=False)
        embed_staff.add_field(name="5️⃣ Disponibilità colloquio", value=dispo, inline=False)
        embed_staff.set_footer(text=f"User ID: {uid} | Tokyo Horizon RP | Whitelist")

        try:
            canale_rev = bot.get_channel(CANALE_REVISIONE_PG) or await bot.fetch_channel(CANALE_REVISIONE_PG)
            await canale_rev.send(
                content=(
                    f"<@&{RUOLO_GESTORE_WL}> 📩 Nuova richiesta PG da {interaction.user.mention}!"
                ),
                embed=embed_staff,
                view=view,
            )
            print(f"[PG] Richiesta inviata da {interaction.user} (id={uid})")
        except Exception as e:
            print(f"[PG] ❌ Errore invio richiesta nel canale revisione: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"[PG MODAL] Errore: {type(error).__name__}: {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


class RichiestaPGView(discord.ui.View):
    """Vista persistente — il bottone rimane attivo dopo i riavvii del bot."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 Richiesta PG",
        style=discord.ButtonStyle.primary,
        custom_id="pg:richiesta",
    )
    async def apri_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RichiestaPGModal())


@bot.tree.command(
    name="setuppg",
    description="[MOD] Pubblica il pannello richiesta personaggio nel canale WL",
)
async def setuppg(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🗼 Richiesta Personaggio — Tokyo Horizon RP",
        description=(
            "Benvenuto/a su **Tokyo Horizon RP**!\n\n"
            "Per ottenere la **whitelist** e iniziare a giocare devi compilare la tua "
            "**scheda personaggio**. Clicca il bottone qui sotto e rispondi alle domande.\n\n"
            "📌 **Come funziona:**\n"
            "• Premi **📋 Richiesta PG** e compila il form\n"
            "• Lo staff riceverà la tua richiesta e ti contatterà\n"
            "• Farai un breve **colloquio orale** per completare la whitelist\n\n"
            "Hai dubbi? Apri un ticket o contatta lo staff. Buon roleplay! 🎮"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.set_footer(text="Tokyo Horizon RP | Sistema Whitelist")

    try:
        canale = bot.get_channel(CANALE_PG) or await bot.fetch_channel(CANALE_PG)
        await canale.send(embed=embed, view=RichiestaPGView())
        await interaction.followup.send(
            f"✅ Pannello PG pubblicato in <#{CANALE_PG}>!", ephemeral=True
        )
        print(f"[PG] Pannello pubblicato da {interaction.user} in #{canale.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ Il bot non ha i permessi per scrivere in <#{CANALE_PG}>.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# MODULO CARTA D'IDENTITÀ
# =============================================================================

_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_CJK     = "assets/fonts/NotoSansCJKjp-Regular.otf"

# Colori stile 在留カード giapponese
_C_BG        = (242, 245, 252)   # sfondo carta celeste chiaro
_C_WHITE     = (255, 255, 255)
_C_NAVY      = (15,  25,  70)    # header/footer navy
_C_LABEL_JP  = (148,  20,  65)   # etichette giapponesi bordeaux
_C_LABEL_EN  = (90,  100, 140)   # etichette inglesi grigio-blu
_C_VALUE     = (10,   15,  45)   # testo valore scuro
_C_DIVIDER   = (190, 198, 220)   # linee divisorie
_C_RED_SEAL  = (185,  20,  20)   # timbro rosso
_C_GOLD      = (170, 130,  20)   # accento dorato
_C_PHOTO_BG  = (225, 230, 245)   # sfondo placeholder foto


async def _scarica_foto(session: aiohttp.ClientSession, url: str):
    """Scarica l'immagine dalla URL e la restituisce come oggetto PIL Image, o None."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                data = await r.read()
                from PIL import Image
                img = Image.open(io.BytesIO(data)).convert("RGB")
                return img
    except Exception as e:
        print(f"[CARTA] ❌ Download foto fallito: {e}")
    return None


def _tronca(testo: str, font, max_w: int) -> str:
    """Tronca il testo con '…' se supera max_w pixel."""
    from PIL import ImageFont
    while font.getlength(testo) > max_w and len(testo) > 1:
        testo = testo[:-1]
    return testo if font.getlength(testo) <= max_w else testo[:-1] + "…"


async def _genera_carta_img(
    nome: str,
    data_luogo: str,
    eta_sesso: str,
    segni: str,
    foto_url: str | None,
) -> discord.File:
    from PIL import Image, ImageDraw, ImageFont
    import hashlib

    W, H = 960, 580

    img  = Image.new("RGB", (W, H), _C_BG)
    draw = ImageDraw.Draw(img)

    # --- Watermark: griglia di cerchi sovrapposti (stile 在留カード) ---
    for ix in range(-20, W + 20, 44):
        for iy in range(-20, H + 20, 44):
            draw.ellipse([ix - 16, iy - 16, ix + 16, iy + 16],
                         outline=(218, 224, 240), width=1)

    # --- Font ---
    try:
        fj_big   = ImageFont.truetype(_FONT_CJK, 20)
        fj_med   = ImageFont.truetype(_FONT_CJK, 14)
        fj_sm    = ImageFont.truetype(_FONT_CJK, 11)
        fj_title = ImageFont.truetype(_FONT_CJK, 30)
        fe_bold  = ImageFont.truetype(_FONT_BOLD,    16)
        fe_med   = ImageFont.truetype(_FONT_BOLD,    13)
        fe_sm    = ImageFont.truetype(_FONT_REGULAR, 11)
        fe_val   = ImageFont.truetype(_FONT_BOLD,    15)
        fe_valsm = ImageFont.truetype(_FONT_BOLD,    13)
        fe_hdr   = ImageFont.truetype(_FONT_BOLD,    11)
    except Exception:
        fj_big = fj_med = fj_sm = fj_title = fe_bold = fe_med = \
        fe_sm = fe_val = fe_valsm = fe_hdr = ImageFont.load_default()

    # =========================================================
    # HEADER BAR
    # =========================================================
    HDR_H = 54
    draw.rectangle([0, 0, W, HDR_H], fill=_C_NAVY)
    # Sinistra: "東京ホライゾン RP" + sub
    draw.text((14, 8),  "東京ホライゾン RP", font=fj_med,  fill=_C_WHITE)
    draw.text((14, 28), "TOKYO HORIZON RP",  font=fe_hdr, fill=(170, 180, 210))
    # Centro: titolo grande
    draw.text((W // 2, 10), "在留カード",        font=fj_title, fill=_C_WHITE, anchor="mt")
    draw.text((W // 2, 40), "CARTA PERSONAGGIO", font=fe_hdr,   fill=(170, 180, 210), anchor="mt")
    # Destra: numero carta
    card_num = "TH-" + hashlib.md5(nome.encode()).hexdigest()[:6].upper()
    draw.text((W - 14, 9),  "番号",   font=fj_sm,  fill=(170, 180, 210), anchor="rt")
    draw.text((W - 14, 22), "N.",     font=fe_hdr, fill=(170, 180, 210), anchor="rt")
    draw.text((W - 14, 35), card_num, font=fe_hdr, fill=_C_WHITE,        anchor="rt")
    # Linea oro sotto header
    draw.line([0, HDR_H, W, HDR_H], fill=_C_GOLD, width=2)

    # =========================================================
    # LAYOUT COSTANTI
    # =========================================================
    CY   = HDR_H + 2        # content start y
    FX   = 12               # field x start
    PH_X = 710              # foto colonna x
    PH_W = W - PH_X - 14   # foto width  (~236px)
    PH_H = 290              # foto height

    # Sfondo bianco zona foto
    draw.rectangle([PH_X - 1, CY, W, H], fill=_C_WHITE)
    draw.line([PH_X - 1, CY, PH_X - 1, H], fill=_C_DIVIDER, width=2)

    FIELD_W = PH_X - FX - 8  # larghezza disponibile campi

    def draw_row(y, h, jp_lbl, en_lbl, value, vfont=None, alt=False):
        """Disegna una riga campo stile 在留カード."""
        draw.rectangle([0, y, PH_X - 2, y + h], fill=(_C_WHITE if alt else _C_BG))
        draw.text((FX,      y + 3),  jp_lbl, font=fj_sm,  fill=_C_LABEL_JP)
        draw.text((FX,      y + 16), en_lbl, font=fe_hdr, fill=_C_LABEL_EN)
        draw.line([FX, y + 29, PH_X - 10, y + 29], fill=_C_DIVIDER, width=1)
        if value:
            vf = vfont or fe_val
            v  = _tronca(value, vf, FIELD_W - 8)
            draw.text((FX + 4, y + 32), v, font=vf, fill=_C_VALUE)
        draw.line([0, y + h - 1, PH_X - 2, y + h - 1], fill=_C_DIVIDER, width=1)
        return y + h

    # --- Parsing ---
    eta_val = sesso_val = ""
    if "/" in eta_sesso:
        p = [x.strip() for x in eta_sesso.split("/", 1)]
        eta_val, sesso_val = p[0], p[1]
    else:
        eta_val = eta_sesso.strip()

    oggi     = date.today()
    scadenza = oggi.replace(year=oggi.year + 1)
    rilascio_str = oggi.strftime("%Y年%m月%d日")
    scadenza_str = scadenza.strftime("%Y年%m月%d日")

    y = CY

    # Riga 1 — 氏名 / NOME
    y = draw_row(y, 62, "氏名", "NOME", nome, fe_val, alt=True)

    # Riga 2 — 生年月日 / DATE OF BIRTH  +  性別 / SEX  (split orizzontale)
    r2h = 56
    draw.rectangle([0, y, PH_X - 2, y + r2h], fill=_C_BG)
    c1w = int(FIELD_W * 0.64)
    # Data/luogo
    draw.text((FX,      y + 3),  "生年月日",        font=fj_sm,  fill=_C_LABEL_JP)
    draw.text((FX,      y + 16), "DATA DI NASCITA / LUOGO", font=fe_hdr, fill=_C_LABEL_EN)
    draw.line([FX, y + 29, FX + c1w, y + 29], fill=_C_DIVIDER, width=1)
    draw.text((FX + 4,  y + 32), _tronca(data_luogo, fe_valsm, c1w - 8), font=fe_valsm, fill=_C_VALUE)
    # Sesso
    sx = FX + c1w + 12
    sw = PH_X - sx - 10
    draw.text((sx,     y + 3),  "性別",  font=fj_sm,  fill=_C_LABEL_JP)
    draw.text((sx,     y + 16), "SESSO", font=fe_hdr, fill=_C_LABEL_EN)
    draw.line([sx, y + 29, sx + sw, y + 29], fill=_C_DIVIDER, width=1)
    draw.text((sx + 4, y + 32), sesso_val or eta_val, font=fe_val, fill=_C_VALUE)
    draw.line([0, y + r2h - 1, PH_X - 2, y + r2h - 1], fill=_C_DIVIDER, width=1)
    y += r2h

    # Riga 3 — 国籍・地域 / NATIONALITY
    y = draw_row(y, 50, "国籍・地域", "NAZIONALITÀ / REGIONE",
                 "Tokyo Horizon", fe_valsm, alt=True)

    # Riga 4 — 住居地 / INDIRIZZO
    y = draw_row(y, 50, "住居地", "INDIRIZZO",
                 "Tokyo Horizon RP — Città Virtuale", fe_valsm)

    # Riga 5 — 在留資格 / STATO
    y = draw_row(y, 50, "在留資格", "STATO",
                 "Personaggio Registrato", fe_valsm, alt=True)

    # Riga 6 — 特記事項 / NOTE SPECIALI
    y = draw_row(y, 58, "特記事項", "NOTE SPECIALI", segni, fe_valsm)

    # Riga 7 — Date affiancate (rilascio | scadenza)
    r7h = 56
    draw.rectangle([0, y, PH_X - 2, y + r7h], fill=_C_WHITE)
    hw = (FIELD_W - 16) // 2
    # Rilascio
    draw.text((FX,        y + 3),  "交付年月日",      font=fj_sm,  fill=_C_LABEL_JP)
    draw.text((FX,        y + 16), "DATA DI RILASCIO", font=fe_hdr, fill=_C_LABEL_EN)
    draw.line([FX, y + 29, FX + hw, y + 29], fill=_C_DIVIDER, width=1)
    draw.text((FX + 4,    y + 32), rilascio_str,      font=fe_valsm, fill=_C_VALUE)
    # Scadenza
    ex = FX + hw + 16
    draw.text((ex,        y + 3),  "在留期間（満了日）",     font=fj_sm,  fill=_C_LABEL_JP)
    draw.text((ex,        y + 16), "PERIODO DI VALIDITÀ (SCADENZA)", font=fe_hdr, fill=_C_LABEL_EN)
    draw.line([ex, y + 29, ex + hw, y + 29], fill=_C_DIVIDER, width=1)
    draw.text((ex + 4,    y + 32), scadenza_str, font=fe_valsm, fill=_C_RED_SEAL)
    draw.line([0, y + r7h - 1, PH_X - 2, y + r7h - 1], fill=_C_DIVIDER, width=1)
    y += r7h

    # =========================================================
    # FOTO
    # =========================================================
    PH_PX = PH_X + 8
    PH_PY = CY + 6
    draw.rectangle([PH_PX, PH_PY, PH_PX + PH_W, PH_PY + PH_H],
                   fill=_C_PHOTO_BG, outline=_C_DIVIDER, width=1)

    foto_img = None
    if foto_url:
        foto_img = await _scarica_foto(bot.aiohttp_session, foto_url)

    if foto_img:
        ratio = max(PH_W / foto_img.width, PH_H / foto_img.height)
        nw    = int(foto_img.width  * ratio)
        nh    = int(foto_img.height * ratio)
        foto_img = foto_img.resize((nw, nh), Image.LANCZOS)
        cx = (nw - PH_W) // 2
        cy_c = (nh - PH_H) // 2
        foto_img = foto_img.crop((cx, cy_c, cx + PH_W, cy_c + PH_H))
        img.paste(foto_img, (PH_PX, PH_PY))
        draw.rectangle([PH_PX, PH_PY, PH_PX + PH_W, PH_PY + PH_H],
                       outline=_C_DIVIDER, width=1)
    else:
        draw.text(
            (PH_PX + PH_W // 2, PH_PY + PH_H // 2),
            "写真\nFOTO",
            font=fj_med, fill=_C_LABEL_EN,
            anchor="mm", align="center",
        )

    # --- "TOKYO HORIZON RP" verticale (lato destro, come MINISTRY OF JUSTICE) ---
    try:
        vert_txt = "TOKYO HORIZON RP"
        tw       = int(fe_hdr.getlength(vert_txt))
        vert_img = Image.new("RGBA", (tw + 4, 14), (0, 0, 0, 0))
        vd       = ImageDraw.Draw(vert_img)
        vd.text((0, 0), vert_txt, font=fe_hdr, fill=_C_NAVY)
        vert_rot = vert_img.rotate(90, expand=True)
        vx = W - 13
        vy = CY + 10
        img.paste(vert_rot, (vx, vy), vert_rot)
    except Exception:
        pass

    # --- Timbro rosso 法務大臣印 ---
    seal_cx = PH_X + (W - PH_X) // 2
    seal_cy = PH_PY + PH_H + 46
    sr      = 38
    draw.ellipse([seal_cx - sr,     seal_cy - sr,     seal_cx + sr,     seal_cy + sr],
                 outline=_C_RED_SEAL, width=3)
    draw.ellipse([seal_cx - sr + 5, seal_cy - sr + 5, seal_cx + sr - 5, seal_cy + sr - 5],
                 outline=_C_RED_SEAL, width=1)
    draw.text((seal_cx, seal_cy - 8), "法務",   font=fj_med, fill=_C_RED_SEAL, anchor="mm")
    draw.text((seal_cx, seal_cy + 9), "大臣印", font=fj_sm,  fill=_C_RED_SEAL, anchor="mm")

    # --- MOJ badge (come nella carta originale) ---
    badge_y = PH_PY + PH_H + 4
    draw.text((PH_X + 10, badge_y), "◆MOJ◆", font=fe_hdr, fill=_C_NAVY)

    # =========================================================
    # FOOTER BAR
    # =========================================================
    footer_y = max(y + 2, H - 68)
    draw.rectangle([0, footer_y, W, H], fill=_C_NAVY)
    draw.line([0, footer_y, W, footer_y], fill=_C_GOLD, width=2)
    # Testo footer giapponese + inglese
    draw.text(
        (14, footer_y + 8),
        f"このカードは {scadenza_str} まで有効です",
        font=fj_med, fill=_C_WHITE,
    )
    draw.text(
        (14, footer_y + 30),
        f"PERIODO DI VALIDITÀ DELLA CARTA  ·  {scadenza.strftime('%d / %m / %Y')}",
        font=fe_hdr, fill=(170, 180, 210),
    )
    # Riga bassa sottolineata come nell'originale
    draw.line([14, footer_y + 26, W - 14, footer_y + 26], fill=_C_GOLD, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="carta_identita.png")


class CartaIdentitaModal(discord.ui.Modal, title="🪪 Carta d'Identità — Tokyo Horizon RP"):
    nome_cognome = discord.ui.TextInput(
        label="Nome e Cognome del Personaggio",
        placeholder="Es: Luca Moretti",
        min_length=3,
        max_length=80,
        style=discord.TextStyle.short,
    )
    data_luogo = discord.ui.TextInput(
        label="Data e Luogo di Nascita",
        placeholder="Es: 15/06/1995, Roma",
        min_length=3,
        max_length=80,
        style=discord.TextStyle.short,
    )
    eta_sesso = discord.ui.TextInput(
        label="Età / Sesso  (es: 28 / M  oppure  28 / F)",
        placeholder="Es: 28 / M",
        min_length=3,
        max_length=20,
        style=discord.TextStyle.short,
    )
    segni = discord.ui.TextInput(
        label="Segni Particolari",
        placeholder="Es: Cicatrice sul sopracciglio sinistro, tatuaggio sul collo",
        min_length=2,
        max_length=200,
        style=discord.TextStyle.short,
    )
    foto_url = discord.ui.TextInput(
        label="URL Foto  (carica su Discord → copia link)",
        placeholder="https://cdn.discordapp.com/... oppure lascia vuoto",
        required=False,
        min_length=0,
        max_length=500,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        nome      = self.nome_cognome.value.strip()
        dl        = self.data_luogo.value.strip()
        es        = self.eta_sesso.value.strip()
        segni_val = self.segni.value.strip()
        url       = self.foto_url.value.strip() or None

        try:
            carta = await _genera_carta_img(nome, dl, es, segni_val, url)
        except Exception as e:
            print(f"[CARTA] ❌ Generazione immagine fallita: {e}")
            await interaction.followup.send(
                "❌ Errore nella generazione della carta. Riprova o contatta lo staff.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🪪 Carta d'Identità Emessa",
            description=(
                f"**{nome}** — la tua Carta d'Identità è stata generata.\n\n"
                "Conserva questo documento: ti verrà richiesto dalla polizia, "
                "per l'acquisto di veicoli e per altre attività ufficiali.\n\n"
                "⚠️ Salva l'immagine — il messaggio è privato e temporaneo."
            ),
            color=discord.Color.from_rgb(212, 175, 55),
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Documenti")

        await interaction.followup.send(embed=embed, file=carta, ephemeral=True)
        print(f"[CARTA] Carta generata per {interaction.user} (id={interaction.user.id}) — nome PG: {nome}")

        # Assegna il ruolo Cittadino Tokyo Horizon
        try:
            member = interaction.user
            ruolo = interaction.guild.get_role(RUOLO_CITTADINO)
            if ruolo and isinstance(member, discord.Member):
                await member.add_roles(ruolo, reason="Carta d'identità completata")
                print(f"[CARTA] Ruolo Cittadino assegnato a {member} (id={member.id})")
            elif not ruolo:
                print(f"[CARTA] ⚠️ Ruolo {RUOLO_CITTADINO} non trovato nel server")
        except discord.Forbidden:
            print(f"[CARTA] ❌ Permessi insufficienti per assegnare il ruolo a {interaction.user}")
        except Exception as e:
            print(f"[CARTA] ❌ Errore assegnazione ruolo: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"[CARTA MODAL] {type(error).__name__}: {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Errore temporaneo. Riprova.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Errore temporaneo. Riprova.", ephemeral=True)
        except Exception:
            pass


class CartaIdentitaView(discord.ui.View):
    """Vista persistente — sopravvive ai riavvii del bot."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🪪 Richiedi Carta d'Identità",
        style=discord.ButtonStyle.primary,
        custom_id="carta:richiedi",
    )
    async def apri_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CartaIdentitaModal())


@bot.tree.command(
    name="setupcarta",
    description="[MOD] Pubblica il pannello Carta d'Identità nel canale documenti",
)
async def setupcarta(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🪪 Carta d'Identità — Tokyo Horizon RP",
        description=(
            "Ogni membro della città deve essere in possesso della propria "
            "**Carta d'Identità** per svolgere attività ufficiali.\n\n"
            "📌 **A cosa serve:**\n"
            "• Identificarti durante i controlli della polizia\n"
            "• Acquistare veicoli e immobili\n"
            "• Accedere a servizi della città\n\n"
            "🖱️ Clicca il bottone qui sotto, compila i dati del tuo personaggio "
            "e riceverai la carta **istantaneamente** — visibile solo a te.\n\n"
            "⚠️ **Salva l'immagine generata!** Il messaggio è privato e temporaneo."
        ),
        color=discord.Color.from_rgb(212, 175, 55),
    )
    embed.set_footer(text="Tokyo Horizon RP | Ufficio Anagrafe")

    try:
        canale = bot.get_channel(CANALE_CARTA) or await bot.fetch_channel(CANALE_CARTA)
        await canale.send(embed=embed, view=CartaIdentitaView())
        await interaction.followup.send(
            f"✅ Pannello Carta d'Identità pubblicato in <#{CANALE_CARTA}>!", ephemeral=True
        )
        print(f"[CARTA] Pannello pubblicato da {interaction.user} in #{canale.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ Il bot non ha i permessi per scrivere in <#{CANALE_CARTA}>.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# PANNELLO TUTORIAL WHITELIST
# =============================================================================

CANALE_TUTORIAL_WL = 1516184631857385592   # canale tutorial / come ottenere la wl

@bot.tree.command(
    name="setuptutorial",
    description="[MOD] Pubblica il messaggio tutorial WL nel canale apposito",
)
async def setuptutorial(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🗼 Come diventare Residente di Tokyo Horizon",
        description=(
            "Benvenuto/a! Per ottenere la **whitelist** e iniziare a fare roleplay "
            "nella città devi seguire **3 semplici passi**.\n\u200b"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )

    embed.add_field(
        name="1️⃣  Compila il Modulo Personaggio (PG)",
        value=(
            "Vai nel canale apposito e premi il bottone **📋 Richiesta PG**.\n"
            "Compila il form con i dati del tuo personaggio e invialo.\n"
            "⏳ Attendi la conferma dello staff — ti arriverà una notifica nel canale esiti."
        ),
        inline=False,
    )

    embed.add_field(
        name="2️⃣  Studia il Regolamento",
        value=(
            "Nel frattempo leggi con attenzione:\n"
            "📖 **Regolamento Generale** — le regole base del server\n"
            "🗺️ **Regolamento Zone** — comportamenti specifici per ogni area della città\n"
            "La conoscenza del regolamento è **obbligatoria** per la WL orale."
        ),
        inline=False,
    )

    embed.add_field(
        name="3️⃣  Supera la Whitelist Orale",
        value=(
            "Dopo che il tuo PG è stato approvato, uno staffer ti contatterà "
            "per un breve **colloquio orale** sul regolamento.\n"
            "✅ Se lo superi… sei ufficialmente un **Residente di Tokyo Horizon**! 🎉"
        ),
        inline=False,
    )

    embed.set_footer(text="Tokyo Horizon RP | Benvenuto nella città")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/684/684908.png")

    try:
        canale = bot.get_channel(CANALE_TUTORIAL_WL) or await bot.fetch_channel(CANALE_TUTORIAL_WL)
        await canale.send(embed=embed)
        await interaction.followup.send(
            f"✅ Tutorial WL pubblicato in <#{CANALE_TUTORIAL_WL}>!", ephemeral=True
        )
        print(f"[TUTORIAL] Pannello pubblicato da {interaction.user} in #{canale.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ Il bot non ha i permessi per scrivere in <#{CANALE_TUTORIAL_WL}>.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# COMANDI SANZIONE (AVVISO / WARN / BAN / SCADENZA)
# =============================================================================

_CANALE_TICKET_PANNELLO = 1516194247210963015


class AvvisoModal(discord.ui.Modal, title="⚠️ Emetti Avviso"):
    player_id  = discord.ui.TextInput(label="🆔 ID Player",    placeholder="ID Discord o nome personaggio", max_length=100, required=False)
    sanzione   = discord.ui.TextInput(label="📄 Sanzione",     placeholder="Es. AVVISO 1", max_length=100, required=False)
    motivazione = discord.ui.TextInput(
        label="📝 Motivazione",
        style=discord.TextStyle.paragraph,
        placeholder="Descrivi la motivazione della sanzione...",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        player_line   = f"│  🆔 **Giocatore:** {self.player_id.value}\n"      if self.player_id.value.strip()   else ""
        sanzione_line = f"│  📋 **Tipo sanzione:** {self.sanzione.value}\n"   if self.sanzione.value.strip()    else ""
        motiv_line    = f"│  📝 **Motivazione:** {self.motivazione.value}\n"  if self.motivazione.value.strip() else ""
        embed = discord.Embed(color=discord.Color.from_rgb(255, 195, 0))
        embed.description = (
            "```ansi\n\u001b[1;33m【 ⚠️  COMUNICAZIONE UFFICIALE — AVVISO 】\u001b[0m\n```"
            f"🗼 **Tokyo Horizon RP** ha registrato una segnalazione a carico del seguente giocatore.\n\n"
            f"┌─────────────────────────┐\n"
            f"{player_line}"
            f"{sanzione_line}"
            f"{motiv_line}"
            f"│  👮 **Operatore:** {interaction.user.mention}\n"
            f"└─────────────────────────┘\n\n"
            f"─────────────────────────────\n"
            f"*Questo avviso è ufficialmente registrato nel sistema disciplinare di Tokyo Horizon. "
            f"In caso di contestazione, contatta lo staff tramite ticket.*"
        )
        embed.set_footer(text="🗼 Tokyo Horizon RP  ·  Sistema Disciplinare Ufficiale")
        await interaction.response.send_message(content=interaction.user.mention, embed=embed)
        print(f"[AVVISO] Emesso da {interaction.user} — player: {self.player_id.value}")


class WarnModal(discord.ui.Modal, title="🚨 Emetti Warn"):
    player_id   = discord.ui.TextInput(label="🆔 ID Player",   placeholder="ID Discord o nome personaggio", max_length=100, required=False)
    sanzione    = discord.ui.TextInput(label="📄 Sanzione",    placeholder="Es. WARN 1", max_length=100, required=False)
    motivazione = discord.ui.TextInput(
        label="📝 Motivazione",
        style=discord.TextStyle.paragraph,
        placeholder="Descrivi la motivazione del warn...",
        max_length=400,
        required=False,
    )
    note = discord.ui.TextInput(
        label="📌 Note (opzionale)",
        style=discord.TextStyle.paragraph,
        placeholder="Eventuali note aggiuntive...",
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        player_line   = f"│  🆔 **Giocatore:** {self.player_id.value}\n"      if self.player_id.value.strip()   else ""
        sanzione_line = f"│  📋 **Tipo sanzione:** {self.sanzione.value}\n"   if self.sanzione.value.strip()    else ""
        motiv_line    = f"│  📝 **Motivazione:** {self.motivazione.value}\n"  if self.motivazione.value.strip() else ""
        note_line     = f"│  📌 **Annotazione:** {self.note.value}\n"         if self.note.value.strip()        else ""
        embed = discord.Embed(color=discord.Color.from_rgb(230, 80, 0))
        embed.description = (
            "```ansi\n\u001b[1;31m【 🚨  PROVVEDIMENTO DISCIPLINARE — WARN 】\u001b[0m\n```"
            f"Il giocatore indicato ha ricevuto un **Warn ufficiale** da parte dello staff di 🗼 **Tokyo Horizon RP**.\n\n"
            f"┌─────────────────────────┐\n"
            f"{player_line}"
            f"{sanzione_line}"
            f"{motiv_line}"
            f"{note_line}"
            f"│  👮 **Operatore:** {interaction.user.mention}\n"
            f"└─────────────────────────┘\n\n"
            f"─────────────────────────────\n"
            f"⚠️ L'accumulo di Warn comporta l'applicazione di sanzioni progressivamente più severe, fino al ban dalla comunità.\n"
            f"*Per contestare questo provvedimento apri un ticket con lo staff.*"
        )
        embed.set_footer(text="🗼 Tokyo Horizon RP  ·  Sistema Disciplinare Ufficiale")
        await interaction.response.send_message(content=interaction.user.mention, embed=embed)
        print(f"[WARN] Emesso da {interaction.user} — player: {self.player_id.value}")


class BanModal(discord.ui.Modal, title="⛔ Emetti Ban"):
    player_id   = discord.ui.TextInput(label="🆔 ID Player",   placeholder="ID Discord o nome personaggio", max_length=100, required=False)
    sanzione    = discord.ui.TextInput(label="📄 Sanzione",    placeholder="Es. BAN 24h / BAN PERMANENTE", max_length=100, required=False)
    motivazione = discord.ui.TextInput(
        label="📝 Motivazione",
        style=discord.TextStyle.paragraph,
        placeholder="Descrivi la motivazione del ban...",
        max_length=400,
        required=False,
    )
    consigli = discord.ui.TextInput(
        label="💬 Messaggio dallo staff (opzionale)",
        style=discord.TextStyle.paragraph,
        placeholder="Consigli o indicazioni per il giocatore...",
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        player_line   = f"│  🆔 **Giocatore:** {self.player_id.value}\n"      if self.player_id.value.strip()   else ""
        sanzione_line = f"│  📋 **Tipo sanzione:** {self.sanzione.value}\n"   if self.sanzione.value.strip()    else ""
        motiv_line    = f"│  📝 **Motivazione:** {self.motivazione.value}\n"  if self.motivazione.value.strip() else ""
        consigli_line = f"│  💬 **Msg staff:** {self.consigli.value}\n"        if self.consigli.value.strip()    else ""
        embed = discord.Embed(color=discord.Color.from_rgb(180, 0, 0))
        embed.description = (
            "```ansi\n\u001b[1;31m【 ⛔  ESPULSIONE DALLA COMUNITÀ — BAN 】\u001b[0m\n```"
            f"Il seguente giocatore è stato **bannato** dalla comunità di 🗼 **Tokyo Horizon RP** per violazione grave del regolamento.\n\n"
            f"┌─────────────────────────┐\n"
            f"{player_line}"
            f"{sanzione_line}"
            f"{motiv_line}"
            f"{consigli_line}"
            f"│  👮 **Operatore:** {interaction.user.mention}\n"
            f"└─────────────────────────┘\n\n"
            f"─────────────────────────────\n"
            f"⛔ Questo provvedimento è immediatamente operativo. "
            f"Se ritieni di poter presentare un ricorso, apri un ticket di **appeal** seguendo le istruzioni dello staff."
        )
        embed.set_footer(text="🗼 Tokyo Horizon RP  ·  Sistema Disciplinare Ufficiale")
        await interaction.response.send_message(content=interaction.user.mention, embed=embed)
        print(f"[BAN] Emesso da {interaction.user} — player: {self.player_id.value}")


class ScadenzaWarnModal(discord.ui.Modal, title="🔔 Avviso Scadenza Warn"):
    id_discord = discord.ui.TextInput(label="👤 ID Discord",  placeholder="ID Discord del giocatore", max_length=100, required=False)
    sanzione   = discord.ui.TextInput(label="📜 Sanzione",    placeholder="Es. WARN 1 — scaduto", max_length=100, required=False)
    motivo     = discord.ui.TextInput(
        label="⏳ Motivo",
        style=discord.TextStyle.paragraph,
        placeholder="Sanzione originale / motivo della scadenza...",
        max_length=400,
        required=False,
    )
    note = discord.ui.TextInput(
        label="📝 Note (opzionale)",
        style=discord.TextStyle.paragraph,
        placeholder="Istruzioni o note per il giocatore...",
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        player_line   = f"│  👤 **Giocatore:** {self.id_discord.value}\n"       if self.id_discord.value.strip() else ""
        sanzione_line = f"│  📜 **Sanzione scaduta:** {self.sanzione.value}\n"  if self.sanzione.value.strip()   else ""
        motivo_line   = f"│  ⏳ **Dettaglio:** {self.motivo.value}\n"            if self.motivo.value.strip()     else ""
        note_line     = f"│  📝 **Note:** {self.note.value}\n"                   if self.note.value.strip()       else ""
        embed = discord.Embed(color=discord.Color.from_rgb(88, 101, 242))
        embed.description = (
            "```ansi\n\u001b[1;34m【 🔔  NOTIFICA SCADENZA — WARN RIMOSSO 】\u001b[0m\n```"
            f"Lo staff di 🗼 **Tokyo Horizon RP** ti informa che una tua sanzione è giunta a scadenza naturale.\n\n"
            f"┌─────────────────────────┐\n"
            f"{player_line}"
            f"{sanzione_line}"
            f"{motivo_line}"
            f"{note_line}"
            f"│  👮 **Operatore:** {interaction.user.mention}\n"
            f"└─────────────────────────┘\n\n"
            f"─────────────────────────────\n"
            f"✅ Per procedere alla rimozione formale del ruolo sanzione, apri un ticket in <#{_CANALE_TICKET_PANNELLO}>."
        )
        embed.set_footer(text="🗼 Tokyo Horizon RP  ·  Sistema Disciplinare Ufficiale")
        await interaction.response.send_message(content=interaction.user.mention, embed=embed)
        print(f"[SCADENZA] Notifica inviata da {interaction.user} — player: {self.id_discord.value}")


# =============================================================================
# COMANDO /chie — COMUNICATO ANONIMO STAFF
# =============================================================================

class ChieModal(discord.ui.Modal, title="📢 Comunicato Staff"):
    testo = discord.ui.TextInput(
        label="✍️ Chi è che...",
        style=discord.TextStyle.paragraph,
        placeholder="Es. ...entra in server senza seguire le procedure di accesso?",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        corpo = self.testo.value.strip()
        embed = discord.Embed(color=discord.Color.from_rgb(114, 137, 218))
        embed.description = (
            "```ansi\n\u001b[1;36m【 📢  COMUNICATO DALLO STAFF 】\u001b[0m\n```"
            f"**Chi è che** {corpo}\n\n"
            f"─────────────────────────────\n"
            f"*Se ti riconosci in questo messaggio, contatta lo staff tramite ticket prima che vengano presi provvedimenti.*"
        ) if corpo else (
            "```ansi\n\u001b[1;36m【 📢  COMUNICATO DALLO STAFF 】\u001b[0m\n```"
            f"Lo staff di 🗼 **Tokyo Horizon RP** ha un comunicato per la community.\n\n"
            f"─────────────────────────────\n"
            f"*Per chiarimenti apri un ticket.*"
        )
        embed.set_footer(text="🗼 Tokyo Horizon RP  ·  Staff")
        await interaction.response.send_message(embed=embed)
        print(f"[CHIE] Comunicato inviato da {interaction.user}")


@bot.tree.command(name="chie", description="[MOD] Invia un comunicato anonimo 'Chi è che...' dalla staff")
async def cmd_chie(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)
        return
    await interaction.response.send_modal(ChieModal())


@bot.tree.command(name="avviso", description="[MOD] Emetti un avviso formale a un giocatore")
async def cmd_avviso(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)
        return
    await interaction.response.send_modal(AvvisoModal())


@bot.tree.command(name="warn", description="[MOD] Emetti un warn a un giocatore")
async def cmd_warn(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)
        return
    await interaction.response.send_modal(WarnModal())


@bot.tree.command(name="ban", description="[MOD] Emetti un ban a un giocatore")
async def cmd_ban(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)
        return
    await interaction.response.send_modal(BanModal())


@bot.tree.command(name="scadenza", description="[MOD] Notifica la scadenza di un warn a un giocatore")
async def cmd_scadenza(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)
        return
    await interaction.response.send_modal(ScadenzaWarnModal())


# =============================================================================
# PANNELLO SANZIONI
# =============================================================================

CANALE_SANZIONI = 1516222042817433661

@bot.tree.command(
    name="setupsanzioni",
    description="[MOD] Pubblica il pannello informativo delle sanzioni nel canale dedicato",
)
async def setupsanzioni(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        canale = bot.get_channel(CANALE_SANZIONI) or await bot.fetch_channel(CANALE_SANZIONI)
    except Exception as e:
        await interaction.followup.send(f"❌ Canale non trovato: {e}", ephemeral=True)
        return

    # ── Embed 1: intestazione + AVVISI & WARN ──────────────────────────────
    embed_warn = discord.Embed(
        title="⚖️ REGOLAMENTO SANZIONI — Tokyo Horizon RP",
        description=(
            "*Di seguito l'elenco completo delle sanzioni attive nel server, "
            "la loro durata e le modalità di gestione.*\n\u200b"
        ),
        color=discord.Color.from_rgb(230, 140, 20),
    )

    embed_warn.add_field(
        name="⏳ AVVISI — Richiami Progressivi",
        value=(
            "• <@&1516210042762690650> ➜ Primo richiamo formale — **2 giorni**\n"
            "• <@&1516210228490932334> ➜ Secondo richiamo — **4 giorni**\n"
            "• <@&1516210479385677944> ➜ Avviso finale prima del Warn — **6 giorni**\n"
        ),
        inline=False,
    )

    embed_warn.add_field(
        name="🔴 WARN — Sanzioni Disciplinari",
        value=(
            "• <@&1516210617415897128> ➜ Sanzione disciplinare lieve — **8 giorni**\n"
            "• <@&1516210769317068951> ➜ Sanzione disciplinare media — **12 giorni**\n"
            "• <@&1516210828699897927> ➜ Sanzione disciplinare grave — **16 giorni**\n"
            "• <@&1516211005666103357> ➜ Ultima opportunità nel server — **21 giorni**\n"
        ),
        inline=False,
    )

    embed_warn.set_footer(text="Tokyo Horizon RP | Sistema Sanzioni")

    # ── Embed 2: BAN temporanei + permanente ──────────────────────────────
    embed_ban = discord.Embed(
        color=discord.Color.from_rgb(200, 30, 30),
    )

    embed_ban.add_field(
        name="❌ BAN TEMPORANEI — Sospensione dalle Sessioni",
        value=(
            "• <@&1516211996561768578> ➜ Accesso alle sessioni negato per **24 ore**\n"
            "• <@&1516215698718855279> ➜ Accesso alle sessioni negato per **48 ore**\n"
            "• <@&1516215922430578849> ➜ Accesso alle sessioni negato per **72 ore**\n"
            "• <@&1516216863678402692> ➜ Accesso alle sessioni negato per **7 giorni**\n"
        ),
        inline=False,
    )

    embed_ban.add_field(
        name="🚫 BAN PERMANENTE",
        value=(
            "• <@&1516211162184814752> ➜ Espulsione definitiva dal server\n"
            "↳ *L'unico modo per rientrare è presentare un appello formale, se consentito.*"
        ),
        inline=False,
    )

    embed_ban.set_footer(text="Tokyo Horizon RP | Sistema Sanzioni")

    # ── Embed 3: info rimozione ────────────────────────────────────────────
    embed_info = discord.Embed(
        color=discord.Color.from_rgb(60, 80, 180),
    )

    embed_info.add_field(
        name="📋 COME VIENE RIMOSSA UNA SANZIONE",
        value="Le sanzioni **non vengono rimosse automaticamente**. Per richiedere la rimozione segui questi passi:",
        inline=False,
    )

    embed_info.add_field(
        name="1️⃣  Attendi la scadenza",
        value="Aspetta che il periodo indicato sia trascorso interamente.\n\u200b",
        inline=False,
    )

    embed_info.add_field(
        name="2️⃣  Apri un Ticket",
        value="Solo a scadenza avvenuta apri un ticket in <#1516194247210963015> chiedendo la rimozione del ruolo sanzione.\n\u200b",
        inline=False,
    )

    embed_info.add_field(
        name="3️⃣  Verifica Staff",
        value=(
            "Lo Staff controllerà che durante il periodo di sanzione il tuo comportamento "
            "sia stato corretto prima di procedere alla rimozione.\n\u200b"
        ),
        inline=False,
    )

    embed_info.add_field(
        name="⚠️ Nota",
        value=(
            "I Ban temporanei vengono gestiti dallo Staff allo scadere del tempo indicato. "
            "Per i Ban Permanenti l'unico modo per rientrare è un eventuale appello, se concesso dall'Amministrazione."
        ),
        inline=False,
    )

    embed_info.set_footer(text="Tokyo Horizon RP | Sistema Sanzioni")

    try:
        await canale.send(embeds=[embed_warn, embed_ban, embed_info])
        await interaction.followup.send(
            f"✅ Pannello sanzioni pubblicato in <#{CANALE_SANZIONI}>!", ephemeral=True
        )
        print(f"[SANZIONI] Pannello pubblicato da {interaction.user} in #{canale.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ Il bot non ha i permessi per scrivere in <#{CANALE_SANZIONI}>.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# SISTEMA TICKET
# =============================================================================

_TIPI_TICKET = {
    "supporto": {
        "label": "🎫 Ticket Supporto",
        "style": discord.ButtonStyle.primary,
        "custom_id": "ticket:apri:supporto",
        "titolo": "🎫 Ticket Supporto",
        "benvenuto": (
            "Benvenuto nel tuo ticket di supporto!\n\n"
            "Hai una domanda o hai bisogno di assistenza? Un membro dello staff ti "
            "risponderà il prima possibile.\n\n"
            "📌 **Descrivi il tuo problema con più dettagli possibili** per ricevere "
            "un aiuto più rapido ed efficace."
        ),
        "prefisso": "supporto",
        "colore": discord.Color.blurple(),
        "ping_admin": False,
    },
    "amministrazione": {
        "label": "🏛️ Ticket Amministrazione",
        "style": discord.ButtonStyle.secondary,
        "custom_id": "ticket:apri:amministrazione",
        "titolo": "🏛️ Ticket Amministrazione",
        "benvenuto": (
            "Benvenuto nel canale riservato all'Amministrazione.\n\n"
            "Questo spazio è destinato a comunicazioni confidenziali che richiedono "
            "l'intervento dei gradi più alti del server.\n\n"
            "📌 **Esponi la tua richiesta in modo chiaro e dettagliato.** "
            "L'Amministrazione ti risponderà appena possibile."
        ),
        "prefisso": "admin",
        "colore": discord.Color.dark_gold(),
        "ping_admin": True,
    },
    "rapimento": {
        "label": "🔒 Ticket Rapimento",
        "style": discord.ButtonStyle.danger,
        "custom_id": "ticket:apri:rapimento",
        "titolo": "🔒 Richiesta Autorizzazione Rapimento",
        "benvenuto": (
            "Vuoi organizzare il rapimento di un personaggio specifico?\n\n"
            "Prima di procedere è necessaria l'**autorizzazione dello staff**.\n\n"
            "📌 **Indica obbligatoriamente:**\n"
            "• Il nome del personaggio da rapire\n"
            "• La motivazione roleplay\n"
            "• Il luogo e il contesto previsti\n\n"
            "⚠️ Azioni non autorizzate saranno sanzionate secondo il regolamento."
        ),
        "prefisso": "rapimento",
        "colore": discord.Color.red(),
        "ping_admin": False,
    },
    "ricompensa": {
        "label": "🎁 Ticket Ricompensa",
        "style": discord.ButtonStyle.success,
        "custom_id": "ticket:apri:ricompensa",
        "titolo": "🎁 Riscossione Premio",
        "benvenuto": (
            "Hai vinto un giveaway o hai diritto a un premio ricevuto nel server?\n\n"
            "Sei nel posto giusto per riscuotere la tua ricompensa!\n\n"
            "📌 **Indica obbligatoriamente:**\n"
            "• Il tipo di premio che hai vinto\n"
            "• Lo screenshot o la prova del premio ricevuto\n\n"
            "Lo staff verificherà e assegnerà il tuo premio al più presto. 🎉"
        ),
        "prefisso": "premio",
        "colore": discord.Color.green(),
        "ping_admin": False,
    },
}

RUOLI_ADMIN_TICKET = {
    1514817350359060571,  # Founder
    1514817646229717174,  # CEO
    1514818027882024960,  # CO CEO
}


async def _crea_canale_ticket(
    interaction: discord.Interaction,
    tipo: str,
) -> None:
    """Crea un canale ticket privato per l'utente che ha cliccato il bottone."""
    global categoria_ticket_id

    if not categoria_ticket_id:
        await interaction.response.send_message(
            "❌ La categoria ticket non è configurata. Chiedi a un admin di usare `/setcategoriaticket`.",
            ephemeral=True,
        )
        return

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "❌ Questo comando funziona solo all'interno di un server.", ephemeral=True
        )
        return

    categoria = guild.get_channel(categoria_ticket_id)
    if categoria is None or not isinstance(categoria, discord.CategoryChannel):
        await interaction.response.send_message(
            "❌ Categoria ticket non trovata. Riconfigurala con `/setcategoriaticket`.",
            ephemeral=True,
        )
        return

    info = _TIPI_TICKET[tipo]
    nome_canale = f"{info['prefisso']}-{interaction.user.name}".lower()[:90]

    # Controlla se l'utente ha già un ticket di questo tipo aperto
    esistente = discord.utils.get(categoria.channels, name=nome_canale)
    if esistente:
        await interaction.response.send_message(
            f"⚠️ Hai già un ticket **{info['titolo']}** aperto: {esistente.mention}",
            ephemeral=True,
        )
        return

    # Permessi: tutti gli altri non vedono; l'utente e lo staff vedono
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
        ),
    }
    for r_id in RUOLI_STAFF:
        role = guild.get_role(r_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )

    try:
        canale = await guild.create_text_channel(
            name=nome_canale,
            category=categoria,
            overwrites=overwrites,
            topic=f"Ticket {info['titolo']} — {interaction.user} (ID: {interaction.user.id})",
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ Il bot non ha i permessi per creare canali nella categoria ticket.", ephemeral=True
        )
        return
    except Exception as e:
        await interaction.response.send_message(f"❌ Errore durante la creazione del ticket: {e}", ephemeral=True)
        return

    # Embed di benvenuto nel canale ticket
    embed = discord.Embed(
        title=info["titolo"],
        description=info["benvenuto"],
        color=info["colore"],
    )
    embed.set_footer(text=f"Tokyo Horizon RP | Ticket aperto da {interaction.user.display_name}")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1254/1254540.png")

    await canale.send(
        content=f"{interaction.user.mention} <@&1514407155577524385>",
        embed=embed,
        view=ChiudiTicketView(),
    )

    await interaction.response.send_message(
        f"✅ Il tuo ticket è stato creato: {canale.mention}", ephemeral=True
    )
    print(f"[TICKET] Aperto '{nome_canale}' da {interaction.user} (id={interaction.user.id})")


class TicketPannelloView(discord.ui.View):
    """Pannello ticket persistente con 4 bottoni — sopravvive ai riavvii."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎫 Ticket Supporto",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:apri:supporto",
        row=0,
    )
    async def apri_supporto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _crea_canale_ticket(interaction, "supporto")

    @discord.ui.button(
        label="🏛️ Ticket Amministrazione",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:apri:amministrazione",
        row=0,
    )
    async def apri_amministrazione(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _crea_canale_ticket(interaction, "amministrazione")

    @discord.ui.button(
        label="🔒 Ticket Rapimento",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:apri:rapimento",
        row=1,
    )
    async def apri_rapimento(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _crea_canale_ticket(interaction, "rapimento")

    @discord.ui.button(
        label="🎁 Ticket Ricompensa",
        style=discord.ButtonStyle.success,
        custom_id="ticket:apri:ricompensa",
        row=1,
    )
    async def apri_ricompensa(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _crea_canale_ticket(interaction, "ricompensa")


class ChiudiTicketView(discord.ui.View):
    """Bottone chiusura ticket persistente — sopravvive ai riavvii."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Chiudi Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:chiudi",
    )
    async def chiudi(self, interaction: discord.Interaction, button: discord.ui.Button):
        raw = getattr(interaction.user, '_roles', None)
        ha_staff = raw is not None and any(r_id in RUOLI_STAFF for r_id in raw)
        e_autore = interaction.channel.topic and f"ID: {interaction.user.id})" in interaction.channel.topic

        if not ha_staff and not e_autore:
            await interaction.response.send_message(
                "❌ Solo il giocatore che ha aperto il ticket o lo staff possono chiuderlo.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("🔒 Ticket in chiusura... Ciao! 👋")
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete(reason=f"Ticket chiuso da {interaction.user}")
            print(f"[TICKET] Canale '{interaction.channel.name}' eliminato da {interaction.user}")
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TICKET] Errore eliminazione canale: {e}")


@bot.tree.command(
    name="setcategoriaticket",
    description="[MOD] Imposta la categoria Discord dove verranno creati i canali ticket",
)
@app_commands.describe(categoria_id="ID numerico della categoria Discord")
async def setcategoriaticket(interaction: discord.Interaction, categoria_id: str):
    global categoria_ticket_id
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    try:
        cid = int(categoria_id)
    except ValueError:
        await interaction.response.send_message(
            "❌ Inserisci un ID numerico valido.", ephemeral=True
        )
        return

    categoria = interaction.guild.get_channel(cid)
    if categoria is None or not isinstance(categoria, discord.CategoryChannel):
        await interaction.response.send_message(
            "❌ Categoria non trovata. Assicurati che l'ID sia corretto e che il bot sia nel server.",
            ephemeral=True,
        )
        return

    categoria_ticket_id = cid
    salva_dati()
    await interaction.response.send_message(
        f"✅ Categoria ticket impostata su **{categoria.name}** (ID: `{cid}`).", ephemeral=True
    )
    print(f"[TICKET] Categoria impostata: {categoria.name} ({cid}) da {interaction.user}")


@bot.tree.command(
    name="setupticket",
    description="[MOD] Pubblica il pannello ticket nel canale corrente",
)
async def setupticket(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🎟️ Centro Assistenza — Tokyo Horizon RP",
        description=(
            "Hai bisogno di aiuto o vuoi contattare il nostro team?\n"
            "Scegli la tipologia di ticket più adatta alla tua richiesta "
            "e ti risponderemo il prima possibile.\n\u200b"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )

    embed.add_field(
        name="🎫 Ticket Supporto",
        value="Hai domande o hai bisogno di assistenza? Contatta un membro dello staff.",
        inline=False,
    )
    embed.add_field(
        name="🏛️ Ticket Amministrazione",
        value="Per richieste riservate che richiedono l'intervento dei gradi più elevati.",
        inline=False,
    )
    embed.add_field(
        name="🔒 Ticket Rapimento",
        value="Richiedi l'autorizzazione dello staff prima di procedere al rapimento di un personaggio.",
        inline=False,
    )
    embed.add_field(
        name="🎁 Ticket Ricompensa",
        value="Vinci un giveaway o hai diritto a un premio? Riscuotilo qui con l'aiuto dello staff.",
        inline=False,
    )

    embed.set_footer(text="Tokyo Horizon RP | Un solo ticket per tipologia • Verrà eliminato alla chiusura")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1254/1254540.png")

    try:
        await interaction.channel.send(embed=embed, view=TicketPannelloView())
        await interaction.followup.send(
            f"✅ Pannello ticket pubblicato in {interaction.channel.mention}!", ephemeral=True
        )
        print(f"[TICKET] Pannello pubblicato da {interaction.user} in #{interaction.channel.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Il bot non ha i permessi per scrivere in questo canale.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# SETUP GUIDA COMANDI
# =============================================================================

@bot.tree.command(
    name="setupguida",
    description="[MOD] Pubblica la guida Concessionaria & Veicoli nel canale corrente",
)
async def setupguida(interaction: discord.Interaction):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message(
            "❌ Solo lo staff può usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    CH_CONC     = "<#1516869463943938318>"   # canale concessionaria
    CH_LISTINO  = "<#1516618214082216018>"   # listino veicoli
    CH_CONTATTO = "<#1517112305093971968>"   # canale per contattare il concessionario

    COLORE_GOLD = discord.Color.from_rgb(212, 175, 55)
    COLORE_DARK = discord.Color.from_rgb(20, 20, 30)

    # ── Embed 1: Benvenuto ────────────────────────────────────────────────
    embed_intro = discord.Embed(
        title="🚗 Tokyo Horizon Motors — Concessionaria Ufficiale",
        description=(
            f"Benvenuto/a nella **Concessionaria di Tokyo Horizon**!\n"
            f"Puoi trovare la concessionaria nel canale {CH_CONC}.\n\u200b"
        ),
        color=COLORE_GOLD,
    )
    embed_intro.set_footer(text="Tokyo Horizon RP | Concessionaria")

    # ── Embed 2: Listino veicoli ──────────────────────────────────────────
    embed_listino = discord.Embed(
        title="📋 Listino Veicoli",
        description=(
            f"Tutti i veicoli disponibili con prezzi e foto si trovano nel canale:\n\n"
            f"➡️ {CH_LISTINO}\n\n"
            "I prezzi possono variare — contratta sempre con il concessionario in RP."
        ),
        color=COLORE_DARK,
    )

    # ── Embed 3: Come acquistare ──────────────────────────────────────────
    embed_acquisto = discord.Embed(
        title="🏪 Come Acquistare un Veicolo",
        color=COLORE_GOLD,
    )
    embed_acquisto.add_field(
        name="1️⃣  Guarda il listino",
        value=f"Consulta {CH_LISTINO} per scegliere il veicolo che ti interessa.\n\u200b",
        inline=False,
    )
    embed_acquisto.add_field(
        name="2️⃣  Contatta un Concessionario",
        value=(
            f"Apri una richiesta nel canale {CH_CONTATTO} e specifica il veicolo e il tuo budget.\n"
            "Il Concessionario ti contatterà per concludere la trattativa in RP.\n\u200b"
        ),
        inline=False,
    )
    embed_acquisto.add_field(
        name="3️⃣  Ricezione del veicolo",
        value=(
            "Il Concessionario registra la vendita tramite il bot.\n"
            "Il veicolo comparirà automaticamente nel tuo `/garage` e riceverai un DM di conferma.\n"
        ),
        inline=False,
    )

    # ── Invio ──────────────────────────────────────────────────────────────
    try:
        await interaction.channel.send(embed=embed_intro)
        await interaction.channel.send(embed=embed_listino)
        await interaction.channel.send(embed=embed_acquisto)
        await interaction.followup.send(
            f"✅ Guida Concessionaria pubblicata in {interaction.channel.mention}!", ephemeral=True
        )
        print(f"[GUIDA] Concessionaria pubblicata da {interaction.user} in #{interaction.channel.name}")
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Il bot non ha i permessi per scrivere in questo canale.", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


# =============================================================================
# CONCESSIONARIA DISCORD
# =============================================================================

_STATIC = f"https://{_DEV_DOMAIN}/static/cars/" if _DEV_DOMAIN else ""

_CATALOGO_DEFAULT = [
    {
        "categoria": "🏎️ SUPER CAR",
        "colore": (220, 40, 40),
        "auto": [
            {"nome": "Grotti Itali RSX",    "prezzo": "€ 3.465.000", "img": _STATIC + "supercar1.jpeg"},
            {"nome": "Pegassi Tempesta",    "prezzo": "€ 2.175.000", "img": _STATIC + "supercar2.webp"},
            {"nome": "Overflod Entity XXR", "prezzo": "€ 2.305.600", "img": _STATIC + "supercar3.webp"},
            {"nome": "Vapid FMJ",           "prezzo": "€ 1.750.000", "img": _STATIC + "supercar4.webp"},
        ],
    },
    {
        "categoria": "🚗 SPORTIVE",
        "colore": (201, 168, 76),
        "auto": [
            {"nome": "Pfister Comet S2",  "prezzo": "€ 1.878.000", "img": _STATIC + "sport1.jpeg"},
            {"nome": "Karin Calico GTF",  "prezzo": "€ 1.995.000", "img": _STATIC + "sport2.webp"},
            {"nome": "Annis Remus",       "prezzo": "€ 1.390.000", "img": _STATIC + "sport3.webp"},
        ],
    },
    {
        "categoria": "💪 MUSCLE",
        "colore": (180, 80, 20),
        "auto": [
            {"nome": "Bravado Gauntlet Hellfire", "prezzo": "€ 875.000",   "img": _STATIC + "muscle1.webp"},
            {"nome": "Bravado Buffalo STX",       "prezzo": "€ 1.190.000", "img": _STATIC + "muscle2.webp"},
            {"nome": "Vapid Dominator GTT",       "prezzo": "€ 1.295.000", "img": _STATIC + "muscle3.webp"},
            {"nome": "Annis Euros",               "prezzo": "€ 1.350.000", "img": _STATIC + "muscle4.webp"},
        ],
    },
    {
        "categoria": "🏛️ SPORTIVE CLASSICHE",
        "colore": (100, 100, 200),
        "auto": [
            {"nome": "Grotti Stinger GT",      "prezzo": "€ 995.000", "img": _STATIC + "classic1.webp"},
            {"nome": "Grotti Turismo Classic", "prezzo": "€ 650.000", "img": _STATIC + "classic2.webp"},
            {"nome": "Benefactor Stirling GT", "prezzo": "€ 975.000", "img": _STATIC + "classic3.webp"},
            {"nome": "Grotti Cheetah Classic", "prezzo": "€ 695.000", "img": _STATIC + "classic4.webp"},
        ],
    },
    {
        "categoria": "🚙 BERLINE",
        "colore": (60, 160, 80),
        "auto": [
            {"nome": "Obey Tailgater S",  "prezzo": "€ 1.595.000", "img": _STATIC + "berlina1.webp"},
            {"nome": "Ocelot Jugular",    "prezzo": "€ 1.225.000", "img": _STATIC + "berlina2.webp"},
            {"nome": "Karin Asterope GT", "prezzo": "€ 795.000",   "img": _STATIC + "berlina3.webp"},
            {"nome": "Declasse Impaler",  "prezzo": "€ 420.000",   "img": _STATIC + "berlina4.webp"},
        ],
    },
    {
        "categoria": "🚙 SUV",
        "colore": (80, 120, 200),
        "auto": [
            {"nome": "Ubermacht Rebla GTS",       "prezzo": "€ 1.250.000", "img": _STATIC + "suv1.webp"},
            {"nome": "Gallivanter Baller ST-D",   "prezzo": "€ 1.495.000", "img": _STATIC + "suv2.webp"},
            {"nome": "Canis Seminole Frontier",   "prezzo": "€ 995.000",   "img": _STATIC + "suv3.webp"},
            {"nome": "Pegassi Toros",             "prezzo": "€ 498.000",   "img": _STATIC + "suv4.webp"},
        ],
    },
    {
        "categoria": "🚗 COMPATTE",
        "colore": (160, 90, 200),
        "auto": [
            {"nome": "Karin Futo GTX",    "prezzo": "€ 1.590.000", "img": _STATIC + "compatta1.webp"},
            {"nome": "Grotti Brioso R/A", "prezzo": "€ 145.000",   "img": _STATIC + "compatta2.webp"},
            {"nome": "Declasse Rhapsody", "prezzo": "€ 200.000",   "img": _STATIC + "compatta3.webp"},
            {"nome": "Weeny Issi Custom", "prezzo": "€ 1.765.000", "img": _STATIC + "compatta4.webp"},
        ],
    },
    {
        "categoria": "🛤️ FUORISTRADA",
        "colore": (130, 90, 50),
        "auto": [
            {"nome": "Vapid Riata",     "prezzo": "€ 745.000",   "img": _STATIC + "offroad1.webp"},
            {"nome": "Canis Kamacho",   "prezzo": "€ 550.000",   "img": _STATIC + "offroad2.webp"},
            {"nome": "Canis Mesa",      "prezzo": "€ 225.000",   "img": _STATIC + "offroad3.webp"},
            {"nome": "Declasse Yosemite","prezzo": "€ 165.000",   "img": _STATIC + "offroad4.webp"},
        ],
    },
    {
        "categoria": "🏍️ MOTO",
        "colore": (200, 50, 150),
        "auto": [
            {"nome": "Dinka Vindicator",    "prezzo": "€ 270.000", "img": _STATIC + "moto1.webp"},
            {"nome": "Western Gargoyle",    "prezzo": "€ 120.000", "img": _STATIC + "moto2.webp"},
            {"nome": "Pegassi Faggio",      "prezzo": "€ 30.000",  "img": _STATIC + "moto3.webp"},
            {"nome": "LCC Innovation",      "prezzo": "€ 255.000", "img": _STATIC + "moto4.webp"},
        ],
    },
]

def _carica_catalogo() -> list:
    """Carica il catalogo da dati_bot.json se presente, altrimenti usa i default."""
    if not os.path.exists(DATI_FILE):
        return [dict(c) for c in _CATALOGO_DEFAULT]
    try:
        with open(DATI_FILE, "r") as f:
            dati = json.load(f)
        salvato = dati.get("catalogo_auto")
        if not salvato:
            return [dict(c) for c in _CATALOGO_DEFAULT]
        # Riapplica i colori (non serializzabili in JSON)
        colori = {c["categoria"]: c["colore"] for c in _CATALOGO_DEFAULT}
        for cat in salvato:
            cat["colore"] = colori.get(cat["categoria"], (150, 150, 150))
        return salvato
    except Exception:
        return [dict(c) for c in _CATALOGO_DEFAULT]

def _salva_catalogo():
    """Aggiunge il catalogo corrente al JSON (senza i colori discord)."""
    if not os.path.exists(DATI_FILE):
        return
    try:
        with open(DATI_FILE, "r") as f:
            dati = json.load(f)
        dati["catalogo_auto"] = [
            {"categoria": cat["categoria"], "auto": cat["auto"]}
            for cat in CATALOGO_DS
        ]
        tmp = DATI_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(dati, f, indent=2)
        os.replace(tmp, DATI_FILE)
    except Exception as e:
        print(f"[CATALOGO] Errore salvataggio: {e}")

CATALOGO_DS: list = _carica_catalogo()

def _tutte_le_auto() -> list[dict]:
    """Restituisce lista piatta di tutte le auto con riferimento alla categoria."""
    out = []
    for cat in CATALOGO_DS:
        for auto in cat["auto"]:
            out.append({**auto, "_cat": cat["categoria"]})
    return out

def _trova_auto(nome: str):
    """Cerca un'auto per nome (case-insensitive). Ritorna (cat_dict, auto_dict) o (None, None)."""
    nome_lower = nome.lower()
    for cat in CATALOGO_DS:
        for auto in cat["auto"]:
            if auto["nome"].lower() == nome_lower:
                return cat, auto
    return None, None

# ---------- Autocomplete ----------

async def _autocomplete_auto(interaction: discord.Interaction, current: str):
    tutte = _tutte_le_auto()
    return [
        app_commands.Choice(name=a["nome"], value=a["nome"])
        for a in tutte
        if current.lower() in a["nome"].lower()
    ][:25]

async def _autocomplete_categoria(interaction: discord.Interaction, current: str):
    categorie = [cat["categoria"] for cat in CATALOGO_DS]
    return [
        app_commands.Choice(name=c, value=c)
        for c in categorie
        if current.lower() in c.lower()
    ][:25]

# ---------- Helper embed auto ----------

def _embed_auto(auto: dict, cat: dict) -> discord.Embed:
    r, g, b = cat["colore"]
    embed = discord.Embed(
        title=auto["nome"],
        color=discord.Color.from_rgb(r, g, b),
    )
    embed.add_field(name="💰 Prezzo", value=f"**{auto['prezzo']}**", inline=True)
    embed.add_field(name="🏷️ Categoria", value=cat["categoria"], inline=True)
    if auto.get("img"):
        embed.set_image(url=auto["img"])
    embed.set_footer(text="📩 Per acquistare apri un ticket o contatta uno staff · Tokyo Horizon RP")
    return embed

# ---------- Comandi ----------

@bot.tree.command(name="pubblicaconcessionaria", description="[STAFF] Pubblica il catalogo veicoli con foto nel canale corrente")
@app_commands.checks.has_permissions(manage_channels=True)
async def pubblicaconcessionaria(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        intestazione = discord.Embed(
            title="🗼 TOKYO HORIZON MOTORS",
            description=(
                "東京ホライズン · カーディーラー\n\n"
                "📅 **Ogni settimana verrà aggiunto un nuovo veicolo per ogni categoria!**\n"
                "🌐 **Sito web:** attualmente in fase di sviluppo — disponibile prossimamente.\n\n"
                "Benvenuto nel catalogo ufficiale della concessionaria.\n"
                "Tutti i prezzi sono in valuta RP · Contatta uno staff per acquistare.\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.from_rgb(220, 40, 40),
        )
        intestazione.set_footer(text="Tokyo Horizon RP · Catalogo Ufficiale · 公式ディーラー")
        await interaction.channel.send(embed=intestazione)

        for cat in CATALOGO_DS:
            # Separatore categoria
            r, g, b = cat["colore"]
            sep = discord.Embed(
                description=f"**{cat['categoria']}**",
                color=discord.Color.from_rgb(r, g, b),
            )
            await interaction.channel.send(embed=sep)
            # Un embed per auto — immagine allegata direttamente (CDN Discord)
            for auto in cat["auto"]:
                img_url = auto.get("img", "")
                filename = img_url.split("/")[-1] if img_url else ""
                filepath = f"static/cars/{filename}"
                embed = discord.Embed(
                    title=auto["nome"],
                    color=discord.Color.from_rgb(r, g, b),
                )
                embed.add_field(name="💰 Prezzo", value=f"**{auto['prezzo']}**", inline=True)
                embed.add_field(name="🏷️ Categoria", value=cat["categoria"], inline=True)
                embed.set_footer(text="📩 Per acquistare apri un ticket o contatta uno staff · Tokyo Horizon RP")
                if filename and os.path.exists(filepath):
                    file = discord.File(filepath, filename=filename)
                    embed.set_image(url=f"attachment://{filename}")
                    await interaction.channel.send(embed=embed, file=file)
                else:
                    await interaction.channel.send(embed=embed)

        chiusura = discord.Embed(
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📩 **Come acquistare:** apri un ticket o contatta uno staff\n"
                "⏱️ Il catalogo viene aggiornato periodicamente · 定期更新"
            ),
            color=discord.Color.from_rgb(30, 30, 40),
        )
        await interaction.channel.send(embed=chiusura)
        await interaction.followup.send("✅ Catalogo pubblicato!", ephemeral=True)
        print(f"[CONCESSIONARIA] Catalogo pubblicato da {interaction.user} in #{interaction.channel.name}")

    except discord.Forbidden:
        await interaction.followup.send("❌ Permessi insufficienti per scrivere in questo canale.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)


@pubblicaconcessionaria.error
async def pubblicaconcessionaria_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)


@bot.tree.command(name="aggiornaconcessionaria", description="[STAFF] Modifica il prezzo di un'auto in catalogo")
@app_commands.describe(auto="Nome dell'auto da aggiornare", prezzo="Nuovo prezzo (es: € 2.500.000)")
@app_commands.autocomplete(auto=_autocomplete_auto)
@app_commands.checks.has_permissions(manage_channels=True)
async def aggiornaconcessionaria(interaction: discord.Interaction, auto: str, prezzo: str):
    cat, found = _trova_auto(auto)
    if not found:
        await interaction.response.send_message(f"❌ Auto `{auto}` non trovata nel catalogo.", ephemeral=True)
        return
    vecchio = found["prezzo"]
    found["prezzo"] = prezzo
    _salva_catalogo()
    embed = discord.Embed(
        title="✅ Prezzo aggiornato",
        color=discord.Color.green(),
    )
    embed.add_field(name="Auto",          value=found["nome"], inline=False)
    embed.add_field(name="Prezzo vecchio", value=vecchio,       inline=True)
    embed.add_field(name="Prezzo nuovo",   value=prezzo,        inline=True)
    embed.set_footer(text="Usa /pubblicaconcessionaria per aggiornare il canale")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"[CONCESSIONARIA] {interaction.user} ha aggiornato {found['nome']}: {vecchio} → {prezzo}")


@aggiornaconcessionaria.error
async def aggiornaconcessionaria_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)


@bot.tree.command(name="aggiungiauto", description="[STAFF] Aggiunge un nuovo veicolo al catalogo")
@app_commands.describe(
    categoria="Categoria in cui inserire l'auto",
    nome="Nome completo (es: Grotti Itali RSX)",
    prezzo="Prezzo (es: € 2.500.000)",
    img_url="URL immagine (lascia vuoto per nessuna foto)",
)
@app_commands.autocomplete(categoria=_autocomplete_categoria)
@app_commands.checks.has_permissions(manage_channels=True)
async def aggiungiauto(interaction: discord.Interaction, categoria: str, nome: str, prezzo: str, img_url: str = ""):
    cat = next((c for c in CATALOGO_DS if c["categoria"] == categoria), None)
    if not cat:
        await interaction.response.send_message(f"❌ Categoria `{categoria}` non trovata.", ephemeral=True)
        return
    _, existing = _trova_auto(nome)
    if existing:
        await interaction.response.send_message(f"❌ `{nome}` è già in catalogo. Usa `/aggiornaconcessionaria` per modificarlo.", ephemeral=True)
        return
    nuova = {"nome": nome, "prezzo": prezzo, "img": img_url or ""}
    cat["auto"].append(nuova)
    _salva_catalogo()
    embed = discord.Embed(title="✅ Auto aggiunta", color=discord.Color.green())
    embed.add_field(name="Nome",      value=nome,      inline=True)
    embed.add_field(name="Prezzo",    value=prezzo,    inline=True)
    embed.add_field(name="Categoria", value=categoria, inline=True)
    if img_url:
        embed.set_thumbnail(url=img_url)
    embed.set_footer(text="Usa /pubblicaconcessionaria per aggiornare il canale")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"[CONCESSIONARIA] {interaction.user} ha aggiunto {nome} in {categoria}")


@aggiungiauto.error
async def aggiungiauto_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)


@bot.tree.command(name="rimuoviauto", description="[STAFF] Rimuove un veicolo dal catalogo")
@app_commands.describe(auto="Nome dell'auto da rimuovere")
@app_commands.autocomplete(auto=_autocomplete_auto)
@app_commands.checks.has_permissions(manage_channels=True)
async def rimuoviauto(interaction: discord.Interaction, auto: str):
    cat, found = _trova_auto(auto)
    if not found:
        await interaction.response.send_message(f"❌ Auto `{auto}` non trovata nel catalogo.", ephemeral=True)
        return
    cat["auto"].remove(found)
    _salva_catalogo()
    embed = discord.Embed(
        title="🗑️ Auto rimossa",
        description=f"**{found['nome']}** rimossa dalla categoria {cat['categoria']}.",
        color=discord.Color.red(),
    )
    embed.set_footer(text="Usa /pubblicaconcessionaria per aggiornare il canale")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    print(f"[CONCESSIONARIA] {interaction.user} ha rimosso {found['nome']}")


@rimuoviauto.error
async def rimuoviauto_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando.", ephemeral=True)


# =============================================================================
# MECCANICO — PREZZI MODIFICHE & RICHIESTA MODIFICA
# =============================================================================

PREZZI_MODIFICHE = [
    ("🛡️ Armatura",         "Corazza Pesante — 100%",                   "€ 50.000"),
    ("🛑 Freni",            "Freni da Gara",                            "€ 20.000"),
    ("🔧 Motore",           "EMS Upgrade Liv. 4",                       "€ 35.000"),
    ("🔊 Marmitta",         "Racing (varia per modello)",               "Su richiesta"),
    ("🚗 Cofano",           "Modifica generica",                        "€ 8.000"),
    ("🎭 Interni",          "Cambio colore interni",                    "€ 5.000"),
    ("💡 Fari",             "Fari Xenon / Modifica",                    "€ 7.500"),
    ("🎨 Colore",           "Verniciatura Perla / Metallizzata",        "€ 10.000"),
    ("🪞 Specchietti",      "Modifica specchietti",                     "€ 3.000"),
    ("🏠 Tettuccio",        "Carbonio / Rimozione",                     "€ 8.000"),
    ("🏎️ Minigonne",        "Kit minigonne",                            "€ 6.000"),
    ("🏁 Spoiler",          "Spoiler da Gara",                          "€ 8.000"),
    ("🔩 Sospensioni",      "Sospensioni da Competizione",              "€ 20.000"),
    ("⚙️ Trasmissione",     "Trasmissione Sport",                       "€ 32.500"),
    ("💨 Turbo",            "Turbina Racing",                           "€ 50.000"),
    ("🛞 Ruote",            "Set ruote (varia per tipo)",               "Su richiesta"),
    ("🪟 Finestrini",       "Oscuramento Totale",                       "€ 5.000"),
]

MECCANICO_IMG = "attached_assets/officina_pulita.jpeg"

@bot.tree.command(name="posizionemeccanico", description="Mostra la posizione dell'officina meccanica sulla mappa")
async def posizionemeccanico(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    embed = discord.Embed(
        title="📍 Posizione Officina Meccanica",
        description=(
            "Questa è la posizione dell'**Officina Meccanica** nel server.\n\n"
            "🔧 Recati qui per richiedere modifiche al tuo veicolo.\n"
            f"📋 Usa `/modificaveicolo` in <#{CANALE_MECCANICO_RICHIESTE}> per inviare la tua richiesta prima di venire."
        ),
        color=discord.Color.from_rgb(30, 144, 255),
    )
    embed.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
    try:
        file = discord.File(MECCANICO_IMG, filename="officina.jpeg")
        embed.set_image(url="attachment://officina.jpeg")
        await interaction.followup.send(embed=embed, file=file)
    except FileNotFoundError:
        await interaction.followup.send(embed=embed)
        print(f"[MECCANICO] ⚠️ Immagine non trovata: {MECCANICO_IMG}")


@bot.tree.command(name="prezzimodifiche", description="Mostra il listino prezzi delle modifiche veicolo (livello massimo)")
async def prezzimodifiche(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    embed = discord.Embed(
        title="🔧 Listino Prezzi — Modifiche Veicolo",
        description=(
            "Benvenuto nell'**Officina Tokyo Horizon**!\n"
            "Di seguito trovi i prezzi per tutte le modifiche al **livello massimo disponibile**.\n\n"
            "Per richiedere una modifica usa il comando `/modificaveicolo`."
        ),
        color=discord.Color.from_rgb(255, 165, 0),
    )
    for emoji_cat, modifica, prezzo in PREZZI_MODIFICHE:
        embed.add_field(
            name=f"{emoji_cat}",
            value=f"**{modifica}**\n`{prezzo}`",
            inline=True,
        )
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(
        name="📋 Come richiedere una modifica",
        value=f"Usa il comando `/modificaveicolo` direttamente in <#{CANALE_MECCANICO_RICHIESTE}>.",
        inline=False,
    )
    embed.set_footer(text="Tokyo Horizon RP | Officina Meccanica • Prezzi fissi — nessuna trattativa")
    embed.set_thumbnail(url="https://static.wikia.nocookie.net/gtawiki/images/9/97/BennyOriginalMotorWorks-GTAO-Exterior.png/revision/latest")
    await interaction.followup.send(embed=embed)


class AccettaModificaView(discord.ui.View):
    def __init__(self, player_id: int, nome_pg: str, modello: str, mods: str, note: str):
        super().__init__(timeout=None)
        self.player_id = player_id
        self.nome_pg   = nome_pg
        self.modello   = modello
        self.mods      = mods
        self.note      = note

    async def _disabilita(self, interaction: discord.Interaction, colore: discord.Color, etichetta: str):
        for item in self.children:
            item.disabled = True
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = colore
            embed.set_footer(text=f"{etichetta} da {interaction.user} • Tokyo Horizon RP | Officina Meccanica")
            await interaction.message.edit(embed=embed, view=self)
        else:
            await interaction.message.edit(view=self)

    def _ha_ruolo_meccanico(self, interaction: discord.Interaction) -> bool:
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if member:
            return any(r.id == 1517200733160734912 for r in member.roles)
        return False

    @discord.ui.button(label="✅ Accetta", style=discord.ButtonStyle.success, custom_id="modifica_accetta")
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ha_ruolo_meccanico(interaction):
            await interaction.response.send_message("❌ Solo i meccanici possono accettare le richieste.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._disabilita(interaction, discord.Color.green(), "✅ Accettata")
        # Salva nello storico modifiche
        storico_modifiche.setdefault(self.player_id, []).append({
            "data":    discord.utils.utcnow().strftime("%d/%m/%Y %H:%M"),
            "veicolo": self.modello,
            "mods":    self.mods,
            "note":    self.note,
            "stato":   "accettata",
        })
        salva_dati()
        try:
            player = await bot.fetch_user(self.player_id)
            dm = discord.Embed(
                title="✅ Richiesta Modifica Accettata!",
                description=(
                    f"La tua richiesta di modifica per **{self.modello}** è stata **accettata** dal meccanico.\n\n"
                    f"🔧 **Modifiche:** {self.mods}\n\n"
                    f"📍 Recati in officina per effettuare le modifiche!"
                ),
                color=discord.Color.green(),
            )
            dm.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
            await player.send(embed=dm)
            print(f"[MECCANICO] ✅ Richiesta accettata — DM inviato a uid={self.player_id}")
        except Exception as e:
            print(f"[MECCANICO] ❌ DM accettazione fallita per uid={self.player_id}: {e}")

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.danger, custom_id="modifica_rifiuta")
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ha_ruolo_meccanico(interaction):
            await interaction.response.send_message("❌ Solo i meccanici possono rifiutare le richieste.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._disabilita(interaction, discord.Color.red(), "❌ Rifiutata")
        try:
            player = await bot.fetch_user(self.player_id)
            dm = discord.Embed(
                title="❌ Richiesta Modifica Rifiutata",
                description=(
                    f"La tua richiesta di modifica per **{self.modello}** è stata **rifiutata** dal meccanico.\n\n"
                    f"Per maggiori informazioni contatta lo staff in gioco."
                ),
                color=discord.Color.red(),
            )
            dm.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
            await player.send(embed=dm)
            print(f"[MECCANICO] ❌ Richiesta rifiutata — DM inviato a uid={self.player_id}")
        except Exception as e:
            print(f"[MECCANICO] ❌ DM rifiuto fallito per uid={self.player_id}: {e}")


class ModificaVeicoloModal(discord.ui.Modal, title="🔧 Richiesta Modifica Veicolo"):
    nome_pg = discord.ui.TextInput(
        label="Nome del tuo personaggio",
        placeholder="Es: Marco Rossi",
        min_length=2,
        max_length=50,
    )
    modello_veicolo = discord.ui.TextInput(
        label="Modello e colore del veicolo",
        placeholder="Es: Zentorno nero, Infernus blu metallizzato",
        min_length=2,
        max_length=80,
    )
    modifiche_richieste = discord.ui.TextInput(
        label="Modifiche richieste",
        placeholder="Es: Motore Liv.4, Turbo, Freni Racing, Corazza Pesante",
        style=discord.TextStyle.paragraph,
        min_length=5,
        max_length=300,
    )
    note = discord.ui.TextInput(
        label="Note aggiuntive (opzionale)",
        placeholder="Es: Verniciatura rossa perla, cerchi bianchi…",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid     = interaction.user.id
        nome    = self.nome_pg.value.strip()
        modello = self.modello_veicolo.value.strip()
        mods    = self.modifiche_richieste.value.strip()
        note    = self.note.value.strip() if self.note.value else "—"

        # Cooldown 2 ore anti-spam
        CD_MODIFICA = 2 * 3600
        ultimo_mod = furto_cooldown.get(uid, {}).get("richiesta_modifica", 0)
        rimasto_cd = CD_MODIFICA - (time.time() - ultimo_mod)
        if rimasto_cd > 0:
            ore_r = int(rimasto_cd) // 3600
            min_r = (int(rimasto_cd) % 3600) // 60
            await interaction.followup.send(
                f"⏳ Hai già inviato una richiesta di recente.\n"
                f"Aspetta ancora **{ore_r}h {min_r}m** prima di inviarne un'altra.",
                ephemeral=True
            )
            return

        furto_cooldown.setdefault(uid, {})["richiesta_modifica"] = time.time()
        salva_dati()

        embed_ok = discord.Embed(
            title="✅ Richiesta Modifica Inviata!",
            description=(
                f"👤 **Personaggio:** `{nome}`\n"
                f"🚗 **Veicolo:** `{modello}`\n"
                f"🔧 **Modifiche:** {mods}\n"
                f"📝 **Note:** {note}\n\n"
                f"Un meccanico valuterà la richiesta e ti risponderà in DM."
            ),
            color=discord.Color.green(),
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
        await interaction.followup.send(embed=embed_ok, ephemeral=True)

        try:
            canale = await bot.fetch_channel(CANALE_MECCANICO_STAFF)
            embed_staff = discord.Embed(
                title="🔧 NUOVA RICHIESTA MODIFICA VEICOLO",
                description=(
                    f"👤 **Personaggio:** `{nome}`\n"
                    f"🎮 **Discord:** {interaction.user.mention} (`{interaction.user}`)\n"
                    f"🚗 **Veicolo:** `{modello}`\n\n"
                    f"🔧 **Modifiche richieste:**\n{mods}\n\n"
                    f"📝 **Note:** {note}"
                ),
                color=discord.Color.orange(),
            )
            embed_staff.set_footer(text=f"Tokyo Horizon RP | Richiesta ricevuta • {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
            embed_staff.set_thumbnail(url=interaction.user.display_avatar.url)
            view = AccettaModificaView(
                player_id=interaction.user.id,
                nome_pg=nome,
                modello=modello,
                mods=mods,
                note=note,
            )
            await canale.send(embed=embed_staff, view=view)
            print(f"[MECCANICO] Richiesta di {interaction.user} inviata in #{canale.name} con bottoni ✅")
        except discord.Forbidden:
            print(f"[MECCANICO] ❌ Permessi mancanti nel canale staff meccanico ({CANALE_MECCANICO_STAFF})")
        except discord.NotFound:
            print(f"[MECCANICO] ❌ Canale staff meccanico non trovato ({CANALE_MECCANICO_STAFF})")
        except Exception as e:
            print(f"[MECCANICO] ❌ Errore invio notifica staff: {e}")


@bot.tree.command(name="modificaveicolo", description="Invia una richiesta di modifica al meccanico")
async def modificaveicolo(interaction: discord.Interaction):
    await interaction.response.send_modal(ModificaVeicoloModal())


@bot.tree.command(name="miemodifiche", description="Visualizza lo storico delle modifiche accettate sul tuo veicolo")
async def miemodifiche(interaction: discord.Interaction):
    if not await safe_defer(interaction, ephemeral=True):
        return
    uid = interaction.user.id
    storico = storico_modifiche.get(uid, [])
    if not storico:
        await interaction.followup.send(
            "🔧 Non hai ancora nessuna modifica accettata.\n"
            f"Invia una richiesta con `/modificaveicolo` in <#{CANALE_MECCANICO_RICHIESTE}>!",
            ephemeral=True
        )
        return
    embed = discord.Embed(
        title="🔧 Le Tue Modifiche Veicolo",
        description=f"Storico delle **{len(storico)}** modifica/e accettate dal meccanico.",
        color=discord.Color.from_rgb(255, 165, 0),
    )
    # Mostra le ultime 10 (Discord ha limite field)
    for entry in storico[-10:]:
        note_txt = f"\n📝 Note: {entry['note']}" if entry.get("note") and entry["note"] != "—" else ""
        embed.add_field(
            name=f"📅 {entry['data']} — {entry['veicolo']}",
            value=f"🔧 {entry['mods']}{note_txt}",
            inline=False,
        )
    if len(storico) > 10:
        embed.set_footer(text=f"Tokyo Horizon RP | Mostrate le ultime 10 di {len(storico)} modifiche totali")
    else:
        embed.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
    embed.set_thumbnail(url="https://static.wikia.nocookie.net/gtawiki/images/9/97/BennyOriginalMotorWorks-GTAO-Exterior.png/revision/latest")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setcanalemeccanico", description="[MOD] Imposta questo canale come canale richieste meccanico")
async def setcanalemeccanico(interaction: discord.Interaction):
    global canale_meccanico_id
    if not await safe_defer(interaction): return
    if not ha_permessi_staff(interaction):
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    canale_meccanico_id = interaction.channel_id
    salva_dati()
    embed = discord.Embed(
        title="✅ Canale Meccanico Impostato",
        description=(
            f"Le richieste di modifica veicolo arriveranno in <#{interaction.channel_id}>.\n\n"
            f"I giocatori possono inviare richieste con `/modificaveicolo`."
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text="Tokyo Horizon RP | Pannello Staff")
    await interaction.followup.send(embed=embed, ephemeral=True)
    print(f"[MECCANICO] Canale richieste impostato: #{interaction.channel.name} ({interaction.channel_id})")


# =============================================================================
# MECCANICO — APPLICA MODIFICA CON PEZZI DI RICAMBIO
# =============================================================================

class ApplicaModificaModal(discord.ui.Modal, title="🔩 Applica Modifica — Pezzi di Ricambio"):
    modello_veicolo = discord.ui.TextInput(
        label="Modello e colore del veicolo",
        placeholder="Es: Zentorno nero, Infernus blu",
        min_length=2,
        max_length=80,
    )
    modifica_applicata = discord.ui.TextInput(
        label="Modifica che stai applicando",
        placeholder="Es: Motore Liv.4, Turbo, Freni da Gara…",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid     = interaction.user.id
        inv     = get_inventario(uid)
        pezzi   = inv.get("Pezzo di Ricambio", 0)

        if pezzi < 3:
            await interaction.followup.send(
                f"❌ Ti servono **3 Pezzi di Ricambio** per applicare una modifica.\n"
                f"Ne hai solo **`{pezzi}x`** nell'inventario — rubane altri dall'officina meccanica!",
                ephemeral=True,
            )
            return

        modello  = self.modello_veicolo.value.strip()
        modifica = self.modifica_applicata.value.strip()

        inv["Pezzo di Ricambio"] -= 3
        if inv["Pezzo di Ricambio"] <= 0:
            del inv["Pezzo di Ricambio"]
        salva_dati()
        rimasti = inv.get("Pezzo di Ricambio", 0)

        embed_ok = discord.Embed(
            title="🔩 Modifica Applicata!",
            description=(
                f"Hai usato **3x Pezzo di Ricambio** per applicare una modifica al tuo veicolo.\n\n"
                f"🚗 **Veicolo:** `{modello}`\n"
                f"🔧 **Modifica:** {modifica}\n\n"
                f"🔩 Pezzi rimasti in inventario: **`{rimasti}x`**"
            ),
            color=discord.Color.green(),
        )
        embed_ok.set_footer(text="Tokyo Horizon RP | Officina Meccanica")
        await interaction.followup.send(embed=embed_ok, ephemeral=True)

        try:
            canale = await bot.fetch_channel(CANALE_MECCANICO_STAFF)
            embed_log = discord.Embed(
                title="🔩 MODIFICA AUTONOMA APPLICATA",
                description=(
                    f"👤 **Giocatore:** {interaction.user.mention} (`{interaction.user}`)\n"
                    f"🚗 **Veicolo:** `{modello}`\n"
                    f"🔧 **Modifica:** {modifica}\n\n"
                    f"🔩 **Pezzi consumati:** 5x\n"
                    f"📦 **Pezzi rimanenti:** {rimasti}x"
                ),
                color=discord.Color.blue(),
            )
            embed_log.set_footer(text=f"Tokyo Horizon RP | Modifica autonoma • {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
            embed_log.set_thumbnail(url=interaction.user.display_avatar.url)
            await canale.send(embed=embed_log)
            print(f"[MECCANICO] 🔩 {interaction.user} ha applicato modifica autonoma — rimasti {rimasti}x pezzi")
        except Exception as e:
            print(f"[MECCANICO] ❌ Notifica staff modifica autonoma fallita: {e}")


@bot.tree.command(name="applicamodifica", description="Applica una modifica al tuo veicolo usando 5 Pezzi di Ricambio (dal furto officina)")
async def applicamodifica(interaction: discord.Interaction):
    await interaction.response.send_modal(ApplicaModificaModal())


# =============================================================================
# AVVIO BOT
# =============================================================================
token = os.environ.get("DISCORD_TOKEN", "").strip()
if not token:
    print("❌ ERRORE: Il token Discord non è stato trovato. Imposta la variabile DISCORD_TOKEN.")
else:
    keep_alive()
    bot.run(token)
