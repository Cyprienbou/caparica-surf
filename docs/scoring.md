# Session scoring (v0, to be calibrated with session feedback)

Each candidate session (beach x time window) gets a score out of 100. Safety exclusions apply first.
Weights set by Cyp on 2026-10-20.

| Block | Points | Main inputs |
|---|---|---|
| Wave size and manageable power | 30 | Surfline surf height at the beach, surf-forecast height, **wave energy (kJ)** |
| Wind quality | 20 | Wind speed, gusts, wind state relative to the beach (offshore ... onshore) |
| Swell direction, period, organisation | 20 | Swell direction vs beach facing (236 deg), period, secondary swell / wind sea |
| Tide suitability | 13 | Tide height and movement; per-beach preference (unknown for now, learned from feedback) |
| Forecast agreement | 10 | Surfline vs surf-forecast vs Open-Meteo models |
| Weather | 5 | Sunshine (low cloud cover), rain, air temperature |
| Access, crowd, skill fit | 2 | Expected crowd, hazards, suitability for an intermediate surfer |

Weather rule (Cyp): never blocking. It acts as a tie-breaker between close windows: a slightly
weaker but sunny window should beat a slightly better window with clouds and light rain; clearly
better waves still win. Full weather points with cloud cover under 30 % and no rain.
Thunderstorms (weather codes 95-99) remain a safety exclusion.

85-100 excellent, 75-84 good, 60-74 possible with compromises, below 60 not recommended.
Scores are decision aids, not probabilities.

## Target profile

- Breaking waves 0.7 to 1.5 m, ideal 0.8 to 1.2 m.
- Light offshore or cross-offshore wind (0-10 km/h ideal, 10-15 conditional).
- Clean, organised, manageable waves. Avoid power, closeouts, strong onshore wind.

## Wave energy

Height alone hides power: 1.2 m at 8 s and 1.2 m at 14 s are very different waves.
Energy per metre of crest over one wavelength (deep water):

    E (kJ) = rho * g^2 * H^2 * T^2 / (16 pi) ~= 1.96 * H^2 * T^2

This is the same scale as the "energy (kJ)" column on surf-forecast.com (checked on 9 slots).
The collector adds `energy_swell_kj` and `energy_total_kj` to `data/latest/marine.csv`.

Starting bands for this surfer (hypothesis, offshore energy, to calibrate with feedback):

| Energy | Example | Reading | Effect on the 25 points |
|---|---|---|---|
| < 100 kJ | 0.7 m / 10 s | likely too weak or mushy | strong penalty |
| 100-400 kJ | 1.0 m / 10-12 s, 1.2 m / 11 s | target zone | full credit if height also fits |
| 400-650 kJ | 1.3 m / 12 s, 1.5 m / 11 s | punchy, conditional | partial credit |
| > 650 kJ | 1.5 m / 12 s+, 1.8 m / 12 s | too powerful for the goal | safety exclusion unless the beach forecast (Surfline) is clearly within 0.7-1.5 m |

Long periods (13 s and more) get an extra caution flag even inside the bands: sets are bigger and
more powerful than the average height suggests, and closeouts are more likely on these sandbars.

## Feedback loop (later)

A session log (date, beach, time, what was actually found, rating /10) will be used to adjust:
energy bands, per-beach offset between forecast and real height, tide preference per beach,
and the weight given to each source.

## On-demand crowd check (separate workflow, not part of the score)

When Cyp asks how many people are in the water, open the MEO Beachcam of that beach in his Chrome
and estimate the number of surfers visible: few / medium / crowded, with the rough count.
The live cams pan between views every 5-10 seconds (tip from Cyp): take 4-6 screenshots over
about 30-40 seconds and count per view, otherwise part of the beach is missed.
Use the free cams: Tarquinio, costa-da-caparica-cds (good, per Cyp), Praia Nova, Sao Joao.
The static CDS Norte / CDS Sul cams need Beachcam+.
Daylight only, approximate (surfers are small at that distance), and it describes now, not tomorrow.
