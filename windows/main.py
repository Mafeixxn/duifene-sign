"""对分易自动签到程序 —— 桌面版"""

import sys
import traceback


def main():
    from app import App
    app = App()
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open("error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        print("程序出错，请查看 error.log 文件", file=sys.stderr)
        input("按回车退出...")
