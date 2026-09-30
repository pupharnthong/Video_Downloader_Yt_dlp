# app.py  —  pip install pywebview yt-dlp   (+ ffmpeg ใน PATH)
# วางไฟล์วิดีโอพื้นหลังชื่อ bg.mp4 ไว้โฟลเดอร์เดียวกับ app.py
import os, base64, webview, yt_dlp

HERE = os.path.dirname(os.path.abspath(__file__))

def bg_src():
    p = os.path.join(HERE, "bg.mp4")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return "data:video/mp4;base64," + base64.b64encode(f.read()).decode()
    return "https://www.pexels.com/download/video/36189491/"

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:Inter,sans-serif}
html,body{height:100%;overflow:hidden;color:#1a1a1a}

/* ---- ทุกอย่างสเกลตามขนาดหน้าต่าง ---- */
:root{--u:clamp(11px,1.25vw,17px)}

#bg{position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:-2}
.veil{position:fixed;inset:0;z-index:-1;
 background:linear-gradient(180deg,rgba(245,243,240,.85) 0%,rgba(245,243,240,.45) 30%,rgba(0,0,0,0) 60%)}

.hero{position:relative;height:100%;display:flex;flex-direction:column;align-items:center;
 justify-content:flex-start;padding:15vh 4vw 4vh;text-align:center;gap:calc(var(--u)*.7)}
.badge{background:rgba(255,255,255,.75);backdrop-filter:blur(8px);border-radius:999px;
 padding:.5em 1.2em;font-size:calc(var(--u)*.78);box-shadow:0 2px 10px rgba(0,0,0,.08)}
h1{font-size:clamp(30px,5.2vw,68px);letter-spacing:-.04em;line-height:1.05;margin-top:.2em}
p.sub{font-size:calc(var(--u)*1.02);color:#3c3c3c;line-height:1.5}

.bar{margin-top:calc(var(--u)*1.4);display:flex;flex-wrap:wrap;justify-content:center;
 gap:calc(var(--u)*.6);width:min(92vw,720px)}
input{flex:1 1 240px;min-width:180px;border:0;border-radius:999px;padding:1em 1.5em;
 font-size:calc(var(--u)*.85);outline:none;background:rgba(255,255,255,.92);box-shadow:0 4px 18px rgba(0,0,0,.12)}
select{border:0;border-radius:999px;padding:0 1em;background:rgba(255,255,255,.92);
 font-size:calc(var(--u)*.8);outline:none}
button{border:0;border-radius:999px;padding:1em 1.6em;font-size:calc(var(--u)*.85);
 font-weight:600;cursor:pointer;white-space:nowrap}
button.ghost{background:#fff;box-shadow:0 4px 18px rgba(0,0,0,.14)}

.glow{position:relative;color:#fff;background:#2b1a5e;isolation:isolate;
 padding:1em 2em;transition:transform .18s ease}
.glow:before{content:'';position:absolute;inset:0;border-radius:inherit;z-index:-1;
 background:linear-gradient(90deg,#7c3aed,#a855f7,#c084fc,#8b5cf6,#7c3aed);
 background-size:300% 100%;animation:slide 4s linear infinite}
.glow:after{content:'';position:absolute;inset:-6px;border-radius:inherit;z-index:-2;filter:blur(18px);
 opacity:.55;background:linear-gradient(90deg,#7c3aed,#c084fc,#8b5cf6);background-size:300% 100%;
 animation:slide 4s linear infinite;transition:opacity .25s ease}
@keyframes slide{to{background-position:300% 0}}
.glow:hover{transform:translateY(-2px) scale(1.04)}
.glow:hover:after{opacity:1;inset:-10px}
.glow:active{transform:translateY(1px) scale(.98)}

#status{margin-top:calc(var(--u)*.9);font-size:calc(var(--u)*.8);color:#333;min-height:1.4em}

/* หน้าต่างเตี้ยมาก -> บีบระยะบนให้ไม่ล้น */
@media (max-height:520px){.hero{padding-top:6vh}}
</style></head><body>
<video id="bg" autoplay muted loop playsinline src="__BG__"></video>
<div class="veil"></div>

<div class="hero">
  <div class="badge">Video + Audio merged</div>
  <h1>Youtube Video Downloader.</h1>
  <p class="sub">Paste a link, pick a resolution, and get a clean MP4.<br>So you can take a breath.</p>
  <div class="bar">
    <input id="url" placeholder="https://youtu.be/...">
    <select id="q"><option>Best</option><option>1080p</option><option>720p</option><option>480p</option><option>Audio only</option></select>
    <button class="ghost" onclick="fetchInfo()">Fetch</button>
    <button class="glow" onclick="dl()">Download</button>
  </div>
  <div id="status"></div>
</div>

<script>
const s=t=>document.getElementById('status').innerText=t;
async function fetchInfo(){s('Fetching...');s(await pywebview.api.info(url.value))}
async function dl(){s('Downloading...');s(await pywebview.api.download(url.value,q.value))}
</script></body></html>
""".replace("__BG__", bg_src())

class Api:
    def info(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as y:
                d = y.extract_info(url, download=False)
            return f"{d['title']} · {d['duration']//60}:{d['duration']%60:02d}"
        except Exception as e:
            return f"Error: {e}"

    def download(self, url, q):
        out = os.path.join(os.path.expanduser("~"), "Downloads", "%(title)s.%(ext)s")
        fmt = {'Best': 'bv*+ba/b', '1080p': 'bv*[height<=1080]+ba/b',
               '720p': 'bv*[height<=720]+ba/b', '480p': 'bv*[height<=480]+ba/b',
               'Audio only': 'ba'}[q]
        opts = {'format': fmt, 'outtmpl': out, 'merge_output_format': 'mp4', 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                y.download([url])
            return "Done — saved to your Downloads folder."
        except Exception as e:
            return f"Error: {e}"

webview.create_window("Video Downloader", html=HTML, js_api=Api(),
                      width=1200, height=880, min_size=(560, 420),
                      resizable=True, maximized=False)
webview.start()