import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os

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
# POSIZIONI — aggiungi nuove ville/case qui sotto, una per riga.
# Per aggiungere foto: copia i file nella cartella principale del bot e
# inserisci i nomi dei file in "mappa" e "esterno". Usa None se non hai foto.
# =============================================================================

VILLE = [
    {
        "nome": "Villa di Lusso #1 — Zona Rockford Hills",
        "mappa": "villa1_mappa.jpeg",
        "esterno": "villa1_esterno.jpeg",
    },
    {
        "nome": "Villa di Lusso #2 — Zona Vinewood Hills",
        "mappa": "villa2_mappa.jpeg",
        "esterno": "villa2_esterno.jpeg",
    },
    # {"nome": "Villa #3 — ...", "mappa": "villa3_mappa.jpeg", "esterno": "villa3_esterno.jpeg"},
]

CASE = [
    {
        "nome": "Appartamento Standard #1",
        "mappa": None,      # sostituisci con "casa1_mappa.jpeg" quando hai la foto
        "esterno": None,    # sostituisci con "casa1_esterno.jpeg" quando hai la foto
    },
    # {"nome": "Appartamento #2 — ...", "mappa": "casa2_mappa.jpeg", "esterno": "casa2_esterno.jpeg"},
]

# =============================================================================
# OGGETTI CON RARITÀ — "rarità" è il peso: più basso = più raro.
# Etichette: ✨ Leggendario (1-2) | 💜 Molto Raro (3-6) | 🟠 Raro (7-12)
#            🟡 Non Comune (13-25) | 🔴 Comune (26+)
# =============================================================================

OGGETTI_VILLA = [
    {"nome": "💎 Diamante Purissimo",        "valore": 45000, "rarità": 2},
    {"nome": "👑 Lingotto d'Oro Massiccio",  "valore": 35000, "rarità": 4},
    {"nome": "📿 Collana di Smeraldi",        "valore": 30000, "rarità": 7},
    {"nome": "🖼️ Quadro Antico di Valore",   "valore": 25000, "rarità": 15},
    {"nome": "⌚ Orologio Rolex Tempestato",  "valore": 20000, "rarità": 28},
]

OGGETTI_CASA = [
    {"nome": "📿 Scatola di Gioielli d'Argento", "valore": 10000, "rarità": 4},
    {"nome": "🏺 Vaso di Porcellana Pregiata",    "valore": 8000,  "rarità": 8},
    {"nome": "💵 Contanti nascosti nel cassetto",  "valore": 6000,  "rarità": 18},
    {"nome": "💻 Computer Portatile Gaming",       "valore": 5000,  "rarità": 30},
    {"nome": "📺 Televisore Led 4K",               "valore": 4000,  "rarità": 42},
]

def etichetta_rarità(peso: int) -> str:
    if peso <= 2:   return "✨ Leggendario"
    if peso <= 6:   return "💜 Molto Raro"
    if peso <= 12:  return "🟠 Raro"
    if peso <= 25:  return "🟡 Non Comune"
    return "🔴 Comune"

def campiona_con_rarità(pool: list, k: int) -> list:
    """Campiona k oggetti unici dal pool usando i pesi di rarità."""
    disponibili = list(pool)
    pesi = [o["rarità"] for o in disponibili]
    scelti = []
    for _ in range(k):
        if not disponibili:
            break
        [scelto] = random.choices(disponibili, weights=pesi, k=1)
        idx = disponibili.index(scelto)
        scelti.append(scelto)
        disponibili.pop(idx)
        pesi.pop(idx)
    return scelti

def costruisci_pool(oggetti_scelti: list) -> tuple[list, str]:
    """Restituisce (pool_finale, descrizione_embed) con percentuali basate sulla rarità."""
    pesi = [o["rarità"] for o in oggetti_scelti]
    somma = sum(pesi)
    # Inverti: oggetto più raro ha MENO probabilità di estrazione
    pesi_inv = [round((1 / p) * 100, 2) for p in pesi]
    somma_inv = sum(pesi_inv)
    pool = []
    desc = ""
    for i, ogg in enumerate(oggetti_scelti):
        perc = round((pesi_inv[i] / somma_inv) * 100)
        perc = max(1, perc)  # minimo 1%
        o = ogg.copy()
        o["percentuale"] = perc
        pool.append(o)
        label = etichetta_rarità(ogg["rarità"])
        desc += f"• {ogg['nome']} {label} — `{perc}%` (Valore: `{ogg['valore']:,}€`)\n"
    return pool, desc

# --- DATABASE IN MEMORIA PER L'ECONOMIA ---
economia = {}

def get_balance(user_id):
    if user_id not in economia:
        economia[user_id] = {"portafoglio": 0, "banca": 5000}
    return economia[user_id]

# --- VISTE INTERATTIVE (BOTTONI) ---
class ScassoButtons(discord.ui.View):
    def __init__(self, autore_id, tipo_furto, pool_oggetti):
        super().__init__(timeout=600)
        self.autore_id = autore_id
        self.tipo_furto = tipo_furto
        self.pool_oggetti = pool_oggetti

    async def avvia_scasso(self, interaction: discord.Interaction, metodo: str):
        if interaction.user.id != self.autore_id:
            await interaction.response.send_message("❌ Questa non è la tua azione!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"🛠️ Hai iniziato a `{metodo}`. L'azione richiederà **5 minuti** come da regolamento. Rimani in zona!",
            ephemeral=True
        )

        await asyncio.sleep(300)

        scelte = [ogg for ogg in self.pool_oggetti]
        pesi = [ogg["percentuale"] for ogg in self.pool_oggetti]

        oggetto_estratto = random.choices(scelte, weights=pesi, k=1)[0]
        valore_finale = oggetto_estratto["valore"]

        bilancio = get_balance(self.autore_id)
        bilancio["banca"] += valore_finale

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


# --- COMANDO UNICO /FURTO CON PARAMETRO TIPO ---
@bot.tree.command(name="furto", description="Seleziona il tipo di furto da effettuare nel server")
@app_commands.describe(tipo="Seleziona il tipo di furto (Villa, Casa o Macchina)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Villa", value="villa"),
    app_commands.Choice(name="Casa", value="casa"),
    app_commands.Choice(name="Macchina", value="macchina")
])
async def furto(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    # Defer subito: dice a Discord "sto elaborando" ed evita il timeout di 3s
    await interaction.response.defer()

    tipo_scelto = tipo.value

    # --- LOGICA VILLA ---
    if tipo_scelto == "villa":
        oggetti_scelti = campiona_con_rarità(OGGETTI_VILLA, k=random.randint(3, 4))
        pool_finale, descrizione_oggetti = costruisci_pool(oggetti_scelti)
        valore_max = max(o["valore"] for o in oggetti_scelti)

        location = random.choice(VILLE)

        embed = discord.Embed(
            title=f"🏰 Furto Selezionato: {location['nome']}",
            description=(
                "**INFORMAZIONI SUL COLPO OTTENUTE DAI SATELLITI**\n\n"
                "**Scegli la modalità di infiltrazione:**\n"
                "• 🪟 Forza la finestra sul retro\n"
                "• 🚪 Forza la porta d'ingresso principale\n\n"
                f"📦 **Merci preziose rilevate all'interno (Max {valore_max:,}€):**\n{descrizione_oggetti}\n"
                "🔑 **Oggetto richiesto:** 🪓 `Piede di Porco o Grimaldello`"
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Tokyo Horizon RP | Sistema Furto")

        view = ScassoButtons(interaction.user.id, "villa", pool_finale)
        files = []
        embeds = []

        if location["esterno"]:
            file_esterno = discord.File(location["esterno"], filename="villa_esterno.jpeg")
            files.append(file_esterno)
            embed.set_image(url="attachment://villa_esterno.jpeg")
        embeds.append(embed)

        if location["mappa"]:
            file_mappa = discord.File(location["mappa"], filename="villa_mappa.jpeg")
            files.append(file_mappa)
            embed_mappa = discord.Embed(
                description="📍 **Posizione sulla mappa**",
                color=discord.Color.purple()
            )
            embed_mappa.set_image(url="attachment://villa_mappa.jpeg")
            embeds.append(embed_mappa)

        await interaction.followup.send(embeds=embeds, files=files, view=view)

    # --- LOGICA CASA ---
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

        view = ScassoButtons(interaction.user.id, "casa", pool_finale)
        files = []
        embeds = []

        if location["esterno"]:
            file_esterno = discord.File(location["esterno"], filename="casa_esterno.jpeg")
            files.append(file_esterno)
            embed.set_image(url="attachment://casa_esterno.jpeg")
        embeds.append(embed)

        if location["mappa"]:
            file_mappa = discord.File(location["mappa"], filename="casa_mappa.jpeg")
            files.append(file_mappa)
            embed_mappa = discord.Embed(
                description="📍 **Posizione sulla mappa**",
                color=discord.Color.dark_green()
            )
            embed_mappa.set_image(url="attachment://casa_mappa.jpeg")
            embeds.append(embed_mappa)

        await interaction.followup.send(embeds=embeds, files=files, view=view)

    # --- LOGICA MACCHINA ---
    elif tipo_scelto == "macchina":
        rarita_scelta = random.choice(["Bassa", "Media", "Alta"])
        destinazioni_mappa = [
            "Sfasciacarrozze di Sandy Shores (Desert)",
            "Discarica Centrale di South Los Santos",
            "Molo di Carico dei Container (Porto di LS)",
            "Chop Shop clandestino di Paleto Bay",
            "Garage Segreto a El Burro Heights",
            "Rimessa Industriale di Cypress Flats",
            "Officina Meccanica di Harmony (Route 68)",
            "Parcheggio Sotterraneo Clienti Privati (Richman)",
            "Hangar dell'Esportatore a Grapeseed",
            "Pontile di Contrabbando a Chumash"
        ]
        destinazione_scelta = random.choice(destinazioni_mappa)

        if rarita_scelta == "Bassa":
            veicolo = "🚗 Karin Dilettante (Utilitaria)"
            guadagno = 5000
            colore_embed = discord.Color.light_gray()
        elif rarita_scelta == "Media":
            veicolo = "🚘 Ubermacht Sentinel (Sportiva)"
            guadagno = 15000
            colore_embed = discord.Color.blue()
        else:
            veicolo = "🏎️ Pegassi Zentorno (Supercar)"
            guadagno = 25000
            colore_embed = discord.Color.gold()

        link_mappa_veicolo = "https://i.imgur.com/vaxK08B.png"
        embed = discord.Embed(
            title="🚘 Furto Selezionato: Veicolo da Esportazione",
            description=(
                f"Hai agganciato una vettura tramite la centralina!\n\n"
                f"🚘 **Modello Mezzo:** `{veicolo}`\n"
                f"📊 **Fascia di Rarità:** `{rarita_scelta}`\n"
                f"📍 **Punto di Consegna:** `{destinazione_scelta}`\n"
                f"💵 **Pagamento Pulito:** `{guadagno:,}€` valore fisso\n\n"
                f"⚠️ **REGOLAMENTO:** Hai **10 MINUTI** reali per viaggiare in mappa fino al punto stabilito e premere il tasto verde. Occhio alla Crash-Rule delle FDO!"
            ),
            color=colore_embed
        )
        embed.set_image(url=link_mappa_veicolo)
        embed.set_footer(text="Tokyo Horizon RP | Sistema Furto")

        view = VeicoloButtons(interaction.user.id, guadagno, destinazione_scelta)
        await interaction.followup.send(embed=embed, view=view)

        await asyncio.sleep(600)
        if not view.consegnato:
            embed_fallimento = discord.Embed(
                title="❌ TEMPO SCADUTO - AZIONE FALLITA",
                description=(
                    f"Il timer di 10 minuti è scaduto prima che potessi consegnare il veicolo `{veicolo}`.\n"
                    f"Nessun compenso accreditato."
                ),
                color=discord.Color.red()
            )
            embed_fallimento.set_footer(text="Tokyo Horizon RP | Sistema Furto")
            try:
                await interaction.edit_original_response(embed=embed_fallimento, view=None)
            except Exception:
                pass


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


# --- COOLDOWN DEPOSITA/PRELEVA (60 secondi) ---
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


# --- COMANDO /DEPOSITA ---
@bot.tree.command(name="deposita", description="Deposita contanti dal portafoglio alla banca")
@app_commands.describe(importo="Importo in euro da depositare (es. 5000)")
async def deposita(interaction: discord.Interaction, importo: int):
    attesa = controlla_cooldown(interaction.user.id, "deposita")
    if attesa > 0:
        embed_cd = discord.Embed(
            title="⏳ Operazione non disponibile",
            description=f"Devi aspettare ancora **{attesa} secondi** prima di poter depositare di nuovo.",
            color=discord.Color.orange()
        )
        embed_cd.set_footer(text="Tokyo Horizon RP | Maze Bank")
        await interaction.response.send_message(embed=embed_cd, ephemeral=True)
        return

    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere maggiore di 0€.", ephemeral=True)
        return

    bil = get_balance(interaction.user.id)
    if importo > bil["portafoglio"]:
        embed_err = discord.Embed(
            title="❌ Fondi insufficienti",
            description=(
                f"Non hai abbastanza contanti in tasca.\n\n"
                f"💵 **Contanti disponibili:** `{bil['portafoglio']:,}€`\n"
                f"❌ **Importo richiesto:** `{importo:,}€`"
            ),
            color=discord.Color.red()
        )
        embed_err.set_footer(text="Tokyo Horizon RP | Maze Bank")
        await interaction.response.send_message(embed=embed_err, ephemeral=True)
        return

    bil["portafoglio"] -= importo
    bil["banca"] += importo

    embed = discord.Embed(
        title="🏛️ Deposito Effettuato — Maze Bank",
        description=(
            f"Hai depositato con successo **`{importo:,}€`** sul tuo conto.\n\n"
            f"💵 **Contanti in Tasca:** `{bil['portafoglio']:,}€`\n"
            f"🏛️ **Deposito Bancario:** `{bil['banca']:,}€`"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Tokyo Horizon RP | Maze Bank • Prossima operazione tra 60s")
    await interaction.response.send_message(embed=embed)


# --- COMANDO /PRELEVA ---
@bot.tree.command(name="preleva", description="Preleva contanti dalla banca al portafoglio")
@app_commands.describe(importo="Importo in euro da prelevare (es. 5000)")
async def preleva(interaction: discord.Interaction, importo: int):
    attesa = controlla_cooldown(interaction.user.id, "preleva")
    if attesa > 0:
        embed_cd = discord.Embed(
            title="⏳ Operazione non disponibile",
            description=f"Devi aspettare ancora **{attesa} secondi** prima di poter prelevare di nuovo.",
            color=discord.Color.orange()
        )
        embed_cd.set_footer(text="Tokyo Horizon RP | Maze Bank")
        await interaction.response.send_message(embed=embed_cd, ephemeral=True)
        return

    if importo <= 0:
        await interaction.response.send_message("❌ L'importo deve essere maggiore di 0€.", ephemeral=True)
        return

    bil = get_balance(interaction.user.id)
    if importo > bil["banca"]:
        embed_err = discord.Embed(
            title="❌ Fondi insufficienti",
            description=(
                f"Non hai abbastanza soldi in banca.\n\n"
                f"🏛️ **Saldo Bancario:** `{bil['banca']:,}€`\n"
                f"❌ **Importo richiesto:** `{importo:,}€`"
            ),
            color=discord.Color.red()
        )
        embed_err.set_footer(text="Tokyo Horizon RP | Maze Bank")
        await interaction.response.send_message(embed=embed_err, ephemeral=True)
        return

    bil["banca"] -= importo
    bil["portafoglio"] += importo

    embed = discord.Embed(
        title="💵 Prelievo Effettuato — Maze Bank",
        description=(
            f"Hai prelevato con successo **`{importo:,}€`** dal tuo conto.\n\n"
            f"💵 **Contanti in Tasca:** `{bil['portafoglio']:,}€`\n"
            f"🏛️ **Deposito Bancario:** `{bil['banca']:,}€`"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Tokyo Horizon RP | Maze Bank • Prossima operazione tra 60s")
    await interaction.response.send_message(embed=embed)


# --- AVVIO BOT ---
token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("❌ ERRORE: Il token Discord non è stato trovato. Imposta la variabile DISCORD_TOKEN.")
else:
    bot.run(token)
