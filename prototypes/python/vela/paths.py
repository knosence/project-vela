from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "runtime" / "config" / "project-vela.yaml"
VERIFICATION_STATUS_PATH = REPO_ROOT / "runtime" / "config" / "verification-status.json"
APPROVALS_PATH = REPO_ROOT / "runtime" / "config" / "approvals.json"
STARTER_PATH = REPO_ROOT / "knowledge" / "INBOX" / "000.Project-Vela-Starter.md"
INBOX_DIR = REPO_ROOT / "knowledge" / "INBOX"
PROFILE_DIR = REPO_ROOT / "runtime" / "personas"
EVENT_LOG_PATH = REPO_ROOT / "knowledge" / "ARTIFACTS" / "logs" / "events.jsonl"
PATCH_LOG_PATH = REPO_ROOT / "knowledge" / "ARTIFACTS" / "logs" / "Vela-Patch-Log.md"
PROPOSALS_DIR = REPO_ROOT / "knowledge" / "ARTIFACTS" / "proposals"
REFS_DIR = REPO_ROOT / "knowledge" / "ARTIFACTS" / "refs"
QUEUE_DIR = REPO_ROOT / "runtime" / "queues"
MATRIX_INDEX_PATH = REPO_ROOT / "knowledge" / "ARTIFACTS" / "refs" / "Index.Knosence-Matrix-Ref.md"
MATRIX_INDEX_JSON_PATH = REPO_ROOT / "runtime" / "config" / "matrix-index.json"
BACKUP_DIR = REPO_ROOT / "knowledge" / "ARTIFACTS" / "archive" / "backups"
