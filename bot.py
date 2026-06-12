import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os
import json
import time
from flask import Flask
from threading import Thread

# Configurazione mini-server finto per Render e UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Il bot è vivo!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

intents = discord.Intents.default()
intents.message_content = True

class TokyoHorizonBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Tokyo Horizon Bot: Comandi slash sincronizzati con successo!")

    async def on_ready(self):
        print(f"✅ {self.user} è online e pronto!")
        print(f"   Connesso a {len(self.guilds)} server/i")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Tokyo Horizon RP 🗼"
            )
        )

bot = TokyoHorizonBot()

# =============================================================================
# POSIZIONI — Elenco completo unito delle Ville e delle Case.
# =============================================================================

VILLE = [
    {
        "nome": "Villa di Lusso #1 — Zona Rockford Hills",
        "mappa": None,
        "esterno": "villa1_esterno.png",
    },
    {
        "nome": "Villa di Lusso #2 — Zona Tongva Hills",
        "mappa": None,
        "esterno": "villa2_esterno.png",
    },
    {
        "nome": "Villa di Lusso #3 — Zona Vinewood Hills",
        "mappa": None,
        "esterno": "villa3_esterno.png",
    },
]

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

OGGETTI_VILLA = [
    {"nome": "💎 Diamante Purissimo",        "valore": 45000, "rarità": 2},
    {"nome": "👑 Lingotto d'Oro Massiccio",  "valore": 35000, "rarità": 4},
    {"nome": "📿 Collana di Smeraldi",        "valore": 30000, "rarità": 7},
    {"nome": "🖼️ Quadro Antico di Valore",   "valore": 25000, "rarità": 15},
    {"nome": "⌚ Orologio Rolex Tempestato",  "valore": 20000, "rarità": 28},
]

OGGETTI_VILLA_PREMIUM = [
    {"nome": "💎 Diamante Purissimo",        "valore": 45000, "rarità": 2},
    {"nome": "👑 Lingotto d'Oro Massiccio",  "valore": 35000, "rarità": 4},
    {"nome": "📿 Collana di Smeraldi",        "valore": 30000, "rarità": 7},
]

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

def costruisci_pool(oggetti_scelti: list) -> tuple[list, str]:
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
        desc += f"• {ogg['nome']} {label} — `{perc}%` (Valore: `{ogg['valore']:,}€`)\n"
    return pool, desc

# --- SALVATAGGIO PERSISTENTE ---
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
                return (
                    {int(k): v for k, v in dati.get("economia", {}).items()},
                    cooldown,
                    {int(k): v for k, v in dati.get("inventario", {}).items()},
                )
        except Exception:
            pass
    return {}, {}, {}

def salva_dati():
    with open(DATI_FILE, "w") as f:
        json.dump({
            "economia":       {str(k): v for k, v in economia.items()},
            "furto_cooldown": {str(k): v for k, v in furto_cooldown.items()},
            "inventario":     {str(k): v for k, v in inventario.items()},
        }, f, indent=2)

economia, furto_cooldown, inventario = carica_dati()

def get_balance(user_id):
    if user_id not in economia:
        economia[user_id] = {"portafoglio": 0, "banca": 5000}
    return economia[user_id]

def get_inventario(user_id):
    if user_id not in inventario:
        inventario[user_id] = {}
    return inventario[user_id]

NEGOZIO = {
    "Piede di Porco": {"prezzo": 1000, "emoji": "🪓", "descrizione": "Forza porte e finestre. Usato per ville e case."},
    "Grimaldello":    {"prezzo": 1500, "emoji": "🗝️", "descrizione": "Scassina serrature di lusso. Usato solo per le ville."},
}
RUOLI_STAFF = {"Founder", "CEO", "CO CEO", "Moderatore"}

# =============================================================================
# INTERFACCE BOTTONI (PUNTI DI ACCESSO)
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
            f"🛠️ Hai iniziato a `{metodo}`. L'azione richiederà **5 minutes** come da regolamento. Rimani in zona!",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await asyncio.sleep(300)

        scelte = [ogg for ogg in self.pool_oggetti]
        pesi = [ogg["percentuale"] for ogg in self.pool_oggetti]
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
    RISCHI = {"davanti": 10, "sopra": 70, "dietro": 40, "garage": 55}

    def __init__(self, autore_id, pool_oggetti, strumento):
        super().__init__(timeout=600)
        self.autore_id = autore_id
        self.pool_oggetti = pool_oggetti
        self.strumento = strumento

    async def avvia_ingresso(self, interaction: discord.Interaction, metodo: str, chiave: str):
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
            f"🛠️ Hai scelto di entrare **{metodo}**. L'azione richiederà **5 minuti** come da regolamento. Rimani in zona!",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await asyncio.sleep(300)

        rischio = self.RISCHI[chiave]
        beccato = random.randint(1, 100) <= rischio

        if beccato:
            bilancio = get_balance(self.autore_id)
            multa = 2000
            bilancio["banca"] = max(0, bilancio["banca"] - multa)
            salva_dati()
            embed_fail = discord.Embed(
                title="🚨 SEI STATO ARRESTATO!",
                description=(
                    f"Le forze dell'ordine ti hanno sorpreso durante il furto!\n\n"
                    f"💸 **Multa:** `{multa:,}€` scalati dalla **Banca**."
                ),
                color=discord.Color.red()
            )
            embed_fail.set_footer(text="Tokyo Horizon RP | Sistema Furto")
            await interaction.followup.send(embed=embed_fail)
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
                    f"Hai ripulito la villa senza lasciare tracce!\n\n"
                    f"📦 **Refurtiva:** `{oggetto_estratto['nome']}`\n"
                    f"💰 **Valore Guadagnato:** `{valore_finale:,}€` depositati in **Banca**."
                ),
                color=discord.Color.green()
            )
            embed_vittoria.set_footer(text="Tokyo Horizon RP | Sistema Furto")
            await interaction.followup.send(embed=embed_vittoria)

    @discord.ui.button(label="Ingresso principale", style=discord.ButtonStyle.danger, emoji="🚪")
    async def davanti(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avvia_ingresso(interaction, "dall'ingresso principale", "davanti")

    @discord.ui.button(label="Dal tetto", style=discord.ButtonStyle.primary, emoji="🏠")
    async def sopra(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avvia_ingresso(interaction, "dal tetto", "sopra")

    @discord.ui.button(label="Ingresso sul retro", style=discord.ButtonStyle.secondary, emoji="🔙")
    async def dietro(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avvia_ingresso(interaction, "dall'ingresso sul retro", "dietro")

    @discord.ui.button(label="Dal garage", style=discord.ButtonStyle.secondary, emoji="🚗")
    async def garage(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avvia_ingresso(interaction, "dal garage", "garage")


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
        await interaction.response.defer()
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

        view = VeicoloButtons(self.autore_id, guadagno, dest["nome"])
        msg = await interaction.followup.send(embeds=embeds, files=files, view=view, wait=True)

        await asyncio.sleep(600)
        if not view.consegnato:
            embed_fail = discord.Embed(
                title="❌ TEMPO SCADUTO — AZIONE FALLITA",
                description=f"Il timer di 10 minuti è scaduto. Il veicolo `{modello_input}` non è stato consegnato.",
                color=discord.Color.red()
            )
            embed_fail.set_footer(text="Tokyo Horizon RP | Sistema Furto Veicoli")
            try:
                await msg.edit(embeds=[embed_fail], view=None)
            except Exception:
                pass


class VeicoloButtons(discord.ui.View):
    def __init__(self, autore_id, guadagno, destinazione):
        super().__init__(timeout=600)
        self.autore_id = autore_id
        self.guadagno = guadagno
        self.destinazione = destinazione
        self.consegnato = False

    @discord.ui.button(label="Consegna Veicolo", style=discord.ButtonStyle.success, emoji="🏁")
    async def consegna(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.autore_id:
            await interaction.response.send_message("❌ Questo veicolo non lo stai guidando tu!", ephemeral=True)
            return

        self.consegnato = True
        self.stop()
        for child in self.children:
            child.disabled = True

        bilancio = get_balance(self.autore_id)
        bilancio["banca"] += self.guadagno
        salva_dati()

        embed_successo = discord.Embed(
            title="🚗 VEICOLO CONSEGNATO AL RICETTATORE!",
            description=(
                f"Hai completato la consegna a: `{self.destinazione}`.\n\n"
                f"💰 **Compenso:** `{self.guadagno:,}€` accreditati in **Banca**."
            ),
            color=discord.Color.green()
        )
        embed_successo.set_footer(text="Tokyo Horizon RP | Sistema Economia")
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=embed_successo)


# --- GESTORE ERRORI GLOBALE ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"[ERRORE COMANDO] {type(error).__name__}: {error}")
    msg = "❌ Si è verificato un errore interno. Riprova tra qualche secondo."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        print(f"[ERRORE] Impossibile inviare messaggio di errore: {e}")


# --- COMANDO UNICO /FURTO ---
@bot.tree.command(name="furto", description="Seleziona il tipo di furto da effettuare nel server")
@app_commands.describe(tipo="Seleziona il tipo di furto (Villa, Casa o Macchina)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Villa", value="villa"),
    app_commands.Choice(name="Casa", value="casa"),
    app_commands.Choice(name="Macchina", value="macchina")
])
async def furto(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    uid = interaction.user.id
    tipo_scelto = tipo.value

    if tipo_scelto == "macchina":
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
        furto_cooldown.setdefault(uid, {})["macchina"] = ora_attuale
        salva_dati()
        await interaction.response.send_modal(MacchinaModal(uid))
        return

    await interaction.response.defer()

    if tipo_scelto == "villa":
        preferenza = ["Grimaldello", "Piede di Porco"]
    elif tipo_scelto == "casa":
        preferenza = ["Piede di Porco"]
    else:
        preferenza = []

    strumento_usato = None
    if preferenza:
        inv = get_inventario(uid)
        strumento_usato = next((s for s in preferenza if inv.get(s, 0) > 0), None)
        if not strumento_usato:
            nomi = " o ".join(f"`{s}`" for s in preferenza)
            await interaction.followup.send(
                f"🔒 Non puoi fare il furto senza strumenti! Hai bisogno di {nomi}. Acquistali con `/negozio`.", ephemeral=True
            )
            return

    if tipo_scelto != "villa":
        ora_attuale = time.time()
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
        furto_cooldown.setdefault(uid, {})[tipo_scelto] = ora_attuale
        salva_dati()

    if tipo_scelto == "villa":
        location = random.choice(VILLE)
        is_premium = location["nome"] in ["Villa di Lusso #2 — Zona Tongva Hills", "Villa di Lusso #3 — Zona Vinewood Hills"]
        pool_oggetti = OGGETTI_VILLA_PREMIUM if is_premium else OGGETTI_VILLA
        k = 3 if is_premium else random.randint(3, 4)

        oggetti_scelti = campiona_con_rarità(pool_oggetti, k=k)
        pool_finale, descrizione_oggetti = costruisci_pool(oggetti_scelti)
        valore_max = max(o["valore"] for o in oggetti_scelti)

        embed = discord.Embed(
            title=f"🏰 Furto Selezionato: {location['nome']}",
            description=(
                "**INFORMAZIONI SUL COLPO OTTENUTE DAI SATELLITI**\n\n"
                "**Scegli il punto di ingresso:**\n"
                "• 🚪 Ingresso principale\n"
                "• 🏠 Dal tetto\n"
                "• 🔙 Ingresso sul retro\n"
                "• 🚗 Dal garage\n\n"
                f"📦 **Merci preziose rilevate all'interno (Max {valore_max:,}€):**\n{descrizione_oggetti}\n"
                "🔑 **Oggetto richiesto:** 🪓 `Piede di Porco o Grimaldello`"
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Furto")

        view = VillaScassoButtons(interaction.user.id, pool_finale, strumento_usato)
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

        if location["mappa"]:
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

        if location["mappa"]:
            try:
                file_mappa = discord.File(location["mappa"], filename="casa_mappa.jpeg")
                files.append(file_mappa)
                embed_mappa = discord.Embed(description="📍 **Posizione sulla mappa**", color=discord.Color.dark_green())
                embed_mappa.set_image(url="attachment://casa_mappa.jpeg")
                embeds.append(embed_mappa)
            except FileNotFoundError:
                pass

        await interaction.followup.send(embeds=embeds, files=files, view=view)


# --- COMANDO /CLASSIFICA ---
@bot.tree.command(name="classifica", description="Mostra i giocatori più ricchi del server")
async def classifica(interaction: discord.Interaction):
    if not economia:
        await interaction.response.send_message("📊 Nessun dato disponibile. Nessuno ha ancora usato il sistema economia!", ephemeral=True)
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
    await interaction.response.send_message(embed=embed)


# --- COMANDO /BILANCIO ---
@bot.tree.command(name="bilancio", description="Verifica il tuo conto corrente e il contante in tasca")
async def bilancio(interaction: discord.Interaction):
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
    await interaction.response.send_message(embed=embed)

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
    attesa = controlla_cooldown(interaction.user.id, "deposita")
    if attesa > 0:
        await interaction.response.send_message(f"⏳ Devi aspettare ancora **{attesa} secondi**.", ephemeral=True)
        return
    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere maggiore di 0€.", ephemeral=True)
        return
    bil = get_balance(interaction.user.id)
    if importo > bil["portafoglio"]:
        await interaction.response.send_message("❌ Non hai abbastanza contanti in tasca.", ephemeral=True)
        return
    bil["portafoglio"] -= importo
    bil["banca"] += importo
    salva_dati()
    await interaction.response.send_message(f"🏛️ Depositati con successo **`{importo:,}€`**.")

@bot.tree.command(name="preleva", description="Preleva contanti dalla banca al portafoglio")
@app_commands.describe(importo="Importo in euro da prelevare")
async def preleva(interaction: discord.Interaction, importo: int):
    attesa = controlla_cooldown(interaction.user.id, "preleva")
    if attesa > 0:
        await interaction.response.send_message(f"⏳ Devi aspettare ancora **{attesa} secondi**.", ephemeral=True)
        return
    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere maggiore di 0€.", ephemeral=True)
        return
    bil = get_balance(interaction.user.id)
    if importo > bil["banca"]:
        await interaction.response.send_message("❌ Non hai abbastanza soldi in banca.", ephemeral=True)
        return
    bil["banca"] -= importo
    bil["portafoglio"] += importo
    salva_dati()
    await interaction.response.send_message(f"💵 Prelevati con successo **`{importo:,}€`**.")

@bot.tree.command(name="paga", description="Paga un altro giocatore con i contanti in tasca")
@app_commands.describe(utente="Il giocatore a cui vuoi pagare", importo="Importo in euro da pagare")
async def paga(interaction: discord.Interaction, utente: discord.Member, importo: int):
    mittente = interaction.user
    if utente.id == mittente.id or utente.bot or importo <= 0:
        await interaction.response.send_message("❌ Transazione non valida.", ephemeral=True)
        return
    bil_mittente = get_balance(mittente.id)
    if importo > bil_mittente["portafoglio"]:
        await interaction.response.send_message("❌ Contanti insufficienti in tasca.", ephemeral=True)
        return
    bil_mittente["portafoglio"] -= importo
    bil_destinatario = get_balance(utente.id)
    bil_destinatario["portafoglio"] += importo
    salva_dati()
    await interaction.response.send_message(f"💸 Hai pagato a {utente.mention} l'importo di `{importo:,}€`.")


# --- NEGOZIO, INVENTARIO, RESET COOLDOWN ---

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
    app_commands.Choice(name="Piede di Porco (1000€)", value="Piede di Porco"),
    app_commands.Choice(name="Grimaldello (1500€)",   value="Grimaldello"),
])
async def compra(interaction: discord.Interaction, articolo: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    nome = articolo.value
    info = NEGOZIO[nome]
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
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="inventario", description="Visualizza il tuo inventario")
async def inventario_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    inv = get_inventario(interaction.user.id)
    if not inv:
        await interaction.followup.send("🎒 Il tuo inventario è vuoto. Acquista qualcosa con `/negozio`!", ephemeral=True)
        return
    righe = "\n".join(f"• {NEGOZIO[n]['emoji'] if n in NEGOZIO else '📦'} **{n}** — `{q}x`" for n, q in inv.items())
    embed = discord.Embed(title=f"🎒 Inventario di {interaction.user.display_name}", description=righe, color=discord.Color.blue())
    embed.set_footer(text="Tokyo Horizon RP | Sistema Inventario")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="resetcooldown", description="[MOD] Azzera il cooldown furto di un giocatore")
@app_commands.describe(utente="Il giocatore di cui resettare il cooldown")
async def resetcooldown(interaction: discord.Interaction, utente: discord.Member):
    await interaction.response.defer(ephemeral=True)
    ha_permesso = any(r.name in RUOLI_STAFF for r in interaction.user.roles) or interaction.user.guild_permissions.administrator
    if not ha_permesso:
        await interaction.followup.send("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        return
    if utente.id in furto_cooldown:
        furto_cooldown[utente.id] = {}
        salva_dati()
    await interaction.followup.send(f"✅ Cooldown furto di {utente.mention} azzerato per tutti i tipi (villa, casa, macchina).", ephemeral=True)


@bot.tree.command(name="dai", description="[MOD] Dai contanti o oggetti a un giocatore")
@app_commands.describe(
    utente="Il giocatore a cui dare qualcosa",
    tipo="Cosa vuoi dare",
    quantita="Importo in € (per contanti) o quantità (per oggetti)"
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Contanti in tasca",    value="portafoglio"),
    app_commands.Choice(name="Contanti in banca",    value="banca"),
    app_commands.Choice(name="Grimaldello",          value="Grimaldello"),
    app_commands.Choice(name="Piede di Porco",       value="Piede di Porco"),
])
async def dai(interaction: discord.Interaction, utente: discord.Member, tipo: app_commands.Choice[str], quantita: int):
    await interaction.response.defer(ephemeral=True)
    ha_permesso = any(r.name in RUOLI_STAFF for r in interaction.user.roles) or interaction.user.guild_permissions.administrator
    if not ha_permesso:
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
    await interaction.followup.send(embed=embed)


# --- AVVIO BOT ---
token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("❌ ERRORE: Il token Discord non è stato trovato. Imposta la variabile DISCORD_TOKEN.")
else:
    keep_alive()
    bot.run(token)

