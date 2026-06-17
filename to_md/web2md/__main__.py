"""模块运行入口:支持 `python -m web2md ...` 这种调用方式。

只做一件事 —— 调用 cli.main(),并用其返回码作为进程退出码,
以便在 Shell 脚本中通过 `$?` 判断执行是否成功(0=成功,非 0=失败)。
"""
from __future__ import annotations

import sys

from web2md.cli import main

if __name__ == "__main__":
    # main() 内部已处理所有异常并返回退出码,此处不再额外捕获
    sys.exit(main())
