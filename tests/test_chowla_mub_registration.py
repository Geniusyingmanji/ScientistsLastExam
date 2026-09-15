"""The Chowla and MUB resources are discoverable candidates, never default tasks."""

from sle.registry import list_tasks


EXPECTED_CANDIDATES = {
    "Mathematics/ChowlaCosineCertificate": "build_certificate",
    "QuantumFoundations/MutuallyUnbiasedBases6": "build_bases",
}


def test_chowla_and_mub_packages_are_registered_with_their_public_entrypoints():
    inventory = {spec.task_id: spec for spec in list_tasks(None)}
    for task_id, entrypoint in EXPECTED_CANDIDATES.items():
        assert task_id in inventory
        assert inventory[task_id].entrypoint == entrypoint


def test_chowla_and_mub_packages_are_excluded_from_the_default_certified_list():
    certified = {spec.task_id for spec in list_tasks()}
    assert certified.isdisjoint(EXPECTED_CANDIDATES)
