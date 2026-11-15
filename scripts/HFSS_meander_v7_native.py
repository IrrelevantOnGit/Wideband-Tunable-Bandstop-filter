# Tunable dual-band bandstop filter (2.4 GHz + 5 GHz), meandered stubs.
# Native AEDT script (IronPython 2.7): run via  Tools > Run Script...
# Both stubs hang off the SAME junction (stub1 above the feed, stub2 below) -> deep S11 dip between notches
# and no stub-to-stub coupling.  Nominal Cvar1=0.92pF, Cvar2=0.46pF.
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop.RestoreWindow()

# ---------------- knobs (mm) ----------------
H = 0.635          # substrate thickness
ER = 10.2
TAND = 0.0022
W50 = 0.58         # 50 ohm line width
W = 0.08           # meander trace width
P = 0.14           # meander pitch
PAD = 0.20
# Stub trace length (mm) = BASE * K.  TUNE:  K_new = K_old * (f_measured / f_target)^2
# (nominal Cvar1=0.92pF -> 2.4 GHz, Cvar2=0.46pF -> 5.0 GHz).  Longer stub -> lower notch.
BASE1, K1, LRUN1 = 7.8, 2.65, 1.20     # stub 1 -> 2.4 GHz (above feed)
BASE2, K2, LRUN2 = 3.0, 1.75, 0.80     # stub 2 -> 5.0 GHz (below feed)
XJ = -0.60                              # junction x (both stubs start here)
SX = 4.0
SY0, SY1 = -2.5, 3.5


def mm(v):
    return "%.4fmm" % v


# ---------------- project / design ----------------
oProject = oDesktop.NewProject()   # fresh project -> no name clashes on reruns
oProject.InsertDesign("HFSS", "HFSS_meander_v5", "DrivenModal", "")
oDesign = oProject.SetActiveDesign("HFSS_meander_v5")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oBnd = oDesign.GetModule("BoundarySetup")

oDef = oProject.GetDefinitionManager()
oDef.AddMaterial(
    ["NAME:RO3010_like", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,
     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
     "permittivity:=", str(ER), "dielectric_loss_tangent:=", str(TAND)])

oDesign.ChangeProperty(["NAME:AllTabs", ["NAME:LocalVariableTab", ["NAME:PropServers", "LocalVariables"],
    ["NAME:NewProps",
     ["NAME:Cvar1", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "0.92pF"],
     ["NAME:Cvar2", "PropType:=", "VariableProp", "UserDef:=", True, "Value:=", "0.46pF"]]]])


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


def cu(name, x, y, dx, dy, sgn=1):
    # sgn=-1 mirrors the shape to the -y side of the feed line
    if sgn < 0:
        y = -(y + dy)
    copper.append(rect(name, x, y, H, "Z", dx, dy))


oEditor.CreateBox(["NAME:BoxParameters", "XPosition:=", mm(-SX), "YPosition:=", mm(SY0), "ZPosition:=", "0mm",
    "XSize:=", mm(2 * SX), "YSize:=", mm(SY1 - SY0), "ZSize:=", mm(H)], attrs("Sub", "RO3010_like", "(0 128 0)"))
rect("GND", -SX, SY0, 0.0, "Z", 2 * SX, SY1 - SY0)
cu("Feed", -SX, -W50 / 2.0, 2 * SX, W50)


def meander(tag, xs, total, lrun, sgn):
    # serpentine of total trace length 'total'; last run trimmed continuously
    yf = W50 / 2.0
    y0 = W50 / 2.0 + 0.30
    step = lrun + P
    n = int(total / step) + 1
    last = total - (n - 1) * step
    if last < 0.35 and n > 1:
        n -= 1
        last += step
    cu(tag + "_in", xs, yf, W, y0 - yf + W, sgn)
    for i in range(n):
        y = y0 + i * P
        ln = lrun
        if i == n - 1:
            ln = last
        if i % 2 == 0:
            x0 = xs
        else:
            x0 = xs + lrun - ln
        cu("%s_run%d" % (tag, i), x0, y, ln, W, sgn)
        if i < n - 1:
            xc = (xs + lrun - W) if (i % 2 == 0) else xs
            cu("%s_con%d" % (tag, i), xc, y, W, P + W, sgn)
    ylast = y0 + (n - 1) * P
    if (n - 1) % 2 == 0:
        xp = x0 + ln - PAD
    else:
        xp = x0
    cu(tag + "_pad", xp, ylast, PAD, PAD + W, sgn)
    return xp, ylast + PAD + W


p1 = meander("S1", XJ, BASE1 * K1, LRUN1, 1)
p2 = meander("S2", XJ, BASE2 * K2, LRUN2, -1)

oEditor.Unite(["NAME:Selections", "Selections:=", ",".join(copper)],
              ["NAME:UniteParameters", "KeepOriginals:=", False])
oBnd.AssignPerfectE(["NAME:PerfE_GND", "Objects:=", ["GND"], "InfGroundPlane:=", False])
try:   # finite-conductivity copper -> realistic notch depth (~-30 dB)
    oBnd.AssignFiniteCond(["NAME:Cu_top", "Objects:=", ["Feed"], "UseMaterial:=", True, "Material:=", "copper",
        "UseThickness:=", True, "Thickness:=", "0.035mm", "Roughness:=", "0um", "InfGroundPlane:=", False,
        "IsTwoSided:=", False, "IsInternal:=", True])
except:
    oBnd.AssignPerfectE(["NAME:PerfE_top", "Objects:=", ["Feed"], "InfGroundPlane:=", False])


def add_cap(tag, p, cvar, sgn):
    xp, ytop = p
    yt = sgn * ytop
    sh = rect(tag + "_capsheet", xp, yt, 0.0, "Y", H, PAD)   # XZ-plane sheet
    xc = xp + PAD / 2.0
    oBnd.AssignLumpedRLC(["NAME:" + tag + "_C", "Objects:=", [sh],
        ["NAME:CurrentLine", "Start:=", [mm(xc), mm(yt), "0mm"], "End:=", [mm(xc), mm(yt), mm(H)]],
        "RLC Type:=", "Parallel",
        "UseResist:=", False, "Resistance:=", "0ohm",
        "UseInduct:=", False, "Inductance:=", "0nH",
        "UseCap:=", True, "Capacitance:=", cvar])


add_cap("S1", p1, "Cvar1", 1)
add_cap("S2", p2, "Cvar2", -1)

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
    "MaxDeltaS:=", 0.02, "PortsOnly:=", False, "UseMatrixConv:=", False, "MaximumPasses:=", 6,
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

# ---------------- reports (axes like the reference: 1-8 GHz, 0..-40 dB) ----------------
oRep = oDesign.GetModule("ReportSetup")


def axes(title):
    try:
        oRep.ChangeProperty(["NAME:AllTabs", ["NAME:Scaling", ["NAME:PropServers", title + ":AxisY1"],
            ["NAME:ChangedProps",
             ["NAME:Specify Min", "Value:=", True], ["NAME:Min", "Value:=", "-40dB"],
             ["NAME:Specify Max", "Value:=", True], ["NAME:Max", "Value:=", "0dB"],
             ["NAME:Specify Spacing", "Value:=", True], ["NAME:Spacing", "Value:=", "5dB"]]]])
    except:
        pass


def report(title, var_list, ys):
    oRep.CreateReport(title, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
        ["Domain:=", "Sweep"], var_list, ["X Component:=", "Freq", "Y Component:=", ys])
    axes(title)


report("S11 and S21 (nominal)", ["Freq:=", ["All"], "Cvar1:=", ["0.92pF"], "Cvar2:=", ["0.46pF"]],
       ["dB(S(port1,port1))", "dB(S(port2,port1))"])
report("S21 vs Cvar1 (2.4 GHz notch)", ["Freq:=", ["All"], "Cvar1:=", ["All"], "Cvar2:=", ["0.46pF"]],
       ["dB(S(port2,port1))"])
report("S21 vs Cvar2 (5 GHz notch)", ["Freq:=", ["All"], "Cvar1:=", ["0.92pF"], "Cvar2:=", ["All"]],
       ["dB(S(port2,port1))"])

try:
    oProject.SaveAs("D:/ansys/HFSS_meander_v5_auto.aedt", True)
except:
    pass
