from orchestrator.video_merger import _select_files

def test_select_files_no_only_files():
    mp4_files = ["/a/b/c/1.mp4", "/a/b/c/TongHop_1.mp4", "/a/b/c/2.mp4"]
    result = _select_files(mp4_files, None)
    assert result == ["/a/b/c/1.mp4", "/a/b/c/2.mp4"]

def test_select_files_with_only_files():
    mp4_files = ["/a/b/c/1.mp4", "/a/b/c/2.mp4", "/a/b/c/3.mp4"]
    result = _select_files(mp4_files, ["1.mp4", "3.mp4"])
    assert result == ["/a/b/c/1.mp4", "/a/b/c/3.mp4"]

def test_select_files_path_traversal():
    mp4_files = ["/a/b/c/1.mp4", "/a/b/c/2.mp4"]
    result = _select_files(mp4_files, ["../secret.mp4", "1.mp4", "/etc/passwd.mp4"])
    # only "1.mp4" is a pure basename. The others contain path separators and will be rejected.
    assert result == ["/a/b/c/1.mp4"]

def test_select_files_filter_tonghop_with_only_files():
    mp4_files = ["/a/b/c/TongHop_1.mp4", "/a/b/c/1.mp4"]
    # Even if explicitly requested, TongHop_ should be filtered out
    result = _select_files(mp4_files, ["TongHop_1.mp4", "1.mp4"])
    assert result == ["/a/b/c/1.mp4"]
