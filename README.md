# KlikAanKlikUit — Home Assistant integratie

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integratie voor de KlikAanKlikUit / Trust ICS-2000 hub, met
UI-configuratie, apparaten-per-apparaat in de apparatenlijst, en status-sync
uit de ICS2000-cloud.

## Installatie via HACS (custom repository)

1. HACS openen → rechtsboven de drie puntjes → **Aangepaste repositories**.
2. URL: `https://github.com/Otte-S/KlikAanKlikUit-HomeAssistant`, type **Integratie**.
3. Toevoegen, daarna in HACS zoeken op **KlikAanKlikUit ICS2000** en downloaden.
4. Home Assistant herstarten.
5. **Instellingen → Apparaten & Diensten → Integratie toevoegen → ICS2000**
   en MAC, e-mail en wachtwoord invullen.

> Er is geen YAML-config meer. Een oude `light: - platform: ics2000` regel uit
> `configuration.yaml` moet je verwijderen; die wordt niet geïmporteerd.

## Migratie vanaf de oude `ics2000`-integratie

Deze integratie gebruikt het domein **`klikaanklikuit`**, niet `ics2000`. Dat is
bewust: zo botst hij niet met de originele integratie en heb je geen twee items
met dezelfde naam. Gevolg is wel dat dit een volledig nieuwe integratie is:

- De oude `ics2000`-integratie/YAML eerst verwijderen.
- Entiteiten komen onder nieuwe ID's (`light.<naam>` via domein `klikaanklikuit`);
  eventuele oude `ics2000.*`-verwijzingen in automatiseringen/dashboards moet je
  handmatig aanpassen.
- De hardware-modelnaam **ICS-2000** blijft als modelveld op het hub-apparaat
  staan — dat is de fysieke hub, los van de integratienaam.

## Wat je krijgt

- **Elk KAKU-apparaat als apparaat** in HA (lampen, dimmers, sensoren), netjes
  onder de ICS2000-hub gehangen via `via_device`, elk met eigen entiteiten.
- **UI config flow** + **opties** (aantal pogingen, pauze, poll-interval) —
  aanpasbaar zonder herinstallatie.
- **Status-sync** uit de ICS2000-cloud (standaard elke 30s), zodat wijzigingen
  via de Trust-app of Zigbee-apparaten ook in HA verschijnen.
- **Temperatuur/vochtigheid-sensoren** voor Zigbee-sensoren.
- **Diagnostische "Raw status"-sensor** voor onbekende apparaten (bv. een
  deurbel) + **Diagnostics-download** om die ruwe waarden te lezen.

## Belangrijke beperking

De statusfeedback komt uit de ICS2000-**cloud**, niet live van het apparaat.

Hoe dit werkt in deze integratie:
- **Besturen (aan/uit/dimmen): lokaal** via UDP zodra het hub-IP bekend is,
  anders valt het automatisch terug op de cloud. Vul eventueel het lokale IP
  van de hub in bij de opties om lokaal te forceren (handig bij VLANs).
- **Uitlezen/ontvangen: cloud**, want de hardware/library heeft geen enkele
  lokale status-methode (ook niet voor Zigbee). Instelbaar poll-interval
  (min. 5s) — lager voor snellere sensoren/automatiseringen, ten koste van
  meer cloudverkeer.
- Omdat een lokaal commando buiten de cloud omgaat, kan de cloud-status daar
  even op achterlopen. De integratie toont daarom direct na een commando een
  optimistische status en laat de cloud het daarna overnemen (die vangt ook
  wijzigingen via de Trust-app op).

Een klassieke 433MHz KAKU-afstandsbediening die rechtstreeks naar een ontvanger
zendt (buiten de hub om) blijft onzichtbaar — dat bereikt de cloud niet.
## HACS-publicatie (voor de repo-eigenaar)

Voor herkenning door HACS moet de repo: publiek zijn, een GitHub-**description**
en **topics** hebben, en minstens één gepubliceerde **release** (niet enkel een
tag). `hacs.json` staat in de root, `manifest.json` bevat `version`. De
`Validate`-workflow draait HACS- en hassfest-validatie bij elke push.
