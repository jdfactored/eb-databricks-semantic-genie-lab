"""
Register every test module so `test_runner` can import it by name.

Notebook `01-semantic-layer-and-metric-views.ipynb` -> `semantic_layer_and_metric_views_tests.py`.
"""

from . import semantic_layer_and_metric_views_tests
from . import genie_agents_tests
from . import genie_vs_raw_tables_tests
from . import genie_ontology_and_genie_one_tests

__all__ = [
    "semantic_layer_and_metric_views_tests",
    "genie_agents_tests",
    "genie_vs_raw_tables_tests",
    "genie_ontology_and_genie_one_tests",
]
