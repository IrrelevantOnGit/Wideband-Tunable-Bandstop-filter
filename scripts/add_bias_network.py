# -*- coding: utf-8 -*-
# add_bias_network.py
# Adds a DC bias network to wideband_bandstop_fixed_v2 (HFSS design "HFSSDesign1").
#
# HOW TO RUN (in Ansys Electronics Desktop):
#   1. Open wideband_bandstop_fixed_v2.aedt and click the HFSS design in the project tree.
#   2. Tools > Run Script...  and pick this file.
#   3. File > Save As...  wideband_bandstop_fixed_v3.aedt
# Run it ONCE on the clean v2 file. Running it twice makes duplicate objects.
#
# WHAT IT BUILDS (for each stage k = 1, 2):
#   gapb<k> + padb<k> : DC-block capacitor (100 pF) in the ground return. The via moves here.
#   btrace<k>         : thin bias trace leaving the varactor pad
#   gapr<k>           : 10 kohm bias resistor (RF choke)
#   bpad<k>           : bias pad. Apply the NEGATIVE bias voltage here.
#   gapd<k> + dpad<k> + viad<k> : 100 pF decoupling capacitor to ground (RF ground for bpad)
# Lumped RLC boundaries: DCblock1/2, BiasRes1/2, Decap1/2.  Metal sheets: boundary PEC_bias.
# Your reports, mesh operation, sweeps, variables and colours are not touched.
# The script only needs the existing design variables: pos1 pos2 w50 l_stub1 l_stub2
# gap_size pad_l sub_h wstub.

import re

try:
    import ScriptEnv
    ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
    oDesktop.RestoreWindow()
except ImportError:
    pass

oProject = oDesktop.GetActiveProject()
oDesign = oProject.GetActiveDesign()
oEditor = oDesign.SetActiveEditor("3D Modeler")
oBnd = oDesign.GetModule("BoundarySetup")

# ---------------------------------------------------------------- helpers
DEFAULTS = {"pos1": 10.0, "pos2": 25.0, "w50": 1.85, "l_stub1": 8.2, "l_stub2": 2.0,
            "gap_size": 0.2, "pad_l": 0.5, "sub_h": 0.813, "wstub": 1.0}
UNIT = {"mm": 1.0, "um": 0.001, "m": 1000.0, "cm": 10.0, "mil": 0.0254}


def var_mm(name):
    """Read a design variable and return its value in mm."""
    try:
        s = str(oDesign.GetVariableValue(name)).strip()
        m = re.match(r"^\s*(-?[0-9.]+(?:e-?[0-9]+)?)\s*([a-z]*)\s*$", s)
        return float(m.group(1)) * UNIT[m.group(2) or "mm"]
    except Exception:
        return DEFAULTS[name]


V = {}
for _n in DEFAULTS:
    V[_n] = var_mm(_n)


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


def sheet(name, xs, ys, w, h):
    """Rectangle sheet at z = sub_h. xs, ys, w, h are expression strings."""
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True, "XStart:=", xs, "YStart:=", ys,
         "ZStart:=", "sub_h", "Width:=", w, "Height:=", h, "WhichAxis:=", "Z"],
        attrs(name, "(230 230 230)", 0.8, "vacuum", True))


def via(name, xc, yc):
    oEditor.CreateCylinder(
        ["NAME:CylinderParameters", "XCenter:=", xc, "YCenter:=", yc, "ZCenter:=", "0mm",
         "Radius:=", "0.15mm", "Height:=", "sub_h", "WhichAxis:=", "Z", "NumSides:=", "0"],
        attrs(name, "(247 242 232)", 0.2, "pec", False))


def lumped(name, obj, x_mm, y_top_mm, y_bot_mm, R=None, C=None):
    z = "%.6fmm" % V["sub_h"]
    oBnd.AssignLumpedRLC(
        ["NAME:" + name, "Objects:=", [obj],
         ["NAME:CurrentLine",
          "Start:=", ["%.6fmm" % x_mm, "%.6fmm" % y_top_mm, z],
          "End:=", ["%.6fmm" % x_mm, "%.6fmm" % y_bot_mm, z]],
         "RLC Type:=", "Serial",
         "UseResist:=", R is not None, "Resistance:=", R or "0ohm",
         "UseInduct:=", False, "Inductance:=", "0nH",
         "UseCap:=", C is not None, "Capacitance:=", C or "0pF"])


# ---------------------------------------------------------------- build
# 1) the two original vias move onto the new DC-block pads, so delete and re-create them
oEditor.Delete(["NAME:Selections", "Selections:=", "via1,via2"])

metal = []
for k in (1, 2):
    p = "pos%d" % k
    ya = "-w50/2-l_stub%d-gap_size-pad_l" % k          # bottom edge of the existing varactor pad
    gs, pl = V["gap_size"], V["pad_l"]
    px = V["pos%d" % k]
    ya_mm = -V["w50"] / 2.0 - V["l_stub%d" % k] - gs - pl

    # DC-block capacitor: gap + pad (0.6 mm wide, left side), via goes under the new pad
    sheet("gapb%d" % k, "%s-wstub/2" % p, ya, "0.6mm", "-gap_size")
    sheet("padb%d" % k, "%s-wstub/2" % p, ya + "-gap_size", "0.6mm", "-pad_l")
    via("via%d" % k, "%s-0.2mm" % p, ya + "-gap_size-pad_l/2")

    # bias feed on the right side: trace, 10 kohm gap, bias pad
    sheet("btrace%d" % k, "%s+0.3mm" % p, ya, "0.2mm", "-2mm")
    sheet("gapr%d" % k, "%s+0.3mm" % p, ya + "-2mm", "0.2mm", "-0.4mm")
    sheet("bpad%d" % k, "%s-0.1mm" % p, ya + "-2.4mm", "1mm", "-1mm")

    # decoupling capacitor from the bias pad to ground
    sheet("gapd%d" % k, "%s-0.1mm" % p, ya + "-3.4mm", "1mm", "-0.2mm")
    sheet("dpad%d" % k, "%s-0.1mm" % p, ya + "-3.6mm", "1mm", "-0.5mm")
    via("viad%d" % k, "%s+0.4mm" % p, ya + "-3.6mm-0.25mm")

    metal += ["padb%d" % k, "btrace%d" % k, "bpad%d" % k, "dpad%d" % k]

    # lumped elements (current line runs across the gap, along -y)
    lumped("DCblock%d" % k, "gapb%d" % k, px - 0.2, ya_mm, ya_mm - gs, R="0.1ohm", C="100pF")
    lumped("BiasRes%d" % k, "gapr%d" % k, px + 0.4, ya_mm - 2.0, ya_mm - 2.4, R="10kohm")
    lumped("Decap%d" % k, "gapd%d" % k, px + 0.4, ya_mm - 3.4, ya_mm - 3.6, R="0.1ohm", C="100pF")

# 2) metal sheets of the bias network become perfect conductors
oBnd.AssignPerfectE(["NAME:PEC_bias", "Objects:=", metal, "InfGroundPlane:=", False])

log("Bias network added. Now run HFSS > Validation Check, then File > Save As v3.")
