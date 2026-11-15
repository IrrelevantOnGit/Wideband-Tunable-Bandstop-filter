# Tunable dual-band bandstop filter (2.4 GHz + 5 GHz) - compact coiled (spiral-meander) stubs.
# Native AEDT script (IronPython 2.7): run via  Tools > Run Script...
# Both stubs hang off the SAME junction (stub1 above the feed, stub2 below).
# Lumped C to ground at the spiral centre = Cvar + fixed trim cap (Cp1/Cp2, the "artificial capacitance").
# Nominal Cvar1=0.92pF -> 2.4 GHz notch, Cvar2=0.46pF -> 5.0 GHz notch.
import ScriptEnv
import time
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop.RestoreWindow()

# ---------------- knobs (mm) ----------------
H = 0.635          # substrate thickness
ER = 10.2
TAND = 0.0022
W50 = 0.58         # 50 ohm line width
W = 0.12           # spiral trace width
S = 0.10           # spiral turn spacing
PITCH = W + S
# Stub path length (mm) = BASE * K.   TUNE:  K_new = K_old * (f_measured / f_target)^1.3
# (measure nominal notch: longer path -> lower frequency)
D1, BASE1, K1 = 1.20, 5.64, 1.00       # stub 1 (2.4 GHz): outer side, base path length, trim
D2, BASE2, K2 = 0.80, 3.03, 1.00       # stub 2 (5.0 GHz)
CP1, CP2 = "0.18pF", "0.05pF"          # fixed parallel trim capacitance (sets sweep spacing)
XJ = -0.60                             # junction x for both stubs
SX = 4.0
SY0, SY1 = -2.0, 2.8


def mm(v):
    return "%.4fmm" % v


# ---------------- project / design ----------------
oProject = oDesktop.NewProject()   # fresh project -> no name clashes on reruns
oProject.InsertDesign("HFSS", "HFSS_meander_v5", "DrivenModal", "")
oDesign = oProject.SetActiveDesign("HFSS_meander_v5")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oBnd = oDesign.GetModule("BoundarySetup")

oProject.GetDefinitionManager().AddMaterial(
    ["NAME:RO3010_like", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,
     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
     "permittivity:=", str(ER), "dielectric_loss_tangent:=", str(TAND)])

oDesign.ChangeProperty(["NAME:AllTabs", ["NAME:LocalVariableTab", ["NAME:PropServers", "LocalVariables"],
    ["NAME:NewProps",
     ["NAME:Cvar1", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "0.92pF"],
     ["NAME:Cvar2", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "0.46pF"],
     ["NAME:Cp1", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", CP1],
     ["NAME:Cp2", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", CP2]]]])


def attrs(name, mat="vacuum", color="(143 175 143)"):
    return ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color, "Transparency:=", 0,
            "PartCoordinateSystem:=", "Global", "UDMId:=", "", "MaterialValue:=", '"%s"' % mat,
            "SurfaceMaterialValue:=", '""', "SolveInside:=", True, "IsMaterialEditable:=", True,
            "UseMaterialAppearance:=", False, "IsLightweight:=", False]


def rect(name, x, y, z, axis, w, h):
    # axis Z: w along X, h along Y | axis Y: w along Z, h along X | axis X: w along Y, h along Z
    oEditor.CreateRectangle(["NAME:RectangleParameters", "IsCovered:=", True,
        "XStart:=", mm(x), "YStart:=", mm(y), "ZStart:=", mm(z),
        "Width:=", mm(w), "Height:=", mm(h), "WhichAxis:=", axis], attrs(name))
    return name


copper = []

oEditor.CreateBox(["NAME:BoxParameters", "XPosition:=", mm(-SX), "YPosition:=", mm(SY0), "ZPosition:=", "0mm",
    "XSize:=", mm(2 * SX), "YSize:=", mm(SY1 - SY0), "ZSize:=", mm(H)], attrs("Sub", "RO3010_like", "(0 128 0)"))
rect("GND", -SX, SY0, 0.0, "Z", 2 * SX, SY1 - SY0)
copper.append(rect("Feed", -SX, -W50 / 2.0, H, "Z", 2 * SX, W50))


def spiral_pts(x0, y0, D, total):
    # square spiral, counter-clockwise inward; segment k has length D - (k//2)*PITCH; last one trimmed
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


def stub(tag, D, total, sgn):
    ys = W50 / 2.0 + 0.20
    pts = [(XJ, 0.0), (XJ, ys)] + spiral_pts(XJ, ys, D, total)[1:]
    pts = [(x, sgn * y) for (x, y) in pts]            # sgn=-1 -> mirrored below the feed
    for i in range(len(pts) - 1):
        (xa, ya), (xb, yb) = pts[i], pts[i + 1]
        x0 = min(xa, xb) - W / 2.0
        x1 = max(xa, xb) + W / 2.0
        y0 = min(ya, yb) - W / 2.0
        y1 = max(ya, yb) + W / 2.0
        copper.append(rect("%s_s%d" % (tag, i), x0, y0, H, "Z", x1 - x0, y1 - y0))
    return pts


pts1 = stub("S1", D1, BASE1 * K1, 1)
pts2 = stub("S2", D2, BASE2 * K2, -1)

oEditor.Unite(["NAME:Selections", "Selections:=", ",".join(copper)],
              ["NAME:UniteParameters", "KeepOriginals:=", False])
oBnd.AssignPerfectE(["NAME:PerfE_GND", "Objects:=", ["GND"], "InfGroundPlane:=", False])
try:   # finite-conductivity copper -> realistic notch depth (~-30 dB)
    oBnd.AssignFiniteCond(["NAME:Cu_top", "Objects:=", ["Feed"], "UseMaterial:=", True, "Material:=", "copper",
        "UseThickness:=", True, "Thickness:=", "0.035mm", "Roughness:=", "0um", "InfGroundPlane:=", False,
        "IsTwoSided:=", False, "IsInternal:=", True])
except:
    oBnd.AssignPerfectE(["NAME:PerfE_top", "Objects:=", ["Feed"], "InfGroundPlane:=", False])


def add_cap(tag, pts, cexpr):
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    if abs(xb - xa) > 1e-9:                      # last run is horizontal -> sheet in YZ plane
        d = 1.0 if xb > xa else -1.0
        xe = xb + d * W / 2.0
        sh = rect(tag + "_capsheet", xe, yb - W / 2.0, 0.0, "X", W, H)
        st = [mm(xe), mm(yb), "0mm"]
        en = [mm(xe), mm(yb), mm(H)]
    else:                                        # last run is vertical -> sheet in XZ plane
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

# ---------------- setup + sweep ----------------
oAn = oDesign.GetModule("AnalysisSetup")
oAn.InsertSetup("HfssDriven", ["NAME:Setup1", "AdaptMultipleFreqs:=", False, "Frequency:=", "5GHz",
    "MaxDeltaS:=", 0.03, "PortsOnly:=", False, "UseMatrixConv:=", False, "MaximumPasses:=", 8,
    "MinimumPasses:=", 1, "MinimumConvergedPasses:=", 1, "PercentRefinement:=", 30, "IsEnabled:=", True,
    "BasisOrder:=", 1])
oAn.InsertFrequencySweep("Setup1", ["NAME:Sweep", "IsEnabled:=", True, "RangeType:=", "LinearCount",
    "RangeStart:=", "1GHz", "RangeEnd:=", "8GHz", "RangeCount:=", 281, "Type:=", "Interpolating",
    "SaveFields:=", False, "SaveRadFields:=", False, "InterpTolerance:=", 0.5, "InterpMaxSolns:=", 250,
    "InterpMinSolns:=", 0, "InterpMinSubranges:=", 1, "InterpUseS:=", True, "InterpUsePortImped:=", True,
    "InterpUsePropConst:=", True, "UseDerivativeConvergence:=", False, "InterpDerivTolerance:=", 0.2,
    "UseFullBasis:=", True, "EnforcePassivity:=", True, "PassivityTolerance:=", 0.0001])

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

# ---------------- reports ----------------
oRep = oDesign.GetModule("ReportSetup")


def axis(title, which, lo, hi, step):
    try:
        oRep.ChangeProperty(["NAME:AllTabs", ["NAME:Scaling", ["NAME:PropServers", title + ":" + which],
            ["NAME:ChangedProps",
             ["NAME:Specify Min", "Value:=", True], ["NAME:Min", "Value:=", str(lo)],
             ["NAME:Specify Max", "Value:=", True], ["NAME:Max", "Value:=", str(hi)],
             ["NAME:Specify Spacing", "Value:=", True], ["NAME:Spacing", "Value:=", str(step)]]]])
    except:
        pass


def report(title, var_list, ys, ylo, yhi, ystep):
    oRep.CreateReport(title, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
        ["Domain:=", "Sweep"], var_list, ["X Component:=", "Freq", "Y Component:=", ys])
    axis(title, "AxisY1", ylo, yhi, ystep)


report("S11 and S21 (nominal)", ["Freq:=", ["All"], "Cvar1:=", ["0.92pF"], "Cvar2:=", ["0.46pF"]],
       ["dB(S(port1,port1))", "dB(S(port2,port1))"], -60, 0, 10)
report("S21 vs Cvar1 (2.4 GHz notch)", ["Freq:=", ["All"], "Cvar1:=", ["All"], "Cvar2:=", ["0.46pF"]],
       ["dB(S(port2,port1))"], -40, 0, 5)
report("S21 vs Cvar2 (5 GHz notch)", ["Freq:=", ["All"], "Cvar1:=", ["0.92pF"], "Cvar2:=", ["All"]],
       ["dB(S(port2,port1))"], -40, 0, 5)

try:   # unique file name so an already-open earlier run never locks the new one
    oProject.SaveAs("D:/ansys/HFSS_meander_v5_%s.aedt" % time.strftime("%H%M%S"), True)
except:
    pass
