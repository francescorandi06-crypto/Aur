import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os
import json
import time
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
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class HorizonTree(app_commands.CommandTree):
    """CommandTree personalizzato che filtra slash command scaduti prima di eseguirli."""
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.type == discord.InteractionType.application_command:
            age = (discord.utils.utcnow() - interaction.created_at).total_seconds()
            if age > 2.5:
                cmd = getattr(interaction.command, 'name', '?')
                print(f"[SKIP] Slash command scaduto ({age:.1f}s): /{cmd} — ignorato.")
                return False
        return True


class TokyoHorizonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, tree_cls=HorizonTree)
        self.aiohttp_session: aiohttp.ClientSession = None

    async def setup_hook(self):
        self.aiohttp_session = aiohttp.ClientSession()
        self.add_view(VeicoloButtons())
        await self.tree.sync()
        print("Tokyo Horizon Bot: Comandi slash sincronizzati con successo!")

    async def close(self):
        if self.aiohttp_session and not self.aiohttp_session.closed:
            await self.aiohttp_session.close()
        await super().close()

    async def on_ready(self):
        print(f"✅ {self.user} è online e pronto!")
        print(f"   Connesso a {len(self.guilds)} server/i")
        for guild in self.guilds:
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)
        print("   Comandi guild-specifici rimossi (pulizia duplicati).")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Tokyo Horizon RP 🗼"
            )
        )

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
                return (
                    {int(k): v for k, v in dati.get("economia", {}).items()},
                    cooldown,
                    {int(k): v for k, v in dati.get("inventario", {}).items()},
                    dati.get("canale_furti_id", None),
                    ordini,
                )
        except Exception:
            pass
    return {}, {}, {}, None, {}

def salva_dati():
    with open(DATI_FILE, "w") as f:
        json.dump({
            "economia":        {str(k): v for k, v in economia.items()},
            "furto_cooldown":  {str(k): v for k, v in furto_cooldown.items()},
            "inventario":      {str(k): v for k, v in inventario.items()},
            "canale_furti_id": canale_furti_id,
            "ordini_macchina": {str(k): v for k, v in ordini_pendenti_macchina.items()},
        }, f, indent=2)

economia, furto_cooldown, inventario, canale_furti_id, ordini_pendenti_macchina = carica_dati()

def get_balance(user_id):
    if user_id not in economia:
        economia[user_id] = {"portafoglio": 0, "banca": 5000}
    return economia[user_id]

def get_inventario(user_id):
    if user_id not in inventario:
        inventario[user_id] = {}
    return inventario[user_id]

NEGOZIO = {
    "Piede di Porco":      {"prezzo": 1000, "emoji": "🪓",  "descrizione": "Forza porte e finestre. Indispensabile per colpi in case, ville e operazioni ad alto rischio."},
    "Grimaldello":         {"prezzo": 1500, "emoji": "🗝️", "descrizione": "Scassina serrature di alta sicurezza. Fondamentale per colpi in ville, operazioni epiche e leggendarie."},
    "Sistema di Hacking":  {"prezzo": 4000, "emoji": "💻",  "descrizione": "Disabilita sistemi di allarme e telecamere. Obbligatorio per ogni furto in villa (insieme a Piede di Porco o Grimaldello)."},
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
        await interaction.followup.send(embed=embed_staff, view=view_approvazione)


# =============================================================================
# GESTORE ERRORI GLOBALE
# =============================================================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        age = (discord.utils.utcnow() - interaction.created_at).total_seconds()
        if age > 2.5:
            return
    print(f"[ERRORE COMANDO] {type(error).__name__}: {error}")
    if isinstance(error, app_commands.CommandSignatureMismatch):
        print("[INFO] Firma comando non aggiornata — risincronizzazione in corso...")
        await bot.tree.sync()
        msg = "⚠️ Il comando è stato appena aggiornato. **Riprova tra 10 secondi** — Discord deve ricaricare la nuova versione."
    else:
        msg = "❌ Si è verificato un errore interno. Riprova tra qualche secondo."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        print(f"[ERRORE] Impossibile inviare messaggio di errore: {e}")


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
    bil = get_balance(interaction.user.id)
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
    ora = asyncio.get_event_loop().time()
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
    app_commands.Choice(name="Piede di Porco (1000€)",     value="Piede di Porco"),
    app_commands.Choice(name="Grimaldello (1500€)",        value="Grimaldello"),
    app_commands.Choice(name="Sistema di Hacking (4000€)", value="Sistema di Hacking"),
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


@bot.tree.command(name="inventario", description="Visualizza il tuo inventario")
async def inventario_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        inv = get_inventario(interaction.user.id)
        inv_filtrato = {n: q for n, q in inv.items() if isinstance(q, int) and q > 0}
        if not inv_filtrato:
            await interaction.followup.send("🎒 Il tuo inventario è vuoto. Acquista qualcosa con `/negozio`!", ephemeral=True)
            return
        righe = "\n".join(
            f"• {NEGOZIO[n]['emoji'] if n in NEGOZIO else '📦'} **{n}** — `{q}x`"
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
    app_commands.Choice(name="🏰 Villa",    value="villa"),
    app_commands.Choice(name="🏠 Casa",     value="casa"),
    app_commands.Choice(name="🚗 Macchina", value="macchina"),
    app_commands.Choice(name="🏧 Bancomat", value="bancomat"),
    app_commands.Choice(name="⚡ Tutti",    value="tutti"),
])
async def resetcooldown(interaction: discord.Interaction, utente: discord.Member, tipo: app_commands.Choice[str]):
    if not ha_permessi_staff(interaction):
        await interaction.response.send_message("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    cd = furto_cooldown.get(utente.id, {})
    if tipo.value == "tutti":
        furto_cooldown[utente.id] = {}
        azzerati = "🏰 Villa, 🏠 Casa, 🚗 Macchina, 🏧 Bancomat"
    else:
        cd.pop(tipo.value, None)
        furto_cooldown[utente.id] = cd
        azzerati = tipo.name
    salva_dati()
    await interaction.response.send_message(
        f"✅ Azzerato **{azzerati}** per {utente.mention}.", ephemeral=True
    )


@bot.tree.command(name="dai", description="[MOD] Dai contanti o oggetti a un giocatore")
@app_commands.describe(
    utente="Il giocatore a cui dare qualcosa",
    tipo="Cosa vuoi dare",
    quantita="Importo in € (per contanti) o quantità (per oggetti)"
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Contanti in tasca",  value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",  value="banca"),
    app_commands.Choice(name="Grimaldello",        value="Grimaldello"),
    app_commands.Choice(name="Piede di Porco",     value="Piede di Porco"),
    app_commands.Choice(name="Sistema di Hacking", value="Sistema di Hacking"),
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
    app_commands.Choice(name="Contanti in tasca",  value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",  value="banca"),
    app_commands.Choice(name="Grimaldello",        value="Grimaldello"),
    app_commands.Choice(name="Piede di Porco",     value="Piede di Porco"),
    app_commands.Choice(name="Sistema di Hacking", value="Sistema di Hacking"),
])
async def togli(interaction: discord.Interaction, utente: discord.Member, tipo: app_commands.Choice[str], quantita: int):
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
        info = NEGOZIO.get(valore, {})
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

LOOT_BANCOMAT = 7000
ATM_IMAGE = "attached_assets/IMG_1429_1781378756942.jpeg"
CANALE_POLIZIA_HARDCODED = 1515439682333180015
RUOLO_POLIZIA_HARDCODED  = 1515441313216991262


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

        bil = get_balance(self.criminal_uid)
        bil["banca"] += LOOT_BANCOMAT
        salva_dati()

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="🚔 RAPINA IN CARICO — BANCOMAT 🏧",
            description=(
                f"✅ **Agente in servizio:** {interaction.user.mention}\n\n"
                f"🦹 **Criminale:** `{self.nome_pg}`\n"
                f"📍 **Posizione:** `{self.posizione}`\n"
                f"👥 **Partecipanti criminale:** `{self.partecipanti}`\n\n"
                f"💰 Bottino di `{LOOT_BANCOMAT:,}€` accreditato in banca al criminale.\n"
                f"⏱️ Scassinamento: 4 minuti | Fuga immediata (nessun dialogo)"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Tokyo Horizon RP | Rapina in Corso")
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

        try:
            criminal = await bot.fetch_user(self.criminal_uid)
            await criminal.send(
                f"🚔 Un FDO (**{interaction.user.display_name}**) ha accettato il servizio per la tua rapina al bancomat!\n"
                f"💰 **`{LOOT_BANCOMAT:,}€`** sono stati accreditati in banca.\n"
                f"⚠️ Procedi con il piano — rispetta le regole di equipaggiamento!"
            )
        except Exception as e:
            print(f"[BANCOMAT] DM criminale fallito: {e}")

    async def on_timeout(self):
        inv = get_inventario(self.criminal_uid)
        inv["Piede di Porco"] = inv.get("Piede di Porco", 0) + 1
        furto_cooldown.get(self.criminal_uid, {}).pop("bancomat", None)
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
            criminal = await bot.fetch_user(self.criminal_uid)
            await criminal.send(
                "⌛ Nessun FDO ha risposto alla tua rapina al bancomat entro 10 minuti.\n"
                "🪓 Il tuo **Piede di Porco** è stato restituito e il cooldown azzerato.\n"
                "Puoi riprovare quando vuoi!"
            )
        except Exception as e:
            print(f"[BANCOMAT] DM timeout criminale fallito: {e}")


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
        await interaction.response.defer(ephemeral=True)

        uid  = self.uid
        nome = self.nome_pg.value.strip()
        pos  = self.posizione.value.strip()
        part = self.partecipanti.value.strip()

        inv = get_inventario(uid)
        if inv.get("Piede di Porco", 0) <= 0:
            await interaction.followup.send("❌ Non hai più il `Piede di Porco` nell'inventario!", ephemeral=True)
            return

        inv["Piede di Porco"] -= 1
        if inv["Piede di Porco"] == 0:
            del inv["Piede di Porco"]
        furto_cooldown.setdefault(uid, {})["bancomat"] = time.time()
        salva_dati()

        embed_ok = discord.Embed(
            title="✅ Rapina Bancomat Inviata!",
            description=(
                f"🕵️ **Personaggio:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti:** `{part}`\n\n"
                f"🪓 Hai usato **1x Piede di Porco**.\n"
                f"💰 Riceverai **`{LOOT_BANCOMAT:,}€`** in banca non appena un FDO accetta il servizio.\n\n"
                f"⏳ La rapina si annulla se nessun FDO risponde entro **10 minuti** — "
                f"il Piede di Porco ti viene restituito.\n"
                f"⚠️ Solo armi bianche o pistole leggere — vietati giubbotti e caschi!"
            ),
            color=discord.Color.green()
        )
        embed_ok.set_thumbnail(url="attachment://atm_rules.jpeg")
        embed_ok.set_footer(text="Tokyo Horizon RP | Sistema Rapina")
        files_ok = [discord.File(ATM_IMAGE, filename="atm_rules.jpeg")] if os.path.exists(ATM_IMAGE) else []
        await interaction.followup.send(embed=embed_ok, files=files_ok, ephemeral=True)

        mention = f"<@&{RUOLO_POLIZIA_HARDCODED}>"
        embed_pol = discord.Embed(
            title="🚨 RAPINA IN CORSO — BANCOMAT 🏧",
            description=(
                f"🦹 **Criminale:** `{nome}`\n"
                f"📍 **Posizione:** `{pos}`\n"
                f"👥 **Partecipanti criminale:** `{part}`\n\n"
                f"👮 **FDO richiesti:** Max **2 FDO**\n"
                f"⚔️ **Equipaggiamento:** Solo armi bianche o pistole leggere\n"
                f"🚫 Vietati giubbotti e caschi\n"
                f"⏱️ **Scassinamento:** 4 minuti | Fuga immediata (nessun dialogo)\n"
                f"💰 **Bottino:** `{LOOT_BANCOMAT:,}€` in contanti puliti\n\n"
                f"⏳ Clicca **Accetta Servizio** entro 10 minuti o la rapina viene annullata."
            ),
            color=discord.Color.red()
        )
        embed_pol.set_thumbnail(url="attachment://atm_rules.jpeg")
        embed_pol.set_footer(text="Tokyo Horizon RP | Allerta FDO — 10 minuti per rispondere")

        view = AccettaRapinaView(uid, nome, pos, part)
        files_pol = [discord.File(ATM_IMAGE, filename="atm_rules.jpeg")] if os.path.exists(ATM_IMAGE) else []

        try:
            target_channel = bot.get_channel(CANALE_POLIZIA_HARDCODED) or await bot.fetch_channel(CANALE_POLIZIA_HARDCODED)
        except Exception as e:
            print(f"[BANCOMAT] Canale polizia non trovato: {e}")
            target_channel = interaction.channel

        try:
            if target_channel:
                msg = await target_channel.send(content=mention, embed=embed_pol, files=files_pol, view=view)
                view.message = msg
        except Exception as e:
            print(f"[BANCOMAT] Invio notifica fallito: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"[BANCOMAT MODAL] {type(error).__name__}: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Errore interno. Riprova.", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="rapina", description="Esegui una rapina — bancomat e altro")
@app_commands.describe(tipo="Tipo di rapina da effettuare")
@app_commands.choices(tipo=[
    app_commands.Choice(name="🏧 Bancomat — 7.000€ | Piede di Porco | Cooldown 12h", value="bancomat"),
])
async def rapina(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    uid = interaction.user.id

    if tipo.value == "bancomat":
        ora = time.time()
        ultimo = furto_cooldown.get(uid, {}).get("bancomat", 0)
        if ora - ultimo < 12 * 3600:
            rimanenti = int(12 * 3600 - (ora - ultimo))
            ore_r = rimanenti // 3600
            min_r = (rimanenti % 3600) // 60
            await interaction.response.send_message(
                f"⏳ Devi aspettare ancora **{ore_r}h {min_r}m** prima di poter rapinare un altro bancomat.",
                ephemeral=True
            )
            return

        inv = get_inventario(uid)
        if inv.get("Piede di Porco", 0) <= 0:
            await interaction.response.send_message(
                "🔒 Per scassinare un bancomat serve **`1x Piede di Porco`**. Acquistalo con `/negozio`.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(BancomatModal(uid))




# =============================================================================
# AVVIO BOT
# =============================================================================
token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("❌ ERRORE: Il token Discord non è stato trovato. Imposta la variabile DISCORD_TOKEN.")
else:
    keep_alive()
    bot.run(token)
