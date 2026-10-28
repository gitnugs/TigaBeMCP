"""Uji MCP Server via HTTP; jalankan saat server.py aktif."""
import asyncio
from mcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8105/mcp") as client:
        daftar = await client.list_tools()
        print("Tools tersedia:", [tool.name for tool in daftar.tools])

        hasil = await client.call_tool(
            "cari_referensi_jadwal",
            {"pertanyaan": "Rabu kelas 4 pakai seragam apa?", "kelas": 4},
        )
        if hasil.is_error:
            raise RuntimeError(f"Pencarian gagal: {hasil.content}")
        print("\nHasil pencarian:", hasil.structured_content)

        dokumen = await client.call_tool(
            "ambil_dokumen_referensi", {"document_id": "SIM-JADWAL-004"}
        )
        if dokumen.is_error:
            raise RuntimeError(f"Pengambilan gagal: {dokumen.content}")
        print("\nIsi dokumen:", dokumen.structured_content)


if __name__ == "__main__":
    asyncio.run(main())
