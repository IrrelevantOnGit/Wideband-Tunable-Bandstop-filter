# -*- coding: utf-8 -*-
# build_bandstop_v5.py  -  AEDT / HFSS (Student 2025 R2) :  Tools > Run Script
#
# Wideband tunable band-stop filter (Wi-Fi / radar coexistence), v5.
# Rebuilt from v4.aedt.  Changes vs v4:
#   * meander: the output-side zigzag (old seg9-seg16, 2 short teeth) is replaced
#     by ONE taller tooth -> board length shrinks (34.25mm -> ~26.55mm at the
#     default TOOTH_TOP_Y/TOOTH_ARM_W below; raise TOOTH_TOP_Y / lower
#     TOOTH_ARM_W for an even deeper meander and a shorter board - see those
#     two knobs). Input/middle teeth, pos1/pos2, stubs, varactor and bias
#     networks, ports, materials: unchanged.
#   * ground plane is flush with the substrate footprint (v4 had the ground
#     5mm larger than the substrate on every side - that's fixed here)
#   * every component has its own colour
#   * Cvar1 / Cvar2 start values tuned to put the notches at 2.4 / 5.0 GHz
#   * clean S11/S21 plots, same idea as fix_s11_plot.py
# Always builds in a brand-new, empty project, so it never collides with an
# existing v4 (or an earlier failed run) and v4.aedt is never touched.
from __future__ import print_function
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop.RestoreWindow()

# ----------------------------- knobs ----------------------------------------
DESIGN_NAME    = "HFSS_meander_v6_deep"  # lives in a NEW project, so the name can never clash
CVAR1_NOM      = "0.92pF"     # stub 1 -> 2.4 GHz notch
CVAR2_NOM      = "0.46pF"     # stub 2 -> 5.0 GHz notch
CVAR1_SWEEP    = "LIN 0.72pF 1.12pF 0.1pF"
CVAR2_SWEEP    = "LIN 0.36pF 0.56pF 0.05pF"
TOOTH_TOP_Y    = 9.0          # mm, DEEPER tooth (v5 default: 7.25mm, v4 teeth: ~4.25mm)
TOOTH_ARM_W    = 5.7          # mm, width of the tooth's top arm. Taller tooth (bigger
                               #     TOOTH_TOP_Y) needs a narrower arm to keep the same
                               #     trace length -> shorter board. v4's own arm: 5.7mm.
TAIL_MIN       = 3.925        # mm, straight run from the tooth to port 2 (matches the
                               #     3.925mm run at the input side, port1 -> first tooth)
SOLVE_NOMINAL  = True
SOLVE_PARAM    = True         # needs ~10 extra solves; set False to skip
# -----------------------------------------------------------------------------

W50 = 1.85                    # mm (feed width, = w50 variable)

# ---- output-tooth geometry, derived so the trace length it replaces is preserved ----
# (same two-leg-one-arm shape as every other tooth in the meander: the arm (TOOTH_ARM_W)
#  spans both legs and overhangs them equally; only the height/arm trade-off changes, so
#  stub positions, stub lengths and the 2.4/5 GHz tuning are untouched)
TOOTH_X0 = 18.775             # mm, left leg's x - same anchor the original v5 used
_LEG_H_REF, _ARM_REF = 7.25 + 0.925, 5.7      # v4-style output-tooth leg height & arm width
_TRACE_LEN = 2 * _LEG_H_REF + _ARM_REF        # path length the output tooth must match
LEG_H = TOOTH_TOP_Y + 0.925
if 2 * LEG_H >= _TRACE_LEN:
    raise Exception("TOOTH_TOP_Y too large for TOOTH_ARM_W >= 0 - lower TOOTH_TOP_Y")
TOOTH_ARM_W = min(TOOTH_ARM_W, _TRACE_LEN - 2 * LEG_H)   # never widen past the reference length
LEG2_X = TOOTH_X0 + TOOTH_ARM_W - 1.85        # right leg's x (arm overhangs both legs equally)
BOARD_L = LEG2_X + TAIL_MIN


def log(msg):
    print(msg)
    try:
        oDesktop.AddMessage("", "", 0, msg)
    except Exception:
        pass


# ----------------------------- project / design -----------------------------
# always start from a brand-new, empty project: nothing from earlier runs or v4.aedt is touched
oProject = oDesktop.NewProject()
oDefMgr = oProject.GetDefinitionManager()

oDesign = None
for soltype in ("HFSS Hybrid Modal Network", "DrivenModal"):
    try:
        oProject.InsertDesign("HFSS", DESIGN_NAME, soltype, "")
        oDesign = oProject.GetActiveDesign()
        if oDesign is not None:
            break
    except Exception:
        oDesign = None
if oDesign is None:
    raise Exception("could not insert HFSS design")
log("design: %s" % oDesign.GetName())

# material used by v4 (eps_r 3.38, tan d 0.0027)
try:
    if not oDefMgr.DoesMaterialExist("RO4003C_338"):
        oDefMgr.AddMaterial(["NAME:RO4003C_338", "CoordinateSystemType:=", "Cartesian",
                             "BulkOrSurfaceType:=", 1,
                             ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
                             "permittivity:=", "3.38",
                             "dielectric_loss_tangent:=", "0.0027"])
except Exception as e:
    log("material: %s" % e)

# ----------------------------- variables ------------------------------------
VARS = [("sub_h", "0.813mm"), ("w50", "1.85mm"), ("wstub", "1mm"),
        ("l_stub1", "8.2mm"), ("l_stub2", "2mm"), ("pos1", "9.1mm"),
        ("pos2", "17.45mm"), ("gap_size", "0.2mm"), ("pad_l", "0.5mm"),
        ("Cvar1", CVAR1_NOM), ("Cvar2", CVAR2_NOM)]
newprops = ["NAME:NewProps"]
for n, v in VARS:
    newprops.append(["NAME:" + n, "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", v])
oDesign.ChangeProperty(["NAME:AllTabs", ["NAME:LocalVariableTab",
                                         ["NAME:PropServers", "LocalVariables"], newprops]])

oEditor = oDesign.SetActiveEditor("3D Modeler")
oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", "mm", "Rescale:=", False])

# ----------------------------- colours --------------------------------------
COL = {
    "substrate": (30, 140, 100),   "ground": (184, 115, 51),  "airbox": (170, 210, 255),
    "feedline": (255, 215, 0),
    "gap": (230, 0, 0),            "pad": (0, 70, 255),       "gapb": (255, 120, 0),
    "padb": (150, 60, 220),        "via": (190, 190, 190),    "btrace": (0, 190, 255),
    "gapr": (100, 50, 0),          "bpad": (255, 100, 170),   "gapd": (120, 0, 60),
    "dpad": (160, 255, 0),         "viad": (255, 255, 255),
    "port1": (255, 0, 255),        "port2": (0, 255, 0),
}
COL2 = {   # stub-2 parts: distinct shades of the same roles, so every one of the 26
           # small bias/varactor parts is visually distinguishable
    "gap": (255, 110, 110),  "pad": (110, 160, 255),  "gapb": (255, 190, 110),
    "padb": (205, 160, 245), "via": (100, 100, 100),  "btrace": (140, 235, 255),
    "gapr": (60, 30, 0),     "bpad": (255, 175, 215), "gapd": (200, 70, 130),
    "dpad": (215, 255, 120), "viad": (30, 30, 30),
}


def shade(role, k):
    return COL[role] if k == 1 else COL2[role]


def attrs(name, color, transp=0.0, mat='"vacuum"', inside=True):
    return ["NAME:Attributes", "Name:=", name, "Flags:=", "",
            "Color:=", "(%d %d %d)" % color, "Transparency:=", transp,
            "PartCoordinateSystem:=", "Global", "UDMId:=", "",
            "MaterialValue:=", mat, "SurfaceMaterialValue:=", '""',
            "SolveInside:=", inside, "ShellElement:=", False,
            "ShellElementThickness:=", "0mm", "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False, "IsLightweight:=", False]


def mm(v):
    return "%gmm" % v


def rect(name, x, y, z, w, h, axis, color, transp=0.0):
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", x, "YStart:=", y, "ZStart:=", z,
         "Width:=", w, "Height:=", h, "WhichAxis:=", axis],
        attrs(name, color, transp))


def box(name, x, y, z, sx, sy, sz, color, transp, mat):
    oEditor.CreateBox(
        ["NAME:BoxParameters", "XPosition:=", x, "YPosition:=", y, "ZPosition:=", z,
         "XSize:=", sx, "YSize:=", sy, "ZSize:=", sz],
        attrs(name, color, transp, mat))


def via(name, x, y, color):
    oEditor.CreateCylinder(
        ["NAME:CylinderParameters", "XCenter:=", x, "YCenter:=", y, "ZCenter:=", "0mm",
         "Radius:=", "0.15mm", "Height:=", "sub_h", "WhichAxis:=", "Z", "NumSides:=", "0"],
        attrs(name, color, 0.0, '"pec"', False))


# ----------------------------- board ----------------------------------------
L = BOARD_L
SUB_Y0 = -18.925                         # fixed - set by the lowest bias component, not by T
SUB_H = TOOTH_TOP_Y + 2.0 - SUB_Y0       # keeps a 2mm clearance above the tallest tooth
AIR_MARGIN = 30.0                        # same radiation-box margin v4 used
box("substrate", "0mm", mm(SUB_Y0), "0mm", mm(L), mm(SUB_H), "sub_h",
    COL["substrate"], 0.45, '"RO4003C_338"')
rect("ground", "0mm", mm(SUB_Y0), "0mm", mm(L), mm(SUB_H), "Z", COL["ground"], 0.3)  # flush with substrate
box("airbox", "0mm", mm(SUB_Y0 - AIR_MARGIN), "-37mm", mm(L), mm(SUB_H + 2 * AIR_MARGIN), "sub_h+74mm",
    COL["airbox"], 0.95, '"vacuum"')

# ----------------------------- feedline + meander ---------------------------
rect("feedline", "0mm", "0.925mm", "sub_h", "3.925mm", "-1.85mm", "Z", COL["feedline"])

T = TOOTH_TOP_Y
# seg9-12: the output tooth - same two-leg-one-arm shape as every other tooth, just
# taller/narrower (TOOTH_X0 / TOOTH_ARM_W / LEG_H / LEG2_X derived above)
SEGS = [   # name, x, y_top, width, height       (mm)
    ("seg1",  2.075, 3.875, 1.85, -4.8),      # input tooth  (unchanged)
    ("seg2",  2.075, 3.875, 5.7,  -1.85),
    ("seg3",  5.925, 3.875, 1.85, -4.8),
    ("seg4",  5.925, 0.925, 6.35, -1.85),     # baseline under stub 1
    ("seg5",  10.425, 4.25, 1.85, -5.175),    # middle tooth (unchanged)
    ("seg6",  10.425, 4.25, 5.7,  -1.85),
    ("seg7",  14.275, 4.25, 1.85, -5.175),
    ("seg8",  14.275, 0.925, 6.35, -1.85),    # baseline under stub 2
    ("seg9",  TOOTH_X0, T, 1.85,        -LEG_H),   # output tooth, leg up
    ("seg10", TOOTH_X0, T, TOOTH_ARM_W, -1.85),    # output tooth, top arm
    ("seg11", LEG2_X,   T, 1.85,        -LEG_H),   # output tooth, leg down
    ("seg12", LEG2_X, 0.925, L - LEG2_X, -1.85),   # tail to port 2
]
for n, x, y, w, h in SEGS:
    rect(n, mm(x), mm(y), "sub_h", mm(w), mm(h), "Z", COL["feedline"])
rect("stub1", "pos1-wstub/2", "-w50/2", "sub_h", "wstub", "-l_stub1", "Z", COL["feedline"])
rect("stub2", "pos2-wstub/2", "-w50/2", "sub_h", "wstub", "-l_stub2", "Z", COL["feedline"])
oEditor.Unite(["NAME:Selections", "Selections:=",
               ",".join(["feedline"] + [s[0] for s in SEGS] + ["stub1", "stub2"])],
              ["NAME:UniteParameters", "KeepOriginals:=", False])

# ----------------------------- varactor + bias networks (unchanged) ---------
G, P = "gap_size", "pad_l"
for k in (1, 2):
    p, ls = "pos%d" % k, "l_stub%d" % k
    y0 = "-w50/2-%s" % ls                       # end of stub line
    y1 = y0 + "-" + G                           # after varactor gap
    y2 = y1 + "-" + P                           # after pad
    y3 = y2 + "-" + G                           # after DC-block gap
    rect("gap%d" % k,   p + "-wstub/2", y0, "sub_h", "wstub", "-" + G, "Z", shade("gap", k))
    rect("pad%d" % k,   p + "-wstub/2", y1, "sub_h", "wstub", "-" + P, "Z", shade("pad", k))
    rect("gapb%d" % k,  p + "-wstub/2", y2, "sub_h", "0.6mm", "-" + G, "Z", shade("gapb", k))
    rect("padb%d" % k,  p + "-wstub/2", y3, "sub_h", "0.6mm", "-" + P, "Z", shade("padb", k))
    via("via%d" % k,    p + "-0.2mm", y3 + "-pad_l/2", shade("via", k))
    rect("btrace%d" % k, p + "+0.3mm", y2, "sub_h", "0.2mm", "-2mm", "Z", shade("btrace", k))
    rect("gapr%d" % k,  p + "+0.3mm", y2 + "-2mm", "sub_h", "0.2mm", "-0.4mm", "Z", shade("gapr", k))
    rect("bpad%d" % k,  p + "-0.1mm", y2 + "-2.4mm", "sub_h", "1mm", "-1mm", "Z", shade("bpad", k))
    rect("gapd%d" % k,  p + "-0.1mm", y2 + "-3.4mm", "sub_h", "1mm", "-0.2mm", "Z", shade("gapd", k))
    rect("dpad%d" % k,  p + "-0.1mm", y2 + "-3.6mm", "sub_h", "1mm", "-0.5mm", "Z", shade("dpad", k))
    via("viad%d" % k,   p + "+0.4mm", y2 + "-3.6mm-0.25mm", shade("viad", k))

# ----------------------------- port sheets ----------------------------------
rect("portsheet1", "0mm", "-5mm", "0mm", "10mm", "8mm", "X", COL["port1"], 0.2)
rect("portsheet2", mm(L), "-5mm", "0mm", "10mm", "8mm", "X", COL["port2"], 0.2)

# ----------------------------- boundaries -----------------------------------
oBnd = oDesign.GetModule("BoundarySetup")

VAL = dict((n, float(v.replace("mm", ""))) for n, v in VARS if v.endswith("mm"))
SUBH = VAL["sub_h"]


def lumped(name, obj, x, ya, yb, r, l, c):
    """x, ya, yb are plain numbers in mm (explicit units avoid zero-length-line errors)"""
    a = ["NAME:" + name, "Objects:=", [obj],
         ["NAME:CurrentLine", "Start:=", [mm(x), mm(ya), mm(SUBH)],
          "End:=", [mm(x), mm(yb), mm(SUBH)]],
         "RLC Type:=", "Serial", "UseResist:=", True, "Resistance:=", r]
    if l:
        a += ["UseInduct:=", True, "Inductance:=", l]
    else:
        a += ["UseInduct:=", False]
    if c:
        a += ["UseCap:=", True, "Capacitance:=", c]
    else:
        a += ["UseCap:=", False]
    try:
        oBnd.AssignLumpedRLC(a)
    except Exception:
        i = a.index("RLC Type:=")
        oBnd.AssignLumpedRLC(a[:i] + a[i + 2:])      # older builds: series is the default


for k in (1, 2):
    px = VAL["pos%d" % k]
    ls = VAL["l_stub%d" % k]
    g, pl = VAL["gap_size"], VAL["pad_l"]
    y0 = -VAL["w50"] / 2.0 - ls          # end of stub line
    y1 = y0 - g                          # after varactor gap
    y2 = y1 - pl                         # after pad
    y3 = y2 - g                          # after DC-block gap
    lumped("Varactor%d" % k, "gap%d" % k,  px,       y0,        y1,        "0.6ohm", "0.5nH", "Cvar%d" % k)
    lumped("DCblock%d" % k,  "gapb%d" % k, px - 0.2, y2,        y3,        "0.1ohm", None,    "100pF")
    lumped("BiasRes%d" % k,  "gapr%d" % k, px + 0.4, y2 - 2.0,  y2 - 2.4,  "10kOhm", None,    None)
    lumped("Decap%d" % k,    "gapd%d" % k, px + 0.4, y2 - 3.4,  y2 - 3.6,  "0.1ohm", None,    "100pF")

metal = ["ground", "feedline"]
for k in (1, 2):
    metal += ["pad%d" % k, "padb%d" % k, "btrace%d" % k, "bpad%d" % k, "dpad%d" % k]
oBnd.AssignPerfectE(["NAME:PEC_metal", "Objects:=", metal, "InfGroundPlane:=", False])

# radiation on every airbox face except the two x-faces that carry the wave ports
faces = []
try:
    for fid in oEditor.GetFaceIDs("airbox"):
        cx = float(list(oEditor.GetFaceCenter(int(fid)))[0])
        if abs(cx) > 1e-6 and abs(cx - L) > 1e-6:
            faces.append(int(fid))
except Exception as e:
    log("face pick failed: %s" % e)
if faces:
    oBnd.AssignRadiation(["NAME:Rad1", "Faces:=", faces, "IsFssReference:=", False,
                          "IsForPML:=", False])
else:
    oBnd.AssignRadiation(["NAME:Rad1", "Objects:=", ["airbox"], "IsFssReference:=", False,
                          "IsForPML:=", False])

for k, x in ((1, "0mm"), (2, mm(L))):
    oBnd.AssignWavePort(
        ["NAME:port%d" % k, "Objects:=", ["portsheet%d" % k], "NumModes:=", 1,
         "RenormalizeAllTerminals:=", True, "UseLineModeAlignment:=", False,
         "DoDeembed:=", False,
         ["NAME:Modes", ["NAME:Mode1", "ModeNum:=", 1, "UseIntLine:=", True,
                         ["NAME:IntLine", "Start:=", [x, "0mm", "0mm"], "End:=", [x, "0mm", mm(SUBH)]],
                         "AlignmentGroup:=", 0, "CharImp:=", "Zpi", "RenormImp:=", "50ohm"]],
         "ShowReporterFilter:=", False, "ReporterFilter:=", [True],
         "UseAnalyticAlignment:=", False])

# ----------------------------- mesh / setup / sweep -------------------------
oMesh = oDesign.GetModule("MeshSetup")
oMesh.AssignLengthOp(["NAME:Length1", "RefineInside:=", True, "Enabled:=", True,
                      "Objects:=", ["gap1", "gap2", "pad1", "pad2"],
                      "RestrictElem:=", False, "NumMaxElem:=", "1000",
                      "RestrictLength:=", True, "MaxLength:=", "1.5mm"])

oSetup = oDesign.GetModule("AnalysisSetup")
oSetup.InsertSetup("HfssDriven",
                   ["NAME:Setup1", "Frequency:=", "5GHz", "MaxDeltaS:=", 0.02,
                    "MaximumPasses:=", 15, "MinimumPasses:=", 1,
                    "MinimumConvergedPasses:=", 1, "PercentRefinement:=", 30,
                    "BasisOrder:=", 1, "IsEnabled:=", True])
oSetup.InsertFrequencySweep("Setup1",
                            ["NAME:Sweep", "IsEnabled:=", True, "RangeType:=", "LinearCount",
                             "RangeStart:=", "1GHz", "RangeEnd:=", "8GHz", "RangeCount:=", 281,
                             "Type:=", "Interpolating", "SaveFields:=", False,
                             "InterpTolerance:=", 0.5, "InterpMaxSolns:=", 250,
                             "InterpMinSolns:=", 0, "InterpMinSubranges:=", 1,
                             "InterpUseS:=", True, "InterpUsePortImped:=", False,
                             "InterpUsePropConst:=", True, "UseFullBasis:=", True,
                             "EnforcePassivity:=", True, "PassivityErrorTolerance:=", 0.0001])

oOpt = oDesign.GetModule("Optimetrics")
for nm, var, data in (("ParametricSetup1", "Cvar1", CVAR1_SWEEP),
                      ("ParametricSetup2", "Cvar2", CVAR2_SWEEP)):
    oOpt.InsertSetup("OptiParametric",
                     ["NAME:" + nm, "IsEnabled:=", True,
                      ["NAME:ProdOptiSetupDataV2", "SaveFields:=", False, "CopyMesh:=", True,
                       "SolveWithCopiedMeshOnly:=", True],
                      ["NAME:StartingPoint"], "Sim. Setups:=", ["Setup1"],
                      ["NAME:Sweeps", ["NAME:SweepDefinition", "Variable:=", var,
                                       "Data:=", data, "OffsetF1:=", False, "Synchronize:=", 0]],
                      ["NAME:Sweep Operations"], ["NAME:Goals"]])

try:
    oEditor.FitAll()
except Exception:
    pass
log("v6 deep-meander model built: board %.2f x %.3f mm (v4: 34.25 x 28.175, v5: 26.55 x 28.175)" % (L, SUB_H))

# ----------------------------- solve ----------------------------------------
if SOLVE_NOMINAL:
    oDesign.Analyze("Setup1")
if SOLVE_PARAM:
    oOpt.SolveSetup("ParametricSetup1")
    oOpt.SolveSetup("ParametricSetup2")

# ----------------------------- plots (same as fix_s11_plot.py) --------------
SETUP = "Setup1 : Sweep"
F_MIN, F_MAX, Y_MIN, Y_MAX = "1GHz", "8GHz", "-40", "0"
TARGETS_GHZ = (2.4, 5.0)
oRep = oDesign.GetModule("ReportSetup")


def variations(**swept):
    out = ["Freq:=", ["All"]]
    for n, v in VARS:
        out += [n + ":=", swept.get(n, ["Nominal"])]
    return out


def prop(tab, server, changed):
    oRep.ChangeProperty(["NAME:AllTabs", ["NAME:" + tab, "PropServers:=", [server],
                                          ["NAME:ChangedProps"] + changed]])


def plot(title, ycomps, colors=None, **swept):
    oRep.CreateReport(title, "Modal Solution Data", "Rectangular Plot", SETUP,
                      ["Domain:=", "Sweep"], variations(**swept),
                      ["X Component:=", "Freq", "Y Component:=", ycomps])
    for tab, server, props in (
            ("Scaling", title + ":AxisY1", [["NAME:Min", "Value:=", Y_MIN], ["NAME:Max", "Value:=", Y_MAX],
                                            ["NAME:Spacing", "Value:=", "5"]]),
            ("Scaling", title + ":AxisX", [["NAME:Min", "Value:=", F_MIN], ["NAME:Max", "Value:=", F_MAX],
                                           ["NAME:Spacing", "Value:=", "0.5GHz"]])):
        try:
            prop(tab, server, props)
        except Exception:
            pass
    for trace, (r, g, b) in (colors or {}).items():
        for key in ("Line Color", "Color"):
            try:
                prop("Attributes", title + ":" + trace, [["NAME:" + key, "R:=", r, "G:=", g, "B:=", b]])
                break
            except Exception:
                pass
    for f in TARGETS_GHZ:
        try:
            oRep.AddCartesianXMarker(title, "%sGHz" % f)
        except Exception:
            pass


try:
    if "S Parameter Plot1" in list(oRep.GetAllReportNames()):
        oRep.DeleteReports(["S Parameter Plot1"])
except Exception:
    pass
plot("S11 and S21 (nominal)", ["dB(S(port1,port1))", "dB(S(port2,port1))"],
     colors={"dB(S(port1,port1))": (0, 90, 255), "dB(S(port2,port1))": (230, 0, 0)})
plot("S21 vs Cvar1 (2.4 GHz notch)", ["dB(S(port2,port1))"], Cvar1=["All"])
plot("S21 vs Cvar2 (5 GHz notch)", ["dB(S(port2,port1))"], Cvar2=["All"])
log("v6 deep-meander done - nominal Cvar1=%s Cvar2=%s" % (CVAR1_NOM, CVAR2_NOM))
