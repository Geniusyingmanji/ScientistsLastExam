"""Operator-only independent complex-impedance reference; no kernel imports."""

import cmath
import math


def spectrum(parameters, spec):
    """Trusted validated inputs. Direct KCL, independent of state-space assembly."""
    result = []
    for frequency in spec["frequencies_hz"]:
        omega = 2*math.pi*frequency
        admittance = complex(1/parameters.leakage_ohm)
        for branch in parameters.branches:
            impedance = branch.resistance + 1j*(omega*branch.inductance - 1/(omega*branch.capacitance))
            admittance += 1/impedance
        voltage = spec["amplitude_v"]/(1 + spec["source_ohm"]*(1/spec["load_ohm"] + admittance))
        if not (cmath.isfinite(voltage)):
            raise RuntimeError("independent impedance reference became nonfinite")
        result.append([voltage.real, voltage.imag])
    return result

