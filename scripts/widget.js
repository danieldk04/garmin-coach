// Widget voor je beginscherm. Werkt met de gratis app Scriptable.
// Zet hieronder je eigen adres en toegangscode, plak het script in Scriptable
// en kies het daarna als widget op je beginscherm.

const ADRES = "https://VUL-JE-ADRES-IN";
const CODE = "VUL-JE-CODE-IN";

const NIVEAU = { READY: "Fris", MODERATE: "Redelijk", LOW: "Laag",
                 VERY_LOW: "Erg laag", HIGH: "Goed", PRIME: "Topvorm" };

function kleur(score) {
  if (score == null) return new Color("#8a8f98");
  if (score >= 75) return new Color("#33c46a");
  if (score >= 50) return new Color("#ff9a3c");
  return new Color("#d9455f");
}

function regel(stapel, label, waarde, tint) {
  const rij = stapel.addStack();
  rij.centerAlignContent();
  const l = rij.addText(label);
  l.font = Font.systemFont(12);
  l.textColor = new Color("#8a8f98");
  rij.addSpacer();
  const w = rij.addText(String(waarde));
  w.font = Font.semiboldSystemFont(14);
  w.textColor = tint || new Color("#1c1e21");
}

const verzoek = new Request(ADRES + "/api/dashboard");
verzoek.headers = { "X-Toegang": CODE };
const d = await verzoek.loadJSON();

const w = new ListWidget();
w.backgroundColor = new Color("#ffffff");
w.setPadding(14, 14, 14, 14);
w.url = ADRES;

const kop = w.addStack();
kop.centerAlignContent();
const score = kop.addText(String(d.gereedheid.score ?? "?"));
score.font = Font.boldSystemFont(34);
score.textColor = kleur(d.gereedheid.score);
kop.addSpacer(8);
const oordeel = kop.addText(NIVEAU[d.gereedheid.niveau] || "");
oordeel.font = Font.mediumSystemFont(14);
oordeel.textColor = new Color("#8a8f98");

w.addSpacer(8);
regel(w, "hartslag", (d.hartslag.nu ?? "–") + " bpm");
regel(w, "rust", (d.hartslag.rust ?? "–") + " bpm");
regel(w, "hrv", (d.hrv.nacht ?? "–") + " ms");
regel(w, "body battery", d.body_battery.nu ?? "–");
regel(w, "slaap", (d.slaap.uren ?? "–") + " uur");

w.addSpacer(4);
const tijd = w.addText("horloge " + (d.sync.laatste_synchronisatie || "").slice(11));
tijd.font = Font.systemFont(10);
tijd.textColor = new Color("#b0b4bb");

if (config.runsInWidget) Script.setWidget(w);
else w.presentMedium();
Script.complete();
