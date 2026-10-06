"""Run logging + provenance: every script writes a timestamped log and a metadata record, so no result is ambiguous."""
import hashlib, hmac, json, os, platform, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # experiment-2-revision/
PROJECT = ROOT.parent                               # CRE_ML_Console_Final_Artifact_Terbaru/
ARTIFACTS = PROJECT / "course_recommender_artifacts_final"
(ROOT / "logs").mkdir(exist_ok=True); (ROOT / "results").mkdir(exist_ok=True)


def resolve_data_dir():
    d = Path(os.getenv("DATA_DIR", "data")).expanduser()
    return (d if d.is_absolute() else PROJECT / d).resolve()


def md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


class Tee:
    def __init__(self, path):
        self.f = open(path, "a", buffering=1); self.o = sys.__stdout__
    def write(self, s):
        self.o.write(s); self.f.write(s)
    def flush(self):
        self.o.flush(); self.f.flush()
    def isatty(self):
        return False


def now():
    return datetime.now().strftime("%H:%M:%S")


def say(msg):
    print(f"[{now()}] {msg}", flush=True)


def start_run(name, args=None):
    """Tee stdout/stderr to logs/<name>_<timestamp>.log and print a provenance header. Returns (log_path, meta)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = ROOT / "logs" / f"{name}_{stamp}.log"
    sys.stdout = sys.stderr = Tee(log)
    import numpy, pandas, sklearn
    meta = {"run": name, "started": stamp, "command": " ".join(sys.argv), "args": vars(args) if args else {},
            "python": sys.version.split()[0], "platform": platform.platform(),
            "numpy": numpy.__version__, "pandas": pandas.__version__, "sklearn": sklearn.__version__,
            "data_dir": str(resolve_data_dir())}
    try:
        import tensorflow as tf, keras
        meta.update(tensorflow=tf.__version__, keras=keras.__version__,
                    gpus=[g.name for g in tf.config.list_physical_devices("GPU")])
    except Exception as e:  # pragma: no cover
        meta["tensorflow"] = f"unavailable: {e}"
    d = Path(meta["data_dir"])
    meta["data_md5"] = {f.name: md5(f) for f in sorted(d.glob("*.csv"))} if d.exists() else "DATA DIR MISSING"
    print("=" * 78); say(f"RUN {name}   log: {log}")
    for k, v in meta.items():
        print(f"  {k:10s}: {v}")
    print("=" * 78, flush=True)
    return log, meta


def save_json(obj, path):
    Path(path).write_text(json.dumps(obj, indent=2, default=float))
    say(f"wrote {path}")


def user_codes(user_ids):
    """Pseudonym codes identical to scripts/anonymize/generate_pseudonyms.py; None if no salt is set."""
    salt = os.environ.get("CRE_ML_ANON_SALT")
    if not salt:
        return None
    return ["U-" + hmac.new(salt.encode("utf-8"), str(u).encode("utf-8"), hashlib.sha256).hexdigest()[:10] for u in user_ids]


def order_digest(user_ids):
    return hashlib.sha256("|".join(map(str, user_ids)).encode()).hexdigest()[:16]
