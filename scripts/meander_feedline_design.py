# -*- coding: utf-8 -*-
# meander_feedline_design.py
#
# Builds a NEW HFSS design (inside the open project) of the dual-band tunable bandstop
# filter with a ZIGZAG (meander) feed line, so the board is much shorter than the
# straight 60 mm version. Your existing design, reports and sweeps are not touched.
#
# HOW TO RUN (Ansys Electronics Desktop):
#   1. Open your project (any project; the script adds a design to it).
#   2. Tools > Run Script...  and pick this file.
#   3. Wait for "DONE" in the Message Manager, run HFSS > Validation Check, then Analyze Setup1.
# If the script stops with an error, the line before it in the Message Manager shows which
# step failed. Delete the new design and send me the message.
#
# WHAT THE ZIGZAG DOES
#   The straight line had three runs: port -> stub 1 = 15 mm, stub 1 -> stub 2 = 15 mm,
#   stub 2 -> port = 30 mm. Each run is folded into a zigzag with the SAME path length,
#   so the electrical length between the stubs is kept. The zigzag goes up (+y);
#   the stubs and the bias network hang down (-y), so they never touch.
#
# Edit the numbers in the PARAMETERS block, then run again (a new design is made each time).

import re
import math

try:
    import ScriptEnv
    ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
    oDesktop.RestoreWindow()
except ImportError:
    pass

# =============================================================== PARAMETERS (mm unless noted)
DESIGN_NAME = "HFSS_meander"

# zigzag shape
MEANDER_GAP = 2.0      # clear gap between neighbouring zigzag runs. Smaller = shorter board, more coupling
E_LEAD = 1.0           # straight lead before/after each zigzag (keep >= W50/2 + 0.1)
LAUNCH = 2.0           # straight launch at each port
NODE_LEN = 2.5         # straight piece where each stub joins the line
PATH_A = 15.0          # path length port1 -> stub 1 centre (same as the straight design)
PATH_B = 15.0          # stub 1 -> stub 2
PATH_C = 30.0          # stub 2 -> port2
RUNS_A = 2             # number of vertical runs per zigzag (must be even)
RUNS_B = 2
RUNS_C = 4
STRAIGHT_LENGTH = 60.0  # length of the old straight version, only used for the comparison printout

# electrical / stack-up (same as the working design)
SUB_H = 0.813
ER, TAND = 3.38, 0.0027
W50 = 1.85
WSTUB = 1.0
L_STUB1, L_STUB2 = 8.2, 2.0
GAP_SIZE, PAD_L = 0.2, 0.5
CVAR1, CVAR2 = "1.5pF", "0.75pF"
ADD_BIAS_NETWORK = True
MARGIN = 5.0           # substrate margin around the circuit
AIR_Y = 25.0           # air box margin in y (z margin is 37 mm, about a quarter wavelength at 2 GHz)
AIR_Z = 37.0

# =============================================================== geometry plan (pure python)
P = W50 + MEANDER_GAP  # centre-to-centre pitch of the zigzag runs


def fmt(x):
    s = ("%.4f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def meander(x, n, path):
    """Zigzag that starts and ends on the baseline y=0. Returns points and the end x."""
    if n % 2 != 0:
        raise ValueError("RUNS must be even")
    amp = (path - 2 * E_LEAD - (n - 1) * P) / float(n)
    if amp < 1.0:
        raise ValueError("zigzag amplitude %.2f mm is too small: use fewer runs or a longer path" % amp)
    pts = []
    x += E_LEAD
    pts.append((x, 0.0))
    for i in range(n):
        y = amp if i % 2 == 0 else 0.0
        pts.append((x, y))
        if i < n - 1:
            x += P
            pts.append((x, y))
    x += E_LEAD
    pts.append((x, 0.0))
    return pts, x, amp


def plan():
    pts = [(0.0, 0.0)]
    x = LAUNCH
    pts.append((x, 0.0))
    # section A
    mp, x, ampA = meander(x, RUNS_A, PATH_A - LAUNCH - NODE_LEN / 2.0)
    pts += mp
    node1 = x + NODE_LEN / 2.0
    x += NODE_LEN
    pts.append((x, 0.0))
    # section B
    mp, x, ampB = meander(x, RUNS_B, PATH_B - NODE_LEN)
    pts += mp
    node2 = x + NODE_LEN / 2.0
    x += NODE_LEN
    pts.append((x, 0.0))
    # section C
    mp, x, ampC = meander(x, RUNS_C, PATH_C - NODE_LEN / 2.0 - LAUNCH)
    pts += mp
    x += LAUNCH
    pts.append((x, 0.0))
    # merge collinear points
    clean = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - clean[-1][0]) < 1e-9 and abs(p[1] - clean[-1][1]) < 1e-9:
            continue
        clean.append(p)
    merged = [clean[0]]
    for i in range(1, len(clean) - 1):
        a, b, c = merged[-1], clean[i], clean[i + 1]
        same_h = abs(a[1] - b[1]) < 1e-9 and abs(b[1] - c[1]) < 1e-9
        same_v = abs(a[0] - b[0]) < 1e-9 and abs(b[0] - c[0]) < 1e-9
        if not (same_h or same_v):
            merged.append(b)
    merged.append(clean[-1])
    # rectangles (x0, x1, y0, y1); square overlap at every inner corner so the union is one piece
    rects = []
    h = W50 / 2.0
    n = len(merged) - 1
    for i in range(n):
        (xa, ya), (xb, yb) = merged[i], merged[i + 1]
        ext0 = h if i > 0 else 0.0
        ext1 = h if i < n - 1 else 0.0
        if abs(ya - yb) < 1e-9:           # horizontal
            s = 1.0 if xb > xa else -1.0
            xs, xe = xa - s * ext0, xb + s * ext1
            rects.append((min(xs, xe), max(xs, xe), ya - h, ya + h))
        else:                             # vertical
            s = 1.0 if yb > ya else -1.0
            ys, ye = ya - s * ext0, yb + s * ext1
            rects.append((xa - h, xa + h, min(ys, ye), max(ys, ye)))
    length = sum(abs(merged[i + 1][0] - merged[i][0]) + abs(merged[i + 1][1] - merged[i][1]) for i in range(n))
    return dict(rects=rects, node1=node1, node2=node2, x_end=x, amps=(ampA, ampB, ampC),
                top=max(p[1] for p in merged) + h, path=length)


PL = plan()
POS = {1: PL["node1"], 2: PL["node2"]}
X_END = PL["x_end"]

# lowest metal of the stub chains (bias network goes furthest down)
CHAIN_DEPTH = 4.1 + 0.2 + 0.0  # padb/gapb stack + dpad chain: bias chain ends 4.1 mm below the varactor pad
YA = {k: -W50 / 2.0 - (L_STUB1 if k == 1 else L_STUB2) - GAP_SIZE - PAD_L for k in (1, 2)}
Y_LOW = min(YA[1], YA[2]) - (4.1 if ADD_BIAS_NETWORK else 0.7)
Y_SUB0 = Y_LOW - MARGIN
Y_SUB1 = PL["top"] + MARGIN


# =============================================================== AEDT helpers
def log(msg):
    try:
        oDesktop.AddMessage("", "", 0, msg, "")
    except Exception:
        pass
    print(msg)


def attrs(name, color, transp, material, solve_inside):
    return ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
            "Transparency:=", transp, "PartCoordinateSystem:=", "Global", "UDMId:=", "",
            "MaterialValue:=", "\"%s\"" % material, "SurfaceMaterialValue:=", "\"\"",
            "SolveInside:=", solve_inside, "ShellElement:=", False,
            "ShellElementThickness:=", "0mm", "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False, "IsLightweight:=", False]


oProject = oDesktop.GetActiveProject()
log("Step 1: insert design %s" % DESIGN_NAME)
oDesign = oProject.InsertDesign("HFSS", DESIGN_NAME, "DrivenModal", "")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oBnd = oDesign.GetModule("BoundarySetup")
oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", "mm", "Rescale:=", False])

# ---- variables
log("Step 2: design variables")
VARS = [("sub_h", "%smm" % fmt(SUB_H)), ("w50", "%smm" % fmt(W50)), ("wstub", "%smm" % fmt(WSTUB)),
        ("l_stub1", "%smm" % fmt(L_STUB1)), ("l_stub2", "%smm" % fmt(L_STUB2)),
        ("pos1", "%smm" % fmt(POS[1])), ("pos2", "%smm" % fmt(POS[2])),
        ("gap_size", "%smm" % fmt(GAP_SIZE)), ("pad_l", "%smm" % fmt(PAD_L)),
        ("Cvar1", CVAR1), ("Cvar2", CVAR2)]
for nm, val in VARS:
    oDesign.ChangeProperty(
        ["NAME:AllTabs",
         ["NAME:LocalVariableTab", ["NAME:PropServers", "LocalVariables"],
          ["NAME:NewProps", ["NAME:" + nm, "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", val]]]])

# ---- material (already present if the project came from the earlier files)
try:
    oProject.GetDefinitionManager().AddMaterial(
        ["NAME:RO4003C_338", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,
         ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
         "permittivity:=", "%s" % ER, "dielectric_loss_tangent:=", "%s" % TAND])
except Exception:
    pass


def sheet(name, xs, ys, w, h, z="sub_h"):
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True, "XStart:=", xs, "YStart:=", ys,
         "ZStart:=", z, "Width:=", w, "Height:=", h, "WhichAxis:=", "Z"],
        attrs(name, "(230 230 230)", 0.8, "vacuum", True))


def via(name, xc, yc):
    oEditor.CreateCylinder(
        ["NAME:CylinderParameters", "XCenter:=", xc, "YCenter:=", yc, "ZCenter:=", "0mm",
         "Radius:=", "0.15mm", "Height:=", "sub_h", "WhichAxis:=", "Z", "NumSides:=", "0"],
        attrs(name, "(247 242 232)", 0.2, "pec", False))


def lumped(name, obj, x_mm, y_top_mm, y_bot_mm, R=None, L=None, C=None):
    z = "%.6fmm" % SUB_H
    oBnd.AssignLumpedRLC(
        ["NAME:" + name, "Objects:=", [obj],
         ["NAME:CurrentLine",
          "Start:=", ["%.6fmm" % x_mm, "%.6fmm" % y_top_mm, z],
          "End:=", ["%.6fmm" % x_mm, "%.6fmm" % y_bot_mm, z]],
         "RLC Type:=", "Serial",
         "UseResist:=", R is not None, "Resistance:=", R or "0ohm",
         "UseInduct:=", L is not None, "Inductance:=", L or "0nH",
         "UseCap:=", C is not None, "Capacitance:=", C or "0pF"])


# ---- substrate, ground, air box
log("Step 3: substrate, ground, air box")
oEditor.CreateBox(
    ["NAME:BoxParameters", "XPosition:=", "0mm", "YPosition:=", "%smm" % fmt(Y_SUB0), "ZPosition:=", "0mm",
     "XSize:=", "%smm" % fmt(X_END), "YSize:=", "%smm" % fmt(Y_SUB1 - Y_SUB0), "ZSize:=", "sub_h"],
    attrs("substrate", "(132 132 193)", 0.2, "RO4003C_338", True))
sheet("ground", "0mm", "%smm" % fmt(Y_SUB0 - 5), "%smm" % fmt(X_END), "%smm" % fmt(Y_SUB1 - Y_SUB0 + 10), z="0mm")
AX0, AX1 = Y_SUB0 - 5 - AIR_Y, Y_SUB1 + 5 + AIR_Y
oEditor.CreateBox(
    ["NAME:BoxParameters", "XPosition:=", "0mm", "YPosition:=", "%smm" % fmt(AX0), "ZPosition:=", "%smm" % fmt(-AIR_Z),
     "XSize:=", "%smm" % fmt(X_END), "YSize:=", "%smm" % fmt(AX1 - AX0), "ZSize:=", "sub_h+%smm" % fmt(2 * AIR_Z)],
    attrs("airbox", "(143 175 143)", 0.9, "vacuum", True))

# ---- zigzag feed line + stubs, united into one sheet
log("Step 4: zigzag feed line (%d pieces), path %.1f mm in %.1f mm" % (len(PL["rects"]), PL["path"], X_END))
names = []
for i, (x0, x1, y0, y1) in enumerate(PL["rects"]):
    nm = "feedline" if i == 0 else "seg%d" % i
    names.append(nm)
    sheet(nm, "%smm" % fmt(x0), "%smm" % fmt(y1), "%smm" % fmt(x1 - x0), "%smm" % fmt(y0 - y1))
for k in (1, 2):
    nm = "stub%d" % k
    names.append(nm)
    sheet(nm, "pos%d-wstub/2" % k, "-w50/2", "wstub", "-l_stub%d" % k)
oEditor.Unite(["NAME:Selections", "Selections:=", ",".join(names)],
              ["NAME:UniteParameters", "KeepOriginals:=", False])

# ---- varactor gap, pad, DC-block, bias network
log("Step 5: varactor gaps, pads and bias network")
metal = ["ground", "feedline"]
for k in (1, 2):
    p = "pos%d" % k
    y0 = "-w50/2-l_stub%d" % k
    ya = y0 + "-gap_size-pad_l"
    px = POS[k]
    ya_mm = YA[k]
    sheet("gap%d" % k, "%s-wstub/2" % p, y0, "wstub", "-gap_size")
    sheet("pad%d" % k, "%s-wstub/2" % p, y0 + "-gap_size", "wstub", "-pad_l")
    metal.append("pad%d" % k)
    lumped("Varactor%d" % k, "gap%d" % k, px, ya_mm + PAD_L + GAP_SIZE, ya_mm + PAD_L,
           R="0.6ohm", L="0.5nH", C="Cvar%d" % k)
    if not ADD_BIAS_NETWORK:
        via("via%d" % k, p, y0 + "-gap_size-pad_l/2")
        continue
    sheet("gapb%d" % k, "%s-wstub/2" % p, ya, "0.6mm", "-gap_size")
    sheet("padb%d" % k, "%s-wstub/2" % p, ya + "-gap_size", "0.6mm", "-pad_l")
    via("via%d" % k, "%s-0.2mm" % p, ya + "-gap_size-pad_l/2")
    sheet("btrace%d" % k, "%s+0.3mm" % p, ya, "0.2mm", "-2mm")
    sheet("gapr%d" % k, "%s+0.3mm" % p, ya + "-2mm", "0.2mm", "-0.4mm")
    sheet("bpad%d" % k, "%s-0.1mm" % p, ya + "-2.4mm", "1mm", "-1mm")
    sheet("gapd%d" % k, "%s-0.1mm" % p, ya + "-3.4mm", "1mm", "-0.2mm")
    sheet("dpad%d" % k, "%s-0.1mm" % p, ya + "-3.6mm", "1mm", "-0.5mm")
    via("viad%d" % k, "%s+0.4mm" % p, ya + "-3.6mm-0.25mm")
    metal += ["padb%d" % k, "btrace%d" % k, "bpad%d" % k, "dpad%d" % k]
    lumped("DCblock%d" % k, "gapb%d" % k, px - 0.2, ya_mm, ya_mm - GAP_SIZE, R="0.1ohm", C="100pF")
    lumped("BiasRes%d" % k, "gapr%d" % k, px + 0.4, ya_mm - 2.0, ya_mm - 2.4, R="10kohm")
    lumped("Decap%d" % k, "gapd%d" % k, px + 0.4, ya_mm - 3.4, ya_mm - 3.6, R="0.1ohm", C="100pF")

log("Step 6: perfect conductors")
oBnd.AssignPerfectE(["NAME:PEC_metal", "Objects:=", metal, "InfGroundPlane:=", False])

# ---- wave ports at both ends of the line
log("Step 7: wave ports")
for idx, xp in ((1, 0.0), (2, X_END)):
    sh = "portsheet%d" % idx
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True, "XStart:=", "%smm" % fmt(xp), "YStart:=", "-5mm",
         "ZStart:=", "0mm", "Width:=", "10mm", "Height:=", "8mm", "WhichAxis:=", "X"],
        attrs(sh, "(255 128 0)", 0.4, "vacuum", True))
    oBnd.AssignWavePort(
        ["NAME:port%d" % idx, "Objects:=", [sh], "NumModes:=", 1, "RenormalizeAllTerminals:=", True,
         "UseLineModeAlign:=", False, "DoDeembed:=", False,
         ["NAME:Modes", ["NAME:Mode1", "ModeNum:=", 1, "UseIntLine:=", True,
                         ["NAME:IntLine", "Start:=", ["%smm" % fmt(xp), "0mm", "0mm"],
                          "End:=", ["%smm" % fmt(xp), "0mm", "%smm" % fmt(SUB_H)]],
                         "AlignmentGroup:=", 0, "CharImp:=", "Zpi", "RenormImp:=", "50ohm"]],
         "ShowReporterFilter:=", False, "ReporterFilter:=", [True], "UseAnalyticAlignment:=", False])

# ---- radiation boundary on every air box face except the two port end faces
log("Step 8: radiation boundary")
rad = []
for f in oEditor.GetFaceIDs("airbox"):
    c = oEditor.GetFaceCenter(int(f))
    cx = float(str(c[0]).replace("mm", ""))
    if abs(cx - 0.0) < 1e-6 or abs(cx - X_END) < 1e-6:
        continue
    rad.append(int(f))
oBnd.AssignRadiation(["NAME:Rad1", "Faces:=", rad, "IsFssReference:=", False, "IsForPML:=", False])

# ---- mesh, setup, sweep
log("Step 9: mesh, setup, sweep")
try:
    oDesign.GetModule("MeshSetup").AssignLengthOp(
        ["NAME:Length1", "RefineInside:=", True, "Enabled:=", True,
         "Objects:=", ["gap1", "gap2", "pad1", "pad2"], "RestrictElem:=", False,
         "NumMaxElem:=", "1000", "RestrictLength:=", True, "MaxLength:=", "1.5mm"])
except Exception:
    log("mesh operation skipped")
oSetup = oDesign.GetModule("AnalysisSetup")
oSetup.InsertSetup("HfssDriven",
                   ["NAME:Setup1", "SolveType:=", "Single", "Frequency:=", "5.5GHz", "MaxDeltaS:=", 0.02,
                    "MaximumPasses:=", 15, "MinimumPasses:=", 1, "MinimumConvergedPasses:=", 1,
                    "PercentRefinement:=", 30, "IsEnabled:=", True, "BasisOrder:=", 1])
oSetup.InsertFrequencySweep("Setup1",
                            ["NAME:Sweep", "IsEnabled:=", True, "RangeType:=", "LinearCount",
                             "RangeStart:=", "1GHz", "RangeEnd:=", "8GHz", "RangeCount:=", 150,
                             "Type:=", "Interpolating", "SaveFields:=", False, "InterpTolerance:=", 0.5,
                             "InterpMaxSolns:=", 250, "InterpMinSolns:=", 0, "InterpMinSubranges:=", 1])

# ---- parametric sweeps (non fatal if the format differs in your version)
try:
    opt = oDesign.GetModule("Optimetrics")
    for k, rng in ((1, "LIN 1.2pF 1.8pF 0.1pF"), (2, "LIN 0.5pF 0.9pF 0.1pF")):
        opt.InsertSetup("OptiParametric",
                        ["NAME:ParametricSetup%d" % k, "IsEnabled:=", True,
                         ["NAME:ProdOptiSetupDataV2", "SaveFields:=", False, "CopyMesh:=", True,
                          "SolveWithCopiedMeshOnly:=", True],
                         ["NAME:StartingPoint"], "Sim. Setups:=", ["Setup1"],
                         ["NAME:Sweeps", ["NAME:SweepDefinition", "Variable:=", "Cvar%d" % k,
                                          "Data:=", rng, "OffsetF1:=", False, "Synchronize:=", 0]],
                         ["NAME:Sweep Operations"], ["NAME:Goals"]])
except Exception:
    log("parametric setups skipped: add them by hand")

log("DONE. Board length %.1f mm (straight version %.1f mm): %.0f%% shorter. Zigzag heights %s mm."
    % (X_END, STRAIGHT_LENGTH, 100.0 * (1.0 - X_END / STRAIGHT_LENGTH),
       ", ".join("%.2f" % a for a in PL["amps"])))
