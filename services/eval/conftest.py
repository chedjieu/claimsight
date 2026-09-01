import os

os.environ.setdefault("CLAIMSIGHT_LLM_PROVIDER", "deterministic")
os.environ.setdefault("CLAIMSIGHT_FORCE_MEMORY", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./claimsight-ci.db")
