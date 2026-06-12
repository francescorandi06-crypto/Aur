import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import os
from flask import Flask
from threading import Thread

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
# VILLE — aggiungi nuove ville qui sotto.
# =============================================================================

VILLE = [
    {
        "nome": "Villa di Lusso #1 — Zona Rockford Hills",
        "mappa": "villa1_mappa.jpeg",
        "esterno": "villa1_esterno.jpeg",
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
# OGGETTI — Pool completo per ville standard, pool premium per ville nuove.
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
        if not disponibili:
            break
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

# --- DATABASE IN MEMORIA PER L'ECONOMIA ---
economia = {}

def get_balance(user_id):
    if user_id not in economia:
        economia[user_id] = {"portafoglio": 0, "banca": 5000}
    return economia[user_id]

# =============================================================================
# PUNTI D'ACCESSO CON TASSO DI RIUSCITA
# Frontale: 10% | Dal tetto: 70% | Garage: 45% | Dietro: 55%
# =============================================================================

ACCESSI_VILLA = [
    {"label": "Frontale",  "emoji": "🚪", "stile": discord.ButtonStyle.danger,    "tasso": 10},
    {"label": "Dal tetto", "emoji": "🏠", "stile": discord.ButtonStyle.primary,   "tasso": 70},
    {"label": "Garage",    "emoji": "🚗", "stile": discord.ButtonStyle.secondary, "tasso": 45},
    {"label": "Dietro",    "emoji": "🌿", "stile": discord.ButtonStyle.secondary, "tasso": 55},
]

class ScassoButtons(discord.ui.View):
    def __init__(self, autore_id, tipo_furto, pool_oggetti):
        super().__init__(timeout=600)
        self.autore_id = autore_id
        self.tipo_furto = tipo_furto
        self.pool_oggetti = pool_oggetti

        for accesso in ACCESSI_VILLA:
            btn = discord.ui.Button(
                label=f"{accesso['label']} ({accesso['tasso']}%)",
                emoji=accesso["emoji"],
                style=accesso["stile"],
                custom_id=f"accesso_{accesso['label'].lower().replace(' ', '_')}"
            )
            btn.callback = self._make_callback(accesso)
            self.add_item(btn)

    def _make_callback(self, accesso):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.autore_id:
                await interaction.response.send_message("❌ Questa non è la tua azione!", ephemeral=True)
                return

            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            await interaction.response.send_message(
                f"{accesso['emoji']} Hai scelto l'accesso **{accesso['label']}** "
                f"(Tasso di riuscita: `{accesso['tasso']}%`). "
                f"L'azione richiederà **5 minuti** come da regolamento. Rimani in zona!",
                ephemeral=True
            )

            await asyncio.sleep(300)

            successo = random.randint(1, 100) <= accesso["tasso"]

            if successo:
                scelte = [ogg for ogg in self.pool_oggetti]
                pesi = [ogg["percentuale"] for ogg in self.pool_oggetti]
                oggetto_estratto = random.choices(scelte, weights=pesi, k=1)[0]
                valore_finale = oggetto_estratto["valore"]

                bilancio = get_balance(self.autore_id)
                bilancio["banca"] += valore_finale

                embed_vittoria = discord.Embed(
                    title=f"✅ FURTO IN {self.tipo_furto.upper()} COMPLETATO!",
                    description=(
                        f"Accesso **{accesso['label']}** riuscito! Hai ripulito la zona senza lasciare tracce!\n\n"
                        f"📦 **Refurtiva:** `{oggetto_estratto['nome']}`\n"
                        f"💰 **Valore Guadagnato:** `{valore_finale:,}€` depositati in **Banca**."
                    ),
                    color=discord.Color.green()
                )
                embed_vittoria.set_footer(text="Tokyo Horizon RP | Sistema Economia")
                await interaction.followup.send(embed=embed_vittoria)
            else:
                penale = 2000 if self.tipo_furto == "villa" else 1000
                bilancio = get_balance(self.autore_id)
                bilancio_precedente = bilancio["portafoglio"] + bilancio["banca"]
                sottrazione = min(penale, bilancio["portafoglio"] + bilancio["banca"])
                if bilancio["portafoglio"] >= penale:
                    bilancio["portafoglio"] -= penale
                elif bilancio["portafoglio"] > 0:
                    resto = penale - bilancio["portafoglio"]
                    bilancio["portafoglio"] = 0
                    bilancio["banca"] = max(0, bilancio["banca"] - resto)
                else:
                    bilancio["banca"] = max(0, bilancio["banca"] - penale)

                embed_fallito = discord.Embed(
                    title=f"❌ FURTO IN {self.tipo_furto.upper()} FALLITO!",
                    description=(
                        f"L'accesso **{accesso['label']}** non è riuscito! Sei stato scoperto!\n\n"
                        f"🚑 **Spese Ospedaliere / Multa:** `-{penale:,}€` scalati dal tuo conto.\n"
                        f"⚠️ Stai più attento la prossima volta."
                    ),
                    color=discord.Color.red()
                )
                embed_fallito.set_footer(text="Tokyo Horizon RP | Sistema Economia")
                await interaction.followup.send(embed=embed_fallito)

        return callback


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
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed_successo)


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
    await interaction.response.defer()
    tipo_scelto = tipo.value

    if tipo_scelto == "villa":
        location = random.choice(VILLE)
        is_premium = location["nome"] in [
            "Villa di Lusso #2 — Zona Tongva Hills",
            "Villa di Lusso #3 — Zona Vinewood Hills",
        ]
        pool_oggetti = OGGETTI_VILLA_PREMIUM if is_premium else OGGETTI_VILLA
        k = 3 if is_premium else random.randint(3, 4)
        oggetti_scelti = campiona_con_rarità(pool_oggetti, k=k)
        pool_finale, descrizione_oggetti = costruisci_pool(oggetti_scelti)
        valore_max = max(o["valore"] for o in oggetti_scelti)

        embed = discord.Embed(
            title=f"🏰 Furto Selezionato: {location['nome']}",
            description=(
                "**INFORMAZIONI SUL COLPO OTTENUTE DAI SATELLITI**\n\n"
                "**Scegli il punto d'accesso:**\n"
                "• 🚪 Frontale — Tasso riuscita `10%`\n"
                "• 🏠 Dal tetto — Tasso riuscita `70%`\n"
                "• 🚗 Garage — Tasso riuscita `45%`\n"
                "• 🌿 Dietro — Tasso riuscita `55%`\n\n"
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
            try:
                file_esterno = discord.File(location["esterno"], filename="villa_esterno.png")
                files.append(file_esterno)
                embed.set_image(url="attachment://villa_esterno.png")
            except FileNotFoundError:
                pass
        embeds.append(embed)

        if location["mappa"]:
            try:
                file_mappa = discord.File(location["mappa"], filename="villa_mappa.jpeg")
                files.append(file_mappa)
                embed_mappa = discord.Embed(
                    description="📍 **Posizione sulla mappa**",
                    color=discord.Color.purple()
                )
                embed_mappa.set_image(url="attachment://villa_mappa.jpeg")
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
                "**Scegli il punto d'accesso:**\n"
                "• 🚪 Frontale — Tasso riuscita `10%`\n"
                "• 🏠 Dal tetto — Tasso riuscita `70%`\n"
                "• 🚗 Garage — Tasso riuscita `45%`\n"
                "• 🌿 Dietro — Tasso riuscita `55%`\n\n"
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
            try:
                file_esterno = discord.File(location["esterno"], filename="casa_esterno.jpeg")
                files.append(file_esterno)
                embed.set_image(url="attachment://casa_esterno.jpeg")
            except FileNotFoundError:
                pass
        embeds.append(embed)

        if location["mappa"]:
            try:
                file_mappa = discord.File(location["mappa"], filename="casa_mappa.jpeg")
                files.append(file_mappa)
                embed_mappa = discord.Embed(
                    description="📍 **Posizione sulla mappa**",
                    color=discord.Color.dark_green()
                )
                embed_mappa.set_image(url="attachment://casa_mappa.jpeg")
                embeds.append(embed_mappa)
            except FileNotFoundError:
                pass

        await interaction.followup.send(embeds=embeds, files=files, view=view)

    elif tipo_scelto == "macchina":
        rarita_scelta = random.choice(["Bassa", "Media", "Alta"])
        destinazioni_mappa = [
            "Sfasciacarrozze di Sandy Shores (Desert)", "Discarica Centrale di South Los Santos",
            "Molo di Carico dei Container (Porto di LS)", "Chop Shop clandestino di Paleto Bay",
            "Garage Segreto a El Burro Heights", "Rimessa Industriale di Cypress Flats",
            "Officina Meccanica di Harmony (Route 68)", "Parcheggio Sotterraneo Clienti Privati (Richman)",
            "Hangar dell'Esportatore a Grapeseed", "Pontile di Contrabbando a Chumash"
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
                description=f"Il timer di 10 minuti è scaduto prima che potessi consegnare il veicolo `{veicolo}`.",
                color=discord.Color.red()
            )
            embed_fallimento.set_footer(text="Tokyo Horizon RP | Sistema Furto")
            try:
                await interaction.edit_original_response(embed=embed_fallimento, view=None)
            except Exception:
                pass


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


# --- COOLDOWN E ALTRI COMANDI BANCA ---
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
    await interaction.response.send_message(f"💸 Hai pagato a {utente.mention} l'importo di `{importo:,}€`.")


# --- AVVIO ---
token = os.environ.get("DISCORD_TOKEN")
if not token:
    print("❌ ERRORE: Il token Discord non è stato trovato. Imposta la variabile DISCORD_TOKEN.")
else:
    keep_alive()
    bot.run(token)
