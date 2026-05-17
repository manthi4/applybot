"""Dashboard package initialisation.

Compatibility shim: some `fasthtml` versions no longer expose a `Card`
symbol. Ensure `fasthtml.common.Card` exists (fallback to `Article`) so
older code continues to import it safely.
"""

try:
    import fasthtml.common as _fh_common
except Exception:
    # If fasthtml isn't installed at import time, do nothing; the
    # ImportError will surface later when the package is actually needed.
    _fh_common = None

if _fh_common is not None and not hasattr(_fh_common, "Card"):
    try:
        # Fallback: alias Card to Article if available
        if hasattr(_fh_common, "Article"):
            setattr(_fh_common, "Card", getattr(_fh_common, "Article"))
    except Exception:
        # Be conservative: if we can't set the attribute, proceed silently.
        pass
