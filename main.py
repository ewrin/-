import os
import json
import queue
import threading
import atexit
import tkinter as tk
from tkinter import ttk, messagebox
from openai import OpenAI

# ====== 配置区 ======

API_KEY = os.getenv("OPENAI_API_KEY", "sk-cKLfBxEtDHgGMSu16wry5GRKhqV847REvRvbD5pmLBbxopE1")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://xh.v1api.cc/v1")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# 记忆相关配置
HISTORY_FILE = "chat_history.json"
MAX_MESSAGES = 20   # 最多保留20条消息（即10轮对话）

# ====== 初始化 ======
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
answer_queue = queue.Queue()
messages = []   # 全局对话历史

# ====== 记忆持久化 ======
def load_history():
    """启动时加载历史对话"""
    global messages
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            messages = json.load(f)
    except FileNotFoundError:
        messages = [{"role": "system", "content": "你是一个乐于助人的AI助手。"}]
    except Exception:
        messages = [{"role": "system", "content": "你是一个乐于助人的AI助手。"}]
    trim_messages()

def save_history():
    """保存历史对话到本地文件"""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def trim_messages():
    """裁剪对话历史，保留最近MAX_MESSAGES条"""
    global messages
    if len(messages) > MAX_MESSAGES:
        if messages[0]["role"] == "system":
            messages = [messages[0]] + messages[-(MAX_MESSAGES - 1):]
        else:
            messages = messages[-MAX_MESSAGES:]

# ====== AI 调用 ======
def ask_ai(request_messages):
    """调用模型接口，request_messages 包含完整上下文"""
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=request_messages,
        temperature=0.7,
        stream=False
    )
    return resp.choices[0].message.content

def ask_ai_thread(request_messages):
    """后台线程执行请求"""
    question = request_messages[-1]["content"]
    try:
        answer = ask_ai(request_messages)
        answer_queue.put(("success", question, answer))
    except Exception as e:
        answer_queue.put(("error", question, str(e)))

def check_answer_queue():
    try:
        status, question, data = answer_queue.get_nowait()
    except queue.Empty:
        root.after(100, check_answer_queue)
        return

    if status == "success":
        # 成功时才把用户问题显示到对话记录
        display_user(question)
        # 显示 AI 回答
        display_assistant(data)
        # 更新历史并保存
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": data})
        trim_messages()
        save_history()

        # 成功后才清空输入框并聚焦
        text_box.delete("1.0", tk.END)
        text_box.focus_set()

        status_label.config(text="")
    else:
        # 失败：不清空输入框，问题保留，可修改重试
        messagebox.showerror("请求失败", data)
        status_label.config(text="请求失败，问题已保留")

    submit_btn.config(state=tk.NORMAL)

# ====== 界面显示 ======
def display_user(question):
    answer_text.config(state=tk.NORMAL)
    answer_text.insert(tk.END, f"\n问题：{question}\n", "user")
    answer_text.config(state=tk.DISABLED)
    answer_text.see(tk.END)

def display_assistant(answer):
    answer_text.config(state=tk.NORMAL)
    answer_text.insert(tk.END, f"\n回答：{answer}\n", "assistant")
    answer_text.config(state=tk.DISABLED)
    answer_text.see(tk.END)

def display_history():
    """启动时把历史记录显示在面板中"""
    answer_text.config(state=tk.NORMAL)
    answer_text.delete("1.0", tk.END)
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            answer_text.insert(tk.END, f"\n问题：{content}\n", "user")
        elif role == "assistant":
            answer_text.insert(tk.END, f"\n回答：{content}\n", "assistant")
    answer_text.config(state=tk.DISABLED)
    answer_text.see(tk.END)

def clear_history():
    """清空记忆并重置界面"""
    global messages
    messages = [{"role": "system", "content": "你是一个乐于助人的AI助手。"}]
    save_history()
    answer_text.config(state=tk.NORMAL)
    answer_text.delete("1.0", tk.END)
    answer_text.config(state=tk.DISABLED)
    status_label.config(text="记忆已清空")

# ====== 提交逻辑 ======
def on_submit():
    question = text_box.get("1.0", tk.END).strip()
    if not question:
        messagebox.showwarning("提示", "请输入问题")
        return

    # 构造带上下文的请求消息（不直接修改全局history，防止失败污染）
    request_messages = list(messages)
    request_messages.append({"role": "user", "content": question})

    submit_btn.config(state=tk.DISABLED)
    status_label.config(text="正在等待 AI 回答…")

    t = threading.Thread(target=ask_ai_thread, args=(request_messages,), daemon=True)
    t.start()
    root.after(100, check_answer_queue)

# ====== 窗口关闭时保存 ======
atexit.register(save_history)

# ====== 主窗口 ======
root = tk.Tk()
root.title("AI 问答助手（带记忆）")
root.geometry("700x750")
root.minsize(550, 600)
root.bind("<Return>", lambda e: on_submit())

# 输入面板
input_frame = tk.LabelFrame(root, text="输入问题", font=("Microsoft YaHei", 10))
input_frame.pack(fill="both", padx=10, pady=10)

text_box = tk.Text(input_frame, height=4, wrap="word", font=("Microsoft YaHei", 10))
text_box.pack(fill="both", expand=True, padx=5, pady=5)

# 按钮区
mid_frame = tk.Frame(root)
mid_frame.pack(fill="x", padx=10, pady=5)

submit_btn = ttk.Button(mid_frame, text="提交", command=on_submit)
submit_btn.pack(side="left")

clear_btn = ttk.Button(mid_frame, text="清空记忆", command=clear_history)
clear_btn.pack(side="left", padx=5)

status_label = tk.Label(mid_frame, text="", fg="#2E74B5")
status_label.pack(side="right")

# 回答/历史显示面板
output_frame = tk.LabelFrame(root, text="对话记录", font=("Microsoft YaHei", 10))
output_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

text_frame = tk.Frame(output_frame)
text_frame.pack(fill="both", expand=True, padx=5, pady=5)

answer_text = tk.Text(text_frame, wrap="word", font=("Microsoft YaHei", 10))
scrollbar = ttk.Scrollbar(text_frame, command=answer_text.yview)
answer_text.configure(yscrollcommand=scrollbar.set)
answer_text.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# 设置消息颜色
answer_text.tag_config("user", foreground="#1F4E79")
answer_text.tag_config("assistant", foreground="#2E7D32")

# 初始状态
load_history()
display_history()

root.mainloop()