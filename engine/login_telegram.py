"""Login Telegram una tantum: crea il file telegram.session. Esegui con LOGIN_TELEGRAM.bat"""
import asyncio

from telethon import TelegramClient

import config


async def main():
    if not config.TG_API_ID or not config.TG_API_HASH:
        print("Compila prima TG_API_ID e TG_API_HASH nel file .env")
        return
    client = TelegramClient(config.TG_SESSION, config.TG_API_ID, config.TG_API_HASH,
                            device_model="SignalBridge", system_version="Windows")
    await client.start()   # chiede numero di telefono, codice e (se presente) password 2FA
    me = await client.get_me()
    print(f"\nOK! Collegato come {me.first_name}. Ora puoi chiudere e avviare AVVIA.bat")
    await client.disconnect()


asyncio.run(main())
