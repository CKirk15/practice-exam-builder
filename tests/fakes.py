"""Test doubles for the yt-dlp adapter."""

VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello there\n"


def entry(video_id):
    return {"videoId": video_id, "title": f"T {video_id}",
            "url": f"https://www.youtube.com/watch?v={video_id}", "durationSec": 100}


def chapters(n):
    intro = [{"startSec": 0, "endSec": 10, "title": "Introduction and setup"}]
    return intro + [{"startSec": 10 * i, "endSec": 10 * (i + 1), "title": f"Topic {i} – é"} for i in range(1, n + 1)]


class FakeClient:
    def __init__(self, videos, infos=None, fail=()):
        self.videos, self.infos, self.fail = videos, infos or {}, set(fail)
        self.downloads = []

    def list_playlist(self, url):
        return [entry(v) for v in self.videos]

    def video_info(self, video_id):
        if video_id in self.fail:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        default = {"durationSec": 210, "chapters": chapters(20), "subtitles": [], "automatic_captions": ["en-orig"]}
        return self.infos.get(video_id, default)

    def download_captions(self, video_id, lang, automatic, dest_dir):
        self.downloads.append((video_id, lang, automatic))
        return VTT
