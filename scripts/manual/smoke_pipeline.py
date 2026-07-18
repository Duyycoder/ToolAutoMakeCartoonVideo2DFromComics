import urllib.request
import json

url = 'http://127.0.0.1:8100/api/pipeline/step1'
payload = {
    'story_name': 'nguoi_lam_nghe_bau_troi_day_sao',
    'source_site': '69shuba',
    'base_url': 'https://www.69shuba.com/txt',
    'story_id': '43372',
    'start_chapter_id': 'Auto',
    'max_chapters': 1,
    'engine': 'gemini_api',
    'gemini_offline_base_url': 'http://localhost:7860/v1',
    'auto_translate': True,
    'continue_download': True
}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        task_key = data['task_key']
        print(f'Started task: {task_key}')
        
        req_sse = urllib.request.Request(f'http://127.0.0.1:8100/api/pipeline/logs/{task_key}')
        with urllib.request.urlopen(req_sse) as sse_res:
            for line in sse_res:
                line = line.decode('utf-8').strip()
                if line:
                    print(line)
except Exception as e:
    print(f'Error: {e}')
