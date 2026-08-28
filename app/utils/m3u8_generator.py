from typing import List
from app.models.channel import Channel

class M3U8Generator:
    def generate_m3u8(self, channels: List[Channel], server_base: str) -> str:
        lines = ["#EXTM3U"]
        for ch in channels:
            line = self._format_channel(ch, server_base)
            lines.append(line)
        return "\n".join(lines)
    
    def _format_channel(self, channel:Channel, server_base: str) -> str:
        if channel.logo:
            extinf = f'#EXTINF:-1 tvg-logo="{channel.logo}" group-title="{channel.group}",{channel.name}'
        else:
            extinf = f'#EXTINF:-1 group-title="{channel.group}",{channel.name}'

        if channel.mode == "proxy":
            final_url = f"{server_base.rstrip('/')}/proxy/{channel.id}/index.m3u8"
        else:
            final_url = channel.url

        return f"{extinf}\n{final_url}"