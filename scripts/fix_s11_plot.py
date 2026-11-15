# -*- coding: utf-8 -*-
# fix_s11_plot.py  -  AEDT / HFSS (Student 2025 R2) :  Tools > Run Script
#
# Replaces the cluttered "S Parameter Plot1" (S11 + S21 for every Cvar1/Cvar2
# combination = 26 overlapping traces) with three readable plots:
#   1. S11 & S21 at the nominal tuning state, 1-8 GHz, -40..0 dB, labelled axes
#   2. S21 family vs Cvar1  (Cvar2 fixed at nominal)  -> moves the 2.4 GHz notch
#   3. S21 family vs Cvar2  (Cvar1 fixed at nominal)  -> moves the 5 GHz notch
# and prints the notch frequencies / depths it finds in the nominal curve.
#
# Run it with the solved design open (Setup1 : Sweep must exist).
from __future__ import print_function
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop.RestoreWindow()

SETUP        = "Setup1 : Sweep"
OLD_PLOT     = "S Parameter Plot1"      # cluttered plot to remove
F_MIN, F_MAX = "1GHz", "8GHz"
Y_MIN, Y_MAX = "-40", "0"
TARGETS_GHZ  = (2.4, 5.0)


def log(msg):
    print(msg)
    try:
        oDesktop.AddMessage("", "", 0, msg)
    except Exception:
        pass


oProject = oDesktop.GetActiveProject()
oDesign  = oProject.GetActiveDesign()
oRep     = oDesign.GetModule("ReportSetup")


def variations(**swept):
    """Freq=All, every design variable Nominal unless listed in swept."""
    out = ["Freq:=", ["All"]]
    try:
        names = list(oDesign.GetVariables())
    except Exception:
        names = ["sub_h", "w50", "wstub", "l_stub1", "l_stub2", "pos1", "pos2",
                 "gap_size", "pad_l", "Cvar1", "Cvar2"]
    for n in names:
        out += [n + ":=", swept.get(n, ["Nominal"])]
    return out


def prop(tab, server, changed):
    oRep.ChangeProperty(["NAME:AllTabs",
                         ["NAME:" + tab, "PropServers:=", [server],
                          ["NAME:ChangedProps"] + changed]])


def tidy(title, ytitle, trace_colors=None):
    """Cosmetics. Each call is optional - a failure never stops the script."""
    steps = [
        ("Scaling", title + ":AxisY1", [["NAME:Min", "Value:=", Y_MIN],
                                        ["NAME:Max", "Value:=", Y_MAX],
                                        ["NAME:Spacing", "Value:=", "5"]]),
        ("Scaling", title + ":AxisX",  [["NAME:Min", "Value:=", F_MIN],
                                        ["NAME:Max", "Value:=", F_MAX],
                                        ["NAME:Spacing", "Value:=", "0.5GHz"]]),
        ("Header", title + ":Header",  [["NAME:Title", "Value:=", title]]),
    ]
    for tab, server, props in steps:
        try:
            prop(tab, server, props)
        except Exception:
            pass
    for trace, (r, g, b) in (trace_colors or {}).items():
        for key in ("Line Color", "Color"):
            try:
                prop("Attributes", title + ":" + trace,
                     [["NAME:" + key, "R:=", r, "G:=", g, "B:=", b]])
                break
            except Exception:
                pass
    for f in TARGETS_GHZ:                       # vertical markers at 2.4 / 5 GHz
        try:
            oRep.AddCartesianXMarker(title, "%sGHz" % f)
        except Exception:
            pass


def plot(title, ycomps, ytitle, colors=None, **swept):
    try:
        if title in list(oRep.GetAllReportNames()):
            oRep.DeleteReports([title])
    except Exception:
        pass
    oRep.CreateReport(title, "Modal Solution Data", "Rectangular Plot", SETUP,
                      ["Domain:=", "Sweep"], variations(**swept),
                      ["X Component:=", "Freq", "Y Component:=", ycomps])
    tidy(title, ytitle, colors)


def notch_report(title):
    """Export the nominal plot to CSV and print the S21 notches."""
    import os, csv, tempfile
    path = os.path.join(tempfile.gettempdir(), "bandstop_nominal.csv")
    try:
        oRep.ExportToFile(title, path)
        rows = list(csv.reader(open(path, "r")))
        head = [h.replace('"', '') for h in rows[0]]
        ci = [i for i, h in enumerate(head) if "port2,port1" in h][0]
        data = [(float(r[0]), float(r[ci])) for r in rows[1:] if len(r) > ci]
        for i in range(1, len(data) - 1):
            if data[i][1] < -10 and data[i][1] <= data[i-1][1] and data[i][1] <= data[i+1][1]:
                log("S21 notch: %.3f GHz  (%.1f dB)" % (data[i][0], data[i][1]))
        for t in TARGETS_GHZ:
            f, v = min(data, key=lambda d: abs(d[0] - t))
            log("S21 at %.2f GHz = %.1f dB" % (t, v))
    except Exception as e:
        log("notch report skipped: %s" % e)


# ---- remove the old, cluttered plot ---------------------------------------
try:
    if OLD_PLOT in list(oRep.GetAllReportNames()):
        oRep.DeleteReports([OLD_PLOT])
except Exception:
    pass

# ---- new plots -------------------------------------------------------------
NOM = "S11 and S21 (nominal)"
plot(NOM, ["dB(S(port1,port1))", "dB(S(port2,port1))"], "dB",
     colors={"dB(S(port1,port1))": (0, 90, 255), "dB(S(port2,port1))": (230, 0, 0)})
plot("S21 vs Cvar1 (2.4 GHz notch)", ["dB(S(port2,port1))"], "dB", Cvar1=["All"])
plot("S21 vs Cvar2 (5 GHz notch)",   ["dB(S(port2,port1))"], "dB", Cvar2=["All"])
notch_report(NOM)
log("fix_s11_plot: done")
