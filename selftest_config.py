# -*- coding: utf-8 -*-
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\pm\soft\21day_system"

CASES = {
    "нет ключа": {},
    "ROUTERAI_API_KEY": {"ROUTERAI_API_KEY": "sk-test-123"},
    "OPENAI_API_KEY": {"OPENAI_API_KEY": "sk-test-123"},
    "ROUTERAI + своя модель": {"ROUTERAI_API_KEY": "sk-test-123",
                               "ROUTERAI_MODEL": "anthropic/claude-sonnet-4.6"},
    "LLM_API_KEY": {"LLM_API_KEY": "sk-test-123"},
}

for label, vars_ in CASES.items():
    env = {"PATH": os.environ["PATH"], "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    env.update(vars_)
    code = ("import config;"
            "print('enabled=%s key=%r url=%s model=%s' % "
            "(config.LLM_ENABLED, config.LLM_KEY_NAME, config.OPENAI_BASE_URL,"
            " config.OPENAI_MODEL))")
    out = subprocess.run([sys.executable, "-c", code], cwd=BASE, env=env,
                         capture_output=True, text=True, encoding="utf-8")
    print(f"[{label}] {out.stdout.strip() or out.stderr.strip()}")
