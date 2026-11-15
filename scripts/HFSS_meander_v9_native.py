# HFSS_meander_v9 - tunable dual-band bandstop filter (2.4 GHz + 5 GHz), coiled-stub version with AUTO-TUNE.
# Native AEDT script (IronPython 2.7): run via  Tools > Run Script...
#
# What it does:
#  1. Builds the filter (stub1 above the feed, stub2 below, both at one junction, spiral coils,
#     lumped C = Cvar + fixed trim cap Cp).
#  2. AUTO-TUNES: solves nominal + one high-C point, reads the notch frequencies from the results,
#     and corrects coil length (K1,K2) and trim caps (Cp1,Cp2) until notches sit at 2.4 / 5.0 GHz and the
#     sweep spacing matches the reference (up to MAX_IT rounds, ~1 min each).
#  3. Builds the final design "HFSS_meander_v9" with the tuned values, runs both parametric sweeps and
#     creates the three reports.
# Set AUTOTUNE = False to skip tuning and use the K/CP values below directly.
import ScriptEnv
import time
import os
import math
import tempfile
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop.RestoreWindow()

# ---------------- knobs ----------------
AUTOTUNE = True
MAX_IT = 5
F1_T, F2_T = 2.4, 5.0                  # target nominal notch frequencies (GHz)
CNOM1, CNOM2 = 0.92, 0.46              # nominal Cvar (pF)
CHI1, CHI2 = 1.12, 0.56                # high end of the sweeps (pF)
CPT1, CPT2 = 0.18, 0.05                # target effective parasitic C (pF) -> reproduces reference sweep spacing
LP = 0.55e-9                           # fixed (non-coil) inductance of the lumped-C path, for the K update

H = 0.635
ER = 10.2
TAND = 0.0022
W50 = 0.58
W = 0.12
S = 0.10
PITCH = W + S
D1, BASE1 = 1.20, 5.64                 # stub 1 outer side (mm), base path length (mm)
D2, BASE2 = 0.80, 3.03                 # stub 2
K1, K2 = 1.20, 1.05                    # starting coil-length factors (tuned automatically)
CP1, CP2 = 0.18, 0.05                  # starting trim caps (pF)
XJ = -0.60
SX = 4.0
SY0, SY1 = -2.0, 2.8


def mm(v):
    return "%.4fmm" % v


def log(msg):
    try:
        oDesktop.AddMessage("", "", 0, msg)
    except:
        pass


oProject = oDesktop.NewProject()
oProject.GetDefinitionManager().AddMaterial(
    ["NAME:RO3010_like", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,
     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
     "permittivity:=", str(ER), "dielectric_loss_tangent:=", str(TAND)])


def attrs(name, mat="vacuum", color="(143 175 143)"):
    return ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color, "Transparency:=", 0,
            "PartCoordinateSystem:=", "Global", "UDMId:=", "", "MaterialValue:=", '"%s"' % mat,
            "SurfaceMaterialValue:=", '""', "SolveInside:=", True, "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False, "IsLightweight:=", False]


def spiral_pts(x0, y0, D, total):
    dirs = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    pts = [(x0, y0)]
    x = x0
    y = y0
    acc = 0.0
    k = 0
    while acc < total - 1e-9:
        L = D - (k // 2) * PITCH
        if L <= 0.12:
            break
        if L > total - acc:
            L = total - acc
        dx, dy = dirs[k % 4]
        x += dx * L
        y += dy * L
        pts.append((x, y))
        acc += L
        k += 1
    return pts


def build_design(dname, k1, k2, cp1, cp2, npts):
    oProject.InsertDesign("HFSS", dname, "DrivenModal", "")
    oDesign = oProject.SetActiveDesign(dname)
    oEditor = oDesign.SetActiveEditor("3D Modeler")
    oBnd = oDesign.GetModule("BoundarySetup")

    oDesign.ChangeProperty(["NAME:AllTabs", ["NAME:LocalVariableTab", ["NAME:PropServers", "LocalVariables"],
        ["NAME:NewProps",
         ["NAME:Cvar1", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "%.4fpF" % CNOM1],
         ["NAME:Cvar2", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "%.4fpF" % CNOM2],
         ["NAME:Cp1", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "%.4fpF" % cp1],
         ["NAME:Cp2", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "%.4fpF" % cp2]]]])

    copper = []

    def rect(name, x, y, z, axis, w, h):
        oEditor.CreateRectangle(["NAME:RectangleParameters", "IsCovered:=", True,
            "XStart:=", mm(x), "YStart:=", mm(y), "ZStart:=", mm(z),
            "Width:=", mm(w), "Height:=", mm(h), "WhichAxis:=", axis], attrs(name))
        return name

    oEditor.CreateBox(["NAME:BoxParameters", "XPosition:=", mm(-SX), "YPosition:=", mm(SY0), "ZPosition:=", "0mm",
        "XSize:=", mm(2 * SX), "YSize:=", mm(SY1 - SY0), "ZSize:=", mm(H)],
        attrs("Sub", "RO3010_like", "(0 128 0)"))
    rect("GND", -SX, SY0, 0.0, "Z", 2 * SX, SY1 - SY0)
    copper.append(rect("Feed", -SX, -W50 / 2.0, H, "Z", 2 * SX, W50))

    def stub(tag, D, total, sgn):
        ys = W50 / 2.0 + 0.20
        pts = [(XJ, 0.0), (XJ, ys)] + spiral_pts(XJ, ys, D, total)[1:]
        pts = [(x, sgn * y) for (x, y) in pts]
        for i in range(len(pts) - 1):
            (xa, ya), (xb, yb) = pts[i], pts[i + 1]
            x0 = min(xa, xb) - W / 2.0
            x1 = max(xa, xb) + W / 2.0
            y0 = min(ya, yb) - W / 2.0
            y1 = max(ya, yb) + W / 2.0
            copper.append(rect("%s_s%d" % (tag, i), x0, y0, H, "Z", x1 - x0, y1 - y0))
        return pts

    pts1 = stub("S1", D1, BASE1 * k1, 1)
    pts2 = stub("S2", D2, BASE2 * k2, -1)

    oEditor.Unite(["NAME:Selections", "Selections:=", ",".join(copper)],
                  ["NAME:UniteParameters", "KeepOriginals:=", False])
    oBnd.AssignPerfectE(["NAME:PerfE_GND", "Objects:=", ["GND"], "InfGroundPlane:=", False])
    try:
        oBnd.AssignFiniteCond(["NAME:Cu_top", "Objects:=", ["Feed"], "UseMaterial:=", True, "Material:=", "copper",
            "UseThickness:=", True, "Thickness:=", "0.035mm", "Roughness:=", "0um", "InfGroundPlane:=", False,
            "IsTwoSided:=", False, "IsInternal:=", True])
    except:
        oBnd.AssignPerfectE(["NAME:PerfE_top", "Objects:=", ["Feed"], "InfGroundPlane:=", False])

    def add_cap(tag, pts, cexpr):
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        if abs(xb - xa) > 1e-9:
            d = 1.0 if xb > xa else -1.0
            xe = xb + d * W / 2.0
            sh = rect(tag + "_capsheet", xe, yb - W / 2.0, 0.0, "X", W, H)
            st = [mm(xe), mm(yb), "0mm"]
            en = [mm(xe), mm(yb), mm(H)]
        else:
            d = 1.0 if yb > ya else -1.0
            ye = yb + d * W / 2.0
            sh = rect(tag + "_capsheet", xb - W / 2.0, ye, 0.0, "Y", H, W)
            st = [mm(xb), mm(ye), "0mm"]
            en = [mm(xb), mm(ye), mm(H)]
        oBnd.AssignLumpedRLC(["NAME:" + tag + "_C", "Objects:=", [sh],
            ["NAME:CurrentLine", "Start:=", st, "End:=", en],
            "RLC Type:=", "Parallel",
            "UseResist:=", False, "Resistance:=", "0ohm",
            "UseInduct:=", False, "Inductance:=", "0nH",
            "UseCap:=", True, "Capacitance:=", cexpr])

    add_cap("S1", pts1, "Cvar1+Cp1")
    add_cap("S2", pts2, "Cvar2+Cp2")

    for i, x in enumerate([-SX, SX]):
        nm = "port%d" % (i + 1)
        sh = rect(nm + "_sheet", x, -1.5, 0.0, "X", 3.0, H)
        oBnd.AssignLumpedPort(["NAME:" + nm, "Objects:=", [sh], "RenormalizeAllTerminals:=", True,
            "DoDeembed:=", False,
            ["NAME:Modes", ["NAME:Mode1", "ModeNum:=", 1, "UseIntLine:=", True,
                ["NAME:IntLine", "Start:=", [mm(x), "0mm", "0mm"], "End:=", [mm(x), "0mm", mm(H)]],
                "CharImp:=", "Zpi"]],
            "ShowReporterFilter:=", False, "ReporterFilter:=", [True], "Impedance:=", "50ohm"])

    oEditor.CreateRegion(["NAME:RegionParameters",
        "+XPaddingType:=", "Absolute Offset", "+XPadding:=", "3mm",
        "-XPaddingType:=", "Absolute Offset", "-XPadding:=", "3mm",
        "+YPaddingType:=", "Absolute Offset", "+YPadding:=", "3mm",
        "-YPaddingType:=", "Absolute Offset", "-YPadding:=", "3mm",
        "+ZPaddingType:=", "Absolute Offset", "+ZPadding:=", "3mm",
        "-ZPaddingType:=", "Absolute Offset", "-ZPadding:=", "3mm"], attrs("Region"))
    oBnd.AssignRadiation(["NAME:Rad1", "Objects:=", ["Region"], "IsFssReference:=", False, "IsForPML:=", False])

    oAn = oDesign.GetModule("AnalysisSetup")
    oAn.InsertSetup("HfssDriven", ["NAME:Setup1", "AdaptMultipleFreqs:=", False, "Frequency:=", "5GHz",
        "MaxDeltaS:=", 0.03, "PortsOnly:=", False, "UseMatrixConv:=", False, "MaximumPasses:=", 8,
        "MinimumPasses:=", 1, "MinimumConvergedPasses:=", 1, "PercentRefinement:=", 30, "IsEnabled:=", True,
        "BasisOrder:=", 1])
    oAn.InsertFrequencySweep("Setup1", ["NAME:Sweep", "IsEnabled:=", True, "RangeType:=", "LinearCount",
        "RangeStart:=", "1GHz", "RangeEnd:=", "8GHz", "RangeCount:=", npts, "Type:=", "Interpolating",
        "SaveFields:=", False, "SaveRadFields:=", False, "InterpTolerance:=", 0.5, "InterpMaxSolns:=", 250,
        "InterpMinSolns:=", 0, "InterpMinSubranges:=", 1, "InterpUseS:=", True, "InterpUsePortImped:=", True,
        "InterpUsePropConst:=", True, "UseDerivativeConvergence:=", False, "InterpDerivTolerance:=", 0.2,
        "UseFullBasis:=", True, "EnforcePassivity:=", True, "PassivityTolerance:=", 0.0001])
    return oDesign


# ---------------- auto-tune helpers ----------------
def read_curve(path):
    f = open(path, "r")
    lines = f.read().splitlines()
    f.close()
    xs = []
    ys = []
    for ln in lines[1:]:
        p = ln.replace('"', "").split(",")
        try:
            xs.append(float(p[0]))
            ys.append(float(p[1]))
        except:
            pass
    mx = max(xs)
    if mx > 1e5:
        xs = [x / 1e9 for x in xs]
    elif mx > 100:
        xs = [x / 1e3 for x in xs]
    return xs, ys


def notch(xs, ys, lo, hi):
    best = None
    for x, y in zip(xs, ys):
        if x >= lo and x <= hi:
            if best is None or y < best[1]:
                best = (x, y)
    return best


def sparam_report(oD, title, c1, c2):
    oD.GetModule("ReportSetup").CreateReport(title, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
        ["Domain:=", "Sweep"], ["Freq:=", ["All"], "Cvar1:=", [c1], "Cvar2:=", [c2]],
        ["X Component:=", "Freq", "Y Component:=", ["dB(S(port2,port1))"]])


def measure(it, k1, k2, cp1, cp2):
    dname = "v9_tune%d" % it
    oD = build_design(dname, k1, k2, cp1, cp2, 701)
    oD.Analyze("Setup1")
    oO = oD.GetModule("Optimetrics")
    oO.InsertSetup("OptiParametric", ["NAME:Tune_hi", "IsEnabled:=", True,
        ["NAME:ProdOptiSetupDataV2", "SaveFields:=", False, "CopyMesh:=", False],
        ["NAME:StartingPoint"], "Sim. Setups:=", ["Setup1"],
        ["NAME:Sweeps",
         ["NAME:SweepDefinition", "Variable:=", "Cvar1", "Data:=", "LIN 0.92pF 1.12pF 0.2pF",
          "OffsetF1:=", False, "Synchronize:=", 1],
         ["NAME:SweepDefinition", "Variable:=", "Cvar2", "Data:=", "LIN 0.46pF 0.56pF 0.1pF",
          "OffsetF1:=", False, "Synchronize:=", 1]],
        ["NAME:Sweep Operations"], ["NAME:Goals"]])
    oO.SolveSetup("Tune_hi")
    tmp = tempfile.gettempdir()
    pa = os.path.join(tmp, "v9_nom_%d.csv" % it)
    pb = os.path.join(tmp, "v9_hi_%d.csv" % it)
    sparam_report(oD, "tune_nom", "%.2fpF" % CNOM1, "%.2fpF" % CNOM2)
    sparam_report(oD, "tune_hi", "%.2fpF" % CHI1, "%.2fpF" % CHI2)
    oR = oD.GetModule("ReportSetup")
    oR.ExportToFile("tune_nom", pa)
    oR.ExportToFile("tune_hi", pb)
    xa, ya = read_curve(pa)
    xb, yb = read_curve(pb)
    n1a = notch(xa, ya, 1.2, 3.7)
    n2a = notch(xa, ya, 3.9, 6.9)
    n1b = notch(xb, yb, 1.2, 3.7)
    n2b = notch(xb, yb, 3.9, 6.9)
    return n1a, n2a, n1b, n2b


def update_stub(k, cp, fa, fb, ca, cb, ft, cpt):
    # fa,fb in GHz at C = ca,cb (pF). Series-LC notch: 1/w^2 = L*(C+Cp)
    wa = 2 * math.pi * fa * 1e9
    wb = 2 * math.pi * fb * 1e9
    Ca = ca * 1e-12
    Cb = cb * 1e-12
    Ltot = (1.0 / (wb * wb) - 1.0 / (wa * wa)) / (Cb - Ca)
    cpeff = 1.0 / (wa * wa * Ltot) - Ca
    cp_new = cp + (cpt * 1e-12 - cpeff) * 1e12
    if cp_new < 0.0:
        cp_new = 0.0
    wt = 2 * math.pi * ft * 1e9
    Lt = 1.0 / (wt * wt * (Ca + cpt * 1e-12))
    if Ltot - LP > 0.05e-9 and Lt - LP > 0.05e-9:
        ratio = (Lt - LP) / (Ltot - LP)
    else:
        ratio = Lt / Ltot
    ratio = max(0.5, min(2.0, ratio))
    k_new = k * math.pow(ratio, 1.0 / 1.4)
    return k_new, cp_new, cpeff * 1e12, Ltot * 1e9


k1, k2, cp1, cp2 = K1, K2, CP1, CP2
if AUTOTUNE:
    best = None
    tuned = []
    for it in range(1, MAX_IT + 1):
        n1a, n2a, n1b, n2b = measure(it, k1, k2, cp1, cp2)
        tuned.append("v9_tune%d" % it)
        e1 = abs(n1a[0] - F1_T)
        e2 = abs(n2a[0] - F2_T)
        k1n, cp1n, cpe1, L1 = update_stub(k1, cp1, n1a[0], n1b[0], CNOM1, CHI1, F1_T, CPT1)
        k2n, cp2n, cpe2, L2 = update_stub(k2, cp2, n2a[0], n2b[0], CNOM2, CHI2, F2_T, CPT2)
        log("v9 tune %d: notch1 %.3f GHz (%.1f dB), notch2 %.3f GHz (%.1f dB) | K1=%.3f K2=%.3f Cp1=%.3f Cp2=%.3f"
            % (it, n1a[0], n1a[1], n2a[0], n2a[1], k1, k2, cp1, cp2))
        score = e1 / F1_T + e2 / F2_T + abs(cpe1 - CPT1) * 0.5 + abs(cpe2 - CPT2) * 0.5
        if best is None or score < best[0]:
            best = (score, k1, k2, cp1, cp2)
        if e1 < 0.012 and e2 < 0.025 and abs(cpe1 - CPT1) < 0.02 and abs(cpe2 - CPT2) < 0.015:
            break
        k1, k2, cp1, cp2 = k1n, k2n, cp1n, cp2n
    k1, k2, cp1, cp2 = best[1], best[2], best[3], best[4]
    log("v9 tuned values: K1=%.4f K2=%.4f CP1=%.4f CP2=%.4f  (copy into the knobs to skip tuning next time)"
        % (k1, k2, cp1, cp2))

# ---------------- final design ----------------
oDesign = build_design("HFSS_meander_v9", k1, k2, cp1, cp2, 281)
oDesign.Analyze("Setup1")

oOpt = oDesign.GetModule("Optimetrics")


def param(name, var, rng):
    oOpt.InsertSetup("OptiParametric", ["NAME:" + name, "IsEnabled:=", True,
        ["NAME:ProdOptiSetupDataV2", "SaveFields:=", False, "CopyMesh:=", False],
        ["NAME:StartingPoint"], "Sim. Setups:=", ["Setup1"],
        ["NAME:Sweeps", ["NAME:SweepDefinition", "Variable:=", var, "Data:=", rng,
                         "OffsetF1:=", False, "Synchronize:=", 0]],
        ["NAME:Sweep Operations"], ["NAME:Goals"]])
    oOpt.SolveSetup(name)


param("Sweep_Cvar1", "Cvar1", "LIN 0.72pF 1.12pF 0.1pF")
param("Sweep_Cvar2", "Cvar2", "LIN 0.36pF 0.56pF 0.05pF")

oRep = oDesign.GetModule("ReportSetup")


def axis(title, lo, hi, step):
    try:
        oRep.ChangeProperty(["NAME:AllTabs", ["NAME:Scaling", ["NAME:PropServers", title + ":AxisY1"],
            ["NAME:ChangedProps",
             ["NAME:Specify Min", "Value:=", True], ["NAME:Min", "Value:=", str(lo)],
             ["NAME:Specify Max", "Value:=", True], ["NAME:Max", "Value:=", str(hi)],
             ["NAME:Specify Spacing", "Value:=", True], ["NAME:Spacing", "Value:=", str(step)]]]])
    except:
        pass


def report(title, var_list, ys, ylo, yhi, ystep):
    oRep.CreateReport(title, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
        ["Domain:=", "Sweep"], var_list, ["X Component:=", "Freq", "Y Component:=", ys])
    axis(title, ylo, yhi, ystep)


report("S11 and S21 (nominal)", ["Freq:=", ["All"], "Cvar1:=", ["0.92pF"], "Cvar2:=", ["0.46pF"]],
       ["dB(S(port1,port1))", "dB(S(port2,port1))"], -60, 0, 10)
report("S21 vs Cvar1 (2.4 GHz notch)", ["Freq:=", ["All"], "Cvar1:=", ["All"], "Cvar2:=", ["0.46pF"]],
       ["dB(S(port2,port1))"], -40, 0, 5)
report("S21 vs Cvar2 (5 GHz notch)", ["Freq:=", ["All"], "Cvar1:=", ["0.92pF"], "Cvar2:=", ["All"]],
       ["dB(S(port2,port1))"], -40, 0, 5)

if AUTOTUNE:                       # tidy: remove the temporary tuning designs
    for nm in tuned:
        try:
            oProject.DeleteDesign(nm)
        except:
            pass
    try:
        oProject.SetActiveDesign("HFSS_meander_v9")
    except:
        pass

try:
    oProject.SaveAs("D:/ansys/HFSS_meander_v9_%s.aedt" % time.strftime("%H%M%S"), True)
except:
    pass
