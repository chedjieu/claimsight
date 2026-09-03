# services/phi_guard — de-identification

Redact names, MRNs, SSNs, DOB, emails, phones, addresses **before** any model-shaped prompt.

Re-identification map is **Fernet-sealed** on the claim row (`vault.py`) and used only for audited `hydrate=true` (medical director). Never sent to the LLM layer.

Also scans prompt-injection phrases in source documents.

```python
from claimsight_phi_guard import PhiGuard
PhiGuard().redact_text("Elena Vasquez MRN-448291")
```

## What this is not

Not Presidio in-process (Presidio-style regex/NER). Not a HIPAA-certified vault. Synthetic fixtures only.
