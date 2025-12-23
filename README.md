# TRELLIS 3D Web Demo + GLB→STEP Converter

Dit project bundelt de Microsoft **TRELLIS** 3D generatiemodellen in één gebruiksvriendelijke webinterface, inclusief:

- **Text → 3D**: genereer 3D-assets vanuit een tekstprompt (TRELLIS-text).
- **Image → 3D**: genereer 3D-assets vanuit één of meerdere afbeeldingen (TRELLIS-image).
- **GLB → STEP**: converteer een bestaand `.glb` 3D-bestand naar een STEP-bestand voor CAD-workflows.

De volledige webapp draait in een **GPU‑enabled Docker container** en is gebouwd met **Gradio**.

> Let op: de onderliggende TRELLIS code en modellen komen uit de officiële Microsoft repository. Zie de map `TRELLIS/` en de bijbehorende README voor alle modeldetails, paper en licentie.

---

## 1. Functionaliteiten

### 1.1 Text → 3D
- Genereer een 3D-object vanuit een korte tekstbeschrijving.
- Gebruikt intern de `TrellisTextTo3DPipeline` (`microsoft/TRELLIS-text-xlarge`).
- Presets voor **Fast / Balanced / High Quality** die automatisch stappen & guidance aanpassen.
- Resultaat:
  - Een **preview‑video** van het 3D-object.
  - Automatisch geëxporteerde **GLB** die je kunt downloaden.

### 1.2 Image → 3D
- Upload één afbeelding of een set van meerdere beelden (multi‑view).
- Gebruikt de `TrellisImageTo3DPipeline` (`microsoft/TRELLIS-image-large`).
- Ondersteunt:
  - Seed + randomize‑seed voor reproduceerbare resultaten.
  - Presets (Fast / Balanced / High Quality).
  - Keuze van multi‑image algoritme: `stochastic` of `multidiffusion`.
- Resultaat:
  - **Video** van het gegenereerde 3D‑object.
  - Downloadbare **GLB** en **STL** (mesh‑export).

### 1.3 GLB → STEP (CAD)
- Upload een `.glb` bestand **of** kies "Use Latest Generated GLB" om de laatste gegenereerde GLB uit de sessie te gebruiken.
- De conversie gebeurt via [`glb_to_step.py`]:
  - Probeert een STEP‑bestand te maken op basis van een triangulated mesh.
  - Maakt altijd een **STL** als tussenstap, zodat je bij falende STEP‑conversie toch een bruikbaar bestand hebt.
  - Probeert de mesh eerst te repareren (gaten vullen, normals fixen, kleine componenten verwijderen).
  - Maakt gebruik van **pythonocc-core** of – als dat niet beschikbaar is – een **FreeCAD** fallback (headless conversie).

> Belangrijk: het omzetten van willekeurige meshes naar geldige CAD‑solids is niet altijd perfect. Voor complexe of niet‑manifold modellen kan conversie mislukken of vereisen dat je de STL eerst repareert in een CAD‑pakket.

---

## 2. Architectuur

Belangrijke bestanden in deze repo:

- `app_combined.py`  
  Eén Gradio app met drie tabs: **Text → 3D**, **Image → 3D** en **GLB → STEP**. Hergebruikt de bestaande `app_text.py` en `app.py` uit de TRELLIS repo om duplicatie van logica te vermijden.

- `glb_to_step.py`  
  CLI + Python functie `glb_to_step(input.glb, output.step)` die GLB/GLTF naar STEP converteert met een STL‑fallback.

- `glb_to_step_app.py`  
  Kleine Gradio app die enkel GLB → STEP aanbiedt op een aparte poort (optioneel te gebruiken naast de hoofdapp).

- `Dockerfile`  
  Bouwt een **CUDA‑enabled** container, installeert alle benodigde 3D‑ en render‑extensies (TRELLIS setup, kaolin, xformers, spconv, nvdiffrast, diff‑gaussian‑rasterization, FreeCAD, …) en stelt `app_combined.py` in als entrypoint.

- `docker-compose.yml`  
  Start de container met GPU‑toegang, mount de huidige projectmap op `/app` en publiceert poort `7860`.

- `TRELLIS/`  
  Gekloonde / ingesloten officiële TRELLIS broncode van Microsoft. Gebruik deze map en de officiële README voor diepere technische details over het model, dataset en training.

---

## 3. Vereisten

### 3.1 Hardware
- NVIDIA GPU met voldoende VRAM (minimaal ~16 GB aanbevolen voor comfortabele generatie).
- NVIDIA drivers + **nvidia‑container‑toolkit** geïnstalleerd op de host, zodat Docker GPU‑toegang heeft.

### 3.2 Software
- Docker
- Docker Compose (v2 of v1, zolang `docker-compose` beschikbaar is)
- Werkend internet tijdens de **eerste build/run** voor het downloaden van modellen & dependencies.

---

## 4. Snelstart (met Docker)

1. **Repo klaarzetten**
   ```bash
   git clone <dit-project>
   cd AI-Edge-2025
   ```

2. **Container bouwen**  
   (dit kan even duren i.v.m. compilatie van CUDA‑extensies en het binnenhalen van modellen)
   ```bash
   docker-compose build
   ```

3. **App starten**
   ```bash
   docker-compose up
   ```

4. **Webinterface openen**
   - Ga in de browser naar: http://localhost:7860
   - Je ziet drie tabs: **Text → 3D**, **Image → 3D**, **GLB → STEP**.

5. **App stoppen**
   - In de terminal waar `docker-compose up` draait: `Ctrl + C`
   - Eventueel containers opruimen:
     ```bash
     docker-compose down
     ```

---

## 5. Gebruik in de UI

### 5.1 Text → 3D
1. Ga naar de tab **Text → 3D**.
2. Vul een tekstprompt in (bijv. "a red chair").
3. Kies desgewenst een preset (Fast / Balanced / High Quality):
   - **Fast**: minder stappen, snellere preview, minder detail.
   - **High Quality**: meer stappen en sterkere guidance, hogere kwaliteit (maar trager).
4. Laat **Randomize Seed** aan voor variatie, of zet het uit en kies zelf een seed.
5. Klik op **Generate from text**.
6. Wacht tot de video verschijnt en download daarna de GLB via het downloadcomponent.

### 5.2 Image → 3D
1. Ga naar **Image → 3D**.
2. Upload één enkele afbeelding of meerdere (bijv. verschillende hoeken van hetzelfde object).
3. Stel seed / presets / multi‑image algoritme in naar wens.
4. Klik op **Generate from image**.
5. Download na het renderen de GLB en/of STL.

### 5.3 GLB → STEP
1. Ga naar **GLB → STEP**.
2. Kies één van de opties:
   - Upload een `.glb` bestand via het uploadveld.
   - Of klik **Use Latest Generated GLB** om automatisch de laatst gegenereerde GLB uit je sessie te pakken.
3. Klik op **Convert to STEP**.
4. Download het resultaat:
   - Als de STEP‑conversie lukt: een `.step` bestand.
   - Als conversie faalt: een `.stl` fallback (met duidelijke foutmelding in de statusbox).

---

## 6. Troubleshooting

- **Geen GPU zichtbaar in de container**  
  Controleer dat je `nvidia-smi` op de host kunt draaien en dat **nvidia‑container‑toolkit** correct is geïnstalleerd. De `docker-compose.yml` verwacht `gpus: all` ondersteuning.

- **Out-of-memory / CUDA errors**  
  Probeer een kleinere preset (**Fast**), of verlaag het aantal sampling steps / guidance sterkte.

- **STEP conversie faalt**  
  - Download de aangeboden **STL** en repareer deze in een CAD‑tool (FreeCAD, Fusion 360, SolidWorks, ...).
  - Controleer of FreeCAD / pythonocc-core in de container aanwezig zijn als je direct STEP wilt genereren.

- **Lange buildtijden**  
  De eerste `docker-compose build` installeert en compileert een aantal zware CUDA‑extensies. Volgende builds zijn meestal veel sneller.

---

## 7. Referenties

- Officiële TRELLIS repository (code, paper, dataset, modellen):
  - https://github.com/microsoft/TRELLIS
- TRELLIS documentatie in deze repo:
  - Zie `TRELLIS/README.md`, `TRELLIS/DATASET.md`, enz.

Deze README beschrijft uitsluitend de integratie‑laag (webapp, Docker, GLB→STEP). Voor onderzoeksideeën, modelarchitecturen en trainingsdetails, raadpleeg vooral de officiële TRELLIS documentatie.
