# Wideband Tunable Band-Stop Filter (2.4 / 5 GHz)

A compact, varactor-tunable **dual-notch band-stop filter** on microstrip, designed and simulated in Ansys HFSS (Student). Two meandered shunt stubs each create one notch, and a varactor at the end of each stub tunes it independently.

![Filter layout](images/layout_top_view.png)
<!-- PLACEHOLDER: top view with dimensions (Fig. 3.1 in the report) -->

## Key specs

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

## How the tuning works

Each stub ends in a lumped capacitor to ground, named `Varactor_D1` and `Varactor_D2` in the model.

- Stub 1 capacitance: `Cvar1 + Cp1`, where Cvar1 is swept from 0.72 to 1.12 pF (nominal 0.92 pF).
- Stub 2 capacitance: `Cvar2 + Cp2`, where Cvar2 is swept from 0.36 to 0.56 pF (nominal 0.46 pF).
- `Cp1 = 0.3664 pF` and `Cp2 = 0.046 pF` are fixed values that place the nominal notches on target.
- More capacitance moves the notch **down** in frequency.

![Tuning of notch 1](images/s21_vs_cvar1.png)
<!-- PLACEHOLDER: S21 vs Cvar1 sweep -->

![Tuning of notch 2](images/s21_vs_cvar2.png)
<!-- PLACEHOLDER: S21 vs Cvar2 sweep -->

## Results

![Nominal S-parameters](images/nominal_s_params.png)
<!-- PLACEHOLDER: nominal S11 and S21, 1–8 GHz -->

## Files

| File | Purpose |
|---|---|
| `WB_tunable_BSF_meander_v8.py` | Builds the full HFSS model, setup, sweeps and reports |
| `WB_tunable_BSF_meander_final_final_final.py` | Renames the stub-end boundaries to `Varactor_D1` / `Varactor_D2` |
| `HFSS_meander_final_final.aedt` | HFSS project file (older v5 revision) |
| `Course_Project_Report_Wideband_Tunable_Bandstop_Filter.docx` | Full project report |
| `WB_tunable_BSF_meander_IEEE_report.md` | IEEE-style report draft |

## How to run

1. Open Ansys Electronics Desktop (Student) and open or create a project.
2. Go to **Tools → Run Script** and pick `WB_tunable_BSF_meander_v8.py`. It builds the geometry, solves, centres the notches and runs both sweeps.
3. To label the varactors, run `WB_tunable_BSF_meander_final_final_final.py` **once** on the solved project.
4. Open the **Results** tree for the S-parameter plots.

## Simulation settings

- Solver: HFSS Hybrid Modal Network, Direct Solver, adaptive frequency 5 GHz
- Max ΔS 0.03, up to 8 passes, first-order basis
- Interpolating sweep 1–8 GHz, 701 points
- Lumped ports at x = ±4 mm, 50 Ω
- Radiation boundary with 3 mm air padding

## Limitations

- The varactors are ideal capacitors: no series resistance or inductance, no bias network.
- Two Cvar2 sweep points (0.36 pF and 0.41 pF) did not meet the adaptive convergence goal.
- Results are simulated only; nothing has been fabricated or measured.

## Tools

Ansys Electronics Desktop / HFSS Student 2025 R2.4, Python (IronPython script API)

## Author

Your Name – Institution – email@domain.com
