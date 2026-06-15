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
import aiohttp
from flask import Flask
from threading import Thread

# Configurazione mini-server finto per UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Il bot è vivo!"

def run_flask():
    app.run(host='0.0.0.0', port=3000)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True  # il thread muore con il processo principale — niente istanze zombie
    t.start()

# Shutdown pulito su SIGTERM (Replit invia SIGTERM per riavviare il workflow)
def _handle_sigterm(signum, frame):
    print("[BOT] SIGTERM ricevuto — uscita pulita.")
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)

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
        # Sync globale — una sola volta all'avvio
        await self.tree.sync()
        print("Tokyo Horizon Bot: setup_hook completato — comandi globali sincronizzati.")

    async def close(self):
        if self.aiohttp_session and not self.aiohttp_session.closed:
            await self.aiohttp_session.close()
        await super().close()

    async def on_ready(self):
        bot.ready_time = discord.utils.utcnow()  # Timestamp da cui accettare interazioni
        print(f"✅ {self.user} è online e pronto!")
        print(f"   Connesso a {len(self.guilds)} server/i")
        # Rimuove i comandi guild-specifici duplicati lasciati da vecchie istanze
        for guild in self.guilds:
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)
        print("   Comandi guild-specifici rimossi (nessun duplicato).")
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

bot = TokyoHorizonBot()

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
        if k in m: return "🔴 Alta", 25000, discord.Color.gold()
    for k in media:
        if k in m: return "🟡 Media", 15000, discord.Color.blue()
    return "⚪ Bassa", 5000, discord.Color.light_gray()

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
                )
        except Exception as e:
            print(f"[CARICA_DATI] Errore caricamento JSON: {e} — partenza con dati vuoti")
    return {}, {}, {}, None, {}, {}, {}, {}, {}, {}, {}

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
        }, f, indent=2)
    os.replace(tmp, DATI_FILE)

economia, furto_cooldown, inventario, canale_furti_id, ordini_pendenti_macchina, rapine_pendenti_bancomat, rapine_pendenti_minimarket, rapine_pendenti_armeria, rapine_pendenti_fleeca, rapine_pendenti_gioielleria, rapine_pendenti_mazebank = carica_dati()

def get_balance(user_id):
    if user_id not in economia:
        economia[user_id] = {"portafoglio": 0, "banca": 5000}
    return economia[user_id]

def get_inventario(user_id):
    if user_id not in inventario:
        inventario[user_id] = {}
    return inventario[user_id]

NEGOZIO = {
    "Cacciavite":           {"prezzo": 1250,  "emoji": "🪛",  "descrizione": "Forza la cassa dei minimarket. Indispensabile per il Colpo al Minimarket (in alternativa al Piede di Porco)."},
    "Piede di Porco":       {"prezzo": 1000,  "emoji": "🪓",  "descrizione": "Forza porte e finestre. Usabile anche per il Colpo al Minimarket. Indispensabile per bancomat, case e ville."},
    "Grimaldello":          {"prezzo": 1500,  "emoji": "🗝️", "descrizione": "Scassina serrature di alta sicurezza. Fondamentale per colpi in ville, operazioni epiche e leggendarie."},
    "Grimaldello Avanzato": {"prezzo": 15000, "emoji": "🔐",  "descrizione": "Scassina serrature blindate di alta sicurezza. Obbligatorio per il Grande Colpo alla Maze Bank (min 2 unità)."},
    "Sistema di Hacking":   {"prezzo": 4000,  "emoji": "💻",  "descrizione": "Disabilita sistemi di allarme e telecamere base. Obbligatorio per ogni furto in villa (insieme a Piede di Porco o Grimaldello)."},
    "Trapano":              {"prezzo": 8000,  "emoji": "🔧",  "descrizione": "Perfora le cassette di sicurezza blindate. Obbligatorio per la Rapina alla Banca Fleeca (1x, insieme a 5x Piede di Porco)."},
}

MERCATO_NERO = {
    "Pistola":                         {"prezzo": 10000, "emoji": "🔫", "descrizione": "Arma da fuoco illegale. Obbligatoria per rapine ai bancomat. Non viene consumata — resta in inventario."},
    "Gas Soporifero":                  {"prezzo": 8000,  "emoji": "😴", "descrizione": "Gas anestetico militare che induce il sonno. Necessario per l'Assalto alla Gioielleria."},
    "Dispositivo di Hacking Medio":    {"prezzo": 15000, "emoji": "📡", "descrizione": "Hackera sistemi di sorveglianza di livello medio. Obbligatorio per l'Assalto alla Gioielleria."},
    "Dispositivo di Hacking Avanzato": {"prezzo": 50000, "emoji": "🖥️", "descrizione": "Hackera sistemi digitali di livello militare. Obbligatorio per il Grande Colpo alla Maze Bank."},
    "Lancia Termica":                  {"prezzo": 30000, "emoji": "🔥", "descrizione": "Brucia serrature e porte blindate. Necessaria per aprire le serrature del caveau della Maze Bank."},
    "Trapano Pesante Professionale":   {"prezzo": 50000, "emoji": "⚙️", "descrizione": "Perfora il caveau della Maze Bank. Obbligatorio per il Grande Colpo."},
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
        inv[self.strumento] -= 1
        if inv[self.strumento] == 0:
            del inv[self.strumento]
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
    def __init__(self, autore_id, guadagno, modello, destinazione, messaggio_originale):
        super().__init__(timeout=1800)
        self.autore_id = autore_id
        self.guadagno = guadagno
        self.modello = modello
        self.destinazione = destinazione
        self.messaggio_originale = messaggio_originale
        self.deciso = False

    @discord.ui.button(label="✅ Approva", style=discord.ButtonStyle.success)
    async def approva(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not ha_permessi_approvazione(interaction):
            await interaction.response.send_message("❌ Solo lo staff può approvare le consegne.", ephemeral=True)
            return
        if self.deciso:
            await interaction.response.send_message("⚠️ Questa consegna è già stata processata.", ephemeral=True)
            return

        self.deciso = True
        for child in self.children:
            child.disabled = True

        ordine = ordini_pendenti_macchina.pop(self.autore_id, None)
        furto_cooldown.setdefault(self.autore_id, {})["macchina"] = time.time()
        bilancio = get_balance(self.autore_id)
        bilancio["banca"] += self.guadagno
        salva_dati()

        embed_are = discord.Embed(
            title="✅ CONSEGNA APPROVATA",
            description=(
                f"La consegna del veicolo `{self.modello}` è stata approvata da {interaction.user.mention}.\n\n"
                f"💰 **Compenso:** `{self.guadagno:,}€` accreditati in banca al giocatore."
            ),
            color=discord.Color.green()
        )
        embed_are.set_footer(text="Tokyo Horizon RP | Pannello Staff")
        await interaction.response.edit_message(embed=embed_are, view=self)

        embed_rapine = discord.Embed(
            title="🚗 VEICOLO CONSEGNATO — APPROVATO!",
            description=(
                f"<@{self.autore_id}> Lo staff ha verificato e **approvato** la tua consegna!\n\n"
                f"🚘 **Veicolo:** `{self.modello}`\n"
                f"📍 **Destinazione:** `{self.destinazione}`\n"
                f"💰 **Compenso:** `{self.guadagno:,}€` accreditati in **Banca**."
            ),
            color=discord.Color.green()
        )
        embed_rapine.set_footer(text="Tokyo Horizon RP | Sistema Economia")

        embed_originale_finale = discord.Embed(
            title="✅ Consegna Approvata",
            description=f"Veicolo `{self.modello}` — approvato da {interaction.user.mention}.",
            color=discord.Color.green()
        )
        embed_originale_finale.set_footer(text="Tokyo Horizon RP | Sistema Furto Veicoli")

        try:
            canale_rapine = self.messaggio_originale.channel
            await canale_rapine.send(f"<@{self.autore_id}>", embed=embed_rapine)
        except Exception as e:
            print(f"[ERRORE] Notifica approvazione in rapine fallita: {e}")
        try:
            await self.messaggio_originale.edit(embed=embed_originale_finale, view=None)
        except Exception as e:
            print(f"[ERRORE] Aggiornamento messaggio originale fallito: {e}")

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.danger)
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not ha_permessi_approvazione(interaction):
            await interaction.response.send_message("❌ Solo lo staff può rifiutare le consegne.", ephemeral=True)
            return
        if self.deciso:
            await interaction.response.send_message("⚠️ Questa consegna è già stata processata.", ephemeral=True)
            return

        self.deciso = True
        for child in self.children:
            child.disabled = True

        ordine = ordini_pendenti_macchina.pop(self.autore_id, None)
        salva_dati()

        embed_are = discord.Embed(
            title="❌ CONSEGNA RIFIUTATA",
            description=(
                f"La consegna del veicolo `{self.modello}` è stata **rifiutata** da {interaction.user.mention}.\n\n"
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
                f"🚘 **Veicolo:** `{self.modello}`\n"
                f"💰 Il compenso di `{self.guadagno:,}€` **non** è stato accreditato.\n\n"
                f"Contatta lo staff per maggiori informazioni."
            ),
            color=discord.Color.red()
        )
        embed_rapine.set_footer(text="Tokyo Horizon RP | Sistema Economia")

        embed_originale_finale = discord.Embed(
            title="❌ Consegna Rifiutata",
            description=f"Veicolo `{self.modello}` — rifiutato da {interaction.user.mention}.",
            color=discord.Color.red()
        )
        embed_originale_finale.set_footer(text="Tokyo Horizon RP | Sistema Furto Veicoli")

        try:
            canale_rapine = self.messaggio_originale.channel
            await canale_rapine.send(f"<@{self.autore_id}>", embed=embed_rapine)
        except Exception as e:
            print(f"[ERRORE] Notifica rifiuto in rapine fallita: {e}")
        try:
            await self.messaggio_originale.edit(embed=embed_originale_finale, view=None)
        except Exception as e:
            print(f"[ERRORE] Aggiornamento messaggio originale fallito: {e}")


class VeicoloButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📸 Ho Inviato la Foto", style=discord.ButtonStyle.primary, custom_id="vei:foto")
    async def conferma_foto(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        ordine = ordini_pendenti_macchina.get(uid)
        if not ordine:
            # Ricarica dal file: potrebbe essere stato scritto da un'altra istanza
            _, _, _, _, ordini_freschi, _ = carica_dati()
            ordini_pendenti_macchina.update(ordini_freschi)
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
            _, _, _, _, ordini_freschi, _ = carica_dati()
            ordini_pendenti_macchina.update(ordini_freschi)
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

        ordine["in_attesa"] = True
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

        view_approvazione = ApprovazioneCosegnaView(
            autore_id=uid,
            guadagno=ordine["guadagno"],
            modello=ordine["modello"],
            destinazione=ordine["destinazione"],
            messaggio_originale=interaction.message,
        )

        await interaction.response.send_message(
            "📋 **Richiesta inviata allo staff!** Attendi che verifichino la tua consegna.",
            ephemeral=True
        )
        try:
            canale_staff = await bot.fetch_channel(CANALE_STAFF_VEICOLI)
            await canale_staff.send(embed=embed_staff, view=view_approvazione)
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
        ordine_attivo = ordini_pendenti_macchina.get(uid)
        if ordine_attivo and ordine_attivo.get("in_attesa"):
            await interaction.response.send_message(
                f"⏳ Hai già una consegna del veicolo `{ordine_attivo.get('modello', '?')}` **in attesa di approvazione dello staff**.\n"
                f"Attendi che lo staff approvi o rifiuti prima di iniziare un nuovo furto.\n"
                f"Se pensi ci sia un errore, contatta lo staff per usare `/resetordine`.",
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

    await interaction.response.defer()

    if tipo_scelto == "villa":
        preferenza = ["Grimaldello", "Piede di Porco"]
    elif tipo_scelto == "casa":
        preferenza = ["Piede di Porco"]
    else:
        preferenza = []

    strumento_usato = None
    if tipo_scelto == "villa":
        inv = get_inventario(uid)
        strumento_usato = next((s for s in preferenza if inv.get(s, 0) > 0), None)
        if not strumento_usato:
            await interaction.followup.send(
                "🔒 Per il furto in villa servono **`Piede di Porco`** o **`Grimaldello`** e **`Sistema di Hacking`**. Acquistali con `/negozio`.", ephemeral=True
            )
            return
        if inv.get("Sistema di Hacking", 0) <= 0:
            await interaction.followup.send(
                "💻 Hai lo strumento da scasso ma ti manca il **`Sistema di Hacking`** (4.000€). Acquistalo con `/negozio`.", ephemeral=True
            )
            return
    elif preferenza:
        inv = get_inventario(uid)
        strumento_usato = next((s for s in preferenza if inv.get(s, 0) > 0), None)
        if not strumento_usato:
            nomi = " o ".join(f"`{s}`" for s in preferenza)
            await interaction.followup.send(
                f"🔒 Non puoi fare il furto senza strumenti! Hai bisogno di {nomi}. Acquistali con `/negozio`.", ephemeral=True
            )
            return

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
                "🔑 **Strumento richiesto:** 🛠️ `Cacciavite o Piede di Porco`"
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
    app_commands.Choice(name="Cacciavite (1.250€)",            value="Cacciavite"),
    app_commands.Choice(name="Piede di Porco (1.000€)",        value="Piede di Porco"),
    app_commands.Choice(name="Grimaldello (1.500€)",           value="Grimaldello"),
    app_commands.Choice(name="Grimaldello Avanzato (15.000€)", value="Grimaldello Avanzato"),
    app_commands.Choice(name="Sistema di Hacking (4.000€)",    value="Sistema di Hacking"),
    app_commands.Choice(name="Trapano (9.990€)",               value="Trapano"),
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
    if bil["portafoglio"] < prezzo:
        await interaction.followup.send(
            f"❌ Non hai abbastanza contanti in tasca! Ti servono `{prezzo:,}€` ma ne hai solo `{bil['portafoglio']:,}€`.", ephemeral=True
        )
        return
    bil["portafoglio"] -= prezzo
    inv = get_inventario(interaction.user.id)
    inv[nome] = inv.get(nome, 0) + 1
    salva_dati()
    embed = discord.Embed(
        title="✅ Acquisto Completato!",
        description=(
            f"Hai acquistato **{info['emoji']} {nome}** per `{prezzo:,}€`.\n\n"
            f"💵 **Contanti rimasti:** `{bil['portafoglio']:,}€`\n"
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
    app_commands.Choice(name="Pistola (10.000€)",                          value="Pistola"),
    app_commands.Choice(name="Gas Soporifero (8.000€)",                    value="Gas Soporifero"),
    app_commands.Choice(name="Dispositivo di Hacking Medio (15.000€)",     value="Dispositivo di Hacking Medio"),
    app_commands.Choice(name="Dispositivo di Hacking Avanzato (50.000€)",  value="Dispositivo di Hacking Avanzato"),
    app_commands.Choice(name="Lancia Termica (30.000€)",                   value="Lancia Termica"),
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
    if bil["portafoglio"] < prezzo:
        mancanti = prezzo - bil["portafoglio"]
        await interaction.followup.send(
            f"❌ Non hai abbastanza contanti in tasca!\n\n"
            f"💵 **In tasca:** `{bil['portafoglio']:,}€` | 🏛️ **In banca:** `{bil['banca']:,}€`\n"
            f"💸 **Ti mancano:** `{mancanti:,}€` in tasca\n\n"
            f"👉 Preleva dalla banca con `/preleva {mancanti:,}` e riprova.",
            ephemeral=True
        )
        return
    bil["portafoglio"] -= prezzo
    inv = get_inventario(interaction.user.id)
    inv[nome] = inv.get(nome, 0) + 1
    salva_dati()
    embed = discord.Embed(
        title="✅ Acquisto Completato!",
        description=(
            f"Hai acquistato **{info['emoji']} {nome}** per `{prezzo:,}€`.\n\n"
            f"💵 **Contanti rimasti:** `{bil['portafoglio']:,}€`\n"
            f"🎒 **In inventario:** `{inv[nome]}x {nome}`"
        ),
        color=discord.Color.dark_red()
    )
    embed.set_footer(text="Tokyo Horizon RP | Mercato Nero")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="inventario", description="Visualizza il tuo inventario")
async def inventario_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        inv = get_inventario(interaction.user.id)
        inv_filtrato = {n: q for n, q in inv.items() if isinstance(q, int) and q > 0}
        if not inv_filtrato:
            await interaction.followup.send("🎒 Il tuo inventario è vuoto. Acquista qualcosa con `/negozio` o `/mercatonero`!", ephemeral=True)
            return
        TUTTI_ITEMS = {**NEGOZIO, **MERCATO_NERO}
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
    app_commands.Choice(name="🏛️ Maze Bank",     value="mazebank"),
    app_commands.Choice(name="⚡ Tutti",          value="tutti"),
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
        ]:
            _pd.pop(utente.id, None)
            _t = _td.pop(utente.id, None)
            if _t and not _t.done():
                _t.cancel()
                print(f"[RESETCD] Task {_label} uid={utente.id} cancellato.")
        azzerati = "🏰 Villa, 🏠 Casa, 🚗 Macchina, 🏧 Bancomat, 🍏 Minimarket, 🔫 Armeria, 🏦 Fleeca, 💎 Gioielleria, 🏛️ Maze Bank"
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
    app_commands.Choice(name="Contanti in tasca",              value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",              value="banca"),
    app_commands.Choice(name="Cacciavite",                     value="Cacciavite"),
    app_commands.Choice(name="Grimaldello",                    value="Grimaldello"),
    app_commands.Choice(name="Grimaldello Avanzato",           value="Grimaldello Avanzato"),
    app_commands.Choice(name="Piede di Porco",                 value="Piede di Porco"),
    app_commands.Choice(name="Sistema di Hacking",             value="Sistema di Hacking"),
    app_commands.Choice(name="Trapano",                        value="Trapano"),
    app_commands.Choice(name="Pistola",                        value="Pistola"),
    app_commands.Choice(name="Gas Soporifero",                 value="Gas Soporifero"),
    app_commands.Choice(name="Dispositivo di Hacking Medio",   value="Dispositivo di Hacking Medio"),
    app_commands.Choice(name="Dispositivo di Hacking Avanzato",value="Dispositivo di Hacking Avanzato"),
    app_commands.Choice(name="Lancia Termica",                 value="Lancia Termica"),
    app_commands.Choice(name="Trapano Pesante Professionale",  value="Trapano Pesante Professionale"),
    app_commands.Choice(name="Giubbotto Antiproiettile",       value="Giubbotto Antiproiettile"),
    app_commands.Choice(name="Mitra Compatto",                 value="Mitra Compatto"),
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
    app_commands.Choice(name="Contanti in tasca",              value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",              value="banca"),
    app_commands.Choice(name="Cacciavite",                     value="Cacciavite"),
    app_commands.Choice(name="Grimaldello",                    value="Grimaldello"),
    app_commands.Choice(name="Grimaldello Avanzato",           value="Grimaldello Avanzato"),
    app_commands.Choice(name="Piede di Porco",                 value="Piede di Porco"),
    app_commands.Choice(name="Sistema di Hacking",             value="Sistema di Hacking"),
    app_commands.Choice(name="Trapano",                        value="Trapano"),
    app_commands.Choice(name="Pistola",                        value="Pistola"),
    app_commands.Choice(name="Gas Soporifero",                 value="Gas Soporifero"),
    app_commands.Choice(name="Dispositivo di Hacking Medio",   value="Dispositivo di Hacking Medio"),
    app_commands.Choice(name="Dispositivo di Hacking Avanzato",value="Dispositivo di Hacking Avanzato"),
    app_commands.Choice(name="Lancia Termica",                 value="Lancia Termica"),
    app_commands.Choice(name="Trapano Pesante Professionale",  value="Trapano Pesante Professionale"),
    app_commands.Choice(name="Giubbotto Antiproiettile",       value="Giubbotto Antiproiettile"),
    app_commands.Choice(name="Mitra Compatto",                 value="Mitra Compatto"),
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
        TUTTI_ITEMS = {**NEGOZIO, **MERCATO_NERO}
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
        "villa":    {"label": "🏰 Villa",       "cooldown": 4 * 3600},
        "casa":     {"label": "🏠 Casa",        "cooldown": 4 * 3600},
        "macchina": {"label": "🚗 Macchina",    "cooldown": 2 * 3600},
        "bancomat": {"label": "🏧 Bancomat",    "cooldown": 12 * 3600},
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
            if ore > 0:
                tempo_str = f"{ore}h {minuti}m"
            else:
                tempo_str = f"{minuti}m {secondi}s"
            righe.append(f"{info['label']} — ⏳ `{tempo_str}`")

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
RUOLO_POLIZIA_HARDCODED  = 1515441313216991262

# Tiene traccia di quali uid hanno già un task accredita_bancomat in esecuzione
# per evitare doppi accrediti in caso di istanze multiple o on_ready duplicati
_bancomat_in_corso: set = set()
# task bancomat attivi per uid → cancellabili da resetcooldown
_bancomat_tasks: dict = {}

LOOT_ARMERIA     = 50_000
LOOT_FLEECA      = 250_000
LOOT_GIOIELLERIA = 500_000
LOOT_MAZEBANK    = 1_000_000

_armeria_in_corso: set     = set()
_armeria_tasks: dict       = {}
_fleeca_in_corso: set      = set()
_fleeca_tasks: dict        = {}
_gioielleria_in_corso: set = set()
_gioielleria_tasks: dict   = {}
_mazebank_in_corso: set    = set()
_mazebank_tasks: dict      = {}


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
            await interaction.followup.send("❌ Non hai la `Pistola` nell'inventario! Acquistala con `/compranero`.", ephemeral=True)
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
                "❌ Non hai la `Pistola` nell'inventario! Acquistala con `/compranero`.", ephemeral=True
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
    dialogo_min: int
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
        rapine_dict.pop(criminal_uid, None)
        salva_dati()
        testo = (
            f"✅ <@{criminal_uid}> **{etichetta} completata!**\n"
            f"💰 **`{loot:,}€`** accreditati in banca.\n"
            f"⚠️ Dialogo obbligatorio di almeno **{dialogo_min} minuti** con gli FDO!"
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
        rapine_pendenti_armeria.pop(criminal_uid, None)
        salva_dati()
        testo = (
            f"✅ <@{criminal_uid}> **Svaligiamento Ammu-Nation completato!**\n"
            f"🎒 Bottino: **5x Giubbotto Antiproiettile**, **3x Pistola**, **1x Mitra Compatto** + munizioni — aggiunti all'inventario.\n"
            f"⚠️ Dialogo obbligatorio di almeno **4 minuti** con gli FDO!"
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
        rapine_pendenti_fleeca, "rapine_pendenti_fleeca", _fleeca_in_corso, _fleeca_tasks, dialogo_min=6)

async def accredita_gioielleria(criminal_uid: int, delay: float):
    await _accredita_generico(criminal_uid, delay, LOOT_GIOIELLERIA, "gioielleria", "Assalto alla Gioielleria",
        rapine_pendenti_gioielleria, "rapine_pendenti_gioielleria", _gioielleria_in_corso, _gioielleria_tasks, dialogo_min=7)

async def accredita_mazebank(criminal_uid: int, delay: float):
    await _accredita_generico(criminal_uid, delay, LOOT_MAZEBANK, "mazebank", "Grande Colpo Maze Bank",
        rapine_pendenti_mazebank, "rapine_pendenti_mazebank", _mazebank_in_corso, _mazebank_tasks, dialogo_min=10)


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
            await interaction.followup.send("❌ Ti manca **1x Lancia Termica**. Acquistala con `/compranero`.", ephemeral=True)
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


@bot.tree.command(name="rapina", description="Esegui una rapina — bancomat, armeria, banca e altro")
@app_commands.describe(tipo="Tipo di rapina da effettuare")
@app_commands.choices(tipo=[
    app_commands.Choice(name="🏧 Bancomat — 7.000€ | Piede di Porco + Pistola | Cooldown 12h",                         value="bancomat"),
    app_commands.Choice(name="🍏 Minimarket — 15.000€ | Cacciavite/PdP + Pistola | Cooldown 24h",                      value="minimarket"),
    app_commands.Choice(name="🔫 Ammu-Nation — Giubbotti+Pistole+Mitra | Nessun attrezzo | Cooldown 24h",               value="armeria"),
    app_commands.Choice(name="🏦 Banca Fleeca — 250.000€ | 5x PdP + Trapano | Cooldown 48h",                           value="fleeca"),
    app_commands.Choice(name="💎 Gioielleria — 500.000€ | Hack Medio + Gas Soporifero | Cooldown 4gg",               value="gioielleria"),
    app_commands.Choice(name="🏛️ Maze Bank — 1.000.000€ | Hack Avanzato + Lancia + Trapano + Grim | Cooldown 1 sett.", value="mazebank"),
])
async def rapina(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    uid = interaction.user.id

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
                    "🔒 Per rapinare un bancomat servono **`1x Piede di Porco`** e **`1x Pistola`**. Acquistali con `/negozio` e `/compranero`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        if inv.get("Pistola", 0) <= 0:
            try:
                await interaction.response.send_message(
                    "🔒 Per rapinare un bancomat serve anche **`1x Pistola`**. Acquistala con `/compranero`.",
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
                    "🔒 Per rapinare un minimarket serve **`1x Cacciavite`** o **`1x Piede di Porco`** e **`1x Pistola`**. Acquistali con `/negozio` e `/compranero`.",
                    ephemeral=True
                )
            except Exception:
                pass
            return
        if inv.get("Pistola", 0) <= 0:
            try:
                await interaction.response.send_message(
                    "🔒 Per rapinare un minimarket serve anche **`1x Pistola`**. Acquistala con `/compranero`.",
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
# AVVIO BOT
# =============================================================================
token = os.environ.get("DISCORD_TOKEN", "").strip()
if not token:
    print("❌ ERRORE: Il token Discord non è stato trovato. Imposta la variabile DISCORD_TOKEN.")
else:
    keep_alive()
    bot.run(token)
