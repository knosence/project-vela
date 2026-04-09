from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "runtime" / "config" / "project-vela.yaml"
VERIFICATION_STATUS_PATH = REPO_ROOT / "runtime" / "config" / "verification-status.json"
APPROVALS_PATH = REPO_ROOT / "runtime" / "config" / "approvals.json"
STARTER_PATH = REPO_ROOT / "knowledge" / "inbox" / "000.Project-Vela-Starter.md"
PROFILE_DIR = REPO_ROOT / "runtime" / "personas"
EVENT_LOG_PATH = REPO_ROOT / "knowledge" / "logs" / "events.jsonl"
PROPOSALS_DIR = REPO_ROOT / "knowledge" / "proposals"
REFS_DIR = REPO_ROOT / "knowledge" / "refs"
QUEUE_DIR = REPO_ROOT / "runtime" / "queues"
MATRIX_INDEX_PATH = REPO_ROOT / "knowledge" / "refs" / "Index.Project-Vela-Matrix-Ref.md"
MATRIX_INDEX_JSON_PATH = REPO_ROOT / "runtime" / "config" / "matrix-index.json"
BACKUP_DIR = REPO_ROOT / "knowledge" / "archive" / "backups"
