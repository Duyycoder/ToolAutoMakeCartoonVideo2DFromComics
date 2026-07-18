import queue

from orchestrator.pipeline import NovelPipeline
from orchestrator.process_manager import ProcessManager


class _Storage:
    def __init__(self):
        self.meta = {"status": "VIDEO_GENERATING", "pipeline_step": 2}

    def read_story_meta(self, _story_name):
        return dict(self.meta)

    def write_story_meta(self, _story_name, meta):
        self.meta = dict(meta)


def test_merge_failure_marks_video_failed(monkeypatch, tmp_path):
    storage = _Storage()
    processes = ProcessManager()
    processes.log_queues["story_step3"] = queue.Queue()
    pipeline = NovelPipeline(storage, processes)
    monkeypatch.setattr(
        "orchestrator.video_merger.merge_videos", lambda *_args, **_kwargs: False)

    success = pipeline._finalize_video_task(
        "Story", str(tmp_path), "story_step3", exit_code=0)

    assert success is False
    assert storage.meta["status"] == "VIDEO_FAILED"
    assert storage.meta["pipeline_step"] == 2


def test_successful_merge_marks_video_generated(monkeypatch, tmp_path):
    storage = _Storage()
    processes = ProcessManager()
    processes.log_queues["story_step3"] = queue.Queue()
    pipeline = NovelPipeline(storage, processes)
    monkeypatch.setattr(
        "orchestrator.video_merger.merge_videos", lambda *_args, **_kwargs: True)

    success = pipeline._finalize_video_task(
        "Story", str(tmp_path), "story_step3", exit_code=0)

    assert success is True
    assert storage.meta["status"] == "VIDEO_GENERATED"
    assert storage.meta["pipeline_step"] == 3
