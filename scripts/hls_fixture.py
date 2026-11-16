"""Owned separate-audio HLS media shared by integration and browser fixtures."""

import subprocess


def grouped_hls(root, source, silent=False):
    for name, stream in (("visual", "v"), ("soundtrack", "a")):
        output = root / f"{name}.m3u8"
        if not output.exists():
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    f"0:{stream}:0",
                    "-c",
                    "copy",
                    "-f",
                    "hls",
                    "-hls_time",
                    "1",
                    "-hls_playlist_type",
                    "vod",
                    str(output),
                ],
                check=True,
            )
    master = root / "separate-audio.m3u8"
    master.write_text(
        "#EXTM3U\n#EXT-X-VERSION:3\n"
        + (
            ""
            if silent
            else '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="1",AUTOSELECT=YES,URI="soundtrack.m3u8",CHANNELS="1"\n'
        )
        + '#EXT-X-STREAM-INF:BANDWIDTH=250000,CODECS="avc1.64000a'
        + ("" if silent else ",mp4a.40.2")
        + '",RESOLUTION=160x90,FRAME-RATE=12.0'
        + ("" if silent else ',AUDIO="audio"')
        + "\nvisual.m3u8\n"
    )
    return master
