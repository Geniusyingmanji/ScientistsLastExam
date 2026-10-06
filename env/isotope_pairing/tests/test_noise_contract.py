import math
import pytest
from env.isotope_pairing.noise_contract import contrast_uncertainty

def test_analytic_uncertainty_and_multiplicity():
    one=contrast_uncertainty(32)
    assert math.isclose(one['standard_error'],.0005)
    assert math.isclose(one['half_width'],.000979981992270027,rel_tol=1e-10)
    assert contrast_uncertainty(128)['half_width']==one['half_width']/2
    assert contrast_uncertainty(32,3)['half_width']>one['half_width']
    assert one['observations_required']==64

def test_contract_rejects_unsupported_budgets():
    for value in (True,1,129,3.5):
        with pytest.raises(ValueError):contrast_uncertainty(value)
    with pytest.raises(ValueError):contrast_uncertainty(32,0)
    with pytest.raises(ValueError):contrast_uncertainty(32,1,float('nan'))
