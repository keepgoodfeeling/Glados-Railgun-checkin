"""定时任务的可选随机延迟；不读取登录凭据。"""

import os
import random
import time


def main():
    raw = os.environ.get("GLADOS_MAX_DELAY_SECONDS", "").strip() or "1800"
    maximum = int(raw)
    if not 0 <= maximum <= 1800:
        raise ValueError("GLADOS_MAX_DELAY_SECONDS 必须在 0 到 1800 之间")
    delay = random.randint(0, maximum)
    print(f"定时签到随机延迟 {delay} 秒（最大 {maximum} 秒）", flush=True)
    time.sleep(delay)


if __name__ == "__main__":
    main()
