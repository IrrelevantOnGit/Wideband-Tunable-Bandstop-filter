# -*- coding: utf-8 -*-
# meander_autotune.py
#
# Builds a NEW HFSS design (inside the open project) of the dual-band tunable bandstop
# filter with a much SHORTER board, then TUNES ITSELF: it solves, reads where the two
# notches are, changes the stub lengths, and repeats until the notches sit on target.
# Your other designs, reports and sweeps are not touched.
#
# HOW TO RUN (Ansys Electronics Desktop):
#   1. Open your project.  2. Tools > Run Script...  and pick this file.
#   3. Wait for "DONE" in the Message Manager (the tuning loop solves the design several times).
#
# WHAT CHANGED COMPARED TO meander_feedline_design.py
#   * Only the section between the two stubs is zigzagged (2 runs = the shortest possible fold).
#     The two end sections do not set any resonance, so they are now short straight lines.
#     Zigzagging them only added bends and mismatch (this is what hurt S11).
#   * Outer corners are notched (mitred), which removes most of the bend capacitance.
#   * 3 mm straight launch at each port, so the wave port sees a clean line.
#   * Lumped elements use expressions, so they follow the stubs when the lengths change.
#   * Auto tuning of l_stub1 and l_stub2 (switch AUTO_TUNE).
#   * Clean reports: "S21_S11_nominal" shows only the nominal design, S21 and S11 together.

import re
import os
import csv

try:
    import ScriptEnv
    ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
    oDesktop.RestoreWindow()
except ImportError:
    pass

# =============================================================== PARAMETERS (mm unless noted)
DESIGN_NAME = "HFSS_meander2"

# board shape. RUNS = number of vertical zigzag runs (even). 0 = straight line.
MEANDER_GAP = 2.0      # clear gap between neighbouring zigzag runs
E_LEAD = 1.0           # straight lead before/after a zigzag
LAUNCH = 3.0           # straight launch at each port
NODE_LEN = 2.0         # straight piece where each stub joins the line
PATH_A = 5.0           # port 1 -> stub 1 centre   (not resonant: keep short)
PATH_B = 15.0          # stub 1 -> stub 2          (sets the stage spacing: folded)
PATH_C = 5.0           # stub 2 -> port 2          (not resonant: keep short)
RUNS_A, RUNS_B, RUNS_C = 0, 2, 0
MITER = True           # notch the outer corner of every bend
STRAIGHT_LENGTH = 60.0  # the old straight board, only for the printout

# stack-up and circuit
SUB_H, ER, TAND = 0.813, 3.38, 0.0027
W50, WSTUB = 1.85, 1.0
L_STUB1, L_STUB2 = 6.6, 1.5      # start values. The tuning loop changes them
GAP_SIZE, PAD_L = 0.2, 0.5
CVAR1, CVAR2 = "1.5pF", "0.75pF"  # nominal varactor values (the tuning target is reached at these)
ADD_BIAS_NETWORK = True
MARGIN, AIR_Y, AIR_Z = 5.0, 25.0, 37.0

# auto tuning
AUTO_TUNE = True
TARGET_F1, TARGET_F2 = 2.45, 5.50   # GHz, at the nominal Cvar1 and Cvar2
WIN1, WIN2 = (1.2, 3.3), (3.3, 7.0)  # where to look for each notch (GHz)
TOL_GHZ = 0.03
MAX_ITER = 6
L_MIN, L_MAX = 0.3, 14.0

# =============================================================== geometry plan (pure python)
P = W50 + MEANDER_GAP


def fmt(x):
    s = ("%.4f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def section(x, path, runs, name):
    """Straight line or zigzag that starts and ends on y = 0."""
    if path < -1e-9:
        raise ValueError("%s: path is shorter than the launch and node pieces" % name)
    if runs == 0:
        if path < 1e-9:
            return [], x, 0.0
        return [(x + path, 0.0)], x + path, 0.0
    if runs % 2 != 0:
        raise ValueError("%s: RUNS must be even" % name)
    amp = (path - 2 * E_LEAD - (runs - 1) * P) / float(runs)
    if amp < 1.0:
        raise ValueError("%s: path %.1f mm is too short to zigzag with %d runs; use RUNS=0 or a longer path"
                         % (name, path, runs))
    pts = []
    x += E_LEAD
    pts.append((x, 0.0))
    for i in range(runs):
        y = amp if i % 2 == 0 else 0.0
        pts.append((x, y))
        if i < runs - 1:
            x += P
            pts.append((x, y))
    x += E_LEAD
    pts.append((x, 0.0))
    return pts, x, amp


def plan():
    pts = [(0.0, 0.0)]
    x = LAUNCH
    pts.append((x, 0.0))
    amps = []
    mp, x, a = section(x, PATH_A - LAUNCH - NODE_LEN / 2.0, RUNS_A, "section A")
    pts += mp
    amps.append(a)
    node1 = x + NODE_LEN / 2.0
    x += NODE_LEN
    pts.append((x, 0.0))
    mp, x, a = section(x, PATH_B - NODE_LEN, RUNS_B, "section B")
    pts += mp
    amps.append(a)
    node2 = x + NODE_LEN / 2.0
    x += NODE_LEN
    pts.append((x, 0.0))
    mp, x, a = section(x, PATH_C - NODE_LEN / 2.0 - LAUNCH, RUNS_C, "section C")
    pts += mp
    amps.append(a)
    x += LAUNCH
    pts.append((x, 0.0))
    clean = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - clean[-1][0]) < 1e-9 and abs(p[1] - clean[-1][1]) < 1e-9:
            continue
        clean.append(p)
    merged = [clean[0]]
    for i in range(1, len(clean) - 1):
        a_, b_, c_ = merged[-1], clean[i], clean[i + 1]
        same_h = abs(a_[1] - b_[1]) < 1e-9 and abs(b_[1] - c_[1]) < 1e-9
        same_v = abs(a_[0] - b_[0]) < 1e-9 and abs(b_[0] - c_[0]) < 1e-9
        if not (same_h or same_v):
            merged.append(b_)
    merged.append(clean[-1])
    h = W50 / 2.0
    ext = 0.0 if MITER else h
    rects = []
    n = len(merged) - 1
    for i in range(n):
        (xa, ya), (xb, yb) = merged[i], merged[i + 1]
        e0 = ext if i > 0 else 0.0
        e1 = ext if i < n - 1 else 0.0
        if abs(ya - yb) < 1e-9:
            s = 1.0 if xb > xa else -1.0
            xs, xe = xa - s * e0, xb + s * e1
            rects.append((min(xs, xe), max(xs, xe), ya - h, ya + h))
        else:
            s = 1.0 if yb > ya else -1.0
            ys, ye = ya - s * e0, yb + s * e1
            rects.append((xa - h, xa + h, min(ys, ye), max(ys, ye)))
    length = sum(abs(merged[i + 1][0] - merged[i][0]) + abs(merged[i + 1][1] - merged[i][1]) for i in range(n))
    return dict(rects=rects, node1=node1, node2=node2, x_end=x, amps=amps,
                top=max(p[1] for p in merged) + h, path=length)


PL = plan()
POS = {1: PL["node1"], 2: PL["node2"]}
X_END = PL["x_end"]
YA_MAX = max(L_STUB1, L_STUB2, 14.0)       # leave room for the stub to grow while tuning
Y_LOW = -W50 / 2.0 - YA_MAX - GAP_SIZE - PAD_L - (4.1 if ADD_BIAS_NETWORK else 0.7)
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


def set_var(name, value):
    oDesign.ChangeProperty(
        ["NAME:AllTabs",
         ["NAME:LocalVariableTab", ["NAME:PropServers", "LocalVariables"],
          ["NAME:ChangedProps", ["NAME:" + name, "Value:=", value]]]])


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


def lumped(name, obj, x_expr, y_top_expr, y_bot_expr, R=None, L=None, C=None):
    """Lumped RLC across a gap. Positions are expressions, so the line follows variable changes."""
    def make(xe, yt, yb):
        return ["NAME:" + name, "Objects:=", [obj],
                ["NAME:CurrentLine", "Start:=", [xe, yt, "sub_h"], "End:=", [xe, yb, "sub_h"]],
                "RLC Type:=", "Serial",
                "UseResist:=", R is not None, "Resistance:=", R or "0ohm",
                "UseInduct:=", L is not None, "Inductance:=", L or "0nH",
                "UseCap:=", C is not None, "Capacitance:=", C or "0pF"]
    oBnd.AssignLumpedRLC(make(x_expr, y_top_expr, y_bot_expr))


# ---- substrate, ground, air box
log("Step 3: substrate, ground, air box")
oEditor.CreateBox(
    ["NAME:BoxParameters", "XPosition:=", "0mm", "YPosition:=", "%smm" % fmt(Y_SUB0), "ZPosition:=", "0mm",
     "XSize:=", "%smm" % fmt(X_END), "YSize:=", "%smm" % fmt(Y_SUB1 - Y_SUB0), "ZSize:=", "sub_h"],
    attrs("substrate", "(132 132 193)", 0.2, "RO4003C_338", True))
sheet("ground", "0mm", "%smm" % fmt(Y_SUB0 - 5), "%smm" % fmt(X_END), "%smm" % fmt(Y_SUB1 - Y_SUB0 + 10), z="0mm")
AY0, AY1 = Y_SUB0 - 5 - AIR_Y, Y_SUB1 + 5 + AIR_Y
oEditor.CreateBox(
    ["NAME:BoxParameters", "XPosition:=", "0mm", "YPosition:=", "%smm" % fmt(AY0), "ZPosition:=", "%smm" % fmt(-AIR_Z),
     "XSize:=", "%smm" % fmt(X_END), "YSize:=", "%smm" % fmt(AY1 - AY0), "ZSize:=", "sub_h+%smm" % fmt(2 * AIR_Z)],
    attrs("airbox", "(143 175 143)", 0.9, "vacuum", True))

# ---- feed line (zigzag between the stubs only) + stubs, united into one sheet
log("Step 4: feed line, %d pieces, path %.1f mm in %.1f mm" % (len(PL["rects"]), PL["path"], X_END))
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

# ---- varactor gap, pads, DC-block, bias network (all positions are expressions)
log("Step 5: varactor gaps, pads and bias network")
metal = ["ground", "feedline"]
for k in (1, 2):
    p = "pos%d" % k
    y0 = "-w50/2-l_stub%d" % k
    ya = y0 + "-gap_size-pad_l"
    sheet("gap%d" % k, "%s-wstub/2" % p, y0, "wstub", "-gap_size")
    sheet("pad%d" % k, "%s-wstub/2" % p, y0 + "-gap_size", "wstub", "-pad_l")
    metal.append("pad%d" % k)
    lumped("Varactor%d" % k, "gap%d" % k, p, y0, y0 + "-gap_size", R="0.6ohm", L="0.5nH", C="Cvar%d" % k)
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
    lumped("DCblock%d" % k, "gapb%d" % k, p + "-0.2mm", ya, ya + "-gap_size", R="0.1ohm", C="100pF")
    lumped("BiasRes%d" % k, "gapr%d" % k, p + "+0.4mm", ya + "-2mm", ya + "-2.4mm", R="10kohm")
    lumped("Decap%d" % k, "gapd%d" % k, p + "+0.4mm", ya + "-3.4mm", ya + "-3.6mm", R="0.1ohm", C="100pF")

log("Step 6: perfect conductors")
oBnd.AssignPerfectE(["NAME:PEC_metal", "Objects:=", metal, "InfGroundPlane:=", False])

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

log("Step 8: radiation boundary")
rad = []
for f in oEditor.GetFaceIDs("airbox"):
    c = oEditor.GetFaceCenter(int(f))
    cx = float(str(c[0]).replace("mm", ""))
    if abs(cx - 0.0) < 1e-6 or abs(cx - X_END) < 1e-6:
        continue
    rad.append(int(f))
oBnd.AssignRadiation(["NAME:Rad1", "Faces:=", rad, "IsFssReference:=", False, "IsForPML:=", False])

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


# =============================================================== reports and auto tuning
def make_report(name, exprs):
    rep = oDesign.GetModule("ReportSetup")
    var = ["Freq:=", ["All"]]
    for nm, _ in VARS:
        var += [nm + ":=", ["Nominal"]]
    rep.CreateReport(name, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
                     ["Domain:=", "Sweep"], var, ["X Component:=", "Freq", "Y Component:=", exprs], [])
    return rep


def read_curve(rep, name):
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or "."
    path = os.path.join(tmp, "%s_%s.csv" % (DESIGN_NAME, name))
    rep.ExportToFile(name, path)
    fr, db = [], []
    f = open(path, "r")
    try:
        for row in csv.reader(f):
            try:
                a, b = float(row[0]), float(row[1])
            except (ValueError, IndexError):
                continue
            fr.append(a)
            db.append(b)
    finally:
        f.close()
    return fr, db


def find_notch(fr, db, lo, hi):
    idx = [i for i in range(len(fr)) if lo <= fr[i] <= hi]
    if len(idx) < 3:
        return None, None
    i = idx[0]
    for j in idx:
        if db[j] < db[i]:
            i = j
    f = fr[i]
    if 0 < i < len(fr) - 1:
        den = db[i - 1] - 2 * db[i] + db[i + 1]
        if abs(den) > 1e-12:
            f = fr[i] + 0.5 * (db[i - 1] - db[i + 1]) / den * (fr[i + 1] - fr[i])
    return f, db[i]


def num_mm(var):
    return float(str(oDesign.GetVariableValue(var)).replace("mm", ""))


def next_length(hist, target):
    """hist = [(length_mm, notch_GHz), ...]. A longer stub gives a lower notch."""
    l1, f1 = hist[-1]
    new = l1 * (f1 / target)
    if len(hist) >= 2:
        l0, f0 = hist[-2]
        if abs(l1 - l0) > 1e-6 and abs(f1 - f0) > 1e-4:
            slope = (f1 - f0) / (l1 - l0)
            if slope < 0:
                new = l1 + (target - f1) / slope
    new = max(0.6 * l1, min(1.6 * l1, new))
    return max(L_MIN, min(L_MAX, new))


result_text = ""
if AUTO_TUNE:
    try:
        log("Step 10: auto tuning (each pass is one solve)")
        rep21 = make_report("AutoTune_S21", ["dB(S(port2,port1))"])
        hist = {1: [], 2: []}
        best = None
        for it in range(MAX_ITER):
            oDesign.Analyze("Setup1")
            fr, db = read_curve(rep21, "AutoTune_S21")
            f1, d1 = find_notch(fr, db, WIN1[0], WIN1[1])
            f2, d2 = find_notch(fr, db, WIN2[0], WIN2[1])
            l1, l2 = num_mm("l_stub1"), num_mm("l_stub2")
            if f1 is None or f2 is None or d1 > -8.0 or d2 > -8.0:
                raise RuntimeError("no clear notch in the search window (depths %s and %s dB). "
                                   "Check the model with a plain Analyze first" % (d1, d2))
            err = abs(f1 - TARGET_F1) + abs(f2 - TARGET_F2)
            log("pass %d: l_stub1 %.2f mm -> notch %.3f GHz (%.1f dB) | l_stub2 %.2f mm -> notch %.3f GHz (%.1f dB)"
                % (it + 1, l1, f1, d1, l2, f2, d2))
            if best is None or err < best[0]:
                best = (err, l1, l2, f1, f2)
            hist[1].append((l1, f1))
            hist[2].append((l2, f2))
            if abs(f1 - TARGET_F1) < TOL_GHZ and abs(f2 - TARGET_F2) < TOL_GHZ:
                break
            if it == MAX_ITER - 1:
                break
            if abs(f1 - TARGET_F1) >= TOL_GHZ:
                set_var("l_stub1", "%.3fmm" % next_length(hist[1], TARGET_F1))
            if abs(f2 - TARGET_F2) >= TOL_GHZ:
                set_var("l_stub2", "%.3fmm" % next_length(hist[2], TARGET_F2))
        # if the last pass is not the best one, go back to the best lengths and solve once more
        if abs(num_mm("l_stub1") - best[1]) > 1e-3 or abs(num_mm("l_stub2") - best[2]) > 1e-3:
            set_var("l_stub1", "%.3fmm" % best[1])
            set_var("l_stub2", "%.3fmm" % best[2])
            oDesign.Analyze("Setup1")
        result_text = "tuned: l_stub1 = %.2f mm (notch %.3f GHz), l_stub2 = %.2f mm (notch %.3f GHz)." % (
            best[1], best[3], best[2], best[4])
        for k, lb, fb, tg in ((1, best[1], best[3], TARGET_F1), (2, best[2], best[4], TARGET_F2)):
            if abs(fb - tg) >= TOL_GHZ:
                if lb <= L_MIN + 1e-3 and fb < tg:
                    result_text += (" Stage %d: the stub is at its %.1f mm minimum and the notch is still %.2f GHz low. "
                                    "Lower Cvar%d (the varactor minimum limits this) or cut the bias network inductance."
                                    % (k, L_MIN, tg - fb, k))
                else:
                    result_text += " Stage %d: notch is %.3f GHz, target %.2f GHz." % (k, fb, tg)
    except Exception as e:
        log("auto tuning stopped: %s. The design is built, tune l_stub1 and l_stub2 by hand." % str(e))

# clean nominal plot: S21 and S11 together, nothing else
try:
    make_report("S21_S11_nominal", ["dB(S(port2,port1))", "dB(S(port1,port1))"])
except Exception:
    log("report S21_S11_nominal skipped")

# S11 summary outside the two notches
try:
    rep11 = make_report("AutoTune_S11", ["dB(S(port1,port1))"])
    fr, db = read_curve(rep11, "AutoTune_S11")
    fa, _ = find_notch(*(read_curve(rep21, "AutoTune_S21") + WIN1)) if AUTO_TUNE else (TARGET_F1, 0)
    fb, _ = find_notch(*(read_curve(rep21, "AutoTune_S21") + WIN2)) if AUTO_TUNE else (TARGET_F2, 0)
    outside = [db[i] for i in range(len(fr))
               if abs(fr[i] - fa) > 0.25 and abs(fr[i] - fb) > 0.25 and fr[i] < 7.5]
    if outside:
        log("S11 outside the notches (1 to 7.5 GHz): worst %.1f dB, average %.1f dB"
            % (max(outside), sum(outside) / len(outside)))
except Exception:
    pass

# parametric sweeps (narrow ranges, mesh is copied so they are fast)
try:
    opt = oDesign.GetModule("Optimetrics")
    for k, rng in ((1, "LIN 1.3pF 1.8pF 0.1pF"), (2, "LIN 0.55pF 0.95pF 0.1pF")):
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

log("DONE. Board length %.1f mm (straight version %.1f mm): %.0f%% shorter. %s"
    % (X_END, STRAIGHT_LENGTH, 100.0 * (1.0 - X_END / STRAIGHT_LENGTH), result_text))
