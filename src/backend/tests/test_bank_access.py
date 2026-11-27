import ast
from pathlib import Path

from app.features.bank_data.tools import READS
from app.features.ledger.service import READ_PATHS

FEATURES = Path(__file__).parents[1] / "app" / "features"
# The ledger reads for the model's tools; documents only stores an upload in the bank.
MAY_CALL_THE_BANK = {"ledger", "documents"}


def _imports_banking(source: Path) -> bool:
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.clients.banking":
            return True
        if isinstance(node, ast.Import) and any(
            alias.name == "app.clients.banking" for alias in node.names
        ):
            return True
    return False


def test_only_the_ledger_reads_the_bank_for_the_model() -> None:
    callers = {
        source.relative_to(FEATURES).parts[0]
        for source in FEATURES.rglob("*.py")
        if _imports_banking(source=source)
    }

    assert callers <= MAY_CALL_THE_BANK


def test_every_bank_data_tool_reads_a_path_the_ledger_allows() -> None:
    allowed = {path.replace("{}", "{x}") for path in READ_PATHS}

    for read in READS:
        fields = read.args.model_fields
        assert read.path.format(**{field: "{x}" for field in fields}) in allowed, read.name
