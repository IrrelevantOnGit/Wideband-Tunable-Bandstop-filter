# Tunable dual-band bandstop filter (2.4 GHz + 5 GHz), heavy meander.
# Native AEDT script (IronPython 2.7): run via  Tools > Run Script...
# Nominal Cvar1=0.92pF, Cvar2=0.46pF. Sweeps: Cvar1 0.72..1.12 (0.1), Cvar2 0.36..0.56 (0.05).
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
GAP = 0.0          # >0 : copper gap between feed line and stubs (series capacitance)
PAD = 0.20
# Stub trace length (mm) = BASE * K. TUNE HERE:  new K = old K * (f_measured / f_target)^2
# (measure notch at nominal Cvar1=0.92pF / Cvar2=0.46pF). Longer stub -> lower notch.
BASE1, K1, LRUN1, XS1 = 7.8, 1.90, 1.20, -1.50    # stub 1 -> 2.4 GHz
BASE2, K2, LRUN2, XS2 = 3.0, 1.40, 0.80, 0.10     # stub 2 -> 5.0 GHz
SX = 4.0
SY0, SY1 = -1.5, 3.5


def mm(v):
    return "%.4fmm" % v


# ---------------- project / design ----------------
oProject = oDesktop.NewProject()   # always a fresh project -> no name clashes on reruns
oProject.InsertDesign("HFSS", "HFSS_meander_v5", "DrivenModal", "")
oDesign = oProject.SetActiveDesign("HFSS_meander_v5")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oBnd = oDesign.GetModule("BoundarySetup")

# material
oDef = oProject.GetDefinitionManager()
oDef.AddMaterial(   # fresh project, so no name clash
    ["NAME:RO3010_like", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,
     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
     "permittivity:=", str(ER), "dielectric_loss_tangent:=", str(TAND)])

# variables
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


def cu(name, x, y, dx, dy):
    copper.append(rect(name, x, y, H, "Z", dx, dy))


# substrate + ground
oEditor.CreateBox(["NAME:BoxParameters", "XPosition:=", mm(-SX), "YPosition:=", mm(SY0), "ZPosition:=", "0mm",
    "XSize:=", mm(2 * SX), "YSize:=", mm(SY1 - SY0), "ZSize:=", mm(H)], attrs("Sub", "RO3010_like", "(0 128 0)"))
rect("GND", -SX, SY0, 0.0, "Z", 2 * SX, SY1 - SY0)

# feed line
cu("Feed", -SX, -W50 / 2.0, 2 * SX, W50)


def meander(tag, xs, total, lrun):
    # serpentine of total trace length 'total'; last run is trimmed continuously
    yf = W50 / 2.0 + GAP
    y0 = W50 / 2.0 + 0.30
    step = lrun + P
    n = int(total / step) + 1
    last = total - (n - 1) * step
    if last < 0.35 and n > 1:
        n -= 1
        last += step
    cu(tag + "_in", xs, yf, W, y0 - yf + W)
    for i in range(n):
        y = y0 + i * P
        ln = lrun
        if i == n - 1:
            ln = last
        if i % 2 == 0:
            x0 = xs
        else:
            x0 = xs + lrun - ln
        cu("%s_run%d" % (tag, i), x0, y, ln, W)
        if i < n - 1:
            xc = (xs + lrun - W) if (i % 2 == 0) else xs
            cu("%s_con%d" % (tag, i), xc, y, W, P + W)
    ylast = y0 + (n - 1) * P
    if (n - 1) % 2 == 0:
        xp = x0 + ln - PAD
    else:
        xp = x0
    cu(tag + "_pad", xp, ylast, PAD, PAD + W)
    return xp, ylast + PAD + W


p1 = meander("S1", XS1, BASE1 * K1, LRUN1)
p2 = meander("S2", XS2, BASE2 * K2, LRUN2)

# merge copper (result keeps name "Feed") and make PEC
oEditor.Unite(["NAME:Selections", "Selections:=", ",".join(copper)],
              ["NAME:UniteParameters", "KeepOriginals:=", False])
oBnd.AssignPerfectE(["NAME:PerfE_Cu", "Objects:=", ["Feed", "GND"], "InfGroundPlane:=", False])


def add_cap(tag, p, cvar):
    xp, ytop = p
    sh = rect(tag + "_capsheet", xp, ytop, 0.0, "Y", H, PAD)   # XZ plane sheet
    xc = xp + PAD / 2.0
    oBnd.AssignLumpedRLC(["NAME:" + tag + "_C", "Objects:=", [sh],
        ["NAME:CurrentLine", "Start:=", [mm(xc), mm(ytop), "0mm"], "End:=", [mm(xc), mm(ytop), mm(H)]],
        "RLC Type:=", "Parallel",
        "UseResist:=", False, "Resistance:=", "0ohm",
        "UseInduct:=", False, "Inductance:=", "0nH",
        "UseCap:=", True, "Capacitance:=", cvar])


add_cap("S1", p1, "Cvar1")
add_cap("S2", p2, "Cvar2")

# lumped ports
for i, x in enumerate([-SX, SX]):
    nm = "port%d" % (i + 1)
    sh = rect(nm + "_sheet", x, -1.5, 0.0, "X", 3.0, H)        # YZ plane sheet
    oBnd.AssignLumpedPort(["NAME:" + nm, "Objects:=", [sh], "RenormalizeAllTerminals:=", True,
        "DoDeembed:=", False,
        ["NAME:Modes", ["NAME:Mode1", "ModeNum:=", 1, "UseIntLine:=", True,
            ["NAME:IntLine", "Start:=", [mm(x), "0mm", "0mm"], "End:=", [mm(x), "0mm", mm(H)]],
            "CharImp:=", "Zpi"]],
        "ShowReporterFilter:=", False, "ReporterFilter:=", [True], "Impedance:=", "50ohm"])

# air region + radiation
oEditor.CreateRegion(["NAME:RegionParameters",
    "+XPaddingType:=", "Absolute Offset", "+XPadding:=", "3mm",
    "-XPaddingType:=", "Absolute Offset", "-XPadding:=", "3mm",
    "+YPaddingType:=", "Absolute Offset", "+YPadding:=", "3mm",
    "-YPaddingType:=", "Absolute Offset", "-YPadding:=", "3mm",
    "+ZPaddingType:=", "Absolute Offset", "+ZPadding:=", "3mm",
    "-ZPaddingType:=", "Absolute Offset", "-ZPadding:=", "3mm"], attrs("Region"))
oBnd.AssignRadiation(["NAME:Rad1", "Objects:=", ["Region"], "IsFssReference:=", False, "IsForPML:=", False])

# ---------------- setup + sweep (light) ----------------
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

# ---------------- parametric sweeps ----------------
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


def report(title, var_list, ys):
    oRep.CreateReport(title, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
        ["Domain:=", "Sweep"], var_list, ["X Component:=", "Freq", "Y Component:=", ys])


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
