import os, json, logging, sys, time

def configure_json_logging(level: str | int = "INFO"):
    lvl = getattr(logging, str(level).upper(), logging.INFO)
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(lvl)
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            d = {
                "ts": int(time.time()*1000),
                "level": record.levelname,
                "msg": record.getMessage(),
                "name": record.name,
            }
            if record.exc_info:
                d["exc"] = self.formatException(record.exc_info)
            return json.dumps(d, ensure_ascii=False)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    logger.addHandler(h)
    return logger

def maybe_enable():
    if os.getenv("QI_JSON_LOGS","0") == "1":
        configure_json_logging(os.getenv("QI_LOG_LEVEL","INFO"))
