import os

os.environ.setdefault("CLAIMSIGHT_LLM_PROVIDER", "deterministic")
os.environ.setdefault("CLAIMSIGHT_FORCE_MEMORY", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./claimsight-ci.db")
os.environ.setdefault("CLAIMSIGHT_QA_SAMPLE_RATE", "0")
os.environ.setdefault("CLAIMSIGHT_VAULT_KEY", "ci-vault-key")
os.environ.setdefault("CLAIMSIGHT_RATE_LIMIT", "0")
