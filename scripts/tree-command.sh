#!/bin/bash

tree -a -I '.git|.venv|venv|node_modules|__pycache__|.mypy_cache|.pytest_cache|.next|.expo|dist|build|.cache|downloads|tmp|data/files' > tree_full.txt