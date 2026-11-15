# -*- coding: utf-8 -*-
# optimize_passband_match.py  -  AEDT / HFSS (Student 2025 R2) :  Tools > Run Script
#
# Run this AFTER build_bandstop_v5.py, on the open HFSS_meander_v5 design.
#
# What it's for: the notches look good, but S11 between them only reaches
# about -2 to -3 dB (confirmed with a quick circuit model: sweeping the
# stub spacing alone cannot fix this - the two varactor-loaded stubs resonate
# fine at their own notch but do nothing for the match in between). Getting
# -15..-20 dB there needs real optimization, not a single hand-picked value,
# so this sets up an Optimetrics Optimization that lets HFSS search several
# geometry variables at once and report back a design it has actually solved.
#
# Free variables given to the optimizer (bounds are generous but physical):
#   wstub     0.6 - 1.4 mm   (stub characteristic impedance)
#   gap_size  0.15 - 0.3 mm  (varactor/DC-block gap -> coupling)
#   pad_l     0.3 - 0.8 mm   (pad length -> added stub reactance)
#   pos2      15.5 - 19.5 mm (spacing between the two stubs -> phase between them)
# Cvar1 / Cvar2 are NOT part of this optimization - they stay at the tuned
# notch values (0.92pF / 0.46pF) so the 2.4 / 5 GHz notches don't drift.
#
# Goal: dB(S(port1,port1)) <= -15 dB over 2.8-4.2 GHz (the mismatched zone),
# while dB(S(port2,port1)) stays <= -20 dB at 2.4 GHz and at 5 GHz (keep the
# notches). Quasi-Newton is used because it's the fastest local optimizer
# available in HFSS Student for a handful of continuous variables; if it
# stalls, rerun it from its last point or switch to "Genetic Algorithm" in
# the Optimetrics dialog for a wider (slower) search.
from __future__ import print_function
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop.RestoreWindow()

DESIGN_NAME = "HFSS_meander_v5"


def log(msg):
    print(msg)
    try:
        oDesktop.AddMessage("", "", 0, msg)
    except Exception:
        pass


oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign(DESIGN_NAME)
oOpt = oDesign.GetModule("Optimetrics")
oRep = oDesign.GetModule("ReportSetup")

# ---- a report the optimizer reads its goals from -----------------------
GOAL_REPORT = "OptGoals"
try:
    if GOAL_REPORT in list(oRep.GetAllReportNames()):
        oRep.DeleteReports([GOAL_REPORT])
except Exception:
    pass
oRep.CreateReport(GOAL_REPORT, "Modal Solution Data", "Rectangular Plot", "Setup1 : Sweep",
                  ["Domain:=", "Sweep"],
                  ["Freq:=", ["All"], "sub_h:=", ["Nominal"], "w50:=", ["Nominal"],
                   "wstub:=", ["Nominal"], "l_stub1:=", ["Nominal"], "l_stub2:=", ["Nominal"],
                   "pos1:=", ["Nominal"], "pos2:=", ["Nominal"], "gap_size:=", ["Nominal"],
                   "pad_l:=", ["Nominal"], "Cvar1:=", ["Nominal"], "Cvar2:=", ["Nominal"]],
                  ["X Component:=", "Freq",
                   "Y Component:=", ["dB(S(port1,port1))", "dB(S(port2,port1))"]])

# ---- optimization setup --------------------------------------------------
try:
    oOpt.DeleteSetups(["OptPassbandMatch"])
except Exception:
    pass

oOpt.InsertSetup("OptiOptimization",
    ["NAME:OptPassbandMatch", "IsEnabled:=", True,
     ["NAME:StartingPoint",
      "wstub:=", "1mm", "gap_size:=", "0.2mm", "pad_l:=", "0.5mm", "pos2:=", "17.45mm"],
     "Optimizer:=", "Quasi Newton",
     "AnalysisStopOptions:=",
     ["NAME:AnalysisStopOptions", "StopForNumIteration:=", True,
      "StopForElapsedTime:=", False, "StopForSlowImprovement:=", True,
      "StopForGrdTolerance:=", False, "MaxNumIteration:=", 40,
      "MaxSolTimeInSec:=", 36000, "RelGradientTolerance:=", 0, "MinNumIteration:=", 10],
     "CostFuncNormType:=", "L2",
     "PlotForVariableReports:=", True,
     "Sim. Setups:=", ["Setup1"],
     ["NAME:Goals",
      ["NAME:Goal", "ReportType:=", "Modal Solution Data", "Solution:=", "Setup1 : Sweep",
       ["NAME:SimValueContext", "Domain:=", "Sweep"],
       "Calculation:=", "dB(S(port1,port1))", "Name:=", "dB(S(port1,port1))",
       ["NAME:Ranges", "Range:=", ["Var:=", "Freq", "Type:=", "rMin", "DiscreteValue:=", "2.8GHz"],
        "Range:=", ["Var:=", "Freq", "Type:=", "rMax", "DiscreteValue:=", "4.2GHz"]],
       "Condition:=", "<=", "GoalValue:=", ["GoalValueType:=", "Single", "Format:=", "Real/Imag",
                                            "bG:=", ["-15"]],
       "Weight:=", "1"],
      ["NAME:Goal", "ReportType:=", "Modal Solution Data", "Solution:=", "Setup1 : Sweep",
       ["NAME:SimValueContext", "Domain:=", "Sweep"],
       "Calculation:=", "dB(S(port2,port1))", "Name:=", "dB(S(port2,port1))_2p4",
       ["NAME:Ranges", "Range:=", ["Var:=", "Freq", "Type:=", "rMin", "DiscreteValue:=", "2.35GHz"],
        "Range:=", ["Var:=", "Freq", "Type:=", "rMax", "DiscreteValue:=", "2.45GHz"]],
       "Condition:=", "<=", "GoalValue:=", ["GoalValueType:=", "Single", "Format:=", "Real/Imag",
                                            "bG:=", ["-20"]],
       "Weight:=", "1"],
      ["NAME:Goal", "ReportType:=", "Modal Solution Data", "Solution:=", "Setup1 : Sweep",
       ["NAME:SimValueContext", "Domain:=", "Sweep"],
       "Calculation:=", "dB(S(port2,port1))", "Name:=", "dB(S(port2,port1))_5p0",
       ["NAME:Ranges", "Range:=", ["Var:=", "Freq", "Type:=", "rMin", "DiscreteValue:=", "4.9GHz"],
        "Range:=", ["Var:=", "Freq", "Type:=", "rMax", "DiscreteValue:=", "5.1GHz"]],
       "Condition:=", "<=", "GoalValue:=", ["GoalValueType:=", "Single", "Format:=", "Real/Imag",
                                            "bG:=", ["-20"]],
       "Weight:=", "1"]],
     ["NAME:Variables",
      "wstub:=", ["Included:=", True, "MinValue:=", "0.6mm", "MaxValue:=", "1.4mm"],
      "gap_size:=", ["Included:=", True, "MinValue:=", "0.15mm", "MaxValue:=", "0.3mm"],
      "pad_l:=", ["Included:=", True, "MinValue:=", "0.3mm", "MaxValue:=", "0.8mm"],
      "pos2:=", ["Included:=", True, "MinValue:=", "15.5mm", "MaxValue:=", "19.5mm"]]])

log("OptPassbandMatch created. Right-click it in Optimetrics and choose Analyze"
    " to run it (about 40 iterations x one solve each - budget time for this)."
    " It leaves Cvar1/Cvar2 untouched so the 2.4/5 GHz notches don't move.")
