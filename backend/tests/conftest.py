import pathlib, sys
import pytest
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

@pytest.fixture
def samples_dir() -> pathlib.Path:
    return ROOT / "samples"


@pytest.fixture(autouse=True, scope="session")
def _isolated_data_dir(tmp_path_factory):
    """Isole les tests de tout dossier de données local (./data, settings.json résiduel)."""
    import os
    d = tmp_path_factory.mktemp("ontoforge-data")
    old = os.environ.get("ONTOFORGE_DATA")
    os.environ.setdefault("ONTOFORGE_DATA", str(d))
    yield
    if old is None and os.environ.get("ONTOFORGE_DATA") == str(d):
        del os.environ["ONTOFORGE_DATA"]
