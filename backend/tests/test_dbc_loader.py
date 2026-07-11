from app.dbc.loader import DbcLoader
from app.core.paths import ASSETS_DIR

def test_loader_scans_assets():
    loader = DbcLoader(ASSETS_DIR)
    result = loader.load()
    assert result.file is None or result.file.endswith(".dbc")
    assert isinstance(result.raw_only, bool)
