import asyncio
import os
import traceback
from asyncio import sleep
from asyncio.exceptions import CancelledError

import click
import json

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout


class Client:

    def __enter__(self):
        self.reader = None
        self.writer = None
        self.token = None
        self.username = None
        self.offset_id = 0
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type and exc_type not in (KeyboardInterrupt, SystemExit, CancelledError):
            print(f'exit exception text: {exc_type} {exc_value}')
            print(traceback.print_tb(tb))
        if self.writer and not self.writer.is_closing():
            self.writer.close()
        return True

    async def start(self):
        self.reader, self.writer = await asyncio.open_connection('127.0.0.1', 501)

    async def send_message(self, message):
        request = {
            'route': 'send_message',
            'message': message,
            'token': self.token,
        }
        await self.send_request(request)

    async def get_messages(self):
        request = {
            'route': 'get_messages',
            'offset_id': self.offset_id,
            'token': self.token,
        }
        await self.send_request(request)
        response = await self.receive_response()
        if response:
            if not response['success']:
                raise RuntimeError(response['message'])
            else:
                return json.loads(response['message'])
        else:
            raise RuntimeError("Connection lost")

    async def authorize(self, route, username, password):
        request = {
            'route': route,
            'username': username,
            'password': password
        }
        await self.send_request(request)
        response = await self.receive_response()
        if response:
            if response['success']:
                self.token = response['token']
                self.username = request['username']
            print(response['message'])
            return response['success']
        else:
            raise RuntimeError("Потеряно соединение с сервером")

    async def send_request(self, request):
        # print('send_request', request)
        self.writer.write(json.dumps(request).encode() + b'\0')
        await self.writer.drain()

    async def receive_response(self):
        response = bytearray()
        while True:
            chunk = await self.reader.read(64)
            if not chunk:
                break

            response += chunk
            if b'\0' in response:
                return json.loads(response.replace(b'\0', b'').decode())

        return None


async def main():
    with Client() as client:

        await client.start()

        if click.confirm("Вы уже зарегистрированы?", default=True):
            route = 'login'
        else:
            route = 'register'

        while True:
            username = input("Логин : ")
            password = input("Пароль: ")

            if not await client.authorize(route, username, password):
                if click.confirm("\nПопробуете снова?", default=False):
                    continue
                else:
                    exit(0)
            else:
                break

        print('Вы в чатике!')

        async def recieve_messages():
            while True:
                try:
                    await sleep(0.1)
                    messages = await client.get_messages()
                    if messages:
                        for message in messages:
                            print(f"{message['user']}: {message['msg']}")
                        client.offset_id = messages[-1]['id']
                except Exception as e:
                    print(e)
                    os._exit(0)

        async def send_message():
            try:
                # https://www.cyberforum.ru/python/thread2312091.html
                # https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html#prompt-in-an-asyncio-application
                session = PromptSession()
                with patch_stdout():
                    while True:

                        text = await session.prompt_async('Введите сообщение: ')

                        if '/exit' in str(text):
                            os._exit(0)
                        elif text:
                            await client.send_message(text)
            except Exception as e:
                print(e)
                os._exit(0)

        try:
            await asyncio.gather(
                recieve_messages(),
                send_message()
            )
        except Exception as e:
            print(e)
            os._exit(0)


if __name__ == '__main__':
    asyncio.run(main())
