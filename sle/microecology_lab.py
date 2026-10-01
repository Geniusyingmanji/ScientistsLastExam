"""Persistent vessels, public instruments and material transfers for Microecology."""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import numpy as np

from .microecology_kernel import A, B, C, S, X, Y, Z, Mechanism, MicroecologyKernel, VERSION, rng_for
from .world_protocol import API_VERSION, InvalidAction, clone, digest, identifier, keys, number


SPECIES = {"A": A, "B": B, "C": C}
CHANNELS = ("peak-01", "peak-02", "peak-03")
MAX_VESSELS = 32
MAX_HOURS = 240.0


@dataclass
class Vessel:
    identifier: str
    label: str
    state: np.ndarray
    volume_ml: float
    temperature_c: float
    created_at_h: float
    lineage: dict


def validate_initial(value):
    keys(value, ("biomass", "nutrient", "volume_ml", "temperature_c"), ("label",))
    keys(value["biomass"], SPECIES)
    for species, concentration in value["biomass"].items():
        number(concentration, 0, 1, "biomass_" + species)
    number(value["nutrient"], 0, 10, "nutrient")
    number(value["volume_ml"], 1, 100, "volume_ml")
    number(value["temperature_c"], 20, 40, "temperature_c")
    if "label" in value:
        identifier(value["label"])


def public_description():
    return {
        "api_version": API_VERSION, "world_family": "Microecology", "world_version": VERSION,
        "status": "prototype_not_difficulty_calibrated",
        "research_prompt": "Three unfamiliar strains A, B and C inhabit a microcosm. Study this system using experiments; propose findings with evidence and a stated scope.",
        "units": {"biomass": "mmol_C/L", "nutrient": "mmol_C/L", "chemistry": "mmol_C/L", "time": "h", "volume": "mL"},
        "semantics": {
            "world": "Mechanism and parameters remain fixed throughout a session and its confirmation.",
            "time": "Only advance moves time; it advances every existing vessel, including samples.",
            "system": "Finite batch vessels with explicitly accounted nutrient additions and transfers; no unreported inflow.",
            "replicates": "Deterministic dynamics; independent additive measurement noise. No intrinsic biological randomness in v1.",
            "measurement": "Non-destructive idealized assays; explicit sample and transfer operations consume volume.",
            "chemistry": "Three anonymous resolved extracellular fractions; IDs are stable within a world, permuted across instances. No molecular identity is supplied.",
            "depletion": "Idealized selective adsorption removes a chosen fraction without changing volume or other fractions.",
            "feed": "An idealized concentrated nutrient pulse adds carbon with negligible volume change.",
            "transfer": "Removes donor volume, filters out cells, and replaces equal receiver volume. Filtered and displaced material leaves the lab inventory.",
            "noise": {"counts_sigma": 0.002, "chemistry_sigma": 0.004, "nutrient_sigma": 0.004,
                      "distribution": "additive Gaussian, readings clipped at zero; independent measurement streams"},
        },
        "limits": {"vessels": MAX_VESSELS, "simulation_hours": MAX_HOURS, "advance_hours": 48},
        "tools": {
            "create": {"arguments": {"biomass": "A/B/C each in [0,1] mmol_C/L", "nutrient": "[0,10] mmol_C/L", "volume_ml": "[1,100]", "temperature_c": "[20,40]", "label": "optional identifier"}, "cost": 10},
            "advance": {"arguments": {"hours": "(0,48]"}, "cost": "max(1, number of vessels) * ceil(hours / 6)"},
            "measure": {"arguments": {"vessel_id": "existing handle", "instrument": ["counts", "chemistry", "nutrient"]}, "cost": "3 for chemistry; otherwise 2"},
            "sample": {"arguments": {"vessel_id": "existing handle", "volume_ml": ">=0.05; leaves >=0.05 in donor", "cell_free": "boolean", "label": "optional identifier"}, "cost": 3},
            "transfer": {"arguments": {"source_id": "existing handle", "target_id": "different handle", "volume_ml": ">=0.05; leaves >=0.05 in donor, <= receiver volume"}, "cost": 4},
            "feed": {"arguments": {"vessel_id": "existing handle", "amount_mmol": ">0; concentration increment <=5"}, "cost": 2},
            "deplete": {"arguments": {"vessel_id": "existing handle", "channel": list(CHANNELS), "fraction": "[0,1]"}, "cost": 3},
            "set_temperature": {"arguments": {"vessel_id": "existing handle", "temperature_c": "[20,40]"}, "cost": 1},
            "inventory": {"arguments": {}, "cost": 0},
        },
    }


class MicroecologyLab:
    def __init__(self, seed=0, *, mechanism=None, channels=None, measurement_stream="exploration", kernel=None):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("invalid operator seed")
        self._seed = seed
        self.kernel = kernel or MicroecologyKernel(mechanism or Mechanism.generate(seed))
        indices = [X, Y, Z]
        rng_for(seed, "channel-permutation").shuffle(indices)
        self._channels = dict(channels or zip(CHANNELS, indices))
        self._measurement_stream = measurement_stream
        self.time_h = 0.0
        self.vessels = {}
        self.observation_index = 0
        self.imported_carbon = self.exported_carbon = 0.0

    def fresh(self, stream):
        return MicroecologyLab(self._seed, mechanism=self.kernel.mechanism,
                              channels=self._channels, measurement_stream=stream)

    def _vessel(self, handle):
        identifier(handle)
        if handle not in self.vessels:
            raise InvalidAction("unknown_vessel")
        return self.vessels[handle]

    def validate(self, operation, args):
        if operation == "create":
            validate_initial(args)
            if len(self.vessels) >= MAX_VESSELS:
                raise InvalidAction("vessel_limit")
            return 10
        if operation == "advance":
            keys(args, ("hours",))
            hours = number(args["hours"], 1e-6, 48, "hours")
            if self.time_h + hours > MAX_HOURS:
                raise InvalidAction("simulation_time_limit")
            return max(1, len(self.vessels)) * math.ceil(hours / 6)
        if operation == "inventory":
            keys(args, ())
            return 0
        if operation == "transfer":
            keys(args, ("source_id", "target_id", "volume_ml"))
            source, target = self._vessel(args["source_id"]), self._vessel(args["target_id"])
            if source is target:
                raise InvalidAction("same_source_target")
            number(args["volume_ml"], 0.05, min(source.volume_ml - 0.05, target.volume_ml), "volume_ml")
            return 4
        schemas = {
            "measure": (("vessel_id", "instrument"), ()),
            "sample": (("vessel_id", "volume_ml", "cell_free"), ("label",)),
            "feed": (("vessel_id", "amount_mmol"), ()),
            "deplete": (("vessel_id", "channel", "fraction"), ()),
            "set_temperature": (("vessel_id", "temperature_c"), ()),
        }
        if operation not in schemas:
            raise InvalidAction("unknown_operation")
        keys(args, *schemas[operation])
        vessel = self._vessel(args["vessel_id"])
        if operation == "measure":
            if args["instrument"] not in ("counts", "chemistry", "nutrient"):
                raise InvalidAction("unknown_instrument")
            return 3 if args["instrument"] == "chemistry" else 2
        if operation == "sample":
            if len(self.vessels) >= MAX_VESSELS:
                raise InvalidAction("vessel_limit")
            number(args["volume_ml"], 0.05, vessel.volume_ml - 0.05, "volume_ml")
            if type(args["cell_free"]) is not bool:
                raise InvalidAction("invalid_cell_free")
            if "label" in args:
                identifier(args["label"])
            return 3
        if operation == "feed":
            number(args["amount_mmol"], 1e-9, 5 * vessel.volume_ml / 1000, "amount_mmol")
            if vessel.state[S] + args["amount_mmol"] * 1000 / vessel.volume_ml > 50:
                raise InvalidAction("nutrient_capacity")
            return 2
        if operation == "deplete":
            if not isinstance(args["channel"], str) or args["channel"] not in self._channels:
                raise InvalidAction("unknown_channel")
            number(args["fraction"], 0, 1, "fraction")
            return 3
        number(args["temperature_c"], 20, 40, "temperature_c")
        return 1

    def _new(self, state, volume, temperature, label, lineage):
        handle = "vessel-%04d" % (len(self.vessels) + 1)
        self.vessels[handle] = Vessel(handle, label or handle, np.array(state, dtype=float),
                                     volume, temperature, self.time_h, clone(lineage))
        return self._metadata(self.vessels[handle])

    def _metadata(self, vessel):
        return {"vessel_id": vessel.identifier, "label": vessel.label, "volume_ml": vessel.volume_ml,
                "temperature_c": vessel.temperature_c, "created_at_h": vessel.created_at_h,
                "time_h": self.time_h, "lineage": clone(vessel.lineage)}

    def execute(self, operation, args):
        """Atomic operation: failed numerical execution restores state and measurement index."""
        self.validate(operation, args)
        snapshot = copy.deepcopy((self.vessels, self.time_h, self.observation_index,
                                  self.imported_carbon, self.exported_carbon))
        try:
            result = self._execute(operation, args)
            if abs(self.carbon_residual()) > 1e-7:
                raise RuntimeError("material_accounting_failure")
            return clone(result)
        except Exception:
            (self.vessels, self.time_h, self.observation_index,
             self.imported_carbon, self.exported_carbon) = snapshot
            raise

    def _execute(self, operation, args):
        if operation == "inventory":
            return {"time_h": self.time_h, "vessels": [self._metadata(v) for v in self.vessels.values()]}
        if operation == "create":
            state = np.zeros(8)
            state[S] = args["nutrient"]
            for species, index in SPECIES.items():
                state[index] = args["biomass"][species]
            self.imported_carbon += float(state.sum()) * args["volume_ml"] / 1000
            return self._new(state, args["volume_ml"], args["temperature_c"], args.get("label"), {"kind": "fresh_preparation"})
        if operation == "advance":
            for vessel in self.vessels.values():
                vessel.state = self.kernel.advance(vessel.state, args["hours"], vessel.temperature_c)
            self.time_h += args["hours"]
            return {"time_h": self.time_h, "advanced_vessels": len(self.vessels)}
        if operation == "transfer":
            source, target = self._vessel(args["source_id"]), self._vessel(args["target_id"])
            volume = args["volume_ml"]
            incoming = source.state.copy()
            incoming[[A, B, C]] = 0
            self.exported_carbon += float(source.state[[A, B, C]].sum() + target.state.sum()) * volume / 1000
            source.volume_ml -= volume
            fraction = volume / target.volume_ml
            target.state = (1 - fraction) * target.state + fraction * incoming
            target.lineage = {"kind": "supernatant_transfer", "previous_sha256": digest(target.lineage),
                              "source_id": source.identifier, "volume_ml": volume, "time_h": self.time_h}
            return {"source": self._metadata(source), "target": self._metadata(target)}
        vessel = self._vessel(args["vessel_id"])
        if operation == "sample":
            volume = args["volume_ml"]
            state = vessel.state.copy()
            if args["cell_free"]:
                self.exported_carbon += float(state[[A, B, C]].sum()) * volume / 1000
                state[[A, B, C]] = 0
            vessel.volume_ml -= volume
            return self._new(state, volume, vessel.temperature_c, args.get("label"),
                             {"kind": "sample", "source_id": vessel.identifier, "time_h": self.time_h,
                              "cell_free": args["cell_free"]})
        if operation == "feed":
            vessel.state[S] += args["amount_mmol"] * 1000 / vessel.volume_ml
            self.imported_carbon += args["amount_mmol"]
        elif operation == "deplete":
            index = self._channels[args["channel"]]
            self.exported_carbon += vessel.state[index] * args["fraction"] * vessel.volume_ml / 1000
            vessel.state[index] *= 1 - args["fraction"]
        elif operation == "set_temperature":
            vessel.temperature_c = args["temperature_c"]
        elif operation == "measure":
            self.observation_index += 1
            instrument = args["instrument"]
            noise = rng_for(self._seed, "%s:%s:%s" % (self._measurement_stream, instrument, self.observation_index))
            indices = SPECIES if instrument == "counts" else self._channels if instrument == "chemistry" else {"nutrient": S}
            sigma = 0.002 if instrument == "counts" else 0.004
            values = {name: max(0.0, float(vessel.state[index]) + noise.gauss(0, sigma)) for name, index in indices.items()}
            return {"observation_id": "obs-%06d" % self.observation_index, "vessel_id": vessel.identifier,
                    "instrument": instrument, "instrument_version": "1", "time_h": self.time_h,
                    "data_type": "scalar_channels", "units": "mmol_C/L", "values": values,
                    "noise_sigma": sigma, "quality_flags": ["zero_clipped_gaussian"],
                    "lineage": clone(vessel.lineage)}
        return self._metadata(vessel)

    def carbon_residual(self):
        current = sum(float(v.state.sum()) * v.volume_ml / 1000 for v in self.vessels.values())
        return current + self.exported_carbon - self.imported_carbon
