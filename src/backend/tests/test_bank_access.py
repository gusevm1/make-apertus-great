import ast
from pathlib import Path

from app.features.bank_data.tools import READS
from app.features.ledger.service import READ_PATHS
from app.features.payments.service import WRITES
from app.features.payments.tools import WRITE_TOOLS

FEATURES = Path(__file__).parents[1] / "app" / "features"
# The ledger reads for the model's tools; documents only stores an upload in the bank;
# payments changes the bank after the customer's yes.
MAY_CALL_THE_BANK = {"ledger", "documents", "payments"}
# The banking client's methods each feature calls; only payments writes, and its tools ask first.
BANK_CALLS = {
    "ledger": {"get"},
    "documents": {"upload_document", "delete_document"},
    "payments": {"write"},
}


def _imports_banking(source: Path) -> bool:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.clients.banking":
            return True
        if isinstance(node, ast.Import) and any(
            alias.name == "app.clients.banking" for alias in node.names
        ):
            return True
    return False


def _bank_calls(source: Path) -> set[str]:
    """The methods called on `banking` or `self.banking`."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and (
            (isinstance(node.func.value, ast.Name) and node.func.value.id == "banking")
            or (isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "banking")
        )
    }


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


def test_only_payments_writes_to_the_bank() -> None:
    calls: dict[str, set[str]] = {}
    for source in FEATURES.rglob("*.py"):
        used = _bank_calls(source=source)
        if used:
            calls.setdefault(source.relative_to(FEATURES).parts[0], set()).update(used)

    assert calls == BANK_CALLS


def test_every_payment_tool_writes_a_path_the_payments_allow() -> None:
    allowed = {(method, path.replace("{}", "{x}")) for method, path in WRITES}

    for write in WRITE_TOOLS:
        fields = write.args.model_fields
        path = write.path.format(**{field: "{x}" for field in fields})
        assert (write.method, path) in allowed, write.name
