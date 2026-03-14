from omegaconf import OmegaConf
import logging.config
import os

def setup_logging(cfg):
    logging_cfg = OmegaConf.to_container(cfg.logging, resolve=False)
    log_dir = os.path.expanduser(cfg.logging.log_dir)
    
    file_handler = logging_cfg["handlers"]["file"]
    file_handler["filename"] = file_handler["filename"].format(
        log_dir=log_dir
    )

    # Ensure directory exists
    os.makedirs(os.path.dirname(file_handler["filename"]), exist_ok=True)

    logging.config.dictConfig(logging_cfg)

def sep(c: str, n: int=55) -> str:
    return c * n