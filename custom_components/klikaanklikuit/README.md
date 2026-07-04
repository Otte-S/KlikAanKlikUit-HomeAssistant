# KlikAanKlikUit — Home Assistant integratie (v2)

Volledige herschrijving van de oorspronkelijke `light.py`-only integratie.

## Wat is er anders

- **UI config flow** in plaats van YAML. Bestaande YAML-config (`light: platform: ics2000`)
  moet je verwijderen en opnieuw instellen via Instellingen > Apparaten & Diensten >
  Integratie toevoegen > ICS2000. Er is geen automatische YAML-import gebouwd.
- **Two-way state sync** via een `DataUpdateCoordinator` die iedere `scan_interval`
  seconden (standaard 30, instelbaar via Opties) `hub.get_device_status()` per
  apparaat pollt. Wijzigingen via de Trust-app of Zigbee-apparaten komen zo in HA
  terecht.
- **Sensoren** voor temperatuur/vochtigheid (Zigbee-sensoren, `device_type=46`).
- **Diagnostische "Raw status"-sensor** voor elk apparaat dat de library niet
  herkent (alles buiten de bekende `DeviceType`s). Zie hieronder voor de deurbel.
- **Diagnostics-download** (Instellingen > Apparaten & Diensten > ICS2000 > … >
  Diagnostics downloaden) geeft een volledige JSON-dump van alle apparaten + raw
  status, met wachtwoord/mail/mac geredacteerd.
- **Opties-flow** voor `tries`, `sleep` en `scan_interval` zonder herinstallatie.

## Belangrijke beperking: dit is geen live two-way

`get_device_status()` haalt de laatst bekende status op uit de ICS2000-cloud
(`trustsmartcloud2.com`). Dat werkt voor alles wat via de hub/Trust-app/Zigbee
loopt. Een **klassieke 433MHz KAKU-afstandsbediening of sensor die rechtstreeks
naar een ontvanger zendt, buiten de ICS2000-hub om, wordt nooit zichtbaar** -
dat verkeer bereikt de cloud niet. Dit is een hardware/protocol-beperking, geen
softwareprobleem. Polling elke 30s is bovendien geen instant push; verwacht een
paar seconden tot een halve minuut vertraging.

## De deurbel

De library kent geen `DeviceType` voor een deurbel/PIR/contactsensor. Twee
scenario's:

1. **Staat als apparaat in de Trust-app** → hij komt terug via `pull_devices()`
   als generieke `Device`, en verschijnt in deze integratie als een
   `sensor.<naam>_raw_status` entiteit met de ruwe function-array. Druk op de
   bel, kijk wat er verandert in die sensor of in de diagnostics-dump, en dat
   function-index is wat een eventuele toekomstige `binary_sensor` voor de
   deurbel zou moeten uitlezen. Dat is nog niet automatisch gebouwd omdat het
   function-index per devicetype verschilt en ik geen echte deurbel-data heb
   om tegen te testen.
2. **Los 433MHz zender/ontvanger-paartje, niet gekoppeld aan de ICS2000** →
   dan bestaat het apparaat niet voor de hub en is dit met deze library
   principieel niet te bouwen, ook niet met meer code.

## Dim-niveau: onopgeloste inconsistentie in de brondata

`light.py` rekent HA-brightness (0-255) om naar een KAKU-dim-niveau door door
17 te delen (niveau 1-15), zoals de oorspronkelijke code deed. De
`ics2000_python`-library zelf zegt in `Hub.dim()` dat het bereik 1-10 is. Deze
twee kloppen niet met elkaar en geen van beide is hier tegen een fysiek
apparaat geverifieerd. Als dimmen op vreemde punten vol/leeg lijkt te lopen,
is dit de eerste plek om te checken.

## Niet gebouwd (bewust)

- Geen YAML-import/migratie.
- Geen `cover`-entiteiten voor `OPEN_CLOSE`-devices - de library zelf mapt dat
  type nu al naar de `Light`-klasse, dus vanuit deze integratie is zo'n
  apparaat niet te onderscheiden van een gewone lamp. Dat zou een aanpassing
  in `ics2000_python` zelf vereisen, niet alleen hier.
- Geen automatische reactie op de deurbel (automatisering "als X dan Y") - dat
  bouw je zelf in HA op basis van de raw-status-sensor zodra bekend is welke
  index verandert.
