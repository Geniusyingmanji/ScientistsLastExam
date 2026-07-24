"""Small, self-contained IAPWS-IF97 implementation for the Rankine oracle.

Only Regions 1, 2 and 4 are implemented.  The cycle contract therefore caps
boiler pressure at 15 MPa and keeps every single-phase state inside those
regions; Region 3 is deliberately unsupported rather than approximated.

Equations and coefficients are transcribed from the IAPWS R7-97(2012) release,
``IF97-Rev.pdf`` (SHA256
``c92f887e989cbf074af1fa982083dc54195d57691eab4fbc950ef6098d4cf1f4``).
Pressure is in MPa, temperature in K, enthalpy in kJ/kg, entropy and heat
capacity in kJ/(kg K), and specific volume in m3/kg.
"""

from __future__ import annotations

import math
from typing import Callable


R = 0.461526
T_MIN = 273.15
T_REGION12 = 623.15
T_MAX_REGION2 = 1073.15
P_TRIPLE_EXTRAPOLATED = 0.000611213
P_CRITICAL = 22.064


_R1_I = (
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3,
    4, 4, 4, 5, 8, 8, 21, 23, 29, 30, 31, 32,
)
_R1_J = (
    -2, -1, 0, 1, 2, 3, 4, 5, -9, -7, -1, 0, 1, 3, -3, 0, 1, 3, 17,
    -4, 0, 6, -5, -2, 10, -8, -11, -6, -29, -31, -38, -39, -40, -41,
)
_R1_N = (
    0.14632971213167,
    -0.84548187169114,
    -3.756360367204,
    0.33855169168385e1,
    -0.95791963387872,
    0.15772038513228,
    -0.16616417199501e-1,
    0.81214629983568e-3,
    0.28319080123804e-3,
    -0.60706301565874e-3,
    -0.18990068218419e-1,
    -0.32529748770505e-1,
    -0.21841717175414e-1,
    -0.52838357969930e-4,
    -0.47184321073267e-3,
    -0.30001780793026e-3,
    0.47661393906987e-4,
    -0.44141845330846e-5,
    -0.72694996297594e-15,
    -0.31679644845054e-4,
    -0.28270797985312e-5,
    -0.85205128120103e-9,
    -0.22425281908000e-5,
    -0.65171222895601e-6,
    -0.14341729937924e-12,
    -0.40516996860117e-6,
    -0.12734301741641e-8,
    -0.17424871230634e-9,
    -0.68762131295531e-18,
    0.14478307828521e-19,
    0.26335781662795e-22,
    -0.11947622640071e-22,
    0.18228094581404e-23,
    -0.93537087292458e-25,
)


_R2_I = (
    1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 6, 6, 6,
    7, 7, 7, 8, 8, 9, 10, 10, 10, 16, 16, 18, 20, 20, 20, 21, 22, 23, 24,
    24, 24,
)
_R2_J = (
    0, 1, 2, 3, 6, 1, 2, 4, 7, 36, 0, 1, 3, 6, 35, 1, 2, 3, 7, 3, 16,
    35, 0, 11, 25, 8, 36, 13, 4, 10, 14, 29, 50, 57, 20, 35, 48, 21, 53,
    39, 26, 40, 58,
)
_R2_N = (
    -0.0017731742473213,
    -0.017834862292358,
    -0.045996013696365,
    -0.057581259083432,
    -0.05032527872793,
    -3.3032641670203e-5,
    -0.00018948987516315,
    -0.0039392777243355,
    -0.043797295650573,
    -2.6674547914087e-5,
    2.0481737692309e-8,
    4.3870667284435e-7,
    -3.227767723857e-5,
    -0.0015033924542148,
    -0.040668253562649,
    -7.8847309559367e-10,
    1.2790717852285e-8,
    4.8225372718507e-7,
    2.2922076337661e-6,
    -1.6714766451061e-11,
    -0.0021171472321355,
    -23.895741934104,
    -5.905956432427e-18,
    -1.2621808899101e-6,
    -0.038946842435739,
    1.1256211360459e-11,
    -8.2311340897998,
    1.9809712802088e-8,
    1.0406965210174e-19,
    -1.0234747095929e-13,
    -1.0018179379511e-9,
    -8.0882908646985e-11,
    0.10693031879409,
    -0.33662250574171,
    8.9185845355421e-25,
    3.0629316876232e-13,
    -4.2002467698208e-6,
    -5.9056029685639e-26,
    3.7826947613457e-6,
    -1.2768608934681e-15,
    7.3087610595061e-29,
    5.5414715350778e-17,
    -9.436970724121e-7,
)
_R2_J0 = (0, 1, -5, -4, -3, -2, -1, 2, 3)
_R2_N0 = (
    -0.96927686500217e1,
    0.10086655968018e2,
    -0.56087911283020e-2,
    0.71452738081455e-1,
    -0.40710498223928,
    0.14240819171444e1,
    -0.43839511319450e1,
    -0.28408632460772,
    0.21268463753307e-1,
)


_SAT_N = (
    0.0,
    0.11670521452767e4,
    -0.72421316703206e6,
    -0.17073846940092e2,
    0.12020824702470e5,
    -0.32325550322333e7,
    0.14915108613530e2,
    -0.48232657361591e4,
    0.40511340542057e6,
    -0.23855557567849,
    0.65017534844798e3,
)


def _finite_positive(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("%s must be finite and positive" % name)
    return value


def region1(temperature_k: float, pressure_mpa: float) -> dict[str, float]:
    """Return stable-liquid Region-1 properties from the fundamental equation."""
    temperature_k = _finite_positive(temperature_k, "temperature")
    pressure_mpa = _finite_positive(pressure_mpa, "pressure")
    if not (T_MIN <= temperature_k <= T_REGION12):
        raise ValueError("Region 1 temperature out of range")
    if pressure_mpa > 100.0:
        raise ValueError("Region 1 pressure out of range")
    tau = 1386.0 / temperature_k
    pi = pressure_mpa / 16.53
    a = 7.1 - pi
    b = tau - 1.222
    gamma = gp = gpp = gt = gtt = gpt = 0.0
    for i, j, n in zip(_R1_I, _R1_J, _R1_N):
        ai = a ** i
        bj = b ** j
        gamma += n * ai * bj
        if i:
            gp -= n * i * a ** (i - 1) * bj
            if i != 1:
                gpp += n * i * (i - 1) * a ** (i - 2) * bj
        if j:
            gt += n * ai * j * b ** (j - 1)
            if j != 1:
                gtt += n * ai * j * (j - 1) * b ** (j - 2)
            if i:
                gpt -= n * i * a ** (i - 1) * j * b ** (j - 1)
    v = pi * gp * R * temperature_k / pressure_mpa / 1000.0
    h = tau * gt * R * temperature_k
    u = (tau * gt - pi * gp) * R * temperature_k
    s = R * (tau * gt - gamma)
    cp = -R * tau * tau * gtt
    denominator = (gp - tau * gpt) ** 2 / (tau * tau * gtt) - gpp
    w = math.sqrt(R * temperature_k * 1000.0 * gp * gp / denominator)
    return {
        "T": temperature_k,
        "P": pressure_mpa,
        "v": v,
        "h": h,
        "u": u,
        "s": s,
        "cp": cp,
        "w": w,
        "region": 1.0,
        "x": 0.0,
    }


def region2(temperature_k: float, pressure_mpa: float) -> dict[str, float]:
    """Return stable-vapor Region-2 properties from the fundamental equation."""
    temperature_k = _finite_positive(temperature_k, "temperature")
    pressure_mpa = _finite_positive(pressure_mpa, "pressure")
    if not (T_MIN <= temperature_k <= T_MAX_REGION2):
        raise ValueError("Region 2 temperature out of range")
    if pressure_mpa > 100.0:
        raise ValueError("Region 2 pressure out of range")
    tau = 540.0 / temperature_k
    pi = pressure_mpa
    go = math.log(pi)
    gop = 1.0 / pi
    gopp = -1.0 / (pi * pi)
    got = gott = 0.0
    for j, n in zip(_R2_J0, _R2_N0):
        go += n * tau ** j
        if j:
            got += n * j * tau ** (j - 1)
            if j != 1:
                gott += n * j * (j - 1) * tau ** (j - 2)
    b = tau - 0.5
    gr = grp = grpp = grt = grtt = grpt = 0.0
    for i, j, n in zip(_R2_I, _R2_J, _R2_N):
        pii = pi ** i
        bj = b ** j
        gr += n * pii * bj
        if i:
            grp += n * i * pi ** (i - 1) * bj
            if i != 1:
                grpp += n * i * (i - 1) * pi ** (i - 2) * bj
        if j:
            grt += n * pii * j * b ** (j - 1)
            if j != 1:
                grtt += n * pii * j * (j - 1) * b ** (j - 2)
            if i:
                grpt += n * i * pi ** (i - 1) * j * b ** (j - 1)
    v = pi * (gop + grp) * R * temperature_k / pressure_mpa / 1000.0
    h = tau * (got + grt) * R * temperature_k
    u = (tau * (got + grt) - pi * (gop + grp)) * R * temperature_k
    s = R * (tau * (got + grt) - (go + gr))
    cp = -R * tau * tau * (gott + grtt)
    numerator = R * temperature_k * 1000.0 * (1.0 + 2.0 * pi * grp + pi * pi * grp * grp)
    denominator = (
        1.0 - pi * pi * grpp
        + (1.0 + pi * grp - tau * pi * grpt) ** 2
        / (tau * tau * (gott + grtt))
    )
    w = math.sqrt(numerator / denominator)
    return {
        "T": temperature_k,
        "P": pressure_mpa,
        "v": v,
        "h": h,
        "u": u,
        "s": s,
        "cp": cp,
        "w": w,
        "region": 2.0,
        "x": 1.0,
    }


def saturation_pressure(temperature_k: float) -> float:
    """Region-4 saturation pressure, Eq. (30), in MPa."""
    temperature_k = _finite_positive(temperature_k, "temperature")
    if not (T_MIN <= temperature_k <= 647.096):
        raise ValueError("saturation temperature out of range")
    n = _SAT_N
    theta = temperature_k + n[9] / (temperature_k - n[10])
    a = theta * theta + n[1] * theta + n[2]
    b = n[3] * theta * theta + n[4] * theta + n[5]
    c = n[6] * theta * theta + n[7] * theta + n[8]
    return (2.0 * c / (-b + math.sqrt(b * b - 4.0 * a * c))) ** 4


def saturation_temperature(pressure_mpa: float) -> float:
    """Region-4 saturation temperature, Eq. (31), in K."""
    pressure_mpa = _finite_positive(pressure_mpa, "pressure")
    if not (P_TRIPLE_EXTRAPOLATED <= pressure_mpa <= P_CRITICAL):
        raise ValueError("saturation pressure out of range")
    n = _SAT_N
    beta = pressure_mpa ** 0.25
    e = beta * beta + n[3] * beta + n[6]
    f = n[1] * beta * beta + n[4] * beta + n[7]
    g = n[2] * beta * beta + n[5] * beta + n[8]
    d = 2.0 * g / (-f - math.sqrt(f * f - 4.0 * e * g))
    return 0.5 * (
        n[10] + d
        - math.sqrt((n[10] + d) ** 2 - 4.0 * (n[9] + n[10] * d))
    )


def saturation_state(pressure_mpa: float) -> dict[str, dict[str, float] | float]:
    """Return Region-1 liquid and Region-2 vapor states below 16.529 MPa."""
    pressure_mpa = _finite_positive(pressure_mpa, "pressure")
    temperature = saturation_temperature(pressure_mpa)
    if temperature > T_REGION12 + 1.0e-9:
        raise ValueError("saturation state would require unimplemented Region 3")
    liquid = region1(temperature, pressure_mpa)
    vapor = region2(temperature, pressure_mpa)
    return {"T": temperature, "liquid": liquid, "vapor": vapor}


def _bisect_property(
    function: Callable[[float], float],
    target: float,
    low: float,
    high: float,
    *,
    iterations: int = 80,
) -> float:
    f_low = function(low) - target
    f_high = function(high) - target
    if abs(f_low) <= 1.0e-12:
        return low
    if abs(f_high) <= 1.0e-12:
        return high
    if f_low * f_high > 0.0:
        raise ValueError("target is outside the supported property interval")
    for _ in range(iterations):
        middle = 0.5 * (low + high)
        f_middle = function(middle) - target
        if f_low * f_middle <= 0.0:
            high = middle
            f_high = f_middle
        else:
            low = middle
            f_low = f_middle
    return 0.5 * (low + high)


def _mixture_state(
    pressure_mpa: float,
    saturation: dict[str, dict[str, float] | float],
    quality: float,
) -> dict[str, float]:
    liquid = saturation["liquid"]
    vapor = saturation["vapor"]
    assert isinstance(liquid, dict) and isinstance(vapor, dict)
    quality = min(1.0, max(0.0, float(quality)))
    result = {
        "T": float(saturation["T"]),
        "P": pressure_mpa,
        "region": 4.0,
        "x": quality,
    }
    for key in ("v", "h", "u", "s"):
        result[key] = liquid[key] + quality * (vapor[key] - liquid[key])
    result["cp"] = math.nan
    result["w"] = math.nan
    return result


def state_ps(pressure_mpa: float, entropy: float) -> dict[str, float]:
    """Return a Region-1/2/4 state from pressure and specific entropy."""
    pressure_mpa = _finite_positive(pressure_mpa, "pressure")
    entropy = float(entropy)
    if not math.isfinite(entropy):
        raise ValueError("entropy must be finite")
    sat = saturation_state(pressure_mpa)
    liquid = sat["liquid"]
    vapor = sat["vapor"]
    assert isinstance(liquid, dict) and isinstance(vapor, dict)
    if liquid["s"] <= entropy <= vapor["s"]:
        return _mixture_state(
            pressure_mpa, sat, (entropy - liquid["s"]) / (vapor["s"] - liquid["s"])
        )
    if entropy < liquid["s"]:
        temperature = _bisect_property(
            lambda t: region1(t, pressure_mpa)["s"],
            entropy,
            T_MIN,
            float(sat["T"]),
        )
        return region1(temperature, pressure_mpa)
    temperature = _bisect_property(
        lambda t: region2(t, pressure_mpa)["s"],
        entropy,
        float(sat["T"]),
        T_MAX_REGION2,
    )
    return region2(temperature, pressure_mpa)


def state_ph(pressure_mpa: float, enthalpy: float) -> dict[str, float]:
    """Return a Region-1/2/4 state from pressure and specific enthalpy."""
    pressure_mpa = _finite_positive(pressure_mpa, "pressure")
    enthalpy = float(enthalpy)
    if not math.isfinite(enthalpy):
        raise ValueError("enthalpy must be finite")
    sat = saturation_state(pressure_mpa)
    liquid = sat["liquid"]
    vapor = sat["vapor"]
    assert isinstance(liquid, dict) and isinstance(vapor, dict)
    if liquid["h"] <= enthalpy <= vapor["h"]:
        return _mixture_state(
            pressure_mpa, sat, (enthalpy - liquid["h"]) / (vapor["h"] - liquid["h"])
        )
    if enthalpy < liquid["h"]:
        temperature = _bisect_property(
            lambda t: region1(t, pressure_mpa)["h"],
            enthalpy,
            T_MIN,
            float(sat["T"]),
        )
        return region1(temperature, pressure_mpa)
    temperature = _bisect_property(
        lambda t: region2(t, pressure_mpa)["h"],
        enthalpy,
        float(sat["T"]),
        T_MAX_REGION2,
    )
    return region2(temperature, pressure_mpa)
