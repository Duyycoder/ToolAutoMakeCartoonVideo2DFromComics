from orchestrator.main import chat_mgr


def test_agent_route_intent_l1_query():
    action, args = chat_mgr.route_intent("Truyện này có bao nhiêu video?")
    assert action == "story_report"

    action, args = chat_mgr.route_intent("Danh sách truyện hiện có")
    assert action == "list_stories"

    action, args = chat_mgr.route_intent("Xem trạng thái hệ thống GPU")
    assert action == "system_status"


def test_agent_route_intent_l2_navigation():
    action, args = chat_mgr.route_intent("Chuyển sang truyện Hoả Vân Lộ")
    assert action == "select_story"
    assert args["name"] == "Hoả Vân Lộ"


def test_agent_route_intent_l3_pipeline():
    action, args = chat_mgr.route_intent("Cào và dịch 20 chương")
    assert action == "run_step"
    assert args["n"] == 1
    assert args["max_chapters"] == 20

    action, args = chat_mgr.route_intent("Gen hình ảnh cho truyện")
    assert action == "run_step"
    assert args["n"] == 3


def test_agent_query_execution():
    res = chat_mgr.agent_query("list_stories", {})
    assert res["type"] == "story_list"
    assert "count" in res

    res = chat_mgr.agent_query("system_status", {})
    assert res["type"] == "system_status"
    assert "gpu_weight" in res


def test_agent_route_intent_run_named_step():
    """"Chạy cho tôi bước 1" từng rơi xuống tra tài liệu, trả về đoạn hướng dẫn thay vì chạy."""
    assert chat_mgr.route_intent("Chạy cho tôi bước 1") == ("run_step", {"n": 1})
    assert chat_mgr.route_intent("chạy bước 1 cho 5 chương") == ("run_step", {"n": 1, "max_chapters": 5})
    assert chat_mgr.route_intent("Bắt đầu bước hai") == ("run_step", {"n": 2})
    assert chat_mgr.route_intent("chạy bước 4")[1] == {"n": 4}
    # Câu hỏi về bước thì vẫn để tài liệu trả lời.
    assert chat_mgr.route_intent("Làm sao chạy bước 1?")[0] == "chat"
    assert chat_mgr.route_intent("Bước 1 làm gì")[0] == "chat"
