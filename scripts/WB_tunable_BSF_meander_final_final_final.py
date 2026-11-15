# -*- coding: utf-8 -*-
"""
WB tunable BSF meander - add varactor diodes at the stub ends
Run:  Tools > Run Script  (AEDT Student, IronPython / CPython)
The project with the filter must be OPEN (any project/design may be active - it is searched for).

Only the two stub-end Lumped RLC boundaries are touched:
    S1_C  (end of stub 1)  ->  Varactor_D1   C = Cvar1 + Cp1
    S2_C  (end of stub 2)  ->  Varactor_D2   C = Cvar2 + Cp2
Cvar* = varactor junction capacitance (tuning), Cp* = fixed package/pad capacitance.
Geometry, ports, setup, sweeps and reports are NOT changed.
Safe to run twice (already-renamed boundaries are skipped).
"""
H_SUB = 0.635  # mm

try:
    import ScriptEnv
    ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
except ImportError:
    pass
oDesktop.RestoreWindow()


def msg(text, sev=0):
    oDesktop.AddMessage("", "", sev, text)


def mm(v):
    return "%gmm" % v


JOBS = (("S1_C", "Varactor_D1", "S1_capsheet", (0.38, 1.29, 0), (0.38, 1.29, H_SUB), "Cvar1+Cp1"),
        ("S2_C", "Varactor_D2", "S2_capsheet", (-0.05, -0.71, 0), (-0.05, -0.71, H_SUB), "Cvar2+Cp2"))

found = 0
done = 0
for pname in oDesktop.GetProjectList():
    try:
        oProject = oDesktop.SetActiveProject(pname)
        dnames = oProject.GetTopDesignList()
    except Exception:
        continue
    for dname in dnames:
        try:
            oDesign = oProject.SetActiveDesign(dname)
            oBnd = oDesign.GetModule("BoundarySetup")
            existing = [str(b) for b in oBnd.GetBoundaries()]
        except Exception:
            continue
        for old, new, sheet, start, end, expr in JOBS:
            if new in existing:
                found += 1
                msg("%s / %s: %s already exists - skipped" % (pname, dname, new))
                continue
            if old not in existing:
                continue
            found += 1
            try:
                oBnd.EditLumpedRLC(
                    old,
                    ["NAME:" + new, "Objects:=", [sheet],
                     ["NAME:CurrentLine", "Start:=", [mm(v) for v in start],
                      "End:=", [mm(v) for v in end]],
                     "RLC Type:=", "Parallel", "UseResist:=", False, "Resistance:=", "0ohm",
                     "UseInduct:=", False, "Inductance:=", "0nH", "UseCap:=", True,
                     "Capacitance:=", expr])
                done += 1
                msg("%s / %s: %s -> %s done" % (pname, dname, old, new))
            except Exception as e:
                msg("%s / %s: could not edit %s: %s" % (pname, dname, old, str(e)), 2)

if found == 0:
    msg("No S1_C / S2_C / Varactor_D boundaries found in any open project - open the filter project first.", 2)
