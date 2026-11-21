# Wideband Tunable Band-Stop Filter (2.4 / 5 GHz)

A compact, varactor-tunable **dual-notch band-stop filter** on microstrip, designed and simulated in Ansys HFSS (Student). Two meandered shunt stubs each create one notch, and a varactor at the end of each stub tunes it independently.

---

## Key Specs

| Item | Value |
|---|---|
| Notch 1 / Notch 2 (nominal) | 2.41 GHz (−27.2 dB) / 5.00 GHz (−31.4 dB) |
| Substrate | εr = 10.2, tan δ = 0.0022, h = 0.635 mm (RO3010-like) |
| Board size | 8.0 × 4.8 mm |
| Feed line | 8.0 × 0.58 mm, ≈ 50 Ω |
| Stub trace / gap | 0.12 mm / 0.10 mm |
| Stub footprint | 1.32 × 3.10 mm (excluding feed) |
| Stub 1 (2.4 GHz) | 7 segments, centreline ≈ 5.90 mm |
| Stub 2 (5 GHz) | 6 segments, centreline ≈ 3.29 mm |
| Mid-band (3.5 GHz) | S21 = −0.5 dB, S11 = −17.5 dB |
| Simulated band | 1–8 GHz, 701 points |

---

## Filter Layout

> 3D isometric view of the microstrip board with radiation boundary box, showing the feed line and two meandered shunt stubs (Ansys HFSS 2025 R2.4 Student).

<img src="final screenshots/Screenshot 2026-10-27 232931.png" alt="3D isometric view of the filter layout" width="800"/>

---

> Top-down (XY-plane) view of the copper layer. The upper stub tunes the 5 GHz notch; the lower stub tunes the 2.4 GHz notch.

<img src="final screenshots/Screenshot 2026-10-27 233020.png" alt="Top-down layout view showing both meandered stubs" width="600"/>

---

## Simulation Results

### Nominal S-Parameters (Cvar1 = 0.92 pF, Cvar2 = 0.46 pF)

> Red = S11 (return loss), Green = S21 (insertion loss). Two clear notches appear at ≈ 2.4 GHz (−27.2 dB) and ≈ 5.0 GHz (−31.4 dB). Mid-band S21 stays near 0 dB.

<img src="final screenshots/Screenshot 2026-10-27 233059.png" alt="Nominal S11 and S21 — dual notches at 2.4 GHz and 5 GHz" width="900"/>

---

### Notch Tuning

#### Cvar1 Sweep — 2.4 GHz Notch (Cvar2 fixed at 0.46 pF)

> Cvar1 swept from 0.72 pF (red, highest frequency) to 1.12 pF (cyan, lowest frequency) in 5 steps. The 2.4 GHz notch shifts while the 5 GHz notch remains stationary — confirming independent stub tuning.

<img src="final screenshots/Screenshot 2026-10-27 233118.png" alt="S21 vs Cvar1 sweep — 2.4 GHz notch tuning" width="900"/>

| Cvar1 | Approx. Notch 1 Frequency |
|-------|--------------------------|
| 0.72 pF | ~2.80 GHz |
| 0.82 pF | ~2.63 GHz |
| 0.92 pF | ~2.41 GHz (nominal) |
| 1.02 pF | ~2.28 GHz |
| 1.12 pF | ~2.18 GHz |

---

#### Cvar2 Sweep — 5 GHz Notch (Cvar1 fixed at 0.92 pF)

> Cvar2 swept from 0.36 pF (red, highest frequency) to 0.56 pF (cyan, lowest frequency) in 5 steps. The 5 GHz notch shifts across a wide range while Notch 1 at 2.4 GHz stays locked.

<img src="final screenshots/Screenshot 2026-10-27 233132.png" alt="S21 vs Cvar2 sweep — 5 GHz notch tuning" width="900"/>

| Cvar2 | Approx. Notch 2 Frequency |
|-------|--------------------------|
| 0.36 pF | ~5.30 GHz |
| 0.41 pF | ~5.15 GHz |
| 0.46 pF | ~5.00 GHz (nominal) |
| 0.51 pF | ~4.75 GHz |
| 0.56 pF | ~4.45 GHz |

---

## How the Tuning Works

Each stub ends in a lumped capacitor to ground, named `Varactor_D1` and `Varactor_D2` in the model.

- **Stub 1 capacitance:** `Cvar1 + Cp1`, where Cvar1 is swept from 0.72 to 1.12 pF (nominal 0.92 pF).
- **Stub 2 capacitance:** `Cvar2 + Cp2`, where Cvar2 is swept from 0.36 to 0.56 pF (nominal 0.46 pF).
- `Cp1 = 0.3664 pF` and `Cp2 = 0.046 pF` are fixed parasitics that place the nominal notches on target.
- **More capacitance → notch moves down in frequency.**

---

## Files

| File | Purpose |
|---|---|
| `HFSS_meander_final_final.aedt` | Main HFSS project file |
| `scripts/WB_tunable_BSF_meander_v8.py` | Builds full HFSS model, setup, sweeps and reports |
| `scripts/WB_tunable_BSF_meander_final_final_final.py` | Renames stub-end boundaries to `Varactor_D1` / `Varactor_D2` |
| `scripts/HFSS_meander_v5_build.py` | Earlier v5 build script |
| `scripts/meander_autotune.py` | Automated notch centering utility |
| `final screenshots/` | HFSS result screenshots (layout + S-parameter plots) |
| `previous versions/` | Archived `.aedt` design revisions |

---

## How to Run

1. Open **Ansys Electronics Desktop (Student)** and open or create a project.
2. Go to **Tools → Run Script** and select `scripts/WB_tunable_BSF_meander_v8.py`.  
   It builds the geometry, solves, centres the notches and runs both Cvar sweeps.
3. To label the varactors, run `scripts/WB_tunable_BSF_meander_final_final_final.py` **once** on the solved project.
4. Open the **Results** tree to view the S-parameter plots.

---

## Simulation Settings

| Setting | Value |
|---|---|
| Solver | HFSS Hybrid Modal Network, Direct Solver |
| Adaptive frequency | 5 GHz |
| Convergence | Max ΔS = 0.03, up to 8 passes, 1st-order basis |
| Frequency sweep | Interpolating, 1–8 GHz, 701 points |
| Ports | Lumped, x = ±4 mm, 50 Ω |
| Radiation boundary | 3 mm air padding on all sides |

---

## Limitations

- Varactors are ideal capacitors — no series resistance, inductance, or bias network modelled.
- Two Cvar2 sweep points (0.36 pF and 0.41 pF) did not meet the adaptive convergence goal.
- Results are simulation-only; no physical fabrication or measurement has been performed.

---

## Tools

Ansys Electronics Desktop / HFSS Student **2025 R2.4** · Python (IronPython script API)

---

## Author

Tanuj 
