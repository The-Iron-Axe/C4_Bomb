import time
import threading
from pynq.overlays.base import BaseOverlay

# --- 1. 全局变量和硬件初始化 ---
base = BaseOverlay("base.bit")
pAudio = base.audio
pAudio.set_volume(50)
audio_lock = threading.Lock()

BEEP_SOUND = "music/beep.wav"
BOOM_SOUND = "music/booming.wav"
DEFUSED_SOUND = "music/defused.wav"
print("音频系统初始化成功。")

PASSWORD = ['BTN3', 'BTN1']
countdown = 40
button_pressed = []
stop_all_threads_event = threading.Event()


# --- 2. 线程函数 ---
def play_accelerating_beep(stop_event):
    """循环播放滴滴声。"""
    sound_interval = 0.9
    MIN_INTERVAL = 0
    SPEED_UP_FACTOR = 0.9
    while not stop_event.is_set():
        with audio_lock:
            pAudio.load(BEEP_SOUND)
            pAudio.play()
        if stop_event.wait(timeout=sound_interval): break
        sound_interval = max(MIN_INTERVAL, sound_interval * SPEED_UP_FACTOR)


def light_show(stop_event):
    """控制LED 0-3 实现跑马灯效果。"""
    path = [0, 1, 2, 3, 2, 1]
    for i in range(4): base.leds[i].off()
    while not stop_event.is_set():
        for led_index in path:
            if stop_event.is_set(): break
            base.leds[led_index].on()
            time.sleep(0.1)
            base.leds[led_index].off()
    for i in range(4): base.leds[i].off()


def led_flash(stop_event):
    """控制RGB LED 4-5，实现越来越急促的红色闪烁效果。"""
    flash_interval = 0.5
    MIN_INTERVAL = 0.05
    SPEED_UP_FACTOR = 0.979
    COLOR = 4  # 红色
    while not stop_event.is_set():
        base.rgbleds[4].write(COLOR)
        base.rgbleds[5].write(COLOR)
        if stop_event.wait(timeout=flash_interval): break
        base.rgbleds[4].off()
        base.rgbleds[5].off()
        if stop_event.wait(timeout=flash_interval): break
        flash_interval = max(MIN_INTERVAL, flash_interval * SPEED_UP_FACTOR)
    base.rgbleds[4].off()
    base.rgbleds[5].off()


def manage_countdown(stop_event):
    """
    管理倒计时。时间到后，将RGB LED变为白色常亮，并播放爆炸声。
    """
    global countdown
    while countdown > 2 and not stop_event.is_set():
        if stop_event.wait(timeout=1): break
        countdown -= 1
        print(f"剩余时间: {countdown} 秒")

    # 检查循环是否因为时间耗尽而自然结束 (而不是因为拆除成功)
    if not stop_event.is_set():
        print("时间到! RGB灯变为白色常亮。")

        # 1. 首先，发出停止信号，让所有其他效果线程（如跑马灯、闪烁灯）停止。
        stop_event.set()

        # 2. 给其他线程一个极短的反应时间，确保 led_flash 线程已退出对LED的控制。
        time.sleep(0.1)

        # 3. 现在，安全地接管RGB LED的控制，并设置为白色常亮 (颜色代码 7)。
        base.rgbleds[4].write(7)
        base.rgbleds[5].write(7)

        # 4. 在白色灯光下，播放最后的爆炸声，并等待其播放完毕。
        with audio_lock:
            pAudio.load(BOOM_SOUND)
            pAudio.play()
            if hasattr(pAudio, '_process') and pAudio._process:
                pAudio._process.wait()


def check_defuse_password(stop_event):
    """检测拆弹密码，并确保成功音效完整播放。"""
    global button_pressed
    last_btn_states = [base.buttons[i].read() for i in range(4)]
    while not stop_event.is_set():
        current_btn3_state = base.buttons[3].read()
        current_btn1_state = base.buttons[1].read()
        if current_btn3_state == 1 and last_btn_states[3] == 0:
            button_pressed.append('BTN3')
            print(f"输入序列: {button_pressed}")
        if current_btn1_state == 1 and last_btn_states[1] == 0:
            button_pressed.append('BTN1')
            print(f"输入序列: {button_pressed}")
        last_btn_states[3] = current_btn3_state
        last_btn_states[1] = current_btn1_state
        if len(button_pressed) >= len(PASSWORD):
            if button_pressed == PASSWORD:
                print("密码正确，已拆除！")
                stop_event.set()
                time.sleep(0.1)
                with audio_lock:
                    pAudio.load(DEFUSED_SOUND)
                    pAudio.play()
                    if hasattr(pAudio, '_process') and pAudio._process:
                        pAudio._process.wait()
                break
            else:
                print(f"密码错误: {button_pressed}。输入已重置。")
                button_pressed = []
        time.sleep(0.05)


# --- 3. 主程序逻辑 ---
def arm_bomb():
    """启动阶段"""
    global button_pressed
    print("-----------------------------------------")
    print("系统就绪。请输入密码来启动定时器。")
    print(f"启动密码: {PASSWORD}")
    print("-----------------------------------------")
    button_pressed = []
    last_btn_states = [base.buttons[i].read() for i in range(4)]
    while True:
        current_btn3_state = base.buttons[3].read()
        current_btn1_state = base.buttons[1].read()
        button_pressed_flag = False
        if current_btn3_state == 1 and last_btn_states[3] == 0:
            button_pressed.append('BTN3')
            button_pressed_flag = True
        if current_btn1_state == 1 and last_btn_states[1] == 0:
            button_pressed.append('BTN1')
            button_pressed_flag = True
        if button_pressed_flag:
            with audio_lock:
                pAudio.load(BEEP_SOUND)
                pAudio.play()
            print(f"启动序列输入: {button_pressed}")
        last_btn_states[1] = current_btn1_state
        last_btn_states[3] = current_btn3_state
        if len(button_pressed) >= len(PASSWORD):
            if button_pressed == PASSWORD:
                print("\n密码正确，定时器已启动！")
                time.sleep(1)
                return
            else:
                print(f"启动序列错误: {button_pressed}。已重置。")
                button_pressed = []
        time.sleep(0.05)


# --- 4. 运行程序 ---
arm_bomb()
button_pressed = []
print("\n-----------------------------------------")
print(f"定时器已激活！你有 {countdown} 秒时间拆除！")
print(f"拆除密码: {PASSWORD}")
print("-----------------------------------------")
threads = [
    threading.Thread(target=manage_countdown, args=(stop_all_threads_event,)),
    threading.Thread(target=check_defuse_password, args=(stop_all_threads_event,)),
    threading.Thread(target=light_show, args=(stop_all_threads_event,)),
    threading.Thread(target=led_flash, args=(stop_all_threads_event,)),
    threading.Thread(target=play_accelerating_beep, args=(stop_all_threads_event,))
]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("\n游戏结束。")

# --- 5. 资源清理 ---
print("正在清理资源...")
for led in base.leds:
    led.off()
for rgbled_index in [4, 5]:
    base.rgbleds[rgbled_index].off()
pAudio.close()
print("清理完成。")