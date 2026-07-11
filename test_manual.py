import sys; sys.path.insert(0, '.')
from orchestrator.storage import StorageManager
from orchestrator.process_manager import ProcessManager
from orchestrator.pipeline import NovelPipeline
sm = StorageManager('storage')
pm = ProcessManager()
pipe = NovelPipeline(sm, pm)
print(pipe.start_step_1_crawl_translate('nguoi_lam_nghe_bau_troi_day_sao', {'source': '69shuba', 'story_id': '43372', 'start_chapter_id': 'Auto', 'continue_download': True, 'num_chapters': 1}, {'auto_translate': True, 'engine': 'gemini_api', 'gemini_offline_base_url': 'http://localhost:7860/v1'}))
