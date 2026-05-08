"""对分易自动签到程序 —— 桌面版（无控制台窗口）"""

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
