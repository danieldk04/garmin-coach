// Widget voor je beginscherm, in de stijl van Bevel: drie ringen op een rij.
// Werkt met de gratis app Scriptable. Vul hieronder je adres en code in.
//
// LAYOUT kiest hoe de widget eruitziet. Verander het woord tussen de
// aanhalingstekens om te wisselen, en run het script los om te zien hoe het
// oogt voordat je hem op je beginscherm zet.
//   "ringen"   -> drie ringen op een rij, zoals Bevel (past bij klein formaat)
//   "compact"  -> één grote ring met een lijst cijfers eronder (medium formaat)
//   "cijfers"  -> alleen een lijst met getallen, geen ringen

const ADRES = "https://garmin-coach-jbe3.onrender.com";
const CODE = "VUL-JE-CODE-IN";
const LAYOUT = "ringen";

const NIVEAU = { READY: "Fris", MODERATE: "Redelijk", LOW: "Laag",
                 VERY_LOW: "Erg laag", HIGH: "Goed", PRIME: "Topvorm" };

const KLEUR = {
  belasting: new Color("#f5a623"),
  herstel: new Color("#8bc34a"),
  slaap: new Color("#5b7fff"),
  tekst: new Color("#1c1e21"),
  zacht: new Color("#8a8f98"),
  fout: new Color("#d9455f"),
  achtergrondring: new Color("#e9e9ec"),
};

// --------------------------------------------------------------------- //
//  Data ophalen
// --------------------------------------------------------------------- //

async function haalOp() {
  const verzoek = new Request(ADRES + "/api/dashboard");
  verzoek.headers = { "X-Toegang": CODE };
  const d = await verzoek.loadJSON();
  if (verzoek.response.statusCode !== 200) {
    throw new Error(d.detail || `Server gaf code ${verzoek.response.statusCode}`);
  }
  return d;
}

function metrieken(d) {
  const belasting = d.stappen.doel
    ? Math.round((d.stappen.aantal / d.stappen.doel) * 100)
    : 0;
  return {
    belasting: Math.max(0, Math.min(100, belasting)),
    herstel: d.gereedheid.score ?? 0,
    slaap: d.slaap.score ?? 0,
  };
}

// --------------------------------------------------------------------- //
//  Een ring tekenen (Scriptable heeft geen kant-en-klare ring, dus we
//  tekenen hem zelf als afbeelding: een grijze cirkel met een gekleurd deel
//  erover, en het percentage in het midden.)
// --------------------------------------------------------------------- //

function boogpunten(ctx, midden, straal, vanHoek, totHoek) {
  const pad = new Path();
  const stappen = 60;
  for (let i = 0; i <= stappen; i++) {
    const hoek = vanHoek + (totHoek - vanHoek) * (i / stappen);
    const punt = new Point(
      midden.x + straal * Math.cos(hoek),
      midden.y + straal * Math.sin(hoek)
    );
    if (i === 0) pad.move(punt);
    else pad.addLine(punt);
  }
  ctx.addPath(pad);
  ctx.strokePath();
}

function ringAfbeelding(percentage, kleur, grootte, dikte) {
  const ctx = new DrawContext();
  ctx.size = new Size(grootte, grootte);
  ctx.opaque = false;
  ctx.respectScreenScale = true;

  const midden = new Point(grootte / 2, grootte / 2);
  const straal = grootte / 2 - dikte / 2;
  const start = -Math.PI / 2;
  const eind = start + 2 * Math.PI * (Math.max(0, Math.min(100, percentage)) / 100);

  ctx.setLineWidth(dikte);
  ctx.setLineJoin(1);
  ctx.setStrokeColor(KLEUR.achtergrondring);
  boogpunten(ctx, midden, straal, start, start + 2 * Math.PI);

  if (percentage > 0) {
    ctx.setStrokeColor(kleur);
    boogpunten(ctx, midden, straal, start, eind);
  }

  ctx.setFont(Font.boldSystemFont(grootte * 0.26));
  ctx.setTextColor(KLEUR.tekst);
  ctx.setTextAlignedCenter();
  ctx.drawTextInRect(
    String(Math.round(percentage)) + "%",
    new Rect(0, grootte / 2 - grootte * 0.16, grootte, grootte * 0.32)
  );

  return ctx.getImage();
}

// --------------------------------------------------------------------- //
//  Layouts
// --------------------------------------------------------------------- //

function layoutRingen(w, m) {
  const rij = w.addStack();
  rij.layoutHorizontally();
  rij.centerAlignContent();

  const items = [
    { label: "Belasting", waarde: m.belasting, kleur: KLEUR.belasting },
    { label: "Herstel", waarde: m.herstel, kleur: KLEUR.herstel },
    { label: "Slaap", waarde: m.slaap, kleur: KLEUR.slaap },
  ];

  items.forEach((item, i) => {
    const kolom = rij.addStack();
    kolom.layoutVertically();
    kolom.centerAlignContent();
    const afbeelding = kolom.addImage(ringAfbeelding(item.waarde, item.kleur, 74, 8));
    afbeelding.imageSize = new Size(74, 74);
    kolom.addSpacer(6);
    const label = kolom.addText(item.label);
    label.font = Font.systemFont(12);
    label.textColor = KLEUR.zacht;
    label.centerAlignText();
    if (i < items.length - 1) rij.addSpacer(14);
  });
}

function regel(stapel, label, waarde) {
  const rij = stapel.addStack();
  rij.centerAlignContent();
  const l = rij.addText(label);
  l.font = Font.systemFont(12);
  l.textColor = KLEUR.zacht;
  rij.addSpacer();
  const w = rij.addText(String(waarde));
  w.font = Font.semiboldSystemFont(14);
  w.textColor = KLEUR.tekst;
}

function layoutCompact(w, m, d) {
  const kop = w.addStack();
  kop.centerAlignContent();
  const afbeelding = kop.addImage(ringAfbeelding(m.herstel, KLEUR.herstel, 64, 8));
  afbeelding.imageSize = new Size(64, 64);
  kop.addSpacer(10);
  const tekstKolom = kop.addStack();
  tekstKolom.layoutVertically();
  const oordeel = tekstKolom.addText(NIVEAU[d.gereedheid.niveau] || "Herstel");
  oordeel.font = Font.semiboldSystemFont(15);
  const sub = tekstKolom.addText("gereedheid vandaag");
  sub.font = Font.systemFont(11);
  sub.textColor = KLEUR.zacht;

  w.addSpacer(10);
  regel(w, "hartslag", (d.hartslag.nu ?? "–") + " bpm");
  regel(w, "rust", (d.hartslag.rust ?? "–") + " bpm");
  regel(w, "hrv", (d.hrv.nacht ?? "–") + " ms");
  regel(w, "body battery", d.body_battery.nu ?? "–");
  regel(w, "slaap", (d.slaap.uren ?? "–") + " uur");
}

function layoutCijfers(w, d) {
  regel(w, "gereedheid", d.gereedheid.score ?? "–");
  regel(w, "hartslag", (d.hartslag.nu ?? "–") + " bpm");
  regel(w, "rust", (d.hartslag.rust ?? "–") + " bpm");
  regel(w, "hrv", (d.hrv.nacht ?? "–") + " ms");
  regel(w, "body battery", d.body_battery.nu ?? "–");
  regel(w, "slaap", (d.slaap.uren ?? "–") + " uur");
}

function foutWidget(tekst) {
  const w = new ListWidget();
  w.backgroundColor = new Color("#ffffff");
  w.setPadding(14, 14, 14, 14);
  w.url = ADRES;
  const titel = w.addText("Coach");
  titel.font = Font.boldSystemFont(18);
  w.addSpacer(8);
  const regel = w.addText(tekst);
  regel.font = Font.systemFont(13);
  regel.textColor = KLEUR.fout;
  return w;
}

// --------------------------------------------------------------------- //
//  Opbouwen
// --------------------------------------------------------------------- //

let widget;
try {
  const d = await haalOp();
  const m = metrieken(d);

  widget = new ListWidget();
  widget.backgroundColor = new Color("#ffffff");
  widget.setPadding(16, 14, 12, 14);
  widget.url = ADRES;

  if (LAYOUT === "ringen") layoutRingen(widget, m);
  else if (LAYOUT === "compact") layoutCompact(widget, m, d);
  else layoutCijfers(widget, d);

  widget.addSpacer(8);
  const tijd = widget.addText("horloge " + (d.sync.laatste_synchronisatie || "").slice(11));
  tijd.font = Font.systemFont(9);
  tijd.textColor = new Color("#c3c6cc");
} catch (fout) {
  widget = foutWidget(String(fout.message || fout));
}

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  if (LAYOUT === "ringen") widget.presentSmall();
  else widget.presentMedium();
}
Script.complete();
