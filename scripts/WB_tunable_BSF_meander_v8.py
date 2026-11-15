# -*- coding: utf-8 -*-
"""
Wideband tunable dual-notch band-stop filter  -  Wi-Fi (2.4 / 5 GHz) + radar coexistence
Ansys Electronics Desktop (HFSS) build script  -  v8

HOW TO RUN
    AEDT  ->  Automation tab  ->  Run Script  ->  pick this file.
    (Works for IronPython 2.7 and CPython 3; no extra packages needed.)

WHAT IT BUILDS  (geometry copied 1:1 from HFSS_meander_v7.aedt)
    * 8 x 4.8 mm RO3010-like substrate (er 10.2, tand 0.0022, h 0.635 mm), PEC ground
    * 0.58 mm (50 ohm) microstrip feed, ports at x = -4 / +4 mm (lumped, 50 ohm)
    * Two heavily meandered stubs (0.12 mm trace / 0.10 mm gap), one each side of the feed.
      Each stub ends in a Lumped-RLC capacitor to ground:
          S1 (2.4 GHz notch):  C = Cvar1 + Cp1
          S2 (5   GHz notch):  C = Cvar2 + Cp2
      Cvar* = tuning (varactor) capacitance, Cp* = fixed "artificial" gap/pad capacitance.
    * Setup1: adaptive @ 5 GHz, interpolating sweep 1-8 GHz

WHAT IT PRODUCES  (no other sweeps are run)
    1. S11 and S21 (nominal)            -> paper Fig. (b)
    2. S21 (nominal)                    -> paper Fig. (a)
    3. S21 vs Cvar1 (2.4 GHz notch)     -> LIN 0.72 pF .. 1.12 pF, step 0.10 pF   (5 curves)
    4. S21 vs Cvar2 (5 GHz notch)       -> LIN 0.36 pF .. 0.56 pF, step 0.05 pF   (5 curves)

    Before the sweeps, ONE quick centering step reads the nominal notch frequencies and nudges
    Cp1 / Cp2 (not the sweep values) so the nominal notches sit on 2.40 GHz and 5.00 GHz.
"""
import os
import csv
import tempfile

try:
    import ScriptEnv
    ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
except ImportError:
    pass
oDesktop.RestoreWindow()

# ----------------------------------------------------------------------------------------
#  USER SETTINGS
# ----------------------------------------------------------------------------------------
PROJECT_NAME = "WB_Tunable_BSF_WiFi_Radar_v8"
DESIGN_NAME = "HFSS_meander_v8"

CVAR1_NOM, CVAR2_NOM = 0.92, 0.46            # pF  (centre of each sweep, same as v5/v7)
CP1_START, CP2_START = 0.157, 0.046          # pF  (v7 used 0.18 / 0.05; re-centred analytically)
CVAR1_SWEEP = "LIN 0.72pF 1.12pF 0.1pF"      # exactly as in your screenshot 1
CVAR2_SWEEP = "LIN 0.36pF 0.56pF 0.05pF"     # exactly as in your screenshot 2

TARGET_F1_GHZ, TARGET_F2_GHZ = 2.40, 5.00
AUTO_CENTER = True                           # one-step notch centering (max 2 extra nominal solves)
CENTER_TOL_GHZ = 0.015
FSTART, FSTOP, FPOINTS = 1.0, 8.0, 701       # GHz, 10 MHz steps

H_SUB = 0.635       # mm
T_CU = 0.035        # mm  (finite-conductivity copper, as in v7)

# stub segments:  name, x, y, width(x), height(y)   [mm, z = H_SUB]
S1_SEGS = [("S1_s0", -0.66, -0.06, 0.12, 0.61), ("S1_s1", -0.66, 0.43, 1.32, 0.12),
           ("S1_s2", 0.54, 0.43, 0.12, 1.32), ("S1_s3", -0.44, 1.63, 1.10, 0.12),
           ("S1_s4", -0.44, 0.65, 0.12, 1.10), ("S1_s5", -0.44, 0.65, 0.88, 0.12),
           ("S1_s6", 0.32, 0.65, 0.12, 0.64)]
S2_SEGS = [("S2_s0", -0.66, -0.55, 0.12, 0.61), ("S2_s1", -0.66, -0.55, 0.92, 0.12),
           ("S2_s2", 0.14, -1.35, 0.12, 0.92), ("S2_s3", -0.44, -1.35, 0.70, 0.12),
           ("S2_s4", -0.44, -1.35, 0.12, 0.70), ("S2_s5", -0.44, -0.77, 0.39, 0.12)]


# ----------------------------------------------------------------------------------------
#  helpers
# ----------------------------------------------------------------------------------------
def mm(v):
    return "%gmm" % v


def msg(text, sev=0):
    oDesktop.AddMessage("", "", sev, text)


def attrs(name, color="(143 175 143)", mat="vacuum", flags=""):
    return ["NAME:Attributes", "Name:=", name, "Flags:=", flags, "Color:=", color,
            "Transparency:=", 0, "PartCoordinateSystem:=", "Global", "UDMId:=", "",
            "MaterialValue:=", '"%s"' % mat, "SurfaceMaterialValue:=", '""',
            "SolveInside:=", True, "ShellElement:=", False, "ShellElementThickness:=", "0mm",
            "ReferenceTemperature:=", "20cel", "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False, "IsLightweight:=", False]


def rect(name, x, y, z, w, h, axis, color="(255 128 0)"):
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True, "XStart:=", mm(x), "YStart:=", mm(y),
         "ZStart:=", mm(z), "Width:=", mm(w), "Height:=", mm(h), "WhichAxis:=", axis],
        attrs(name, color))


def new_var(name, value):
    oDesign.ChangeProperty(["NAME:AllTabs", ["NAME:LocalVariableTab",
                            ["NAME:PropServers", "LocalVariables"],
                            ["NAME:NewProps", ["NAME:" + name, "PropType:=", "VariableProp",
                                               "UserDef:=", True, "Value:=", value]]]])


def set_var(name, value):
    oDesign.ChangeProperty(["NAME:AllTabs", ["NAME:LocalVariableTab",
                            ["NAME:PropServers", "LocalVariables"],
                            ["NAME:ChangedProps", ["NAME:" + name, "Value:=", value]]]])


def lumped_cap(name, sheet, start, end, expr):
    oBnd.AssignLumpedRLC(
        ["NAME:" + name, "Objects:=", [sheet],
         ["NAME:CurrentLine", "Start:=", [mm(v) for v in start], "End:=", [mm(v) for v in end]],
         "RLC Type:=", "Parallel", "UseResist:=", False, "Resistance:=", "0ohm",
         "UseInduct:=", False, "Inductance:=", "0nH", "UseCap:=", True, "Capacitance:=", expr])


def lumped_port(name, sheet, x):
    oBnd.AssignLumpedPort(
        ["NAME:" + name, "Objects:=", [sheet], "RenormalizeAllTerminals:=", True,
         "DoDeembed:=", False,
         ["NAME:Modes", ["NAME:Mode1", "ModeNum:=", 1, "UseIntLine:=", True,
                         ["NAME:IntLine", "Start:=", [mm(x), "0mm", "0mm"],
                          "End:=", [mm(x), "0mm", mm(H_SUB)]],
                         "AlignmentGroup:=", 0, "CharImp:=", "Zpi", "RenormImp:=", "50ohm"]],
         "ShowReporterFilter:=", False, "ReporterFilter:=", [True],
         "FullResistance:=", "50ohm", "FullReactance:=", "0ohm"])


# ----------------------------------------------------------------------------------------
#  project / design / variables / material
# ----------------------------------------------------------------------------------------
oProject = oDesktop.NewProject()
oDesign = None
for sol in ("HFSS Hybrid Modal Network", "HFSS Modal Network", "DrivenModal"):
    try:
        oProject.InsertDesign("HFSS", DESIGN_NAME, sol, "")
        oDesign = oProject.SetActiveDesign(DESIGN_NAME)
        if oDesign is not None:
            break
    except Exception:
        oDesign = None
if oDesign is None:
    raise RuntimeError("Could not insert HFSS design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

try:
    outdir = oDesktop.GetProjectDirectory()
except Exception:
    outdir = tempfile.gettempdir()
try:
    oProject.SaveAs(os.path.join(outdir, PROJECT_NAME + ".aedt"), True)
except Exception:
    msg("SaveAs failed - project stays unsaved until you save it manually.", 1)

new_var("Cvar1", "%gpF" % CVAR1_NOM)
new_var("Cvar2", "%gpF" % CVAR2_NOM)
new_var("Cp1", "%gpF" % CP1_START)
new_var("Cp2", "%gpF" % CP2_START)

oProject.GetDefinitionManager().AddMaterial(
    ["NAME:RO3010_like", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,
     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
     "permittivity:=", "10.2", "dielectric_loss_tangent:=", "0.0022"])

# ----------------------------------------------------------------------------------------
#  geometry
# ----------------------------------------------------------------------------------------
oEditor.CreateBox(["NAME:BoxParameters", "XPosition:=", "-4mm", "YPosition:=", "-2mm",
                   "ZPosition:=", "0mm", "XSize:=", "8mm", "YSize:=", "4.8mm",
                   "ZSize:=", mm(H_SUB)], attrs("Sub", "(0 128 0)", "RO3010_like"))
rect("GND", -4, -2, 0, 8, 4.8, "Z", "(143 175 143)")
rect("Feed", -4, -0.29, H_SUB, 8, 0.58, "Z")
for (n, x, y, w, h) in S1_SEGS + S2_SEGS:
    rect(n, x, y, H_SUB, w, h, "Z")
oEditor.Unite(["NAME:Selections", "Selections:=",
               ",".join(["Feed"] + [s[0] for s in S1_SEGS + S2_SEGS]),
               "NewPartsModelFlag:=", "Model"],
              ["NAME:UniteParameters", "KeepOriginals:=", False])

# capacitor sheets (vertical, ground -> stub end) and port sheets
rect("S1_capsheet", 0.32, 1.29, 0, H_SUB, 0.12, "Y")       # XZ-plane sheet at y = 1.29
rect("S2_capsheet", -0.05, -0.77, 0, 0.12, H_SUB, "X")     # YZ-plane sheet at x = -0.05
rect("port1_sheet", -4, -1.5, 0, 3, H_SUB, "X")
rect("port2_sheet", 4, -1.5, 0, 3, H_SUB, "X")

oEditor.CreateRegion(
    ["NAME:RegionParameters",
     "+XPaddingType:=", "Absolute Offset", "+XPadding:=", "3mm",
     "-XPaddingType:=", "Absolute Offset", "-XPadding:=", "3mm",
     "+YPaddingType:=", "Absolute Offset", "+YPadding:=", "3mm",
     "-YPaddingType:=", "Absolute Offset", "-YPadding:=", "3mm",
     "+ZPaddingType:=", "Absolute Offset", "+ZPadding:=", "3mm",
     "-ZPaddingType:=", "Absolute Offset", "-ZPadding:=", "3mm"],
    attrs("Region", "(143 175 143)", "vacuum", "Wireframe#"))

# ----------------------------------------------------------------------------------------
#  boundaries & excitations
# ----------------------------------------------------------------------------------------
oBnd = oDesign.GetModule("BoundarySetup")
oBnd.AssignPerfectE(["NAME:PerfE_GND", "Objects:=", ["GND"], "InfGroundPlane:=", False])
oBnd.AssignFiniteCond(["NAME:Cu_top", "Objects:=", ["Feed"], "UseMaterial:=", True,
                       "Material:=", "copper", "UseThickness:=", True,
                       "Thickness:=", mm(T_CU), "Roughness:=", "0um",
                       "InfGroundPlane:=", False, "IsTwoSided:=", False, "IsInternal:=", True])
lumped_cap("S1_C", "S1_capsheet", (0.38, 1.29, 0), (0.38, 1.29, H_SUB), "Cvar1+Cp1")
lumped_cap("S2_C", "S2_capsheet", (-0.05, -0.71, 0), (-0.05, -0.71, H_SUB), "Cvar2+Cp2")
lumped_port("port1", "port1_sheet", -4)
lumped_port("port2", "port2_sheet", 4)
oBnd.AssignRadiation(["NAME:Rad1", "Objects:=", ["Region"],
                      "IsFssReference:=", False, "IsForPML:=", False])

# ----------------------------------------------------------------------------------------
#  analysis setup (single adaptive solve + one interpolating sweep)
# ----------------------------------------------------------------------------------------
oSetup = oDesign.GetModule("AnalysisSetup")
oSetup.InsertSetup("HfssDriven",
                   ["NAME:Setup1", "SolveType:=", "Single", "Frequency:=", "5GHz",
                    "MaxDeltaS:=", 0.03, "MaximumPasses:=", 8, "MinimumPasses:=", 1,
                    "MinimumConvergedPasses:=", 1, "PercentRefinement:=", 30,
                    "IsEnabled:=", True, "BasisOrder:=", 1, "DoLambdaRefine:=", True,
                    "DoMaterialLambda:=", True, "SetLambdaTarget:=", False,
                    "PortAccuracy:=", 2, "DrivenSolverType:=", "Direct Solver"])
oSetup.InsertFrequencySweep("Setup1",
                            ["NAME:Sweep", "IsEnabled:=", True, "RangeType:=", "LinearCount",
                             "RangeStart:=", "%gGHz" % FSTART, "RangeEnd:=", "%gGHz" % FSTOP,
                             "RangeCount:=", FPOINTS, "Type:=", "Interpolating",
                             "SaveFields:=", False, "SaveRadFields:=", False,
                             "InterpTolerance:=", 0.5, "InterpMaxSolns:=", 250,
                             "InterpMinSolns:=", 0, "InterpMinSubranges:=", 1,
                             "InterpUseS:=", True, "InterpUsePortImped:=", True,
                             "InterpUsePropConst:=", True, "UseDerivativeConvergence:=", False,
                             "InterpDerivTolerance:=", 0.2, "UseFullBasis:=", True,
                             "EnforcePassivity:=", True, "PassivityErrorTolerance:=", 0.0001])

# ----------------------------------------------------------------------------------------
#  reports
# ----------------------------------------------------------------------------------------
oRep = oDesign.GetModule("ReportSetup")
SOLN = "Setup1 : Sweep"


def make_report(name, traces, variations):
    oRep.CreateReport(name, "Modal Solution Data", "Rectangular Plot", SOLN,
                      ["Domain:=", "Sweep"], variations,
                      ["X Component:=", "Freq", "Y Component:=", traces], [])
    try:        # cosmetic: y-axis -40..0 dB like the reference plots
        oRep.ChangeProperty(["NAME:AllTabs", ["NAME:Scaling",
                             ["NAME:PropServers", name + ":AxisY1"],
                             ["NAME:ChangedProps", ["NAME:Specify Min", "Value:=", True],
                              ["NAME:Min", "Value:=", "-40"], ["NAME:Specify Max", "Value:=", True],
                              ["NAME:Max", "Value:=", "0"], ["NAME:Specify Spacing", "Value:=", True],
                              ["NAME:Spacing", "Value:=", "5"]]]])
    except Exception:
        pass


def nominal_family():
    return ["Freq:=", ["All"], "Cvar1:=", ["%gpF" % CVAR1_NOM], "Cvar2:=", ["%gpF" % CVAR2_NOM]]


def read_nominal(report):
    """Export a nominal report to CSV and return (freq_GHz[], s21_dB[], s11_dB[])."""
    path = os.path.join(tempfile.gettempdir(), "wb_bsf_nominal.csv")
    try:
        oRep.ExportToFile(report, path)
    except Exception:
        oRep.ExportToFile(report, path, False)
    with open(path, "r") as fh:
        rows = [r for r in csv.reader(fh) if r]
    hdr = rows[0]
    scale = 1.0
    h0 = hdr[0].lower()
    if "[mhz]" in h0:
        scale = 1e-3
    elif "[hz]" in h0:
        scale = 1e-9
    c21 = [i for i, h in enumerate(hdr) if "port2,port1" in h.replace(" ", "")][0]
    c11 = [i for i, h in enumerate(hdr) if "port1,port1" in h.replace(" ", "")][0]
    fr, s21, s11 = [], [], []
    for r in rows[1:]:
        try:
            fr.append(float(r[0]) * scale)
            s21.append(float(r[c21]))
            s11.append(float(r[c11]))
        except (ValueError, IndexError):
            continue
    return fr, s21, s11


def notch(fr, s21, lo, hi):
    best = None
    for f, v in zip(fr, s21):
        if lo <= f <= hi and (best is None or v < best[1]):
            best = (f, v)
    return best


def at(fr, vals, f0):
    k = min(range(len(fr)), key=lambda i: abs(fr[i] - f0))
    return vals[k]


# ----------------------------------------------------------------------------------------
#  nominal solve  (+ optional one-step centering of the two notches)
# ----------------------------------------------------------------------------------------
msg("Solving nominal design ...")
oDesign.Analyze("Setup1")
make_report("S11 and S21 (nominal)", ["dB(S(port1,port1))", "dB(S(port2,port1))"],
            nominal_family())

if AUTO_CENTER:
    try:
        cp1, cp2 = CP1_START, CP2_START
        for it in range(2):
            fr, s21, s11 = read_nominal("S11 and S21 (nominal)")
            n1 = notch(fr, s21, 1.8, 3.3)
            n2 = notch(fr, s21, 4.0, 6.2)
            msg("centering pass %d: notch1 = %.3f GHz (%.1f dB), notch2 = %.3f GHz (%.1f dB)"
                % (it, n1[0], n1[1], n2[0], n2[1]))
            if abs(n1[0] - TARGET_F1_GHZ) < CENTER_TOL_GHZ and abs(n2[0] - TARGET_F2_GHZ) < CENTER_TOL_GHZ:
                break
            # f ~ 1/sqrt(C)  ->  C_new = C_old * (f_meas / f_target)^2
            c1_new = (CVAR1_NOM + cp1) * (n1[0] / TARGET_F1_GHZ) ** 2
            c2_new = (CVAR2_NOM + cp2) * (n2[0] / TARGET_F2_GHZ) ** 2
            cp1_new, cp2_new = c1_new - CVAR1_NOM, c2_new - CVAR2_NOM
            if not (0.0 <= cp1_new <= 0.5 and 0.0 <= cp2_new <= 0.3):
                msg("centering skipped: required Cp out of range (%.3f / %.3f pF)"
                    % (cp1_new, cp2_new), 1)
                break
            cp1, cp2 = cp1_new, cp2_new
            set_var("Cp1", "%.4fpF" % cp1)
            set_var("Cp2", "%.4fpF" % cp2)
            oDesign.Analyze("Setup1")
            try:
                oRep.UpdateAllReports()
            except Exception:
                pass
        msg("Final Cp1 = %.4f pF, Cp2 = %.4f pF" % (cp1, cp2))
    except Exception as e:
        msg("Auto-centering skipped (%s). Notches are at the analytic start values." % str(e), 1)

make_report("S21 (nominal)", ["dB(S(port2,port1))"], nominal_family())

# ----------------------------------------------------------------------------------------
#  the two parametric sweeps (exactly the ranges of the reference plots)
# ----------------------------------------------------------------------------------------
oOpt = oDesign.GetModule("Optimetrics")
for sw_name, var, data in (("Sweep_Cvar1", "Cvar1", CVAR1_SWEEP), ("Sweep_Cvar2", "Cvar2", CVAR2_SWEEP)):
    oOpt.InsertSetup("OptiParametric",
                     ["NAME:" + sw_name, "IsEnabled:=", True,
                      ["NAME:ProdOptiSetupDataV2", "SaveFields:=", False, "CopyMesh:=", False,
                       "SolveWithCopiedMeshOnly:=", True],
                      ["NAME:StartingPoint"], "Sim. Setups:=", ["Setup1"],
                      ["NAME:Sweeps", ["NAME:SweepDefinition", "Variable:=", var,
                                       "Data:=", data, "OffsetF1:=", False, "Synchronize:=", 0]],
                      ["NAME:Sweep Operations"], ["NAME:Goals"]])
msg("Solving parametric sweeps (5 + 5 points) ...")
oOpt.SolveSetup("Sweep_Cvar1")
oOpt.SolveSetup("Sweep_Cvar2")

make_report("S21 vs Cvar1 (2.4 GHz notch)", ["dB(S(port2,port1))"],
            ["Freq:=", ["All"], "Cvar1:=", ["All"], "Cvar2:=", ["%gpF" % CVAR2_NOM]])
make_report("S21 vs Cvar2 (5 GHz notch)", ["dB(S(port2,port1))"],
            ["Freq:=", ["All"], "Cvar1:=", ["%gpF" % CVAR1_NOM], "Cvar2:=", ["All"]])

# ----------------------------------------------------------------------------------------
#  summary
# ----------------------------------------------------------------------------------------
try:
    fr, s21, s11 = read_nominal("S11 and S21 (nominal)")
    n1, n2 = notch(fr, s21, 1.8, 3.3), notch(fr, s21, 4.0, 6.2)
    msg("NOMINAL: notch1 %.3f GHz (%.1f dB) | notch2 %.3f GHz (%.1f dB)" % (n1[0], n1[1], n2[0], n2[1]))
    msg("NOMINAL mid-band: S21 @3.0/3.5/4.0 GHz = %.1f / %.1f / %.1f dB ; S11 = %.1f / %.1f / %.1f dB"
        % (at(fr, s21, 3.0), at(fr, s21, 3.5), at(fr, s21, 4.0),
           at(fr, s11, 3.0), at(fr, s11, 3.5), at(fr, s11, 4.0)))
except Exception:
    pass
bx = [s[1] for s in S1_SEGS + S2_SEGS] + [s[1] + s[3] for s in S1_SEGS + S2_SEGS]
by = [s[2] for s in S1_SEGS + S2_SEGS] + [s[2] + s[4] for s in S1_SEGS + S2_SEGS]
msg("Stub footprint (excl. 8 mm feed): %.2f x %.2f mm" % (max(bx) - min(bx), max(by) - min(by)))
try:
    oProject.Save()
except Exception:
    pass
msg("v8 done - nominal Cvar1=%gpF Cvar2=%gpF" % (CVAR1_NOM, CVAR2_NOM))
