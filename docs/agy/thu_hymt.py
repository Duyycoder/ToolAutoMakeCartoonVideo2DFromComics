"""Thử model dịch chuyên dụng hy-mt2 (Hunyuan-MT) qua Ollama: chất lượng + lọt chữ nguồn."""
import json, re, time, urllib.request

URL = "http://localhost:11434/api/generate"


def dich(model, prompt):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.1, "top_p": 0.6, "repeat_penalty": 1.05}}).encode()
    t = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(URL, body, {"Content-Type": "application/json"}), timeout=300))
    return r["response"].strip(), time.time() - t


def prompt_hymt(src_lang_zh, dich_sang, text):
    # Mẫu prompt chính thức của Hunyuan-MT: nguồn/đích có tiếng Trung thì dùng câu lệnh tiếng Trung.
    if src_lang_zh:
        return f"把下面的文本翻译成{dich_sang}，不要额外解释。\n\n{text}"
    return f"Translate the following segment into {dich_sang}, without additional explanation.\n\n{text}"


CAU_ZH = ["师兄，你这一剑已经到了化境，整个宗门没人能接得住。",
          "他冷笑一声：“区区筑基期，也敢在我面前放肆？”",
          "林凡拿出储物戒指，里面装满了灵石和丹药。"]
CAU_VI = ["Anh đã xin nói tôi là tình yêu nói cho cùng nó là sự ngã giá",
          "Lớp bổ túc tâm lý học: lý thuyết kinh tế tình dục của Baumeister và Vohs"]
han = re.compile(r"[㐀-鿿豈-﫿]")
for c in CAU_ZH:
    kq, s = dich("hy-mt2:1.8b", prompt_hymt(True, "越南语", c))
    print(f"[zh→vi {s:.1f}s] lọt Hán={len(han.findall(kq))} | {kq}")
for c in CAU_VI:
    kq, s = dich("hy-mt2:1.8b", prompt_hymt(False, "English", c))
    print(f"[vi→en {s:.1f}s] | {kq}")
