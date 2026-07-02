"""Console progress logging for the campaign pipeline. Separate from
usage_tracker (which logs cost to the DB) -- this is stdout-only, so you can
watch a campaign run stage by stage without querying the DB."""
from datetime import datetime


def log(tag: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{tag}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        # Windows console codepages (e.g. cp1252) can't encode characters
        # like em-dashes or curly quotes that show up in LLM-generated
        # score_reason text -- never let a log line crash the pipeline.
        print(line.encode("ascii", errors="replace").decode("ascii"), flush=True)
